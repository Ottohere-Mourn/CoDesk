from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc19b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc19b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['handbrake', 'avidemux', 'vlc']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn the available video editor (prefer HandBrake; setup may use Avidemux or VLC only if the primary application cannot be installed), configure export for MP4, H.264/x264, 15 fps constant frame rate, and save to `/home/user/workspace/c19/clips/clip_final.mp4`. Before encoding, verify the shared interface shows Seconds 2 to 7 and 640x360. Wait if those upstream settings are not ready, but re-check the shared state periodically rather than remaining in long repeated waits. Do not alter the trim range or dimensions. Start the export and wait for it to finish.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 19, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 19, "B")
TASK_CLASS = TaskPgconc19b
