"""Unit tests for the 5-case Exam-Style GUI+CLI contention suite (EC-01..EC-05)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from experiments.exam_contention_v1 import build_exam_agent_prompt
from tasks.exam_contention_v1.common import FORBIDDEN_EXAM_PATTERNS
from tasks.exam_contention_v1.registry import CASE_MODULES, EC_BY_ID, EXAM_CONTENTION_CATALOG


def test_exam_contention_catalog_five_distinct_domains_and_open_gui_docs() -> None:
    assert len(EXAM_CONTENTION_CATALOG) == 5
    assert [m["id"] for m in EXAM_CONTENTION_CATALOG] == ["EC-01", "EC-02", "EC-03", "EC-04", "EC-05"]
    assert len({m["domain"] for m in EXAM_CONTENTION_CATALOG}) == 5
    assert len({m["portal_port"] for m in EXAM_CONTENTION_CATALOG}) == 5
    for meta in EXAM_CONTENTION_CATALOG:
        assert meta["id"] in EC_BY_ID
        assert len(meta["roles"]) == 2
        assert str(meta.get("open_gui_doc", "")).startswith("/workspace/")


def test_prompts_are_driver_agnostic_and_free_of_bans_or_peer_spoilers() -> None:
    for tid, mod in sorted(CASE_MODULES.items()):
        tickets = mod.build_tickets_by_role()
        assert set(tickets.keys()) == set(mod.META["roles"])
        for role, md in tickets.items():
            full_p = build_exam_agent_prompt(md, 1800).lower()
            for pat in FORBIDDEN_EXAM_PATTERNS:
                assert pat not in full_p, f"Forbidden pattern {pat!r} in {tid}/{role}"


def test_five_gate_deterministic_manifest_all_valid() -> None:
    manifest = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "results-manifests"
        / "exam_contention_v1_5gate_selfval_20261120.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["all_5_gates_valid"] is True
    assert len(data["cases"]) == 5
    for tid, entry in data["cases"].items():
        assert entry["all_5_gates_valid"] is True, tid
        assert entry["gate1_pristine_pass"] is False, tid
        assert entry["gate2_seq_ab_pass"] is True, tid
        assert entry["gate3_seq_ba_pass"] is True, tid
        assert entry["gate4_naive_race_pass"] is False, tid
        assert entry["gate5_careful_conc_pass"] is True, tid
        assert entry["gate5_within_55pct_budget"] is True, tid


def test_skill_static_auditor_passes_zero_fail_zero_warn_if_installed() -> None:
    auditor = Path.home() / ".codex/skills/paragui-case-design/scripts/audit_case_module.py"
    if not auditor.is_file():
        return
    repo_root = Path(__file__).resolve().parent.parent
    for target in (repo_root / "tasks/exam_contention_v1", repo_root / "experiments/exam_contention_v1.py"):
        cp = subprocess.run([sys.executable, str(auditor), "--json", str(target)], capture_output=True, text=True, check=True)
        rows = json.loads(cp.stdout)
        for row in rows:
            assert row["status"] == "PASS", row
            assert row["fails"] == [], row
            assert row["warns"] == [], row


def test_live_20episode_manifest_exhibits_non_yolo_and_contention_drop() -> None:
    manifest = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "results-manifests"
        / "exam_contention_v1_sol61_astra_20261121.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["total_live_episodes"] == 20
    assert data["all_non_yolo_verified"] is True
    summ = data["summary_by_model_and_mode"]
    for model in ("gpt-6.1-sol", "gpt-6-astra"):
        seq = summ[f"{model}:seq_ab"]
        conc = summ[f"{model}:shared"]
        assert seq["total_cases"] == 5 and conc["total_cases"] == 5
        assert seq["all_non_yolo_verified"] is True and conc["all_non_yolo_verified"] is True
        assert seq["joint_pass_rate"] > conc["joint_pass_rate"], model
