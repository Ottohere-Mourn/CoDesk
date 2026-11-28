from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc18a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc18a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn LibreOffice Calc, edit only `/home/user/workspace/c18/gpu_billing.xlsx`, sheet `Billing`. Set B3 to 420 and correct C4 to 18.5. Enter formulas D2:D5 as `=B2*C2` down the rows, then B6=`=SUM(B2:B5)` and D6=`=SUM(D2:D5)`. Do not edit the Writer memo; it belongs to the other operator. Save the workbook and verify the formulas and totals.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 18, "A")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 18, "A")
TASK_CLASS = TaskPgconc18a
