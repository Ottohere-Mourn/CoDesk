from typing import TYPE_CHECKING
from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_cases as pair
if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv

class TaskPgconc12b(BaseTask):
    intermediate_eval_safe = False
    id = "pgconc12b"; snapshot = "paragui"; source = "paragui"
    trajectory = "trajectories/"; related_apps = ["libreoffice"]
    proxy = False; fixed_ip = False; possibility_of_env_change = "low"
    instruction = "Complete the `This Week's Experiments and Schedule` section in the open LibreOffice Writer document `lab_weekly_checklist.docx`. Fill its three reserved rows with these items, keeping their meaning intact: `[Pending] C09-C11 shared-desktop integration and baseline statistics`; `[Verify] export evaluation logs and archive anomalous traces`; `[Sync] finalize the Friday lab-meeting presentation materials`. Preserve the existing meeting background and the other section, then save the shared document in Writer.\n\nThis is one Ubuntu desktop and one Writer window shared with another editor. The cursor, selection, focus, and unsaved buffer may change while you work. Re-check the section and saved document after interruptions; coordinate through the visible document, not a separate chat. The physical display is 1920x1080; scaled screenshots are previews.  There is no reset limit or reset penalty.\n\nYou may freely choose either the GUI or the Guest CLI, including reading and writing task files and running Python or shell commands, to complete your assigned work. Guest CLI commands execute inside this OSWorld Guest, not on the HealthCare host. The host-side Oracle, ground truth and control plane are not exposed through Guest CLI; do not alter evaluation state. The two Actors share one desktop session and have no direct chat unless your task explicitly says otherwise."
    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup_writer(setup_controller, open_document=False)
    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_writer(env, "B")
TASK_CLASS = TaskPgconc12b
