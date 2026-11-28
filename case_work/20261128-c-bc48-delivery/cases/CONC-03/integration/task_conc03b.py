from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc03 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc03b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc03b"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["libreoffice", "terminal"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = 'Complete the three-page safety briefing in the already-open LibreOffice Impress file /home/user/workspace/out_b/Safety_Brief.pptx. You may use the GUI or local command-line tools.\n\nUse /home/user/workspace/in_b/safety_spec.txt and the three supplied icons to replace each placeholder title, footer ID, and draft body with the specified safety guidance. Insert icon_helmet.png on page 1, icon_hazard.png on page 2, and icon_exit.png on page 3. Keep every icon fully inside the slide and clear of the title, guidance, and footer. Save the presentation in place and export a three-page PDF to /home/user/workspace/out_b/Safety_Brief.pdf. Reopen or render both outputs to verify the slide order and layout.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, open_chrome=False)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_b(env)


TASK_CLASS = TaskPgconc03b
