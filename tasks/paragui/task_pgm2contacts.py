"""paraGUI contention task pgm2contacts (pair m2, family F2: one Thunderbird); see spec_m2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm2contacts(BaseTask):
    intermediate_eval_safe = False
    id = "pgm2contacts"
    snapshot = "paragui"
    instruction = "Before going on leave, my chief of staff Grace left me a to-do list for my Thunderbird address book (her email \"Address book clean-up\"). Please do it in my Personal Address Book: merge the duplicate contacts into one card per person (the address they currently email me from is the primary email, their other address the secondary email), delete the card of the person who left, add the new people she lists with name, email, organization, job title and work phone taken from their email signatures or business card, and create the mailing list she describes. When the address book is clean, export it as a CSV file to ~/Documents/HPCH_contacts.csv."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'image_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_contacts(env, "pgm2contacts_result")


TASK_CLASS = TaskPgm2contacts
