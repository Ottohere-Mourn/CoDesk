from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from oscombo.collab.data_to_deck.protocol import ProtocolStore
from oscombo.collab.model_and_review import CASE_ID, CONDITIONS
from oscombo.collab.model_and_review import interaction_log, spec
from oscombo.collab.model_and_review.integration import codex_collaboration_binding
from oscombo.collab.model_and_review.oracle import evaluate_blend_file, evaluate_snapshot
from oscombo.collab.model_and_review.blend_format import has_blend_container_header
from oscombo.collab.model_and_review.runner import make_plan, prepare_run, reset_owned_run
from oscombo.collab.model_and_review.revision_store import RevisionStore

PACKAGE = Path(__file__).resolve().parents[1] / "oscombo" / "collab" / "model_and_review"


def _gold_snapshot():
    return json.loads((PACKAGE / "fixtures" / "gold_state.json").read_text(encoding="utf-8"))


def _object(snapshot, name):
    return next(row for row in snapshot["objects"] if row["name"] == name)


def test_gold_normalized_scene_passes_exact_oracle():
    result = evaluate_snapshot(_gold_snapshot())
    assert result["status"] == "PASS", result
    assert result["actor_subscores"] == {"A_geometry": True, "B_review_presentation": True}
    assert result["measured"]["bulb_radial_clearance_m"] == pytest.approx(0.48375)
    assert result["measured"]["bulb_vertical_clearance_m"] == pytest.approx(0.13)


def test_baseline_geometry_fingerprint_catches_protected_object_mesh_changes():
    snapshot = _gold_snapshot()
    for row in snapshot["objects"]:
        if row["name"] in spec.PROTECTED_OBJECTS:
            row["geometry_sha256"] = "baseline-" + row["name"]
    baseline = {name: {
        "type": row["type"], "location": row["location"], "dimensions": row["dimensions"],
        "rotation_euler": row.get("rotation_euler"), "scale": row.get("scale"),
        "materials": row["materials"], "geometry_sha256": row["geometry_sha256"],
    } for row in snapshot["objects"] for name in [row["name"]] if name in spec.PROTECTED_OBJECTS}
    assert evaluate_snapshot(snapshot, baseline_protected=baseline)["status"] == "PASS"
    _object(snapshot, "Lamp_Stem")["geometry_sha256"] = "tampered-mesh"
    result = evaluate_snapshot(snapshot, baseline_protected=baseline)
    assert result["status"] == "FAIL"
    stem = next(check for check in result["checks"] if check["name"] == "object:Lamp_Stem")
    assert not stem["passed"]


@pytest.mark.parametrize("mutation", [
    "shade_size", "shade_position", "shade_profile", "bulb_clearance", "camera_lens",
    "camera_aim", "key_power", "fill_size", "rim_color", "protected_stem", "material",
    "missing_object", "extra_object",
])
def test_negative_controls_fail_oracle(mutation):
    snapshot = _gold_snapshot()
    if mutation == "shade_size":
        _object(snapshot, "Lamp_Shade")["dimensions"][0] = 1.4
    elif mutation == "shade_position":
        _object(snapshot, "Lamp_Shade")["location"][2] = 2.4
    elif mutation == "shade_profile":
        snapshot["shade_profile"]["inner_radius_bottom_m"] = 0.8
    elif mutation == "bulb_clearance":
        _object(snapshot, "Lamp_Bulb")["dimensions"] = [0.8, 0.8, 0.8]
    elif mutation == "camera_lens":
        _object(snapshot, "Camera_Main")["lens_mm"] = 45.0
    elif mutation == "camera_aim":
        snapshot["camera_target_alignment_dot"] = 0.95
    elif mutation == "key_power":
        _object(snapshot, "Key_Light")["power_w"] = 451.0
    elif mutation == "fill_size":
        _object(snapshot, "Fill_Light")["size_m"] = 2.0
    elif mutation == "rim_color":
        _object(snapshot, "Rim_Light")["color"] = [1.0, 1.0, 1.0]
    elif mutation == "protected_stem":
        _object(snapshot, "Lamp_Stem")["location"][2] += 0.01
    elif mutation == "material":
        snapshot["material_colors"]["Mat_Deep_Green"][0] = 0.5
    elif mutation == "missing_object":
        snapshot["objects"] = [row for row in snapshot["objects"] if row["name"] != "Lamp_Base"]
    else:
        snapshot["objects"].append({"name": "Unrequested_Object", "type": "MESH"})
    assert evaluate_snapshot(snapshot)["status"] == "FAIL", mutation


