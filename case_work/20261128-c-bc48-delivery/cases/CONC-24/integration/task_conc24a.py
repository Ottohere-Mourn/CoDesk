from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc24a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc24a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['gimp', 'libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn GIMP, edit `/home/user/workspace/c24/raw_diagram.png`. Scale it from 1000x600 to exactly 600x360. Add clear light-colored text `V2.4 VERIFIED` near the upper middle, fully inside the canvas. Export the result to `/home/user/workspace/c24/exports/release_fig.png`. Do not operate Impress or edit the deck; the other operator owns presentation work.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 24, "A")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 24, "A")
TASK_CLASS = TaskPgconc24a
