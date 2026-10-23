"""paraGUI contention task pgf3slides (pair F3); see spec_f3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf3slides(BaseTask):
    intermediate_eval_safe = False
    id = "pgf3slides"
    snapshot = "paragui"
    instruction = "I coordinate the volunteers of the Riverside Makers Collective. The photos people sent me from Saturday's fair are in ~/Pictures/MakersFair_2026, and the scanned programme with my handwritten changes on the day is ~/Documents/MakersFair/programme_scan.pdf. Please do three things. 1) The family with the red umbrella asked us not to keep or publish any photo of them - delete those photos. 2) Sort the remaining photos into subfolders of ~/Pictures/MakersFair_2026 named \"HH-MM <programme item>\" after the programme item they show, using the time the item actually took place (e.g. \"10-30 Pottery wheel demo\"); photos that don't show a programme item that took place go into a subfolder \"General\". 3) In the thank-you slideshow ~/Documents/MakersFair/MakersFair_2026_recap.pptx (open in LibreOffice Impress) add, between the title slide and the closing slide, one slide per programme item that took place, in programme order, with the title \"HH:MM <programme item>\" (the actual time) and one photo of that item. Save the slideshow in its current format."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['nautilus', 'eog', 'pdfviewer', 'impress']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_slides(env, "pgf3slides_result")


TASK_CLASS = TaskPgf3slides
