"""Contract, prompt-hygiene, static-audit, harness-isolation & 5-gate/eval manifest tests for reworked novel_frontier_v1."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tasks.novel_frontier_v1.common import verify_prompt_hygiene
from tasks.novel_frontier_v1.registry import (
    AUTHENTIC_TOP5_MODULES,
    NF_BY_ID,
    RETAINED_TOP5_CATALOG,
    RETAINED_TOP5_IDS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = Path.home() / ".codex/skills/paragui-case-design/scripts/audit_case_module.py"
SELFVAL_MANIFEST = REPO_ROOT / "docs/results-manifests/novel_frontier_v2_authentic_5gate_20261124.json"
EVAL_MANIFEST = REPO_ROOT / "docs/results-manifests/novel_frontier_v2_authentic_top5_eval_20261124.json"


def _load_tool(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reworked_authentic_top5_structure() -> None:
    assert RETAINED_TOP5_IDS == ("NF-01", "NF-05", "NF-11", "NF-13", "NF-14")
    assert len(AUTHENTIC_TOP5_MODULES) == 5
    assert len(RETAINED_TOP5_CATALOG) == 5
    assert set(NF_BY_ID.keys()) == set(RETAINED_TOP5_IDS)

    tracks = [m["track"] for m in RETAINED_TOP5_CATALOG]
    assert tracks.count("track1_isolated_screen") == 2
    assert tracks.count("track2_shared_state") == 3

    ports = [m["portal_port"] for m in RETAINED_TOP5_CATALOG]
    assert len(set(ports)) == 5
    for m in RETAINED_TOP5_CATALOG:
        assert m["max_cua_calls"] is None and int(m["conc_role_timeout_s"]) >= 7200
        assert len(m["roles"]) == 2


def test_prompt_hygiene_and_driver_agnosticism_all_5() -> None:
    for mod in AUTHENTIC_TOP5_MODULES:
        tickets = mod.build_tickets_by_role()
        assert set(tickets.keys()) == set(mod.META["roles"])
        hygiene = verify_prompt_hygiene(tickets)
        assert hygiene["ok"], f"{mod.TASK_ID} failed prompt hygiene: {hygiene['forbidden_hits']}"


def test_paragui_static_auditor_zero_fail_zero_warn() -> None:
    auditor = _load_tool(AUDIT_SCRIPT, "audit_case_module")
    pkg_dir = REPO_ROOT / "tasks/novel_frontier_v1"
    for py_f in sorted(pkg_dir.glob("*.py")):
        if py_f.name in ("__init__.py", "registry.py"):
            continue
        res = auditor.audit_python_file(py_f)
        assert res["status"] == "PASS", f"{py_f.name}: {res}"
    runner_res = auditor.audit_python_file(REPO_ROOT / "experiments/novel_frontier_v1.py")
    assert runner_res["status"] == "PASS", f"Runner audit failed: {runner_res}"


def test_harness_readonly_grading_and_x11_cli_isolation() -> None:
    runner_src = (REPO_ROOT / "experiments/novel_frontier_v1.py").read_text(encoding="utf-8")
    stop_idx = runner_src.index("def stop_and_grade")
    stop_blk = runner_src[stop_idx:stop_idx + 1200].lower()
    assert "ctrl+s" not in stop_blk
    assert "xdotool" not in stop_blk
    exec_idx = runner_src.index("def exec_role")
    exec_blk = runner_src[exec_idx:exec_idx + 900]
    assert "DISPLAY=:99" not in exec_blk
    assert "/tmp/.X11-unix" not in exec_blk
    assert '"--pid", f"container:{self.container_name}"' in runner_src


def test_reworked_top5_5gate_self_validation_manifest() -> None:
    assert SELFVAL_MANIFEST.is_file()
    data = json.loads(SELFVAL_MANIFEST.read_text(encoding="utf-8"))
    assert data["all_5_gates_valid"] is True
    assert set(data["cases"].keys()) == set(RETAINED_TOP5_IDS)
    for tid, c in data["cases"].items():
        assert c["all_5_gates_valid"] is True, f"{tid} failed 5-gate validation"
        assert c["gate1_pristine_pass"] is False and c["gate1_pristine_score"] <= 0.20
        assert c["gate2_seq_ab_pass"] is True and c["gate2_seq_ab_score"] >= 0.99
        assert c["gate3_seq_ba_pass"] is True and c["gate3_seq_ba_score"] >= 0.99
        assert c["gate4_contention_surface_active"] is True and c["gate4_contention_pass"] is False
        assert c["gate5_careful_conc_pass"] is True and c["gate5_careful_conc_score"] >= 0.99
        assert c["gate5_within_55pct_budget"] is True


def test_reworked_top5_dual_model_eval_manifest_when_present() -> None:
    if not EVAL_MANIFEST.is_file():
        return
    ev = json.loads(EVAL_MANIFEST.read_text(encoding="utf-8"))
    assert tuple(ev["retained_rebuilt_cases"]) == RETAINED_TOP5_IDS
    v5 = ev["v5_final_wave_40_actors"]
    for m_key in ("gpt-6.1-sol", "gpt-6-astra"):
        iso_b = v5[f"isolated_{m_key}"]
        shr_b = v5[f"shared_{m_key}"]
        assert iso_b["permission_audit_ok_actors"] == 10 and shr_b["permission_audit_ok_actors"] == 10
        assert shr_b["mean_score_avg"] < iso_b["mean_score_avg"]
        assert set(shr_b["tasks"].keys()) == set(RETAINED_TOP5_IDS)
