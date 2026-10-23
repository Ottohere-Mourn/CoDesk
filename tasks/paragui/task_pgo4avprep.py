"""paraGUI contention task pgo4avprep (pair O4, family F1 office documents); spec: spec_o4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_o4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgo4avprep(BaseTask):
    intermediate_eval_safe = False
    id = "pgo4avprep"
    snapshot = "paragui"
    instruction = "I'm Lina Park, a PhD student at the Institute for Data Systems. My DSSW workshop talk ~/Documents/Talk/StreamJoin_DSSW.pptx is open in LibreOffice Impress. Please get it ready for the conference AV team following our institute's rules in ~/Documents/Talk/IDS_talk_rules.txt: switch it to 16:9, put my speaker script (scanned at ~/Documents/Talk/speaker_script.pdf) into the speaker notes of every slide, add the acknowledgements slide the script describes, save the presentation in place as .pptx, and export a PDF of the notes pages to ~/Documents/Talk/StreamJoin_DSSW_notes.pdf."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['impress', 'evince']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_avprep(env, "pgo4avprep_result")


TASK_CLASS = TaskPgo4avprep
