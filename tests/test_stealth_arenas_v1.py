"""Unit tests for the 15-task diverse stealth-contention 4-agent benchmark (SA-01..SA-15)."""
from __future__ import annotations

from experiments.stealth_arenas_v1 import build_stealth_prompt
from tasks.stealth_arenas_v1.catalog import SA_BY_ID, STEALTH_ARENAS_CATALOG
from tasks.stealth_arenas_v1.simulators import role_bench_slug, role_close_token


def test_stealth_arenas_15_diverse_domains_and_ports():
    assert len(STEALTH_ARENAS_CATALOG) == 15
    domains = {row["domain"] for row in STEALTH_ARENAS_CATALOG}
    ports = {int(row["portal_port"]) for row in STEALTH_ARENAS_CATALOG}
    assert len(domains) == 15
    assert len(ports) == 15
    for row in STEALTH_ARENAS_CATALOG:
        assert len(row["roles"]) == 4
        assert set(row["roles"]) == set(row["seq_order"])
        assert len(row["real_websites"]) >= 6
        assert all(u.startswith("https://") for u in row["real_websites"])
        slugs = {role_bench_slug(row["id"], r) for r in row["roles"]}
        toks = {role_close_token(row["id"], r) for r in row["roles"]}
        assert len(slugs) == 4 and len(toks) == 4


def test_stealth_prompt_has_zero_multi_agent_spoilers():
    p = build_stealth_prompt("# Ticket CAD-101\nMachine pinion.", 3300)
    low = p.lower()
    for forbidden in ("colleague", "teammate", "other agent", "peer", "concurrent", "scratchpad", "drc_audit", "role_signoff"):
        assert forbidden not in low
