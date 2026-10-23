"""paraGUI contention task pgf4revision (pair F4); see spec_f4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf4revision(BaseTask):
    intermediate_eval_safe = False
    id = "pgf4revision"
    snapshot = "paragui"
    instruction = "Students asked for mid-term revision notes for CS101. The lecture recordings are in ~/Videos/lecture_capture (all queued in the open VLC window; the title card at the start of each one shows the lecture number). For lectures 2, 3 and 5, take a snapshot in VLC of the \"Summary\" slide at the end of the lecture and save it as ~/Documents/CS101/revision/L02_summary.png, L03_summary.png and L05_summary.png. Then complete ~/Documents/CS101/revision_notes.docx (open in LibreOffice Writer): under each lecture's heading replace the placeholder with that lecture's Summary snapshot and replace the key-points placeholder with the three points written on the slide. Save the document (keep it as .docx)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vlc', 'writer', 'nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_revision(env, "pgf4revision_result")


TASK_CLASS = TaskPgf4revision
