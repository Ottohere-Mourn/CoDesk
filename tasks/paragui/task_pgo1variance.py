"""paraGUI contention task pgo1variance (pair O1, family F1 office documents); spec: spec_o1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo1variance(BaseTask):
    intermediate_eval_safe = False
    id = "pgo1variance"
    snapshot = "paragui"
    instruction = "I'm Elena Marsh, operations manager at Harbourside Community Health, and I need the Q3 budget-versus-actuals view for tomorrow's operations review. Our workbook ~/Documents/Ops_Budget_2026Q3.xlsx is open in LibreOffice Calc. (1) The CFO's decisions on our virement requests are in the scanned memo ~/Documents/BT-2026-07_budget_transfer.pdf: enter the approved transfers (only those) in the 'Approved transfers' column of the Budget sheet, positive for the receiving and negative for the giving cost centre, so that the 'Revised Q3 budget' column updates. (2) Add a sheet named 'Variance' with one row per cost centre: code, name, revised budget, actual spend, variance (actual minus revised budget) and variance % (variance divided by revised budget). Actual spend is the total of the 'Budget charge' column of the Actuals sheet for that cost centre; the September invoices are still being keyed into Actuals, so use formulas that also pick up rows added later, not typed-in numbers. (3) Use conditional formatting to show the variance % in red for every cost centre that is more than 10% over its revised budget, and put a column chart comparing revised budget and actual per cost centre on the Variance sheet. (4) Add a sheet named 'Notes' with a short paragraph for the meeting that names the cost centre(s) more than 10% over budget and cites the memo reference. Save the workbook in place as .xlsx."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['calc', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_variance(env, "pgo1variance_result")


TASK_CLASS = TaskPgo1variance
