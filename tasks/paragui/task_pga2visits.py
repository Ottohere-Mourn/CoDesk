"""paraGUI task pga2visits (RED pair a2); see spec_a2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga2visits(BaseTask):
    intermediate_eval_safe = False
    id = "pga2visits"
    snapshot = "paragui"
    instruction = "I'm Ines Varga, principal at Varga & Hale Architects. Building control has emailed me next week's site inspection appointments (a scanned schedule attached to their email in Thunderbird). Please put every inspection I have to attend into my Home calendar as one entry per site that blocks the whole trip, from leaving the studio to getting back - the travel times are in Marco's email 'Design reviews + site visits next week'. Marco's email also asks for three internal design reviews: book each as a one-hour entry called 'Design review - <project>' at the earliest time that is still free in my calendar, Tuesday to Thursday between 10:00 and 17:00 and starting on the hour or half hour, in the order he lists them. Never double-book me. Then write a new email to the studio team (team@vargahale.co.uk) with the subject 'Design reviews next week' listing the day and time of each review, and leave it in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'pdf_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_visits(env, "pga2visits_result")


TASK_CLASS = TaskPga2visits
