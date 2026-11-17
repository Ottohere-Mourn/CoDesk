from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v46 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV46Disputereview(BaseTask):
 intermediate_eval_safe=False
 id="pgv46disputereview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Review the synthetic duplicate ATM withdrawal dispute DIS-882. Record the review decision, transaction reference, dispute amount, and review reference; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"A","pgv46disputereview_result")
TASK_CLASS=TaskV46Disputereview
