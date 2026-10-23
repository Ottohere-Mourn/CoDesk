"""paraGUI contention task pga3stocktake (pair a3); see spec_a3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga3stocktake(BaseTask):
    intermediate_eval_safe = False
    id = "pga3stocktake"
    snapshot = "paragui"
    instruction = "I run the workshop at Copper Lane Cycles. Last Friday (30 October) we counted bays B and T, and the two count sheets are scanned in ~/Documents/Stock/Stocktake. Please apply the count to our parts stock workbook ~/Documents/Stock/parts_stock.xlsx, which is open in LibreOffice Calc. The sheets were printed with the system quantity at the time and stock has moved since, so don't overwrite On hand with the counted number: correct each item's On hand by its variance (counted minus the printed system qty) and set Last counted to 30/10/2026 for every item on the sheets. Delete the rows of the items marked as discontinued, and add the new items written in at the bottom of the sheets as new rows in SKU order (category as for the other items with that SKU prefix, On hand = the counted quantity). Then add a sheet named 'Variance 2026-11' listing every item with a non-zero variance - SKU, description, system qty, counted, variance (a new item counts as system qty 0). Save the workbook in place, keeping the .xlsx format."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['libreoffice_calc', 'document_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_stocktake(env, "pga3stocktake_result")


TASK_CLASS = TaskPga3stocktake
