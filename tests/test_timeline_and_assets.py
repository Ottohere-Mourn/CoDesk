from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from oscombo.collab.timeline_and_assets import CASE_ID, CONDITIONS, spec
from oscombo.collab.timeline_and_assets.fixture import (
    asset_definitions, materialize_template, write_gold_artifacts,
)
from oscombo.collab.timeline_and_assets.integration import codex_collaboration_binding
from oscombo.collab.timeline_and_assets.interaction_log import append_event
from oscombo.collab.timeline_and_assets.mlt_project import frame_time, parse_project, write_project
from oscombo.collab.timeline_and_assets.oracle import evaluate_artifacts, tree_hashes
from oscombo.collab.timeline_and_assets.runner import (
    configure_run, evaluate_run, make_plan, prepare_run, reset_owned_run,
)


def _new_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    materialize_template(workspace)
    baseline = tree_hashes(workspace)
    return workspace, baseline


def _gold(workspace):
    write_gold_artifacts(workspace)


def _write_candidate(workspace, *, video=None, audio=None, duration=None, subtitles=None):
    video = [dict(row) for row in (video or spec.GOLD_SHOTS)]
    audio = [dict(spec.GOLD_AUDIO)] if audio is None else [dict(row) for row in audio]
    write_project(workspace / spec.FINAL_PROJECT_RELATIVE, assets=asset_definitions(workspace),
                  video=video, audio=audio, duration_frames=duration or spec.GOLD_DURATION_FRAMES,
                  subtitle_path="GreenLoop_Final.kdenlive.srt")
    from oscombo.collab.timeline_and_assets.fixture import dump_srt
    dump_srt(workspace / spec.FINAL_SUBTITLE_RELATIVE, subtitles or spec.GOLD_SUBTITLES)


def _set_entry(workspace, predicate, attr, value):
    path = workspace / spec.FINAL_PROJECT_RELATIVE
    tree = ET.parse(path)
    for node in tree.getroot().findall(".//entry"):
        if predicate(node):
            node.attrib[attr] = value
            break
    else:
        raise AssertionError("target entry not found")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def test_initial_fixture_is_fixed_partial_kdenlive_project(tmp_path):
    workspace, _ = _new_workspace(tmp_path)
    state = parse_project(workspace / spec.PROJECT_RELATIVE)
    assert state["fps"] == 25
    assert state["duration_frames"] == 100
    assert [r["asset_id"] for r in state["tracks"]["Video 1"]] == ["ASSET-01", "ASSET-03"]
    assert state["bin_assets"] == spec.GOLD_BIN_ASSETS
    assert len(list((workspace / "assets").glob("clip_*.mp4"))) == 4
    assert (workspace / "assets" / "music_bed.wav").is_file()
    assert (workspace / spec.PROJECT_RELATIVE).read_text(encoding="utf-8").startswith("<?xml")


def test_correct_project_and_manifest_pass_joint_oracle(tmp_path):
    workspace, baseline = _new_workspace(tmp_path)
    _gold(workspace)
    result = evaluate_artifacts(workspace, baseline_hashes=baseline)
    assert result["status"] == "PASS"
    assert result["actor_subscores"] == {"A_asset_curation": True, "B_timeline_edit": True}
    assert all(check["passed"] for check in result["checks"])


@pytest.mark.parametrize("mutation", ["wrong_order", "wrong_source_range", "wrong_track", "wrong_duration",
                                        "wrong_subtitle", "missing_audio", "missing_outtake", "outtake_in_timeline",
                                        "wrong_asset_resource", "wrong_profile", "modified_source"])
def test_negative_controls_fail_oracle(tmp_path, mutation):
    workspace, baseline = _new_workspace(tmp_path)
    _gold(workspace)
    project = workspace / spec.FINAL_PROJECT_RELATIVE
    if mutation == "wrong_order":
        state = parse_project(project)
        bad = [dict(x) for x in spec.GOLD_SHOTS]
        bad[0]["asset_id"], bad[1]["asset_id"] = bad[1]["asset_id"], bad[0]["asset_id"]
        _write_candidate(workspace, video=bad)
    elif mutation == "wrong_source_range":
        _set_entry(workspace, lambda n: n.attrib.get("producer") == "producer0", "in", frame_time(26))
    elif mutation == "wrong_track":
        tree = ET.parse(project)
        for prop in tree.getroot().findall(".//tractor/property"):
            if prop.attrib.get("name") == "kdenlive:track_name" and prop.text == "Video 1":
                prop.text = "Video 2"
                break
        tree.write(project, encoding="utf-8", xml_declaration=True)
    elif mutation == "wrong_duration":
        bad_video = [dict(row) for row in spec.GOLD_SHOTS]
        bad_video[-1]["source_out_frame"] = 73
        bad_audio = [dict(spec.GOLD_AUDIO)]
        bad_audio[0]["source_out_frame"] = 248
        _write_candidate(workspace, video=bad_video, audio=bad_audio, duration=249)
    elif mutation == "wrong_subtitle":
        from oscombo.collab.timeline_and_assets.fixture import dump_srt
        cues = [dict(x) for x in spec.GOLD_SUBTITLES]
        cues[1]["text"] = "Rinse. Recover. Reuse incorrectly."
        dump_srt(workspace / spec.FINAL_SUBTITLE_RELATIVE, tuple(cues))
    elif mutation == "missing_audio":
        _write_candidate(workspace, audio=[])
    elif mutation == "missing_outtake":
        tree = ET.parse(project)
        main_bin = tree.getroot().find("./playlist[@id='main_bin']")
        for entry in list(main_bin):
            producer = entry.attrib.get("producer", "")
            producer_el = tree.getroot().find(f"./producer[@id='{producer}']")
            if producer_el is not None and any(p.attrib.get("name") == "kdenlive:clipname" and p.text == "ASSET-04"
                                               for p in producer_el.findall("property")):
                main_bin.remove(entry)
                break
        tree.write(project, encoding="utf-8", xml_declaration=True)
    elif mutation == "outtake_in_timeline":
        # Point the final shot entry at the outtake producer, preserving timing.
        tree = ET.parse(project)
        playlist = tree.getroot().find("./playlist[@id='playlist_video1']")
        entries = playlist.findall("entry")
        source = next(p for p in tree.getroot().findall("producer")
                      if any(x.attrib.get("name") == "kdenlive:clipname" and x.text == "ASSET-04"
                             for x in p.findall("property")))
        entries[-1].set("producer", source.attrib["id"])
        tree.write(project, encoding="utf-8", xml_declaration=True)
    elif mutation == "wrong_asset_resource":
        tree = ET.parse(project)
        producer = tree.getroot().find("./producer[@id='producer0']")
        next(p for p in producer.findall("property") if p.attrib.get("name") == "resource").text = "../assets/clip_02.mp4"
        tree.write(project, encoding="utf-8", xml_declaration=True)
    elif mutation == "wrong_profile":
        tree = ET.parse(project)
        tree.getroot().find("profile").set("width", "640")
        tree.write(project, encoding="utf-8", xml_declaration=True)
    else:
        with (workspace / "assets" / "clip_01.mp4").open("ab") as stream:
            stream.write(b"tamper")
    result = evaluate_artifacts(workspace, baseline_hashes=baseline)
    assert result["status"] == "FAIL", result


