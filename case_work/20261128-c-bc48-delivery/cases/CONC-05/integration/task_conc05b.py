from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc05 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc05b(BaseTask):
    intermediate_eval_safe=False
    id="pgconc05b";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","terminal"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="Migrate all four legacy TechWiki operations SOPs into the new publisher using the last two tabs in the already-open Chrome window. The read-only source is at http://127.0.0.1:18102/legacy and the publisher is at http://127.0.0.1:18102/editor. You may use the GUI or local command-line tools.\n\nFor SOP-01 through SOP-04, preserve the exact title, all three command lines including punctuation and unique marker, both core rules, and the correct category. Select the category using the publisher's dropdown and publish each SOP. A window or tab switch closes that dropdown, so reopen it if needed. After publishing all four, use Export Wiki JSON and verify /home/user/workspace/out_b/wiki_migrated.json contains exactly four complete entries. Do not paste any client-onboarding information into a SOP.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_b(env)
TASK_CLASS=TaskPgconc05b
