"""paraGUI SHELTER-INTAKE1: safety inspection closure and repair work order."""
from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_s1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgshelterfacilities(BaseTask):
    intermediate_eval_safe=False
    id='pgs1facilities'; snapshot='paragui'; source='paragui'; trajectory='trajectories/'; related_apps=['chrome']
    proxy=False; fixed_ip=False; possibility_of_env_change='low'
    instruction="""I'm Alex Kim, the facilities coordinator on the Harborlight evening shift. The local operations board is open at http://127.0.0.1:8131. Review the SAFE-204 inspection notice. Close room CR-201 because of the documented electrical burning odor, set its usable capacity to zero, and create the required high-priority open repair work order with the instruction to inspect and isolate the west outlet before reopening. Verify that both the closure and work order were saved. Do not alter any household placement or another room."""
    def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None: pair.setup(setup_controller)
    def evaluate(self,env:'DesktopEnv'): return pair.evaluate_facilities(env,'pgs1facilities_result')
TASK_CLASS=TaskPgshelterfacilities
