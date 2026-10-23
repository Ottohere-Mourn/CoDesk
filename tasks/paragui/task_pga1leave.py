"""paraGUI task pga1leave (pair a1, RED round); see spec_a1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga1leave(BaseTask):
    intermediate_eval_safe = False
    id = "pga1leave"
    snapshot = "paragui"
    instruction = "I'm Sam Ellison, deputy manager at Elmbrook House Care Home. Our rota system RotaDesk is at http://127.0.0.1:8131 (open in Chrome; username sam.ellison, password Elmbrook-Rota-26). Please deal with all the pending leave requests for the week of 16 November exactly as the leave policy in RotaDesk says: approve or decline each one (give the reason when you decline). For every request you approve, take the person off all their shifts during the leave and put a colleague on each of those shifts who is allowed to work it under our rota rules. Then write a short summary to ~/Documents/Leave/leave_decisions_wk47.txt with one line per request: the person, the dates, approved or declined, and who covers their shifts (or why it was declined)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_leave(env, "pga1leave_result")


TASK_CLASS = TaskPga1leave
