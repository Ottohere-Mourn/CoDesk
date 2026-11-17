from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v43 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV43Workpackage(BaseTask):
 intermediate_eval_safe=False
 id="pgv43workpackage";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Update the affected synthetic site work package for RFI-731. Record the work zone, affected trade, revised shift, and package reference; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"B","pgv43workpackage_result")
TASK_CLASS=TaskV43Workpackage
