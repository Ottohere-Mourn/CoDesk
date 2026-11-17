from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v44 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV44Donationintake(BaseTask):
 intermediate_eval_safe=False
 id="pgv44donationintake";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Complete the synthetic food-rescue intake for donation DON-244. Record the screening disposition, receiving temperature, use-by date, and donor lot; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"A","pgv44donationintake_result")
TASK_CLASS=TaskV44Donationintake
