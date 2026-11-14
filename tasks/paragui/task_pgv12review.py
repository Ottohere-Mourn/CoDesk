from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v12 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV12Review(BaseTask):
 intermediate_eval_safe=False
 id="pgv12review";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Civic Records Office Disclosure & Intake Desk, apply the explicit synthetic review note to PR-508-A, PR-512-B, and PR-519-C. Enter release action, withheld pages (write None when none), redaction basis, and review reference for each document, then save. Do not infer rules beyond the note.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv12review_result")
TASK_CLASS=TaskV12Review
