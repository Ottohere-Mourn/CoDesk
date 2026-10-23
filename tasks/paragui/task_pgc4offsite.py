"""paraGUI contention task pgc4offsite (pair C4); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc4offsite(BaseTask):
    intermediate_eval_safe = False
    id = "pgc4offsite"
    snapshot = "paragui"
    instruction = "Dana sent the team an email about our November offsite, and Priya from Ops sent my hotel booking. In Thunderbird, save the agenda PDF from Dana's email and the booking confirmation PDF from Priya's email into ~/Documents/Offsite/ (keep their file names). Then reply to Dana's offsite email: say that I will attend and that I am vegetarian. Don't send it - save the reply as a draft, I want to read it before it goes out."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_offsite(env, "pgc4offsite_result")


TASK_CLASS = TaskPgc4offsite
