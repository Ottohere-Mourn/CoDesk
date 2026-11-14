from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v17 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV17Exhibit(BaseTask):
 intermediate_eval_safe=False
 id="pgv17exhibit";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Harbor City Museum Exhibitions Desk, record gallery placement for object OBJ-2306. Enter gallery location, display mount, maximum illumination, and exhibition placement reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv17exhibit_result")
TASK_CLASS=TaskV17Exhibit
