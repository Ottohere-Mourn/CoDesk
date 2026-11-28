from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc22b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc22b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['inkscape', 'libreoffice']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. This office/software task has no reset limit or reset penalty.\n\nIn Inkscape (or the LibreOffice Draw fallback, if that is what setup opened), edit `/home/user/workspace/c22/arch_diagram.svg`. Wait until the middle rectangle is aligned with its two neighbors and green. Replace the three placeholder labels with `INGEST`, `ROUTER-V2`, and `STORAGE`. Save the SVG, then export the page at 800x400 to `/home/user/workspace/c22/output/arch_final.png`. Do not move rectangles or change their fills.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 22, "B")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 22, "B")
TASK_CLASS = TaskPgconc22b
