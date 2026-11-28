from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc10b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc10b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "You are Actor B, responsible for the blue water character in Grid Fire & Water at http://127.0.0.1:18210/. Handle the blue character's objectives, including its blue gems, blue passage, lever mechanism, and blue exit. Coordinate through the visible game state with the red character so the shared gate and bridge mechanisms can be used. Avoid fire hazards; do not try to control the red character.\n\nThis is one shared Ubuntu desktop, browser, mouse, and keyboard, with no direct chat. The other actor may change focus or move the red character while you act. A closed gate, a temporarily unavailable bridge, a blocked move, or a hazard return is normal game state. Re-observe character positions and mechanism state, then adapt; do not treat ordinary waiting or contention as proof the task is impossible. The physical display is 1920x1080; screenshots may be scaled previews. \n\nUse at most two resets. A third reset ends the run as a failure with a total score of 0.0000. Try to recover from a hazard or missed input before resetting.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_game(setup_controller, "CONC-10", open_tabs=False)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_game(env, "CONC-10", "B")
TASK_CLASS = TaskPgconc10b
