from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v18 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV18Utility(BaseTask):
 intermediate_eval_safe=False
 id="pgv18utility";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Sunfield Solar Cooperative, complete the utility authorization handover for PV site PV-614. Enter utility status, export limit, monitoring owner, and permission-to-operate reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv18utility_result")
TASK_CLASS=TaskV18Utility
