"""Print the five scheduled 4 x 6 parcel labels."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v2 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv2cartons(BaseTask):
 intermediate_eval_safe=False
 id="pgv2cartons";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""On the Riverside Logistics Shared Thermal Label Desk, prepare all five parcel labels in the work queue: P-6201 (3 copies), P-6207 (2), P-6214 (1), P-6228 (4), and P-6233 (2). Use the PARCEL_4X6 / Parcel 4 x 6 stock profile. For each listed label, enter the requested copy count and print it. Check the selected profile before each print because this is a shared print station. Do not print bin labels. Stop when all five requested parcel labels are recorded."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_parcels(env,"pgv2cartons_result")
TASK_CLASS=TaskPgv2cartons
