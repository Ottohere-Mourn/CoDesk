"""paraGUI contention task pgw4feedback (pair W4); see spec_w4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw4feedback(BaseTask):
    intermediate_eval_safe = False
    id = "pgw4feedback"
    snapshot = "paragui"
    instruction = 'I\'m Jordan Ellis, talent acquisition lead at Quillon Health. Our applicant tracking system, Quillon Talent, is at http://127.0.0.1:8104 (open in Chrome; log in as jordan.ellis, password Quillon-Talent-26). The phone-interview feedback forms of the eight candidates in the stage "Interviewed - awaiting decision" have been scanned and attached to their profiles. For each of them, enter the scorecard in Quillon Talent exactly as written on the form and move the candidate to the stage that our interview decision rubric (Interview_Decision_Rubric.pdf in my Documents folder) prescribes. Book the onsite loop for next week (26-30 Oct 2026) for everyone who goes to Onsite, as the rubric and the requisition\'s interview plan describe. Finally, leave a note on each of the two requisitions saying who goes to onsite (with the date), who goes to hiring manager review and who was rejected.'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_feedback(env, "pgw4feedback_result")


TASK_CLASS = TaskPgw4feedback
