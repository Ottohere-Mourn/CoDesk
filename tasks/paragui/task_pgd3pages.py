"""paraGUI contention task pgd3pages (pair D3, family F4 software development); see spec_d3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd3pages(BaseTask):
    intermediate_eval_safe = False
    id = "pgd3pages"
    snapshot = "paragui"
    instruction = "Our practice manager Ilka has sent the texts for three new pages of the Kestrel Physio website: ~/Documents/Website_update_Oct2026.docx. The site's source is in ~/projects/kestrel-site (open in VS Code) and its live preview runs at http://127.0.0.1:8113 (open in Chrome; it rebuilds automatically when files change). Please add the Treatments, Team and Prices pages as described in her document (as Markdown pages in content/, with the price list as a proper table), change the navigation in templates/base.html to the order she asks for, and fix every broken link that tools/linkcheck.py reports for the preview. Check the pages in Chrome, then commit your changes, and nothing else, with the message 'Add treatments, team and prices pages'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome', 'libreoffice_writer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_pages(env, "pgd3pages_result")


TASK_CLASS = TaskPgd3pages
