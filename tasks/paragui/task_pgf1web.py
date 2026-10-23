"""paraGUI contention task pgf1web (pair F1); see spec_f1.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f1 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf1web(BaseTask):
    intermediate_eval_safe = False
    id = "pgf1web"
    snapshot = "paragui"
    instruction = "Four new products go live on the Kestrel & Fern webshop on Friday. They are listed in the \"Web images\" sheet of ~/Pictures/Shoot_2026-10-14/Shoot_2026-10-14.xlsx (open in LibreOffice), and the photos from yesterday's shoot are in that folder. Please make their web images in GIMP the same way as last week's KF-108 (~/Documents/Webshop/web/KF-108.jpg, open in GIMP): use a sharp, upright photo of the product (not an out-of-focus one), crop it to a square around the product with a little margin, scale it to 1200x1200 px and add the text \"© Kestrel & Fern\" as a text layer in the bottom-right corner. For each SKU save the GIMP file as ~/Documents/Webshop/xcf/<SKU>.xcf and export ~/Documents/Webshop/web/<SKU>.jpg with JPEG quality 85. Then fill in the sheet for each SKU: Source frame (the file name of the photo you used), Width and Height (px) of the exported image, and save the workbook (keep it as .xlsx)."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['gimp', 'calc', 'nautilus']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_web(env, "pgf1web_result")


TASK_CLASS = TaskPgf1web
