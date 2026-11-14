from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v11 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV11Holds(BaseTask):
 intermediate_eval_safe=False
 id="pgv11holds";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Riverside Public Library Circulation Recovery Desk, prepare the pending holds for COPY-1102, COPY-2088, and COPY-3194. Use each source note to enter hold status, pickup branch, expiry date, and patron notice reference, then save each copy.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv11holds_result")
TASK_CLASS=TaskV11Holds
