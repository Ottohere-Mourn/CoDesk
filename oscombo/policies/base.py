"""Policy interface: the model that picks the next action inside the step-loop harness.

A policy is anything with

    reset() -> None
    predict(instruction: str, obs: dict) -> (raw_response, actions)

which is exactly the interface of the official OSWorld ``mm_agents`` agents, so most of them plug in as is
(see ``osworld_agents.py``). ``obs`` holds ``screenshot`` (PNG bytes) and, if the policy sets
``needs_a11y = True``, ``accessibility_tree``. ``actions`` is a list of pyautogui code strings and/or the
special actions ``DONE`` / ``FAIL`` / ``WAIT``, either as strings or as OSWorld action dicts.
"""
from __future__ import annotations

from typing import Any, Protocol

SPECIAL = ("DONE", "FAIL", "WAIT")


class Policy(Protocol):
    def reset(self) -> None: ...

    def predict(self, instruction: str, obs: dict[str, Any]) -> tuple[Any, list[Any]]: ...


def normalize_action(action: Any) -> str:
    """One returned action -> "DONE" | "FAIL" | "WAIT" | pyautogui code."""
    if isinstance(action, str):
        return action.strip() if action.strip() in SPECIAL else action
    if isinstance(action, dict):
        kind = action.get("action_type")
        if kind in SPECIAL:
            return kind
        for key in ("action", "command", "code"):
            if isinstance(action.get(key), str):
                return action[key]
    raise ValueError(f"cannot turn {action!r} into a pyautogui action")


def require_model(spec: dict) -> str:
    if not spec.get("model"):
        raise ValueError(f"policy {spec.get('policy')!r} needs a model name (--model or \"model\" in the spec)")
    return spec["model"]


def response_text(response: Any) -> Any:
    """Short loggable form of a policy's raw response."""
    if isinstance(response, dict):
        return response.get("response", response)
    return response
