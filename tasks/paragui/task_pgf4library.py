"""paraGUI contention task pgf4library (pair F4); see spec_f4.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_f4 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgf4library(BaseTask):
    intermediate_eval_safe = False
    id = "pgf4library"
    snapshot = "paragui"
    instruction = "I'm the TA for CS101. The lecture-capture system dumped this term's recordings into ~/Videos/lecture_capture with useless names, and they are all queued in the VLC window that is open. Please turn them into a proper lecture library: the title card at the start of each recording shows the lecture number and topic. Move every lecture recording to ~/Videos/CS101/ named CS101_L<two-digit lecture number>.mp4 (e.g. CS101_L01.mp4), and delete the recordings that are not lectures (test or empty recordings). Then, in VLC, save a playlist ~/Videos/CS101/CS101_lectures.xspf that contains exactly the five lectures in lecture order (pointing to the renamed files), and write ~/Videos/CS101/index.txt with one line per lecture: the lecture number (L01 ...), its topic and the length of the recording as mm:ss."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['vlc', 'nautilus', 'gedit']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_library(env, "pgf4library_result")


TASK_CLASS = TaskPgf4library
