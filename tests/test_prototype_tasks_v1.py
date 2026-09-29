from __future__ import annotations

import base64
import json

from swcub.instances import TaskInstanceSpec
from swcub.actors import ScriptedBrowserTabActor
from swcub.task_factory import (CONTEXT_TEMPLATE_ID, MODAL_TEMPLATE_ID,
                                TEMPLATE_REGISTRY, verify_initial_files,
                                verify_instance_directory, verify_manifest,
                                write_instance)
from swcub.tasks.prototypes_v1 import (ModalSaveExactEvaluator,
                                       browser_context_server_source,
                                       evaluate_browser_context,
                                       generate_browser_context_instance,
                                       generate_modal_instance)


def test_modal_and_context_instances_use_the_common_factory_contract():
    for factory, template_id in ((generate_modal_instance, MODAL_TEMPLATE_ID),
                                  (generate_browser_context_instance, CONTEXT_TEMPLATE_ID)):
        first, replay = factory(9), factory(9)
        assert first == replay
        assert first["template_id"] == template_id
        assert verify_manifest(first)
        assert verify_initial_files(first)["success"]
        assert TaskInstanceSpec.from_dict(first).task_id == first["task_id"]
        decoded = {item["guest_path"]: base64.b64decode(item["content_base64"], validate=True)
                   for item in first["initial_files"]}
        assert all(decoded[item["guest_path"]] for item in first["initial_files"])
        assert factory(10)["content_fingerprint"] != first["content_fingerprint"]
        assert TEMPLATE_REGISTRY[template_id].generate(9) == first


def test_prototype_factory_artifacts_round_trip_through_immutable_instance_writer(tmp_path):
    for factory in (generate_modal_instance, generate_browser_context_instance):
        manifest = factory(12)
        base = tmp_path / manifest["family_id"]
        base.mkdir()
        destination = write_instance(manifest, base)
        verified = verify_instance_directory(destination)
        assert verified["success"]


def test_modal_evaluator_separates_file_success_from_dialog_owner_evidence():
    manifest = generate_modal_instance(2)
    evaluator = ModalSaveExactEvaluator(manifest["expected_state"])
    actual = manifest["expected_state"]
    correct_events = [
        {"kind": "dialog_confirmed", "actor_id": "writer_actor",
         "dialog_owner": "writer_actor", "target_path": actual["writer"]["saved_path"]},
        {"kind": "dialog_confirmed", "actor_id": "calc_actor",
         "dialog_owner": "calc_actor", "target_path": actual["calc"]["saved_path"]},
    ]
    good = evaluator.evaluate(actual, correct_events)
    assert good["joint_success"]
    assert good["dialog_attribution_complete"]
    bad = evaluator.evaluate(actual, [
        {"kind": "dialog_confirmed", "actor_id": "writer_actor",
         "dialog_owner": "calc_actor", "target_path": actual["writer"]["saved_path"]}])
    assert bad["joint_success"]  # final artifacts pass; interaction evidence does not
    assert bad["dialog_owner_evidence"]["writer_actor"] == "mismatch"
    assert bad["dialog_owner_evidence"]["calc_actor"] == "unknown"
    assert bad["cross_owner_confirmation_count"] == 1


def test_browser_context_requires_same_window_and_observed_tab_transition_evidence():
    manifest = generate_browser_context_instance(4)
    actual = {"tabs": {"tab-a": {"goal": manifest["actor_goals"]["actor_a"]["expected"]},
                       "tab-b": {"goal": manifest["actor_goals"]["actor_b"]["expected"]}}}
    events = [
        {"kind": "tab_activated", "window_id": "0x101", "before_tab": "tab-a",
         "after_tab": "tab-b"},
        {"kind": "tab_activated", "window_id": "0x101", "before_tab": "tab-b",
         "after_tab": "tab-a"},
    ]
    result = evaluate_browser_context(actual, events, manifest["expected_state"])
    assert result["joint_success"]
    assert result["same_top_level_window"]
    assert result["application_context_evidence"] == "supported"
    assert result["tab_change_count"] == 2

    missing = evaluate_browser_context(actual, [], manifest["expected_state"])
    assert missing["joint_success"]
    assert missing["application_context_evidence"] == "unknown"


def test_browser_fixture_source_is_valid_python_and_encodes_two_actor_routes():
    source = browser_context_server_source("A-1", "B-1").decode()
    compile(source, "guest-browser-context-fixture.py", "exec")
    assert "actor-a" in source and "actor-b" in source
    assert "visibilitychange" in source
    assert "goal_committed" in source
    assert "127.0.0.1" in source and "8766" in source


def test_browser_context_scripted_actor_yields_then_reacquires_own_tab():
    class Context:
        def __init__(self):
            self.actions = []

        def press_key(self, key):
            self.actions.append(("key", key))

        def observe(self):
            self.actions.append(("observe",))
            return {"screenshot": b"unit-fixture"}

        def click(self, x, y):
            self.actions.append(("click", x, y))

        def type_text(self, value):
            self.actions.append(("type", value))

    a, b = ScriptedBrowserTabActor("actor_a", "A-1"), ScriptedBrowserTabActor("actor_b", "B-1")
    ca, cb = Context(), Context()
    assert a.run_step(ca) is False
    assert b.run_step(cb) is True
    assert a.run_step(ca) is True
    assert [x for x in ca.actions if x[:2] == ("key", "ctrl+1")] == [
        ("key", "ctrl+1"), ("key", "ctrl+1")]
    assert ("type", "A-1") in ca.actions
    assert ("click", 170, 255) in ca.actions
    assert ("key", "ctrl+2") in cb.actions
