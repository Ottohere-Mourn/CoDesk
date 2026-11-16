from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v37 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV37Incidentreview(BaseTask):
 intermediate_eval_safe=False
 id="pgv37incidentreview";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At Cedarline Telecom, complete the synthetic incident review for TEL-771. Record severity, suspected cause, affected services, and incident reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A','pgv37incidentreview_result')
TASK_CLASS=TaskV37Incidentreview
