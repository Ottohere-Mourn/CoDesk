"""paraGUI task pgx1report (F6 pair x1); see spec_x1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx1report(BaseTask):
    intermediate_eval_safe = False
    id = "pgx1report"
    snapshot = "paragui"
    instruction = "Tom wants the September management report - his email 'September management pack' in Thunderbird says what goes in it. Take all figures from the Reports page of Ledgerline (http://127.0.0.1:8121, username sam, password HarbourPine26). Keep the numbers and the column chart in ~/Documents/Reports/Mgmt_Pack_2026-09.xlsx, write the report in LibreOffice Writer and save it as ~/Documents/Reports/Management_Report_2026-09.docx, export it to Management_Report_2026-09.pdf in the same folder, upload that PDF to Ledgerline as the September 2026 board pack, and reply to Tom's email with the PDF attached. Leave the reply in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc', 'libreoffice_writer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_report(env, "pgx1report_result")


TASK_CLASS = TaskPgx1report
