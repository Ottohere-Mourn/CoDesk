"""paraGUI task pgx2sched (F6 pair x2); see spec_x2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx2sched(BaseTask):
    intermediate_eval_safe = False
    id = "pgx2sched"
    snapshot = "paragui"
    instruction = "Please schedule the panel interviews for our Product Designer role (REQ-027). The candidates have answered my 'Interview availability' emails in Thunderbird, and Ben Okoro's email 'PD panel interviews next week' has the panel's constraints, his booking rule and the panel sheet. Book the slots in HireDesk (http://127.0.0.1:8122, username alex, password Fernleaf!Talent) and update anyone who has dropped out, fill in Ben's panel sheet and save it as ~/Documents/Recruiting/ProductDesigner_interviews.xlsx, and reply to each scheduled candidate's latest email with an invitation giving the date, time and the video link from HireDesk. Leave the replies in Drafts - don't send them."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_sched(env, "pgx2sched_result")


TASK_CLASS = TaskPgx2sched
