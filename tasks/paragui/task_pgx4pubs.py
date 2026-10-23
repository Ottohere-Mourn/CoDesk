"""paraGUI task pgx4pubs (F6 pair x4); see spec_x4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_x4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgx4pubs(BaseTask):
    intermediate_eval_safe = False
    id = "pgx4pubs"
    snapshot = "paragui"
    instruction = "Elena wants our publication lists brought up to date - see her email 'Website publications update' in Thunderbird. Using the acceptance emails, camera-ready PDFs and arXiv notice in the mailbox, add or update every new paper of both groups in LabDesk's Publications (http://127.0.0.1:8124, username jross, password Northbridge#26) with the exact title, authors in order, venue, year and arXiv id; add the Marsh Lab papers to the website repo ~/projects/marsh-lab-website (_bibliography/papers.bib, following its README) and commit; then leave an announcement draft to ml-groups@lists.northbridge.ac.uk listing the new papers. Nothing that was rejected should appear anywhere. Leave the announcement in Drafts - don't send it."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'chrome', 'vs_code', 'terminal']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_pubs(env, "pgx4pubs_result")


TASK_CLASS = TaskPgx4pubs
