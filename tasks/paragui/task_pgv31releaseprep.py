from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v31 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskV31Releaseprep(BaseTask):
 intermediate_eval_safe=False
 id="pgv31releaseprep";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction='At the Civic Data Office, prepare the open-data release for DAT-6028. Enter the approved export format, planned release date, public catalog title, and release package reference, then save.'
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate(env,'B','pgv31releaseprep_result')
TASK_CLASS=TaskV31Releaseprep
