"""paraGUI contention task pgm4newsletter (pair m4, family F2: one Thunderbird); see spec_m4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm4newsletter(BaseTask):
    intermediate_eval_safe = False
    id = "pgm4newsletter"
    snapshot = "paragui"
    instruction = "Please prepare the Fern & Fennel December newsletter in Thunderbird (my shop account hello@fernandfennel.shop). Marco's email \"December newsletter - featured products\" has the promo sheet with the three featured products, their December prices, the product links, which photos to use and the coupon code. Write an HTML email with the subject \"Fern & Fennel - December picks\": a short greeting, then for each product its photo (from ~/Pictures/newsletter/, shown inline in the message, not as an attachment), its name, the December price and a link to its product page, then the coupon code, and at the bottom an unsubscribe link to https://fernandfennel.shop/unsubscribe. Address it to hello@fernandfennel.shop and put every customer who opted in to the newsletter in ~/Documents/customers.csv in Bcc - but leave out anyone who has asked us by email to unsubscribe, and use the new address of anyone who told us their email address changed. Save it as a template (I want to reuse the layout next month) and also save it as a draft, ready to send on 1 December. Don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_newsletter(env, "pgm4newsletter_result")


TASK_CLASS = TaskPgm4newsletter
