from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v14 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV14Disposition(BaseTask):
 intermediate_eval_safe=False
 id="pgv14disposition";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Northline Manufacturing quality desk, record the nonconformance disposition for VALVE-8021. Use its NCR note to enter severity, disposition, affected units, and NCR reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv14disposition_result")
TASK_CLASS=TaskV14Disposition
