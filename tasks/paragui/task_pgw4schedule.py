"""paraGUI contention task pgw4schedule (pair W4); see spec_w4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_w4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgw4schedule(BaseTask):
    intermediate_eval_safe = False
    id = "pgw4schedule"
    snapshot = "paragui"
    instruction = 'I\'m Jordan Ellis, talent acquisition lead at Quillon Health. Our applicant tracking system, Quillon Talent, is at http://127.0.0.1:8104 (open in Chrome; log in as jordan.ellis, password Quillon-Talent-26). Please schedule the hiring manager interviews for the five shortlisted Staff Data Engineer candidates (REQ-221): Nadia Rahman, Owen Fischer, Keiko Sato, Luis Ortega and Grace Mwangi. Each one is a 45-minute "Hiring manager interview" with Priya Raman next week (26-30 Oct 2026). Book them in the Quillon Talent calendar inside Priya\'s interview availability, respecting each candidate\'s availability note on their profile and without double-booking Priya, and move each candidate to the stage "HM interview". Then create my weekly recruiting summary ~/Documents/recruiting_weekly_wk43.xlsx with two sheets: "Applications", with the number of applications received from 19 to 23 Oct 2026 per requisition (one row per requisition code) and per source (one column per source), as shown on the Reports page; and "HM interviews", listing the five interviews (candidate, date, start time, interviewer).'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['chrome', 'libreoffice_calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_schedule(env, "pgw4schedule_result")


TASK_CLASS = TaskPgw4schedule
