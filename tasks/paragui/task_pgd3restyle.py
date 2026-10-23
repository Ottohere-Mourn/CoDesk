"""paraGUI contention task pgd3restyle (pair D3, family F4 software development); see spec_d3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd3restyle(BaseTask):
    intermediate_eval_safe = False
    id = "pgd3restyle"
    snapshot = "paragui"
    instruction = "I run the Kestrel Physio practice. Our website's source is in ~/projects/kestrel-site (open in VS Code) and its live preview runs at http://127.0.0.1:8113 (open in Chrome; it rebuilds automatically when files change). Our designer has handed over the 2026 design: the mockup docs/design/landing-2026-mockup.png and the style guide page docs/design/styleguide-2026-p7.pdf. Please restyle the site accordingly: put the style guide's colours, type sizes and spacing into the design tokens in static/css/tokens.css, change the landing page (templates/home.html) to match the mockup's texts, button and cards, and add the phone button shown in the mockup to the header of every page. Leave the navigation items as they are. Check the result in the preview in Chrome, then commit your changes, and nothing else, with the message 'Restyle landing page to the 2026 design'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome', 'pdf_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_restyle(env, "pgd3restyle_result")


TASK_CLASS = TaskPgd3restyle
