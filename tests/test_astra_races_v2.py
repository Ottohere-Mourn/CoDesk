"""Unit tests for the 10-task Astra-High professional & browser race suite."""
from __future__ import annotations

from experiments.astra_races_v2 import MODEL_NAME, REASONING_EFFORT, build_astra_config_template, build_astra_prompt
from experiments.codesk_container_codex import validate_container_config_text
from tasks.astra_races_v2.catalog import ASTRA_RACE_CATALOG


def test_ten_diverse_tasks_registered():
    assert len(ASTRA_RACE_CATALOG) == 10
    ids = [row["id"] for row in ASTRA_RACE_CATALOG]
    assert ids == [f"AR-{idx:02d}" for idx in range(1, 11)]
    categories = {row["category"] for row in ASTRA_RACE_CATALOG}
    assert len(categories) == 10


def test_astra_high_container_config_valid_and_non_yolo():
    assert MODEL_NAME == "gpt-6-astra"
    assert REASONING_EFFORT == "high"
    rendered = build_astra_config_template().replace("__CONTAINER_RELAY_PORT__", "18080")
    cfg = validate_container_config_text(rendered, mode="container-unrestricted")
    assert cfg["model"] == "gpt-6-astra"
    assert cfg["model_reasoning_effort"] == "high"
    assert cfg["approval_policy"] == "never"
    assert cfg["features"]["shell_tool"] is True


def test_prompt_maps_private_ticket_and_work_dirs():
    prompt = build_astra_prompt("A", "# Ticket VIZ-901")
    assert "/var/tickets/A" in prompt
    assert "/var/agent_work/A" in prompt
    assert "FULL HYBRID GUI+CLI" in prompt
