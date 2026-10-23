"""paraGUI contention task pgc5brand (pair C5); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c5 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc5brand(BaseTask):
    intermediate_eval_safe = False
    id = "pgc5brand"
    snapshot = "paragui"
    instruction = 'Our company branding changed. Update ~/Documents/Q3_model_review.pptx so that every slide follows the new brand guide in ~/Documents/brand_guide.txt, then save the presentation in PowerPoint (.pptx) format.'
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['impress']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_brand(env, "pgc5brand_result")


TASK_CLASS = TaskPgc5brand
