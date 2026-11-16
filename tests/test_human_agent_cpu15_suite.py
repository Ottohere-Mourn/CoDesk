"""Offline verification for the 17-case Human-Agent CPU15 Docker + non-YOLO All-Tools Codex suite."""
from __future__ import annotations

from pathlib import Path
import tempfile

from experiments.codesk_container_codex import validate_container_config_text
from experiments.human_agent_cpu15_suite import build_ha_agent_prompt, build_ha_codex_config_template
from tasks.human_agent_v1.catalog import (
    ACTIVE_16_KEYS,
    HUMAN_AGENT_17_CATALOG,
    SOURCE_COMMIT,
    get_case_prompts,
    get_user_actions,
    load_app_module,
)


def test_catalog_has_all_17_cases() -> None:
    assert len(HUMAN_AGENT_17_CATALOG) == 17
    assert len(ACTIVE_16_KEYS) == 16
    assert SOURCE_COMMIT.startswith("684c79a")
    for spec in HUMAN_AGENT_17_CATALOG:
        actions = get_user_actions(spec)
        assert len(actions) >= 3, f"{spec.key} missing user actions"
        urls = {
            "app_url": "http://127.0.0.1:18000",
            "ttr_url": "http://127.0.0.1:18001",
            "handoff_url": "http://127.0.0.1:18002",
            "triage_url": "http://127.0.0.1:18003",
        }
        at, ut = get_case_prompts(spec, urls)
        assert len(at) > 40 and len(ut) > 30
        prompt = build_ha_agent_prompt(spec, at, max_steps=spec.agent_budget)
        assert "desktop.screenshot" in prompt
        assert "workspace-write" in prompt


def test_codex_config_is_all_tools_non_yolo() -> None:
    tmpl = build_ha_codex_config_template("gpt-6.1-sol", "medium")
    rendered = tmpl.replace("__CONTAINER_RELAY_PORT__", "18999")
    parsed = validate_container_config_text(rendered, mode="container-unrestricted")
    assert parsed["sandbox_mode"] == "workspace-write"
    assert parsed["approval_policy"] == "never"
    assert parsed["features"]["shell_tool"] is True
    assert parsed["apps"]["_default"]["default_tools_approval_mode"] == "approve"
    assert parsed["mcp_servers"]["desktop"]["default_tools_approval_mode"] == "approve"
    assert parsed["mcp_servers"]["guest_bash"]["default_tools_approval_mode"] == "approve"
    assert "yolo" not in rendered.lower()
    assert "danger-full-access" not in rendered.lower()


def test_all_single_app_fixtures_and_pristine_oracles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        for spec in HUMAN_AGENT_17_CATALOG:
            if spec.kind in {"single_app", "po_archive"}:
                app = load_app_module(spec)
                db = tdir / f"{spec.key}.sqlite3"
                manifest = app.create_fixture(db, f"test-{spec.key}")
                assert "fixture_id" in manifest
                ev = app.evaluate(db)
                assert ev["agent"]["success"] is False
                assert ev["user"]["success"] is False
