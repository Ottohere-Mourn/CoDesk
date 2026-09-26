from __future__ import annotations

import json
from pathlib import Path

import pytest

from swcub.instances import TaskInstanceError, TaskInstanceSpec, aggregate_reports


ROOT = Path(__file__).resolve().parents[1]


def instance_dict():
    return json.loads((ROOT / "tasks/instances/office_writer_calc.json").read_text())


def test_office_instance_schema_resolves_actor_turn_triggers():
    spec = TaskInstanceSpec.from_dict(instance_dict())
    assert spec.materialize_schedule() == ["writer_actor", "writer_actor", "calc_actor"]


def test_all_current_osworld_task_instances_are_valid_and_have_private_goals():
    instances = [TaskInstanceSpec.from_dict(json.loads(path.read_text()))
                 for path in sorted((ROOT / "tasks/instances").glob("*.json"))]
    assert {spec.task_id for spec in instances} == {
        "OFFICE-GUI-GUI-001", "BROWSER-GUI-CLI-001", "BROWSER-GUI-HUMAN-001"}
    assert all(spec.actor_goals for spec in instances)


def test_task_instance_initialization_resets_then_seeds_declared_state():
    spec = TaskInstanceSpec.from_dict(instance_dict())
    calls = []

    def reset(instance_id, seed):
        environment = {"id": instance_id, "seed": seed}
        calls.append(("reset", instance_id, seed))
        return environment

    def apply(environment, initial_state):
        environment["initial_state"] = initial_state
        calls.append(("initialize", initial_state))

    environment = spec.initialize(reset, apply)
    assert calls[0] == ("reset", "office-v0-sequential-seed0", 0)
    assert environment["initial_state"] == spec.initial_state
    assert environment["initial_state"] is not spec.initial_state


def test_task_instance_rejects_trigger_deadlock():
    data = instance_dict()
    data["schedule"] = [{"actor_id": "writer_actor", "trigger": {
        "after_actor_turn": {"actor_id": "calc_actor", "count": 1}}}]
    with pytest.raises(TaskInstanceError, match="deadlock"):
        TaskInstanceSpec.from_dict(data)


def test_result_aggregation_reports_both_actor_goal_rates():
    summary = aggregate_reports([
        {"task_instance_id": "run1", "evaluation": {"success": True},
         "reset_check": {"success": True}, "individual_goals": {
             "writer_actor": {"success": True}, "calc_actor": {"success": False}}},
        {"task_instance_id": "run2", "evaluation": {"success": False},
         "reset_check": {"success": True}, "individual_goals": {
             "writer_actor": {"success": True}, "calc_actor": {"success": True}}},
    ])
    assert summary["episodes"] == 2
    assert summary["evaluation_successes"] == 1
    assert summary["reset_successes"] == 2
    assert summary["actor_goals"]["writer_actor"]["success_rate"] == 1
    assert summary["actor_goals"]["calc_actor"]["success_rate"] == 0.5
