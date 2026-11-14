from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v18 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV18Commission(BaseTask):
 intermediate_eval_safe=False
 id="pgv18commission";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Sunfield Solar Cooperative, record the acceptance commissioning tests for PV site PV-614. Enter inverter status, AC output, anti-islanding test result, and commissioning report reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv18commission_result")
TASK_CLASS=TaskV18Commission
