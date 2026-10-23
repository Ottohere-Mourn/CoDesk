"""paraGUI contention task pgw1triage (pair W1); see spec_w1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw1triage(BaseTask):
    intermediate_eval_safe = False
    id = "pgw1triage"
    snapshot = "paragui"
    instruction = "I'm Sam Rivera, support team lead at Larkspur Software. Our help desk, the Larkspur Support Desk, is at http://127.0.0.1:8101 (open in Chrome; log in as sam.rivera, password Larkspur-Desk-26). Please triage the untriaged ticket queue exactly as our triage policy says (Support_Triage_Policy_v3.pdf in my Documents folder): every ticket needs the right team, priority, assignee and status, and spam and duplicates must be closed the way the policy describes. When the queue is done, post the triage handover on the desk's Team board as the policy asks."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_triage(env, "pgw1triage_result")


TASK_CLASS = TaskPgw1triage
