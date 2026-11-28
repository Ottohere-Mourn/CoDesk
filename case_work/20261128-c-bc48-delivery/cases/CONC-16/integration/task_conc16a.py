from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc16a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc16a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nYou are the source-data entry and correction operator for `/home/user/workspace/c16/experiment_metrics.xlsx`, sheet `Metrics`, open in LibreOffice Calc. In the raw data area A2:E6 only: correct Model-B to C3=124.0 and D3=78.5; fill row 4 with `Model-C | 32 | 95.0 | 94.0 | 16.0`, row 5 with `Model-D | 32 | 130.0 | 76.0 | 20.0`, and row 6 with `Model-E | 64 | 88.0 | 109.5 | 24.0`. Do not edit column F or summary rows 7–9; those belong to the other operator. Verify the raw rows and save the workbook.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 16, "A")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 16, "A")
TASK_CLASS = TaskPgconc16a
