from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v46 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV46Cardsupport(BaseTask):
 intermediate_eval_safe=False
 id="pgv46cardsupport";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Complete the synthetic card-support action for DIS-882. Record the card action, replacement card last four, delivery method, and member-service reference; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"B","pgv46cardsupport_result")
TASK_CLASS=TaskV46Cardsupport
