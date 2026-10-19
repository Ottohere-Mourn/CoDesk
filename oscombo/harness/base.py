"""Harness interface: how one agent drives the shared Guest for one task.

The runner builds one harness per agent, calls ``prepare(ctx)`` (slow setup such as model clients, before the
agents are released together), then ``run(ctx)`` in the agent's own thread. ``run`` returns an ``AgentResult``;
an exception escaping ``run`` is recorded as status ``error`` and the other agents keep going.

Statuses: ``done`` (agent claimed success), ``fail`` (agent claimed the task is infeasible -> the official
evaluator sees a final FAIL action), ``max_steps``, ``timeout``, ``error``.

Trace records (one per step, written to ``trace.jsonl`` with the agent name added) follow
``{"step", "t", "infer_s", "response", "actions": [{"t", "window_before", "code"}], "done", "fail"}``;
``window_before`` (focused window title right before the action) feeds the interference metric.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..guest import Guest


@dataclass
class AgentContext:
    name: str                 # agentA, agentB, ...
    task_id: str
    instruction: str
    guest: Guest
    out: Path                 # run directory, shared by all agents of the run; prefix files with ``name``
    max_steps: int
    spec: dict                # this agent's spec: harness, policy, model, options, ...
    t0: float = 0.0           # agent-phase start; trace times are relative to it
    stop: threading.Event = field(default_factory=threading.Event)  # set by the runner to abort


@dataclass
class AgentResult:
    status: str = "not_started"
    error: str | None = None
    trace: list[dict] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def steps(self) -> int:
        return sum(1 for r in self.trace if "step" in r)


class Harness:
    def __init__(self, spec: dict):
        self.spec = spec

    def prepare(self, ctx: AgentContext) -> None:
        """Optional slow setup before the agents start together."""

    def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError
