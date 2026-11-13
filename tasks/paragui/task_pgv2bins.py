"""Print the five scheduled 2 x 1 bin-location label batches."""
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_v2 as pair
if TYPE_CHECKING:
 from desktop_env.controllers.setup import SetupController
 from desktop_env.desktop_env import DesktopEnv
class TaskPgv2bins(BaseTask):
 intermediate_eval_safe=False
 id="pgv2bins";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome"]
 proxy=False;fixed_ip=False;possibility_of_env_change="low"
 instruction="""On the Riverside Logistics Shared Thermal Label Desk, prepare all five shelf/bin labels in the work queue: B-104 (2 copies), B-118 (1), B-203 (3), B-417 (2), and B-512 (1). Use the BIN_2X1 / Bin 2 x 1 stock profile. For each listed label, enter the requested copy count and print it. Check the selected profile before each print because this is a shared print station. Do not print parcel labels. Stop when all five requested bin labels are recorded."""
 def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
 def evaluate(self,env:"DesktopEnv"):return pair.evaluate_bins(env,"pgv2bins_result")
TASK_CLASS=TaskPgv2bins
