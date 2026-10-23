"""paraGUI contention task pgc4inbox (pair C4); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc4inbox(BaseTask):
    intermediate_eval_safe = False
    id = "pgc4inbox"
    snapshot = "paragui"
    instruction = 'My inbox (jordan.lee@northwindlabs.com in Thunderbird) is out of control - please get it to inbox zero. Create three folders under my account: Finance, Newsletters and Team. Move receipts, invoices, bills and payment confirmations into Finance; newsletters, marketing and job-alert mail into Newsletters; and everything from my colleagues (anyone with a @northwindlabs.com address) into Team. Delete the spam and phishing messages. When you are done the Inbox should be empty.'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_inbox(env, "pgc4inbox_result")


TASK_CLASS = TaskPgc4inbox
