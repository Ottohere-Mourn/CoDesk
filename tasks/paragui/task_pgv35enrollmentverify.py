from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v35 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV35Enrollmentverify(BaseTask):
 intermediate_eval_safe=False
 id="pgv35enrollmentverify";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Linden State University, complete the synthetic enrollment verification for FA-803. Record enrollment status, verified document, follow-up due date, and verification reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv35enrollmentverify_result')
TASK_CLASS=TaskV35Enrollmentverify
