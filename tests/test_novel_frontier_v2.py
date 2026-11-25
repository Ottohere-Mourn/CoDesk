"""Unit & static-hygiene tests for novel_frontier_v2 (20 candidates -> Top-5)."""
from __future__ import annotations

from pathlib import Path
import re
import tempfile

from tasks.novel_frontier_v2 import (
    nf2_05_qtassistant_arinc429_flight_calc,
    nf2_12_freecad_cubesat_mass_cg_coupled,
    nf2_13_qgis_spatialite_feeder_hosting_coupled,
    nf2_15_qtdesigner_linguist_etcs_rail_coupled,
)
from tasks.novel_frontier_v2.common import verify_prompt_hygiene
from tasks.novel_frontier_v2.registry import ALL_20_CATALOG, ALL_20_MODULES, CANDIDATE_MODULES, RETAINED_TOP5_IDS


def test_catalog_20_complete_and_unique() -> None:
    assert len(ALL_20_MODULES) == 20
    assert len(CANDIDATE_MODULES) == 20
    ports = set()
    role_names = set()
    for mod in ALL_20_MODULES:
        meta = mod.META
        assert meta["id"].startswith("NF2-")
        assert meta["conc_role_timeout_s"] >= 7200
        assert meta["iso_role_timeout_s"] >= 7200
        assert meta["max_cua_calls"] is None
        assert meta["portal_port"] not in ports
        ports.add(meta["portal_port"])
        ra, rb = meta["roles"]
        assert ra != rb
        role_names.update((ra, rb))
        tickets = mod.build_tickets_by_role()
        assert set(tickets.keys()) == {ra, rb}
        hyg = verify_prompt_hygiene(tickets)
        assert hyg["ok"], f"{meta['id']} failed prompt hygiene: {hyg}"
    assert RETAINED_TOP5_IDS == ("NF2-05", "NF2-11", "NF2-12", "NF2-13", "NF2-15")
    for tid in RETAINED_TOP5_IDS:
        assert tid in CANDIDATE_MODULES


def test_nf215_parse_ui_supports_qtdesigner_minimumsize_and_minimumwidth() -> None:
    with tempfile.TemporaryDirectory() as td:
        ui_p = Path(td) / "designer_saved.ui"
        ui_p.write_text(
            nf2_15_qtdesigner_linguist_etcs_rail_coupled._render_etcs_ui(
                "background-color: #0B101B; color: #F8FAFC;",
                528,
                495,
                300,
                60,
                (40, 400, 5),
                (10, 60, 5),
            ),
            encoding="utf-8",
        )
        parsed = nf2_15_qtdesigner_linguist_etcs_rail_coupled._parse_ui(ui_p)
        assert parsed["speed_w"] == 528
        assert parsed["banner_w"] == 495
        assert parsed["btn_w"] == 300
        assert parsed["btn_h"] == 60
        assert parsed["max_spin"] == [40, 400, 5]
        assert parsed["rel_spin"] == [10, 60, 5]
        assert "#0b101b" in parsed["qss"].lower()


def test_harness_xvfb_auth_and_uid2000_enforced() -> None:
    root = Path(__file__).resolve().parents[1]
    runner_src = (root / "experiments/novel_frontier_v2.py").read_text(encoding="utf-8")
    assert "-auth /run/user/1000/x99.auth" in runner_src
    assert "Xvfb :99 -screen 0 1920x1080x24 -ac" not in runner_src
    assert '"--user", "2000:0"' in runner_src
    assert "useradd -m -u 2000 -g 0 -s /bin/bash cli_user" in runner_src
    nf12_src = Path(nf2_12_freecad_cubesat_mass_cg_coupled.__file__).read_text(encoding="utf-8")
    assert "valid_unsat_active_fastener_count" in nf12_src
    assert "valid_telemetry_sunlit_slice_count" in nf12_src
    assert '"active_fastener_count"' not in nf12_src
    assert '"sunlit_slice_count"' not in nf12_src
    epv, eev, pcnt, pmva, ecnt, emva = nf2_13_qgis_spatialite_feeder_hosting_coupled._compute_nf213_oracles()
    assert len(epv) == 12 and len(eev) == 9
    assert pcnt > 50 and pmva > 15.0 and ecnt > 80 and emva > 16.5
    assert nf2_05_qtassistant_arinc429_flight_calc.ARINC_ORACLE["valid_normal_op_count"] > 300


def test_py311_fstring_compatibility() -> None:
    root = Path(__file__).resolve().parents[1]
    for p in sorted((root / "tasks/novel_frontier_v2").glob("*.py")) + [root / "experiments/novel_frontier_v2.py"]:
        if not p.is_file():
            continue
        for idx, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if 'f"' in ln or "f'" in ln:
                for m in re.finditer(r"(?<!\{)\{(?!\{)[^}]*\\[^}]*\}", ln):
                    raise AssertionError(f"Python 3.11 incompatible backslash in f-string at {p.name}:{idx}: {m.group(0)}")


if __name__ == "__main__":
    test_catalog_20_complete_and_unique()
    test_nf215_parse_ui_supports_qtdesigner_minimumsize_and_minimumwidth()
    test_harness_xvfb_auth_and_uid2000_enforced()
    test_py311_fstring_compatibility()
    print("ALL_NF2_TESTS_PASSED", len(ALL_20_CATALOG))
