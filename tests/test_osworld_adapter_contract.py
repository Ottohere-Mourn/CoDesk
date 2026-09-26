"""Interface contract checks with a stub; these are not OSWorld VM results."""
from __future__ import annotations
import logging
import shlex

import pytest

from swcub.evaluator import OSWorldTaskEvaluator
from swcub.osworld_adapter import OSWorldSharedEpisode


class DesktopEnvStub:
    """Small signature-compatible stand-in used only to check adapter wiring."""

    def __init__(self):
        self.pauses: list[float] = []
        self.actions: list[object] = []
        self.eval_logger = None
        self.closed = False

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


def test_osworld_cli_action_requires_same_guest_executor():
    episode = OSWorldSharedEpisode(DesktopEnvStub())
    with pytest.raises(RuntimeError, match="cli_executor bound to the same OSWorld guest"):
        episode.act("cli_actor", "cli", ["cat", "/workspace/shared.csv"])
