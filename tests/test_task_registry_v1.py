import json
from pathlib import Path

import pytest

from swcub.task_registry_v1 import (
    TaskRegistryError,
    evaluate_exact_state,
    initial_state_fixture,
    interaction_metrics,
    load_registry,
    summarize_episode_outcomes,
    validate_suite_config,
    verify_reset,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "tasks/codesk_task_registry_v1.json"
CONFIG_PATH = ROOT / "configs/task_suite_v1_offline_review.json"


def test_v1_registry_and_offline_config_are_well_formed():
    registry = load_registry(REGISTRY_PATH)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert len(registry["tasks"]) == 4
    assert len(registry["deferred_variants"]) == 4
    assert validate_suite_config(config, registry) == {"selected_tasks": 4, "conditions": 3}
    assert {task["family"] for task in registry["tasks"]} == {
        "focus_input_routing", "clipboard_ownership", "window_dialog_competition",
        "gui_cli_shared_state",
    }


def test_config_cannot_enable_guest_or_model_execution():
    registry = load_registry(REGISTRY_PATH)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["guest_launch_allowed"] = True
    with pytest.raises(TaskRegistryError, match="disable Guest and model launches"):
        validate_suite_config(config, registry)


def test_fixture_is_detached_and_reset_requires_exact_seed():
    task = load_registry(REGISTRY_PATH)["tasks"][0]
    fixture = initial_state_fixture(task)
    fixture["writer.text"] = "mutated"
    assert task["initial_state"]["writer.text"] == "Quarterly status report"
    assert verify_reset(task, task["initial_state"])["success"] is True
    assert verify_reset(task, {**task["initial_state"], "extra": "contamination"})["success"] is False


def test_programmatic_oracle_scores_each_actor_and_joint_state():
    task = load_registry(REGISTRY_PATH)["tasks"][0]
    result = evaluate_exact_state(task, {
        "writer.text": "Approved by GUI actor",
        "calc.cells": [["Record", "Status"], ["Quarterly", "Approved"]],
    })
    assert result["actor_success"] == {"writer_actor": True, "calc_actor": True}
    assert result["joint_success"] is True
    wrong = evaluate_exact_state(task, {"writer.text": "wrong", "calc.cells": []})
    assert wrong["joint_success"] is False


def test_interaction_metrics_require_a_logged_shared_state_cause():
    task = load_registry(REGISTRY_PATH)["tasks"][0]
    events = [
        {"sequence": 1, "actor_id": "writer_actor", "kind": "observation",
         "resource": "desktop_session", "revision": 1},
        {"sequence": 2, "actor_id": "calc_actor", "kind": "state_change",
         "resource": "focus", "before": "Writer", "after": "Calc"},
        {"sequence": 3, "actor_id": "writer_actor", "kind": "action",
         "resource": "keyboard", "observed_revision": 1, "current_revision": 2,
         "outcome": "ok"},
        {"sequence": 4, "actor_id": "writer_actor", "kind": "action",
         "resource": "desktop_session", "outcome": "ok", "details": {"recovery": True}},
    ]
    metrics = interaction_metrics(events, task)
    assert metrics["focus_transition_count"] == 1
    assert len(metrics["evidence_supported_conflicts"]) == 1
    assert metrics["recovery_steps_by_actor"] == {"writer_actor": 1}


def test_missing_recovery_contract_fails_registry_validation():
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    del registry["tasks"][0]["recovery"]["opportunity"]
    with pytest.raises(TaskRegistryError, match="recovery.opportunity"):
        from swcub.task_registry_v1 import validate_registry
        validate_registry(registry)


def test_registry_rejects_gui_cli_backend_confound():
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    task = next(t for t in registry["tasks"] if t["task_id"] == "CODESK-TD-STALE-MERGE-001")
    task["conditions"]["ma_id"]["backend_binding"] = "private_backend"
    from swcub.task_registry_v1 import validate_registry
    with pytest.raises(TaskRegistryError, match="must hold application backend constant"):
        validate_registry(registry)


def test_exposure_failure_and_recovery_are_reported_separately():
    evaluator = {"actor_success": {"writer_actor": True, "calc_actor": True},
                 "joint_success": True}
    events = [
        {"sequence": 1, "kind": "exposure_opportunity", "source": "scheduled_stress",
         "opportunity_id": "copy-window-1"},
        {"sequence": 2, "kind": "interference_exposure", "source": "scheduled_stress",
         "opportunity_id": "copy-window-1", "resource": "clipboard"},
        {"sequence": 3, "kind": "conflict_detected", "sequence": 3},
        {"sequence": 4, "actor_id": "writer_actor", "kind": "action",
         "details": {"recovery": True}},
    ]
    summary = summarize_episode_outcomes(evaluator, events)
    assert summary["exposure"]["realized_exposures_by_source"]["scheduled_stress"] == 1
    assert summary["task_outcome"]["joint_failure"] is False
    assert summary["recovery"]["recovery_success"] is True


def test_scheduled_opportunity_alone_is_not_exposure_or_failure():
    summary = summarize_episode_outcomes(
        {"actor_success": {"a": True, "b": True}, "joint_success": True},
        [{"sequence": 1, "kind": "exposure_opportunity", "source": "scheduled_stress",
          "opportunity_id": "stress-1"}],
    )
    assert summary["exposure"]["realized_exposures_by_source"]["scheduled_stress"] == 0
    assert summary["exposure"]["rate_by_source"]["scheduled_stress"] == 0
    assert summary["task_outcome"]["joint_failure"] is False
    assert summary["recovery"]["recovery_success"] is None
