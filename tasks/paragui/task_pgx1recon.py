"""paraGUI task pgx1recon (F6 pair x1); see spec_x1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx1recon(BaseTask):
    intermediate_eval_safe = False
    id = "pgx1recon"
    snapshot = "paragui"
    instruction = "It's month-end at Harbour & Pine and our accountant Priya needs the September bank reconciliation - her email 'September close - bank reconciliation' in Thunderbird has the template and her rules, and Tom emailed me a scan of the paper bank statement. Please record every customer payment on the statement against the right invoice in Ledgerline (http://127.0.0.1:8121, username sam, password HarbourPine26), dated the day the money arrived. Customers often quote the wrong invoice number, so check who paid and how much; split a transfer that pays several invoices, and don't post anything twice. Save the completed template as ~/Documents/Finance/Bank_Rec_2026-09.xlsx and reply to Priya's email with it attached, listing the unmatched items and anything still owed after a short payment, with amounts. Leave the reply in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_recon(env, "pgx1recon_result")


TASK_CLASS = TaskPgx1recon
