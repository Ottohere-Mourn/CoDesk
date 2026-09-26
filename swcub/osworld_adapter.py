"""Thin adapter for OSWorld DesktopEnv without a hard dependency on its package.

Construct a pinned OSWorld DesktopEnv in the caller, then wrap it here. The CLI
executor is injected by the harness so it can run in the same guest/workspace.
"""

from __future__ import annotations

import inspect
import json
import logging
import shlex
from typing import Any, Callable

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
                 window_focus_translator: Callable[[dict[str, Any]], Any] | None = None):
        self.desktop_env = desktop_env
        self.environment_id = f"osworld-{id(desktop_env):x}"
        self.cli_executor = cli_executor
        self.window_focus_translator = window_focus_translator
        self.observation: Any = None
        self.screenshot_history: list[tuple[str, bytes]] = []
        self.revision = 0
        self.actor_steps: dict[str, int] = {}
        super().__init__({})

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
                                 "observation": _digestable(self.observation)})
        screenshot = self.observation.get("screenshot") if isinstance(self.observation, dict) else None
        if isinstance(screenshot, bytes):
            self.screenshot_history.append((f"{len(self.screenshot_history) + 1:02d}-{actor_id}", screenshot))
        return self.observation

    def refresh_observation(self, source: str = "orchestrator") -> Any:
        """Fetch a current Guest screenshot after non-GUI setup operations."""
        getter = getattr(self.desktop_env, "_get_obs", None)
        if not callable(getter):
            raise RuntimeError("DesktopEnv does not expose its observation refresh hook")
        before = self.snapshot()
        self.observation = getter()
        self.log.record(source, "observation", "osworld.refresh_observation",
                        before, self.snapshot(), observed_revision=self.revision,
                        details={"environment_id": self.environment_id,
                                 "guest_container_id": self.snapshot().get("guest_container_id")})
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
        self.log.record("orchestrator", "reset", "osworld.reset", before, self.snapshot(),
                        details={"task_config_id": task_config.get("id") if isinstance(task_config, dict) else None,
                                 "seed": seed,
                                 "guest_container_id": self.snapshot().get("guest_container_id")})
        return self.observation

    def gui_action(self, actor: str, action: Any, pause: float = 2,
                   source_action: Any | None = None,
                   observed_revision: int | None = None) -> Any:
        before = self.snapshot()
        observed_revision = self.revision if observed_revision is None else observed_revision
        self.observation, reward, done, info = self.desktop_env.step(action, pause=pause)
        self.revision += 1
        self.actor_steps[actor] = self.actor_steps.get(actor, 0) + 1
        self.log.record(actor, "gui", "osworld.step", before, self.snapshot(),
                        observed_revision, details={"action": _digestable(action),
                                                    "source_action": _digestable(
                                                        action if source_action is None else source_action),
                                                    "environment_id": self.environment_id,
                                                    "guest_container_id": self.snapshot().get("guest_container_id"),
                                                    "revision_before_action": before["revision"],
                                                    "revision_after_action": self.revision,
                                                    "stale_observation": (observed_revision is not None
                                                                           and observed_revision < before["revision"]),
                                                    "reward": reward, "done": done,
                                                    "info": _digestable(info)})
        return self.observation

    def cli_action(self, actor: str, command: str,
                   observed_revision: int | None = None) -> Any:
        if self.cli_executor is None:
            raise RuntimeError("provide cli_executor bound to the same OSWorld guest workspace")
        before = self.snapshot()
        observed_revision = self.revision if observed_revision is None else observed_revision
        # DesktopEnv marks itself used after GUI steps. A CLI command can mutate
        # the same Guest filesystem without a GUI step, so mark it explicitly to
        # ensure the next reset reverts the VM snapshot too.
        if hasattr(self.desktop_env, "is_environment_used"):
            self.desktop_env.is_environment_used = True
        result = self.cli_executor(command)
        self.revision += 1
        self.actor_steps[actor] = self.actor_steps.get(actor, 0) + 1
        self.log.record(actor, "cli", "shared_guest.command", before, self.snapshot(),
                        observed_revision, details={"command": command,
                                                    "environment_id": self.environment_id,
                                                    "guest_container_id": self.snapshot().get("guest_container_id"),
                                                    "revision_before_action": before["revision"],
                                                    "revision_after_action": self.revision,
                                                    "stale_observation": (observed_revision is not None
                                                                           and observed_revision < before["revision"]),
                                                    "result": _digestable(result)})
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
