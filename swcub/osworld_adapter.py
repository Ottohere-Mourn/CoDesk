"""Thin adapter for OSWorld DesktopEnv without a hard dependency on its package.

Construct a pinned OSWorld DesktopEnv in the caller, then wrap it here. The CLI
executor is injected by the harness so it can run in the same guest/workspace.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import shlex
import time
from typing import Any, Callable
import xml.etree.ElementTree as ET

from .core import Episode


def _digestable(value: Any) -> Any:
    """Reduce common OSWorld observations to stable metadata before hashing."""
    if isinstance(value, bytes):
        from hashlib import sha256
        return {"bytes_sha256": sha256(value).hexdigest(), "length": len(value)}
    if isinstance(value, dict):
        return {str(k): _digestable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_digestable(v) for v in value]
    if hasattr(value, "tobytes") and hasattr(value, "shape"):
        from hashlib import sha256
        data = value.tobytes()
        return {"array_sha256": sha256(data).hexdigest(), "shape": list(value.shape),
                "dtype": str(getattr(value, "dtype", "unknown"))}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"type": type(value).__name__, "repr": repr(value)[:300]}


class OSWorldSharedEpisode(Episode):
    """One OSWorld desktop plus injected CLI access to its same guest workspace.

    ActorContext text/key/submit operations become PyAutoGUI command strings.
    Window focus is application-specific and requires a ``window_focus_translator``.
    """

    def __init__(self, desktop_env: Any,
                 cli_executor: Callable[[str], Any] | None = None,
                 window_focus_translator: Callable[[dict[str, Any]], Any] | None = None,
                 clipboard_sampler: Any | None = None,
                 require_clipboard_observer: bool = False,
                 clipboard_actor_payload_digests: dict[str, str] | None = None):
        self.desktop_env = desktop_env
        self.environment_id = f"osworld-{id(desktop_env):x}"
        self.cli_executor = cli_executor
        self.window_focus_translator = window_focus_translator
        self.clipboard_sampler = clipboard_sampler
        self.require_clipboard_observer = require_clipboard_observer
        self.clipboard_actor_payload_digests = dict(clipboard_actor_payload_digests or {})
        self.clipboard_observer_health: dict[str, Any] = {
            "enabled": clipboard_sampler is not None,
            "valid": clipboard_sampler is not None,
            "samples": 0,
            "failures": 0,
        }
        # Local import keeps the legacy OSWorld adapter independent unless a
        # clipboard task explicitly opts into private selection instrumentation.
        if clipboard_sampler is not None:
            from .clipboard_observer import ClipboardEventTracker
            self._clipboard_tracker = ClipboardEventTracker()
        else:
            self._clipboard_tracker = None
        self.observation: Any = None
        self.screenshot_history: list[tuple[str, bytes]] = []
        self.revision = 0
        self.actor_steps: dict[str, int] = {}
        self._revision_actors: list[str] = []
        self.environment_health: dict[str, Any] = {
            "observation_refresh_attempts": 0,
            "observation_transient_failures": 0,
            "accessibility_tree_failures": 0,
        }
        super().__init__({})

    def _active_window_title(self) -> str | None:
        """Extract the publicly visible focused window from OSWorld's UI tree."""
        if not isinstance(self.observation, dict):
            return None
        tree = self.observation.get("accessibility_tree")
        if not isinstance(tree, str):
            return None
        match = re.search(r'<frame name="([^"]+)"[^>]*st:active="true"', tree)
        return match.group(1) if match else None

    def attach_clipboard_sampler(self, sampler: Any, *,
                                 actor_payload_digests: dict[str, str] | None = None,
                                 required: bool = True) -> None:
        """Opt this episode into hidden clipboard instrumentation before actors run."""
        if self.actor_steps:
            raise RuntimeError("clipboard observer must be attached before actor actions")
        from .clipboard_observer import ClipboardEventTracker
        self.clipboard_sampler = sampler
        self.require_clipboard_observer = required
        self.clipboard_actor_payload_digests = dict(actor_payload_digests or {})
        self._clipboard_tracker = ClipboardEventTracker()
        self.clipboard_observer_health.update({"enabled": True, "valid": True,
                                               "samples": 0, "failures": 0})

    def _clipboard_sample(self, actor: str, phase: str,
                          source_action: Any = None) -> dict[str, Any] | None:
        """Log hidden evaluator-side clipboard state without returning it to actors."""
        if self.clipboard_sampler is None:
            return None
        before = self.clipboard_observer_health.copy()
        try:
            raw = self.clipboard_sampler.sample()
            event = self._clipboard_tracker.record(raw, actor_id=actor,
                                                   source_action=source_action,
                                                   phase=phase,
                                                   expected_payload_sha256=(
                                                       self.clipboard_actor_payload_digests.get(actor)))
            event["paste_target"] = self._focused_accessibility_target()
            self.clipboard_observer_health["samples"] += 1
            after = self.clipboard_observer_health.copy()
            self.log.record("clipboard_observer", "instrumentation", "clipboard.sample",
                            before, after, outcome="ok",
                            details={**event, "source_actor": actor})
            return event
        except Exception as exc:
            self.clipboard_observer_health["valid"] = False
            self.clipboard_observer_health["failures"] += 1
            after = self.clipboard_observer_health.copy()
            self.log.record("clipboard_observer", "instrumentation", "clipboard.sample",
                            before, after, outcome="unavailable",
                            details={"phase": phase, "source_actor": actor,
                                     "error": f"{type(exc).__name__}: {exc}"})
            if self.require_clipboard_observer:
                raise RuntimeError("required clipboard observer unavailable") from exc
            return None

    def _focused_accessibility_target(self) -> dict[str, Any] | None:
        """Return the most specific focused editable a11y node, without text content."""
        if not isinstance(self.observation, dict):
            return None
        tree = self.observation.get("accessibility_tree")
        if not isinstance(tree, str) or not tree.strip():
            return None
        try:
            root = ET.fromstring(tree)
        except ET.ParseError:
            return None
        state_ns = "https://accessibility.ubuntu.example.org/ns/state"
        attr_ns = "https://accessibility.ubuntu.example.org/ns/attributes"
        component_ns = "https://accessibility.ubuntu.example.org/ns/component"
        candidates = []
        for node in root.iter():
            if node.get(f"{{{state_ns}}}focused") != "true":
                continue
            editable = node.get(f"{{{state_ns}}}editable") == "true"
            focusable = node.get(f"{{{state_ns}}}focusable") == "true"
            if not editable and not focusable:
                continue
            candidates.append({"role": node.tag.rsplit("}", 1)[-1],
                               "name": node.get("name") or None,
                               "toolkit": node.get(f"{{{attr_ns}}}toolkit"),
                               "editable": editable, "focusable": focusable,
                               "coordinates": node.get(f"{{{component_ns}}}screencoord"),
                               "size": node.get(f"{{{component_ns}}}size")})
        if not candidates:
            return None
        # Accessibility trees report inherited focused state on ancestors too;
        # the last eligible node in document order is normally the leaf widget.
        return {**candidates[-1], "availability": "focused_accessibility_node"}

    def snapshot(self) -> Any:
        provider = getattr(self.desktop_env, "provider", None)
        guest_container = getattr(provider, "container", None)
        container_id = getattr(guest_container, "id", None)
        return {"revision": self.revision,
                "observation": _digestable(self.observation),
                "actor_steps": dict(self.actor_steps),
                "environment_id": self.environment_id,
                "guest_container_id": container_id}

    def observe(self, actor_id: str, interface: str = "gui") -> Any:
        if interface != "gui":
            raise ValueError(f"OSWorld observation does not support interface {interface!r}")
        if self.observation is None:
            raise RuntimeError("reset the OSWorld episode before observing")
        self.log.record(actor_id, "observation", "osworld.observe", self.snapshot(), self.snapshot(),
                        observed_revision=self.revision,
                        details={"environment_id": self.environment_id,
                                 "guest_container_id": self.snapshot().get("guest_container_id"),
                                 "active_window_title": self._active_window_title(),
                                 "observation": _digestable(self.observation)})
        screenshot = self.observation.get("screenshot") if isinstance(self.observation, dict) else None
        if isinstance(screenshot, bytes):
            self.screenshot_history.append((f"{len(self.screenshot_history) + 1:02d}-{actor_id}", screenshot))
        return self.observation

    def refresh_observation(self, source: str = "orchestrator") -> Any:
        """Fetch a current observation, retrying transient missing accessibility data.

        Readiness/observation health is infrastructure state. This retry does not
        alter actions, actor order, or evaluator decisions. If the pinned OSWorld
        service remains unavailable, fail before actors consume an unattributable
        observation and let the runner preserve artifacts and close the Guest.
        """
        getter = getattr(self.desktop_env, "_get_obs", None)
        if not callable(getter):
            raise RuntimeError("DesktopEnv does not expose its observation refresh hook")
        before = self.snapshot()
        max_attempts = 3
        last_reason = "missing screenshot"
        for attempt in range(1, max_attempts + 1):
            self.environment_health["observation_refresh_attempts"] += 1
            self.observation = getter()
            screenshot = self.observation.get("screenshot") if isinstance(self.observation, dict) else None
            require_tree = bool(getattr(self.desktop_env, "require_a11y_tree", False))
            tree = self.observation.get("accessibility_tree") if isinstance(self.observation, dict) else None
            screenshot_ok = isinstance(screenshot, bytes) and bool(screenshot)
            tree_ok = (not require_tree) or (isinstance(tree, str) and bool(tree.strip()))
            if screenshot_ok and tree_ok:
                break
            self.environment_health["observation_transient_failures"] += 1
            if require_tree and not tree_ok:
                self.environment_health["accessibility_tree_failures"] += 1
                last_reason = "accessibility tree missing after OSWorld observation request"
            elif not screenshot_ok:
                last_reason = "screenshot missing after OSWorld observation request"
            self.log.record(source, "healthcheck", "osworld.observation_retry",
                            before, self.snapshot(), outcome="retry",
                            details={"attempt": attempt, "max_attempts": max_attempts,
                                     "reason": last_reason,
                                     "guest_container_id": self.snapshot().get("guest_container_id")})
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
        else:
            raise RuntimeError(f"OSWorld observation health check failed: {last_reason}")

        screenshot = self.observation.get("screenshot") if isinstance(self.observation, dict) else None
        if isinstance(screenshot, bytes) and screenshot:
            self.screenshot_history.append(
                (f"refresh-{len(self.screenshot_history) + 1:02d}-{source}", screenshot))
        self.log.record(source, "observation", "osworld.refresh_observation",
                        before, self.snapshot(), observed_revision=self.revision,
                        details={"environment_id": self.environment_id,
                                 "guest_container_id": self.snapshot().get("guest_container_id"),
                                 "refresh_attempts": attempt,
                                 "accessibility_tree_available": (
                                     isinstance(self.observation.get("accessibility_tree"), str)
                                     and bool(self.observation["accessibility_tree"].strip())
                                     if isinstance(self.observation, dict) else False)})
        return self.observation

    def act(self, actor_id: str, interface: str, action: Any,
            observed_revision: int | None = None) -> Any:
        if interface == "gui":
            osworld_action = self._translate_gui_operation(action)
            return self.gui_action(actor_id, osworld_action, source_action=action,
                                   observed_revision=observed_revision)
        if interface == "cli":
            command = shlex.join(list(map(str, action))) if isinstance(action, (list, tuple)) else str(action)
            return self.cli_action(actor_id, command, observed_revision)
        raise ValueError(f"unsupported OSWorld interface: {interface}")

    def _translate_gui_operation(self, action: Any) -> Any:
        """Translate ActorContext operations while preserving native OSWorld actions."""
        if not isinstance(action, dict) or "op" not in action:
            return action
        operation = action["op"]
        if operation == "type" and isinstance(action.get("value"), str):
            return f"pyautogui.write({json.dumps(action['value'], ensure_ascii=False)})"
        if operation == "key" and isinstance(action.get("key"), str):
            raw_key = action["key"].lower()
            if "+" in raw_key:
                keys = [part.strip() for part in raw_key.split("+")]
                keys = [{"ctrl": "ctrl", "control": "ctrl", "return": "enter"}.get(key, key)
                        for key in keys]
                return "pyautogui.hotkey(" + ", ".join(json.dumps(key) for key in keys) + ")"
            key = {"return": "enter", "esc": "escape", "backspace": "backspace"}.get(
                raw_key, raw_key)
            return f"pyautogui.press({json.dumps(key)})"
        if operation == "submit" and isinstance(action.get("value"), str):
            value = json.dumps(action["value"], ensure_ascii=False)
            return f"pyautogui.write({value}); pyautogui.press('enter')"
        if operation == "click" and type(action.get("x")) is int and type(action.get("y")) is int:
            return f"pyautogui.click({action['x']}, {action['y']})"
        if operation == "focus":
            if self.window_focus_translator is not None:
                return self.window_focus_translator(action)
            raise NotImplementedError(
                "window focus is application-specific; provide window_focus_translator")
        raise ValueError(f"unsupported GUI operation for OSWorld: {action!r}")

    def close(self) -> None:
        self.desktop_env.close()

    def reset(self, task_config: dict[str, Any], seed: int | None = None) -> Any:
        before = self.snapshot()
        self.observation = self.desktop_env.reset(task_config=task_config, seed=seed)
        self.revision = 0
        self.actor_steps.clear()
        self._revision_actors.clear()
        if self._clipboard_tracker is not None:
            self._clipboard_tracker.reset()
            self.clipboard_observer_health.update({"valid": True, "samples": 0,
                                                   "failures": 0})
        self.log.record("orchestrator", "reset", "osworld.reset", before, self.snapshot(),
                        details={"task_config_id": task_config.get("id") if isinstance(task_config, dict) else None,
                                 "seed": seed,
                                 "guest_container_id": self.snapshot().get("guest_container_id")})
        return self.observation

    def gui_action(self, actor: str, action: Any, pause: float = 2,
                   source_action: Any | None = None,
                   observed_revision: int | None = None) -> Any:
        before = self.snapshot()
        active_window_before = self._active_window_title()
        observed_revision = self.revision if observed_revision is None else observed_revision
        intervening_actors = self._revision_actors[observed_revision: self.revision]
        self._clipboard_sample(actor, "before_action", source_action or action)
        self.observation, reward, done, info = self.desktop_env.step(action, pause=pause)
        active_window_after = self._active_window_title()
        self.revision += 1
        self._revision_actors.append(actor)
        self.actor_steps[actor] = self.actor_steps.get(actor, 0) + 1
        self.log.record(actor, "gui", "osworld.step", before, self.snapshot(),
                        observed_revision, details={"action": _digestable(action),
                                                    "source_action": _digestable(
                                                        action if source_action is None else source_action),
                                                    "environment_id": self.environment_id,
                                                    "guest_container_id": self.snapshot().get("guest_container_id"),
                                                    "revision_before_action": before["revision"],
                                                    "revision_after_action": self.revision,
                                                    "active_window_before": active_window_before,
                                                    "active_window_after": active_window_after,
                                                    "stale_observation": (observed_revision is not None
                                                                           and observed_revision < before["revision"]),
                                                    "stale_due_other_actor": any(
                                                        other_actor != actor
                                                        for other_actor in intervening_actors),
                                                    "intervening_action_actors": intervening_actors,
                                                    "reward": reward, "done": done,
                                                    "info": _digestable(info)})
        self._clipboard_sample(actor, "after_action", source_action or action)
        return self.observation

    def cli_action(self, actor: str, command: str,
                   observed_revision: int | None = None) -> Any:
        if self.cli_executor is None:
            raise RuntimeError("provide cli_executor bound to the same OSWorld guest workspace")
        before = self.snapshot()
        observed_revision = self.revision if observed_revision is None else observed_revision
        intervening_actors = self._revision_actors[observed_revision: self.revision]
        # DesktopEnv marks itself used after GUI steps. A CLI command can mutate
        # the same Guest filesystem without a GUI step, so mark it explicitly to
        # ensure the next reset reverts the VM snapshot too.
        if hasattr(self.desktop_env, "is_environment_used"):
            self.desktop_env.is_environment_used = True
        self._clipboard_sample(actor, "before_action", command)
        result = self.cli_executor(command)
        self.revision += 1
        self._revision_actors.append(actor)
        self.actor_steps[actor] = self.actor_steps.get(actor, 0) + 1
        self.log.record(actor, "cli", "shared_guest.command", before, self.snapshot(),
                        observed_revision, details={"command": command,
                                                    "environment_id": self.environment_id,
                                                    "guest_container_id": self.snapshot().get("guest_container_id"),
                                                    "revision_before_action": before["revision"],
                                                    "revision_after_action": self.revision,
                                                    "stale_observation": (observed_revision is not None
                                                                           and observed_revision < before["revision"]),
                                                    "stale_due_other_actor": any(
                                                        other_actor != actor
                                                        for other_actor in intervening_actors),
                                                    "intervening_action_actors": intervening_actors,
                                                    "result": _digestable(result)})
        self._clipboard_sample(actor, "after_action", command)
        return result

    def evaluate_osworld_task(self) -> float:
        """Delegate to OSWorld's evaluator, including its required eval logger."""
        evaluate = self.desktop_env.evaluate
        eval_logger = logging.getLogger("swcub.osworld.evaluator")
        try:
            signature = inspect.signature(evaluate)
        except (TypeError, ValueError):
            # DesktopEnv's Python implementation accepts the logger. Preserve that
            # official call shape if a wrapped callable does not expose a signature.
            return float(evaluate(eval_logger))
        try:
            signature.bind(eval_logger)
        except TypeError:
            signature.bind()
            return float(evaluate())
        return float(evaluate(eval_logger))

    def copy_artifacts(self, out: Any) -> None:
        """Save the latest real Guest screenshot with the episode artifacts."""
        from pathlib import Path
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        screenshot = self.observation.get("screenshot") if isinstance(self.observation, dict) else None
        if isinstance(screenshot, bytes):
            (out / "guest-screen.png").write_bytes(screenshot)
        for name, image_bytes in self.screenshot_history:
            (out / f"observation-{name}.png").write_bytes(image_bytes)
