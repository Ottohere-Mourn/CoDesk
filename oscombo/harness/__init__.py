"""Harness registry. ``make_harness(spec)`` builds the harness named by ``spec["harness"]`` (default "step").

Built-in: ``step`` (official OSWorld-style loop around a policy, see ``oscombo.policies``), ``command`` (any
external program), ``codex`` (codex CLI + desktop MCP tools), ``pi`` (pi agent + the same tools as an
extension). Out-of-tree: ``"harness": "pkg.module:Class"`` with a ``Harness`` subclass (see ``base.py``).
"""
from __future__ import annotations

import importlib

from .base import AgentContext, AgentResult, Harness

HARNESSES: dict[str, str] = {
    "step": "oscombo.harness.step_loop:StepLoopHarness",
    "command": "oscombo.harness.external:CommandHarness",
    "codex": "oscombo.harness.external:CodexHarness",
    "pi": "oscombo.harness.external:PiHarness",
}


def make_harness(spec: dict) -> Harness:
    name = spec.get("harness", "step")
    module, sep, attr = HARNESSES.get(name, name).partition(":")
    if not sep:
        raise ValueError(f"unknown harness {name!r}; built-in: {sorted(HARNESSES)} or 'module:Class'")
    return getattr(importlib.import_module(module), attr)(spec)


__all__ = ["AgentContext", "AgentResult", "Harness", "HARNESSES", "make_harness"]
