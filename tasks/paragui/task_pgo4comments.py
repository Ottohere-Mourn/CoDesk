"""paraGUI contention task pgo4comments (pair O4, family F1 office documents); spec: spec_o4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo4comments(BaseTask):
    intermediate_eval_safe = False
    id = "pgo4comments"
    snapshot = "paragui"
    instruction = "I'm Lina Park, a PhD student at the Institute for Data Systems. My advisor Markus went through a printout of my DSSW workshop talk and wrote his comments on it in red; the scan is ~/Documents/Talk/handout_comments_MW.pdf. Please make all of his changes in the presentation that is open in LibreOffice Impress (~/Documents/Talk/StreamJoin_DSSW.pptx), save it in place as .pptx, and export a PDF of the slides to ~/Documents/Talk/StreamJoin_DSSW_v2_for_Markus.pdf so I can send it back to him."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['impress', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_comments(env, "pgo4comments_result")


TASK_CLASS = TaskPgo4comments
