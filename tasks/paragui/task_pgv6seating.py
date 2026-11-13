from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v6 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv6seating(BaseTask):
 intermediate_eval_safe=False
 id='pgv6seating';snapshot='paragui';source='paragui';trajectory='trajectories/';related_apps=['chrome']
 proxy=False;fixed_ip=False;possibility_of_env_change='low'
 instruction="In Northbridge University's Examination Access Desk, record the exam seating plan exactly as given for ST-401, ST-407, and ST-412. Enter the assigned room, seat, arrival slot, and required equipment. Save each record."
 def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:'DesktopEnv'):return pair.evaluate(env,'B','pgv6seating_result')
TASK_CLASS=TaskPgv6seating
