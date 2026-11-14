from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v15 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV15Badge(BaseTask):
 intermediate_eval_safe=False
 id="pgv15badge";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Building Operations Visitor Access Desk, provision temporary badge for VIS-7304. Use its approved badge form to enter access zone, valid-until date in YYYY-MM-DD format, sponsor team, and badge reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv15badge_result")
TASK_CLASS=TaskV15Badge
