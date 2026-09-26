"""All tests use a real Docker Ubuntu container, Xvfb, Tk, xdotool, and shared disk file."""
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
import subprocess

import pytest

from swcub.actors import (HumanReplayActor, ScriptedCLIActor, ScriptedFocusGUIActor, ScriptedGUIActor)
from swcub.core import EventLog, read_event_log
from swcub.environment import ActorContext, DockerX11Workspace
from swcub.evaluator import FocusStateEvaluator, RequiredRowsEvaluator
from swcub.orchestrator import DualActorOrchestrator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def adapter():
    env = DockerX11Workspace(ROOT, command_timeout=30)
    env.build()
    yield env
    env.close()


def run_episode(adapter, tmp_path, actors, schedule, expected, stale=False):
    adapter.log = EventLog()
    adapter.reset(stale_gui_write=stale)
    return DualActorOrchestrator(adapter).run(
        actors, schedule, RequiredRowsEvaluator(expected), tmp_path)


def test_real_gui_single_actor(adapter, tmp_path):
    actor = ScriptedGUIActor()
    result = run_episode(adapter, tmp_path, [actor], ["gui_actor", "gui_actor"],
                         [{"id": "G1", "actor": "gui", "value": "GUI_VALUE"}])
    assert result["evaluation"]["success"] is True
    assert result["actors"]["gui_actor"]["environment_id"] == result["environment_id"]
    assert result["actors"]["gui_actor"]["turns"] == 2
    observed = actor.observation
    assert isinstance(observed["screenshot"], bytes)
    assert observed["screenshot_format"] == "xwd"
    assert (observed["screenshot_width"], observed["screenshot_height"]) == (1024, 768)
    screenshot_path = tmp_path / "gui_actor-screen.xwd"
    assert observed["screenshot_bytes"] == screenshot_path.stat().st_size > 1000
    assert hashlib.sha256(observed["screenshot"]).hexdigest() == observed["screenshot_sha256"]
    assert observed["screenshot"] == screenshot_path.read_bytes()
    event = read_event_log(tmp_path / "events.jsonl")[1]
    assert event["action"] == "x11.screenshot"
    assert event["details"]["screenshot_sha256"] == observed["screenshot_sha256"]
    assert "screenshot" not in event["details"]


def test_real_cli_single_actor(adapter, tmp_path):
    result = run_episode(adapter, tmp_path, [ScriptedCLIActor()], ["cli_actor"],
                         [{"id": "C1", "actor": "cli", "value": "CLI_VALUE"}])
    assert result["evaluation"]["success"] is True
    assert result["actors"]["cli_actor"]["environment_id"] == result["environment_id"]


def test_real_joint_actors_share_one_environment(adapter, tmp_path):
    gui_actor = ScriptedGUIActor()
    result = run_episode(adapter, tmp_path, [gui_actor, ScriptedCLIActor()],
                         ["gui_actor", "cli_actor", "gui_actor"], None)
    assert result["evaluation"]["success"] is True
    assert {actor["environment_id"] for actor in result["actors"].values()} == {result["environment_id"]}
    with (tmp_path / "shared.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [
        {"id": "C1", "actor": "cli", "value": "CLI_VALUE"},
        {"id": "G1", "actor": "gui", "value": "GUI_VALUE"},
    ]
    assert result["actors"]["gui_actor"]["turns"] == 2
    events = read_event_log(tmp_path / "events.jsonl")
    observe_index = next(i for i, event in enumerate(events)
                         if event["actor"] == "gui_actor" and event["action"] == "x11.screenshot")
    cli_index = next(i for i, event in enumerate(events)
                     if event["actor"] == "cli_actor" and event["kind"] == "cli")
    gui_write_index = next(i for i, event in enumerate(events)
                           if event["actor"] == "gui_actor" and event["action"] == "xdotool.type")
    gui_commit_index = next(i for i, event in enumerate(events)
                            if event["actor"] == "gui_actor" and event["action"] == "xdotool.key")
    assert observe_index < cli_index < gui_write_index < gui_commit_index
    assert events[observe_index]["observed_revision"] == 0
    assert events[cli_index]["observed_revision"] == 0
    assert events[gui_write_index]["observed_revision"] == 0
    assert events[gui_commit_index]["observed_revision"] == 0
    assert events[cli_index]["details"]["revision_before_action"] == 0
    assert events[cli_index]["details"]["revision_after_action"] == 1
    assert events[gui_write_index]["details"]["revision_before_action"] == 1
    assert events[gui_write_index]["details"]["revision_after_action"] == 1
    assert events[gui_commit_index]["details"]["revision_before_action"] == 1
    assert events[gui_commit_index]["details"]["revision_after_action"] == 2
    assert events[gui_write_index]["before_digest"] == events[cli_index]["after_digest"]
    assert gui_actor.observation is not None
    assert {event["actor"] for event in events} >= {"gui_actor", "cli_actor", "evaluator"}
    assert len({event["details"].get("environment_id") for event in events
                if event["actor"] in {"gui_actor", "cli_actor"}}) == 1


