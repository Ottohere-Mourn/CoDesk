"""paraGUI contention task pgd4release (pair D4, family F4 software development); see spec_d4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd4release(BaseTask):
    intermediate_eval_safe = False
    id = "pgd4release"
    snapshot = "paragui"
    instruction = "Please prepare release 1.4.0 of our shorebirds package (~/projects/shorebirds, open in VS Code) exactly as described in RELEASING.md. I have already started the new version on Zenodo; the screenshot of the draft (docs/release/zenodo-draft-1.4.0.png) shows the reserved DOI and the publication date to use. The changelog must cover everything merged since v1.3.0, not just the notes already listed under Unreleased. Build the dist archive, then restart the lab's report server (./dev.sh restart) and check in Chrome (http://127.0.0.1:8114) that its footer shows the new version and DOI. Thanks, Femke"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_release(env, "pgd4release_result")


TASK_CLASS = TaskPgd4release
