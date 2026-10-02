"""Thin ActorContext bridge for the official OSWorld agent protocol."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
from typing import Any, Callable

from .environment import ActorContext


class OSWorldAgentActor:
    """Run a caller-provided OSWorld ``predict`` / ``reset`` agent as one actor.

    Planning, vision grounding, response parsing, and action construction remain
    inside the supplied OSWorld agent. This class only passes screenshots in,
    forwards its native action strings to OSWorld, and records the trace.
    """

    role = "gui"

    def __init__(self, agent: Any, instruction: str, *, actor_id: str = "gui_actor",
                 max_steps: int = 20,
                 event_callback: Callable[[dict[str, Any]], None] | None = None,
                 artifact_directory: Path | None = None,
                 action_boundary_callback: Callable[["OSWorldAgentActor", Any], None] | None = None):
        self.agent = agent
        self.instruction = instruction
        self.actor_id = actor_id
        self.max_steps = max_steps
        self.event_callback = event_callback
        self.action_boundary_callback = action_boundary_callback
        self._pending_actions: list[Any] = []
        self.artifact_directory = (Path(artifact_directory).resolve()
                                   if artifact_directory is not None else None)
        self.trace: list[dict[str, Any]] = []
        self.terminated = False
        self.paused = False
        self.yield_requested = False
        self.steps = 0
        self._started = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def yield_turn(self) -> None:
        """Request that the turn scheduler run another actor before this one."""
        self.yield_requested = True

    def reset(self) -> None:
        """Reset actor-local history and counters; environment reset is scheduler-owned."""
        self.agent.reset()
        self.trace.clear()
        self.terminated = False
        self.paused = False
        self.yield_requested = False
        self.steps = 0
        self._pending_actions.clear()
        self._started = True

    def run_step(self, context: ActorContext) -> bool:
        """Execute one official observe/predict/action batch and return completion."""
        if self.terminated:
            return True
        if self.paused:
            return False
        if not self._started:
            self.reset()
        if self._pending_actions:
            pending, self._pending_actions = self._pending_actions, []
            return self._execute_actions(context, pending)
        if self.steps >= self.max_steps:
            raise RuntimeError(f"OSWorld agent did not terminate within {self.max_steps} steps")
        try:
            observation = context.observe()
        except Exception as exc:
            raise OSWorldAgentActorError("observation", exc) from exc
        screenshot = observation.get("screenshot")
        refreshes = 0
        while (not isinstance(screenshot, bytes) or not screenshot) and refreshes < 3:
            refreshes += 1
            time.sleep(1)
            try:
                observation = context.refresh_observation()
            except Exception as exc:
                raise OSWorldAgentActorError("observation", exc) from exc
            screenshot = observation.get("screenshot")
        if not isinstance(screenshot, bytes) or not screenshot:
            raise OSWorldAgentActorError(
                "observation", RuntimeError(
                    "OSWorld agent received no screenshot bytes after 3 refresh attempts"))
        from PIL import Image
        import io
        with Image.open(io.BytesIO(screenshot)) as image:
            screen_size = list(image.size)
        observation_file = None
        if self.artifact_directory is not None:
            observation_path = (self.artifact_directory / "observations"
                                / f"step-{self.steps + 1:03d}.png")
            observation_path.parent.mkdir(parents=True, exist_ok=True)
            observation_path.write_bytes(screenshot)
            observation_file = str(observation_path.relative_to(
                self.artifact_directory.parent.parent))
        started = time.monotonic()
        previous_cwd = os.getcwd()
        try:
            if self.artifact_directory is not None:
                self.artifact_directory.mkdir(parents=True, exist_ok=True)
                os.chdir(self.artifact_directory)
            response, actions = self.agent.predict(self.instruction, observation)
        except Exception as exc:
            raise OSWorldAgentActorError("model_inference", exc) from exc
        finally:
            if os.getcwd() != previous_cwd:
                os.chdir(previous_cwd)
        inference_ms = round((time.monotonic() - started) * 1000, 2)
        actions = list(actions or [])
        self.steps += 1
        record = {
            "step": self.steps,
            "actor_id": self.actor_id,
            "agent": type(self.agent).__name__,
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "observation_file": observation_file,
            "screen_size": screen_size,
            "observed_revision": context._observed_revision,
            "response": response,
            "native_actions": actions,
            "inference_ms": inference_ms,
            "actor_step_budget": self.max_steps,
            "screenshot_refreshes": refreshes,
        }
        self.trace.append(record)
        if self.event_callback:
            self.event_callback(record)

        self.yield_requested = False
        return self._execute_actions(context, actions)

    def _execute_actions(self, context: ActorContext, actions: list[Any]) -> bool:
        for index, action in enumerate(actions):
            if action == "DONE":
                self.terminated = True
                return True
            if action == "FAIL":
                raise RuntimeError("official OSWorld agent returned FAIL")
            try:
                context.execute_gui_action(action)
            except Exception as exc:
                raise OSWorldAgentActorError("gui_action", exc) from exc
            if self.action_boundary_callback is not None:
                self.action_boundary_callback(self, action)
            if self.paused:
                self._pending_actions = list(actions[index + 1:])
                return False
        if self.steps >= self.max_steps:
            raise RuntimeError(f"OSWorld agent did not terminate within {self.max_steps} steps")
        return False

    def run(self, context: ActorContext) -> None:
        while not self.run_step(context):
            pass


class OSWorldAgentActorError(RuntimeError):
    """Identify whether an agent turn failed at observation, inference, or input."""

    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(f"{stage}: {type(cause).__name__}: {cause}")
