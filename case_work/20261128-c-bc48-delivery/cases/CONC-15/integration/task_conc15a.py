from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc15a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc15a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ['chrome']
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = 'This is one shared Ubuntu 1920x1080 desktop with one mouse, keyboard, and application session. There is no direct chat between the two operators. Focus changes, blocked actions, dialogs being interrupted, and input landing in the wrong place are normal shared-desktop conditions: re-check the visible state and continue rather than assuming the task is impossible. Screenshots may be scaled previews.  Do not alter evaluator state. You may use at most two game resets. A third reset immediately fuses the run and sets the score to 0.0000. Treat reset as a costly restart, not undo; recover from the current visible state whenever practical.\n\nYou are the Fault Console panel operator. Work through the ten faults shown at http://127.0.0.1:18215/panel. Verify each full fault code and visible symptom. Use the globally shared probe budget (two uses total) only when the panel indicates extra evidence is needed. Read saved CODE -> ACTION_NUMBER recommendations from http://127.0.0.1:18215/handover, then choose and apply the matching repair in the panel. Before every Apply, re-check the current target and supporting evidence. Distinguish I from 1 and O from 0; do not force a downstream MASKED fault before its prerequisite is resolved. Do not write the manual conclusion for the other operator.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_case(setup_controller, 15, "A")
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate(env, 15, "A")
TASK_CLASS = TaskPgconc15a
