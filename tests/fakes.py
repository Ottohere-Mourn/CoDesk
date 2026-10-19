"""In-memory stand-ins for OSWorld's DesktopEnv, so the pipeline can be tested without a Guest."""
from __future__ import annotations

import threading


class FakeController:
    def __init__(self, shots: bool = True):
        self.shots = shots
        self.executed: list[str] = []
        self.lock = threading.Lock()

    def get_screenshot(self):
        return b"\x89PNG fake" if self.shots else None

    def get_accessibility_tree(self):
        return "<tree/>"

    def execute_python_command(self, code: str):
        with self.lock:
            self.executed.append(code)
        return {"status": "success"}


class FakeSetupController:
    def __init__(self):
        self.calls: list[list[str]] = []

    def setup(self, config, use_proxy=False):
        self.calls.append([c["type"] for c in config])
        return True

    def reset_cache_dir(self, cache_dir):
        pass


class FakeEnv:
    """Scores a task 1.0 when at least one action was executed while it was set up, else 0.0."""

    def __init__(self, *_, **__):
        self.vm_ip, self.server_port = "localhost", 5000
        self.controller = FakeController()
        self.setup_controller = FakeSetupController()
        self.task_config = None
        self.evaluator = None
        self.action_history: list = []
        self.evaluated: list[tuple[str, list, list]] = []
        self.closed = False

    def reset(self, task_config=None):
        self._set_task_info(task_config)
        self.setup_controller.setup(task_config.get("config", []))

    def _set_task_info(self, task):
        self.task_config = task
        self.task_id = task["id"]
        self.cache_dir = "/tmp/oscombo-test-cache"
        self.evaluator = task.get("evaluator")

    @staticmethod
    def _has_custom_setup(task):
        return False

    def evaluate(self):
        postconfig = (self.evaluator or {}).get("postconfig", [])
        self.evaluated.append((self.task_id, list(self.action_history), postconfig))
        if self.action_history and self.action_history[-1] == "FAIL":
            return 0.0
        return 1.0 if self.controller.executed else 0.0

    def close(self):
        self.closed = True


def task(tid: str, config=None, postconfig=None) -> dict:
    return {"id": tid, "instruction": f"do {tid}", "config": config or [],
            "evaluator": {"func": "check", "postconfig": postconfig or []}}
