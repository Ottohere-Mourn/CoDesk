from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v7 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgV7Labcustody(BaseTask):
 intermediate_eval_safe=False
 id="pgv7labcustody";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In the Cedar County Water Lab Accession & Bench Review, enter source, received time, cooler temperature, chain-of-custody reference, and intake status from the custody sheet for WQ-611, WQ-612, and WQ-613. Preserve HOLD for the warm sample. Save and verify all three records.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv7labcustody_result")
TASK_CLASS=TaskPgV7Labcustody
