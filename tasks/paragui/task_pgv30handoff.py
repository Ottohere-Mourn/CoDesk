from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v30 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV30Handoff(BaseTask):
 intermediate_eval_safe=False
 id="pgv30handoff";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Brightpath SaaS, complete the onboarding handoff review for synthetic customer ONB-6194. Enter readiness, workspace alias, customer point of contact, and handoff checklist reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv30handoff_result')
TASK_CLASS=TaskV30Handoff
