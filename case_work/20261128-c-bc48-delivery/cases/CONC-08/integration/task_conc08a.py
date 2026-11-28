from __future__ import annotations
import sys
import importlib
from pathlib import Path

# Ensure this run's private task bridges/oracles take precedence even when
# OSWorld has already imported its base evaluation_examples package.
RUNNER_ROOT = Path(__file__).resolve().parents[4]
if str(RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_ROOT))
for _name, _path in (("evaluation_examples", RUNNER_ROOT / "evaluation_examples"),
                     ("evaluation_examples.task_class", RUNNER_ROOT / "evaluation_examples/task_class")):
    _module = sys.modules.get(_name)
    if _module is not None and hasattr(_module, "__path__"):
        _paths = list(_module.__path__)
        if str(_path) not in _paths:
            _module.__path__ = [str(_path), *_paths]
# The OSWorld task_class package may already be loaded as a regular package;
# extending evaluation_examples.__path__ alone cannot make Python discover
# this run's bridge inside that already-imported subpackage.
_task_class_package = importlib.import_module("evaluation_examples.task_class")
_task_class_path = str(RUNNER_ROOT / "evaluation_examples/task_class")
_task_class_locations = list(getattr(_task_class_package, "__path__", []))
if _task_class_path not in _task_class_locations:
    _task_class_package.__path__ = [_task_class_path, *_task_class_locations]
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc08 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgconc08a(BaseTask):
    intermediate_eval_safe=False
    id="pgconc08a";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","libreoffice"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction='Complete the annual revenue close on the shared Ubuntu desktop. FinAudit is the first Chrome tab. Another analyst is concurrently editing HR_Cost in the same workbook and using the same desktop, browser window, and LibreOffice process.  Use GUI or CLI tools for workbook, browser, presentation, and JSON tasks, as you prefer, and save each artifact at its required path. The Guest physical desktop is 1920x1080; model screenshot previews may be scaled and do not indicate the physical resolution.\n\n1. Clean sales_q1.csv through sales_q4.csv in /home/user/workspace/in_a: remove repeated invoice IDs, but retain each valid negative return. Inspect all four PNG credit memos and extract each exact verification code, amount, and tax category. Complete the Rev_Ledger sheet in /home/user/workspace/shared/Corp_Annual_2026.xlsx. Preserve HR_Cost and FX_Tax_Rates. Keep currency conversion and all quarter/year totals as live formulas that reference FX_Tax_Rates; never replace formulas with hard-coded totals. Use the four memo adjustments. Export the completed Rev_Ledger sheet to /home/user/workspace/out_a/Rev_Ledger.pdf.\n2. In FinAudit at http://127.0.0.1:18141 submit all four credit memos with the exact code, amount, tax category, and matching PNG attachment. Finalize the batch and retain its returned close code.\n3. Create a readable quarterly net-revenue chart at /home/user/workspace/out_a/rev_trend.png. Update the already-open /home/user/workspace/out_a/Finance_Close.pptx with reconciled quarter/year totals, the chart without overlap, control risks, source evidence, and reviewer sign-off. Save the four-slide deck and export /home/user/workspace/out_a/Finance_Close.pdf.\n4. Write /home/user/workspace/out_a/finance_close.json with the four quarterly USD totals, annual net revenue, total memo adjustments in USD, four exact source records, and the returned close code. Reopen/check the workbook, PDF, and presentation before finishing. Do not modify HR_Cost or FX_Tax_Rates.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise.'
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_a(env)
TASK_CLASS=TaskPgconc08a
