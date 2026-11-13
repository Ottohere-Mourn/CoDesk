from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v8 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgV8Permitreview(BaseTask):
 intermediate_eval_safe=False
 id="pgv8permitreview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In the Riverton Permit Desk, review ROW-2101, ROW-2102, and ROW-2103 against each application summary. Record the review status, next review desk, and due date exactly as shown. Save all three applications.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv8permitreview_result")
TASK_CLASS=TaskPgV8Permitreview
