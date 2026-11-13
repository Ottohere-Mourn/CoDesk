"""Clip-review maintenance triage: record the equipment faults."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgv1maint(BaseTask):
    intermediate_eval_safe=False
    id="pgv1maint"; snapshot="paragui"; source="paragui"; trajectory="trajectories/"; related_apps=["chrome"]
    proxy=False; fixed_ip=False; possibility_of_env_change="low"
    instruction="""Review clip NL-448 (Loading Bay 4, Camera B) in Northline Clip Review Desk. Record the equipment conditions needing maintenance: Conveyor C7's red beacon stays on after reset; the unloaded Dock 4 leveller's fault lamp remains red and it will not return level; Door 4's shutter stops halfway; fluid is pooling below the dock-lift hydraulic hose; and Conveyor C7 is running with its left guard missing. For each one, navigate to its frame, select Maintenance, enter a short factual note naming the equipment/defect, and use ?Log observation at visible time?. Cover all five conditions; do not add pedestrian-safety or routine observations."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None: pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"): return pair.evaluate_maintenance(env,"pgv1maint_result")
TASK_CLASS=TaskPgv1maint
