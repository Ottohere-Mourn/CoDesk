"""Unit tests for the 8-case 4-agent Thematic Arenas suite (TA-A1..TA-E1)."""
from __future__ import annotations

from pathlib import Path
from experiments.thematic_arenas_v1 import build_arena_prompt
from tasks.thematic_arenas_v1.catalog import TA_BY_ID, THEMATIC_ARENAS_CATALOG
from tasks.thematic_arenas_v1.graders import grade_arena_a, grade_arena_c
from tasks.thematic_arenas_v1.suite import build_arena_a, build_arena_c
from tasks.thematic_arenas_v1.xlsx_utils import read_multisheet_xlsx, update_single_sheet_xlsx


def test_thematic_arenas_catalog_structure():
    assert len(THEMATIC_ARENAS_CATALOG) == 8
    ids = [r["id"] for r in THEMATIC_ARENAS_CATALOG]
    assert ids == ["TA-A1", "TA-A2", "TA-B1", "TA-B2", "TA-C1", "TA-C2", "TA-D1", "TA-E1"]
    for r in THEMATIC_ARENAS_CATALOG:
        assert len(r["roles"]) == 4
        assert float(r["critical_section_lower_bound_s"]) >= 120.0
        assert int(r["conc_role_timeout_s"]) >= 1800


def test_xlsx_cooperative_update_preserves_summary_formulas(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    tks = {r: tmp_path / f"{r}.md" for r in TA_BY_ID["TA-A1"]["roles"]}
    build_arena_a("TA-A1", ws, tks)
    xlsx_p = ws / "Q3_Operating_Model.xlsx"
    update_single_sheet_xlsx(xlsx_p, "Ops_KPI", [["table_id", "wh", "lm", "tot", "sla"], ["ops_w01", 48.0, 14.0, 62.0, 98.4]])
    wb = read_multisheet_xlsx(xlsx_p)
    assert wb["Summary"]["B2"]["formula"] == "SUM(Revenue_Cost!B2:B14)"
    assert wb["Summary"]["B5"]["formula"] == "B2-B3-B4"
    assert wb["Ops_KPI"]["D2"]["value"] == 62.0


def test_4d_grading_efficiency_and_side_effects(tmp_path: Path):
    ws = tmp_path / "ws_c"
    ws.mkdir()
    tks = {r: tmp_path / f"{r}.md" for r in TA_BY_ID["TA-C1"]["roles"]}
    build_arena_c("TA-C1", ws, tks)
    g = grade_arena_c("TA-C1", ws, {"collateral_side_effects": {"observation_pollutions": 2, "uncoordinated_restarts": 2}}, wall_s=320.0)
    assert g["joint_pass"] is False
    assert g["canary_passed"] is False
    assert g["efficiency"]["efficiency_score"] == 0.5
    assert g["collateral_side_effects"]["observation_pollutions"] == 2


def test_coord_mode_prompt_ablation():
    p_none = build_arena_prompt("FIN", "Export BI", 2400, "no_comm")
    p_pad = build_arena_prompt("FIN", "Export BI", 2400, "shared_scratchpad")
    assert "SCRATCHPAD" not in p_none
    assert "/workspace/.coord/SCRATCHPAD.md" in p_pad
