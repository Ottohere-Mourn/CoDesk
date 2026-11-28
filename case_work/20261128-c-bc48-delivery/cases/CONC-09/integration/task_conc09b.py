from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc09b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc09b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "Work as Actor B, the blue-apron cook chef in Line Kitchen at http://127.0.0.1:18209/. Own cooking and service: take prepared items from the central pass, cook and plate them, and serve only when the finished plate matches the currently visible order. Orders appear one at a time, so rely on the live order display. Do not go to the raw ingredient crates, collect raw ingredients such as lettuce, or chop food; those are Actor A's responsibilities.\n\nThis is a shared Ubuntu desktop with one mouse, keyboard, and Chrome session. There is no direct chat. The other actor may change focus, move a chef, occupy a station, or temporarily block a path. Waiting, blocked movement, missed input, an empty pass, and changing station state are normal; re-observe the screen and adapt rather than assuming the task is impossible. The physical display is 1920x1080; screenshots may be scaled previews. \n\nUse at most two resets. A third reset ends the run as a failure with a total score of 0.0000. Treat Reset as a costly restart, not an undo; try to recover from mistakes by checking the current state.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_game(setup_controller, "CONC-09", open_tabs=False)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_game(env, "CONC-09", "B")
TASK_CLASS = TaskPgconc09b
