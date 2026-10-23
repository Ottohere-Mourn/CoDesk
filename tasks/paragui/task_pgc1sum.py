"""paraGUI contention task pgc1sum (pair C1); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc1sum(BaseTask):
    intermediate_eval_safe = False
    id = "pgc1sum"
    snapshot = "paragui"
    instruction = "Our Q3 sales numbers are in ~/Documents/sales_2026Q3.xlsx (sheet 'Raw', an export from the CRM). Build the summary for Friday's regional review: add a new sheet named 'Summary' with the total Revenue per region (North America, EMEA, APAC, LATAM) for each month (July, August, September 2026), calculated from the Raw data, and add a column chart of that table on the same sheet. Keep the workbook as .xlsx in the same place."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_summary(env, "pgc1sum_result")


TASK_CLASS = TaskPgc1sum
