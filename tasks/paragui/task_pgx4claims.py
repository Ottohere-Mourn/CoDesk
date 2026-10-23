"""paraGUI task pgx4claims (F6 pair x4); see spec_x4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx4claims(BaseTask):
    intermediate_eval_safe = False
    id = "pgx4claims"
    snapshot = "paragui"
    instruction = "Please do the ECCV 2026 travel expense claims Elena asked for (her email 'ECCV claims' in Thunderbird); the receipts are in the travellers' emails and the rules are in the policy that School Finance emailed. In LabDesk (http://127.0.0.1:8124, username jross, password Northbridge#26) create and submit one claim per traveller, with a line for each reimbursable receipt in the receipt's own currency and date, applying the policy's caps and exclusions. File every traveller's receipt email into a new mail folder Claims/ECCV 2026. Then fill in ~/Documents/Lab/ECCV2026_travel_summary.xlsx (claim number and GBP total per traveller, totals per grant) and leave a draft to finance-claims@inf.northbridge.ac.uk listing the claim numbers with their GBP totals. Leave it in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_claims(env, "pgx4claims_result")


TASK_CLASS = TaskPgx4claims
