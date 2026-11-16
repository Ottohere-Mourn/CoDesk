from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v32 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV32Meterreview(BaseTask):
 intermediate_eval_safe=False
 id="pgv32meterreview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Northshore Energy Cooperative, investigate synthetic meter discrepancy MTR-1472. Enter the finding, verified reading, account action, and review reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv32meterreview_result')
TASK_CLASS=TaskV32Meterreview
