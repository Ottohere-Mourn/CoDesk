"""paraGUI contention task pgo3format (pair O3, family F1 office documents); spec: spec_o3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo3format(BaseTask):
    intermediate_eval_safe = False
    id = "pgo3format"
    snapshot = "paragui"
    instruction = "I'm Dr Amara Osei, PI of our grant application to the Northern Health Research Fund. The full proposal is open in LibreOffice Writer (~/Documents/Grant/NHRF_proposal_Osei.docx). Please make it comply with the funder's formatting requirements in the scanned Annex C (~/Documents/Grant/NHRF_Annex_C_formatting.pdf): page size and margins, body text, heading styles, the header with our application reference, page numbers and the reference list - without changing the wording of the proposal. Save it in place as .docx and export the submission PDF into ~/Documents/Grant/ with the file name the annex asks for."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['writer', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_format(env, "pgo3format_result")


TASK_CLASS = TaskPgo3format
