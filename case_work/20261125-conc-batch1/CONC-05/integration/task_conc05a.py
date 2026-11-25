from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc05 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc05a(BaseTask):
    intermediate_eval_safe=False
    id="pgconc05a";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","terminal"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="""Use the first two tabs in the already-open Chrome window to enter four new MiniCRM client records. The Application Library is at http://127.0.0.1:18101/docs; the data-entry form is at http://127.0.0.1:18101/form. You may use the GUI or local command-line tools.

Read all four scanned application images. For each client, enter its exact company name, IBAN, Tax ID, and service tier, then submit the record. After all four submissions, use Export CRM JSON and verify that /home/user/workspace/out_a/crm_records.json contains exactly four complete records. Do not mix content from the TechWiki tabs into any client field."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_a(env)
TASK_CLASS=TaskPgconc05a
