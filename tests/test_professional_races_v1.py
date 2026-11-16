"""Unit tests for the 4 professional-software Full-CLI+GUI race tasks."""
from __future__ import annotations

from experiments.codesk_container_codex import validate_container_config_text
from experiments.professional_races_v1 import build_agent_prompt, build_full_cli_config_template
from tasks.professional_races_v1.suite import TASK_CATALOG, analyze_version_history, role_prompts


def test_catalog_and_prompts_have_no_coagent_spoilers():
    assert len(TASK_CATALOG) == 4
    for entry in TASK_CATALOG:
        prompts = role_prompts(entry["id"])
        assert set(prompts.keys()) == {"A", "B"}
        for role_text in prompts.values():
            lowered = role_text.lower()
            assert "another agent" not in lowered
            assert "handoff" not in lowered
            wrapped = build_agent_prompt(role_text)
            assert "FULL HYBRID GUI+CLI" in wrapped
            assert "--yolo" not in wrapped


def test_full_cli_container_config_passes_non_yolo_guard():
    rendered = build_full_cli_config_template("gpt-6.1-sol").replace("__CONTAINER_RELAY_PORT__", "18080")
    cfg = validate_container_config_text(rendered, mode="container-unrestricted")
    assert cfg["approval_policy"] == "never"
    assert cfg["sandbox_mode"] == "workspace-write"
    assert cfg["features"]["shell_tool"] is True


def test_analyze_version_history_detects_lost_update():
    rows = [
        {"timestamp": 1.0, "project_sha256": "h0", "role_a_in_project": False, "role_b_in_project": False},
        {"timestamp": 5.0, "project_sha256": "h1", "role_a_in_project": True, "role_b_in_project": False},
        {"timestamp": 7.0, "project_sha256": "h2", "role_a_in_project": False, "role_b_in_project": True},
    ]
    res = analyze_version_history(rows)
    assert res["distinct_project_versions"] == 3
    assert res["lost_update_observed"] is True
    assert res["lost_update_regressions"][0]["signal"] == "role_a_in_project"
