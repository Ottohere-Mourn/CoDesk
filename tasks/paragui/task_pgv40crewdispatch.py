from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v40 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV40Crewdispatch(BaseTask):
 intermediate_eval_safe=False
 id="pgv40crewdispatch";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='River County Parks: Complete the synthetic parks crew work order for TREE-044. Record assigned crew, equipment, work window, and dispatch reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv40crewdispatch_result')
TASK_CLASS=TaskV40Crewdispatch
