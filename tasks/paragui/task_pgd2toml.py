"""paraGUI contention task pgd2toml (pair D2, family F4 software development); see spec_d2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd2toml(BaseTask):
    intermediate_eval_safe = False
    id = "pgd2toml"
    snapshot = "paragui"
    instruction = "I maintain meterflow, our smart-meter ingest pipeline (~/projects/meterflow, open in VS Code; its dashboard runs at http://127.0.0.1:8112, open in Chrome). We decided in docs/adr/0007-toml-config.md to move the settings from settings.ini to settings.toml. Please do the migration exactly as the ADR says: a settings.toml with the same values and proper TOML types, config loading through the vendored tomli, settings.ini deleted, and no code, test, script, VS Code launch configuration or README text still pointing to the INI file. Ops could only send a screenshot of the current production settings (docs/ops/prod-settings.png); turn it into deploy/prod.toml with the same structure. scripts/check.sh must pass. Then restart the dashboard (./dev.sh restart) and check in Chrome that its Config page says it was loaded from settings.toml. Commit your changes, and nothing else, with the message 'Move settings from INI to TOML (ADR-0007)'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_toml(env, "pgd2toml_result")


TASK_CLASS = TaskPgd2toml
