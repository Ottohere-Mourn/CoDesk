"""Task wrapper for MECH-03 Calc actor."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from tasks.mechanism_expansion_v1 import mech03 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskMech03A(BaseTask):
 intermediate_eval_safe=False
 id="mech03a";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["libreoffice_calc","libreoffice_writer"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction=pair.TASKS["A"]
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller,"A")
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"A")
TASK_CLASS=TaskMech03A
