"""paraGUI ROUTE-RECON1: record a customer deferral."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_k2 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgk2defer(BaseTask):
 intermediate_eval_safe=False
 id="pgk2defer";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""Riverside Hall (work order WO-503) called: no staff can receive the technician Friday. In Work orders, mark WO-503 Deferred, reschedule it to 2026-11-14, and enter the exact note: Customer requested Saturday access; no Friday attendance. Save and verify the update. Do not edit the route."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_update(env,"pgk2defer_result")
TASK_CLASS=TaskPgk2defer
