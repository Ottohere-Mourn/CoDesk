from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v19 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV19Housekeeping(BaseTask):
 intermediate_eval_safe=False
 id="pgv19housekeeping";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Harborlight Hotel, complete the room-turnover inspection for stay STAY-7327. Enter room condition, linen and bath check, minibar check, and room release reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv19housekeeping_result')
TASK_CLASS=TaskV19Housekeeping
