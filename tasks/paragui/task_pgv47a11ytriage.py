from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v47 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV47A11Ytriage(BaseTask):
 intermediate_eval_safe=False
 id="pgv47a11ytriage";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Triage synthetic accessibility finding AX-417. Record severity, affected component, WCAG criterion, and remediation ticket; save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,"A","pgv47a11ytriage_result")
TASK_CLASS=TaskV47A11Ytriage
