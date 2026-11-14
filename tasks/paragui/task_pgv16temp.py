from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v16 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV16Temp(BaseTask):
 intermediate_eval_safe=False
 id="pgv16temp";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Lakeside Dining Food Safety Desk, record cooler temperature follow-up for CHILL-271. Enter observed temperature, corrective action, recheck temperature, and temperature log reference in the Temperature & corrective action form, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv16temp_result")
TASK_CLASS=TaskV16Temp
