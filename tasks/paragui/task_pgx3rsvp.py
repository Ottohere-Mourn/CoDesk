"""paraGUI task pgx3rsvp (F6 pair x3); see spec_x3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx3rsvp(BaseTask):
    intermediate_eval_safe = False
    id = "pgx3rsvp"
    snapshot = "paragui"
    instruction = "I'm organising Brightwater Studio's 15th-anniversary client evening on 19 November. The replies to my invitation are in my Thunderbird inbox, and Martin's email 'Anniversary evening - arrangements' has the rules. Please record every reply in the anniversary guest list on our Hub (http://127.0.0.1:8123, username rosa, password Glasshouse15): who is coming or not, the name of their plus-one, and anyone coming in someone else's place - a later email from the same person overrides an earlier one. Move every RSVP email you have dealt with into a new folder 'Anniversary RSVPs' under my account. Then save the door list (every expected guest including plus-ones, with their company - not our own staff) as ~/Documents/Events/Anniversary_door_list.xlsx, and write an email to Clara at The Glasshouse with the final total headcount and the door list attached, copying Martin, and tell Martin in it about anyone who asked to come on a forwarded invitation. Leave the email in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_rsvp(env, "pgx3rsvp_result")


TASK_CLASS = TaskPgx3rsvp
