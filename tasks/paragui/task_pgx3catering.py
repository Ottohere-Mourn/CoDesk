"""paraGUI task pgx3catering (F6 pair x3); see spec_x3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx3catering(BaseTask):
    intermediate_eval_safe = False
    id = "pgx3catering"
    snapshot = "paragui"
    instruction = "Please sort out the catering for our anniversary client evening on 19 November. Use the replies to my invitation in Thunderbird (each guest and plus-one chose a main course and told us about dietary needs; a later email from the same person overrides an earlier one) and our hosts' choices on the event page in our Hub (http://127.0.0.1:8123, username rosa, password Glasshouse15). Martin started the Fennel & Fig order in Hub Purchasing, and his email 'Anniversary evening - arrangements' says what everyone gets: finish that order with the right quantities, charged to the anniversary evening, and submit it. Then put the order's total and PO number into the catering line of ~/Documents/Events/Anniversary_Budget_2026.xlsx and update the total and the remaining budget there. Finally write an email to Dev at Fennel & Fig with the PO number and the guests who have allergies or dietary requirements, by name. Leave it in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_catering(env, "pgx3catering_result")


TASK_CLASS = TaskPgx3catering
