from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc06 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgconc06a(BaseTask):
    intermediate_eval_safe=False
    id="pgconc06a";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","terminal"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="""Complete the four MetricPulse BI reviews in the first Chrome tab. The second analyst is using the same desktop and Downloads folder, so inspect each downloaded image before moving it. You may use the GUI or local command-line tools.

For NA-Q3, EU-Q3, APAC-Q4, and LATAM-Q4, select the matching region and quarter, read the pixel-rendered Target Adjustment from the chart, and download both the report CSV and chart PNG. Rename and archive each pair as /home/user/workspace/out_a/bi_pack/{combo}.csv and {combo}.png. Sum the revenue column in each CSV and compute csv_total minus target_adjustment. Save valid JSON to /home/user/workspace/out_a/bi_audit.json with one object per combo and the keys csv_total, target_adjustment, and variance. Confirm the four archived chart files are MetricPulse charts, not the other analyst's same-named summit images."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_a(env)
TASK_CLASS=TaskPgconc06a
