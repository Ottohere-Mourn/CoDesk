"""Offline CoDesk V1 task registry validation and declarative oracle helpers.

This module deliberately does not create Guests or start applications. It validates
task contracts and evaluates already-captured authoritative state/event data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CONDITIONS = {"solo", "ma_id", "ma_sd"}
REQUIRED_TASK_FIELDS = {
    "task_id", "version", "family", "status", "actors", "initial_state",
    "shared_resources", "interaction", "joint_feasibility", "conditions",
    "evaluator", "attribution", "recovery", "reset", "references",
}


class TaskRegistryError(ValueError):
    """Raised when a task definition is incomplete or internally inconsistent."""


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_registry(data)
    return data


def validate_registry(registry: Any) -> dict[str, int]:
    errors: list[str] = []
    if not isinstance(registry, dict):
        raise TaskRegistryError("registry root must be an object")
    if registry.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    tasks = registry.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty array")
        tasks = []
    ids: set[str] = set()
    families: set[str] = set()
    for i, task in enumerate(tasks):
        p = f"tasks[{i}]"
        if not isinstance(task, dict):
            errors.append(f"{p} must be an object")
            continue
        for field in REQUIRED_TASK_FIELDS - set(task):
            errors.append(f"{p}.{field} is required")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{p}.task_id must be a non-empty string")
        elif task_id in ids:
            errors.append(f"duplicate task_id: {task_id}")
        else:
            ids.add(task_id)
        family = task.get("family")
        if isinstance(family, str):
            families.add(family)
        status = task.get("status")
        if status not in {"scripted_anchor", "registered_anchor", "design_only"}:
            errors.append(f"{p}.status is not a supported evidence status")
        actors = task.get("actors")
        if not isinstance(actors, dict) or len(actors) != 2:
            errors.append(f"{p}.actors must define exactly two independent actors")
            actors = {}
        actor_ids = set(actors)
        for actor_id, actor in actors.items():
            if not isinstance(actor_id, str) or not isinstance(actor, dict):
                errors.append(f"{p}.actors entries must map actor IDs to objects")
                continue
            if not isinstance(actor.get("modality"), str) or not actor.get("modality"):
                errors.append(f"{p}.actors.{actor_id}.modality is required")
            if not isinstance(actor.get("goal"), str) or not actor.get("goal"):
                errors.append(f"{p}.actors.{actor_id}.goal is required")
            if not actor.get("oracle_checks"):
                errors.append(f"{p}.actors.{actor_id}.oracle_checks must be non-empty")
        if not isinstance(task.get("initial_state"), dict) or not task["initial_state"]:
            errors.append(f"{p}.initial_state must be a non-empty object")
        if not isinstance(task.get("shared_resources"), list) or not task["shared_resources"]:
            errors.append(f"{p}.shared_resources must be non-empty")
        interaction = task.get("interaction")
        if not isinstance(interaction, dict) or not interaction.get("mechanism"):
            errors.append(f"{p}.interaction.mechanism is required")
        elif not interaction.get("ma_sd_path"):
            errors.append(f"{p}.interaction.ma_sd_path must describe an organic interaction")
        if task.get("joint_feasibility", {}).get("feasible") is not True:
            errors.append(f"{p}.joint_feasibility.feasible must be true")
        conditions = task.get("conditions")
        if not isinstance(conditions, dict) or set(conditions) != CONDITIONS:
            errors.append(f"{p}.conditions must define solo, ma_id, and ma_sd")
        else:
            for condition, spec in conditions.items():
                if (not isinstance(spec, dict) or not spec.get("control")
                        or not spec.get("topology") or not spec.get("backend_binding")):
                    errors.append(
                        f"{p}.conditions.{condition} needs control, topology, and backend_binding")
            if (isinstance(conditions.get("ma_id"), dict)
                    and isinstance(conditions.get("ma_sd"), dict)
                    and conditions["ma_id"].get("backend_binding")
                    != conditions["ma_sd"].get("backend_binding")):
                errors.append(
                    f"{p}.conditions MA-ID and MA-SD must hold application backend constant")
        evaluator = task.get("evaluator")
        if not isinstance(evaluator, dict) or not evaluator.get("oracle") or not evaluator.get("checks"):
            errors.append(f"{p}.evaluator needs an objective oracle and exact checks")
        attribution = task.get("attribution")
        if not isinstance(attribution, dict) or not attribution.get("supported_when"):
            errors.append(f"{p}.attribution.supported_when is required")
        if not isinstance(task.get("recovery"), dict) or not task["recovery"].get("opportunity"):
            errors.append(f"{p}.recovery.opportunity is required")
        if not isinstance(task.get("reset"), dict) or not task["reset"].get("verification"):
            errors.append(f"{p}.reset.verification is required")
        if not isinstance(task.get("references"), list):
            errors.append(f"{p}.references must be an array")
    if len(families) > 4:
        errors.append("V1 must have at most four task families")
    if errors:
        raise TaskRegistryError("; ".join(errors))
    return {"tasks": len(tasks), "families": len(families),
            "design_only": sum(t["status"] == "design_only" for t in tasks)}


def validate_suite_config(config: Any, registry: dict[str, Any]) -> dict[str, int]:
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise TaskRegistryError("suite config schema_version must be 1")
    if config.get("execution_mode") != "offline_contract_review":
        raise TaskRegistryError("this V1 config is review-only; live execution is not enabled")
    if config.get("guest_launch_allowed") is not False or config.get("model_launch_allowed") is not False:
        raise TaskRegistryError("offline V1 config must explicitly disable Guest and model launches")
    task_ids = config.get("task_ids")
    known = {task["task_id"] for task in registry["tasks"]}
    if not isinstance(task_ids, list) or not task_ids or len(set(task_ids)) != len(task_ids):
        raise TaskRegistryError("task_ids must be a non-empty unique array")
    unknown = set(task_ids) - known
    if unknown:
        raise TaskRegistryError(f"unknown task IDs: {sorted(unknown)}")
    if set(config.get("conditions", [])) != CONDITIONS:
        raise TaskRegistryError("suite config must list Solo, MA-ID, and MA-SD")
    return {"selected_tasks": len(task_ids), "conditions": len(CONDITIONS)}


def initial_state_fixture(task: dict[str, Any]) -> dict[str, Any]:
    """Return a detached seed state for an adapter-specific setup implementation."""
    return json.loads(json.dumps(task["initial_state"]))


def verify_reset(task: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    """Check exact reset state. Caller supplies private authoritative state."""
    expected = task["initial_state"]
    passed = actual_state == expected
    return {"success": passed, "expected": expected, "actual": actual_state,
            "difference_keys": sorted(set(expected) | set(actual_state)) if not passed else []}


def evaluate_exact_state(task: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Apply declarative dotted-path checks to hidden authoritative state.

    `actual` is expected to come from the private evaluator callback, never ActorContext.
    """
    checks: list[dict[str, Any]] = []
    for actor_id, actor in task["actors"].items():
        for check in actor["oracle_checks"]:
            path = check["path"]
            got = _get_path(actual, path)
            passed = got == check["equals"]
            checks.append({"actor_id": actor_id, "path": path, "expected": check["equals"],
                           "actual": got, "success": passed})
    for check in task["evaluator"].get("invariants", []):
        got = _get_path(actual, check["path"])
        checks.append({"actor_id": None, "path": check["path"], "expected": check["equals"],
                       "actual": got, "success": got == check["equals"]})
    actor_results = {actor_id: all(c["success"] for c in checks if c["actor_id"] == actor_id)
                     for actor_id in task["actors"]}
    return {"actor_success": actor_results, "joint_success": bool(checks) and all(
        item["success"] for item in checks), "checks": checks}


