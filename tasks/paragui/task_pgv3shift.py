"""Assign six volunteers to Saturday food-pantry shifts."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v3 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv3shift(BaseTask):
 intermediate_eval_safe=False
 id="pgv3shift";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""In the Community Pantry Desk, complete the Saturday 21 November 2026 shift roster. Record and save each of these six assignments in the Shift roster area:
- V-214 Ada Bell: Check-in, 08:00-10:00, CONFIRMED
- V-238 Ben Carter: Produce, 08:00-11:00, CONFIRMED
- V-251 Chi Diaz: Bagging, 09:00-12:00, CONFIRMED
- V-267 Devon Evans: Check-in, 10:00-12:00, CONFIRMED
- V-299 Eli Flores: Driver, 07:30-11:30, CONFIRMED
- V-304 Faye Grant: Cold storage, 08:00-11:00, CONFIRMED
Do not change or process mileage claims. Stop when the six shift assignments have been saved."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_shift(env,"pgv3shift_result")
TASK_CLASS=TaskPgv3shift
