from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v4 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv4facilities(BaseTask):
 intermediate_eval_safe=False
 id='pgv4facilities';snapshot='paragui';source='paragui';trajectory='trajectories/';related_apps=['chrome']
 proxy=False;fixed_ip=False;possibility_of_env_change='low'
 instruction="In the Northbridge College Room & Programme Desk, process the facilities inspection notices. Mark R-101 CLOSED with reason \"Exit-light test failed\" and work order FM-6201; mark R-201 CLOSED with reason \"Damaged floor box cover\" and work order FM-6202. Do not edit programme bookings."
 def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:'DesktopEnv'):return pair.evaluate(env,'B','pgv4facilities_result')
TASK_CLASS=TaskPgv4facilities
