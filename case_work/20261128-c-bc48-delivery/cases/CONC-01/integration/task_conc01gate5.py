"""Deterministic real-Guest reference replay for CONC-01 Gate 5; no model call."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_common as C
from evaluation_examples.task_class import pg_conc01 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc01gate5(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc01gate5"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["chrome", "terminal"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = 'A deterministic reference replay is running in this prepared desktop. Do not make changes; finish after the replay setup returns.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller, open_tabs=True)
        root = f"{C.HOME}/.local/share/paragui/conc01"
        C.upload(setup_controller, [("CONC-01/gate5_reference.py", f"{root}/gate5_reference.py")])
        C.sh(setup_controller, f"python3 -u {root}/gate5_reference.py", timeout=2400)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_gate5(env)


TASK_CLASS = TaskPgconc01gate5
