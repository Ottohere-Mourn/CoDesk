import json
import pytest

from tasks.professional_v3.protocol import ROOT, main, make_plan


@pytest.fixture
def catalog():
    return json.loads((ROOT / "catalog.json").read_text())


def test_candidate_readiness_does_not_claim_calibrated_difficulty(catalog):
    assert catalog["status"] == "p10_calibration_ready"
    assert catalog["agent_trajectories"] == 0
    assert not catalog["difficulty_calibrated"]
    assert not catalog["official_benchmark_subset"]
    assert [pair["id"] for pair in catalog["pairs"]] == ["p10", "p11", "p12"]
    for pair in catalog["pairs"]:
        assert set(pair["readiness"]) == set(catalog["required_readiness"])
        assert not pair["readiness"]["hybrid_calibration"]
        if pair["id"] == "p10":
            assert pair["status"] == "native_validated_calibration_ready"
            assert all(pair["readiness"][name] for name in catalog["calibration_prerequisites"])
        else:
            assert pair["status"] == "spec_only"
            assert not any(pair["readiness"].values())
        assert not pair["provenance"]["copied_assets"]
        assert not pair["provenance"]["copied_prompts"]


def test_hybrid_policy_does_not_manufacture_failure(catalog):
    policy = catalog["policy"]
    assert policy["programming_allowed"] and policy["application_apis_allowed"]
    assert policy["agent_initiated_locks_allowed"]
    assert not policy["automatic_input_lock"]
    assert policy["required_click_count"] is None
    assert policy["required_channel_switch_count"] is None
    assert not policy["private_final_projects_allowed"]
    assert not policy["host_unrestricted_codex"]
    assert not policy["reference_access_allowed"]
    assert policy["preservation_points"] == 0
    assert not policy["role_score_comparison_to_weavebench_passrate"]


def test_role_contracts_and_original_prompts_exist(catalog):
    for pair in catalog["pairs"]:
        assert set(pair["agents"]) == {"a", "b"}
        assert set(pair["agents"]["a"]["writes"]).isdisjoint(pair["agents"]["b"]["writes"])
        assert len(pair["concurrency_surfaces"]) >= 4
        assert len(pair["negative_controls"]) >= 5
        assert pair["independence"]
        for role in pair["agents"].values():
            assert len(set(role["critical_checks"])) == 8
            assert pair["native_file"] in role["outputs"]
            prompt = (ROOT / role["instruction_file"]).read_text()
            assert "CLI" in prompt and "allowed" in prompt
            assert "live" in prompt and "native" in prompt
            assert "Use only the GUI" not in prompt


def test_single_pair_stage_counts_and_readiness(catalog):
    plan = make_plan(catalog, ["p10"], ["codex", "freehand"], 1)
    assert plan["totals"] == {"conditions": 10, "agent_rollouts": 16}
    assert plan["plan_only"] and not plan["execution_supported"]
    assert plan["calibration_readiness_blockers"]["p10"] == []
    assert plan["publication_readiness_blockers"]["p10"] == ["hybrid_calibration"]
    assert all(job["input_manifest_sha256"] is None for job in plan["jobs"])


def test_calibration_is_not_a_circular_prerequisite_for_its_own_pilot(catalog):
    pair = catalog["pairs"][0]
    for name in catalog["calibration_prerequisites"]:
        pair["readiness"][name] = True
    plan = make_plan(catalog, ["p10"], ["codex"], 1)
    assert plan["calibration_readiness_blockers"]["p10"] == []
    assert plan["publication_readiness_blockers"]["p10"] == ["hybrid_calibration"]
    assert not plan["execution_supported"]


def test_full_design_counts_are_not_confused_with_agent_count(catalog):
    plan = make_plan(catalog, ["p10", "p11", "p12"], ["codex", "freehand"], 3)
    assert plan["totals"] == {"conditions": 90, "agent_rollouts": 144}
    assert len({job["id"] for job in plan["jobs"]}) == 90
    assert len({job["input_variant"] for job in plan["jobs"]}) == 9


def test_controls_share_inputs_budgets_and_start_fresh(catalog):
    plan = make_plan(catalog, ["p10"], ["codex", "freehand"], 2)
    for harness in ("codex", "freehand"):
        for instance in ("p10-instance-001", "p10-instance-002"):
            jobs = [job for job in plan["jobs"] if job["harness"] == harness and job["input_variant"] == instance]
            assert {job["condition"] for job in jobs} == set(catalog["conditions"])
            assert all(job["fresh_environment"] and job["shared_final_project"] for job in jobs)
            assert all(job["budget_per_agent"] == catalog["baseline_budget"] for job in jobs)
            sequential = next(job for job in jobs if job["condition"] == "sequential_ba")
            assert sequential["roles"] == ["b", "a"] and sequential["simultaneous_agents"] == 1
            parallel = next(job for job in jobs if job["condition"] == "parallel_shared")
            assert parallel["simultaneous_agents"] == 2 and parallel["shared_desktop"]


def test_order_is_reproducible_and_budget_objects_are_independent(catalog):
    first = make_plan(catalog, ["p10"], ["codex", "freehand"], 2)
    second = make_plan(catalog, ["p10"], ["codex", "freehand"], 2)
    assert first == second
    assert first["jobs"][0]["harness"] == "codex"
    assert first["jobs"][10]["harness"] == "freehand"
    first["jobs"][0]["budget_per_agent"]["max_actions"] = 1
    assert first["jobs"][1]["budget_per_agent"]["max_actions"] == 300
    assert catalog["baseline_budget"]["max_actions"] == 300


def test_isolated_parallel_is_only_an_explicit_diagnostic(catalog):
    plan = make_plan(catalog, ["p10"], ["codex", "freehand"], 1, isolated_control=True)
    assert plan["totals"] == {"conditions": 12, "agent_rollouts": 20}
    diagnostic = [job for job in plan["jobs"] if job["condition"] == "parallel_isolated_api_control"]
    assert len(diagnostic) == 2
    assert all(not job["shared_desktop"] and not job["shared_final_project"] for job in diagnostic)
    assert all(job["simultaneous_agents"] == 2 for job in diagnostic)


@pytest.mark.parametrize("pairs,harnesses,repetitions", [
    ([], ["codex"], 1), (["p3"], ["codex"], 1), (["p10", "p10"], ["codex"], 1),
    (["p10"], [], 1), (["p10"], ["other"], 1), (["p10"], ["codex", "codex"], 1),
    (["p10"], ["codex"], 0), (["p10"], ["codex"], -1), (["p10"], ["codex"], True),
])
def test_invalid_plans_are_rejected(catalog, pairs, harnesses, repetitions):
    with pytest.raises(ValueError):
        make_plan(catalog, pairs, harnesses, repetitions)


def test_cli_only_writes_a_plan_and_refuses_overwrite(tmp_path):
    target = tmp_path / "plan.json"
    main(["--pairs", "p10", "--out", str(target)])
    data = json.loads(target.read_text())
    assert data["plan_only"] and not data["execution_supported"]
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        main(["--pairs", "p11", "--out", str(target)])
    assert target.read_bytes() == before
