from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc11a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc11a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "You are Actor A, the panel operator in Fault Console. The panel is at http://127.0.0.1:18211/panel. Resolve the eight queued faults by checking each live fault code and its symptoms, using a diagnostic probe when the evidence calls for one, and consulting the saved built-in handover note at http://127.0.0.1:18211/handover before applying a repair. Match the note to the currently selected fault and verify the evidence before choosing an action: a wrong repair permanently locks that fault. You own the final repair and Apply actions; Actor B's role is diagnosis and handover, not applying repairs. The shared probe allowance is three.\n\nThe setup opens one shared Chrome session with three tabs: the panel at /panel, the scanned manual at /manual, and the handover note at /handover, all on port 18211. You share one Ubuntu desktop, mouse, and keyboard with the manual operator. Focus changes, waiting for evidence, and updates to the handover are normal. There is no direct chat; use the visible panel state and built-in handover. Re-check the selected fault and saved note after a tab or focus change. The physical display is 1920x1080; screenshots may be scaled previews. \n\nUse at most two resets. A third reset ends the run as a failure with a total score of 0.0000. Treat Reset as a costly restart, not an undo.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_game(setup_controller, "CONC-11", open_tabs=True)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_game(env, "CONC-11", "A")
TASK_CLASS = TaskPgconc11a
