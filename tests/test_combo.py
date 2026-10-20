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


def test_postconfig_saves_per_task_before_restarts_and_restarts_deduplicated():
    a = task("a", postconfig=[RELAUNCH])
    b = task("b", postconfig=[ACTIVATE, SAVE])
    c = task("c", postconfig=[RELAUNCH])
    save, restart = combo.postconfig_phases([a, b, c])
    assert save == [[], [ACTIVATE, SAVE], []]
    assert restart == [RELAUNCH]


def test_evaluate_tasks_applies_postconfig_once_and_marks_fail():
    env = FakeEnv()
    env.controller.executed.append("pyautogui.click(1, 1)")
    tasks = [task("a", postconfig=[RELAUNCH, SAVE]), task("b", postconfig=[ACTIVATE, SAVE])]
    result: dict = {}
    scores = combo.evaluate_tasks(env, tasks, [False, True], result)
    assert env.setup_controller.calls == [["execute"], ["activate_window", "execute"], ["launch"]]
    assert scores == {"a": 1.0, "b": 0.0}
    # each task's own evaluation runs with its postconfig removed (already applied) and its own FAIL flag
    assert env.evaluated == [("a", [], []), ("b", ["FAIL"], [])]
    assert result["eval_postconfig"] == {"save": [["execute"], ["activate_window", "execute"]], "restart": ["launch"]}


def test_one_tasks_failing_save_does_not_skip_the_others(monkeypatch):
    monkeypatch.setattr(combo.time, "sleep", lambda s: None)
    env = FakeEnv()
    orig = env.setup_controller.setup

    def flaky(config, use_proxy=False):
        if config and config[0]["type"] == "activate_window":
            raise RuntimeError("window not found")
        return orig(config, use_proxy)

    env.setup_controller.setup = flaky
    result: dict = {}
    combo.evaluate_tasks(env, [task("a", postconfig=[ACTIVATE]), task("b", postconfig=[SAVE])], [False, False], result)
    assert env.setup_controller.calls == [["execute"]]
    assert "window not found" in result["eval_errors"]["postconfig_save:a"]


def test_setup_records_windows_per_task():
    env = FakeEnv()
    views = iter([{"1"}, {"1", "2"}, {"1", "2", "3", "4"}])
    info = combo.setup_tasks(env, [task("a"), task("b")], probe=lambda: next(views))
    assert info["setup_windows"] == [["2"], ["3", "4"]]


def test_evaluator_crash_gives_none():
    class Broken(FakeEnv):
        def evaluate(self):
            raise RuntimeError("getter failed")

    result: dict = {}
    assert combo.evaluate_tasks(Broken(), [task("a")], [False], result) == {"a": None}
    assert "getter failed" in result["eval_errors"]["a"]
