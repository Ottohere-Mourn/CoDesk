"""Unit and contract tests for exam_contention_v2 (updated $paragui-case-design suite)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from experiments.codesk_container_codex import validate_container_config_text
from experiments.exam_contention_v2 import (
    build_ec2_agent_prompt,
    build_ec2_codex_config,
    summarize_ec2_telemetry,
)
from tasks.exam_contention_v2.common import (
    FORBIDDEN_EXAM_V2_PATTERNS,
    build_grade_payload,
    verify_prompt_hygiene,
)
from tasks.exam_contention_v2.registry import (
    CANDIDATE_MODULES,
    CANDIDATE_POOL_CATALOG,
    EC2_BY_ID,
    RETAINED_TOP5_IDS,
)

CODESK_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = Path("/home/v-yukezhao/.codex/skills/paragui-case-design/scripts/audit_case_module.py")


def test_candidate_pool_and_top5_cover_both_contention_tracks() -> None:
    assert [m["id"] for m in CANDIDATE_POOL_CATALOG] == [f"EC2-C0{i}" for i in range(1, 10)]
    track1 = [m for m in CANDIDATE_POOL_CATALOG if m["track"] == "track1_isolated_screen"]
    track2 = [m for m in CANDIDATE_POOL_CATALOG if m["track"] == "track2_shared_state"]
    assert len(track1) == 5
    assert len(track2) == 4
    assert all(m["workspace_mode"] == "isolated" for m in track1)
    assert all(m["workspace_mode"] == "shared" for m in track2)

    assert len(RETAINED_TOP5_IDS) == 5
    assert len(set(RETAINED_TOP5_IDS)) == 5
    for tid in RETAINED_TOP5_IDS:
        assert tid in EC2_BY_ID
    top5_tracks = {EC2_BY_ID[tid]["track"] for tid in RETAINED_TOP5_IDS}
    assert top5_tracks == {"track1_isolated_screen", "track2_shared_state"}


def test_all_18_role_prompts_are_driver_agnostic_and_gag_free() -> None:
    driver_schema_leaks = (
        "desktop.click",
        "click_and_type",
        "qwen_cua_driver",
        "mcp_servers",
    )
    for tid, mod in CANDIDATE_MODULES.items():
        tickets = mod.build_tickets_by_role()
        assert tuple(tickets.keys()) == tuple(mod.META["roles"])
        hygiene = verify_prompt_hygiene(tickets)
        assert hygiene["ok"], f"{tid} hygiene failed: {hygiene}"
        for role, md in tickets.items():
            low = md.lower()
            for pat in FORBIDDEN_EXAM_V2_PATTERNS:
                assert pat not in low, f"{tid}/{role} leaked forbidden pattern {pat!r}"
            for leak in driver_schema_leaks:
                assert leak not in low, f"{tid}/{role} task.md hardcoded driver schema {leak!r}"
            # Runner wrapper must cleanly support both qwen_cua and xdotool with guest_bash enabled
            for drv in ("qwen_cua", "xdotool"):
                wrapped = build_ec2_agent_prompt(md, role, 1500, drv, 65)
                assert "guest_bash" in wrapped


def test_non_yolo_codex_configs_keep_gui_and_cli_enabled() -> None:
    for drv, expected_server in (("qwen_cua", "[mcp_servers.qwen_cua_driver]"), ("xdotool", "[mcp_servers.desktop]")):
        cfg = build_ec2_codex_config("gpt-6.1-sol", "high", gui_driver=drv)
        assert expected_server in cfg
        assert "[mcp_servers.guest_bash]" in cfg
        parsed = validate_container_config_text(
            cfg.replace("__CONTAINER_RELAY_PORT__", "18080"),
            mode="container-unrestricted",
        )
        assert parsed["sandbox_mode"] == "workspace-write"
        assert parsed["approval_policy"] == "never"


def test_partial_credit_rubric_and_telemetry_summary() -> None:
    g = build_grade_payload(
        task_id="EC2-TEST",
        checks_a=[("c1", True, 0.5, "e1"), ("c2", False, 0.5, "e2")],
        checks_b=[("b1", True, 1.0, "eb1")],
        checks_joint=[("j1", True, 0.25, "ej1")],
        tickets_by_role={"rA": "Clean task A", "rB": "Clean task B"},
        service_state={},
        wall_seconds=12.5,
        pass_threshold=0.90,
    )
    # Role A: (0.5 + 0.25) / 1.25 = 0.60; Role B: (1.0 + 0.25) / 1.25 = 1.00
    assert g["score_a"] == 0.6
    assert g["score_b"] == 1.0
    assert g["mean_score"] == 0.8
    assert g["pass_a"] is False
    assert g["pass_b"] is True
    assert g["joint_pass"] is False

    tl = [
        {"start_wall": 1.0, "role": "rA", "raw_tool": "click", "args": {"app": "VibraScope"}, "win_before": "VibraScope", "win_after": "VibraScope", "pointer_moved": True, "clipboard_changed": False},
        {"start_wall": 2.0, "role": "rB", "raw_tool": "hotkey", "args": {"app": "TelemetryHex"}, "win_before": "VibraScope", "win_after": "TelemetryHex", "pointer_moved": False, "clipboard_changed": True},
    ]
    tel = summarize_ec2_telemetry(tl, ("rA", "rB"), None, None)
    assert tel["interleaving_role_switches"] == 1
    assert tel["focus_flips"] == 1
    assert tel["misrouted_keystrokes"] == 1
    assert tel["pointer_moves"] == 1
    assert tel["clipboard_changes"] == 1


def test_5gate_self_validation_manifest_all_9_valid() -> None:
    mf = CODESK_ROOT / "docs/results-manifests/exam_contention_v2_9cand_5gate_selfval_20261122.json"
    assert mf.is_file()
    data = json.loads(mf.read_text(encoding="utf-8"))
    assert data["all_5_gates_valid"] is True
    assert len(data["cases"]) == 9
    for tid, row in data["cases"].items():
        assert row["all_5_gates_valid"] is True, f"{tid} failed 5-gate check: {row}"
        assert row["gate1_pristine_pass"] is False
        assert row["gate1_pristine_score"] <= 0.20
        assert row["gate2_seq_ab_pass"] is True and row["gate2_seq_ab_score"] == 1.0
        assert row["gate3_seq_ba_pass"] is True and row["gate3_seq_ba_score"] == 1.0
        assert row["gate4_contention_surface_active"] is True
        assert row["gate5_careful_conc_pass"] is True and row["gate5_careful_conc_score"] == 1.0
        assert row["gate5_within_55pct_budget"] is True


def test_empirical_broad_search_and_top5_dual_model_manifests() -> None:
    scr_p = CODESK_ROOT / "docs/results-manifests/exam_contention_v2_9cand_screening_20261122.json"
    top_p = CODESK_ROOT / "docs/results-manifests/exam_contention_v2_top5_sol61_astra_20261122.json"
    assert scr_p.is_file() and top_p.is_file()

    scr = json.loads(scr_p.read_text(encoding="utf-8"))
    assert scr["total_candidates_screened"] == 9
    assert scr["total_episodes_run"] == 18
    assert scr["all_permission_audits_verified"] is True
    assert tuple(scr["retained_top5_ids"]) == RETAINED_TOP5_IDS
    assert len(scr["filtered_out_ids"]) == 4

    top = json.loads(top_p.read_text(encoding="utf-8"))
    assert tuple(top["retained_top5_ids"]) == RETAINED_TOP5_IDS
    for model_key in ("gpt-6.1-sol", "gpt-6-astra"):
        ms = top["macro_summary"][model_key]
        assert ms["all_permission_audits_verified"] is True
        assert ms["shared_mean_score"] < ms["isolated_mean_score"]
        assert ms["shared_joint_pass_rate"] < ms["isolated_joint_pass_rate"]
        assert ms["mean_token_inflation_ratio"] > 1.25
        assert ms["mean_wall_inflation_ratio"] > 1.20
        assert ms["total_shared_focus_flips"] > ms["total_isolated_focus_flips"]


def test_skill_static_auditor_zero_fail_zero_warn() -> None:
    if not AUDIT_SCRIPT.is_file():
        return
    for target in (CODESK_ROOT / "tasks/exam_contention_v2", CODESK_ROOT / "experiments/exam_contention_v2.py"):
        cp = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--json", str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        rep = json.loads(cp.stdout)
        assert isinstance(rep, list) and len(rep) >= 1
        for item in rep:
            assert item["status"] == "PASS", f"Non-PASS on {target}: {item}"
            assert item["fails"] == [] and item["warns"] == [], f"Findings on {target}: {item}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
