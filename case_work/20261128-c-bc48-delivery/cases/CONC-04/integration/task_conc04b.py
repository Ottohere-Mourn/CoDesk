from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc04 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc04b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc04b"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["chrome", "terminal"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = 'Complete the MetricAnnotator anomaly review at http://127.0.0.1:18092. Four time-series charts, chart_1 through chart_4, are available. You may use the GUI or local command-line tools.\n\nFor each chart, draw exactly two tight rectangles around its visible anomalous intervals. Select each rectangle and classify it with the keyboard: 1 = SPIKE, 2 = DROP, 3 = FLATLINE. If you need to remove a rectangle, select it and use Delete or Backspace. Review all four charts and their classifications before using Submit all charts and export PNGs.\n\nSave the combined labels to /home/user/workspace/out_b/anomaly_labels.json and the four annotated chart images to /home/user/workspace/out_b/chart_1.png through /home/user/workspace/out_b/chart_4.png. Verify that each chart contains exactly two visibly labeled boxes and that no chart is obstructed before finishing.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, "b")

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_b(env)


TASK_CLASS = TaskPgconc04b
