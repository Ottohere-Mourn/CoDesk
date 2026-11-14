from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v13 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV13Access(BaseTask):
 intermediate_eval_safe=False
 id="pgv13access";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Research Data Repository, apply the access and retention review to DS-4102. Use its governance note to enter access tier, release date as YYYY-MM-DD, retention class, and governance review reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv13access_result")
TASK_CLASS=TaskV13Access
