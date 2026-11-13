from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v6 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv6accommodations(BaseTask):
 intermediate_eval_safe=False
 id='pgv6accommodations';snapshot='paragui';source='paragui';trajectory='trajectories/';related_apps=['chrome']
 proxy=False;fixed_ip=False;possibility_of_env_change='low'
 instruction="In Northbridge University's Examination Access Desk, confirm the three approved accommodation profiles exactly from each authorization notice. Enter the approved support, room requirement, and approval reference for ST-401, ST-407, and ST-412. Save each profile."
 def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:'DesktopEnv'):return pair.evaluate(env,'A','pgv6accommodations_result')
TASK_CLASS=TaskPgv6accommodations
