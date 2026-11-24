"""Unit tests for Batch 3 tasks/rb_osw2_synth_v3 (RBS3-01..RBS3-05) & LAW_8 zero-spoiler coupled contention."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tasks.rb_osw2_synth_v3.common import FORBIDDEN_EXAM_V2_PATTERNS, verify_prompt_hygiene
from tasks.rb_osw2_synth_v3.registry import RBS3_BY_ID, RBS3_CATALOG, RBS3_MODULES
from tools.paragui_case_factory import CONFLICT_LAWS, HORIZON_BANDS, audit_case_blueprint_meta

CODESK_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = Path("/home/v-yukezhao/.codex/skills/paragui-case-design/scripts/audit_case_module.py")


def test_rbs3_factory_law8_and_non_saturated_band() -> None:
    assert "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING" in CONFLICT_LAWS
    assert "non_saturated_coupled_contention" in HORIZON_BANDS
    assert HORIZON_BANDS["non_saturated_coupled_contention"]["min_subchecks_total"] == 40


def test_rbs3_suite_blueprints_and_prompt_hygiene() -> None:
    assert [m["id"] for m in RBS3_CATALOG] == [f"RBS3-0{i}" for i in range(1, 6)]
    tracks: set[str] = set()
    for tid, mod in RBS3_MODULES.items():
        meta = RBS3_BY_ID[tid]
        tracks.add(meta["track"])
        assert "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING" in meta["archetypes"]
        assert meta["max_cua_calls"] <= 45
        bp_rep = audit_case_blueprint_meta(meta, mod)
        assert bp_rep["blueprint_valid"] is True, f"{tid} blueprint warnings: {bp_rep['warnings']}"
        assert bp_rep["predicted_contention_index"] == 100.0
        assert bp_rep["total_subchecks"] == 40

        tickets = mod.build_tickets_by_role()
        assert verify_prompt_hygiene(tickets)["ok"]
        for role, md in tickets.items():
            low = md.lower()
            for pat in FORBIDDEN_EXAM_V2_PATTERNS:
                assert pat not in low, f"{tid}/{role} leaked {pat!r}"
            for drv_leak in ("qwen_cua_driver", "desktop.click", "click_and_type"):
                assert drv_leak not in low, f"{tid}/{role} leaked driver schema {drv_leak!r}"

    assert tracks == {"track1_isolated_screen", "track2_shared_state"}


def test_rbs3_static_auditor_zero_fail_zero_warn() -> None:
    if not AUDIT_SCRIPT.is_file():
        return
    for target in (CODESK_ROOT / "tasks/rb_osw2_synth_v3", CODESK_ROOT / "experiments/rb_osw2_synth_v3.py"):
        cp = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(target)], check=True, capture_output=True, text=True)
        rep = json.loads(cp.stdout)
        for item in rep:
            assert item["status"] == "PASS" and item["fails"] == [] and item["warns"] == []


def test_static_auditor_flags_rigid_split_screen_unless_opted_in() -> None:
    if not AUDIT_SCRIPT.is_file():
        return
    with tempfile.TemporaryDirectory() as tmp:
        bad_py = Path(tmp) / "split_bad.py"
        bad_py.write_text('def boot():\n    self.setGeometry(920, 40, 860, 600)\n', encoding="utf-8")
        cp1 = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(bad_py)], check=True, capture_output=True, text=True)
        r1 = json.loads(cp1.stdout)[0]
        assert r1["status"] == "WARN" and any("RIGID_SPLIT_SCREEN" in w for w in r1["warns"])

        opt_py = Path(tmp) / "split_optin.py"
        opt_py.write_text('ALLOW_CUSTOM_WINDOW_LAYOUT = True\ndef boot():\n    self.setGeometry(920, 40, 860, 600)\n', encoding="utf-8")
        cp2 = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(opt_py)], check=True, capture_output=True, text=True)
        r2 = json.loads(cp2.stdout)[0]
        assert r2["status"] == "PASS" and r2["warns"] == []


def test_rbs3_5gate_and_dual_model_manifests_when_present() -> None:
    sv_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v3_5gate_selfval_20261123.json"
    bm_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v3_sol61_astra_20261123.json"
    if sv_p.is_file():
        sv = json.loads(sv_p.read_text(encoding="utf-8"))
        assert sv["all_5_gates_valid"] is True
        assert len(sv["cases"]) == 5
    if bm_p.is_file():
        bm = json.loads(bm_p.read_text(encoding="utf-8"))
        assert bm["total_episodes"] == 20
        assert bm["total_non_yolo_agent_runs"] == 40
        for mkey in ("gpt-6.1-sol", "gpt-6-astra"):
            ms = bm["macro_summary"][mkey]
            assert ms["all_permission_audits_verified"] is True
            assert ms["shared_mean_score"] < ms["isolated_mean_score"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
