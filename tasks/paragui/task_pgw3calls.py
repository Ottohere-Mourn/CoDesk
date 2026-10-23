"""paraGUI contention task pgw3calls (pair W3); see spec_w3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw3calls(BaseTask):
    intermediate_eval_safe = False
    id = "pgw3calls"
    snapshot = "paragui"
    instruction = "I'm Morgan Lee, sales operations manager at Bluepeak Outdoor. Our CRM, Bluepeak CRM, is at http://127.0.0.1:8103 (open in Chrome; log in as morgan.lee, password Bluepeak-CRM-26). Please enter this week's calls from my notes (~/Documents/call_notes_wk43.docx) into the CRM: log each call as a Call activity on the right account (date, the contact I spoke to, a short summary), create the opportunities the notes mention with their amount, stage and close date, and make the contact and address changes the notes ask for. Then put the new opportunities' CRM IDs (OPP-...) into the CRM ID column of my pipeline sheet ~/Documents/pipeline_q4.xlsx."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'libreoffice_writer', 'libreoffice_calc', 'eog']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_calls(env, "pgw3calls_result")


TASK_CLASS = TaskPgw3calls
