from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc20b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc20b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['vlc', 'gedit']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn VLC, review `/home/user/workspace/c20/demo_silent.mp4` with the corrected `/home/user/workspace/c20/demo_silent.srt`. Wait until the subtitle editor shows that all three entries have been corrected and saved. Load/reload the subtitle track in VLC. Pause on the green Phase 2 scene between about 5–7 seconds and take a VLC snapshot, then pause on the orange Phase 3 scene between about 9–11 seconds and take another VLC snapshot. VLC's snapshot folder is `/home/user/workspace/c20/snapshots/`; use Video > Take Snapshot or Shift+S. preserve the provided source where the task requires it; CLI is available for permitted workspace edits and screenshots.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 20, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 20, "B")
TASK_CLASS = TaskPgconc20b
