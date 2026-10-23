"""paraGUI contention task pgo3budget (pair O3, family F1 office documents); spec: spec_o3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo3budget(BaseTask):
    intermediate_eval_safe = False
    id = "pgo3budget"
    snapshot = "paragui"
    instruction = "I'm Dr Amara Osei, PI of our grant application to the Northern Health Research Fund. The funder has just changed its cost rules; their letter is scanned at ~/Documents/Grant/NHRF_cost_rules_letter.pdf. Please bring our budget into line with it: update the budget workbook ~/Documents/Grant/NHRF_budget_Osei.xlsx (everything is calculated from its Rates sheet) and take out anything that is no longer eligible. Then make the proposal that is open in LibreOffice Writer (~/Documents/Grant/NHRF_proposal_Osei.docx) consistent with the revised budget: the budget table and the justification text in section 5, and the amount requested in the cover table. Save both files in place in their current formats, and leave me a short note in ~/Documents/Grant/budget_changes.txt with the new total and what you changed."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['writer', 'calc', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_budget(env, "pgo3budget_result")


TASK_CLASS = TaskPgo3budget
