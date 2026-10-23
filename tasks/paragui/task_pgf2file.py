"""paraGUI contention task pgf2file (pair F2); see spec_f2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf2file(BaseTask):
    intermediate_eval_safe = False
    id = "pgf2file"
    snapshot = "paragui"
    instruction = "I run Harbour Street Bakery. Yesterday I fed this month's paperwork through the scanner; the scans are in ~/Documents/Scans/2026-10 (open in Files). Please file them: put each document into ~/Documents/Paperwork/2026/<type>/, where the type is one of Invoices, Credit notes, Receipts, Delivery notes, Utilities or Letters, and rename it to YYYY-MM-DD_<Vendor>_<number>.pdf - the date printed on the document, the first word of the company that issued it and its invoice/receipt/bill/reference number with any \"/\" replaced by \"-\" (for example 2026-10-03_Millbrook_INV-20417.pdf). Delete blank pages and any document that was scanned twice (keep the first scan), so that the Scans folder ends up empty. Then add one row per filed document to the \"Document register\" sheet of ~/Documents/Bookkeeping/bookkeeping_2026-10.xlsx (open in LibreOffice): new file name, type, date (YYYY-MM-DD), vendor, document number and total amount in £ (leave the total empty for delivery notes and letters), and save the workbook (keep it as .xlsx)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['nautilus', 'pdfviewer', 'calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_file(env, "pgf2file_result")


TASK_CLASS = TaskPgf2file
