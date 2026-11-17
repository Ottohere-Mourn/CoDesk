from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v42 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV42Manifestreview(BaseTask):
 intermediate_eval_safe=False
 id="pgv42manifestreview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='Summit Environmental: Complete the synthetic waste manifest review for WASTE-519. Record waste profile, UN identification, container count, and generator sign-off, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv42manifestreview_result')
TASK_CLASS=TaskV42Manifestreview