def interaction_metrics(events: list[dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
    """Derive auditable interaction/recovery counts without assigning unsupported causes."""
    ordered = sorted(events, key=lambda e: e.get("sequence", 0))
    focus_changes = sum(e.get("kind") == "state_change" and e.get("resource") == "focus"
                        and e.get("before") != e.get("after") for e in ordered)
    invalid_actions = sum(e.get("kind") == "action" and e.get("outcome") in
                          {"invalid", "rejected", "error"} for e in ordered)
    actions_by_actor: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    last_observation: dict[str, dict[str, Any]] = {}
    for event in ordered:
        actor = event.get("actor_id")
        if event.get("kind") == "observation" and actor:
            last_observation[actor] = event
            continue
        if event.get("kind") != "action" or not actor:
            continue
        actions_by_actor[actor] = actions_by_actor.get(actor, 0) + 1
        observed = event.get("observed_revision")
        obs = last_observation.get(actor)
        if obs and type(observed) is int and type(event.get("current_revision")) is int:
            intervening = [change for change in ordered
                           if obs.get("sequence", 0) < change.get("sequence", 0)
                           < event.get("sequence", 0)
                           and change.get("kind") == "state_change"
                           and change.get("actor_id") != actor
                           and change.get("resource") in task["shared_resources"]]
            if intervening and observed < event["current_revision"]:
                conflicts.append({"actor_id": actor, "observation_sequence": obs.get("sequence"),
                                  "action_sequence": event.get("sequence"),
                                  "intervening_sequences": [x.get("sequence") for x in intervening],
                                  "classification": "evidence_supported_staleness"})
    recovery_steps: dict[str, int] = {}
    for conflict in conflicts:
        actor = conflict["actor_id"]
        after = [e for e in ordered if e.get("actor_id") == actor
                 and e.get("kind") == "action" and e.get("sequence", 0) > conflict["action_sequence"]]
        recovery = next((e for e in after if e.get("details", {}).get("recovery") is True), None)
        if recovery:
            recovery_steps[actor] = recovery_steps.get(actor, 0) + sum(
                e.get("actor_id") == actor and e.get("kind") == "action"
                and conflict["action_sequence"] < e.get("sequence", 0) <= recovery.get("sequence", 0)
                for e in ordered)
    return {"focus_transition_count": focus_changes, "invalid_action_count": invalid_actions,
            "action_count_by_actor": actions_by_actor, "evidence_supported_conflicts": conflicts,
            "recovery_steps_by_actor": recovery_steps,
            "unattributed_failures": "must be decided by comparing oracle result and event evidence"}


def summarize_episode_outcomes(evaluator: dict[str, Any],
                               events: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep resource exposure, terminal failure, and recovery as separate outcomes.

    Exposure is counted only from explicit observer events. A scheduled opportunity is
    a denominator, not a failure or an assertion that interference actually occurred.
    """
    ordered = sorted(events, key=lambda e: e.get("sequence", 0))
    opportunities = [e for e in ordered if e.get("kind") == "exposure_opportunity"]
    exposures = [e for e in ordered if e.get("kind") == "interference_exposure"]
    sources = ("natural", "scheduled_stress")
    exposure_counts = {}
    opportunity_counts = {}
    exposure_event_counts = {}
    for source in sources:
        opportunity_ids = {e.get("opportunity_id") for e in opportunities
                           if e.get("source") == source and e.get("opportunity_id")}
        exposed_ids = {e.get("opportunity_id") for e in exposures
                       if e.get("source") == source and e.get("opportunity_id")}
        opportunity_counts[source] = len(opportunity_ids)
        exposure_counts[source] = len(opportunity_ids & exposed_ids)
        exposure_event_counts[source] = sum(e.get("source") == source for e in exposures)
    conflicts = [e for e in ordered if e.get("kind") == "conflict_detected"]
    recovery_actions = [e for e in ordered if e.get("kind") == "action"
                        and e.get("details", {}).get("recovery") is True]
    joint_success = evaluator.get("joint_success") is True
    recovery_success: bool | None
    if not recovery_actions:
        recovery_success = None
    else:
        had_prior_conflict = any(c.get("sequence", 0) < recovery_actions[-1].get("sequence", 0)
                                 for c in conflicts)
        recovery_success = bool(had_prior_conflict and joint_success)
    actor_success = evaluator.get("actor_success", {})
    return {
        "exposure": {
            "opportunities_by_source": opportunity_counts,
            "realized_exposures_by_source": exposure_counts,
            "exposure_events_by_source": exposure_event_counts,
            "unlinked_opportunity_event_count": sum(
                e.get("source") in sources and not e.get("opportunity_id") for e in opportunities),
            "unlinked_exposure_event_count": sum(
                e.get("source") in sources and not e.get("opportunity_id") for e in exposures),
            "unsupported_source_event_count": sum(
                e.get("source") not in sources for e in opportunities + exposures),
            "rate_by_source": {
                source: (exposure_counts[source] / opportunity_counts[source]
                         if opportunity_counts[source] else None)
                for source in sources
            },
            "events": exposures,
        },
        "task_outcome": {
            "actor_success": actor_success,
            "actor_failure_count": sum(value is False for value in actor_success.values()),
            "joint_success": joint_success,
            "joint_failure": not joint_success,
        },
        "recovery": {
            "conflict_detected_count": len(conflicts),
            "recovery_action_count": len(recovery_actions),
            "recovery_success": recovery_success,
            "interpretation": "Operational recovery outcome only; no claim about internal awareness.",
        },
    }


def _get_path(state: Any, dotted_path: str) -> Any:
    if isinstance(state, dict) and dotted_path in state:
        return state[dotted_path]
    value = state
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    registry = load_registry(args.registry)
    summary: dict[str, Any] = validate_registry(registry)
    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        summary["config"] = validate_suite_config(config, registry)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