def test_three_conditions_keep_backend_message_and_budget_semantics_equal():
    plans = {condition: make_plan(condition, "same-run") for condition in CONDITIONS}
    assert len({plan["workspace_backend_id"] for plan in plans.values()}) == 1
    assert len({plan["workspace_backend_topology"] for plan in plans.values()}) == 1
    assert len({plan["message_protocol"] for plan in plans.values()}) == 1
    assert len({plan["scoring"] for plan in plans.values()}) == 1
    assert plans["collaborative_isolated"]["budget"] == plans["collaborative_shared"]["budget"]
    assert [plans[c]["desktop_count"] for c in CONDITIONS] == [1, 2, 1]
    assert plans["single_agent"]["budget"]["single_agent_total_steps"] == 480
    assert plans["single_agent"]["budget"]["single_agent_total_tokens"] == 24000


def test_setup_protocol_actor_binding_event_log_and_reset(tmp_path):
    run_root = tmp_path / "run"
    created = prepare_run(run_root, "tla-test-001")
    assert Path(created["workspace"]).is_dir()
    configure_run(run_root, "collaborative_isolated")
    store_mod = __import__("oscombo.collab.data_to_deck.protocol", fromlist=["ProtocolStore"])
    store = store_mod.ProtocolStore(run_root / "collaboration", "tla-test-001")
    attachment = store.put_attachment("A", "shotlist.json", b'{"shots":3}')
    store.send("A", "B", "The wash take is in the attachment.", [attachment["attachment_id"]])
    assert store.messages("B")
    assert store.get_attachment("B", attachment["attachment_id"]) == b'{"shots":3}'
    binding, env = codex_collaboration_binding(run_root, "A", "http://127.0.0.1:9999")
    assert binding["collaboration"]["actor"] == "A" and env["CODESK_TLA_A_COLLAB_TOKEN"]

    event = {"schema_version": 1, "case_id": CASE_ID, "run_id": "tla-test-001", "seq": 1,
             "actor_id": "A", "event_type": "observation", "timestamp_monotonic_ns": 1,
             "window": {"sample_atomic": False},
             "kdenlive_state": {"active_monitor": "clip", "source_asset_id": "ASSET-01",
                                "source_playhead_frame": 25, "timeline_playhead_frame": 0,
                                "active_track": "Video 1", "selected_bin_asset_ids": ["ASSET-01"],
                                "selected_timeline_clip_ids": [], "evidence": "visible_ui"}}
    log_path = append_event(run_root, event)
    assert json.loads(log_path.read_text().splitlines()[0])["actor_id"] == "A"

    _gold(Path(created["workspace"]))
    reset = reset_owned_run(run_root, "tla-test-001")
    assert reset["status"] == "RESET_VERIFIED"
    assert Path(reset["archive"], "workspace", "deliverables", "GreenLoop_Final.kdenlive").is_file() is True
    assert Path(reset["archive"], "interaction_events.jsonl").is_file()
    assert (run_root / "interaction_events.jsonl").read_text() == ""
    assert list((run_root / "pre_reset").iterdir())


def test_event_writer_rejects_wrong_owner(tmp_path):
    run_root = tmp_path / "run"
    prepare_run(run_root, "tla-test-002")
    event = {"schema_version": 1, "case_id": CASE_ID, "run_id": "different-run", "seq": 1,
             "actor_id": "B", "event_type": "action_start", "timestamp_monotonic_ns": 7}
    with pytest.raises(PermissionError):
        append_event(run_root, event)


def test_runner_evaluate_writes_scoped_provenance_without_gui_claim(tmp_path):
    run_root = tmp_path / "run"
    prepare_run(run_root, "tla-eval-001")
    configure_run(run_root, "single_agent")
    _gold(run_root / "workspace")
    result = evaluate_run(run_root)
    assert result["status"] == "PASS"
    provenance = json.loads((run_root / "provenance.json").read_text())
    assert provenance["case_id"] == CASE_ID
    assert provenance["gui_action_trace"] == "NOT_PRESENT_OFFLINE"
    assert provenance["kdenlive_open_save_roundtrip"] == "PENDING_GUEST_SMOKE"
