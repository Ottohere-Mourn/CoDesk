"""Unit tests for the 4-task ultra-long-horizon benchmark suite (LH-01..LH-04) on gpt-6.1-sol."""
from __future__ import annotations

from experiments.codesk_container_codex import validate_container_config_text
from experiments.long_horizon_v1 import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL_NAME,
    build_lh_config_template,
    build_lh_prompt,
)
from tasks.long_horizon_v1.catalog import LONG_HORIZON_CATALOG


def test_four_long_horizon_tasks_registered():
    assert [row["id"] for row in LONG_HORIZON_CATALOG] == ["LH-01", "LH-02", "LH-03", "LH-04"]
    ports = {row["portal_port"] for row in LONG_HORIZON_CATALOG}
    assert ports == {18911, 18912, 18913, 18914}
    for row in LONG_HORIZON_CATALOG:
        assert row["seq_role_timeout_s"] >= 1200
        assert row["conc_role_timeout_s"] >= 2400


def test_sol61_container_config_stays_non_yolo_workspace_write():
    assert DEFAULT_MODEL_NAME == "gpt-6.1-sol"
    assert DEFAULT_EFFORT == "high"
    rendered = build_lh_config_template("gpt-6.1-sol", "high").replace("__CONTAINER_RELAY_PORT__", "18080")
    cfg = validate_container_config_text(rendered, mode="container-unrestricted")
    assert cfg["model"] == "gpt-6.1-sol"
    assert cfg["sandbox_mode"] == "workspace-write"
    assert cfg["approval_policy"] == "never"
    assert cfg["features"]["shell_tool"] is True
    for srv in cfg["mcp_servers"].values():
        assert srv["default_tools_approval_mode"] == "approve"


def test_lh_prompt_maps_ticket_and_drc_instructions():
    prompt = build_lh_prompt("B", "# Ticket ENV-LH01-B", 1350)
    assert "/var/tickets/B" in prompt
    assert "/var/agent_work/B" in prompt
    assert "1350 seconds" in prompt
