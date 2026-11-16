from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v33 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV33Intaketriage(BaseTask):
 intermediate_eval_safe=False
 id="pgv33intaketriage";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Great Lakes Wildlife Rescue, complete the synthetic intake triage for WILD-3381. Enter the species group, condition, triage disposition, and assessment reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv33intaketriage_result')
TASK_CLASS=TaskV33Intaketriage
