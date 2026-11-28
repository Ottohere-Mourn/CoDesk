from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc21a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc21a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['gimp']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn GIMP, use `/home/user/workspace/c21/raw_banner.png` as the source. Scale the image to exactly 800x400 pixels using Image > Scale Image. Select the background image layer and raise its brightness by about +35 to +50 without washing the image out. Do not add text, save the XCF, or export the PNG; that work belongs to the other operator. Stay within the background resize/brightness role: do not open or manipulate the Text Tool or text-color dialogs, and avoid interrupting active text work. After your background adjustments are complete, leave the shared canvas for the other operator.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 21, "A")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 21, "A")
TASK_CLASS = TaskPgconc21a
