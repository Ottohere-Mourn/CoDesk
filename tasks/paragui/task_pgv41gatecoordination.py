from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v41 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV41Gatecoordination(BaseTask):
 intermediate_eval_safe=False
 id="pgv41gatecoordination";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Monarch Air Services: Complete the synthetic gate coordination plan for SSR-782. Record assigned team, gate, boarding time, and coordination reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv41gatecoordination_result')
TASK_CLASS=TaskV41Gatecoordination
