from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v14 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV14Rework(BaseTask):
 intermediate_eval_safe=False
 id="pgv14rework";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Northline Manufacturing quality desk, record rework verification for VALVE-8021. Use its rework slip to enter operation, verification result, inspection station, and verification reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv14rework_result")
TASK_CLASS=TaskV14Rework
