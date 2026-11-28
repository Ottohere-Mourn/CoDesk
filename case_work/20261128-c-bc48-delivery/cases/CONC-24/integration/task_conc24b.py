from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc24b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc24b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['gimp', 'libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn LibreOffice Impress, edit `/home/user/workspace/c24/release_deck.pptx`. On slide 1 replace `[STATUS_TBD]` with `Release Ready`. On slide 2 insert `/home/user/workspace/c24/exports/release_fig.png` (not the raw source), once the other operator has exported it. Set the caption to `Architecture Snapshot - V2.4 VERIFIED` or equivalent wording that includes both `Architecture Snapshot` and the exact version label. Save the deck. Do not edit the GIMP image.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 24, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 24, "B")
TASK_CLASS = TaskPgconc24b
