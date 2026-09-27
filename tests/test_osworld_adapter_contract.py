"""Interface contract checks with a stub; these are not OSWorld VM results."""
from __future__ import annotations
import ast
import logging
import shlex

import pytest

from swcub.environment import ActorContext
from swcub.actors import ScriptedGuestFocusGUIActor, ScriptedGuestHumanReplayActor
from swcub.evaluator import (GuestCsvEvaluator, GuestFocusEvaluator,
                             GuestLibreOfficeEvaluator, GuestWebStateEvaluator,
                             OSWorldTaskEvaluator)
from swcub.osworld_adapter import OSWorldSharedEpisode


class DesktopEnvStub:
    """Small signature-compatible stand-in used only to check adapter wiring."""

    def __init__(self):
        self.pauses: list[float] = []
        self.actions: list[object] = []
        self.eval_logger = None
        self.closed = False
        self.is_environment_used = False

    def reset(self, task_config=None, seed=None, options=None):
        return {"screenshot": b"stub-screen", "instruction": task_config["instruction"]}

    def step(self, action, pause=2):
        self.actions.append(action)
        self.pauses.append(pause)
        return {"screenshot": b"after-action"}, 0.0, False, {"stub": True}

    def evaluate(self, eval_logger: logging.Logger):
        self.eval_logger = eval_logger
        return 1.0

    def close(self):
        self.closed = True

    def _get_obs(self):
        return {"screenshot": b"refreshed-screen"}


class NoArgumentEvaluatorStub(DesktopEnvStub):
    def evaluate(self):
        return 0.5


def test_osworld_adapter_matches_reset_step_eval_and_cli_injection():
    desktop = DesktopEnvStub()
    commands: list[str] = []
    episode = OSWorldSharedEpisode(desktop, cli_executor=lambda command: commands.append(command) or "ok")

    initial = episode.reset({"id": "stub-task", "instruction": "type a value"}, seed=7)
    assert initial["instruction"] == "type a value"
    assert episode.observe("gui_actor")["screenshot"] == b"stub-screen"
    episode.act("gui_actor", "gui", "pyautogui.press('x')")
    result = episode.act("cli_actor", "cli", ["python3", "-c", "print('ok')"])

    assert desktop.actions == ["pyautogui.press('x')"]
    assert desktop.pauses == [2]
    assert len(commands) == 1
    assert desktop.is_environment_used is True
    assert shlex.split(commands[0]) == ["python3", "-c", "print('ok')"]
    assert result == "ok"
    assert OSWorldTaskEvaluator().evaluate(episode) == {"success": True, "osworld_score": 1.0}
    assert isinstance(desktop.eval_logger, logging.Logger)
    assert len(episode.log.events) == 4
    episode.close()
    assert desktop.closed


def test_osworld_adapter_supports_no_argument_evaluator_wrappers():
    episode = OSWorldSharedEpisode(NoArgumentEvaluatorStub())
    assert OSWorldTaskEvaluator().evaluate(episode) == {"success": False, "osworld_score": 0.5}


def test_osworld_adapter_refreshes_observation_after_cli_setup():
    episode = OSWorldSharedEpisode(DesktopEnvStub())
    episode.reset({"id": "task", "instruction": "open app"})
    context = ActorContext("gui_actor", episode, "gui")
    result = context.refresh_observation()
    assert result["screenshot"] == b"refreshed-screen"
    assert episode.log.events[-1].action == "osworld.refresh_observation"
    assert episode.log.events[-1].actor == "gui_actor"
    assert episode.screenshot_history[-1][1] == b"refreshed-screen"


def test_actor_context_gui_operations_translate_and_focus_is_injectable():
    desktop = DesktopEnvStub()
    episode = OSWorldSharedEpisode(
        desktop, window_focus_translator=lambda operation: "pyautogui.getActiveWindow()")
    episode.reset({"id": "stub-task", "instruction": "edit the active field"})
    gui = ActorContext("gui_actor", episode, "gui")

    gui.type_text("A 'quoted' value")
    gui.press_key("Return")
    gui.submit_gui("Approved")
    gui.focus_window("Document")

    assert desktop.actions == [
        'pyautogui.write("A \'quoted\' value")',
        'pyautogui.press("enter")',
        'pyautogui.write("Approved"); pyautogui.press(\'enter\')',
        "pyautogui.getActiveWindow()",
    ]
    for command in desktop.actions:
        ast.parse(command)
    action_event = episode.log.events[1]
    assert action_event.details["source_action"] == {"op": "type", "value": "A 'quoted' value"}


def test_window_focus_needs_an_application_specific_translator():
    episode = OSWorldSharedEpisode(DesktopEnvStub())
    with pytest.raises(NotImplementedError, match="window focus is application-specific"):
        episode.act("gui_actor", "gui", {"op": "focus", "window": "Document"})


