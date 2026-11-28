from __future__ import annotations
import importlib
import sys
from pathlib import Path

# The OSWorld task_class package is already imported from its base tree. Add
# this attempt's bridge directory to that loaded package before resolving the
# versioned bridge module; otherwise Python can silently import a stale base
# pg_conc02_retry.py instead of the staged, audited setup.
RUNNER_ROOT = Path(__file__).resolve().parents[4]
if str(RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_ROOT))
_task_class_package = importlib.import_module("evaluation_examples.task_class")
_task_class_path = str(RUNNER_ROOT / "evaluation_examples/task_class")
_task_class_locations = list(getattr(_task_class_package, "__path__", []))
if _task_class_path not in _task_class_locations:
    _task_class_package.__path__ = [_task_class_path, *_task_class_locations]

from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc02_retry as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgconc02b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc02b"
    snapshot = "paragui"
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ["libreoffice"]
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"
    instruction = 'Complete the four-slide product launch deck in /home/user/workspace/out_b/Product_Launch_Final.pptx. The file is open in LibreOffice Impress.  Use the supplied materials in /home/user/workspace/in_b/ and perform presentation edits, saves, and PDF export with the GUI or Guest CLI, as you prefer.\n\nSet the cover title to "Project Helios v2.4 Launch" and derive its banner color from the supplied swatch image. Reorder the product overview before the launch-parameters slide. Correct all four specifications from launch_memo.txt and highlight every cell in the Helios Max row. Insert both supplied product views on the overview slide without covering its title or bottom caption. Replace the final-slide placeholder with the three required launch points, add the speaker note, and adjust layout so the full text fits above the safe bottom margin.\n\nSave the presentation in place and export it as PDF using GUI or Guest CLI methods to create the four-page /home/user/workspace/out_b/Product_Launch_Final.pdf. Reopen or render the saved outputs and verify the content and page layout before finishing.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_actor_b(env)


TASK_CLASS = TaskPgconc02b
