"""Unit tests for the 15-task 2-agent (dual-agent) stealth contention suite (SD-01..SD-15)."""
from __future__ import annotations

from experiments.stealth_dual_v1 import build_stealth_dual_prompt
from tasks.stealth_dual_v1.builders import _common_bench_footer
from tasks.stealth_dual_v1.catalog import SD_BY_ID, STEALTH_DUAL_CATALOG
from tasks.stealth_dual_v1.simulators import APPROVED_ECO_SPECS


def test_stealth_dual_15_diverse_two_agent_cases() -> None:
    assert len(STEALTH_DUAL_CATALOG) == 15
    domains = {c["domain"] for c in STEALTH_DUAL_CATALOG}
    ports = {c["portal_port"] for c in STEALTH_DUAL_CATALOG}
    assert len(domains) == 15
    assert len(ports) == 15
    for item in STEALTH_DUAL_CATALOG:
        tid = item["id"]
        assert tid in SD_BY_ID
        assert tid in APPROVED_ECO_SPECS
        assert len(item["roles"]) == 2
        assert tuple(item["seq_order"]) == (item["roles"][1], item["roles"][0])
        assert item["critical_section_lower_bound_s"] >= 1800.0
        assert len(item["real_websites"]) >= 4


def test_stealth_dual_prompts_have_zero_multi_agent_or_winner_spoilers() -> None:
    forbidden = ("teammate", "colleague", "peer agent", "other agent", "another agent", "cand-14", "race condition")
    for item in STEALTH_DUAL_CATALOG:
        tid = item["id"]
        ra, rb = item["roles"]
        p_a = build_stealth_dual_prompt(_common_bench_footer(tid, ra, is_rb=False), 4500).lower()
        p_b = build_stealth_dual_prompt(_common_bench_footer(tid, rb, is_rb=True), 4500).lower()
        for bad in forbidden:
            assert bad not in p_a, (tid, bad)
            assert bad not in p_b, (tid, bad)
