"""Native Kdenlive fixture and real GUI result regression checks."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from oscombo.collab.timeline_and_assets_lite_v1 import spec
from oscombo.collab.timeline_and_assets_lite_v1.oracle import evaluate, project_state, sha256
from oscombo.collab.timeline_and_assets_lite_v1.runner import TEMPLATE


def _workspace(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    target = tmp_path / "workspace"
    shutil.copytree(TEMPLATE, target)
    baseline = {p.relative_to(target).as_posix(): sha256(p)
                for p in target.rglob("*") if p.is_file()}
    return target, baseline


def test_native_starter_has_real_media_and_wrong_middle(tmp_path: Path) -> None:
    workspace, baseline = _workspace(tmp_path)
    result = evaluate(workspace, baseline)
    assert result["checks"]["native_project_parseable"]
    assert result["checks"]["all_five_bin_assets"]
    assert result["checks"]["music_bed_intact"]
    assert not result["checks"]["asset_manifest_saved"]
    assert result["state"]["tracks"]["playlist4"][1]["asset"] == "clip_04.mp4"
    assert result["state"]["tracks"]["playlist6"] == [
        {"asset": "clip_02.mp4", "position": 275, "source_in": 0, "duration": 100}]
    assert not result["joint_business_success"]


def test_actual_gui_saved_repair_passes(tmp_path: Path) -> None:
    workspace, baseline = _workspace(tmp_path)
    gold = Path(__file__).resolve().parents[1] / "oscombo/collab/timeline_and_assets_lite_v1/fixtures/private/gui_gold.kdenlive"
    shutil.copy2(gold, workspace / spec.PROJECT)
    (workspace / "shot_manifest.txt").write_text(
        "middle_source=clip_02.mp4\nouttake_source=clip_04.mp4\nslot_frames=75-174\n")
    result = evaluate(workspace, baseline)
    assert result["joint_business_success"], result["checks"]


def test_wrong_track_or_changed_media_rejected(tmp_path: Path) -> None:
    workspace, baseline = _workspace(tmp_path)
    gold = Path(__file__).resolve().parents[1] / "oscombo/collab/timeline_and_assets_lite_v1/fixtures/private/gui_gold.kdenlive"
    shutil.copy2(gold, workspace / spec.PROJECT)
    (workspace / "shot_manifest.txt").write_text(
        "middle_source=clip_02.mp4\nouttake_source=clip_04.mp4\nslot_frames=75-174\n")
    tree = ET.parse(workspace / spec.PROJECT)
    video = tree.getroot().find("playlist[@id='playlist4']")
    spare = tree.getroot().find("playlist[@id='playlist6']")
    spare.append(video.findall("entry")[1])
    tree.write(workspace / spec.PROJECT, encoding="utf-8", xml_declaration=True)
    result = evaluate(workspace, baseline)
    assert not result["joint_business_success"]
    assert not result["checks"]["other_video_lanes_empty"]
    (workspace / "assets/clip_02.mp4").write_bytes(b"tampered")
    assert not evaluate(workspace, baseline)["checks"]["protected_clip_02.mp4"]
