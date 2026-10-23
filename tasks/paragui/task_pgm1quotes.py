"""paraGUI contention task pgm1quotes (pair m1, family F2: one Thunderbird); see spec_m1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm1quotes(BaseTask):
    intermediate_eval_safe = False
    id = "pgm1quotes"
    snapshot = "paragui"
    instruction = "Daniel asked me to sort out the reading-room furniture for the Riverside Library job - his email \"[RLP] Reading room furniture - please compare the quotes\" has the criteria. Four vendors sent quotes by email: find them in my Thunderbird mailbox and save every quote PDF into ~/Documents/RLP/Quotes/ (keep the file names). Then make a workbook ~/Documents/RLP/Furniture_Quotes.xlsx with one row per vendor and the columns Vendor, Quote No, Total (USD, incl. delivery and tax), Delivery Date, Chair Warranty (years), Meets Criteria (Y/N). If a vendor revised its quote, use only the latest version. Pick the vendor according to Daniel's criteria, then reply to that vendor's latest quote email accepting the quote (mention their quote number and our purchase order number), and reply to Daniel telling him which vendor you chose and the total. Save both replies as drafts; don't send anything."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_quotes(env, "pgm1quotes_result")


TASK_CLASS = TaskPgm1quotes
