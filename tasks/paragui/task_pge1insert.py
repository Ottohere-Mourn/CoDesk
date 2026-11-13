"""EDIT-MODE1: insert a release status phrase in Writer."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_e1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPge1insert(BaseTask):
    intermediate_eval_safe = False
    id = "pge1insert"; snapshot = "paragui"; source = "paragui"; trajectory = "trajectories/"; related_apps = ["writer"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = """The open Writer file is the final release-review note. On its first line, insert READY and one following space immediately before HOLD-FOR-REVIEW. Do not select or replace the existing HOLD-FOR-REVIEW text: it must remain complete after your insertion. Save the file. Do not change the reviewer code or guard phrase."""
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_insert(env, "pge1insert_result")
TASK_CLASS = TaskPge1insert
