"""paraGUI ROUTE-RECON1: build a route from the morning manifest."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_k2 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgk2route(BaseTask):
 intermediate_eval_safe=False
 id="pgk2route";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""Prepare draft route RTE-17 for the Friday morning wave using the frozen 08:00 released manifest. Include every released work order in its exact listed sequence: WO-501, WO-502, WO-503, WO-504. Set service date 2026-11-13, vehicle Van 4, departure 08:00, and status Draft, save, and verify the route. Do not edit individual work orders."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_route(env,"pgk2route_result")
TASK_CLASS=TaskPgk2route
