"""Unit tests for the 5-case Real-Web + Real-Software macOS-style 2-Space suite."""
from __future__ import annotations

from experiments.codesk_container_codex import validate_container_config_text
from experiments.human_agent_cpu15_suite import build_ha_codex_config_template
from experiments.real_macos_ha_suite import build_real_macos_agent_prompt
from tasks.real_macos_ha_v1.catalog import REAL_MACOS_5_CATALOG, get_real_user_actions


def test_real_macos_catalog_and_prompts() -> None:
    assert len(REAL_MACOS_5_CATALOG) == 5
    for spec in REAL_MACOS_5_CATALOG:
        assert spec.user_url.startswith("https://")
        assert spec.agent_url.startswith("https://")
        acts = get_real_user_actions(spec)
        assert len(acts) >= 8
        prompt = build_real_macos_agent_prompt(spec)
        assert "Space 2" in prompt
        assert "workspace-write" in prompt


def test_non_yolo_all_tools_config() -> None:
    rendered = build_ha_codex_config_template("gpt-6.1-sol", "medium").replace("__CONTAINER_RELAY_PORT__", "18080")
    parsed = validate_container_config_text(rendered, mode="container-unrestricted")
    assert parsed["sandbox_mode"] == "workspace-write"
    assert parsed["approval_policy"] == "never"
    assert parsed["features"]["shell_tool"] is True
