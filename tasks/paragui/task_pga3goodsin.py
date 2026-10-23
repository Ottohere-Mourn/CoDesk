"""paraGUI contention task pga3goodsin (pair a3); see spec_a3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga3goodsin(BaseTask):
    intermediate_eval_safe = False
    id = "pga3goodsin"
    snapshot = "paragui"
    instruction = "I run the workshop at Copper Lane Cycles. Three supplier deliveries arrived this week and their delivery notes are scanned in ~/Documents/Stock/Deliveries. Please book them into our parts stock workbook ~/Documents/Stock/parts_stock.xlsx, which is open in LibreOffice Calc: for every item we actually received, add the received quantity to its On hand figure and set its Last received date to the delivery date, and log each booked line on the 'Goods in' sheet (date, supplier, delivery note number, our SKU, quantity). Only book what physically arrived and stayed here - not back-ordered quantities and not anything that went back with the driver - and where a supplier printed the wrong reference, match the item to our SKU by its description. Save the workbook in place, keeping the .xlsx format. Then list everything that is still on back-order (supplier, our SKU, description, quantity still to come) in ~/Documents/Stock/backorders_2026-11.txt."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['libreoffice_calc', 'document_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_goodsin(env, "pga3goodsin_result")


TASK_CLASS = TaskPga3goodsin
