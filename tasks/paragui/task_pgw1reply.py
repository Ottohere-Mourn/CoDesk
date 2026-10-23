"""paraGUI contention task pgw1reply (pair W1); see spec_w1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw1reply(BaseTask):
    intermediate_eval_safe = False
    id = "pgw1reply"
    snapshot = "paragui"
    instruction = "I'm Sam Rivera, support team lead at Larkspur Software. Our help desk, the Larkspur Support Desk, is at http://127.0.0.1:8101 (open in Chrome; log in as sam.rivera, password Larkspur-Desk-26). Please answer tickets #1037, #1043, #1048, #1051, #1056 and #1059 for me. Each answer must be a public reply that resolves the customer's question with the right article from the desk's knowledge base (mention the article number, e.g. KB-104), and each ticket must end up in the status our status guide (KB-001) prescribes, with any internal note the guide requires. Don't change anything else on these tickets. Then add one row per ticket to my support log ~/Documents/support_log_2026-10.xlsx (date 2026-10-22, ticket number, customer, KB article, new status), keeping the existing rows."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_reply(env, "pgw1reply_result")


TASK_CLASS = TaskPgw1reply
