"""paraGUI contention task pgm4support (pair m4, family F2: one Thunderbird); see spec_m4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm4support(BaseTask):
    intermediate_eval_safe = False
    id = "pgm4support"
    snapshot = "paragui"
    instruction = "Please work through the customer support emails in my shop's Thunderbird inbox (hello@fernandfennel.shop). Answer each one with the matching macro from ~/Documents/KB/Support_Macros.docx (one macro per email; fill in the customer's first name and the order number where the macro has placeholders) and save each reply as a draft - don't send anything. Then move every handled support email into a folder Support/Done (create it under my account: Support with the subfolder Done). Mark the scam and spam emails as junk so that they end up in the Junk folder, and leave all other non-support emails in the Inbox. Finally, log every support email you handled in ~/Documents/support_log.xlsx with the columns Date, Customer Email, Order No and Macro (the macro code, e.g. KB-03)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'libreoffice_writer', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_support(env, "pgm4support_result")


TASK_CLASS = TaskPgm4support
