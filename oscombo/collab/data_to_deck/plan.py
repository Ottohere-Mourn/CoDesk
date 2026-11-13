"""Condition/topology contract and independent entrypoint for the manual case."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from . import spec

Condition = Literal["single_agent", "collaborative_isolated", "collaborative_shared"]


@dataclass(frozen=True)
class ConditionPlan:
    condition: Condition
    roles: tuple[str, ...]
    guest_count: int
    desktop_sessions: tuple[str, ...]
    workspace_policy: str
    source_bundle: str
    role_budgets: dict[str, dict[str, int]]
    total_model_token_budget: int
    message_api: bool
    attachment_api: bool
    output_paths: dict[str, str]
    oracle: str = "oscombo.collab.data_to_deck.oracle.evaluate"


def make_plan(condition: Condition, source_bundle: str = "fixture_manifest.json") -> ConditionPlan:
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if condition == "single_agent":
        roles, guests, desktops = ("S",), 1, ("guest-0",)
        workspace = "one actor executes both role interfaces sequentially; local fixture copy"
        budgets = {"S": {"steps": sum(v["steps"] for v in spec.ROLE_BUDGET.values()),
                          "model_tokens": spec.TOTAL_MODEL_TOKEN_BUDGET}}
    elif condition == "collaborative_isolated":
        roles, guests, desktops = ("A", "B"), 2, ("guest-A", "guest-B")
        workspace = "byte-identical source fixtures copied to independent Guest workspaces"
        budgets = {r: dict(spec.ROLE_BUDGET[r]) for r in roles}
    else:
        roles, guests, desktops = ("A", "B"), 1, ("guest-0",)
        workspace = "one Guest and live desktop; per-role output ownership remains separated"
        budgets = {r: dict(spec.ROLE_BUDGET[r]) for r in roles}
    return ConditionPlan(condition, roles, guests, desktops, workspace, source_bundle,
                         budgets,
                         spec.TOTAL_MODEL_TOKEN_BUDGET, True, True, dict(spec.OUTPUTS))


def plan_dict(condition: Condition) -> dict[str, object]:
    return asdict(make_plan(condition))


def validate_live_prerequisites(env: dict[str, str] | None = None) -> list[str]:
    """Return blockers without starting Guests, containers, services, or downloads."""
    import os
    env = env or os.environ
    blockers = []
    if not env.get("OSWORLD_DIR"):
        blockers.append("OSWORLD_DIR is unset; OSWorld Guest provider is not connected")
    if not env.get("OSCOMBO_GUEST_IMAGE"):
        blockers.append("OSCOMBO_GUEST_IMAGE is unset; no pinned Guest image configured")
    return blockers
