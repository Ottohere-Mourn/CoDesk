"""Shared archive completeness validation and manifest creation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .grade import validate_grade
from .permission_audit import VERIFIED_SCHEMA, verify_episode_permissions
from .timeline import TIMELINE_SCHEMA


MANIFEST_SCHEMA = "paragui.archive-manifest/v1"
_ACTOR_FILES = ("actions.jsonl", "codex_events.jsonl", "permission-audit-verified.json")
_RUN_FILES = ("grade.json", "report.json", "shared_timeline.json")


def _parse_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _validate_jsonl(path: Path) -> None:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def validate_batch(root: str | Path, *, ignore_incomplete_attempts: bool = False) -> dict[str, Any]:
    batch = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    cases_root = batch / "cases"
    trajectories_root = batch / "trajectories"
    if not cases_root.is_dir():
        errors.append("Missing cases/ directory")
    if not trajectories_root.is_dir():
        errors.append("Missing trajectories/ directory")
    case_ids: set[str] = set()
    if cases_root.is_dir():
        for case_dir in sorted(p for p in cases_root.iterdir() if p.is_dir()):
            config = case_dir / "case.json"
            if not config.is_file():
                errors.append(f"{config.relative_to(batch)} is missing")
                continue
            try:
                data = _parse_json(config)
                if data.get("case_id") != case_dir.name:
                    errors.append(f"case_id mismatch in {config.relative_to(batch)}")
                case_ids.add(case_dir.name)
            except Exception as exc:
                errors.append(f"Invalid {config.relative_to(batch)}: {exc}")
    run_count = 0
    if trajectories_root.is_dir():
        for case_dir in sorted(p for p in trajectories_root.iterdir() if p.is_dir()):
            if case_dir.name not in case_ids:
                errors.append(f"Trajectory case {case_dir.name} has no cases/{case_dir.name}/case.json")
            run_dirs = sorted(p for p in case_dir.iterdir() if p.is_dir())
            if not run_dirs:
                warnings.append(f"No runs archived for {case_dir.name}")
            for run_dir in run_dirs:
                run_count += 1
                # The opt-in tolerant mode is used only by concurrent episode
                # finalizers and the final batch report. report.json is written
                # after all required current-episode artifacts exist. Strict CLI
                # validation remains the default for packaging and regression tests.
                if ignore_incomplete_attempts and not (run_dir / "report.json").is_file():
                    warnings.append(f"Incomplete/unaccepted attempt retained but not graded: {run_dir.relative_to(batch)}")
                    continue
                for name in _RUN_FILES:
                    if not (run_dir / name).is_file():
                        errors.append(f"Missing {run_dir.relative_to(batch) / name}")
                actor_dirs = {"actor_a": run_dir / "actor_a", "actor_b": run_dir / "actor_b"}
                for actor, actor_dir in actor_dirs.items():
                    for name in _ACTOR_FILES:
                        path = actor_dir / name
                        if not path.is_file():
                            errors.append(f"Missing {path.relative_to(batch)}")
                        elif name.endswith(".jsonl"):
                            try:
                                _validate_jsonl(path)
                            except Exception as exc:
                                errors.append(str(exc))
                    cert = actor_dir / "permission-audit-verified.json"
                    if cert.is_file():
                        try:
                            cert_data = _parse_json(cert)
                            if cert_data.get("schema_version") != VERIFIED_SCHEMA or cert_data.get("verified") is not True:
                                errors.append(f"Permission certificate not verified/schema mismatch: {cert.relative_to(batch)}")
                            elif (actor_dir / "codex_events.jsonl").is_file():
                                entry = cert_data.get("entry_audit")
                                if not isinstance(entry, dict):
                                    errors.append(f"Permission certificate lacks entry_audit: {cert.relative_to(batch)}")
                                else:
                                    recomputed = verify_episode_permissions(
                                        entry,
                                        session_event_files=[actor_dir / "codex_events.jsonl"],
                                        expected_model=entry.get("model_id"),
                                    )
                                    def policy_rows(value: dict[str, Any]) -> list[tuple[Any, ...]]:
                                        return sorted(
                                            (row.get("sandbox_mode"), row.get("approval_policy"), row.get("model_id"), row.get("cwd"))
                                            for row in value.get("turn_contexts", [])
                                        )
                                    if policy_rows(cert_data) != policy_rows(recomputed):
                                        errors.append(f"Permission certificate disagrees with archived turn_context: {cert.relative_to(batch)}")
                        except Exception as exc:
                            errors.append(f"Invalid {cert.relative_to(batch)}: {exc}")
                grade_path = run_dir / "grade.json"
                if grade_path.is_file():
                    try:
                        validate_grade(_parse_json(grade_path))
                    except Exception as exc:
                        errors.append(f"Invalid {grade_path.relative_to(batch)}: {exc}")
                timeline_path = run_dir / "shared_timeline.json"
                if timeline_path.is_file():
                    try:
                        timeline = _parse_json(timeline_path)
                        if timeline.get("schema_version") != TIMELINE_SCHEMA or not isinstance(timeline.get("events"), list):
                            errors.append(f"Invalid timeline schema: {timeline_path.relative_to(batch)}")
                        starts = [int(e["start_wall_ms"]) for e in timeline.get("events", [])]
                        if starts != sorted(starts):
                            errors.append(f"Timeline events are not time-sorted: {timeline_path.relative_to(batch)}")
                        if not isinstance(timeline.get("aggregate"), dict):
                            errors.append(f"Timeline aggregate missing: {timeline_path.relative_to(batch)}")
                    except Exception as exc:
                        errors.append(f"Invalid {timeline_path.relative_to(batch)}: {exc}")
                report_path = run_dir / "report.json"
                if report_path.is_file():
                    try:
                        _parse_json(report_path)
                    except Exception as exc:
                        errors.append(f"Invalid {report_path.relative_to(batch)}: {exc}")
    if not case_ids:
        warnings.append("No Case definitions discovered")
    return {"ok": not errors, "case_count": len(case_ids), "run_count": run_count, "errors": errors, "warnings": warnings}


def build_manifest(root: str | Path, *, ignore_incomplete_attempts: bool = False) -> dict[str, Any]:
    batch = Path(root)
    validation = validate_batch(batch, ignore_incomplete_attempts=ignore_incomplete_attempts)
    if not validation["ok"]:
        raise ValueError("Archive is incomplete: " + "; ".join(validation["errors"]))
    files = []
    for area in (batch / "cases", batch / "trajectories"):
        for path in sorted(p for p in area.rglob("*") if p.is_file()):
            content = path.read_bytes()
            files.append({
                "path": path.relative_to(batch).as_posix(),
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
    return {
        "schema_version": MANIFEST_SCHEMA,
        "batch_id": batch.name,
        "case_count": validation["case_count"],
        "run_count": validation["run_count"],
        "file_count": len(files),
        "files": files,
    }


def write_manifest(root: str | Path, destination: str | Path | None = None, *, ignore_incomplete_attempts: bool = False) -> Path:
    batch = Path(root)
    target = Path(destination) if destination else batch / "archive-manifest.json"
    manifest = build_manifest(batch, ignore_incomplete_attempts=ignore_incomplete_attempts)
    # Concurrent episode finalizers may update the batch manifest simultaneously.
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target
