"""Unit tests for Batch 2 tasks/rb_osw2_synth_v2 (RBS2-01..RBS2-06) & LAW_7 visual-canvas factory rules."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tasks.rb_osw2_synth_v2.common import FORBIDDEN_EXAM_V2_PATTERNS, verify_prompt_hygiene
from tasks.rb_osw2_synth_v2.registry import RBS2_BY_ID, RBS2_CATALOG, RBS2_MODULES
from tools.paragui_case_factory import CONFLICT_LAWS, HORIZON_BANDS, audit_case_blueprint_meta

CODESK_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = Path("/home/v-yukezhao/.codex/skills/paragui-case-design/scripts/audit_case_module.py")


def test_rbs2_factory_law7_and_high_granularity_band() -> None:
    assert "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI" in CONFLICT_LAWS
    assert "high_granularity_visual_recreation" in HORIZON_BANDS
    assert HORIZON_BANDS["high_granularity_visual_recreation"]["min_subchecks_total"] == 36


def test_rbs2_suite_blueprints_and_prompt_hygiene() -> None:
    assert [m["id"] for m in RBS2_CATALOG] == [f"RBS2-0{i}" for i in range(1, 7)]
    covered_laws: set[str] = set()
    tracks: set[str] = set()
    for tid, mod in RBS2_MODULES.items():
        meta = RBS2_BY_ID[tid]
        tracks.add(meta["track"])
        covered_laws.update(meta["archetypes"])
        assert "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI" in meta["archetypes"]
        bp_rep = audit_case_blueprint_meta(meta, mod)
        assert bp_rep["blueprint_valid"] is True, f"{tid} blueprint warnings: {bp_rep['warnings']}"
        assert bp_rep["horizon_symmetry_ratio"] >= 0.95
        assert bp_rep["est_overlap_seconds"] >= 400.0
        assert bp_rep["total_subchecks"] >= 38

        tickets = mod.build_tickets_by_role()
        assert verify_prompt_hygiene(tickets)["ok"]
        for role, md in tickets.items():
            low = md.lower()
            for pat in FORBIDDEN_EXAM_V2_PATTERNS:
                assert pat not in low, f"{tid}/{role} leaked {pat!r}"
            for drv_leak in ("qwen_cua_driver", "desktop.click", "click_and_type"):
                assert drv_leak not in low, f"{tid}/{role} leaked driver schema {drv_leak!r}"

    assert tracks == {"track1_isolated_screen", "track2_shared_state"}
    assert covered_laws == set(CONFLICT_LAWS.keys())


def test_rbs2_static_auditor_zero_fail_zero_warn() -> None:
    if not AUDIT_SCRIPT.is_file():
        return
    for target in (CODESK_ROOT / "tasks/rb_osw2_synth_v2", CODESK_ROOT / "experiments/rb_osw2_synth_v2.py"):
        cp = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(target)], check=True, capture_output=True, text=True)
        rep = json.loads(cp.stdout)
        for item in rep:
            assert item["status"] == "PASS" and item["fails"] == [] and item["warns"] == []


def test_rbs2_5gate_and_dual_model_manifests_when_present() -> None:
    sv_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v2_5gate_selfval_20261123.json"
    bm_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v2_sol61_astra_20261123.json"
    assert sv_p.is_file() and bm_p.is_file()
    sv = json.loads(sv_p.read_text(encoding="utf-8"))
    assert sv["all_5_gates_valid"] is True
    assert len(sv["cases"]) == 6

    bm = json.loads(bm_p.read_text(encoding="utf-8"))
    assert bm["total_episodes"] == 24
    assert bm["total_non_yolo_agent_runs"] == 48
    assert bm["total_subchecks_across_suite"] == 234
    for mkey in ("gpt-6.1-sol", "gpt-6-astra"):
        ms = bm["macro_summary"][mkey]
        assert ms["all_permission_audits_verified"] is True
        assert ms["mean_overlap_ratio"] >= 0.60
        assert ms["mean_active_role_overlap_ratio"] >= 0.85
        assert ms["mean_cli_inflation_ratio"] >= 1.30
        assert ms["total_shared_focus_flips"] > ms["total_isolated_focus_flips"]
        assert ms["total_shared_misrouted_keystrokes"] >= 10


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
