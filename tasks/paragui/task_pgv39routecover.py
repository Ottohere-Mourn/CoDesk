from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v39 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV39Routecover(BaseTask):
 intermediate_eval_safe=False
 id="pgv39routecover";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Tidewater Regional Transit: Complete the synthetic Route 12 cover plan for BUS-208. Record cover status, affected route, replacement vehicle, and cover shift, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv39routecover_result')
TASK_CLASS=TaskV39Routecover
