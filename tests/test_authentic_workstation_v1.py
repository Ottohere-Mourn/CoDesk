"""Unit & static-audit tests for authentic_workstation_v1 (AW-01..AW-22)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from experiments.authentic_workstation_v1 import build_aw_agent_prompt
from tasks.authentic_workstation_v1 import (
    AW_BY_ID,
    AW_CATALOG,
    AW_MODULES,
)
from tasks.authentic_workstation_v1.aw01_commerce_qa_vs_launch_reel import (
    compute_qa_oracle,
    compute_reel_oracle,
)
from tasks.authentic_workstation_v1.aw02_gimp_inkscape_packaging import (
    compute_color_oracle,
    compute_dieline_oracle,
)
from tasks.authentic_workstation_v1.aw04_ma_qoe_tax_dealroom import compute_dealroom_oracle
from tasks.authentic_workstation_v1.aw05_freecad_2u_blade_cad import compute_cad_oracle
from tasks.authentic_workstation_v1.aw19_libreoffice_dense_budget_and_redline import compute_aw19_oracle
from tasks.authentic_workstation_v1.aw20_inkscape_gimp_freecad_meddevice_enclosure import compute_aw20_oracle
from tasks.authentic_workstation_v1.aw21_isolated_chromium_finops_vs_reel import compute_aw21_oracle
from tasks.authentic_workstation_v1.common import build_aw_grade_payload, verify_prompt_hygiene
from tasks.authentic_workstation_v1.registry import RETAINED_TOP5_IDS

CODESK_ROOT = Path(__file__).resolve().parents[1]


def _load_skill_auditor():
    cand_paths = [
        CODESK_ROOT / ".agents/skills/paragui-case-design/scripts/audit_case_module.py",
        Path.home() / ".codex/skills/paragui-case-design/scripts/audit_case_module.py",
    ]
    for p in cand_paths:
        if p.is_file():
            spec = importlib.util.spec_from_file_location("audit_case_module", p)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise AssertionError("audit_case_module.py not found")


def test_catalog_and_retained_top5_metadata() -> None:
    assert [c["id"] for c in AW_CATALOG] == [f"AW-{i:02d}" for i in range(1, 23)]
    assert RETAINED_TOP5_IDS == ("AW-12", "AW-14", "AW-15", "AW-19", "AW-20")
    assert set(RETAINED_TOP5_IDS).issubset(set(AW_BY_ID))
    for meta in AW_CATALOG:
        assert int(meta["max_cua_calls"]) >= 120
        assert int(meta["iso_role_timeout_s"]) >= 1200
        assert int(meta["conc_role_timeout_s"]) >= 1500
        assert len(meta["roles"]) == 2


def test_all_tickets_pass_prompt_hygiene_and_agent_prompt_honesty() -> None:
    for tid, mod in AW_MODULES.items():
        ra, rb = mod.TASK_META["roles"]
        hyg = verify_prompt_hygiene({ra: mod.TICKET_A, rb: mod.TICKET_B})
        assert hyg["ok"], f"{tid} failed prompt hygiene: {hyg}"
        wrapped = build_aw_agent_prompt(mod.TICKET_A, ra, 1200, "qwen_cua", 140)
        assert "qwen_cua_driver" in wrapped
        assert "guest_bash" in wrapped
        assert "read-only" in wrapped


def test_isolated_mode_skips_joint_coupling_penalties() -> None:
    checks_a = [("a1", True, 1.0, "err_a")]
    checks_b = [("b1", False, 1.0, "err_b")]
    checks_j = [("j1", False, 2.0, "peer_missing")]

    iso = build_aw_grade_payload(
        task_id="AW-01",
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_j,
        tickets_by_role={"r1": "clean work order", "r2": "clean work order"},
        service_state={},
        wall_seconds=12.0,
        active_mode="isolated",
    )
    assert iso["score_a"] == 1.0
    assert iso["pass_a"] is True
    assert iso["subchecks_joint"] == {}

    sh = build_aw_grade_payload(
        task_id="AW-01",
        checks_a=checks_a,
        checks_b=checks_a,
        checks_joint=checks_j,
        tickets_by_role={"r1": "clean work order", "r2": "clean work order"},
        service_state={},
        wall_seconds=12.0,
        active_mode="shared",
    )
    assert sh["joint_pass"] is False
    assert sh["score_a"] < 1.0


def test_domain_oracles_invariants() -> None:
    qa = compute_qa_oracle()
    assert qa["air_blocked_carts"] == ["CART-105", "CART-108"]
    assert qa["hazmat_surcharge_carts"] == ["CART-106"]
    assert qa["eu_reverse_charge_carts"] == ["CART-101", "CART-103"]

    reel = compute_reel_oracle()
    assert 100.0 < reel["enterprise_nrr_pct"] < 130.0
    assert 60.0 < reel["nongaap_gross_margin_pct"] < 80.0

    col = compute_color_oracle()
    assert col["over_tac_swatches"] == ["Brand_Obsidian", "Shadow_Plum"]
    for cmyk in col["adjusted_cmyk"].values():
        assert sum(cmyk) <= 300.15

    die = compute_dieline_oracle()
    assert len(die["ean13_full"]) == 13
    assert die["net_carton_mass_g"] == 56.0

    dr = compute_dealroom_oracle()
    assert dr["asc606_deferred_rev_adj_musd"] < 0
    assert dr["litigation_capped_addback_musd"] == 1.25

    cad = compute_cad_oracle()
    assert cad["active_vent_hole_count"] == 187
    assert cad["top_shroud_volume_mm3"] < 255360.0
    assert 48.0 <= cad["chassis_delta_p_pa"] <= 56.0

    o19 = compute_aw19_oracle()
    assert o19["total_landed_musd"] > o19["total_cif_musd"] > 14.0
    assert o19["total_yr2_lease_musd"] > 10.0

    o20 = compute_aw20_oracle()
    assert 150.0 < o20["bezel_mass_g"] < 180.0
    assert 410.0 < o20["rear_mass_g"] < 450.0

    o21 = compute_aw21_oracle()
    assert o21["eu_reverse_charge_ids"] == ["INV-401", "INV-406"]
    assert o21["unused_ri_waste_usd"] > 0


def test_skill_static_auditor_zero_fail_zero_warn() -> None:
    aud = _load_skill_auditor()
    targets = [
        *sorted(
            p
            for p in (CODESK_ROOT / "tasks/authentic_workstation_v1").glob("*.py")
            if p.name not in ("__init__.py", "registry.py")
        ),
        CODESK_ROOT / "experiments/authentic_workstation_v1.py",
    ]
    for t in targets:
        res = aud.audit_python_file(t)
        assert res["status"] == "PASS", f"{t.name} failed static audit: {res}"
        assert res["fails"] == []
        assert res["warns"] == []


class AuthenticWorkstationV1TestSuite(unittest.TestCase):
    def test_all(self) -> None:
        test_catalog_and_retained_top5_metadata()
        test_all_tickets_pass_prompt_hygiene_and_agent_prompt_honesty()
        test_isolated_mode_skips_joint_coupling_penalties()
        test_domain_oracles_invariants()
        test_skill_static_auditor_zero_fail_zero_warn()


if __name__ == "__main__":
    unittest.main()
