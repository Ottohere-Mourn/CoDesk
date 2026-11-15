from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v23 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV23Repairdispatch(BaseTask):
 intermediate_eval_safe=False
 id="pgv23repairdispatch";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Redleaf Mutual, coordinate a repair visit for claim CLM-5286. Enter contractor, arrival window, property access note, and repair work order reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv23repairdispatch_result")
TASK_CLASS=TaskV23Repairdispatch
