"""paraGUI contention task pgc2claim (pair C2); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc2claim(BaseTask):
    intermediate_eval_safe = False
    id = "pgc2claim"
    snapshot = "paragui"
    instruction = 'I need to file the expense claim for my Berlin client visit (16-19 Sep 2026). The receipts for that trip are in my Downloads folder. Fill in ~/Documents/claims/expense_form.xlsx: one line per receipt (date, vendor, category, amount in EUR) starting at row 6, and the total amount in D11. Also put a copy of each of those receipts into a new folder ~/Documents/claims/2026-09-trip/. Save the form as .xlsx.'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['nautilus', 'calc', 'pdfviewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_claim(env, "pgc2claim_result")


TASK_CLASS = TaskPgc2claim
