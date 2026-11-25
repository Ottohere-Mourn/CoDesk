from __future__ import annotations
from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_conc06 as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv
class TaskPgconc06b(BaseTask):
    intermediate_eval_safe=False
    id="pgconc06b";snapshot="paragui";source="paragui";trajectory="trajectories/";related_apps=["chrome","libreoffice","terminal"]
    proxy=False;fixed_ip=False;possibility_of_env_change="low"
    instruction="""Complete the five-slide Summit_Brochure.pptx already open in LibreOffice Impress. AssetHub is open in the second Chrome tab. The other analyst is concurrently saving many files named chart.png to the shared Downloads folder. You may use the GUI or local command-line tools.

Read /home/user/workspace/in_b/agenda_errata.txt, download the four named summit graphics from AssetHub, and verify each image before inserting it. Correct the four Day 1 agenda cells on slide 2. Place Summit_Keynote, Summit_TrackA, Summit_TrackB, and Summit_Roadmap on slides 2, 3, 4, and 5 respectively, keeping every picture inside the slide and away from text. On slide 5, add the full concluding statement from the errata and adjust its text box or font so it is fully visible. Save /home/user/workspace/out_b/Summit_Brochure.pptx and export a five-page PDF to /home/user/workspace/out_b/Summit_Brochure.pdf. Verify that each page contains the intended summit image and that no BI chart was inserted by mistake."""
    def setup(self,setup_controller:"SetupController",use_proxy:bool=False)->None:pair.setup(setup_controller)
    def evaluate(self,env:"DesktopEnv"):return pair.evaluate_actor_b(env)
TASK_CLASS=TaskPgconc06b
