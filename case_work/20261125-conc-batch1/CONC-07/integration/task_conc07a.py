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
from evaluation_examples.task_class import pg_conc07 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgconc07a(BaseTask):
    intermediate_eval_safe=False
    id="pgconc07a";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","libreoffice"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="""Complete the Q4 supplier close in the already-open shared Ubuntu desktop. SupplyPortal is the first Chrome tab. The workbook database and LibreOffice session are shared with the other analyst. The Guest CLI tool is read-only and only for inspecting files; do not rely on it to write. Complete data entry in the browser GUI, presentation editing in Impress, and summary-file creation in LibreOffice Writer using the desktop GUI. The Guest physical desktop is 1920x1080; model screenshot previews may be scaled and do not indicate the physical resolution.

1. Maximize Chrome in the desktop GUI; the physical desktop is wide enough for the 1600-pixel view. Download the supplier master CSV and the three supplier exhibits from SupplyPortal. Read the six quality-review sheets in /home/user/workspace/in_a/qc_sheets; SUP-02 and SUP-05 have exact defect deductions and should be submitted with their matching QC image attachments. Enter all six supplier rows through the SupplyPortal form (the Guest CLI is read-only), preserving gross amount, deduction, net payable, and dispute flag. Finalize the batch and record its dynamic batch code.
2. Read /home/user/workspace/in_a/review_spec_a.txt and /home/user/workspace/in_a/brand_swatch_a.png. Complete the open /home/user/workspace/out_a/Q4_Supplier_Review.pptx: set the brand green, correct the six-vendor summary table, replace slides 3–5 placeholders with the three correct supplier exhibits, document both exceptions on slide 6, and add the full slide-7 note.
3. Save the seven-slide PPTX and export a seven-page PDF to /home/user/workspace/out_a/Q4_Supplier_Review.pdf. Write /home/user/workspace/out_a/settlement_audit.json with all six exact settlement rows, the two exceptions, and the returned batch_code. Verify both output formats before finishing."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_a(env)
TASK_CLASS=TaskPgconc07a
