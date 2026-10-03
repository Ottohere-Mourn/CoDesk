from __future__ import annotations

import base64
import json

from swcub.instances import TaskInstanceSpec
from swcub.task_factory import (GeneratedOfficeExactEvaluator, RunConfig,
                                generate_clipboard_instance, generate_office_instance,
                                initialize_instance,
                                render_calc_fods, render_writer_fodt,
                                validate_office_candidate, verify_initial_files,
                                verify_instance_directory, verify_manifest, write_instance)
from swcub.tasks.clipboard_v1 import (ClipboardTaskEvaluator, CALC_PATH as CLIP_CALC_PATH,
                                      WRITER_PATH as CLIP_WRITER_PATH,
                                      calc_seed_odf, writer_seed_odf)


def files_for(manifest):
    return {item["guest_path"]: base64.b64decode(item["content_base64"])
            for item in manifest["initial_files"]}


def parsed_state(manifest, files):
    from swcub.evaluator import GuestLibreOfficeBindingEvaluator as Parser
    initial = manifest["initial_state"]
    return {"writer_text": Parser._parse_writer(
                files[initial["writer_document"]["path"]].decode()),
            "calc_cells": Parser._parse_calc(
                files[initial["calc_sheet"]["path"]].decode())}


def test_office_factory_reproducible_hashes_and_task_instance_schema():
    left, right = generate_office_instance(101), generate_office_instance(101)
    assert left == right
    assert verify_manifest(left) is True
    assert verify_initial_files(left)["success"] is True
    assert TaskInstanceSpec.from_dict(left).task_id == left["task_id"]
    changed = json.loads(json.dumps(left))
    changed["actor_goals"]["calc_actor"]["expected"] = "Other"
    assert verify_manifest(changed) is False


def test_office_factory_emits_distinct_semantic_candidates_not_layout_variants():
    manifests = [generate_office_instance(seed) for seed in (11, 22, 33, 44, 55, 66, 77, 88)]
    assert len({item["task_id"] for item in manifests}) == 8
    assert len({item["content_fingerprint"] for item in manifests}) == 8
    assert len({item["actor_goals"]["writer_actor"]["expected"] for item in manifests}) == 8
    assert all("window_geometry" not in item and "repeat" not in item for item in manifests)
    assert all(validate_office_candidate(item)["success"] for item in manifests)


def test_generated_office_seed_files_match_initial_state_and_joint_oracle():
    manifest = generate_office_instance(31)
    files = files_for(manifest)
    initial = parsed_state(manifest, files)
    assert initial["writer_text"] == manifest["initial_state"]["writer_document"]["text"]
    assert initial["calc_cells"] == manifest["initial_state"]["calc_sheet"]["cells"]
    evaluator = GeneratedOfficeExactEvaluator(
        manifest, lambda path: files[path].decode(),
        required_actors=("writer_actor", "calc_actor"))
    assert evaluator.evaluate()["success"] is False  # initial fixture is not pre-solved

    expected = manifest["expected_state"]
    files[manifest["initial_state"]["writer_document"]["path"]] = render_writer_fodt(
        [expected["writer_text"]])
    files[manifest["initial_state"]["calc_sheet"]["path"]] = render_calc_fods(
        expected["calc_cells"])
    result = evaluator.evaluate()
    assert result["success"] is True
    assert result["actor_goal_success"] == {"writer_actor": True, "calc_actor": True}


def test_office_solo_oracles_check_assigned_goal_and_non_target_integrity():
    manifest = generate_office_instance(40)
    files = files_for(manifest)
    expected = manifest["expected_state"]
    writer_path = manifest["initial_state"]["writer_document"]["path"]
    calc_path = manifest["initial_state"]["calc_sheet"]["path"]
    files[writer_path] = render_writer_fodt([expected["writer_text"]])
    writer_result = GeneratedOfficeExactEvaluator(
        manifest, lambda path: files[path].decode(), ("writer_actor",)).evaluate()
    assert writer_result["success"] is True
    assert writer_result["final_state"]["calc_cells"] == manifest["initial_state"][
        "calc_sheet"]["cells"]

    files[writer_path] = render_writer_fodt(
        [manifest["initial_state"]["writer_document"]["text"]])
    files[calc_path] = render_calc_fods(expected["calc_cells"])
    calc_result = GeneratedOfficeExactEvaluator(
        manifest, lambda path: files[path].decode(), ("calc_actor",)).evaluate()
    assert calc_result["success"] is True

    files[writer_path] = render_writer_fodt(["unauthorized edit"])
    contaminated = GeneratedOfficeExactEvaluator(
        manifest, lambda path: files[path].decode(), ("calc_actor",)).evaluate()
    assert contaminated["success"] is False
    assert contaminated["non_target_mutations"][0]["resource"] == "writer_document"

    files[writer_path] = render_writer_fodt(
        [manifest["initial_state"]["writer_document"]["text"]])
    wrong_goal = dict(files)
    wrong_cells = [list(row) for row in expected["calc_cells"]]
    wrong_cells[1][1] = "Rejected"
    wrong_goal[calc_path] = render_calc_fods(wrong_cells)
    failed_goal = GeneratedOfficeExactEvaluator(
        manifest, lambda path: wrong_goal[path].decode(),
        ("calc_actor",)).evaluate()
    assert failed_goal["success"] is False
    assert failed_goal["non_target_mutations"] == []
    assert failed_goal["goal_state_errors"][0]["cell"] == "B2"


