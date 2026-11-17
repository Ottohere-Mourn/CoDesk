"""Unit tests for the 4-agent ultra-long-horizon real-web + real-software arenas (UA-01..UA-04)."""
from __future__ import annotations

from experiments.ultra_arenas_v1 import build_ultra_prompt
from tasks.ultra_arenas_v1.catalog import UA_BY_ID, ULTRA_ARENAS_CATALOG


def test_ultra_arenas_catalog_has_real_websites_and_long_horizon_bounds():
    assert len(ULTRA_ARENAS_CATALOG) == 15
    for row in ULTRA_ARENAS_CATALOG:
        assert len(row["roles"]) == 4
        assert len(row["real_websites"]) >= 5
        assert all(u.startswith("https://") for u in row["real_websites"])
        assert float(row["critical_section_lower_bound_s"]) >= 1600.0
        assert int(row["conc_role_timeout_s"]) >= 2400
    for fid in ("UA-08", "UA-09", "UA-10", "UA-11", "UA-12", "UA-13", "UA-14", "UA-15"):
        assert fid in UA_BY_ID
        assert float(UA_BY_ID[fid]["critical_section_lower_bound_s"]) >= 2160.0
        assert int(UA_BY_ID[fid]["conc_role_timeout_s"]) >= 3600
        assert len(UA_BY_ID[fid]["real_websites"]) >= 16


def test_blind_natural_prompt_contains_zero_peer_spoilers():
    p_nc = build_ultra_prompt("FIN", "Complete Q3 sheet.", 2700, "no_comm")
    assert "colleague" not in p_nc.lower()
    assert "other agent" not in p_nc.lower()
    assert "SCRATCHPAD" not in p_nc
    p_pad = build_ultra_prompt("FIN", "Complete Q3 sheet.", 2700, "shared_scratchpad")
    assert "/workspace/.coord/SCRATCHPAD.md" in p_pad