def test_real_stale_write_conflict_fails_evaluator(adapter, tmp_path):
    result = run_episode(adapter, tmp_path, [ScriptedGUIActor(), ScriptedCLIActor()],
                         ["gui_actor", "cli_actor", "gui_actor"], None, stale=True)
    assert result["evaluation"]["success"] is False
    assert result["evaluation"]["missing"] == [
        {"id": "C1", "actor": "cli", "value": "CLI_VALUE"}
    ]
    assert result["evaluation"]["final_rows"] == [
        {"id": "G1", "actor": "gui", "value": "GUI_VALUE"}
    ]



def test_actor_tools_do_not_expose_evaluator_or_other_role(adapter):
    adapter.log = EventLog()
    adapter.reset()
    gui = ActorContext("gui_actor", adapter, "gui")
    cli = ActorContext("cli_actor", adapter, "cli")
    assert not hasattr(gui, "evaluator")
    assert not hasattr(cli, "evaluator")
    with pytest.raises(PermissionError):
        gui.run_cli(["python3", "--version"])
    with pytest.raises(PermissionError):
        cli.observe()


def test_reset_recreates_clean_real_desktop_and_workspace(adapter):
    adapter.log = EventLog()
    old_environment = adapter.reset()
    ScriptedGUIActor().run(ActorContext("gui_actor", adapter, "gui"))
    assert adapter.csv_path.read_text().count("GUI_VALUE") == 1
    new_environment = adapter.reset()
    assert old_environment != new_environment
    assert adapter.csv_path.read_text(encoding="utf-8") == "id,actor,value\n"
    assert adapter.window_id
    proc = subprocess.run(["docker", "inspect", new_environment], capture_output=True, text=True)
    old_proc = subprocess.run(["docker", "inspect", old_environment], capture_output=True, text=True)
    assert proc.returncode == 0
    assert old_proc.returncode != 0
    assert any(event.kind == "reset" for event in adapter.log.events)


def test_real_focus_gui_and_human_replay_recover(adapter, tmp_path):
    adapter.log = EventLog()
    adapter.reset(task="focus")
    actors = [ScriptedFocusGUIActor(recover=True), HumanReplayActor()]
    result = DualActorOrchestrator(adapter).run(
        actors, ["gui_actor", "human_replay", "gui_actor"], FocusStateEvaluator(), tmp_path)
    assert result["evaluation"]["success"] is True
    assert result["evaluation"]["final_state"] == {"Document": "Approved", "Chat": "Review note"}
    assert result["actors"]["gui_actor"]["turns"] == 2
    assert result["actors"]["human_replay"]["turns"] == 1
    assert len({actor["environment_id"] for actor in result["actors"].values()}) == 1


def test_real_focus_stale_keyboard_input_is_detected(adapter, tmp_path):
    adapter.log = EventLog()
    adapter.reset(task="focus")
    actors = [ScriptedFocusGUIActor(recover=False), HumanReplayActor()]
    result = DualActorOrchestrator(adapter).run(
        actors, ["gui_actor", "human_replay", "gui_actor"], FocusStateEvaluator(), tmp_path)
    assert result["evaluation"]["success"] is False
    assert result["evaluation"]["final_state"] == {"Document": "", "Chat": "Review noteApproved"}
    assert {event.actor for event in adapter.log.events} >= {"gui_actor", "human_replay", "evaluator"}


def test_real_focus_goals_are_independently_solvable(adapter, tmp_path):
    adapter.log = EventLog()
    adapter.reset(task="focus")
    gui = ScriptedFocusGUIActor(recover=True)
    gui_expected = {"Document": "Approved", "Chat": ""}
    gui_result = DualActorOrchestrator(adapter).run(
        [gui], ["gui_actor", "gui_actor"], FocusStateEvaluator(gui_expected), tmp_path / "gui")
    assert gui_result["evaluation"]["success"] is True

    adapter.log = EventLog()
    adapter.reset(task="focus")
    human_expected = {"Document": "", "Chat": "Review note"}
    human_result = DualActorOrchestrator(adapter).run(
        [HumanReplayActor()], ["human_replay"], FocusStateEvaluator(human_expected), tmp_path / "human")
    assert human_result["evaluation"]["success"] is True
