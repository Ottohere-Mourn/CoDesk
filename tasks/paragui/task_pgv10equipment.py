from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v10 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgV10Equipment(BaseTask):
 intermediate_eval_safe=False
 id="pgv10equipment";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Northview Care Discharge Transition Desk, confirm home-equipment dispatch for DC-1801, DC-1802, and DC-1803. Enter equipment, delivery window, vendor reference, and CONFIRMED status from each summary. Save all three requests.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv10equipment_result")
TASK_CLASS=TaskPgV10Equipment
