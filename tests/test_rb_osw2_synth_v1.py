"""Unit tests for tools/paragui_case_factory.py and tasks/rb_osw2_synth_v1 (RBS-01..RBS-06)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tasks.rb_osw2_synth_v1.common import FORBIDDEN_EXAM_V2_PATTERNS, verify_prompt_hygiene
from tasks.rb_osw2_synth_v1.registry import RBS_BY_ID, RBS_CATALOG, RBS_MODULES
from tools.paragui_case_factory import (
    CONFLICT_LAWS,
    HORIZON_BANDS,
    audit_case_blueprint_meta,
    infer_rb_app_traits,
    score_role_pair,
)

CODESK_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = Path("/home/v-yukezhao/.codex/skills/paragui-case-design/scripts/audit_case_module.py")
FACTORY_SCRIPT = CODESK_ROOT / "tools/paragui_case_factory.py"


def test_case_factory_laws_and_upstream_rb_miner() -> None:
    assert len(CONFLICT_LAWS) >= 6
    assert {
        "compact_live_qa",
        "recreation_explore_build_verify",
        "deep_coupled_workbench",
    }.issubset(set(HORIZON_BANDS))
    rb_jsonl = CODESK_ROOT / "tasks/recreationbench_v1/metadata/ubuntu.jsonl"
    assert rb_jsonl.is_file()
    rows = [infer_rb_app_traits(json.loads(ln)) for ln in rb_jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 50
    ps = score_role_pair(rows[0], rows[1])
    assert 0.0 < ps["horizon_symmetry_ratio"] <= 1.0
    assert ps["est_overlap_seconds"] > 100.0


def test_case_factory_scaffold_passes_static_auditor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_py = Path(tmp) / "rbs_scaffold_check.py"
        subprocess.run(
            [
                sys.executable,
                str(FACTORY_SCRIPT),
                "scaffold",
                "--case-id",
                "RBS-99",
                "--title",
                "Scaffolded Twin-Modal Check",
                "--laws",
                "LAW_1_KEYSTROKE_MISROUTING",
                "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
                "--out",
                str(out_py),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert out_py.is_file()
        if AUDIT_SCRIPT.is_file():
            cp = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(out_py)], check=True, capture_output=True, text=True)
            rep = json.loads(cp.stdout)
            assert rep[0]["status"] == "PASS" and rep[0]["fails"] == [] and rep[0]["warns"] == []


def test_rbs_suite_blueprints_and_prompt_hygiene() -> None:
    assert [m["id"] for m in RBS_CATALOG] == [f"RBS-0{i}" for i in range(1, 7)]
    covered_laws: set[str] = set()
    tracks = set()
    for tid, mod in RBS_MODULES.items():
        meta = RBS_BY_ID[tid]
        tracks.add(meta["track"])
        covered_laws.update(meta["archetypes"])
        bp_rep = audit_case_blueprint_meta(meta, mod)
        assert bp_rep["blueprint_valid"] is True, f"{tid} blueprint warnings: {bp_rep['warnings']}"
        assert bp_rep["horizon_symmetry_ratio"] >= 0.90
        assert bp_rep["est_overlap_seconds"] >= 340.0
        assert bp_rep["total_subchecks"] >= 28

        tickets = mod.build_tickets_by_role()
        assert verify_prompt_hygiene(tickets)["ok"]
        for role, md in tickets.items():
            low = md.lower()
            for pat in FORBIDDEN_EXAM_V2_PATTERNS:
                assert pat not in low, f"{tid}/{role} leaked {pat!r}"
            for drv_leak in ("qwen_cua_driver", "desktop.click", "click_and_type"):
                assert drv_leak not in low, f"{tid}/{role} leaked driver schema {drv_leak!r}"

    assert tracks == {"track1_isolated_screen", "track2_shared_state"}
    assert {k for k in CONFLICT_LAWS if k.startswith(("LAW_1_", "LAW_2_", "LAW_3_", "LAW_4_", "LAW_5_", "LAW_6_"))}.issubset(covered_laws)


def test_rbs_static_auditor_zero_fail_zero_warn() -> None:
    if not AUDIT_SCRIPT.is_file():
        return
    for target in (CODESK_ROOT / "tasks/rb_osw2_synth_v1", CODESK_ROOT / "experiments/rb_osw2_synth_v1.py"):
        cp = subprocess.run([sys.executable, str(AUDIT_SCRIPT), "--json", str(target)], check=True, capture_output=True, text=True)
        rep = json.loads(cp.stdout)
        for item in rep:
            assert item["status"] == "PASS" and item["fails"] == [] and item["warns"] == []


def test_rbs_5gate_and_dual_model_manifests() -> None:
    sv_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v1_5gate_selfval_20261123.json"
    bm_p = CODESK_ROOT / "docs/results-manifests/rb_osw2_synth_v1_sol61_astra_20261123.json"
    mn_p = CODESK_ROOT / "lists/recreationbench_mined_top15_v2.json"
    assert sv_p.is_file() and bm_p.is_file() and mn_p.is_file()

    sv = json.loads(sv_p.read_text(encoding="utf-8"))
    assert sv["all_5_gates_valid"] is True
    assert len(sv["cases"]) == 6

    bm = json.loads(bm_p.read_text(encoding="utf-8"))
    assert bm["total_episodes"] == 24
    assert bm["total_non_yolo_agent_runs"] == 48
    for mkey in ("gpt-6.1-sol", "gpt-6-astra"):
        ms = bm["macro_summary"][mkey]
        assert ms["all_permission_audits_verified"] is True
        assert ms["mean_overlap_ratio"] >= 0.70
        assert ms["mean_token_inflation_ratio"] > 1.20
        assert ms["mean_cli_inflation_ratio"] > 1.50
        assert ms["total_shared_focus_flips"] > ms["total_isolated_focus_flips"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
