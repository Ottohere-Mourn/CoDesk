"""Unit tests for the curated 8-case high-quality benchmark suite (curated_8cases_v1)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tasks.curated_8cases_v1.registry import (
    CURATED_8_BY_ID,
    CURATED_8_CATALOG,
    CURATED_8_IDS,
    CURATED_8_MODULES,
    DEFAULT_ANTI_DEADLOCK_TIMEOUT_S,
    resolve_workspace_map,
    verify_svg_group_layers_non_empty,
)
from tasks.rb_osw2_synth_v3.common import FORBIDDEN_EXAM_V2_PATTERNS

CODESK_ROOT = Path(__file__).resolve().parents[1]
REPO_AUDITOR = CODESK_ROOT / ".agents/skills/paragui-case-design/scripts/audit_case_module.py"


def test_curated_8cases_exact_ids_and_hardened_metadata() -> None:
    expected = (
        "RBS3-04",
        "RBS3-05",
        "RBS3-02",
        "RBS2-06",
        "RBS-06",
        "RBS3-01",
        "EC-01",
        "EC-03",
    )
    assert CURATED_8_IDS == expected
    assert [m["id"] for m in CURATED_8_CATALOG] == list(expected)
    for tid in expected:
        meta = CURATED_8_BY_ID[tid]
        assert (CODESK_ROOT / meta["source_file"]).is_file(), tid
        assert len(meta["roles"]) == 2
        assert meta["max_cua_calls"] is None
        assert meta["iso_role_timeout_s"] >= DEFAULT_ANTI_DEADLOCK_TIMEOUT_S
        assert meta["conc_role_timeout_s"] >= DEFAULT_ANTI_DEADLOCK_TIMEOUT_S
        assert meta["workspace_mode"] in ("isolated", "shared")
        if meta["workspace_mode"] == "shared":
            assert meta["absent_peer_reference_fill_in_isolated"] is True
    assert CURATED_8_BY_ID["RBS3-05"]["share_desk_pid"] is True


def test_curated_8cases_prompts_driver_agnostic_and_clean() -> None:
    for tid, mod in CURATED_8_MODULES.items():
        tickets = mod.build_tickets_by_role()
        assert set(tickets.keys()) == set(CURATED_8_BY_ID[tid]["roles"])
        for role, md in tickets.items():
            low = md.lower()
            for pat in FORBIDDEN_EXAM_V2_PATTERNS:
                assert pat not in low, f"{tid}/{role} leaked forbidden pattern {pat!r}"
            for drv_leak in ("qwen_cua_driver", "desktop.click", "click_and_type"):
                assert drv_leak not in low, f"{tid}/{role} leaked driver schema {drv_leak!r}"


def test_workspace_map_resolution_and_svg_non_empty_checker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        iso_map = resolve_workspace_map("RBS3-01", root)
        assert len(set(iso_map.values())) == 2
        shr_map = resolve_workspace_map("EC-01", root)
        assert len(set(shr_map.values())) == 1

        req_ids = ("iec-emc-class-a-badge", "port-legend-qsfp", "thermal-airflow-notice")
        empty_svg = root / "empty.svg"
        empty_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g id="iec-emc-class-a-badge"/>'
            '<g id="port-legend-qsfp"><text>QSFP</text></g>'
            '<g id="thermal-airflow-notice"><rect width="10" height="10"/></g>'
            "</svg>",
            encoding="utf-8",
        )
        errs = verify_svg_group_layers_non_empty(empty_svg, req_ids)
        assert len(errs) == 1 and "iec-emc-class-a-badge" in errs[0]

        valid_svg = root / "valid.svg"
        valid_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g id="iec-emc-class-a-badge"><text>CLASS A</text></g>'
            '<g id="port-legend-qsfp"><text>QSFP</text></g>'
            '<g id="thermal-airflow-notice"><rect width="10" height="10"/></g>'
            "</svg>",
            encoding="utf-8",
        )
        assert verify_svg_group_layers_non_empty(valid_svg, req_ids) == []


def test_curated_manifest_and_static_auditor_pass() -> None:
    manifest_p = CODESK_ROOT / "lists/curated_high_quality_8cases_20261124.json"
    assert manifest_p.is_file()
    data = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data["total_cases"] == 8
    assert data["case_ids"] == list(CURATED_8_IDS)
    for entry in data["cases"]:
        assert entry["empirical_results"], entry["id"]

    assert REPO_AUDITOR.is_file()
    for target in (CODESK_ROOT / "tasks/curated_8cases_v1", CODESK_ROOT / "experiments/curated_8cases_v1.py"):
        cp = subprocess.run(
            [sys.executable, str(REPO_AUDITOR), "--json", str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(cp.stdout)
        for row in rows:
            assert row["status"] == "PASS", row
            assert row["fails"] == [], row
            assert row["warns"] == [], row
