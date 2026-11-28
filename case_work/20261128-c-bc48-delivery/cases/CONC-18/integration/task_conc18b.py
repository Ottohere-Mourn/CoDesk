from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc18b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc18b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nUse the latest values in Calc `/home/user/workspace/c18/gpu_billing.xlsx` to complete `/home/user/workspace/c18/audit_memo.docx` in LibreOffice Writer. Wait until B3 is filled and the totals are calculated. Replace all memo placeholders with: Total GPU Hours = Calc B6; Video-Stream Cost = D3 formatted to one decimal plus `RMB`; Total Monthly Cost = D6 formatted to one decimal plus `RMB`; Budget Status = `OVER_BUDGET` if total exceeds 25000.0 RMB, otherwise `WITHIN_BUDGET`; Variance vs Cap = total minus 25000.0 RMB, to one decimal; Audit Note = `Highest spend is Vision-Pretrain (10000.0 RMB); cap review required.` Do not edit the Calc workbook. Save the memo without `[TBD]` placeholders.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 18, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 18, "B")
TASK_CLASS = TaskPgconc18b
