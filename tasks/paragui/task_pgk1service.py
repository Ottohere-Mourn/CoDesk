"""paraGUI COURT-SERVICE1: record service for a different docket."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_k1 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgk1service(BaseTask):
 intermediate_eval_safe=False
 id="pgk1service";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""Record proof of service for docket SC-193. This legacy clerk desk has a single active-docket selector. In the docket index, make SC-193 active, verify that the header shows SC-193, then open Proof of service. Enter service date 2026-11-08, method Personal service, server ID PS-441, outcome Served, save, and verify the displayed docket number. Do not prepare a filing packet."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_service(env,"pgk1service_result")
TASK_CLASS=TaskPgk1service
