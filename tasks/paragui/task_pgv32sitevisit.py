from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v32 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV32Sitevisit(BaseTask):
 intermediate_eval_safe=False
 id="pgv32sitevisit";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Northshore Energy Cooperative, schedule the site revisit for MTR-1472. Enter the assigned technician, visit date, arrival window, and work order reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv32sitevisit_result')
TASK_CLASS=TaskV32Sitevisit
