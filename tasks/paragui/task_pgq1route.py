"""paraGUI ROUTE-LIVE1: make a Friday route consistent with live dispatch status."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_q1 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgq1route(BaseTask):
    intermediate_eval_safe = False
    id = "pgq1route"; snapshot = "paragui"; source = "paragui"; trajectory = "trajectories/"; related_apps = ["chrome"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = """Prepare Draft route RTE-17 for the Friday morning wave. Use the 08:00 released manifest as the ordered source list, but check the current status of every work order on the dispatch board before saving. Include every manifest order that is still Scheduled when you save the route, in exact manifest order; omit anything Deferred or Cancelled. Set service date 2026-11-13, vehicle Van 4, departure 08:00, and status Draft. Save and verify the route. Do not edit individual work orders."""
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_route(env, "pgq1route_result")
TASK_CLASS = TaskPgq1route
