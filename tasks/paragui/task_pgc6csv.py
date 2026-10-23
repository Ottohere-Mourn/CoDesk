"""paraGUI contention task pgc6csv (pair C6); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c6 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc6csv(BaseTask):
    intermediate_eval_safe = False
    id = "pgc6csv"
    snapshot = "paragui"
    instruction = "Finance wants a CSV export in our invoicer project (~/projects/invoicer, open in VS Code). Add a function export_csv(invoices, path) to app/report.py that writes a header row id,customer,amount,status followed by one row per invoice, add a unit test for it in tests/test_report.py, note the feature under 'Unreleased' in CHANGELOG.md, make sure all tests pass (python3 -m unittest), and commit your change with the message 'Add CSV export'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_csv(env, "pgc6csv_result")


TASK_CLASS = TaskPgc6csv
