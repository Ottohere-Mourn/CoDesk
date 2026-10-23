"""paraGUI task pga2requests (RED pair a2); see spec_a2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_a2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPga2requests(BaseTask):
    intermediate_eval_safe = False
    id = "pga2requests"
    snapshot = "paragui"
    instruction = "I'm Ines Varga, principal at Varga & Hale Architects. Several people have emailed me asking for a meeting next week (23-27 November 2026). Please deal with all of them in Thunderbird the way my studio manager Ruth describes in her handover email 'Your calendar - how I do it (handover)': book each meeting in my Home calendar at the time they asked for if that time is free, otherwise at the alternative they offered, with the meeting place as the location and the people named in the request as attendees (use their email addresses, but don't send any invitations). Watch out for follow-up emails that change a request. Whenever a meeting could not go at their first choice, reply to their email telling them the day and time I've booked, and leave those replies in Drafts - don't send them."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'image_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_requests(env, "pga2requests_result")


TASK_CLASS = TaskPga2requests
