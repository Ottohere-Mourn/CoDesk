#!/usr/bin/env python3
"""Aggregate preserved real Qwen Writer/Calc episodes; never grades an episode."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CONDITIONS = ("solo", "ma_id", "ma_sd")
ACTORS = ("writer_actor", "calc_actor")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def episode_artifact_integrity(episode_dir: Path) -> tuple[bool, list[str]]:
    provenance_path = episode_dir / "provenance.json"
    if not provenance_path.is_file():
        return False, ["provenance.json missing"]
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected = provenance.get("artifact_sha256")
    if not isinstance(expected, dict) or not expected:
        return False, ["provenance artifact_sha256 missing or empty"]
    errors = []
    for relative, expected_hash in expected.items():
        candidate = (episode_dir / relative).resolve()
        if not candidate.is_relative_to(episode_dir.resolve()) or not candidate.is_file():
            errors.append(f"artifact missing/outside episode root: {relative}")
            continue
        if sha256(candidate) != expected_hash:
            errors.append(f"artifact hash mismatch: {relative}")
    return not errors, errors


def load_episodes(root: Path) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in sorted(root.rglob("report.json")):
        episode_dir = path.parent.resolve()
        if episode_dir in seen:
            continue
        seen.add(episode_dir)
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (report.get("task_id") != "CODESK-TA-OFFICE-001"
                or report.get("actor_implementation") != "qwen3vl"
                or report.get("condition") not in CONDITIONS):
            continue
        intact, integrity_errors = episode_artifact_integrity(episode_dir)
        validity = report.get("episode_validity") or {}
        episodes.append({"path": episode_dir, "report": report,
                         "valid": validity.get("valid_for_agent_success_rate") is True,
                         "reset_ok": (report.get("reset_check") or {}).get("success") is True,
                         "provenance_ok": (report.get("provenance_status") == "complete"
                                           and (episode_dir / "provenance.json").is_file()),
                         "artifacts_ok": intact,
                         "integrity_errors": integrity_errors})
    for path in sorted(root.rglob("error.json")):
        episode_dir = path.parent.resolve()
        if episode_dir in seen:
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (report.get("task_id") != "CODESK-TA-OFFICE-001"
                or report.get("actor_implementation") != "qwen3vl"
                or report.get("condition") not in CONDITIONS):
            continue
        intact, integrity_errors = episode_artifact_integrity(episode_dir)
        episodes.append({"path": episode_dir, "report": report, "valid": False,
                         "reset_ok": (report.get("reset_check") or {}).get("success") is True,
                         "provenance_ok": (report.get("provenance_status") == "complete"
                                           and (episode_dir / "provenance.json").is_file()),
                         "artifacts_ok": intact,
                         "integrity_errors": integrity_errors})
        seen.add(episode_dir)
    for path in sorted(root.rglob("operator-abort.json")):
        episode_dir = path.parent.resolve()
        if episode_dir in seen:
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (report.get("task_id") != "CODESK-TA-OFFICE-001"
                or report.get("actor_implementation") != "qwen3vl"
                or report.get("condition") not in CONDITIONS):
            continue
        episodes.append({"path": episode_dir, "report": report, "valid": False,
                         "reset_ok": False,
                         "provenance_ok": False, "artifacts_ok": False,
                         "integrity_errors": ["operator-aborted before complete episode provenance"]})
    return episodes


def goal_success(ep: dict[str, Any], actor_id: str) -> bool | None:
    rows = ((ep["report"].get("evaluation") or {}).get("actor_goal_success") or {})
    row = rows.get(actor_id)
    return row.get("success") if isinstance(row, dict) else None


def condition_stats(episodes: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    attempts = [ep for ep in episodes if ep["report"].get("condition") == condition]
    valid = [ep for ep in attempts if ep["valid"]]
    result: dict[str, Any] = {
        "attempted": len(attempts),
        "valid": len(valid),
        "environment_invalid": len(attempts) - len(valid),
        "actors": {},
        "joint_success": {"successes": 0, "valid_episodes": 0},
        "integrity": {"reset_passes": sum(ep["reset_ok"] for ep in attempts),
                      "provenance_passes": sum(ep["provenance_ok"] for ep in attempts),
                      "artifact_passes": sum(ep["artifacts_ok"] for ep in attempts)},
        "interaction": {"focus_transitions": 0, "focus_conflicts": 0,
                        "input_misrouting": 0, "contamination_events": 0,
                        "cross_actor_stale_observations": 0,
                        "recovery_steps": 0},
        "actor_actions": {},
    }
    for actor_id in ACTORS:
        scores = [goal_success(ep, actor_id) for ep in valid]
        known = [score for score in scores if score is not None]
        result["actors"][actor_id] = {"successes": sum(known),
                                       "valid_scored": len(known)}
        action_counts = []
        execution_ms = []
        for ep in valid:
            actor = (ep["report"].get("actors") or {}).get(actor_id, {})
            if isinstance(actor.get("submitted_gui_action_count"), int):
                action_counts.append(actor["submitted_gui_action_count"])
            if isinstance(actor.get("model_turn_elapsed_ms"), (int, float)):
                execution_ms.append(float(actor["model_turn_elapsed_ms"]))
        result["actor_actions"][actor_id] = {
            "mean_gui_actions": round(sum(action_counts) / len(action_counts), 2)
                if action_counts else None,
            "mean_turn_execution_seconds": round(sum(execution_ms) / len(execution_ms) / 1000, 2)
                if execution_ms else None,
        }
    for ep in valid:
        goals = [goal_success(ep, actor_id) for actor_id in ACTORS]
        if all(score is not None for score in goals):
            result["joint_success"]["valid_episodes"] += 1
            result["joint_success"]["successes"] += int(all(goals))
        report = ep["report"]
        focus = report.get("focus_metrics") or {}
        result["interaction"]["focus_transitions"] += len(
            report.get("window_activation_events") or [])
        result["interaction"]["focus_conflicts"] += int(
            focus.get("focus_mismatch_action_count", 0))
        result["interaction"]["input_misrouting"] += int(
            focus.get("mis_input_action_count", 0))
        result["interaction"]["recovery_steps"] += int(
            focus.get("recovery_action_count", 0))
        result["interaction"]["contamination_events"] += len(
            report.get("contamination_events") or [])
        result["interaction"]["cross_actor_stale_observations"] += int(
            (report.get("failure_attribution") or {}).get(
                "cross_actor_stale_observations", 0))
    for actor_id, values in result["actors"].items():
        denominator = values["valid_scored"]
        values["success_rate"] = round(values["successes"] / denominator, 4) if denominator else None
    denominator = result["joint_success"]["valid_episodes"]
    result["joint_success"]["success_rate"] = (
        round(result["joint_success"]["successes"] / denominator, 4)
        if denominator else None)
    return result


def failure_rows(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ep in episodes:
        report = ep["report"]
        if ep["valid"] and (report.get("evaluation") or {}).get("success") is True:
            continue
        if ep["valid"]:
            category = report.get("model_failure_class", "unattributed_goal_failure")
        else:
            category = report.get("failure_class") or report.get("model_failure_class") \
                or report.get("failure_stage") \
                or report.get("episode_status") or "environment_invalid"
        rows.append({"run_id": report.get("run_id", ep["path"].name),
                     "condition": report.get("condition"),
                     "repeat": report.get("repeat"), "valid": ep["valid"],
                     "category": category,
                     "reason": report.get("reason") or report.get("error"),
                     "scenario_outcome": report.get("scenario_outcome"),
                     "actor_goal_success": {
                         actor_id: goal_success(ep, actor_id) for actor_id in ACTORS},
                     "actor_errors": report.get("model_actor_errors") or {
                         actor_id: (report.get("actors") or {}).get(actor_id, {}).get("error")
                         for actor_id in ACTORS
                         if (report.get("actors") or {}).get(actor_id, {}).get("error")},
                     "path": str(ep["path"]),
                     "observation_frames": [str(path.relative_to(ep["path"]))
                         for path in sorted((ep["path"] / "model-actors").glob(
                             "*/observations/*.png"))]})
    return rows


def write_reports(root: Path, report_path: Path, failures_path: Path) -> None:
    episodes = load_episodes(root)
    stats = {condition: condition_stats(episodes, condition) for condition in CONDITIONS}
    invalid = [ep for ep in episodes if not ep["valid"]]
    all_integrity_ok = all(ep["reset_ok"] and ep["provenance_ok"] and ep["artifacts_ok"]
                           for ep in episodes)
    lines = ["# CoDesk Writer + Calc: Real Dual-Agent Evaluation",
             "", "## Protocol and limits", "",
             "Task `CODESK-TA-OFFICE-001` version `1.0.0`; OSWorld V2.1; local Qwen3-VL-30B-A3B-Instruct through the existing OSWorld Qwen3VLAgent. Each model episode uses two distinct Qwen actor objects and one local inference process. MA-ID has two Guests; MA-SD has one shared Guest. Model schedules use the same fixed Writer/Calc round-robin order. Scripted episodes are excluded.",
             "", f"Artifact root: `{root}`. Attempts discovered: {len(episodes)}; all-attempt reset/provenance/artifact checks pass: `{all_integrity_ok}`.",
             "", "These are small task-specific observations, not a stable performance estimate.", "",
             "## Results by condition", "",
             "| Condition | Attempts | Valid | Env/service invalid | Writer | Calc | Joint | Reset / provenance / artifacts | Focus/window transitions | Focus conflicts | Misrouted input | Contamination | Cross-actor stale | Recovery actions |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for condition in CONDITIONS:
        row = stats[condition]
        a = row["actors"]
        joint = row["joint_success"]
        integrity = row["integrity"]
        interaction = row["interaction"]
        pct = lambda actor: (f"{a[actor]['successes']}/{a[actor]['valid_scored']}"
                             if a[actor]["valid_scored"] else "n/a")
        lines.append(
            f"| {condition} | {row['attempted']} | {row['valid']} | {row['environment_invalid']} | "
            f"{pct('writer_actor')} | {pct('calc_actor')} | "
            f"{joint['successes']}/{joint['valid_episodes']} | "
            f"{integrity['reset_passes']}/{row['attempted']} · "
            f"{integrity['provenance_passes']}/{row['attempted']} · "
            f"{integrity['artifact_passes']}/{row['attempted']} | "
            f"{interaction['focus_transitions']} | "
            f"{interaction['focus_conflicts']} | {interaction['input_misrouting']} | "
            f"{interaction['contamination_events']} | "
            f"{interaction['cross_actor_stale_observations']} | {interaction['recovery_steps']} |")
    lines.extend(["", "### Execution metrics", "",
                  "Per valid episode average model-turn elapsed time (includes observation, inference, and serial action submission); action counts are GUI submissions recorded by the Guest adapter.", ""])
    for condition in CONDITIONS:
        lines.append(f"- **{condition}:** " + "; ".join(
            f"{actor}: {stats[condition]['actor_actions'][actor]['mean_gui_actions']} GUI actions, "
            f"{stats[condition]['actor_actions'][actor]['mean_turn_execution_seconds']} s"
            for actor in ACTORS))
    lines.extend(["", "## Validity and interpretation", "",
                  f"{len(invalid)} attempts were marked environment/service/runner invalid and are excluded from model success denominators. Their IDs and reasons are retained in `REAL_DUAL_AGENT_FAILURE_CASES.md`.",
                  "A shared-desktop effect is attributed only when the episode is valid and both the event log shows input routed to the wrong active application and the final ODF evaluator shows corresponding unexpected state mutation. Goal misses without both forms of evidence remain model/task or unattributed failures. Staleness counts include only actions with another actor's commit since that actor's last observation; repeated actions within one model-issued action batch are not counted as cross-actor stale.",
                  "Recovery actions are observable focus-reacquisition actions after a focus mismatch (for example, explicit Alt+Tab or a later action that returns to the Actor's target window). This measures behavior and does not claim access to the model's internal conflict awareness.",
                  "Scripted negative controls are reported separately in the historical `REAL_APP_TRACK_A_RESULTS.md` and never mixed into this table.", "",
                  "## Reproduction", "",
                  "Run one episode at a time on a shared host; this preserves the single active model worker and limits MA-ID to two active task Guests. Example:", "",
                  "```bash",
                  "bash scripts/run_writer_calc_v1.sh --condition ma_id --repeat 1 \\",
                  "  --run-id <unique-run-id> \\",
                  "  --artifact-parent /mnt/raid1/mjh/CoDesk-V1-artifacts/real-dual-agent-eval \\",
                  "  --actor-implementation qwen3vl",
                  "```", ""])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    failures = failure_rows(episodes)
    failure_lines = ["# CoDesk Writer + Calc: Real Dual-Agent Failure Cases", "",
                     f"Source artifact root: `{root}`. {len(failures)} failed or invalid model attempts retained.", ""]
    if not failures:
        failure_lines.append("No failed or invalid Qwen model attempts were found in this artifact root.")
    for failure in failures:
        failure_lines.extend([f"## {failure['run_id']}", "",
            f"- Condition/repeat: `{failure['condition']}` / `{failure['repeat']}`",
            f"- Valid for model scoring: `{failure['valid']}`",
            f"- Category: `{failure['category']}`",
            f"- Reason: `{failure['reason']}`",
            f"- Scenario: `{failure['scenario_outcome']}`",
            f"- Actor goals: `{failure['actor_goal_success']}`",
            f"- Actor errors: `{failure['actor_errors']}`",
            f"- Artifacts: `{failure['path']}`", ""])
        if failure["observation_frames"]:
            failure_lines.append("Saved observation frames: " + ", ".join(
                f"`{relative}`" for relative in failure["observation_frames"]) + "")
        events_path = Path(failure["path"]) / "events.jsonl"
        if events_path.is_file():
            failure_lines.extend(["Event timeline:", "", "| seq | UTC | actor | event | window before → after | action |",
                                  "|---:|---|---|---|---|---|"])
            for line in events_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                details = event.get("details") or {}
                if event.get("kind") not in {"schedule", "model_decision", "gui", "actor"}:
                    continue
                before, after = details.get("active_window_before"), details.get("active_window_after")
                action = details.get("source_action", details.get("actor_id", ""))
                safe = lambda value: str(value or "").replace("|", "\\|").replace("\n", " ")
                failure_lines.append(
                    f"| {event.get('seq')} | {event.get('ts_utc')} | {event.get('actor')} | "
                    f"{event.get('action')} | {safe(before)} → {safe(after)} | {safe(action)} |")
            failure_lines.append("")
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    failures_path.write_text("\n".join(failure_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--report", type=Path,
                        default=Path("REAL_DUAL_AGENT_EVAL_REPORT.md"))
    parser.add_argument("--failures", type=Path,
                        default=Path("REAL_DUAL_AGENT_FAILURE_CASES.md"))
    args = parser.parse_args()
    write_reports(args.artifact_root.resolve(), args.report.resolve(), args.failures.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
