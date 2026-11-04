"""Offline oracle and GUI action contract checks; these are not Guest episodes."""
from __future__ import annotations

from swcub.task_factory import render_calc_fods, render_writer_fodt
from swcub.tasks.workflows_v1 import C03, F01, F04
from swcub.tasks.workflow_actors_v1 import FocusBlockCalcActor, RectangleCalcActor, WorkflowWriterActor


class ActionRecorder:
    def __init__(self):
        self.actions = []

    def observe(self):
        self.actions.append(("observe",))
        return {"screenshot": b"offline-action-contract"}

    def press_key(self, key):
        self.actions.append(("key", key))

    def type_text(self, value):
        self.actions.append(("type", value))


def files_for(workflow, active=()):
    state = workflow.state_for(active)
    return {workflow.writer_path: render_writer_fodt(state["writer_text"].split("\n")).decode(),
            workflow.calc_path: render_calc_fods(state["calc_cells"]).decode()}


def test_fixed_manifest_and_initial_odf_are_reproducible():
    for workflow in (F01, F04, C03):
        first, second = workflow.files(), workflow.files()
        assert first == second and first is not second
        assert len(workflow.fixture_digest()) == 64
        assert workflow.parse(lambda path: workflow.files()[path].decode()) == workflow.state_for(())
        assert workflow.evaluate(files_for(workflow).__getitem__, ("actor_a", "actor_b"))["success"] is False


def test_solo_a_solo_b_joint_and_nontarget_integrity():
    for workflow in (F01, F04, C03):
        for active in (("actor_a",), ("actor_b",), ("actor_a", "actor_b")):
            result = workflow.evaluate(files_for(workflow, active).__getitem__, active)
            assert result["success"]
            assert result["non_target_integrity"]
            assert all(result["actor_goal_success"].values())
        altered = files_for(workflow, ("actor_a",))
        altered[workflow.writer_path] = render_writer_fodt(["UNAUTHORIZED"]).decode()
        result = workflow.evaluate(altered.__getitem__, ("actor_a",))
        assert not result["success"]
        assert "writer_text" in result["non_target_mutations"]


def test_f01_reversed_actor_application_mapping_and_exact_oracle():
    assert F01.manifest()["actor_applications"] == {"actor_a": "Writer", "actor_b": "Calc"}
    assert F01.state_for(("actor_a",))["writer_text"] == F01.writer_final
    assert F01.state_for(("actor_a",))["calc_cells"] == [list(row) for row in F01.calc_initial]
    assert F01.state_for(("actor_b",))["calc_cells"] == [list(row) for row in F01.calc_final]
    assert F01.state_for(("actor_b",))["writer_text"] == F01.writer_initial
    for active in (("actor_a",), ("actor_b",), ("actor_a", "actor_b")):
        result = F01.evaluate(files_for(F01, active).__getitem__, active)
        assert result["success"] and all(result["actor_goal_success"].values())


def test_f04_oracle_rejects_neighbor_change_and_incomplete_block():
    state = F04.state_for(("actor_a", "actor_b"))
    state["calc_cells"][3][1] = "99"
    files = files_for(F04, ("actor_a", "actor_b"))
    files[F04.calc_path] = render_calc_fods(state["calc_cells"]).decode()
    result = F04.evaluate(files.__getitem__, ("actor_a", "actor_b"))
    assert not result["success"]
    assert "calc_cells" in result["non_target_mutations"]
    state["calc_cells"][3][1] = "Safe"
    state["calc_cells"][2][2] = ""
    files[F04.calc_path] = render_calc_fods(state["calc_cells"]).decode()
    assert not F04.evaluate(files.__getitem__, ("actor_a", "actor_b"))["success"]


def test_c03_oracle_rejects_flattened_or_shifted_rectangle():
    state = C03.state_for(("actor_a", "actor_b"))
    state["calc_cells"][3][0] = "Q1 Q2 17 29"
    state["calc_cells"][3][1] = ""
    files = files_for(C03, ("actor_a", "actor_b"))
    files[C03.calc_path] = render_calc_fods(state["calc_cells"]).decode()
    result = C03.evaluate(files.__getitem__, ("actor_a", "actor_b"))
    assert not result["success"]
    assert "calc_cells" in result["non_target_mutations"]


def test_scripted_actions_use_gui_copy_paste_and_recovery_options():
    copy = ActionRecorder()
    actor = RectangleCalcActor(shared_desktop=True, recopy_on_resume=False)
    assert actor.run_step(copy) is False
    assert actor.run_step(copy) is True
    assert copy.actions.count(("key", "ctrl+c")) == 1
    assert copy.actions.count(("key", "ctrl+v")) == 1
    assert ("key", "alt+tab") in copy.actions
    recopy = ActionRecorder()
    recovering = RectangleCalcActor(shared_desktop=True, recopy_on_resume=True)
    recovering.run(recopy)
    assert recopy.actions.count(("key", "ctrl+c")) == 2
    writer = ActionRecorder()
    WorkflowWriterActor(template="C-03", shared_desktop=True).run(writer)
    assert ("key", "ctrl+c") in writer.actions and ("key", "ctrl+v") in writer.actions
    focus = ActionRecorder()
    FocusBlockCalcActor(shared_desktop=True, recover_focus=True).run(focus)
    assert [action[1] for action in focus.actions if action[0] == "type"] == ["11", "21", "12", "22"]
    assert ("key", "alt+tab") in focus.actions


