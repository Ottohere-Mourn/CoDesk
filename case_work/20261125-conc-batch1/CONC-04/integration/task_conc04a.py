from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc04 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc04a(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc04a"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["chrome", "terminal"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = """Complete the FlowCanvas service topology at http://127.0.0.1:18091. The six component cards and six named target slots are visible on the canvas. You may use the GUI or local command-line tools.

Place API Gateway, Auth Service, Order Engine, Inventory DB, Event Bus, and Billing Worker in their matching dashed slots. Then draw exactly these seven directed connections by dragging from each source anchor to its target: API Gateway to Auth Service; Auth Service to Order Engine; Order Engine to Inventory DB; Auth Service to Event Bus; Event Bus to Billing Worker; Billing Worker to Inventory DB; Order Engine to Billing Worker. Trace a multi-segment path around both red restricted zones whenever a direct segment would cross a zone. Each drag must finish at the destination anchor.

Submit the topology. Save the canvas image and JSON to /home/user/workspace/out_a/arch_flow.png and /home/user/workspace/out_a/arch_flow.json. Verify the six placements, seven directed connections, and unobstructed visible canvas before finishing."""

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, "a")

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_a(env)


TASK_CLASS = TaskPgconc04a
