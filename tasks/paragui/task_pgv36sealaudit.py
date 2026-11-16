from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v36 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV36Sealaudit(BaseTask):
 intermediate_eval_safe=False
 id="pgv36sealaudit";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At North Ward Election Services, complete the synthetic equipment seal audit for EPK-019. Record seal condition, scanner units, discrepancy, and certification reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv36sealaudit_result')
TASK_CLASS=TaskV36Sealaudit
