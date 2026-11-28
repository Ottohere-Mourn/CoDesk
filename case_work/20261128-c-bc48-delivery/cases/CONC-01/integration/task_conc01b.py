from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc01 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc01b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc01b"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["chrome"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = "Review the six live Northstar Operations telemetry tabs in the open Chrome page at http://127.0.0.1:18082. The Guest's physical desktop resolution is 1920x1080. A screenshot preview shown to the model may be scaled; do not infer physical resolution from the preview dimensions. Maximize Chrome through the desktop GUI and verify the page's own viewport status.  \n\nFor CPU, GPU, Network, Disk, Queue, and Latency, inspect both highlighted chart peaks by hovering over the points and record the exact values returned by their tooltips. After inspecting both peaks on each tab, click Save current tab PNG; the page exports that tab to /home/user/workspace/out_b/ops_tab_1.png through /home/user/workspace/out_b/ops_tab_6.png. The export button is available, and you may also use the Guest CLI for permitted workspace files. Do not report values from a page that shows a narrow-window warning.\n\nAfter inspecting all twelve peaks, click Export telemetry JSON. The page saves /home/user/workspace/out_b/ops_telemetry.json with keys tab_1 through tab_6; each value contains numeric peak_a and peak_b fields. Verify the saved values and all seven exported files before finishing.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, open_tabs=False)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_b(env)


TASK_CLASS = TaskPgconc01b
