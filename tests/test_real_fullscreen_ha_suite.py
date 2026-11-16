"""Unit tests for the 5-case Full-Screen User Interface + Natural Agent Preemption suite."""
from __future__ import annotations

from experiments.codesk_container_codex import validate_container_config_text
from experiments.human_agent_cpu15_suite import build_ha_codex_config_template
from experiments.real_fullscreen_ha_suite import FULLSCREEN_OPENBOX_RC_XML, build_fullscreen_agent_prompt
from tasks.real_fullscreen_ha_v1.catalog import REAL_FULLSCREEN_5_CATALOG, get_fullscreen_user_actions


def test_fullscreen_catalog_and_neutral_prompts() -> None:
    assert len(REAL_FULLSCREEN_5_CATALOG) == 5
    assert "<maximized>yes</maximized>" in FULLSCREEN_OPENBOX_RC_XML
    for spec in REAL_FULLSCREEN_5_CATALOG:
        assert spec.user_url.startswith("https://")
        assert all(u.startswith("https://") for u in spec.agent_target_urls)
        acts = get_fullscreen_user_actions(spec)
        assert len(acts) >= 8
        prompt = build_fullscreen_agent_prompt(spec)
        assert "Space 2" not in prompt
        assert "desktop.click" not in prompt
        assert "workspace-write" in prompt


def test_non_yolo_config_for_fullscreen_suite() -> None:
    rendered = build_ha_codex_config_template("gpt-6.1-sol", "medium").replace("__CONTAINER_RELAY_PORT__", "18080")
    parsed = validate_container_config_text(rendered, mode="container-unrestricted")
    assert parsed["sandbox_mode"] == "workspace-write"
    assert parsed["approval_policy"] == "never"
    assert parsed["features"]["shell_tool"] is True
