"""Offline oracle and GUI action contract checks; these are not Guest episodes."""
from __future__ import annotations

from swcub.task_factory import render_calc_fods, render_writer_fodt
from swcub.tasks.workflows_v1 import C03, F04
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
    for workflow in (F04, C03):
        first, second = workflow.files(), workflow.files()
        assert first == second and first is not second
        assert len(workflow.fixture_digest()) == 64
        assert workflow.parse(lambda path: workflow.files()[path].decode()) == workflow.state_for(())
        assert workflow.evaluate(files_for(workflow).__getitem__, ("actor_a", "actor_b"))["success"] is False


def test_solo_a_solo_b_joint_and_nontarget_integrity():
    for workflow in (F04, C03):
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
