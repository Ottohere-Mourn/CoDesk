"""Small MLT/Kdenlive project serializer and read-only timeline parser.

This deliberately supports the subset used by CDD-TLA-001. It is not a
general-purpose Kdenlive project editor. Kdenlive GUI round-trip remains a
separate runtime gate.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def frame_time(frame: int, fps: int = 25) -> str:
    if frame < 0 or fps <= 0:
        raise ValueError("frame must be nonnegative and fps must be positive")
    ms = round(frame * 1000 / fps)
    seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_time(value: str, fps: int = 25) -> int:
    try:
        hh, mm, rest = value.split(":")
        ss, ms = rest.split(".")
        total_ms = ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(ms)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"unsupported MLT time value: {value!r}") from exc
    frame_float = total_ms * fps / 1000
    frame = round(frame_float)
    if abs(frame_float - frame) > 1e-8:
        raise ValueError(f"time {value!r} is not frame-aligned at {fps} fps")
    return frame


def _property(parent: ET.Element, name: str, value: object) -> None:
    child = ET.SubElement(parent, "property", {"name": name})
    child.text = str(value)


def _playlist_xml(parent: ET.Element, playlist_id: str, placements: list[dict[str, Any]],
                  duration_frames: int, fps: int) -> ET.Element:
    playlist = ET.SubElement(parent, "playlist", {"id": playlist_id})
    cursor = 0
    for placement in sorted(placements, key=lambda item: item["timeline_start_frame"]):
        start = int(placement["timeline_start_frame"])
        source_in = int(placement["source_in_frame"])
        source_out = int(placement["source_out_frame"])
        if start < cursor or source_out < source_in or start + source_out - source_in + 1 > duration_frames:
            raise ValueError("overlapping, negative, or out-of-range timeline placement")
        if start > cursor:
            blank = ET.SubElement(playlist, "blank", {"length": frame_time(start - cursor, fps)})
        entry = ET.SubElement(playlist, "entry", {
            "producer": placement["producer"], "in": frame_time(source_in, fps),
            "out": frame_time(source_out, fps),
        })
        _property(entry, "kdenlive:id", placement.get("timeline_item_id", "1"))
        cursor = start + source_out - source_in + 1
    if cursor < duration_frames:
        ET.SubElement(playlist, "blank", {"length": frame_time(duration_frames - cursor, fps)})
    return playlist


def write_project(path: str | Path, *, assets: list[dict[str, str]],
                  video: list[dict[str, Any]], audio: list[dict[str, Any]],
                  duration_frames: int, subtitle_path: str | None,
                  fps: int = 25, width: int = 320, height: int = 180) -> Path:
    """Write a compact MLT XML project with Kdenlive track metadata.

    `assets` entries have asset_id, path, and kind. Timeline placements add
    `asset_id`, source frame bounds, timeline start, and `track`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("mlt", {"LC_NUMERIC": "C", "producer": "main_bin", "version": "7.0"})
    ET.SubElement(root, "profile", {
        "description": "CoDesk 320x180 25 fps", "width": str(width), "height": str(height),
        "progressive": "1", "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "frame_rate_num": str(fps), "frame_rate_den": "1", "colorspace": "709",
    })

    producer_by_asset: dict[str, str] = {}
    for index, asset in enumerate(assets):
        producer_id = f"producer{index}"
        producer_by_asset[asset["asset_id"]] = producer_id
        producer = ET.SubElement(root, "producer", {"id": producer_id})
        _property(producer, "mlt_service", "avformat")
        _property(producer, "resource", asset["path"])
        _property(producer, "kdenlive:clipname", asset["asset_id"])
        _property(producer, "kdenlive:folderid", "")
        _property(producer, "kdenlive:id", index + 1)
        _property(producer, "kdenlive:clip_type", "1" if asset["kind"] == "video" else "2")
        _property(producer, "kdenlive:originalurl", asset["path"])

    black = ET.SubElement(root, "producer", {"id": "black_track"})
    _property(black, "mlt_service", "color")
    _property(black, "resource", "black")
    _property(black, "kdenlive:playlistid", "black_track")
    _property(black, "mlt_image_format", "rgba")

    video_rows = [x for x in video if x["track"] == "Video 1"]
    audio_rows = [x for x in audio if x["track"] == "Audio 1"]
    for item in video_rows + audio_rows:
        item["producer"] = producer_by_asset[item["asset_id"]]

    _playlist_xml(root, "playlist_video1", video_rows, duration_frames, fps)
    ET.SubElement(root, "playlist", {"id": "playlist_video1_mix"})
    _playlist_xml(root, "playlist_audio1", audio_rows, duration_frames, fps)
    ET.SubElement(root, "playlist", {"id": "playlist_audio1_mix"})

    track_video = ET.SubElement(root, "tractor", {"id": "track_video1", "in": "0",
                                                   "out": str(duration_frames - 1)})
    _property(track_video, "kdenlive:track_name", "Video 1")
    _property(track_video, "kdenlive:timeline_active", "1")
    _property(track_video, "kdenlive:trackheight", "67")
    ET.SubElement(track_video, "track", {"producer": "playlist_video1", "hide": "audio"})
    ET.SubElement(track_video, "track", {"producer": "playlist_video1_mix", "hide": "audio"})

    track_audio = ET.SubElement(root, "tractor", {"id": "track_audio1", "in": "0",
                                                   "out": str(duration_frames - 1)})
    _property(track_audio, "kdenlive:track_name", "Audio 1")
    _property(track_audio, "kdenlive:timeline_active", "1")
    _property(track_audio, "kdenlive:trackheight", "67")
    _property(track_audio, "kdenlive:audio_track", "1")
    ET.SubElement(track_audio, "track", {"producer": "playlist_audio1", "hide": "video"})
    ET.SubElement(track_audio, "track", {"producer": "playlist_audio1_mix", "hide": "video"})

    sequence = ET.SubElement(root, "tractor", {"id": "sequence0", "in": "0",
                                                 "out": str(duration_frames - 1)})
    _property(sequence, "kdenlive:uuid", "{6f59cb2a-2d8e-4d1c-8f1c-c0de00000001}")
    _property(sequence, "kdenlive:sequenceproperties.name", "GreenLoop")
    _property(sequence, "kdenlive:sequenceproperties.documentid", "CoDesk-GreenLoop")
    ET.SubElement(sequence, "track", {"producer": "black_track"})
    ET.SubElement(sequence, "track", {"producer": "track_video1"})
    ET.SubElement(sequence, "track", {"producer": "track_audio1", "hide": "video"})
    if subtitle_path:
        subtitle_filter = ET.SubElement(sequence, "filter", {"id": "subtitle_filter"})
        _property(subtitle_filter, "mlt_service", "avfilter.subtitles")
        _property(subtitle_filter, "internal_added", "237")
        _property(subtitle_filter, "av.filename", subtitle_path)
        _property(subtitle_filter, "kdenlive:locked", "1")

    bin_playlist = ET.SubElement(root, "playlist", {"id": "main_bin"})
    _property(bin_playlist, "kdenlive:docproperties.version", "1.1")
    _property(bin_playlist, "kdenlive:documentnotes", "CoDesk CDD-TLA-001 fixture")
    for asset in assets:
        entry = ET.SubElement(bin_playlist, "entry", {"producer": producer_by_asset[asset["asset_id"]]})
        _property(entry, "kdenlive:id", producer_by_asset[asset["asset_id"]].removeprefix("producer"))
    sequence_entry = ET.SubElement(bin_playlist, "entry", {"producer": "sequence0"})
    _property(sequence_entry, "kdenlive:id", "100")
    _property(sequence_entry, "kdenlive:clipname", "GreenLoop")

    wrapper = ET.SubElement(root, "tractor", {"id": "projecttractor", "in": "0",
                                                "out": str(duration_frames - 1)})
    _property(wrapper, "kdenlive:projectTractor", "1")
    ET.SubElement(wrapper, "track", {"producer": "sequence0", "in": "0",
                                      "out": str(duration_frames - 1)})
    ET.indent(root, space="  ")
    path.write_bytes(b"<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(root, encoding="utf-8") + b"\n")
    return path


def _properties(node: ET.Element) -> dict[str, str]:
    return {p.attrib["name"]: p.text or "" for p in node.findall("property") if "name" in p.attrib}


def _playlist_rows(playlist: ET.Element, producers: dict[str, dict[str, str]], fps: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = 0
    for child in playlist:
        if child.tag == "blank":
            cursor += parse_time(child.attrib["length"], fps)
        elif child.tag == "entry":
            source_in = parse_time(child.attrib["in"], fps)
            source_out = parse_time(child.attrib["out"], fps)
            p = producers.get(child.attrib["producer"], {})
            props = _properties(child)
            rows.append({
                "asset_id": props.get("cod:asset_id", p.get("kdenlive:clipname", "")),
                "source_in_frame": source_in, "source_out_frame": source_out,
                "timeline_start_frame": cursor,
                "duration_frames": source_out - source_in + 1,
            })
            cursor += source_out - source_in + 1
    return rows


def parse_project(path: str | Path, *, fps: int = 25) -> dict[str, Any]:
    """Parse the supported MLT/Kdenlive subset into an evaluator-friendly view."""
    root = ET.parse(path).getroot()
    profile_node = root.find("profile")
    profile = None
    if profile_node is not None:
        numerator = int(profile_node.attrib.get("frame_rate_num", fps))
        denominator = int(profile_node.attrib.get("frame_rate_den", "1"))
        if denominator != 1:
            raise ValueError("this case parser supports integer frame rates only")
        fps = numerator
        profile = {"width": int(profile_node.attrib.get("width", "0")),
                   "height": int(profile_node.attrib.get("height", "0")), "fps": fps}
    producers = {node.attrib["id"]: _properties(node) for node in root.findall("producer") if "id" in node.attrib}
    playlists = {node.attrib["id"]: node for node in root.findall("playlist") if "id" in node.attrib}
    tracks: dict[str, list[dict[str, Any]]] = {}
    for tractor in root.findall("tractor"):
        props = _properties(tractor)
        title = props.get("kdenlive:track_name")
        if not title:
            continue
        child_tracks = tractor.findall("track")
        if not child_tracks:
            continue
        playlist_id = child_tracks[0].attrib.get("producer", "")
        if playlist_id in playlists:
            tracks[title] = _playlist_rows(playlists[playlist_id], producers, fps)

    bin_assets: set[str] = set()
    bin_asset_entries: list[str] = []
    bin_resources: dict[str, str] = {}
    main_bin = playlists.get("main_bin")
    if main_bin is not None:
        for entry in main_bin.findall("entry"):
            producer_id = entry.attrib.get("producer", "")
            props = _properties(entry)
            asset_id = props.get("cod:asset_id") or producers.get(producer_id, {}).get("kdenlive:clipname")
            if asset_id:
                bin_assets.add(asset_id)
                bin_asset_entries.append(asset_id)
                resource = producers.get(producer_id, {}).get("resource")
                if resource:
                    candidate = Path(resource)
                    if not candidate.is_absolute():
                        candidate = Path(path).resolve().parent / candidate
                    bin_resources[asset_id] = str(candidate.resolve())

    subtitle_filter = None
    for prop in root.findall(".//filter/property"):
        if prop.attrib.get("name") == "mlt_service" and (prop.text or "") == "avfilter.subtitles":
            subtitle_filter = prop.getparent() if hasattr(prop, "getparent") else None
            break
    # ElementTree nodes do not expose parent; locate the filter by its service.
    subtitle_path = None
    for node in root.findall(".//filter"):
        props = _properties(node)
        if props.get("mlt_service") == "avfilter.subtitles":
            subtitle_path = props.get("av.filename")
            break

    duration = max((max((row["timeline_start_frame"] + row["duration_frames"] for row in rows), default=0)
                    for rows in tracks.values()), default=0)
    # Playlist trailing blanks are included so empty tail/audio duration counts.
    for tractor in root.findall("tractor"):
        if _properties(tractor).get("kdenlive:track_name"):
            for child in tractor.findall("track")[:1]:
                playlist = playlists.get(child.attrib.get("producer", ""))
                if playlist is not None:
                    total = 0
                    for item in playlist:
                        if item.tag == "blank":
                            total += parse_time(item.attrib["length"], fps)
                        elif item.tag == "entry":
                            total += parse_time(item.attrib["out"], fps) - parse_time(item.attrib["in"], fps) + 1
                    duration = max(duration, total)
    return {"tracks": tracks, "bin_assets": bin_assets, "bin_asset_entries": bin_asset_entries,
            "bin_resources": bin_resources,
            "subtitle_filter_path": subtitle_path, "duration_frames": duration,
            "fps": fps, "profile": profile}
