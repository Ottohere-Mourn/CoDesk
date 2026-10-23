"""paraGUI contention task pgw3dedupe (pair W3); see spec_w3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw3dedupe(BaseTask):
    intermediate_eval_safe = False
    id = "pgw3dedupe"
    snapshot = "paragui"
    instruction = "I'm Morgan Lee, sales operations manager at Bluepeak Outdoor. Our CRM, Bluepeak CRM, is at http://127.0.0.1:8103 (open in Chrome; log in as morgan.lee, password Bluepeak-CRM-26). The account list has collected duplicate accounts. Please find every duplicate and merge it exactly as our Data quality guide in the CRM says (which record survives, which field values it keeps, who owns it) - but careful, some different companies just have similar names. Then write a merge log to ~/Documents/crm_merge_log.csv with one row per merge: the surviving account's ID and the merged account's ID (e.g. ACC-1001,ACC-1002)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'gedit']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_dedupe(env, "pgw3dedupe_result")


TASK_CLASS = TaskPgw3dedupe
