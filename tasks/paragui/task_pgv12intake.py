from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v12 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV12Intake(BaseTask):
 intermediate_eval_safe=False
 id="pgv12intake";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Civic Records Office Disclosure & Intake Desk, register PR-508-A, PR-512-B, and PR-519-C from each intake slip. Enter source office, received date, document type, and custody reference for every document, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv12intake_result")
TASK_CLASS=TaskV12Intake
