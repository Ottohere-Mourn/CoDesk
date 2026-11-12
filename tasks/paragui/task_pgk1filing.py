"""paraGUI COURT-SERVICE1: prepare the assigned small-claims filing packet."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_k1 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgk1filing(BaseTask):
 intermediate_eval_safe=False
 id="pgk1filing";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""Prepare the filing packet for docket SC-208. This legacy clerk desk has a single active-docket selector. In the docket index, make SC-208 active, verify that the header shows SC-208, then open Filing packet. Enter plaintiff Aster HVAC LLC, defendant Vale Apartments LLC, claim amount 1240.00, attach complaint_SC208.pdf, set status to Ready for clerk check, save, and verify the displayed docket number. Do not enter proof-of-service information."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_filing(env,"pgk1filing_result")
TASK_CLASS=TaskPgk1filing
