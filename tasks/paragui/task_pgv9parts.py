from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v9 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgV9Parts(BaseTask):
 intermediate_eval_safe=False
 id="pgv9parts";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Metro Field Service, reserve the listed part for each of WO-8170, WO-8224, and WO-8318. Enter part number, quantity, reservation reference, and RESERVED status from each order. Save all three.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv9parts_result")
TASK_CLASS=TaskPgV9Parts
