"""Unit tests for the 15-case artisan 2-agent fair contention suite (FC-01..FC-15)."""
from __future__ import annotations

import json
from pathlib import Path
import time

from experiments.fair_contention_v1 import build_fair_dual_prompt
from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    FORBIDDEN_PROMPT_PATTERNS,
    verify_stage_regime_purity,
)
from tasks.fair_contention_v1.registry import CASE_MODULES, FAIR_CONTENTION_CATALOG, FC_BY_ID


def test_fair_contention_catalog_has_15_unique_domains_and_ports() -> None:
    assert len(FAIR_CONTENTION_CATALOG) == 15
    ids = [m["id"] for m in FAIR_CONTENTION_CATALOG]
    assert ids == [f"FC-{i:02d}" for i in range(1, 16)]
    assert len({m["domain"] for m in FAIR_CONTENTION_CATALOG}) == 15
    assert len({m["conflict_archetype"] for m in FAIR_CONTENTION_CATALOG}) == 15
    assert len({m["portal_port"] for m in FAIR_CONTENTION_CATALOG}) == 15
    for meta in FAIR_CONTENTION_CATALOG:
        tid = meta["id"]
        assert tid in FC_BY_ID
        assert tid in CASE_MODULES
        assert len(meta["roles"]) == 2
        assert meta["conc_role_timeout_s"] >= 2200
        assert meta["seq_role_timeout_s"] >= 2800


def test_all_15_cases_pass_gate4_protocol_transparency_and_zero_forbidden_patterns() -> None:
    for tid, mod in sorted(CASE_MODULES.items()):
        audit = mod.audit_case_transparency()
        assert audit["ok"] is True, f"{tid} failed transparency audit: {audit}"
        assert audit["forbidden_hits"] == []
        assert audit["missing_public_tokens"] == []

        tickets = mod.build_tickets_by_role()
        assert set(tickets.keys()) == set(mod.META["roles"])
        for role, t_md in tickets.items():
            full_prompt = build_fair_dual_prompt(t_md, 3600).lower()
            for pat in FORBIDDEN_PROMPT_PATTERNS:
                assert pat not in full_prompt, f"Forbidden pattern {pat!r} found in {tid}/{role}"


def test_background_regime_sampler_and_stage_purity_verifier() -> None:
    state = {"mode": "REG_A"}
    with BackgroundRegimeSampler(lambda: state["mode"], "REG_A", interval=0.02) as s_pure:
        time.sleep(0.07)
    assert s_pure.purity == 1.0

    state["mode"] = "REG_B"
    with BackgroundRegimeSampler(lambda: state["mode"], "REG_A", interval=0.02) as s_contam:
        time.sleep(0.05)
    assert s_contam.purity == 0.0

    pstate = {
        "stage_purity": {
            "sub_a": {"s2": 1.0, "s3": 0.95, "s4": 1.0, "s5": 1.0},
            "sub_b": {"s2": 1.0, "s3": 0.40, "s4": 0.0, "s5": 0.0},
        }
    }
    assert verify_stage_regime_purity(pstate, "sub_a", ("s2", "s3", "s4", "s5")) == []
    errs_b = verify_stage_regime_purity(pstate, "sub_b", ("s2", "s3", "s4", "s5"))
    assert len(errs_b) == 3


def test_self_validation_manifest_proves_all_15_four_gate_valid() -> None:
    manifest = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "results-manifests"
        / "fair_contention_v1_self_validation_20261120.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["all_valid"] is True
    assert data["total_cases"] == 15
    assert len(data["cases"]) == 15
    for tid, entry in data["cases"].items():
        assert entry["all_4_gates_valid"] is True, tid
        assert entry["gate1_pristine_pass"] is False, tid
        assert entry["gate2a_seq_ab_pass"] is True, tid
        assert entry["gate2b_seq_ba_pass"] is True, tid
        assert entry["gate3_sim_race_pass"] is False, tid
        assert entry["gate4_protocol_transparency"]["ok"] is True, tid


def test_benchmark_results_manifest_zero_concurrent_pass_and_30m_floor() -> None:
    manifest = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "results-manifests"
        / "fair_contention_v1_sol61_astra_20261120.json"
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["four_gate_self_validation_all_15_passed"] is True
    for model_name in ("gpt-6.1-sol", "gpt-6-astra"):
        m_block = data["models"][model_name]
        assert m_block["joint_pass_count"] == 0, model_name
        assert m_block["total_tasks"] == 15, model_name
        assert len(m_block["results"]) == 15, model_name
        for tid, rep in m_block["results"].items():
            assert rep["joint_pass"] is False, (model_name, tid)
            assert rep["wall_seconds"] >= 1800.0, (model_name, tid, rep["wall_seconds"])
    seq = data["sequential_controls"]
    assert seq["FC-13_seq_ab_gpt-6.1-sol"]["joint_pass"] is True
    assert seq["FC-13_seq_ba_gpt-6.1-sol"]["joint_pass"] is True
