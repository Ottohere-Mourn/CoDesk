#!/usr/bin/env python3
"""Recompute goal and contamination summaries from preserved episode reports.

This post-hoc audit never edits the episode reports. It separates unmet goals
that leave the initial state intact from unexpected saved-state mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any


INITIAL = {
    "writer_text": "Quarterly status report",
    "calc_cells": [["Record", "Status"], ["Quarterly", "Draft"]],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_report(path: Path, coordinator_row: dict[str, Any] | None = None) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    actual_by_binding = report["evaluation"]["final_state_by_binding"]
    expected_by_binding = report["evaluation"]["expected_state_by_binding"]
    goals = report["evaluation"]["actor_goal_success"]
    contamination: list[dict[str, Any]] = []
    state_mismatches: list[dict[str, Any]] = []
    for binding, expected in expected_by_binding.items():
        actual = actual_by_binding[binding]
        for field, value in actual.items():
            if value == expected[field]:
                continue
            mismatch = {"desktop_binding": binding, "field": field,
                        "expected": expected[field], "actual": value}
            state_mismatches.append(mismatch)
            if value != INITIAL[field]:
                contamination.append({**mismatch, "initial": INITIAL[field],
                                      "classification": "unexpected_state_mutation"})

    if report["condition"] == "ma_sd":
        final = actual_by_binding.get("shared_desktop", {})
        writer_in_calc = any(
            "Approved by GUI actor" in cell
            for row in final.get("calc_cells", []) for cell in row)
        writer_unchanged = final.get("writer_text") == INITIAL["writer_text"]
        attributed_input = report.get("focus_metrics", {}).get("mis_input_actions", [])
        trigger = bool(writer_in_calc and writer_unchanged and attributed_input)
        classification = ("shared_focus_interference_attributed" if trigger else
                          "document_setup_not_loaded" if (
                              final.get("writer_text") == INITIAL["writer_text"]
                              and final.get("calc_cells") == INITIAL["calc_cells"]
                              and any("Untitled" in str(event.get("after", ""))
                                      for event in report.get("window_activation_events", [])))
                          else "expected_interference_not_attributed")
        scenario_success = trigger
    else:
        scenario_success = all(item["success"] for item in goals.values())
        if scenario_success:
            classification = "all_isolated_goals_met"
        elif contamination:
            classification = "isolated_goal_failure_with_unexpected_mutation"
        else:
            classification = "isolated_goal_failure_state_unchanged"

    return {
        "episode_id": path.parents[1].name,
        "run_id": report["run_id"],
        "task_id": report["task_id"],
        "task_version": report["task_version"],
        "condition": report["condition"],
        "repeat": report["repeat"],
        "source_report": str(path),
        "source_report_sha256": sha256(path),
        "original_scenario_outcome": report.get("scenario_outcome"),
        "audited_scenario_outcome": classification,
        "scenario_success": scenario_success,
        "actor_goal_success": {actor: result["success"] for actor, result in goals.items()},
        "state_mismatches": state_mismatches,
        "contamination_events": contamination,
        "focus_metrics": {
            "mis_input_action_count": report.get("focus_metrics", {}).get("mis_input_action_count", 0),
            "unknown_input_action_count": report.get("focus_metrics", {}).get("unknown_input_action_count", 0),
            "recovery_action_count": report.get("focus_metrics", {}).get("recovery_action_count", 0),
            "window_activation_event_count": len(report.get("window_activation_events", [])),
        },
        "reset_success": report.get("reset_check", {}).get("success", False),
        "artifact_integrity": ((coordinator_row or {}).get("artifact_integrity")),
        "provenance_valid": ((coordinator_row or {}).get("provenance_valid")),
        "report_contract_valid": ((coordinator_row or {}).get("report_contract_valid")),
        "resource_lifecycle_valid": report.get("resource_lifecycle", {}).get(
            "all_containers_have_destroy_record", False)
            and report.get("resource_lifecycle", {}).get("labels_consistent", False),
        "elapsed_seconds": report.get("elapsed_seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    reports = sorted(root.glob("episodes/*/*/report.json"))
    if not reports:
        parser.error(f"no episode reports found under {root}")
    summary_path = root / "experiment_summary.json"
    if not summary_path.is_file():
        parser.error(f"missing coordinator summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    coordinator_by_report = {
        str(Path(item["report_path"]).resolve()): item
        for item in summary.get("episodes", []) if item.get("report_path")
    }
    rows = [audit_report(path, coordinator_by_report.get(str(path.resolve()))) for path in reports]
    counts: dict[str, Any] = {}
    for condition in ("solo", "ma_id", "ma_sd"):
        selected = [row for row in rows if row["condition"] == condition]
        counts[condition] = {
            "episodes": len(selected),
            "scenario_successes": sum(row["scenario_success"] for row in selected),
            "writer_goal_successes": sum(row["actor_goal_success"].get("writer_actor", False)
                                          for row in selected),
            "calc_goal_successes": sum(row["actor_goal_success"].get("calc_actor", False)
                                        for row in selected),
            "reset_successes": sum(row["reset_success"] for row in selected),
            "unexpected_mutation_episode_count": sum(bool(row["contamination_events"])
                                                      for row in selected),
            "median_elapsed_seconds": median(
                row["elapsed_seconds"] for row in selected if row["elapsed_seconds"] is not None),
        }
    output = args.output or root / "posthoc_evaluation_audit.v1.json"
    if output.exists():
        parser.error(f"refusing to overwrite existing audit: {output}")
    result = {
        "schema_version": 1,
        "task_family": "writer_calc_v1",
        "source_artifact_root": str(root),
        "classification_policy": {
            "goal_failure": "actor goal does not match final state",
            "contamination": "a mismatched saved field differs from both expected and task initial state",
            "ma_sd_success": "Writer text appears in Calc, Writer remains initial, and Writer input is event-attributed to Calc focus",
            "source_reports_modified": False,
        },
        "episode_count": len(rows),
        "counts_by_condition": counts,
        "scenario_success_count": sum(row["scenario_success"] for row in rows),
        "reset_success_count": sum(row["reset_success"] for row in rows),
        "resource_lifecycle_valid_count": sum(row["resource_lifecycle_valid"] for row in rows),
        "artifact_integrity_count": sum(row["artifact_integrity"] is True for row in rows),
        "provenance_valid_count": sum(row["provenance_valid"] is True for row in rows),
        "episodes": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "episode_count": len(rows),
                      "counts_by_condition": counts}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
