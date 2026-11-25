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
class TaskPgconc08b(BaseTask):
    intermediate_eval_safe=False
    id="pgconc08b";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","libreoffice"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="""Complete the annual people-cost close on the shared Ubuntu desktop. HRDesk is the second Chrome tab. Another analyst is concurrently editing Rev_Ledger in the same workbook and using the same desktop, browser window, and LibreOffice process. The Guest CLI tool is read-only and can only inspect files; do not rely on it to edit or save. Use Calc for workbook changes, the browser GUI for HRDesk, Impress for the presentation, and Writer for the required JSON file, saving every artifact through desktop GUI dialogs. The Guest physical desktop is 1920x1080; model screenshot previews may be scaled and do not indicate the physical resolution.

1. Clean payroll_q1.csv through payroll_q4.csv in /home/user/workspace/in_b: remove repeated time-card rows, retain valid correction entries, and calculate overtime as base pay divided by 173 hours multiplied by overtime hours and the recorded multiplier. Inspect all four PNG allowance approvals and extract each exact verification code, amount, and department. Complete the HR_Cost sheet in /home/user/workspace/shared/Corp_Annual_2026.xlsx. Preserve Rev_Ledger and FX_Tax_Rates. Keep currency conversion, employer tax, and all quarter/year totals as live formulas that reference FX_Tax_Rates; never replace formulas with hard-coded totals. Apply a conditional highlight to every over-budget department row using the provided budget table. Export HR_Cost to /home/user/workspace/out_b/HR_Cost.pdf.
2. In HRDesk at http://127.0.0.1:18142 submit all four allowance approvals with the exact code, amount, department, and matching PNG attachment. Finalize the batch and retain its returned close code.
3. Create a readable quarterly people-cost chart at /home/user/workspace/out_b/hr_cost_chart.png. Update the already-open /home/user/workspace/out_b/HR_Close.pptx with reconciled quarter/year totals, the chart without overlap, exception notes, source evidence, and reviewer sign-off. Save the four-slide deck and export /home/user/workspace/out_b/HR_Close.pdf.
4. Write /home/user/workspace/out_b/hr_close.json with the four quarterly USD totals, annual people cost, total allowance cost in USD, four exact source records, over-budget departments, and the returned close code. Reopen/check the workbook, PDF, and presentation before finishing. Do not modify Rev_Ledger or FX_Tax_Rates."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_b(env)
TASK_CLASS=TaskPgconc08b
