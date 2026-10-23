"""paraGUI contention task pgc5results (pair C5); see paraGUI docs/CONTENTION_TASKS_DESIGN.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_c5 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgc5results(BaseTask):
    intermediate_eval_safe = False
    id = "pgc5results"
    snapshot = "paragui"
    instruction = "Please finish ~/Documents/Q3_model_review.pptx for Monday: add three slides at the end based on ~/Documents/results.xlsx - a 'Results' slide with a table of every model's Accuracy and F1, an 'Accuracy comparison' slide with a bar chart of the accuracy per model, and a 'Conclusions' slide with at least two bullet points that name the best model. Save the presentation in PowerPoint (.pptx) format."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['impress', 'calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_results(env, "pgc5results_result")


TASK_CLASS = TaskPgc5results
