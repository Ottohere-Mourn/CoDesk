"""paraGUI contention task pgm1rules (pair m1, family F2: one Thunderbird); see spec_m1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm1rules(BaseTask):
    intermediate_eval_safe = False
    id = "pgm1rules"
    snapshot = "paragui"
    instruction = "Daniel Okoye, our project director, emailed me the new mail-handling rules for the Riverside Library project - they are in the scanned memo attached to his email \"Mail rules for the Riverside Library project\". Please set this up in my Thunderbird account (sofia.marquez@larchmontdg.com) exactly as the memo says: the folders, the two tags and the four message filters in the given order (the filters must also work on mail that arrives later). Then run the filters on my Inbox so that my existing mail gets sorted. Finally, reply to Daniel's email confirming that it is set up and telling him how many of my existing messages ended up in each of the four project folders. Save the reply as a draft - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_rules(env, "pgm1rules_result")


TASK_CLASS = TaskPgm1rules
