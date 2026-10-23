"""paraGUI task pga5sale (pair a5); see spec_a5.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a5 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga5sale(BaseTask):
    intermediate_eval_safe = False
    id = "pga5sale"
    snapshot = "paragui"
    instruction = "Black Friday is coming up at Fenwick & Bloom Home & Garden. Our designer's flyer proof with my handwritten corrections is scanned at ~/Documents/Marketing/BF_flyer_proof_marked.pdf. Please set up the sale in our back office ShopAdmin (http://127.0.0.1:8135, username jess, password Bloom-Admin-26): every product on the corrected flyer gets the discount shown for it, with the sale price, sale dates and promotion label entered as the Pricing policy page in ShopAdmin describes. Then make the price list for the printer: ~/Documents/Marketing/black_friday_prices.csv with the columns SKU, product, was, now (the regular retail price and the Black Friday sale price), one row per product in the Black Friday sale."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'pdf_viewer', 'text_editor']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_sale(env, "pga5sale_result")


TASK_CLASS = TaskPga5sale