def test_c03_paste_destination_cells_are_truly_empty_xml():
    from xml.etree import ElementTree as ET
    root = ET.fromstring(C03.files()[C03.calc_path])
    ns = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    rows = list(root.iter(ns + "table-row"))
    for row, col in ((3, 0), (3, 1), (4, 0), (4, 1)):
        cell = list(rows[row].findall(ns + "table-cell"))[col]
        assert not cell.attrib and not list(cell)


def test_osworld_actor_defers_predicted_actions_without_replanning():
    from io import BytesIO
    from PIL import Image
    from swcub.osworld_agent_actor import OSWorldAgentActor

    image_buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(image_buffer, format="PNG")
    screenshot = image_buffer.getvalue()

    class Agent:
        def __init__(self):
            self.predict_calls = 0

        def reset(self):
            pass

        def predict(self, instruction, observation):
            self.predict_calls += 1
            return "planned", [
                "pyautogui.typewrite('Approved by GUI actor')",
                "pyautogui.hotkey('ctrl', 's')",
            ]

    class Context:
        _observed_revision = 7

        def __init__(self):
            self.actions = []

        def observe(self):
            return {"screenshot": screenshot}

        def execute_gui_action(self, action):
            self.actions.append(action)

    agent = Agent()
    context = Context()
    actor = OSWorldAgentActor(
        agent, "type the selected text", actor_id="actor_a",
        decision_boundary_callback=lambda actor_obj, actions: actor_obj.pause(),
    )

    assert actor.run_step(context) is False
    assert actor.paused and actor.steps == 1
    assert context.actions == []
    assert agent.predict_calls == 1

    actor.resume()
    assert actor.run_step(context) is False
    assert context.actions == [
        "pyautogui.typewrite('Approved by GUI actor')",
        "pyautogui.hotkey('ctrl', 's')",
    ]
    assert agent.predict_calls == 1


def test_focus_metrics_detect_typewrite_and_double_quoted_paste_routing():
    from types import SimpleNamespace
    from scripts.run_workflows_v1 import _event_metrics

    events = [
        SimpleNamespace(kind="gui", actor="actor_a", seq=1, details={
            "action": 'pyautogui.typewrite("Approved by GUI actor")',
            "active_window_before": "Calc - Shared.ods",
            "active_window_after": "Calc - Shared.ods",
        }),
        SimpleNamespace(kind="gui", actor="actor_a", seq=2, details={
            "action": 'pyautogui.hotkey("ctrl", "v")',
            "active_window_before": "Calc - Shared.ods",
            "active_window_after": "Calc - Shared.ods",
        }),
    ]
    result = _event_metrics(events, F01)
    assert result["known_wrong_app_content_action_count"] == 2
    assert [row["wrong_app"] for row in result["keyboard_routes"]] == [True, True]
    assert result["observed_interference"] == "wrong_app_content_action_observed"


def _clipboard_event(seq, source_actor, phase, action, digest=None,
                     changed=False, copy_action=False, target="Calc - Shared.ods"):
    from types import SimpleNamespace

    return SimpleNamespace(
        kind="clipboard", actor="clipboard_observer", action="clipboard.sample",
        outcome="ok", seq=seq, details={
            "source_actor": source_actor, "phase": phase, "source_action": action,
            "payload_sha256": digest, "payload_changed": changed,
            "copy_or_cut_action": copy_action, "active_window_title": target,
        },
    )


def test_clipboard_metrics_recognize_native_ctrl_v_action_and_original_digest():
    from scripts.run_workflows_v1 import _event_metrics

    original = "a" * 64
    events = [
        _clipboard_event(1, "actor_a", "after_action",
                         "pyautogui.hotkey('ctrl', 'c')", original, True, True),
        _clipboard_event(2, "actor_a", "before_action",
                         "pyautogui.hotkey('ctrl', 'v')", original),
    ]
    evidence = _event_metrics(events, C03)["clipboard_evidence"]
    assert evidence["copy_a_seq"] == 1
    assert evidence["paste_a_seq"] == 2
    assert evidence["paste_payload_matches_original"] is True
    assert evidence["paste_target_app"] == "Calc"
    assert evidence["classification"] == "no_overwrite_at_paste"


def test_clipboard_metrics_detect_intervening_actor_b_copy():
    from scripts.run_workflows_v1 import _event_metrics

    original, replacement = "a" * 64, "b" * 64
    events = [
        _clipboard_event(1, "actor_a", "after_action",
                         "pyautogui.hotkey('ctrl', 'c')", original, True, True),
        _clipboard_event(2, "actor_b", "after_action",
                         'pyautogui.hotkey("ctrl", "c")', replacement, True, True),
        _clipboard_event(3, "actor_a", "before_action",
                         'pyautogui.hotkey("ctrl", "v")', replacement),
    ]
    evidence = _event_metrics(events, C03)["clipboard_evidence"]
    assert evidence["copy_b_seq"] == 2
    assert evidence["paste_a_seq"] == 3
    assert evidence["paste_payload_matches_original"] is False
    assert evidence["overwrite_between_copies"] is True
    assert evidence["classification"] == "clipboard_overwrite_supported"
