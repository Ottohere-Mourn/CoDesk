"""Scripted policy without a model: replays fixed actions, then DONE. For pipeline smoke tests and baselines.

``options.actions``  list of pyautogui code strings (or DONE / FAIL / WAIT); default: none, i.e. DONE at once
``options.file``     json file holding such a list (used when ``actions`` is not given)
``options.delay``    seconds to sleep per step, to imitate model latency (default 0)
"""
from __future__ import annotations

import json
import time
from typing import Any


class ScriptedPolicy:
    def __init__(self, actions: list[str], delay: float = 0.0):
        self.actions, self.delay = list(actions), delay
        self.i = 0

    def reset(self, *_: Any) -> None:
        self.i = 0

    def predict(self, instruction: str, obs: dict[str, Any]) -> tuple[str, list[str]]:
        time.sleep(self.delay)
        if self.i >= len(self.actions):
            return "script finished", ["DONE"]
        action = self.actions[self.i]
        self.i += 1
        return f"scripted step {self.i}", [action]


def make(env: Any, spec: dict) -> ScriptedPolicy:
    opts = spec.get("options", {})
    actions = opts.get("actions")
    if actions is None and opts.get("file"):
        with open(opts["file"], encoding="utf-8") as f:
            actions = json.load(f)
    return ScriptedPolicy(actions or [], float(opts.get("delay", 0)))
