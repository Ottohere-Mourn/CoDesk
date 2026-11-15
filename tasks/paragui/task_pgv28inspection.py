from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v28 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV28Inspection(BaseTask):
 intermediate_eval_safe=False
 id="pgv28inspection";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At North County Community Sports League, complete the field readiness inspection for fixture MCH-8301. Enter the playing surface status, inspection finding, goal/equipment check, and inspection reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv28inspection_result')
TASK_CLASS=TaskV28Inspection
