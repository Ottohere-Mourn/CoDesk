from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v39 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV39Vehicleinspection(BaseTask):
 intermediate_eval_safe=False
 id="pgv39vehicleinspection";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Tidewater Regional Transit: Complete the synthetic vehicle safety inspection for BUS-208. Record inspection result, observed defect, work order, and inspection reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv39vehicleinspection_result')
TASK_CLASS=TaskV39Vehicleinspection
