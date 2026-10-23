"""paraGUI contention task pgo2dpa (pair O2, family F1 office documents); spec: spec_o2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo2dpa(BaseTask):
    intermediate_eval_safe = False
    id = "pgo2dpa"
    snapshot = "paragui"
    instruction = "I work in legal operations at Corvid Analytics. Brightline's data protection officer has signed off the wording of a new data protection clause; it is in the scanned rider ~/Documents/Contracts/Rider_DP-1_Data_Protection.pdf. Please put it into the master services agreement that is open in LibreOffice Writer (~/Documents/Contracts/Brightline_MSA_v4.docx) exactly as the rider instructs: new Clause 8 'Data Protection' right after Clause 7 (Confidentiality) with the same heading style as the other clauses, the new definition in clause 1.1, the following clauses, their sub-clauses and all cross-references renumbered, and the new clause added to the list of clauses that survive termination. Then update the table of contents, save the document in place as .docx, and export a PDF of the updated agreement to ~/Documents/Contracts/Brightline_MSA_DPA_review.pdf for their DPO. Leave the reviewers' tracked changes and comments as they are - a colleague is handling those."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['writer', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_dpa(env, "pgo2dpa_result")


TASK_CLASS = TaskPgo2dpa
