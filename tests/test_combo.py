from oscombo import combo

from fakes import FakeEnv, task

LAUNCH_CHROME = {"type": "launch", "parameters": {"command": ["google-chrome", "--remote-debugging-port=1337"]}}
OPEN_FILE = {"type": "open", "parameters": {"path": "/home/user/a.xlsx"}}
ACTIVATE = {"type": "activate_window", "parameters": {"window_name": "a.xlsx - LibreOffice Calc"}}
SAVE = {"type": "execute", "parameters": {"command": ["xdotool", "key", "ctrl+s"]}}
RELAUNCH = {"type": "launch", "parameters": {"command": ["pkill", "chrome"]}}


def test_identical_setup_steps_run_once():
    a = task("a", config=[LAUNCH_CHROME])
    b = task("b", config=[LAUNCH_CHROME, OPEN_FILE])
    extra, skipped = combo.dedupe_setup([a, b])
    assert extra == [[OPEN_FILE]]
    assert skipped == ["launch"]


def test_setup_tasks_uses_reset_then_controller():
    env = FakeEnv()
    info = combo.setup_tasks(env, [task("a", config=[LAUNCH_CHROME]), task("b", config=[LAUNCH_CHROME, OPEN_FILE])])
    assert env.setup_controller.calls == [["launch"], ["open"]]
    assert info["skipped_duplicate_setup_steps"] == ["launch"]


def test_postconfig_saves_before_restarts_and_restarts_deduplicated():
    a = task("a", postconfig=[RELAUNCH])
    b = task("b", postconfig=[ACTIVATE, SAVE])
    c = task("c", postconfig=[RELAUNCH])
    phases = combo.postconfig_phases([a, b, c])
    assert phases["save"] == [ACTIVATE, SAVE]
    assert phases["restart"] == [RELAUNCH]


def test_evaluate_tasks_applies_postconfig_once_and_marks_fail():
    env = FakeEnv()
    env.controller.executed.append("pyautogui.click(1, 1)")
    tasks = [task("a", postconfig=[RELAUNCH]), task("b", postconfig=[ACTIVATE, SAVE])]
    result: dict = {}
    scores = combo.evaluate_tasks(env, tasks, [False, True], result)
    assert env.setup_controller.calls == [["activate_window", "execute"], ["launch"]]
    assert scores == {"a": 1.0, "b": 0.0}
    # each task's own evaluation runs with its postconfig removed (already applied) and its own FAIL flag
    assert env.evaluated == [("a", [], []), ("b", ["FAIL"], [])]
    assert result["eval_postconfig"] == {"save": ["activate_window", "execute"], "restart": ["launch"]}


def test_evaluator_crash_gives_none():
    class Broken(FakeEnv):
        def evaluate(self):
            raise RuntimeError("getter failed")

    result: dict = {}
    assert combo.evaluate_tasks(Broken(), [task("a")], [False], result) == {"a": None}
    assert "getter failed" in result["eval_errors"]["a"]
