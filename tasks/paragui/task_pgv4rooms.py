from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v4 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv4rooms(BaseTask):
 intermediate_eval_safe=False
 id='pgv4rooms';snapshot='paragui';source='paragui';trajectory='trajectories/';related_apps=['chrome']
 proxy=False;fixed_ip=False;possibility_of_env_change='low'
 instruction="In the Northbridge College Room & Programme Desk, schedule both upcoming programmes. For each programme, select a currently OPEN room that meets its attendance and step-free requirements, then choose the exact programme time slot and setup shown on the programme card. A room closure entered by Facilities is real; do not use a room that is closed. Save each programme: EV-311 and EV-314."
 def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:'DesktopEnv'):return pair.evaluate(env,'A','pgv4rooms_result')
TASK_CLASS=TaskPgv4rooms