def test_osworld_hotkey_translation_and_screenshot_artifact_copy(tmp_path):
    desktop = DesktopEnvStub()
    episode = OSWorldSharedEpisode(desktop)
    episode.reset({"id": "stub-task", "instruction": "open terminal"})
    assert episode._translate_gui_operation({"op": "key", "key": "ctrl+alt+t"}) == (
        "pyautogui.hotkey(\"ctrl\", \"alt\", \"t\")")
    assert episode._translate_gui_operation({"op": "click", "x": 45, "y": 15}) == (
        "pyautogui.click(45, 15)")
    episode.copy_artifacts(tmp_path)
    assert (tmp_path / "guest-screen.png").read_bytes() == b"stub-screen"


def test_guest_focus_evaluator_detects_misdirected_text():
    state = {"/tmp/swcub_document.txt": "Approved\n",
             "/tmp/swcub_chat.txt": "Review note\n"}
    evaluator = GuestFocusEvaluator(lambda path: state[path], {
        "Document": "Approved\n", "Chat": "Review note\n"})
    assert evaluator.evaluate(None)["success"] is True

    state["/tmp/swcub_document.txt"] = ""
    state["/tmp/swcub_chat.txt"] = "Review note\nApproved\n"
    result = evaluator.evaluate(None)
    assert result["success"] is False
    assert result["missing"]["Document"]["actual"] == ""
    assert result["missing"]["Chat"]["actual"] == "Review note\nApproved\n"


def test_guest_focus_actor_interfaces_dispatch_real_desktop_operations():
    desktop = DesktopEnvStub()
    episode = OSWorldSharedEpisode(desktop)
    episode.reset({"id": "focus-probe", "instruction": "use two windows"})
    gui_context = ActorContext("gui_actor", episode, "gui")
    gui = ScriptedGuestFocusGUIActor(recover=True)
    assert gui.run_step(gui_context) is False
    assert gui.run_step(gui_context) is True
    guest_actions = [event.details.get("source_action") for event in episode.log.events]
    assert {"op": "click", "x": 420, "y": 220} in guest_actions

    human_context = ActorContext("human_replay", episode, "human_replay")
    ScriptedGuestHumanReplayActor().run(human_context)
    guest_actions = [event.details.get("source_action") for event in episode.log.events]
    assert {"op": "click", "x": 1320, "y": 220} in guest_actions
    assert {"op": "type", "value": "Review note"} in guest_actions


def test_guest_libreoffice_evaluator_checks_saved_document_and_sheet():
    text_ns = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    table_ns = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    writer = f'<doc xmlns:t="{text_ns}"><t:p>Approved by GUI actor</t:p></doc>'
    calc = (f'<doc xmlns:t="{text_ns}" xmlns:table="{table_ns}">'
            '<table:table-row><table:table-cell><t:p>Record</t:p></table:table-cell>'
            '<table:table-cell><t:p>Status</t:p></table:table-cell></table:table-row>'
            '<table:table-row><table:table-cell><t:p>Quarterly</t:p></table:table-cell>'
            '<table:table-cell><t:p>Approved</t:p></table:table-cell></table:table-row></doc>')
    state = {"/tmp/swcub_office/document.fodt": writer,
             "/tmp/swcub_office/table.fods": calc}
    evaluator = GuestLibreOfficeEvaluator(lambda path: state[path],
        "Approved by GUI actor", [["Record", "Status"], ["Quarterly", "Approved"]])
    assert evaluator.evaluate(None)["success"] is True

    state["/tmp/swcub_office/table.fods"] = calc.replace("Approved", "GUI actor text")
    result = evaluator.evaluate(None)
    assert result["success"] is False
    assert result["missing"]["calc_sheet"]["actual"][1][1] == "GUI actor text"


def test_guest_web_state_evaluator_checks_gui_and_cli_fields():
    state = '{"gui_status":"Approved","cli_note":"Reviewed by CLI"}'
    evaluator = GuestWebStateEvaluator(lambda: state,
        {"gui_status": "Approved", "cli_note": "Reviewed by CLI"})
    assert evaluator.evaluate(None)["success"] is True

    stale = '{"gui_status":"Approved","cli_note":"Draft"}'
    result = GuestWebStateEvaluator(lambda: stale,
        {"gui_status": "Approved", "cli_note": "Reviewed by CLI"}).evaluate(None)
    assert result["success"] is False
    assert result["missing"]["cli_note"]["actual"] == "Draft"


def test_guest_csv_evaluator_checks_exact_rows_without_actor_access():
    result = GuestCsvEvaluator(
        lambda: "actor,value\ngui,GUI_VALUE\ncli,CLI_VALUE\n",
        [{"actor": "gui", "value": "GUI_VALUE"},
         {"actor": "cli", "value": "CLI_VALUE"}],
    ).evaluate(None)
    assert result["success"] is True
    assert result["actual_rows"] == 2
    assert result["missing"] == []


def test_osworld_cli_action_requires_same_guest_executor():
    episode = OSWorldSharedEpisode(DesktopEnvStub())
    with pytest.raises(RuntimeError, match="cli_executor bound to the same OSWorld guest"):
        episode.act("cli_actor", "cli", ["cat", "/workspace/shared.csv"])
