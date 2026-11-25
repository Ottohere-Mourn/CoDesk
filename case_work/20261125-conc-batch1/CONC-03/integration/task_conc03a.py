from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc03 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc03a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc03a"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["chrome", "terminal"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = """Review all three pending claims in the already-open ProcureHub Expense Approval Queue at http://127.0.0.1:18085. You may use the GUI or local command-line tools.

The receipt PNGs are in /home/user/workspace/in_a/receipts/. Compare each image's printed AMOUNT PAID and approval seal with the amount declared in the queue. Attach the matching image to its claim before submitting a decision. Approve EXP-401 and EXP-403. Reject EXP-402 with reason code ERR_AMOUNT_MISMATCH because the receipt total differs from the submitted amount. If a receipt lacks the VERIFIED seal, reject it with ERR_MISSING_STAMP.

The row action menu closes when Chrome loses focus. Reopen it as needed after using the native file chooser. When all three decisions are recorded, export the summary to /home/user/workspace/out_a/approval_summary.csv. Verify the CSV header is claim_id,status,reason_code,uploaded_filename and confirm all three rows are present."""

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, open_chrome=True)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_a(env)


TASK_CLASS = TaskPgconc03a
