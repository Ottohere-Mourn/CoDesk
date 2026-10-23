"""paraGUI contention task pgf3poster (pair F3); see spec_f3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf3poster(BaseTask):
    intermediate_eval_safe = False
    id = "pgf3poster"
    snapshot = "paragui"
    instruction = "We've booked next year's Riverside Makers Fair - the details are on the sticky note I photographed, ~/Documents/MakersFair/committee_note.jpg. Please finish the \"save the date\" poster ~/Documents/MakersFair/poster_2027.docx (open in LibreOffice Writer): replace [DATE], [TIME] and [VENUE] with the details from the note, and in the table put one photo from this year's fair (~/Pictures/MakersFair_2026) of each of these acts - the pottery wheel demo, the children's choir and the ukulele club - with a caption under each photo naming the group or stall as written on their banner. Don't use any photo showing the family with the red umbrella; they asked not to be published. The poster must stay a single A4 page. Save the document (keep it as .docx) and also export it as ~/Documents/MakersFair/poster_2027.pdf."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['writer', 'eog', 'nautilus', 'pdfviewer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_poster(env, "pgf3poster_result")


TASK_CLASS = TaskPgf3poster
