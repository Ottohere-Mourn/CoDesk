"""paraGUI contention task pgd2kelvar (pair D2, family F4 software development); see spec_d2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd2kelvar(BaseTask):
    intermediate_eval_safe = False
    id = "pgd2kelvar"
    snapshot = "paragui"
    instruction = "We have a new metering vendor, Kelvar, whose meters just went live in the Hafenkante district. Their interface specification (a scanned PDF) is docs/vendors/Kelvar_KMF_Interface_v2.1.pdf and their first deliveries are in data/inbox/kelvar/ of our meterflow repo (~/projects/meterflow, open in VS Code; the dashboard runs at http://127.0.0.1:8112, open in Chrome). Following docs/vendors/ONBOARDING.md, write a parser for their KMF files, register it, enable the vendor in our settings (inbox folder 'kelvar', meter prefix as in their meter ids), add unit tests based on the sample deliveries and add Kelvar to the vendor table in the README. scripts/check.sh must pass. Then restart the dashboard (./dev.sh restart) and check in Chrome that Kelvar shows up with plausible numbers. Commit your work, and nothing else, with the message 'Add Kelvar KMF parser'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome', 'pdf_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_kelvar(env, "pgd2kelvar_result")


TASK_CLASS = TaskPgd2kelvar
