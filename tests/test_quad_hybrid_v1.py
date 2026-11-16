"""Unit tests for the 4-agent Hybrid GUI+CLI benchmark suite (QH-01..QH-04)."""
from __future__ import annotations

from experiments.codesk_container_codex import validate_container_config_text
from experiments.long_horizon_v1 import build_lh_config_template
from experiments.quad_hybrid_v1 import build_quad_prompt
from tasks.quad_hybrid_v1.catalog import QUAD_HYBRID_CATALOG, QUAD_ROLES
from tasks.quad_hybrid_v1.portals import PORTAL_SPECS, build_portal_html


def test_quad_catalog_and_portal_specs_complete():
    assert QUAD_ROLES == ("B", "C", "D", "A")
    assert [r["id"] for r in QUAD_HYBRID_CATALOG] == ["QH-01", "QH-02", "QH-03", "QH-04"]
    assert len({r["portal_port"] for r in QUAD_HYBRID_CATALOG}) == 4
    for tid in ["QH-01", "QH-02", "QH-03", "QH-04"]:
        html = build_portal_html(tid)
        assert "cv_B" in html and "cv_A" in html
        assert set(PORTAL_SPECS[tid]["cards"].keys()) == {"B", "C", "D", "A"}


def test_quad_prompt_allows_full_cli_and_explains_live_gui_console():
    prompt = build_quad_prompt("C", "# Role C Ticket", 540)
    assert "FULL HYBRID GUI+CLI" in prompt
    assert "guest_bash" in prompt
    assert "desktop.screenshot" in prompt
    assert "/var/tickets/C" in prompt
    assert "--yolo" not in prompt
    cfg = validate_container_config_text(build_lh_config_template("gpt-6.1-sol", "high").replace("__CONTAINER_RELAY_PORT__", "18080"), mode="container-unrestricted")
    assert cfg["sandbox_mode"] == "workspace-write"
    assert cfg["approval_policy"] == "never"
