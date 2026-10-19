"""Policy registry. ``make_policy(env, spec)`` builds the policy named by ``spec["policy"]``.

Built-in names are listed in ``POLICIES``. Out-of-tree policies need no registration: give
``"policy": "my_pkg.my_module:make"`` where ``make(env, spec)`` returns an object with ``reset()`` and
``predict(instruction, obs) -> (response, actions)`` (see ``base.py``).
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

POLICIES: dict[str, str] = {
    "openai-cua": "oscombo.policies.openai_cua:make",
    "chat-pyautogui": "oscombo.policies.osworld_agents:make_chat_pyautogui",
    "responses-pyautogui": "oscombo.policies.osworld_agents:make_responses_pyautogui",
    "osworld-agent": "oscombo.policies.osworld_agents:make_osworld_agent",
    "scripted": "oscombo.policies.scripted:make",
}


def resolve(name: str) -> Callable[[Any, dict], Any]:
    target = POLICIES.get(name, name)
    module, sep, attr = target.partition(":")
    if not sep:
        raise ValueError(f"unknown policy {name!r}; built-in: {sorted(POLICIES)} or 'module:factory'")
    return getattr(importlib.import_module(module), attr)


def make_policy(env: Any, spec: dict) -> Any:
    return resolve(spec["policy"])(env, spec)
