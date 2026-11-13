"""Clip-review safety follow-up: record the four pedestrian/egress hazards."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgv1safety(BaseTask):
    intermediate_eval_safe=False
    id="pgv1safety"; snapshot="paragui"; source="paragui"; trajectory="trajectories/"; related_apps=["chrome"]
    proxy=False; fixed_ip=False; possibility_of_env_change="low"
    instruction="""Review clip NL-448 (Loading Bay 4, Camera B) in Northline Clip Review Desk. Record every condition in the Safety follow-up worklist that needs action: a loaded forklift crossing while a pedestrian is still in the lane; the emergency exit keep-clear hatch blocked by pallets; an employee in the forklift zone without a high-visibility vest; and a forklift reversing blind without a spotter or horn. For each one, navigate to the frame showing it, select Safety follow-up, write a short factual note, and use ?Log observation at visible time?. Cover all four observations; do not add routine or equipment-maintenance items."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None: pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"): return pair.evaluate_safety(env,"pgv1safety_result")
TASK_CLASS=TaskPgv1safety
