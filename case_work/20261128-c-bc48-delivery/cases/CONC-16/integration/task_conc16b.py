from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc16b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc16b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nYou are the formula and summary operator for `/home/user/workspace/c16/experiment_metrics.xlsx`, sheet `Metrics`, open in LibreOffice Calc. Use formulas only: fill F2:F6 with `=D2/E2` through `=D6/E6`; set C7/D7 to `=SUM(C2:C6)` / `=SUM(D2:D6)`; set C8/D8/F8 to `=AVERAGE(C2:C6)` / `=AVERAGE(D2:D6)` / `=AVERAGE(F2:F6)`; set D9 to `=MAX(D2:D6)` and F9 to `=IF(D8>=80,"PASS","REVIEW")`. Do not modify A2:E6 or hard-code formula results. Check for formula errors and save.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 16, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 16, "B")
TASK_CLASS = TaskPgconc16b
