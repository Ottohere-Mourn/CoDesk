"""Thin ActorContext bridge for the official OSWorld agent protocol."""
from __future__ import annotations

import hashlib
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
                 event_callback: Callable[[dict[str, Any]], None] | None = None):
        self.agent = agent
        self.instruction = instruction
        self.actor_id = actor_id
        self.max_steps = max_steps
        self.event_callback = event_callback
        self.trace: list[dict[str, Any]] = []
        self.terminated = False

    def run(self, context: ActorContext) -> None:
        self.agent.reset()
        for step in range(1, self.max_steps + 1):
            observation = context.observe()
            screenshot = observation.get("screenshot")
            if not isinstance(screenshot, bytes) or not screenshot:
                raise RuntimeError("OSWorld agent received no screenshot bytes")
            from PIL import Image
            import io
            with Image.open(io.BytesIO(screenshot)) as image:
                screen_size = list(image.size)
            started = time.monotonic()
            response, actions = self.agent.predict(self.instruction, observation)
            inference_ms = round((time.monotonic() - started) * 1000, 2)
            actions = list(actions or [])
            record = {
                "step": step,
                "actor_id": self.actor_id,
                "agent": type(self.agent).__name__,
                "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                "screen_size": screen_size,
                "observed_revision": context._observed_revision,
                "response": response,
                "native_actions": actions,
                "inference_ms": inference_ms,
            }
            self.trace.append(record)
            if self.event_callback:
                self.event_callback(record)

            for action in actions:
                if action == "DONE":
                    self.terminated = True
                    return
                if action == "FAIL":
                    raise RuntimeError("official OSWorld agent returned FAIL")
                context.execute_gui_action(action)
        raise RuntimeError(f"OSWorld agent did not terminate within {self.max_steps} steps")
