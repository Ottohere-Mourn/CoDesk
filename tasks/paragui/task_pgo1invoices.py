"""paraGUI contention task pgo1invoices (pair O1, family F1 office documents); spec: spec_o1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo1invoices(BaseTask):
    intermediate_eval_safe = False
    id = "pgo1invoices"
    snapshot = "paragui"
    instruction = "I'm Elena Marsh, operations manager at Harbourside Community Health. Our Q3 operations budget workbook ~/Documents/Ops_Budget_2026Q3.xlsx is open in LibreOffice Calc. The September supplier invoices have just been scanned into ~/Documents/invoices/inbox - please book them into the Actuals sheet (July and August are already there), following the finance office's coding rules in ~/Documents/invoices/AP_coding_rules.txt: one row per invoice with posting date, invoice number, vendor, description, cost centre (from the 'Deliver to' department), GL account (see the Codes sheet), net, VAT, gross and budget charge. The rules also say how to treat credit notes, duplicates, quotations and anything that does not belong to Q3. Move every PDF you book into ~/Documents/invoices/booked, and list the documents you leave in the inbox, each with the reason, in ~/Documents/invoices/inbox/NOT_BOOKED.txt. Save the workbook in place, keeping the .xlsx format."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['calc', 'evince', 'nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_invoices(env, "pgo1invoices_result")


TASK_CLASS = TaskPgo1invoices
