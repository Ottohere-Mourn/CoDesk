from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v15 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV15Induction(BaseTask):
 intermediate_eval_safe=False
 id="pgv15induction";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Building Operations Visitor Access Desk, log site induction for VIS-7304. Use its induction form to enter induction status, escort requirement, induction date in YYYY-MM-DD format, and induction reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv15induction_result")
TASK_CLASS=TaskV15Induction
