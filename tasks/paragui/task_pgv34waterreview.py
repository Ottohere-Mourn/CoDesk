from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v34 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV34Waterreview(BaseTask):
 intermediate_eval_safe=False
 id="pgv34waterreview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At the River County Water Quality Desk, complete the synthetic sample review for WQ-9204. Record its sample classification, laboratory result, disposition, and laboratory reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv34waterreview_result')
TASK_CLASS=TaskV34Waterreview
