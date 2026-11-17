from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v42 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV42Pickupscheduling(BaseTask):
 intermediate_eval_safe=False
 id="pgv42pickupscheduling";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Summit Environmental: Complete the synthetic licensed pickup plan for WASTE-519. Record transporter, pickup window, receiving facility, and manifest number, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv42pickupscheduling_result')
TASK_CLASS=TaskV42Pickupscheduling
