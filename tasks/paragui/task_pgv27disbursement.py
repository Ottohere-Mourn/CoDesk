from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v27 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV27Disbursement(BaseTask):
 intermediate_eval_safe=False
 id="pgv27disbursement";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Riverbend Grants Office, prepare a draft disbursement schedule for grant GR-4418. Enter tranche, proposed date, masked account alias, and draft reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B',"pgv27disbursement_result")
TASK_CLASS=TaskV27Disbursement
