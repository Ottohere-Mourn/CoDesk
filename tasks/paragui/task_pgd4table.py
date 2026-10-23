"""paraGUI contention task pgd4table (pair D4, family F4 software development); see spec_d4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_d4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgd4table(BaseTask):
    intermediate_eval_safe = False
    id = "pgd4table"
    snapshot = "paragui"
    instruction = "I'm Noor, a PhD student in the Wadden Lab. Our analysis package is in ~/projects/shorebirds (open in VS Code) and the lab's report page runs at http://127.0.0.1:8114 (open in Chrome). 'python3 -m shorebirds.run_all' now crashes on the 2026 survey sheet, and the report no longer reproduces Table 2 of our submitted paper (paper/draft_v3.pdf, page 4; the paper's numbers and the rules in the table's footnote are correct). Please fix the analysis code so that it runs on all survey sheets and reproduces Table 2 exactly, regenerate results/table2.csv and results/fig2_trends.svg with run_all, add a unit test that would have caught the problems, and make sure all tests pass (python3 -m unittest). Then restart the report server (./dev.sh restart) and check in Chrome that its Table 2 matches the paper. Commit your changes, and nothing else, with the message 'Fix Table 2 analysis for the 2026 survey data'."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vscode', 'terminal', 'chrome', 'pdf_viewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_table(env, "pgd4table_result")


TASK_CLASS = TaskPgd4table