def test_all_three_conditions_hold_backend_and_budget_constant():
    plans = {condition: make_plan(condition, "mar-contract") for condition in CONDITIONS}
    assert len({p["workspace_backend_id"] for p in plans.values()}) == 1
    assert len({p["workspace_backend_topology"] for p in plans.values()}) == 1
    assert len({p["save_policy"] for p in plans.values()}) == 1
    assert len({p["message_protocol"] for p in plans.values()}) == 1
    assert len({p["scoring"] for p in plans.values()}) == 1
    assert plans["collaborative_isolated"]["budget"] == plans["collaborative_shared"]["budget"]
    assert [plans[c]["desktop_count"] for c in CONDITIONS] == [1, 2, 1]
    assert plans["single_agent"]["budget"]["single_agent_total_steps"] == 360
    assert plans["single_agent"]["budget"]["single_agent_total_tokens"] == 24000
    assert plans["collaborative_isolated"]["project_path"] == plans["collaborative_shared"]["project_path"]


def test_plan_rejects_unknown_condition_and_nonpositive_budget():
    with pytest.raises(ValueError):
        make_plan("two_unrelated_guests", "bad")
    with pytest.raises(ValueError):
        make_plan("single_agent", "bad", steps_per_actor=0)


def test_message_and_attachment_use_existing_protocol(tmp_path):
    run_root = tmp_path / "owned-run"
    run_root.mkdir()
    (run_root / "ownership.json").write_text(json.dumps({
        "case_id": CASE_ID, "run_id": "mar-protocol", "run_root": str(run_root.resolve())
    }), encoding="utf-8")
    tokens = {"A": "a-token", "B": "b-token", "S": "s-token"}
    (run_root / "secrets").mkdir()
    (run_root / "secrets" / "collaboration_tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
    store = ProtocolStore(run_root / "collaboration", "mar-protocol")
    item = store.put_attachment("A", "clearance-review.txt", b"Bulb radial clearance verified.")
    store.send("A", "B", "Please review the measured shade clearance.", [item["attachment_id"]])
    assert store.messages("B")[0]["actor"] == "A"
    assert store.get_attachment("B", item["attachment_id"]) == b"Bulb radial clearance verified."
    binding, env = codex_collaboration_binding(run_root, "B", "http://127.0.0.1:8800")
    assert binding["collaboration"]["actor"] == "B"
    assert env == {"CODESK_MAR_B_COLLAB_TOKEN": "b-token"}


def test_action_boundary_log_captures_app_state_and_marks_sampling_limit(tmp_path):
    run_root = tmp_path / "owned-run"
    run_root.mkdir()
    (run_root / "ownership.json").write_text(json.dumps({
        "case_id": CASE_ID, "run_id": "mar-log", "run_root": str(run_root.resolve())
    }), encoding="utf-8")
    before = {"sampled_monotonic_ns": 100, "active_object": "Lamp_Shade",
              "selected_objects": ["Lamp_Shade"], "mode": "EDIT_MESH",
              "active_workspace": "Layout", "active_screen": "Layout", "active_area_type": "VIEW_3D",
              "scene_camera": "Camera_Main", "viewports": [{"view_perspective": "PERSP"}]}
    after = {**before, "sampled_monotonic_ns": 200, "active_object": "Camera_Main",
             "selected_objects": ["Camera_Main"], "mode": "OBJECT"}
    interaction_log.append_action_boundary(run_root, run_id="mar-log", actor_id="B",
                                           action_id="action-7", action_label="select camera",
                                           before=before, after=after)
    rows = [json.loads(line) for line in (run_root / "interaction_events.jsonl").read_text().splitlines()]
    assert [row["event_type"] for row in rows] == ["action_start", "action_end"]
    assert rows[0]["blender_state"]["mode"] == "EDIT_MESH"
    assert rows[1]["blender_state"]["active_object"] == "Camera_Main"
    assert rows[0]["atomic_with_input"] is False
    assert "not an atomic key-event trace" in rows[1]["causality_limit"]


def test_prepare_and_reset_fail_closed_without_a_real_blend(tmp_path):
    absent_fixture = tmp_path / "missing-blender-fixture.blend"
    run_root = tmp_path / "must-not-be-created"
    with pytest.raises(FileNotFoundError, match="real Blender fixture is unavailable"):
        prepare_run(run_root, "mar-no-fixture", fixture_path=absent_fixture)
    assert not run_root.exists()
    with pytest.raises(FileNotFoundError):
        evaluate_blend_file(tmp_path / "missing-scene")
    with pytest.raises(FileNotFoundError):
        reset_owned_run(tmp_path / "unrelated-path", "mar-unknown", fixture_path=absent_fixture)
    assert CASE_ID == "CDD-MAR-001"


def test_blender_generator_is_real_bpy_writer():
    builder_path = PACKAGE / "blender" / "build_fixture.py"
    source = builder_path.read_text(encoding="utf-8")
    compile(source, str(builder_path), "exec")
    assert "import bpy" in source
    assert "bpy.ops.wm.save_as_mainfile" in source
    assert "has_blend_container_header_at" in source
    snapshot_path = PACKAGE / "blender" / "snapshot_scene.py"
    compile(snapshot_path.read_text(encoding="utf-8"), str(snapshot_path), "exec")


def test_case_schemas_and_gold_manifest_are_parseable_json():
    for path in (PACKAGE / "fixtures" / "gold_state.json",
                 PACKAGE / "fixtures" / "blender_fixture_manifest.json",
                 PACKAGE / "fixtures" / "scene_snapshot.schema.json",
                 PACKAGE / "fixtures" / "run_config.schema.json",
                 PACKAGE / "interaction_event.schema.json"):
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)


