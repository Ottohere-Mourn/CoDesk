from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v21 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV21Pickup(BaseTask):
 intermediate_eval_safe=False
 id="pgv21pickup";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Maple Grove Veterinary, complete the administrative pickup and follow-up record for clinic visit PET-0427. Enter pickup status, pickup window, owner contact note, and follow-up reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv21pickup_result')
TASK_CLASS=TaskV21Pickup
