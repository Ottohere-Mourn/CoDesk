"""Independent parser-based final-state Oracle for CDD-TLA-001."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import CASE_ID, CASE_VERSION, spec
from .fixture import parse_srt
from .mlt_project import parse_project


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not p.is_symlink()}


def _check(checks: list[dict[str, Any]], key: str, ok: bool, detail: str) -> None:
    checks.append({"id": key, "passed": bool(ok), "detail": detail})


def evaluate_artifacts(workspace: str | Path, *, baseline_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    """Score actor-visible deliverables without trusting GUI success messages.

    Gold ranges and exact required subtitle content are imported from private
    package code and must remain outside the mounted actor workspace.
    """
    root = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    shot_path = root / spec.SHOT_MANIFEST_RELATIVE
    project_path = root / spec.FINAL_PROJECT_RELATIVE
    subtitle_path = root / spec.FINAL_SUBTITLE_RELATIVE

    current_hashes = tree_hashes(root)
    protected_ok = True
    if baseline_hashes is not None:
        for name in spec.PROTECTED_WORKSPACE_FILES:
            if current_hashes.get(name) != baseline_hashes.get(name):
                protected_ok = False
                errors.append(f"protected fixture changed or missing: {name}")
    _check(checks, "starter_and_source_integrity", protected_ok,
           "all protected source media, catalog, brief and starter-project hashes match the run baseline")

    manifest: dict[str, Any] = {}
    try:
        manifest = json.loads(shot_path.read_text(encoding="utf-8"))
        rows = manifest.get("selected_shots", [])
        manifest_projection = [
            {key: row.get(key) for key in ("asset_id", "source_in_frame", "source_out_frame", "story_role")}
            for row in rows
        ]
        gold_projection = [
            {key: row[key] for key in ("asset_id", "source_in_frame", "source_out_frame", "story_role")}
            for row in spec.GOLD_SHOTS
        ]
        reason_ok = len(rows) == 3 and all(len(str(row.get("selection_reason", "")).strip()) >= 8 for row in rows)
        unused = manifest.get("unused_assets", [])
        outtake_ok = any(row.get("asset_id") == "ASSET-04" and row.get("timeline_use") is False
                         and len(str(row.get("reason", "")).strip()) >= 8 for row in unused)
        manifest_ok = (manifest.get("case_id") == CASE_ID and manifest.get("case_version") == CASE_VERSION
                       and manifest_projection == gold_projection and reason_ok and outtake_ok)
        if not manifest_ok:
            errors.append("asset shot manifest does not match the required selections, ranges, or outtake decision")
        _check(checks, "curation_manifest", manifest_ok,
               "A's traceable shot list has the required story sequence, ranges and nonempty selection rationale")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"asset shot manifest unreadable: {exc}")
        _check(checks, "curation_manifest", False, "manifest missing or malformed")

    project: dict[str, Any] = {}
    try:
        project = parse_project(project_path, fps=spec.FPS)
        expected_resources = {asset_id: str((root / relative).resolve())
                              for asset_id, relative in spec.GOLD_ASSET_RESOURCES.items()}
        resource_ok = project["bin_resources"] == expected_resources
        profile_ok = project.get("profile") == {"width": 320, "height": 180, "fps": spec.FPS}
        _check(checks, "project_profile_and_media_resources", resource_ok and profile_ok,
               "project profile is 320x180/25fps and each bin asset resolves to its frozen source file")
        if not resource_ok or not profile_ok:
            errors.append("project profile or source resource paths differ from the fixed fixture")
        actual_video = project["tracks"].get("Video 1", [])
        expected_video = [{key: shot[key] for key in ("asset_id", "source_in_frame", "source_out_frame",
                                                        "timeline_start_frame")}
                          for shot in spec.GOLD_SHOTS]
        video_projection = [{key: row[key] for key in expected_video[0]} for row in actual_video]
        video_ok = video_projection == expected_video
        _check(checks, "video_timeline", video_ok,
               "V1 asset identity/order, source in/out, timeline start and contiguity match the gold edit")
        if not video_ok:
            errors.append("V1 timeline differs from the gold shot order, trims, positions, or track")

        audio_rows = project["tracks"].get("Audio 1", [])
        expected_audio = [{key: spec.GOLD_AUDIO[key] for key in
                           ("asset_id", "source_in_frame", "source_out_frame", "timeline_start_frame")}]
        audio_projection = [{key: row[key] for key in expected_audio[0]} for row in audio_rows]
        audio_ok = audio_projection == expected_audio
        _check(checks, "audio_track", audio_ok,
               "the supplied bed is placed on A1 from frame 0 through the final frame")
        if not audio_ok:
            errors.append("A1 music bed is missing, misplaced, trimmed incorrectly, or duplicated")

        duration_ok = project["duration_frames"] == spec.GOLD_DURATION_FRAMES
        _check(checks, "total_duration", duration_ok,
               f"parsed project duration is {project['duration_frames']} frames; expected 250")
        if not duration_ok:
            errors.append("project duration is not exactly 10 seconds at 25 fps")

        bin_ok = (project["bin_assets"] == spec.GOLD_BIN_ASSETS
                  and sorted(project["bin_asset_entries"]) == sorted(spec.GOLD_BIN_ASSETS))
        track_set_ok = set(project["tracks"]) == {"Video 1", "Audio 1"}
        no_outtake = all(row["asset_id"] != "ASSET-04"
                         for rows in project["tracks"].values() for row in rows)
        _check(checks, "bin_and_non_target_preservation", bin_ok and no_outtake and track_set_ok,
               "the exact source bin and two required tracks are present; outtake remains only in the bin")
        if not bin_ok or not no_outtake or not track_set_ok:
            errors.append("source/bin inventory, target track set, or outtake placement is incorrect")

        filter_path = project.get("subtitle_filter_path") or ""
        filter_ok = bool(filter_path) and Path(filter_path).name == subtitle_path.name
        _check(checks, "subtitle_filter", filter_ok,
               "the Kdenlive project enables its native avfilter.subtitles sidecar")
        if not filter_ok:
            errors.append("project subtitle filter is absent or references a different sidecar")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"final project could not be parsed: {exc}")
        for key in ("video_timeline", "audio_track", "total_duration", "bin_and_non_target_preservation", "subtitle_filter"):
            _check(checks, key, False, "project missing or malformed")
        _check(checks, "project_profile_and_media_resources", False, "project missing or malformed")

    try:
        actual_cues = parse_srt(subtitle_path)
        subtitle_ok = actual_cues == list(spec.GOLD_SUBTITLES)
        _check(checks, "subtitle_content_and_timing", subtitle_ok,
               "subtitle text and exact cue times match the three shot beats")
        if not subtitle_ok:
            errors.append("subtitle cue count, text, or time range differs from the gold")
    except (OSError, ValueError) as exc:
        _check(checks, "subtitle_content_and_timing", False, "subtitle sidecar missing or malformed")
        errors.append(f"subtitle sidecar unreadable: {exc}")

    passed = bool(checks) and all(item["passed"] for item in checks)
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "status": "PASS" if passed else "FAIL",
        "joint_success": passed,
        "actor_subscores": {
            "A_asset_curation": next((c["passed"] for c in checks if c["id"] == "curation_manifest"), False),
            "B_timeline_edit": all(c["passed"] for c in checks if c["id"] in {
                "project_profile_and_media_resources", "video_timeline", "audio_track", "total_duration",
                "bin_and_non_target_preservation", "subtitle_filter", "subtitle_content_and_timing"}),
        },
        "checks": checks, "errors": errors,
        "observed_interference": "NOT_INFERRED_BY_FINAL_STATE_ORACLE; correlate GUI action and app-state traces",
        "note": "A correct final artifact does not prove a message exchange or a shared-desktop causal effect.",
    }
