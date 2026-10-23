"""paraGUI contention task pgd1export (pair D1, family F4 software development); see spec_d1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd1export(BaseTask):
    intermediate_eval_safe = False
    id = "pgd1export"
    snapshot = "paragui"
    instruction = "Our bookkeeper at Brandt & Partner wants to import the Larder & Co web-shop orders into his accounting software every month. The shop's code is in ~/projects/larder-shop (open in VS Code) and its dev server is running at http://127.0.0.1:8111 (open in Chrome). The file layout he needs is shown in the screenshot of his import template, docs/requests/bookkeeping-import-template.png. Please add an endpoint /orders/export.csv?month=YYYY-MM that returns that month's orders exactly in his layout (served as text/csv), add a 'Download CSV' link to the admin Orders page (/orders) that exports the month currently shown, document the endpoint in README.md and add a unit test for the export. Restart the dev server (./dev.sh restart), then open the October 2026 orders in Chrome, download the export with your new link and save it as ~/Documents/Bookkeeping/larder-orders-2026-10.csv. Finally commit your changes, and nothing else, with the message 'Add bookkeeping CSV export'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_export(env, "pgd1export_result")


TASK_CLASS = TaskPgd1export
