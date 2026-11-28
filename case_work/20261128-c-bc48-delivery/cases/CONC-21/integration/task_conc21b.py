from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc21b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc21b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['gimp']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn GIMP, wait until the shared canvas is 800x400 and visibly brighter than the original. Add a clear light-colored text layer reading exactly `CODESK 2026`, centered slightly above the middle and fully within the canvas. Save the editable project as `/home/user/workspace/c21/banner_work.xcf`, then export the final image as `/home/user/workspace/c21/output/banner_final.png` and confirm the PNG export dialog. Do not resize or adjust background brightness. Keep to text, saving, and export; do not alter the background. Choose a readable light text color and avoid repeating the same color-dialog actions without checking the visible state. If the dialog or canvas state does not respond as expected, pause and re-check before trying a correction, and avoid interrupting an active background adjustment.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 21, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 21, "B")
TASK_CLASS = TaskPgconc21b
