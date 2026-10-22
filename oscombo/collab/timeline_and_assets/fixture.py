"""Build/reset helpers for the fixed CDD-TLA-001 project fixture."""
from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path
from typing import Any

from . import spec
from .mlt_project import parse_project, write_project

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATE = PACKAGE_ROOT / "template"


def dump_srt(path: str | Path, cues: tuple[dict[str, Any], ...]) -> Path:
    def stamp(ms: int) -> str:
        hours, rem = divmod(ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, millis = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    lines: list[str] = []
    for i, cue in enumerate(cues, start=1):
        lines.extend([str(i), f"{stamp(cue['start_ms'])} --> {stamp(cue['end_ms'])}", cue["text"], ""])
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def parse_srt(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    def ms(stamp: str) -> int:
        hhmmss, frac = stamp.split(",")
        hh, mm, ss = (int(part) for part in hhmmss.split(":"))
        return ((hh * 60 + mm) * 60 + ss) * 1000 + int(frac)

    cues = []
    for block in text.split("\n\n"):
        rows = block.splitlines()
        if len(rows) < 3 or not rows[0].strip().isdigit() or " --> " not in rows[1]:
            raise ValueError("malformed SRT cue")
        start, end = rows[1].split(" --> ", 1)
        cues.append({"start_ms": ms(start), "end_ms": ms(end), "text": "\n".join(rows[2:])})
    return cues


def asset_definitions(workspace: str | Path) -> list[dict[str, str]]:
    root = Path(workspace)
    return [
        {"asset_id": "ASSET-01", "path": "../assets/clip_01.mp4", "kind": "video"},
        {"asset_id": "ASSET-02", "path": "../assets/clip_02.mp4", "kind": "video"},
        {"asset_id": "ASSET-03", "path": "../assets/clip_03.mp4", "kind": "video"},
        {"asset_id": "ASSET-04", "path": "../assets/clip_04.mp4", "kind": "video"},
        {"asset_id": "AUDIO-01", "path": "../assets/music_bed.wav", "kind": "audio"},
    ]


def write_initial_project(workspace: str | Path) -> Path:
    root = Path(workspace)
    assets = asset_definitions(root)
    video = [
        {"asset_id": "ASSET-01", "track": "Video 1", "source_in_frame": 0,
         "source_out_frame": 49, "timeline_start_frame": 0},
        {"asset_id": "ASSET-03", "track": "Video 1", "source_in_frame": 25,
         "source_out_frame": 74, "timeline_start_frame": 50},
    ]
    audio = [{"asset_id": "AUDIO-01", "track": "Audio 1", "source_in_frame": 0,
              "source_out_frame": 99, "timeline_start_frame": 0}]
    project = root / "project" / "GreenLoop.kdenlive"
    write_project(project, assets=assets, video=video, audio=audio, duration_frames=100,
                  subtitle_path="GreenLoop.kdenlive.srt")
    dump_srt(project.with_name(project.name + ".srt"), (
        {"start_ms": 0, "end_ms": 1800, "text": "Sort it for a second life."},
        {"start_ms": 2000, "end_ms": 3900, "text": "Ready for another use."},
    ))
    return project


def gold_manifest() -> dict[str, Any]:
    return {
        "case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
        "revision": 1, "selected_shots": [
            {**shot, "source_in_seconds": shot["source_in_frame"] / spec.FPS,
             "source_out_seconds_inclusive": shot["source_out_frame"] / spec.FPS,
             "selection_reason": f"Matches the {shot['story_role']} beat in the supplied footage."}
            for shot in spec.GOLD_SHOTS
        ],
        "unused_assets": [{"asset_id": "ASSET-04", "timeline_use": False,
                           "reason": "Lower-quality outtake; not part of the requested story."}],
    }


def write_gold_artifacts(workspace: str | Path) -> None:
    """Create the hidden all-correct candidate used by deterministic tests."""
    from .spec import GOLD_AUDIO, GOLD_DURATION_FRAMES, GOLD_SHOTS, GOLD_SUBTITLES
    root = Path(workspace)
    out = root / "deliverables"
    out.mkdir(parents=True, exist_ok=True)
    (out / "asset_shot_manifest.json").write_text(
        json.dumps(gold_manifest(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_project(out / "GreenLoop_Final.kdenlive", assets=asset_definitions(root),
                  video=[dict(x) for x in GOLD_SHOTS], audio=[dict(GOLD_AUDIO)],
                  duration_frames=GOLD_DURATION_FRAMES,
                  subtitle_path="GreenLoop_Final.kdenlive.srt")
    dump_srt(out / "GreenLoop_Final.kdenlive.srt", GOLD_SUBTITLES)


def materialize_template(destination: str | Path) -> Path:
    """Copy fixed case materials and construct the starter project."""
    dst = Path(destination)
    if dst.exists() and any(dst.iterdir()):
        raise FileExistsError(f"workspace must be empty: {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, dst, dirs_exist_ok=True)
    write_initial_project(dst)
    validate_fixed_fixture(dst)
    return dst


def validate_fixed_fixture(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace)
    catalog = json.loads((root / "asset_catalog.json").read_text(encoding="utf-8"))
    if catalog != spec.PUBLIC_ASSET_CATALOG:
        raise RuntimeError("public asset catalog differs from the frozen case spec")
    recorded = json.loads((root / "fixture_sha256.json").read_text(encoding="utf-8"))["sha256"]
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((root / "assets").iterdir()) if p.is_file()}
    if recorded != actual:
        raise RuntimeError("fixed media fixture hash mismatch")
    state = parse_project(root / spec.PROJECT_RELATIVE, fps=spec.FPS)
    if state["bin_assets"] != spec.GOLD_BIN_ASSETS or state["duration_frames"] != 100:
        raise RuntimeError("starter project structure is not the frozen partial initial state")
    return {"catalog": catalog, "asset_sha256": actual, "initial_project_state": state}
