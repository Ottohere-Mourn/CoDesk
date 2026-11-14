from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v11 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV11Returns(BaseTask):
 intermediate_eval_safe=False
 id="pgv11returns";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Riverside Public Library Circulation Recovery Desk, process returned copies COPY-1102, COPY-2088, and COPY-3194. For each, enter condition, next route, exact shelf location, and return receipt reference from its return slip, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv11returns_result")
TASK_CLASS=TaskV11Returns
