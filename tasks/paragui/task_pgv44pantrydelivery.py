from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v44 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV44Pantrydelivery(BaseTask):
 intermediate_eval_safe=False
 id="pgv44pantrydelivery";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Schedule the synthetic DON-244 food donation for delivery. Record the recipient pantry, crate count, delivery window, and route reference; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"B","pgv44pantrydelivery_result")
TASK_CLASS=TaskV44Pantrydelivery
