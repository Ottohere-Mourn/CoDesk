from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v5 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv5expenses(BaseTask):
 intermediate_eval_safe=False
 id='pgv5expenses';snapshot='paragui';source='paragui';trajectory='trajectories/';related_apps=['chrome']
 proxy=False;fixed_ip=False;possibility_of_env_change='low'
 instruction="In the Linden Community Foundation Month-end Finance Desk, enter both staff reimbursement claims. For each EX record, fill employee, amount, and cost center exactly as printed. Click Copy source reference and paste it into Receipt reference so the long identifier is exact. Save EX-904 and EX-909."
 def setup(self,setup_controller:'SetupController',use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:'DesktopEnv'):return pair.evaluate(env,'B','pgv5expenses_result')
TASK_CLASS=TaskPgv5expenses
