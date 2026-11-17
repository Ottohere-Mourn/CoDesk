from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v45 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV45Shuttlestaging(BaseTask):
 intermediate_eval_safe=False
 id="pgv45shuttlestaging";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Stage the shuttle for synthetic heat-response case HEAT-305. Record the assigned vehicle, route, pickup window, and dispatch reference; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"B","pgv45shuttlestaging_result")
TASK_CLASS=TaskV45Shuttlestaging
