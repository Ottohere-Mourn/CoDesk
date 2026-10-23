"""paraGUI contention task pgd1cart (pair D1, family F4 software development); see spec_d1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd1cart(BaseTask):
    intermediate_eval_safe = False
    id = "pgd1cart"
    snapshot = "paragui"
    instruction = "I run the Larder & Co online deli. The shop's code is in ~/projects/larder-shop (open in VS Code) and its dev server is running at http://127.0.0.1:8111 (open in Chrome). Support filed issues/ISSUE-42.md: a customer says her cart total is higher than the sale prices, and her cart only exists in the screenshot attached to the issue. Please find and fix the bug so the cart follows docs/PRICING.md, and add a regression test to tests/test_cart.py that rebuilds exactly her cart (same products and quantities) and asserts the correct total. Make sure the tests pass (python3 -m unittest), restart the dev server (./dev.sh restart) and rebuild her cart in Chrome to check that the shop now shows the right total. Then set the issue's status to fixed, write the corrected total into the issue file, and commit just these changes with the message 'Fix sale discount in cart line totals (#42)'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_cart(env, "pgd1cart_result")


TASK_CLASS = TaskPgd1cart
