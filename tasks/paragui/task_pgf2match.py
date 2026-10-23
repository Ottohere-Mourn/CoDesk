"""paraGUI contention task pgf2match (pair F2); see spec_f2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf2match(BaseTask):
    intermediate_eval_safe = False
    id = "pgf2match"
    snapshot = "paragui"
    instruction = "Before I pay this month's suppliers, please do the three-way match for the five invoices that belong to our October purchase orders PO-1041 to PO-1045. The purchase orders are in the \"PO list\" sheet of ~/Documents/Bookkeeping/bookkeeping_2026-10.xlsx (open in LibreOffice); the supplier invoices and delivery notes are among the paperwork I scanned yesterday into ~/Documents/Scans/2026-10. In the \"AP check\" sheet enter every line of those five invoices as invoiced (invoice no., PO no., item, qty, unit price, line total), and in the Issue column write \"price\" if the unit price differs from the PO, \"qty\" if the invoiced quantity differs from what we actually received (my staff write shortages by hand on the delivery note; if there is no delivery note, we received what we ordered) or \"not on PO\" for items we never ordered; leave it empty when the line is fine. Save the workbook (keep it as .xlsx). Then write ~/Documents/Bookkeeping/supplier_queries.txt with one line per invoice that has a problem: the invoice number, the supplier and the amount we were over-charged in £ excluding VAT (for each line: invoiced amount minus what we owe for the quantity received at the PO price)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['pdfviewer', 'calc', 'gedit', 'nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_match(env, "pgf2match_result")


TASK_CLASS = TaskPgf2match
