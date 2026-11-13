"""Reconcile six signed mileage reimbursement slips."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v3 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv3mileage(BaseTask):
 intermediate_eval_safe=False
 id="pgv3mileage";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""In the Community Pantry Desk, process the six signed mileage slips for Saturday 21 November 2026. For each listed volunteer, calculate reimbursable amount as miles times $0.67, rounded to the nearest cent. Enter the amount, choose APPROVED when the total is $25.00 or less and REVIEW when it is above $25.00, and enter the note exactly: Verified from signed slip. Save all six:
V-214 Ada Bell; V-238 Ben Carter; V-251 Chi Diaz; V-267 Devon Evans; V-299 Eli Flores; V-304 Faye Grant.
The submitted miles are shown beside each volunteer in the desk. Do not change shift assignments or shift windows."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_mileage(env,"pgv3mileage_result")
TASK_CLASS=TaskPgv3mileage
