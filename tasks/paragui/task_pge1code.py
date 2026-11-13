"""EDIT-MODE1: change a fixed-width reviewer code using Writer's overwrite toggle."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_e1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPge1code(BaseTask):
    intermediate_eval_safe = False
    id = "pge1code"; snapshot = "paragui"; source = "paragui"; trajectory = "trajectories/"; related_apps = ["writer"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = """In the open Writer release-review note, replace the four-character reviewer code ____ with AB12. Use Writer's Insert/Overwrite toggle (the Insert key) and type AB12 over the four underscores without selecting any text, so the field remains exactly four characters. Save the file. Do not change the release status line or guard phrase."""
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_code(env, "pge1code_result")
TASK_CLASS = TaskPge1code
