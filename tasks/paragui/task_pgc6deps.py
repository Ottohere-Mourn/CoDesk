"""paraGUI contention task pgc6deps (pair C6); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c6 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc6deps(BaseTask):
    intermediate_eval_safe = False
    id = "pgc6deps"
    snapshot = "paragui"
    instruction = "Security asked every team to apply advisory SA-2026-07; it is described in SECURITY_ADVISORY.md of our invoicer repo (~/projects/invoicer, open in VS Code). Bump the affected packages in requirements.txt to the fixed versions, note the bump under 'Unreleased' in CHANGELOG.md, check that the unit tests still pass (python3 -m unittest), and commit just this change with the message 'Bump dependencies for SA-2026-07'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_deps(env, "pgc6deps_result")


TASK_CLASS = TaskPgc6deps
