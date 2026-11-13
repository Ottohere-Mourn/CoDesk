from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v8 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgV8Permitfees(BaseTask):
 intermediate_eval_safe=False
 id="pgv8permitfees";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In the Riverton Permit Desk, post the cashier receipts for ROW-2101, ROW-2102, and ROW-2103. Enter receipt number, fee amount, posted date, and POSTED status. Save and verify all three receipts.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv8permitfees_result")
TASK_CLASS=TaskPgV8Permitfees
