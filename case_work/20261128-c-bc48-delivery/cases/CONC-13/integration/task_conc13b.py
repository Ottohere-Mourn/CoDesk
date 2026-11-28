from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc13b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc13b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['chrome']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. You may use at most two game resets. A third reset immediately fuses the run and sets the score to 0.0000. Treat reset as a costly restart, not undo; recover from the current visible state whenever practical.\n\nYou are the blue-apron cook chef in Line Kitchen Hard at http://127.0.0.1:18213/. You own collecting prepared items from the shared Pass, cooking items that require heat, plating, and serving only when the complete plate matches the currently visible composite order. Watch the stove heat and collect cooked items promptly to avoid burning. Do not go to the raw bins or chopping board; those belong to the prep chef.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 13, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 13, "B")
TASK_CLASS = TaskPgconc13b
