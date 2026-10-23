"""paraGUI contention task pgm3inbox (pair m3, family F2: one Thunderbird); see spec_m3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm3inbox(BaseTask):
    intermediate_eval_safe = False
    id = "pgm3inbox"
    snapshot = "paragui"
    instruction = "My Thunderbird inbox (lukas.brandt@aldervane.de) needs a clean-up. Under my account, create a folder Travel and a folder Projects with the subfolders Donauwerke, Helios and Marlow. Move every mail about one of these three client projects into its project folder (the clients write from donauwerke.at, helios-energie.de and marlowretail.co.uk; colleagues put the project name in the subject) and every booking confirmation or other travel-related mail into Travel. Archive everything else I received before 1 October 2026 with Thunderbird's Archive function. Star every message in which someone asks me to do something by a specific date, wherever it ends up, and create a saved search folder called \"Follow-up\" under my account that shows all starred messages from all of these folders. Finally, write ~/Documents/followups.txt with one line per starred message: the deadline as YYYY-MM-DD, the sender's name and the subject."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'gedit']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_inbox(env, "pgm3inbox_result")


TASK_CLASS = TaskPgm3inbox
