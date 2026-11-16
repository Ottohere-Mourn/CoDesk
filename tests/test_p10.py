from types import SimpleNamespace

import pytest

from experiments import professional_native as native
from tasks.professional_v3.p10_oracle import population_at, risk_class, shortest_routes, validate_allocation


def test_population_uses_latest_eligible_record_without_zero_imputation():
    records = [
        {"parcel_id": "parcel", "residents": "10", "observed_at": "2024-01-01", "quality": "approved"},
        {"parcel_id": "parcel", "residents": "20", "observed_at": "2024-12-01", "quality": "approved"},
        {"parcel_id": "parcel", "residents": "999", "observed_at": "2026-01-01", "quality": "approved"},
        {"parcel_id": "parcel", "residents": "555", "observed_at": "2024-12-20", "quality": "rejected"},
        {"parcel_id": "missing", "residents": "-1", "observed_at": "2024-01-01", "quality": "approved"},
    ]
    selected = population_at(records, "2025-01-01")
    assert selected["parcel"]["residents"] == 20
    assert "missing" not in selected


@pytest.mark.parametrize("coverage,population,depth,affected,expected", [
    (.79, 200, 2, 200, "Unknown"), (1, None, 2, 0, "Unknown"),
    (.8, 200, 1, 0, "High"), (1, 200, 0, 100, "High"),
    (1, 100, .25, 0, "Medium"), (1, 100, 0, 20, "Medium"), (1, 100, 0, 0, "Low"),
])
def test_risk_boundaries(coverage, population, depth, affected, expected):
    assert risk_class(coverage, population, depth, affected) == expected


@pytest.fixture
def network():
    return {"edges": [
        {"edge_id": "direct", "source": "start", "target": "end", "seconds": 60, "closed": True, "accessible": True},
        {"edge_id": "first", "source": "start", "target": "middle", "seconds": 60, "closed": False, "accessible": True},
        {"edge_id": "second", "source": "middle", "target": "end", "seconds": 120, "closed": False, "accessible": True}],
        "origins": [{"origin_id": "origin", "node": "start", "demand": 5, "wheelchair": True}],
        "shelters": [{"shelter_id": "shelter", "node": "end", "capacity": 4, "accessible": True}]}


def test_directed_routing_does_not_cross_closed_edges_or_reverse_roads(network):
    distances, paths = shortest_routes(network["edges"], "start", True)
    assert distances["end"] == 3
    assert paths["end"] == ["first", "second"]
    assert "start" not in shortest_routes(network["edges"], "end")[0]
    network["edges"][2]["accessible"] = False
    assert "end" not in shortest_routes(network["edges"], "start", True)[0]


def test_allocation_checks_native_routes_not_reported_cost(network):
    row = {"origin_id": "origin", "shelter_id": "shelter", "persons": 4, "minutes": 3, "edge_ids": ["first", "second"]}
    optimum = {"served": 4, "cost": 12}
    result = validate_allocation([row], network, optimum)
    assert all(result[key] for key in ("paths", "capacity", "served", "cost"))
    row["persons"] = 5
    assert not validate_allocation([row], network, optimum)["capacity"]
    row.update(persons=4, minutes=1, edge_ids=["direct"])
    assert not validate_allocation([row], network, optimum)["paths"]
    row["persons"] = float("nan")
    assert not validate_allocation([row], network, optimum)["cost"]


def test_bad_role_order_is_rejected_before_output_creation(tmp_path):
    with pytest.raises(ValueError, match="Task roles"):
        native.run(SimpleNamespace(task_roles="aa", out=tmp_path / "trial"))
    assert not (tmp_path / "trial").exists()


def test_solo_prompt_does_not_invent_an_active_competitor(tmp_path):
    args = SimpleNamespace(harness="codex", interaction_mode="hybrid", coagent_hint=False,
                           codex_permissions="container-unrestricted")
    session, _command = native.prepare_native(tmp_path, args, {"model": "test-model"}, "http://relay/v1", "Task")
    prompt = (session / "task.md").read_text()
    assert "only active agent" in prompt
    assert "Another independent agent works" not in prompt
    assert "Both agents share" not in prompt
