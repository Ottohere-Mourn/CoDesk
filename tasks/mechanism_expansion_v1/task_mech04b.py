from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from tasks.mechanism_expansion_v1 import mech04 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskMech04B(BaseTask):
    intermediate_eval_safe=False
    id="mech04b"; snapshot="paragui"; source="paragui"; trajectory="trajectories/"
    related_apps=["libreoffice_calc"]; proxy=False; fixed_ip=False
    possibility_of_env_change="low"
    instruction=pair.TASKS["B"]
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:
        pair.setup(setup_controller,"B")
    def evaluate(self,env:"DesktopEnv"):
        return pair.evaluate(env,"B")
TASK_CLASS=TaskMech04B