def test_writer_calc_generator_supports_250_reproducible_unique_seeds():
    manifests = [generate_office_instance(seed) for seed in range(250)]
    assert len({item["task_id"] for item in manifests}) == 250
    assert len({item["content_fingerprint"] for item in manifests}) == 250
    assert all(verify_manifest(item) for item in manifests[:3])


def test_run_config_geometry_and_repeats_do_not_mutate_task_identity():
    manifest = generate_office_instance(12)
    left = RunConfig(manifest["instance_id"], "ma_sd", 1,
                     {"writer_actor": (0, 0, 900, 700)}).to_dict()
    right = RunConfig(manifest["instance_id"], "ma_sd", 2,
                      {"writer_actor": (10, 20, 800, 600)}).to_dict()
    assert left["run_id"] != right["run_id"]
    assert manifest["task_id"] == generate_office_instance(12)["task_id"]
    assert manifest["content_fingerprint"] == generate_office_instance(12)["content_fingerprint"]
    solo_writer = RunConfig(manifest["instance_id"], "solo", 1,
                            solo_actor_id="writer_actor").to_dict()
    solo_calc = RunConfig(manifest["instance_id"], "solo", 1,
                          solo_actor_id="calc_actor").to_dict()
    assert solo_writer["run_id"] != solo_calc["run_id"]


def test_write_verify_cycle_preserves_instance_files_without_overwrite(tmp_path):
    manifest = generate_office_instance(9)
    target = write_instance(manifest, tmp_path)
    stored = json.loads((target / "manifest.json").read_text())
    assert verify_manifest(stored) is True
    assert (target / "initial/document.fodt").is_file()
    assert verify_instance_directory(target)["success"] is True
    artifact = target / "initial/document.fodt"
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    assert verify_instance_directory(target)["success"] is False


def test_common_initializer_resets_then_seeds_exact_manifest_files():
    manifest = generate_office_instance(17)
    events = []
    guest_files = {}
    environment = initialize_instance(
        manifest,
        lambda instance_id, seed: events.append(("reset", instance_id, seed)) or {},
        lambda env, path, data: (events.append(("write", path, data)),
                                guest_files.__setitem__(path, data)),
        lambda env, path: guest_files[path])
    assert environment == {}
    assert events[0] == ("reset", manifest["instance_id"], manifest["seed"])
    assert len([event for event in events if event[0] == "write"]) == 2


def test_clipboard_template_uses_common_manifest_contract_but_stays_unvalidated():
    manifest = generate_clipboard_instance(5)
    assert verify_manifest(manifest) is True
    assert TaskInstanceSpec.from_dict(manifest).task_id == manifest["task_id"]
    assert verify_initial_files(manifest)["success"] is True
    assert manifest["validation_status"].startswith("design_only")
    assert {"environment", "actors", "actor_goals", "initial_state", "expected_state",
            "initial_files", "evaluator", "schedule", "joint_feasibility"} <= set(manifest)
    values = files_for(manifest)
    writer_token = manifest["actor_goals"]["writer_actor"]["source"]
    calc_token = manifest["actor_goals"]["calc_actor"]["source"]
    values[CLIP_WRITER_PATH] = writer_seed_odf(writer_token).decode()
    values[CLIP_CALC_PATH] = calc_seed_odf(calc_token).decode()
    result = ClipboardTaskEvaluator(lambda path: values[path], writer_source=writer_token,
                                    calc_source=calc_token,
                                    task_id=manifest["task_id"],
                                    task_version=manifest["template_version"]).evaluate()
    assert result["success"] is False
    assert result["initial_state"]["writer_text"] == (
        f"{writer_token}\nINSERT COPIED VALUE")
    values[CLIP_WRITER_PATH] = writer_seed_odf(writer_token).decode().replace(
        "<text:p>INSERT COPIED VALUE</text:p>",
        f"<text:p>{writer_token}</text:p>")
    values[CLIP_CALC_PATH] = calc_seed_odf(calc_token).decode().replace(
        "<table:table-cell/></table:table-row>",
        f"<table:table-cell office:value-type=\"string\"><text:p>{calc_token}</text:p>"
        "</table:table-cell></table:table-row>")
    final = ClipboardTaskEvaluator(lambda path: values[path], writer_source=writer_token,
                                   calc_source=calc_token, task_id=manifest["task_id"],
                                   task_version=manifest["template_version"]).evaluate()
    assert final["success"] is True
