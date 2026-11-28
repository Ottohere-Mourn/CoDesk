from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc09a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc09a"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "Work as Actor A, the red-apron prep chef in Line Kitchen at http://127.0.0.1:18209/. Own raw-ingredient preparation: use the currently visible order to determine what is needed, collect those ingredients, prepare them at the board, and make the prepared items available at the central pass. Do not take over cooking, plating, or serving; those are Actor B's responsibilities. Orders appear one at a time, so work from the live order display rather than guessing future orders.\n\nThis is a shared Ubuntu desktop with one mouse, keyboard, and Chrome session. There is no direct chat. The other actor may change focus, move a chef, occupy a station, or temporarily block a path. Waiting, blocked movement, missed input, and changing station state are normal; re-observe the screen and adapt rather than assuming the task is impossible. The physical display is 1920x1080; screenshots may be scaled previews. \n\nUse at most two resets. A third reset ends the run as a failure with a total score of 0.0000. Treat Reset as a costly restart, not an undo; try to recover from mistakes by checking the current state.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_game(setup_controller, "CONC-09", open_tabs=True)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_game(env, "CONC-09", "A")
TASK_CLASS = TaskPgconc09a
