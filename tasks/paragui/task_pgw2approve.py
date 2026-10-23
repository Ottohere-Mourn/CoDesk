"""paraGUI contention task pgw2approve (pair W2); see spec_w2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw2approve(BaseTask):
    intermediate_eval_safe = False
    id = "pgw2approve"
    snapshot = "paragui"
    instruction = "I'm Dana Okafor, Marketing Director at Fenwick & Hale. Twelve expense reports from my team are waiting for my approval in Fenwick Spend, our expense portal (http://127.0.0.1:8102, open in Chrome; log in as dana.okafor, password Fenwick-Spend-26 - approvals are in the Approver view). Please go through each of them and approve or reject it according to our travel & expense policy (Fenwick_TE_Policy_2026.pdf in my Documents folder), checking every line against its receipt. When you reject a report, say in the comment exactly what is wrong. Finally, save a short summary as ~/Documents/approvals_2026-10-22.txt with one line per report: the report number (EXP-...), Approved or Rejected, and the reason for each rejection."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_approve(env, "pgw2approve_result")


TASK_CLASS = TaskPgw2approve
