"""paraGUI contention task pgf1cull (pair F1); see spec_f1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf1cull(BaseTask):
    intermediate_eval_safe = False
    id = "pgf1cull"
    snapshot = "paragui"
    instruction = "I run the Kestrel & Fern ceramics webshop. Our photographer copied yesterday's product shoot into ~/Pictures/Shoot_2026-10-14 (the folder is open in Files, and his workbook Shoot_2026-10-14.xlsx from that folder is open in LibreOffice). Please cull and organise the shoot. Rejects are: the grey-card and black lens-cap test frames, the slate frames (the white card with the SKU that he holds up before each product), out-of-focus frames, extra copies of a file, and, in a burst of near-identical frames, every frame except the first one. Move all rejects into a subfolder Rejects (keep their file names). Every product frame belongs to the SKU on the slate shot just before it: move the keepers into Selects/<SKU>/ and rename them <SKU>_01.jpg, <SKU>_02.jpg, ... in shooting order. Two keepers were shot in portrait but are stored sideways - turn those upright. Finally fill in the \"Shot list\" sheet for every file: SKU (for slates and product frames), Status (keep or reject) and New name (keepers only), and save the workbook (keep it as .xlsx)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['nautilus', 'eog', 'gimp', 'calc']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_cull(env, "pgf1cull_result")


TASK_CLASS = TaskPgf1cull
