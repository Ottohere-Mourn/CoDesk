"""paraGUI contention task pgw2claim (pair W2); see spec_w2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw2claim(BaseTask):
    intermediate_eval_safe = False
    id = "pgw2claim"
    snapshot = "paragui"
    instruction = 'I\'m Dana Okafor, Marketing Director at Fenwick & Hale. Please file my expense report for the Kestrel Foods client visit in Chicago (14-16 Oct 2026) in Fenwick Spend, our expense portal (http://127.0.0.1:8102, open in Chrome; log in as dana.okafor, password Fenwick-Spend-26). The receipts for the trip (flights, hotel, two taxi rides and the client dinner) are in my Downloads folder. Create a report titled "Chicago - Kestrel Foods visit, 14-16 Oct", add one line per receipt with the date, category, merchant and amount in USD, attach each receipt to its line, and submit the report for approval. The dinner on the 15th was me plus three people from Kestrel Foods; wine is not reimbursable, so claim only the food and soft drinks. Then export the Marketing department\'s approved reports for October 2026 from the Reports page as CSV and save the file as ~/Documents/marketing_approved_oct2026.csv.'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'eog', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_claim(env, "pgw2claim_result")


TASK_CLASS = TaskPgw2claim
