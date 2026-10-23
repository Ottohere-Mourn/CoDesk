"""paraGUI contention task pgc2tidy (pair C2); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc2tidy(BaseTask):
    intermediate_eval_safe = False
    id = "pgc2tidy"
    snapshot = "paragui"
    instruction = "My Downloads folder is a mess. Please tidy it up: move every PDF into ~/Documents/Archive/<YYYY-MM>/ according to the date in its file name (PDFs without a date go to ~/Documents/Archive/undated/), move the images into ~/Pictures/Downloads/, and delete the installer packages (.deb, .zip) and the duplicate copies whose names end in ' (1)'. When you are done, Downloads should be empty."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_tidy(env, "pgc2tidy_result")


TASK_CLASS = TaskPgc2tidy
