"""paraGUI task pga5prices (pair a5); see spec_a5.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a5 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga5prices(BaseTask):
    intermediate_eval_safe = False
    id = "pga5prices"
    snapshot = "paragui"
    instruction = "I run the online shop of Fenwick & Bloom Home & Garden. Our tools supplier Greenleaf has sent a price-change letter; the scan is ~/Documents/Suppliers/Greenleaf_price_change_Nov2026.pdf. Please put it into our back office ShopAdmin (http://127.0.0.1:8135, username jess, password Bloom-Admin-26): for every product the letter covers, enter the new cost price and recalculate the regular retail price exactly as the Pricing policy page in ShopAdmin says, and follow the policy for products that are on promotion and for items Greenleaf no longer supplies. Then save a summary as ~/Documents/Pricing/price_update_greenleaf.csv with the columns SKU, old cost, new cost, old retail, new retail - one row per product whose cost price changed, using our ShopAdmin SKUs."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'pdf_viewer', 'text_editor']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_prices(env, "pga5prices_result")


TASK_CLASS = TaskPga5prices
