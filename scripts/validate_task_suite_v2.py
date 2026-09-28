#!/usr/bin/env python3
"""Validate completed real-Guest episodes listed in the V2 task suite manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tasks/task_suite_v2.json"
DEFAULT_RUN_ROOT = Path("/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/task-suite-v2")
FULL_ID = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object in {path}")
    return value


def validate_episode(episode: dict[str, Any], task_id: str, run_root: Path) -> dict[str, Any]:
    episode_id = episode["episode_id"]
    declared_dir = episode.get("artifact_dir")
    artifact_dir = (ROOT / declared_dir).resolve() if declared_dir else (run_root / episode_id).resolve()
    if not artifact_dir.is_relative_to(ROOT) and not str(artifact_dir).startswith(
            "/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/"):
        raise ValidationError(f"{episode_id}: artifact_dir escapes project/artifact roots")
    report_path = artifact_dir / "report.json"
    report = _read_json(report_path)
    if report.get("scenario") != episode["scenario"]:
        raise ValidationError(f"{episode_id}: report scenario does not match manifest")
    if report.get("task_id") not in {None, task_id, "BROWSER-GUI-CLI-001", "FOCUS-001"}:
        raise ValidationError(f"{episode_id}: unexpected task id {report.get('task_id')!r}")
    if report.get("task_version") != "2.0.0":
        raise ValidationError(f"{episode_id}: task_version is not frozen at 2.0.0")
    metadata = report.get("episode_metadata")
    if not isinstance(metadata, dict) or metadata.get("metadata_schema_version") != 1:
        raise ValidationError(f"{episode_id}: missing episode metadata schema v1")
    provenance_path = artifact_dir / str(report.get("provenance_file", "provenance.json"))
    provenance = _read_json(provenance_path)
    if provenance.get("artifact_sha256", {}).get("report.json") is None:
        raise ValidationError(f"{episode_id}: provenance has no report digest")
    if provenance.get("resources", {}).get("guest_created_and_destroyed") is not True:
        raise ValidationError(f"{episode_id}: provenance does not prove ledgered Guest lifecycle")
    evaluation = report.get("evaluation") or {}
    reset = report.get("reset_check") or {}
    if reset.get("success") is not True:
        raise ValidationError(f"{episode_id}: environment reset did not pass")
    if report.get("success") is not True:
        raise ValidationError(f"{episode_id}: scenario or reset did not pass")
    outcome = episode["expected"]
    if outcome == "pass":
        if evaluation.get("success") is not True or report.get("scenario_success") is not True:
            raise ValidationError(f"{episode_id}: expected successful goal evaluation")
    elif outcome == "detected_failure":
        if evaluation.get("success") is not False or report.get("scenario_success") is not True:
            raise ValidationError(f"{episode_id}: expected evaluator-detected failure control")
    else:
        raise ValidationError(f"{episode_id}: unknown expected result {outcome!r}")

    events_path = artifact_dir / "events.jsonl"
    if not events_path.is_file():
        raise ValidationError(f"{episode_id}: missing event log")
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    event_actors = {row.get("actor") for row in events}
    required = {"evaluator"}
    missing_events = required - event_actors
    if missing_events:
        raise ValidationError(f"{episode_id}: missing event sources {sorted(missing_events)}")
    actor_ids = set((report.get("actors") or {}).keys())
    if len(actor_ids) < 1:
        raise ValidationError(f"{episode_id}: no actor results recorded")
    expected_actors = set(episode.get("active_actors", []))
    if actor_ids != expected_actors:
        raise ValidationError(f"{episode_id}: actor roster {sorted(actor_ids)} does not match "
                              f"manifest {sorted(expected_actors)}")
    environment_ids = {value.get("environment_id") for value in (report.get("actors") or {}).values()
                       if isinstance(value, dict) and value.get("environment_id")}
    if len(environment_ids) != 1:
        raise ValidationError(f"{episode_id}: actors do not share exactly one environment id")
    guest_ids = {row.get("details", {}).get("guest_container_id") for row in events
                 if row.get("actor") in actor_ids
                 and row.get("details", {}).get("guest_container_id")}
    if len(guest_ids) != 1:
        raise ValidationError(f"{episode_id}: actor events do not identify exactly one shared Guest")
    guest_id = next(iter(guest_ids))
    reported_guest_id = (report.get("same_guest_container_id")
                         or report.get("shared_guest_container_id"))
    if not FULL_ID.fullmatch(str(reported_guest_id or "")) or reported_guest_id != guest_id:
        raise ValidationError(f"{episode_id}: report and actor trace do not agree on full Guest ID")
    screenshots = list(artifact_dir.glob("observation-*.png"))
    screenshots += list(artifact_dir.glob("observation-refresh-*.png"))
    screenshots += [artifact_dir / "guest-screen.png"] if (artifact_dir / "guest-screen.png").is_file() else []
    if not screenshots or not (artifact_dir / "reset-check/guest-screen.png").is_file():
        raise ValidationError(f"{episode_id}: missing task screenshot or reset screenshot")
    if not evaluation:
        raise ValidationError(f"{episode_id}: hidden-state evaluator result is missing")

    ledger_path = artifact_dir / "resource-events.jsonl"
    ledger_present = ledger_path.is_file()
    if ledger_present:
        ledger = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()
                  if line.strip()]
        resource_events = {(row.get("event"), row.get("resource_type")) for row in ledger}
        if ("created", "container") not in resource_events or ("destroyed", "container") not in resource_events:
            raise ValidationError(f"{episode_id}: Guest ownership ledger lacks create/destroy records")
    elif not episode.get("legacy_artifact"):
        raise ValidationError(f"{episode_id}: missing resource ownership ledger")
    reset_guest_id = (reset.get("previous_guest_container_id"), reset.get("new_guest_container_id"))
    if (reset_guest_id[0] != guest_id or not FULL_ID.fullmatch(str(reset_guest_id[1] or ""))
            or reset_guest_id[0] == reset_guest_id[1]):
        raise ValidationError(f"{episode_id}: reset did not create a distinct clean Guest")
    for relative, expected_digest in provenance.get("artifact_sha256", {}).items():
        candidate = (artifact_dir / relative).resolve()
        if not candidate.is_relative_to(artifact_dir.resolve()) or not candidate.is_file():
            raise ValidationError(f"{episode_id}: invalid provenance artifact path {relative!r}")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_digest:
            raise ValidationError(f"{episode_id}: artifact digest mismatch for {relative}")

    return {"task_id": task_id, "episode_id": episode_id, "condition": episode["condition"],
            "scenario": report["scenario"], "success": True,
            "evaluator_success": bool(evaluation.get("success")),
            "reset_success": True, "environment_id": next(iter(environment_ids)),
            "guest_container_id": guest_id, "resource_ledger_present": ledger_present,
            "actor_ids": sorted(actor_ids), "event_count": len(events),
            "screenshot_count": len(screenshots), "artifact_dir": str(artifact_dir)}


def validate_suite(manifest_path: Path, run_root: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 2:
        raise ValidationError("suite must contain at least two task classes")
    results: list[dict[str, Any]] = []
    for task in tasks:
        episodes = task.get("episodes") if isinstance(task, dict) else None
        if not isinstance(episodes, list) or not episodes:
            raise ValidationError("each task must list episodes")
        conditions = {row.get("condition") for row in episodes}
        for expected_condition in ("solo", "naive_failure_trigger", "coordination_recovery"):
            if expected_condition not in conditions:
                raise ValidationError(f"{task.get('task_id')}: missing {expected_condition}")
        task_actors = set((task.get("actors") or {}).keys())
        if task.get("task_version") != manifest.get("suite_version"):
            raise ValidationError(f"{task.get('task_id')}: task and suite versions differ")
        solo_actors = {actor_id for row in episodes if row.get("condition") == "solo"
                       for actor_id in row.get("active_actors", [])}
        if solo_actors != task_actors:
            raise ValidationError(f"{task.get('task_id')}: solo episodes do not cover every actor")
        for joint_condition in ("naive_failure_trigger", "coordination_recovery"):
            joint_rosters = [set(row.get("active_actors", [])) for row in episodes
                             if row.get("condition") == joint_condition]
            if task_actors not in joint_rosters:
                raise ValidationError(f"{task.get('task_id')}: {joint_condition} lacks all actors")
        results.extend(validate_episode(row, task["task_id"], run_root) for row in episodes)
    return {"suite_id": manifest.get("suite_id"), "suite_version": manifest.get("suite_version"),
            "environment": manifest.get("environment"), "validated_episode_count": len(results),
            "task_count": len(tasks), "all_validated": True, "episodes": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_suite(args.manifest, args.run_root)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
