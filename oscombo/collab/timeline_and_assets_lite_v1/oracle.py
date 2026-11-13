"""Score the saved native Kdenlive project, including every occupied track."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from . import spec


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame(timecode: str) -> int:
    hours, minutes, seconds = timecode.split(":")
    total = (int(hours) * 3600 + int(minutes) * 60) * 1000 + round(float(seconds) * 1000)
    frames = round(total * spec.FPS / 1000)
    if abs(total - frames * 1000 / spec.FPS) > 1:
        raise ValueError(f"non-frame-aligned timecode: {timecode}")
    return frames


def _playlist(root: ET.Element, playlist_id: str, resources: dict[str, str]) -> list[dict]:
    node = root.find(f"playlist[@id='{playlist_id}']")
    if node is None:
        raise ValueError(f"missing native playlist {playlist_id}")
    cursor = 0
    entries = []
    for child in node:
        if child.tag == "blank":
            cursor += _frame(child.attrib["length"])
        elif child.tag == "entry":
            source = resources[child.attrib["producer"]]
            start = _frame(child.attrib["in"])
            end = _frame(child.attrib["out"])
            duration = end - start + 1
            entries.append({"asset": Path(source).name, "position": cursor,
                            "source_in": start, "duration": duration})
            cursor += duration
    return entries


def project_state(path: Path) -> dict:
    root = ET.parse(path).getroot()
    if root.tag != "mlt" or root.attrib.get("producer") != "main_bin":
        raise ValueError("not a native Kdenlive MLT project")
    profile = root.find("profile")
    if profile is None:
        raise ValueError("missing Kdenlive profile")
    resources = {}
    for producer in root.findall("producer"):
        props = {p.attrib.get("name"): p.text for p in producer.findall("property")}
        resources[producer.attrib["id"]] = props.get("resource", "")
    bin_entries = root.find("playlist[@id='main_bin']")
    if bin_entries is None:
        raise ValueError("missing Kdenlive Project Bin")
    bin_assets = [Path(resources[e.attrib["producer"]]).name
                  for e in bin_entries.findall("entry")]
    tracks = {name: _playlist(root, name, resources) for name in
              ("playlist0", "playlist1", "playlist2", "playlist3",
               "playlist4", "playlist5", "playlist6", "playlist7")}
    return {"profile": {k: profile.attrib.get(k) for k in
                        ("width", "height", "frame_rate_num", "frame_rate_den")},
            "bin_assets": sorted(bin_assets), "tracks": tracks}


def evaluate(workspace: Path, baseline_hashes: dict[str, str],
             messages: list[dict] | None = None, require_collaboration: bool = False) -> dict:
    root = Path(workspace)
    checks = {}
    for name in spec.MEDIA:
        relative = f"assets/{name}"
        path = root / relative
        checks[f"protected_{name}"] = path.is_file() and sha256(path) == baseline_hashes.get(relative)
    manifest = root / "shot_manifest.txt"
    checks["asset_manifest_saved"] = manifest.is_file() and manifest.read_text().splitlines() == [
        "middle_source=clip_02.mp4", "outtake_source=clip_04.mp4", "slot_frames=75-174"]
    project = root / spec.PROJECT
    checks["project_exists"] = project.is_file()
    state = None
    error = None
    if checks["project_exists"]:
        try:
            state = project_state(project)
        except (ET.ParseError, KeyError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
    checks["native_project_parseable"] = state is not None
    if state:
        checks["profile_320x180_25fps"] = state["profile"] == {
            "width": "320", "height": "180", "frame_rate_num": "25", "frame_rate_den": "1"}
        checks["all_five_bin_assets"] = state["bin_assets"] == sorted(spec.MEDIA)
        checks["v1_exact_three_shots"] = state["tracks"]["playlist4"] == [
            {"asset": "clip_01.mp4", "position": 0, "source_in": 0, "duration": 75},
            {"asset": "clip_02.mp4", "position": 75, "source_in": 0, "duration": 100},
            {"asset": "clip_03.mp4", "position": 175, "source_in": 0, "duration": 75},
        ]
        checks["other_video_lanes_empty"] = all(not state["tracks"][name] for name in
                                                  ("playlist5", "playlist6", "playlist7"))
        checks["music_bed_intact"] = state["tracks"]["playlist2"] == [
            {"asset": "music_bed.wav", "position": 0, "source_in": 0, "duration": 250}]
        checks["other_audio_lanes_empty"] = all(not state["tracks"][name] for name in
                                                  ("playlist0", "playlist1", "playlist3"))
    if require_collaboration:
        messages = messages or []
        checks["A_review_message"] = any(
            event.get("type") == "message" and event.get("actor") == "A" and
            event.get("recipient") in ("B", "all") and
            "clip_02.mp4" in str(event.get("body", "")) and
            "clip_04.mp4" in str(event.get("body", ""))
            for event in messages)
    return {"checks": checks, "state": state, "parse_error": error,
            "joint_business_success": bool(checks) and all(checks.values())}
