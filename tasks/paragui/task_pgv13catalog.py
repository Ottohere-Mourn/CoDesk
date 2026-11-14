from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v13 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV13Catalog(BaseTask):
 intermediate_eval_safe=False
 id="pgv13catalog";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='In Research Data Repository, catalog dataset DS-4102. Use its catalog note to enter dataset type, collection date as YYYY-MM-DD, steward unit, and catalog reference, then save the dataset.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'A',"pgv13catalog_result")
TASK_CLASS=TaskV13Catalog
