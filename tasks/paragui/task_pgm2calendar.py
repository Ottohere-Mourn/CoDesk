"""paraGUI contention task pgm2calendar (pair m2, family F2: one Thunderbird); see spec_m2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm2calendar(BaseTask):
    intermediate_eval_safe = False
    id = "pgm2calendar"
    snapshot = "paragui"
    instruction = "My chief of staff Grace is on leave, so you are handling my calendar now. Several people emailed me meeting requests for the week of 16 November 2026 - please put all of them into my calendar in Thunderbird (the Home calendar), following Grace's handover email \"How I handle your calendar (handover)\" in my inbox: the right date, start and end time, the room or video link as the location, and everyone named in the request as attendees (use the email addresses given in the requests). If someone does not get their first-choice slot, reply to their request telling them the time you booked - save those replies as drafts, don't send them, and don't send any invitations."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'image_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_calendar(env, "pgm2calendar_result")


TASK_CLASS = TaskPgm2calendar