def test_versioned_artifact_store_serializes_writers_and_preserves_revisions(tmp_path):
    # Generic payload mode tests only the revision/lease protocol. It never
    # represents or carries a file labelled as a Blender project.
    initial = tmp_path / "initial.payload"
    initial.write_bytes(b"revision-zero")
    store = RevisionStore.initialize(tmp_path / "store", "mar-store", initial,
                                     artifact_kind="generic_test_payload")
    a = store.acquire("A", "desktop-A")
    a_path = Path(a["checkout_path"])
    assert a_path.suffix == ".payload" and a_path.read_bytes() == b"revision-zero"
    with pytest.raises(RuntimeError, match="another actor holds"):
        store.acquire("B", "desktop-B")
    a_path.write_bytes(b"revision-one")
    committed = store.commit(a["token"], a_path)
    assert committed["revision"] == 1
    assert Path(committed["path"]).read_bytes() == b"revision-one"
    assert (tmp_path / "store" / "revisions" / "revision-000000.blob").read_bytes() == b"revision-zero"
    b = store.acquire("B", "desktop-B")
    assert b["revision"] == 1 and Path(b["checkout_path"]).read_bytes() == b"revision-one"
    store.abandon(b["token"])
    events = [json.loads(line) for line in (tmp_path / "store" / "events.jsonl").read_text().splitlines()]
    assert [(row["event"], row["actor_id"]) for row in events] == [
        ("lease_acquired", "A"), ("commit", "A"), ("lease_acquired", "B"), ("abandon", "B")]


def test_revision_store_rejects_non_blender_bytes_as_blend(tmp_path):
    payload = tmp_path / "ordinary-input"
    payload.write_bytes(b"not a Blender project")
    with pytest.raises(ValueError, match="genuine Blender"):
        RevisionStore.initialize(tmp_path / "bad-store", "mar-bad-store", payload,
                                 artifact_kind="blender_project")
    assert not (tmp_path / "bad-store").exists()


def test_blend_container_signature_accepts_plain_and_zstd_compressed_files():
    assert has_blend_container_header(b"BLENDER-v400")
    assert has_blend_container_header(b"\x28\xb5\x2f\xfdcompressed-blend")
    assert not has_blend_container_header(b"not a Blender project")


@pytest.mark.skipif(not os.environ.get("CODESK_BLENDER_BIN"),
                    reason="set CODESK_BLENDER_BIN to run genuine .blend fixture tests")
def test_real_blend_initial_fails_and_gold_passes_with_protected_baseline():
    from oscombo.collab.model_and_review.oracle import extract_blend_snapshot, _protected_fingerprint

    blender = os.environ["CODESK_BLENDER_BIN"]
    initial = PACKAGE / "fixtures" / "initial.blend"
    gold = PACKAGE / "fixtures" / "private" / "gold.blend"
    initial_snapshot = extract_blend_snapshot(initial, blender)
    protected = {
        name: _protected_fingerprint(next(row for row in initial_snapshot["objects"]
                                          if row["name"] == name))
        for name in spec.PROTECTED_OBJECTS
    }
    assert evaluate_blend_file(initial, blender, baseline_protected=protected)["status"] == "FAIL"
    assert evaluate_blend_file(gold, blender, baseline_protected=protected)["status"] == "PASS"
