from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from tasks.mechanism_expansion_v1 import undo_family as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
CASE_ID="mech07"
ROLE="A"
class TaskMECH07A(BaseTask):
    intermediate_eval_safe=False
    id=f"{CASE_ID}{ROLE.lower()}"; snapshot="paragui"; source="paragui"; trajectory="trajectories/"
    related_apps=["libreoffice_calc"]; proxy=False; fixed_ip=False
    possibility_of_env_change="low"
    instruction=pair.TASKS[CASE_ID][ROLE]
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:
        pair.setup(setup_controller,CASE_ID,ROLE)
    def evaluate(self,env:"DesktopEnv"):
        return pair.evaluate(env,CASE_ID,ROLE)
TASK_CLASS=TaskMECH07A
