"""paraGUI contention task pgo2redlines (pair O2, family F1 office documents); spec: spec_o2.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o2 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo2redlines(BaseTask):
    intermediate_eval_safe = False
    id = "pgo2redlines"
    snapshot = "paragui"
    instruction = "I work in legal operations at Corvid Analytics. The Brightline master services agreement ~/Documents/Contracts/Brightline_MSA_v4.docx is open in LibreOffice Writer; it came back with tracked changes and comments from three reviewers. Please do what our head of legal, Hannah, asks in ~/Documents/Contracts/Email_from_Hannah.txt: resolve every one of the reviewers' tracked changes according to her rules and her scanned call notes (~/Documents/Contracts/call_notes_2026-10-14.pdf), delete the review comments, save the document in place as .docx, and write the list of points where we rejected Brightline's edits to ~/Documents/Contracts/Brightline_rejected_points.txt."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['writer', 'evince', 'gedit']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_redlines(env, "pgo2redlines_result")


TASK_CLASS = TaskPgo2redlines
