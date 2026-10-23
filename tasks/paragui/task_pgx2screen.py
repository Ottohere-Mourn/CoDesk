"""paraGUI task pgx2screen (F6 pair x2); see spec_x2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx2screen(BaseTask):
    intermediate_eval_safe = False
    id = "pgx2screen"
    snapshot = "paragui"
    instruction = "I'm covering the CV screening for Grace Liu's Data Analyst opening (REQ-031). Her email 'REQ-031 screening - rubric and tracker' in Thunderbird has the scoring rubric and her tracker, and the applications came in by email with the CVs attached (some are scans, and one applicant sent an updated CV). Put every applicant into HireDesk (http://127.0.0.1:8122, username alex, password Fernleaf!Talent) on REQ-031 - some people are already on file from earlier applications, so don't create duplicates - fill in their scorecard and move them to Phone screen or Rejected (with a reason) as the rubric says. Then add them to Grace's tracker, save it as ~/Documents/Recruiting/REQ-031_screening.xlsx and reply to Grace's email with the tracker attached, naming the shortlisted candidates. Leave the reply in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_screen(env, "pgx2screen_result")


TASK_CLASS = TaskPgx2screen
