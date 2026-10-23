"""paraGUI contention task pgc1clean (pair C1); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc1clean(BaseTask):
    intermediate_eval_safe = False
    id = "pgc1clean"
    snapshot = "paragui"
    instruction = "The 'Raw' sheet in ~/Documents/sales_2026Q3.xlsx is a messy CRM export. Clean it up in place before Friday's regional review: remove the duplicated orders (same Order ID), make every Date a real date displayed as YYYY-MM-DD, and fix the Region names so that only North America, EMEA, APAC and LATAM remain. Do not drop or change any real order. Keep the workbook as .xlsx in the same place."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_clean(env, "pgc1clean_result")


TASK_CLASS = TaskPgc1clean
