from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc11b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc11b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'You are Actor B, the manual and handover analyst in Fault Console. The scanned service manual is at http://127.0.0.1:18211/manual and the built-in shared handover note is at http://127.0.0.1:18211/handover. For the eight queued faults, compare each live fault code and its symptoms with the service manual, then write and save a concise `CODE -> ACTION_NUMBER` conclusion in the handover note for Actor A. When a diagnosis depends on a probe, use the updated panel evidence after Actor A runs it before recording or revising your conclusion. Do not operate the repair panel, choose or apply the final repair, or press Apply; those actions belong to Actor A. The shared probe allowance is three.\n\nThe setup opens one shared Chrome session with three tabs: the panel at http://127.0.0.1:18211/panel, the scanned manual at /manual, and the handover note at /handover. Start from the manual and handover tabs; use the panel only to observe the current fault or a probe result, not to operate it. You share one Ubuntu desktop, mouse, and keyboard with the panel operator. Focus changes, waiting for probe evidence, and updates to the handover are normal. There is no direct chat; the built-in handover is the coordination surface. Re-check the live fault and saved note after a tab or focus change. The physical display is 1920x1080; screenshots may be scaled previews. \n\nUse at most two resets. A third reset ends the run as a failure with a total score of 0.0000. Treat Reset as a costly restart, not an undo.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_game(setup_controller, "CONC-11", open_tabs=False)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_game(env, "CONC-11", "B")
TASK_CLASS = TaskPgconc11b
