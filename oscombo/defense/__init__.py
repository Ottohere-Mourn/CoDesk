"""Pluggable per-harness defenses for agents sharing one desktop (paraGUI attack/defense rounds).

A defense lives *inside one agent's harness*. Rules (enforced partly here, audited by the lead for the rest):
  1. Per harness only: no shared state, lock, file or channel between the two harnesses; each harness knows nothing
     about the other agent or its task (a real product cannot assume it controls the other assistant).
  2. The model must never be told that another agent/user exists or what anyone else is doing. Instruction addenda and
     notices are checked against FORBIDDEN below and dropped (and counted as violations) if they match.
  3. General: the same code path for every task -- no task ids, file names, URLs or per-task app lists. App-class
     mechanisms (e.g. "a harness always uses its own browser instance") are allowed when applied uniformly.
  4. Must not hurt performance alone: solo/sequential scores must not drop and overhead must stay small.
  5. Must not touch task setup, assets or checkers.

Select with `--defense NAME` (a module of this package, e.g. ``v1``, or ``pkg.module`` for your own); the module
defines `class Defense(DefenseBase)`. Hooks are called by the step harness (oscombo/harness/step_loop.py) in every
shared-Guest mode (solo, sequential, parallel, shadow).
"""
from __future__ import annotations

import importlib
import re
from typing import Any

FORBIDDEN = re.compile(r"\bagents?\b|another (user|person|program|assistant|process)|other (user|person|assistant|"
                       r"program)|someone|somebody|concurren|simultaneous|shared desktop|colleague|second (user|"
                       r"assistant)|interfer", re.I)


class DefenseBase:
    """No-op defense; subclasses override hooks. `guest_sh(cmd)` runs a shell command in the Guest."""

    def __init__(self, env: Any, name: str, guest_sh) -> None:
        self.env, self.name, self.guest_sh = env, name, guest_sh
        self.stats: dict[str, Any] = {}

    def start(self, setup_windows: set[str]) -> None:
        """Before the agent's first step. setup_windows: X window ids that appeared during this agent's task setup."""

    def instruction(self, text: str) -> str:
        """Return the instruction given to the model (may append generic, task-independent guidance)."""
        return text

    def before_observe(self) -> None:
        """Right before each screenshot."""

    def observe(self, png: bytes) -> bytes:
        """May post-process the screenshot the model sees."""
        return png

    def transform_action(self, code: str) -> str | None:
        """pyautogui code about to run in the Guest; return replacement code, or None to skip it."""
        return code

    def after_action(self, code: str, record: dict) -> None:
        """After an action ran (record holds t, window_before, code)."""

    def notice(self) -> str | None:
        """Optional generic text for the model, sent with the next observation."""
        return None


def load(name: str):
    mod = importlib.import_module(name if "." in name else f"oscombo.defense.{name}")
    return mod.Defense


def clean_text(text: str | None, stats: dict) -> str | None:
    """Drop instruction addenda / notices that would reveal other agents (rule 2)."""
    if text and FORBIDDEN.search(text):
        stats["rule2_violations"] = stats.get("rule2_violations", 0) + 1
        return None
    return text
