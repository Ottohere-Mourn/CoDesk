#!/usr/bin/env python3
"""Run real local-browser GUI/CLI/Human Replay episodes in OSWorld V2.1."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OSWORLD_V2_DIR = Path(os.environ.get(
    "OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1")).resolve()
sys.path.insert(0, str(OSWORLD_V2_DIR))
from desktop_env.desktop_env import DesktopEnv
from mm_agents.qwen3vl_agent import Qwen3VLAgent

from swcub.actors import (ScriptedBrowserGUIActor, ScriptedBrowserHumanReplayActor,
                          ScriptedWebCacheGUIActor, ScriptedGuestCLIActor, ScriptedWriterActor)
from swcub.core import EventLog
from swcub.comparison_metrics import summarize_focus_events
from swcub.evaluator import GuestWebStateEvaluator
from swcub.instances import TaskInstanceSpec
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_agent_actor import OSWorldAgentActor
from swcub.provenance import TASK_VERSION, stamp_episode_provenance
from swcub.resource_safety import ensure_resource_identity
from swcub.tasks.web_workspace import server_source


STATE_PATH = "/tmp/swcub_web/state.json"
ALL_EXPECTED = {
    "gui_status": "Approved", "cli_note": "Reviewed by CLI",
    "human_goal": "Reviewed by human", "agent_goal": "Approved by GUI actor",
}
SCENARIOS = ("gui-cli-gui-solo", "gui-cli-cli-solo", "gui-cli-refresh", "gui-cli-stale",
             "qwen-gui-cli-solo", "qwen-gui-cli-naive", "qwen-gui-cli-recovery",
             "human-solo", "agent-solo", "agent-qwen-solo",
             "human-agent-focus-aware", "human-agent-naive",
             "comparison-agent-solo", "comparison-writer-solo",
             "comparison-sequential", "comparison-naive-shared",
             "comparison-focus-aware")
QWEN_GUI_CLI_SCENARIOS = {"qwen-gui-cli-solo", "qwen-gui-cli-naive",
                          "qwen-gui-cli-recovery"}
GUI_CLI_SCENARIOS = {scenario for scenario in SCENARIOS
                     if scenario.startswith("gui-cli-")} | QWEN_GUI_CLI_SCENARIOS


def make_comparison_writer(scenario: str):
    """Reuse the calibrated scripted Writer turns with a real visible app switch.

    The browser episode opens Chrome in kiosk mode, so the existing office actor's
    dock click cannot reach Writer. For non-focus-aware runs it uses the ordinary
    GUI Alt+Tab operation once at the start of its first turn; later turns receive
    no scheduler help, allowing the shared focus to change naturally.
    """
    from swcub.actors import ScriptedWriterActor

    class ComparisonWriterActor:
        actor_id = "writer_actor"
        role = "gui"

        def __init__(self):
            self.delegate = ScriptedWriterActor(recover_focus=False)
            self.did_initial_switch = False

        def run_step(self, context):
            if not self.did_initial_switch:
                self.did_initial_switch = True
                if scenario == "comparison-writer-solo":
                    # The solo control is initialized with Writer as its target
                    # window. Place the caret in the visible document body;
                    # a window title alone does not guarantee keyboard focus
                    # inside LibreOffice's document canvas.
                    context.click(800, 375)
                    context.observe()
                    self.delegate.turn = 1
                    return False
                if scenario != "comparison-focus-aware":
                    context.press_key("alt+tab")
                    # Observe the newly focused public desktop. The underlying
                    # action and observation events retain actor provenance.
                    context.observe()
            return self.delegate.run_step(context)

        def run(self, context):
            while not self.run_step(context):
                pass

    return ComparisonWriterActor()


class LocalQwenInferenceClient:
    """Transport adapter used by the pinned OSWorld Qwen3VLAgent."""

    def __init__(self, port: int):
        self.url = f"http://127.0.0.1:{port}/infer"

    def complete(self, payload: dict[str, object], _model: str) -> str:
        body = json.dumps({"messages": payload["messages"],
                           "max_new_tokens": min(int(payload.get("max_tokens", 512)), 512)}).encode()
        request = Request(self.url, data=body,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=240) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError(f"invalid local model-worker reply: {result!r}")
        return result["text"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    args = parser.parse_args()
    scenario = args.scenario
    instance_path = (ROOT / "tasks/instances/browser_gui_cli.json"
                     if scenario in GUI_CLI_SCENARIOS else
                     ROOT / "tasks/instances/browser_human_gui.json")
    instance_spec = TaskInstanceSpec.from_dict(json.loads(instance_path.read_text(encoding="utf-8")))
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/browser" / scenario))
    out.mkdir(parents=True, exist_ok=True)
    resource_identity = ensure_resource_identity(out / "resource-events.jsonl")
    guest_image = os.environ.get(
        "SWCUB_OSWORLD_GUEST_IMAGE",
        str(OSWORLD_V2_DIR / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2"),
    )
    desktop = DesktopEnv(provider_name="docker", path_to_vm=guest_image,
                         cache_dir=os.environ.get(
                             "SWCUB_OSWORLD_CACHE_DIR",
                             "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/task-cache"),
                         os_type="Ubuntu", action_space="pyautogui")

    def command(argv: list[str]) -> str:
        response = requests.post(
            f"http://{desktop.vm_ip}:{desktop.server_port}/execute",
            # Chrome's DevTools activation loop below can legitimately take
            # up to 60 s on a cold Guest. Keep the API command timeout above
            # that bound so slow startup returns its own status instead of a
            # spurious Guest-side HTTP 500.
            json={"command": argv, "shell": False, "timeout": 90}, timeout=(5, 105))
        response.raise_for_status()
        payload = response.json()
        if payload.get("returncode", 0) not in (0, None):
            raise RuntimeError(f"Guest command failed: {payload!r}")
        return str(payload.get("output", ""))

    def wait_for_desktop(episode: OSWorldSharedEpisode, timeout: float = 300) -> bool:
        import io
        deadline = time.monotonic() + timeout
        attempts = 0
        last_reason = "screenshot endpoint not ready"
        while time.monotonic() < deadline:
            attempts += 1
            try:
                response = requests.get(f"http://{desktop.vm_ip}:{desktop.server_port}/screenshot",
                                        timeout=(5, 10))
                response.raise_for_status()
                screen = response.content
                with Image.open(io.BytesIO(screen)) as image:
                    pixels = list(image.convert("RGB").resize((64, 64)).getdata())
                visible = sum(max(pixel) > 24 for pixel in pixels) / len(pixels)
                if visible > 0.05 and len(set(pixels)) > 16:
                    episode.observation = {"screenshot": screen}
                    episode.log.record("environment", "healthcheck", "guest.desktop_ready",
                                       {"attempts": attempts - 1}, {"attempts": attempts},
                                       outcome="ready", details={"visible_ratio": visible})
                    return True
                last_reason = f"blank screenshot visible_ratio={visible:.4f}"
            except (requests.RequestException, OSError, ValueError) as exc:
                last_reason = f"{type(exc).__name__}: {exc}"
            time.sleep(5)
        episode.log.record("environment", "healthcheck", "guest.desktop_ready",
                           {"attempts": attempts}, {"ready": False}, outcome="timeout",
                           details={"last_reason": last_reason})
        return False

    episode = OSWorldSharedEpisode(desktop, cli_executor=lambda raw: command(shlex.split(raw)))
    episode.log = EventLog()
    model_worker: subprocess.Popen[bytes] | None = None
    report: dict[str, object] | None = None

    source = base64.b64encode(server_source()).decode("ascii")
    initial_state = json.dumps(instance_spec.initial_state, separators=(",", ":"))
    setup = ("from pathlib import Path; import base64,json; p=Path('/tmp/swcub_web'); "
             "p.mkdir(exist_ok=True); "
             f"(p/'server.py').write_bytes(base64.b64decode('{source}')); "
             f"(p/'state.json').write_text(json.dumps(json.loads({initial_state!r})))")

    def reset_guest(instance_id: str, seed: int) -> OSWorldSharedEpisode:
        episode.reset(task_config=None, seed=seed)
        if not wait_for_desktop(episode):
            raise TimeoutError(f"Guest desktop was not ready for {instance_id}")
        return episode

    def initialize_guest(environment: OSWorldSharedEpisode, state: dict[str, object]) -> None:
        environment.cli_action("task_setup", "python3 -c " + shlex.quote(setup))

    try:
        # Reset and task state are both driven by the validated task instance;
        # the app server and browser are started only after its hidden seed lands.
        episode = instance_spec.initialize(reset_guest, initialize_guest)
        probe = command(["bash", "-lc", "command -v google-chrome; google-chrome --version; command -v python3"])
        (out / "guest-app-availability.txt").write_text(probe, encoding="utf-8")
        if "google-chrome" not in probe:
            raise RuntimeError(f"Chrome is unavailable in Guest: {probe!r}")

        if scenario.startswith("comparison-"):
            from scripts.run_osworld_v2_1_office import flat_writer, WRITER_DRAFT, WRITER_FINAL, WRITER_PATH
            writer_b64 = base64.b64encode(flat_writer()).decode("ascii")
            seed_writer = ("from pathlib import Path; import base64; "
                           "p=Path('/tmp/swcub_office'); p.mkdir(exist_ok=True); "
                           f"Path('{WRITER_PATH}').write_bytes(base64.b64decode('{writer_b64}'))")
            episode.cli_action("task_setup", "python3 -c " + shlex.quote(seed_writer))
            writer_launch = (f"soffice --nologo --norestore --nofirststartwizard --writer {shlex.quote(WRITER_PATH)} "
                             ">/tmp/swcub_office/writer-launch.log 2>&1 & sleep 10")
            episode.cli_action("task_setup", "bash -lc " + shlex.quote(writer_launch))

        start = ("python3 /tmp/swcub_web/server.py >/tmp/swcub_web/server.log 2>&1 & "
                 "for n in $(seq 1 30); do curl -fsS http://127.0.0.1:8765/health >/dev/null && exit 0; sleep 1; done; exit 1")
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(start))
        activate_task_page = "python3 -c " + shlex.quote(
            "import json,urllib.request; "
            "targets=json.load(urllib.request.urlopen('http://127.0.0.1:9223/json/list',timeout=2)); "
            "page=next((x for x in targets if x.get('type')=='page' and "
            "x.get('url')=='http://127.0.0.1:8765/'),None); "
            "assert page is not None, 'task page target unavailable'; "
            "urllib.request.urlopen('http://127.0.0.1:9223/json/activate/'+page['id'],timeout=2).read()"
        )
        launch = ("google-chrome --no-sandbox --disable-dev-shm-usage --no-first-run "
                  "--remote-debugging-port=9223 --user-data-dir=/tmp/swcub_web/chrome "
                  "--kiosk http://127.0.0.1:8765/ >/tmp/swcub_web/chrome.log 2>&1 & "
                  "for n in $(seq 1 60); do "
                  + activate_task_page + " && sleep 2 && exit 0; "
                  "sleep 1; done; exit 1")
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
        window_activation = (
            "if command -v wmctrl >/dev/null 2>&1; then "
            "wmctrl -a 'Shared Workspace - Google Chrome' || true; "
            "elif command -v xdotool >/dev/null 2>&1; then "
            "wid=$(xdotool search --onlyvisible --name 'Shared Workspace' 2>/dev/null | tail -1); "
            "test -z \"$wid\" || xdotool windowactivate --sync \"$wid\" || true; "
            "fi"
        )
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(window_activation))
        # DevTools can report the local page before the window manager paints
        # any usable desktop. Activate the exact task tab above, then wait for
        # a visible UI surface before handing control to an actor. The active
        # window may legitimately be Writer, so task-specific focus remains
        # part of the experiment and is not forced here.
        browser_deadline = time.monotonic() + 60
        browser_attempts = 0
        browser_ready = False
        while time.monotonic() < browser_deadline:
            browser_attempts += 1
            observation = episode.refresh_observation()
            title = episode._active_window_title()
            screenshot = observation.get("screenshot") if isinstance(observation, dict) else None
            colors = 0
            if isinstance(screenshot, bytes) and screenshot:
                try:
                    with Image.open(io.BytesIO(screenshot)) as image:
                        colors = len(set(image.convert("RGB").resize((64, 64)).getdata()))
                except (OSError, ValueError):
                    colors = 0
            if colors > 16:
                browser_ready = True
                episode.log.record("environment", "healthcheck", "guest.visible_ui_ready",
                                   {"ready": False}, {"ready": True}, outcome="ready",
                                   details={"attempts": browser_attempts,
                                            "active_window_title": title,
                                            "sampled_colors": colors})
                break
            time.sleep(2)
        if not browser_ready:
            episode.log.record("environment", "healthcheck", "guest.visible_ui_ready",
                               {"attempts": browser_attempts}, {"ready": False},
                               outcome="timeout",
                               details={"active_window_title": episode._active_window_title(),
                                        "sampled_colors": colors})
            raise TimeoutError("Guest desktop remained visually blank after task setup")

        if scenario == "comparison-writer-solo":
            focus_writer = (
                "for n in $(seq 1 45); do "
                "window=$(xdotool search --onlyvisible --name 'document.fodt' 2>/dev/null | tail -1); "
                "if test -n \"$window\"; then "
                "xdotool windowactivate --sync \"$window\" && xdotool getactivewindow getwindowname && exit 0; "
                "fi; sleep 1; done; exit 1"
            )
            focused_title = episode.cli_action(
                "task_setup", "bash -lc " + shlex.quote(focus_writer)).strip()
            episode.refresh_observation(source="writer_solo_preflight")
            if "document.fodt" not in focused_title or "Writer" not in focused_title:
                raise RuntimeError(f"Writer solo preflight did not focus the seeded document: {focused_title!r}")

        expected: dict[str, str]
        actors: list[object]
        schedule: list[str]
        if scenario.startswith("gui-cli-"):
            if scenario == "gui-cli-gui-solo":
                actors, schedule, expected = [ScriptedWebCacheGUIActor(refresh=True)], ["gui_actor", "gui_actor"], {"gui_status": "Approved"}
            elif scenario == "gui-cli-cli-solo":
                cli = ScriptedGuestCLIActor(["curl", "-fsS", "-X", "POST", "http://127.0.0.1:8765/cli",
                    "-H", "Content-Type: application/json", "-d", '{"cli_note":"Reviewed by CLI"}'])
                actors, schedule, expected = [cli], ["cli_actor"], {"cli_note": "Reviewed by CLI"}
            else:
                refresh = scenario == "gui-cli-refresh"
                actors = [ScriptedWebCacheGUIActor(refresh=refresh), ScriptedGuestCLIActor([
                    "curl", "-fsS", "-X", "POST", "http://127.0.0.1:8765/cli",
                    "-H", "Content-Type: application/json", "-d", '{"cli_note":"Reviewed by CLI"}'])]
                schedule = instance_spec.materialize_schedule()
                expected = instance_spec.expected_state
        elif scenario == "human-solo":
            actors, schedule, expected = [ScriptedBrowserHumanReplayActor()], ["human_replay"], {"human_goal": ALL_EXPECTED["human_goal"]}
        elif scenario == "agent-solo":
            actors, schedule, expected = [ScriptedBrowserGUIActor(recover_focus=True)], ["gui_actor", "gui_actor"], {"agent_goal": ALL_EXPECTED["agent_goal"]}
        elif scenario == "agent-qwen-solo" or scenario in QWEN_GUI_CLI_SCENARIOS or scenario in {
                "comparison-agent-solo", "comparison-sequential",
                "comparison-naive-shared", "comparison-focus-aware"}:
            host_python = os.environ.get("SWCUB_MODEL_PYTHON", "/opt/miniconda3/bin/python")
            model_path = Path(os.environ.get(
                "SWCUB_LOCAL_VLM_PATH", "/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct"))
            device = os.environ.get("SWCUB_LOCAL_VLM_DEVICE", "auto")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            worker_log = (out / "model_worker.log").open("w", encoding="utf-8")
            worker_env = os.environ.copy()
            worker_env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                               "HF_HUB_DISABLE_TELEMETRY": "1"})
            worker_env.setdefault("CUDA_VISIBLE_DEVICES", "0,2,3,4,5,6,7")
            model_worker = subprocess.Popen(
                [host_python, str(ROOT / "scripts/local_qwen_worker.py"),
                 "--model", str(model_path), "--device", device, "--port", str(port)],
                env=worker_env, stdout=worker_log, stderr=subprocess.STDOUT)
            worker_log.close()
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                if model_worker.poll() is not None:
                    raise RuntimeError(f"local Qwen worker exited; see {out / 'model_worker.log'}")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                        model_metadata = json.loads(response.read())
                    break
                except Exception:
                    time.sleep(2)
            else:
                raise TimeoutError("local Qwen worker did not become ready within 600 seconds")
            model_agent = Qwen3VLAgent(
                platform="ubuntu", model="qwen3-vl", max_tokens=512,
                action_space="pyautogui", observation_type="screenshot",
                coordinate_type="relative")
            model_agent.call_llm = LocalQwenInferenceClient(port).complete

            def record_model_step(record: dict[str, object]) -> None:
                before = episode.snapshot()
                episode.log.record(str(record.get("actor_id", "gui_actor")), "model",
                                   "osworld.qwen3vl.predict", before, before,
                                   observed_revision=record.get("observed_revision")
                                   if type(record.get("observed_revision")) is int else None,
                                   details=record)

            if scenario in QWEN_GUI_CLI_SCENARIOS:
                task = ('In the Shared Workspace page, set the GUI status field to exactly '
                        'Approved and save the record. Preserve every other field. If the visible '
                        'record may be stale, you may refresh it before saving. Stop when the task is complete.')
            else:
                task = ('In the browser review form, enter exactly "Approved by GUI actor" '
                        'in the GUI Agent Goal field and submit it.')
            qwen_actor = OSWorldAgentActor(model_agent, task, actor_id="gui_actor", max_steps=20,
                                           event_callback=record_model_step)
            if scenario.startswith("comparison-"):
                writer_actor = make_comparison_writer(scenario)
                if scenario == "comparison-agent-solo":
                    actors, schedule = [qwen_actor], ["gui_actor"] * qwen_actor.max_steps
                elif scenario == "comparison-sequential":
                    actors, schedule = [qwen_actor, writer_actor], (
                        ["gui_actor"] * qwen_actor.max_steps + ["writer_actor"] * 2)
                elif scenario == "comparison-naive-shared":
                    actors, schedule = [qwen_actor, writer_actor], (
                        [actor_id for _ in range(qwen_actor.max_steps)
                         for actor_id in ("gui_actor", "writer_actor")])
                else:
                    actors, schedule = [qwen_actor, writer_actor], (
                        [actor_id for _ in range(qwen_actor.max_steps)
                         for actor_id in ("gui_actor", "writer_actor")])
                expected = {}
            elif scenario in QWEN_GUI_CLI_SCENARIOS:
                cli_actor = ScriptedGuestCLIActor([
                    "curl", "-fsS", "-X", "POST", "http://127.0.0.1:8765/cli",
                    "-H", "Content-Type: application/json",
                    "-d", '{"cli_note":"Reviewed by CLI"}'])
                if scenario == "qwen-gui-cli-solo":
                    actors, schedule = [qwen_actor], ["gui_actor"] * qwen_actor.max_steps
                    expected = {"gui_status": "Approved"}
                else:
                    actors = [qwen_actor, cli_actor]
                    schedule = ["gui_actor", "cli_actor"] + [
                        "gui_actor"] * (qwen_actor.max_steps - 1)
                    expected = instance_spec.expected_state
            else:
                actors, schedule, expected = [qwen_actor], ["gui_actor"] * qwen_actor.max_steps, {
                    "agent_goal": ALL_EXPECTED["agent_goal"]}
            model_metadata = {"name": model_metadata["model"], "device": device,
                              "worker": "local Transformers inference; local_files_only",
                              "agent_framework": "OSWorld-V2.1 Qwen3VLAgent",
                              "agent_source": str(OSWORLD_V2_DIR / "mm_agents/qwen3vl_agent.py"),
                              "coordinate_type": "relative 0..999; native OSWorld parser scales to screenshot pixels"}
        else:
            recover = scenario == "human-agent-focus-aware"
            actors = [ScriptedBrowserGUIActor(recover_focus=recover), ScriptedBrowserHumanReplayActor()]
            schedule = instance_spec.materialize_schedule()
            expected = instance_spec.expected_state
        if scenario == "comparison-writer-solo":
            writer_actor = make_comparison_writer(scenario)
            actors, schedule, expected = [writer_actor], ["writer_actor", "writer_actor"], {}
        if scenario.startswith("comparison-"):
            from scripts.run_osworld_v2_1_office import WRITER_DRAFT, WRITER_FINAL, WRITER_PATH
            active = {actor.actor_id for actor in actors}
            expected_agent = (ALL_EXPECTED["agent_goal"] if "gui_actor" in active else "")
            expected_writer = (WRITER_FINAL if "writer_actor" in active else WRITER_DRAFT)
            class ComparisonEvaluator:
                def evaluate(self, environment):
                    web_state = json.loads(command(["cat", STATE_PATH]))
                    writer_xml = command(["cat", WRITER_PATH])
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(writer_xml)
                    writer_text = "\n".join("".join(p.itertext()) for p in root.iter(
                        "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"))
                    agent_ok = web_state.get("agent_goal", "") == expected_agent
                    writer_ok = writer_text == expected_writer
                    goals = {"qwen_browser": {"active": "gui_actor" in active,
                                               "success": agent_ok,
                                               "expected": expected_agent,
                                               "actual": web_state.get("agent_goal", "")},
                             "scripted_writer": {"active": "writer_actor" in active,
                                                  "success": writer_ok,
                                                  "expected": expected_writer,
                                                  "actual": writer_text}}
                    return {"success": all(g["success"] for g in goals.values()),
                            "individual_goals": goals,
                            "final_state": {"web": web_state, "writer_text": writer_text},
                            "missing": {k: v for k, v in goals.items() if not v["success"]}}
            evaluator = ComparisonEvaluator()
        else:
            evaluator = GuestWebStateEvaluator(lambda: command(["cat", STATE_PATH]), expected)

        def record_turn_focus(actor, turn_index):
            before = episode.snapshot()
            if scenario in QWEN_GUI_CLI_SCENARIOS and actor.actor_id == "gui_actor":
                active_before = episode._active_window_title()
                scheduler_action = None
                # The public Refresh button is the declared recovery intervention.
                # Turn 3 follows the first Qwen step and the CLI update in the fixed schedule.
                if scenario == "qwen-gui-cli-recovery" and turn_index == 3:
                    scheduler_action = "pyautogui.click(145, 410)"
                    episode.gui_action(
                        "focus_scheduler", scheduler_action,
                        source_action={"op": "scheduler_refresh_latest_state",
                                       "turn_index": turn_index,
                                       "target_control": "Refresh latest state"})
                active_after = episode._active_window_title()
                episode.log.record(
                    "focus_scheduler" if scheduler_action else "focus_observer", "focus",
                    "qwen_gui_cli_actor_turn", before, episode.snapshot(),
                    details={"actor_id": actor.actor_id, "turn_index": turn_index,
                             "policy": scenario, "active_window_before": active_before,
                             "active_window_after": active_after,
                             "scheduler_action": scheduler_action,
                             "cli_trigger_expected": turn_index >= 3})
                return
            active_window = command(["bash", "-lc", "xdotool getactivewindow getwindowname 2>/dev/null || true"]).strip()
            target = "Chrome" if actor.actor_id == "gui_actor" else "Writer"
            if scenario == "comparison-focus-aware":
                if actor.actor_id == "gui_actor":
                    search_args = "--class google-chrome"
                else:
                    # LibreOffice exposes class names that vary between soffice,
                    # soffice.bin, and desktop packaging; its visible title is stable.
                    search_args = "--name 'LibreOffice Writer'"
                focus_cmd = (f"window=$(xdotool search --onlyvisible {search_args} | tail -n 1); "
                             "test -n \"$window\" && xdotool windowactivate --sync \"$window\"; "
                             "xdotool getactivewindow getwindowname")
                active_window = command(["bash", "-lc", focus_cmd]).strip()
            episode.log.record("focus_scheduler", "focus", "actor_turn.focus", before,
                               episode.snapshot(), details={"actor_id": actor.actor_id,
                                                            "turn_index": turn_index,
                                                            "policy": scenario if scenario.startswith("comparison-") else "none",
                                                            "target_app": target,
                                                            "active_window_title": active_window,
                                                            "target_visible": (target.lower() in active_window.lower())})
        focus_hook = (record_turn_focus if scenario.startswith("comparison-")
                      or scenario in QWEN_GUI_CLI_SCENARIOS else None)
        report = DualActorOrchestrator(episode).run(actors, schedule, evaluator, out,
                                                    copy_artifacts=False,
                                                    before_actor_turn=focus_hook)
        if scenario in QWEN_GUI_CLI_SCENARIOS and qwen_actor is not None:
            model_events = [event for event in episode.log.events
                            if event.actor == "gui_actor" and event.kind == "model"]
            cli_events = [event for event in episode.log.events
                          if event.actor == "cli_actor" and event.kind == "cli"]
            interference_seq = min((event.seq for event in cli_events), default=None)
            recovery_steps = (sum(event.seq > interference_seq for event in model_events)
                              if interference_seq is not None else 0)
            focus_conflicts = []
            for event in episode.log.events:
                if event.actor != "gui_actor" or event.kind != "gui":
                    continue
                title = event.details.get("active_window_before")
                action = str(event.details.get("action", "")).lower()
                is_input = any(token in action for token in
                               ("pyautogui.write", "pyautogui.press", "pyautogui.hotkey"))
                if is_input and isinstance(title, str) and "chrome" not in title.lower():
                    focus_conflicts.append(event)
            invalid_action_count = sum(
                event.outcome != "ok" for event in episode.log.events
                if event.actor == "gui_actor" and event.kind in {"gui", "actor"})
            report["interaction_metrics"] = {
                "focus_conflict_count": len(focus_conflicts),
                "invalid_action_count": invalid_action_count,
                "recovery_steps": recovery_steps,
                "total_steps": sum(1 for event in episode.log.events
                                   if event.kind in {"gui", "cli"}
                                   and event.actor not in {"task_setup", "environment"}),
                "model_decision_steps": len(model_events),
                "focus_conflict_event_sequences": [event.seq for event in focus_conflicts],
                "cli_interference_event_sequence": interference_seq,
                "scheduler_refresh_count": sum(
                    event.actor == "focus_scheduler" and event.kind == "gui"
                    for event in episode.log.events),
            }
        if scenario.startswith("comparison-"):
            report["focus_metrics"] = summarize_focus_events(episode.log.events)
            focus_turns = report["focus_metrics"]["focus_events"]
            if scenario == "comparison-focus-aware":
                scheduler_turns = [row for row in focus_turns
                                   if row.get("policy") == "comparison-focus-aware"]
                failed_turns = [row for row in scheduler_turns if not row.get("target_visible")]
                report["focus_scheduler"] = {
                    "turn_count": len(scheduler_turns),
                    "failed_turn_count": len(failed_turns),
                    "success": bool(scheduler_turns) and not failed_turns,
                    "failed_turns": failed_turns,
                }
        report["scenario"] = scenario
        report["task_id"] = ("SWCUB-STALE-MERGE-001" if scenario in GUI_CLI_SCENARIOS
                              else instance_spec.task_id)
        if scenario in GUI_CLI_SCENARIOS:
            report["task_version"] = TASK_VERSION
            report["condition"] = {
                "gui-cli-gui-solo": "solo", "gui-cli-cli-solo": "solo",
                "gui-cli-stale": "naive_shared", "gui-cli-refresh": "recovery",
                "qwen-gui-cli-solo": "solo", "qwen-gui-cli-naive": "naive_shared",
                "qwen-gui-cli-recovery": "recovery_aware",
            }[scenario]
        repeat_id = os.environ.get("SWCUB_EPISODE_REPEAT", "01")
        if scenario in QWEN_GUI_CLI_SCENARIOS:
            report["task_instance_id"] = f"{instance_spec.instance_id}-{scenario}-repeat{repeat_id}"
        elif scenario in {"gui-cli-refresh", "human-agent-focus-aware"}:
            report["task_instance_id"] = instance_spec.instance_id
        else:
            report["task_instance_id"] = f"browser-v0-{scenario}-seed0"
        report["same_guest_container_id"] = episode.snapshot().get("guest_container_id")
        report["resource_run_id"] = resource_identity.run_id
        report["resource_ledger"] = str(resource_identity.ledger_path)
        report["guest_apps"] = probe.strip().splitlines()
        if scenario == "agent-qwen-solo" or scenario in QWEN_GUI_CLI_SCENARIOS or scenario in {
                "comparison-agent-solo", "comparison-sequential",
                "comparison-naive-shared", "comparison-focus-aware"}:
            trace_path = out / "model_trace.jsonl"
            trace_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                                 for item in qwen_actor.trace), encoding="utf-8")
            report["model"] = {**model_metadata, "trace": "model_trace.jsonl",
                               "name": "Qwen3-VL-30B-A3B-Instruct",
                               "model_config_sha256": "6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912",
                               "steps": len(qwen_actor.trace),
                               "action_steps": sum(len(item.get("native_actions", []))
                                                   for item in qwen_actor.trace)}
            actor_result = report["actors"].get("gui_actor", {})
            model_goal = (report["evaluation"].get("individual_goals", {})
                          .get("qwen_browser", {}).get("success")
                          if scenario.startswith("comparison-")
                          else report["evaluation"].get("success"))
            if model_goal is True:
                report["model_failure_class"] = "none"
            elif "did not terminate within" in str(actor_result.get("error", "")):
                report["model_failure_class"] = "model_task_failure"
            elif actor_result.get("error"):
                report["model_failure_class"] = "environment_or_action_execution_failure"
            else:
                report["model_failure_class"] = "model_task_failure"
            if scenario in QWEN_GUI_CLI_SCENARIOS and model_goal is not True:
                final_state = report["evaluation"].get("final_state", {})
                scheduler_count = report.get("interaction_metrics", {}).get(
                    "scheduler_refresh_count", 0)
                if actor_result.get("error"):
                    report["model_failure_class"] = "grounding"
                elif scenario == "qwen-gui-cli-naive" and final_state.get("cli_note") != "Reviewed by CLI":
                    report["model_failure_class"] = "interaction_conflict"
                elif scenario == "qwen-gui-cli-recovery" and scheduler_count != 1:
                    report["model_failure_class"] = "scheduler_issue"
                else:
                    report["model_failure_class"] = "model_capability"
        state = report["evaluation"].get("final_state", {})
        active_actor_ids = {actor.actor_id for actor in actors}
        if scenario.startswith("comparison-"):
            report["condition"] = scenario.removeprefix("comparison-")
            report["task_pair"] = {"actor_a": "OSWorld V2.1 Qwen3VLAgent Browser review form",
                                   "actor_b": "existing ScriptedWriterActor Writer document"}
            report["task_id"] = "SWCUB-BROWSER-WRITER-PAIR-001"
            report["task_instance_id"] = f"browser-writer-v0-{report['condition']}-seed0"
            report["same_guest_container_id"] = episode.snapshot().get("guest_container_id")
            report["individual_goals"] = report["evaluation"].get("individual_goals", {})
        elif scenario in GUI_CLI_SCENARIOS:
            report["individual_goals"] = {}
            if "gui_actor" in active_actor_ids:
                report["individual_goals"]["gui_actor"] = {
                    "success": state.get("gui_status") == "Approved", "actual": state.get("gui_status")}
            if "cli_actor" in active_actor_ids:
                report["individual_goals"]["cli_actor"] = {
                    "success": state.get("cli_note") == "Reviewed by CLI", "actual": state.get("cli_note")}
        elif scenario in {"human-solo", "agent-solo", "agent-qwen-solo",
                          "human-agent-focus-aware", "human-agent-naive"}:
            report["individual_goals"] = {}
            if "human_replay" in active_actor_ids:
                report["individual_goals"]["human_replay"] = {
                    "success": state.get("human_goal") == ALL_EXPECTED["human_goal"], "actual": state.get("human_goal")}
            if "gui_actor" in active_actor_ids:
                report["individual_goals"]["gui_actor"] = {
                    "success": state.get("agent_goal") == ALL_EXPECTED["agent_goal"], "actual": state.get("agent_goal")}
        if scenario.startswith("comparison-"):
            scheduler_ok = report.get("focus_scheduler", {}).get("success", True)
            report["scenario_success"] = bool(report["evaluation"]["success"] and scheduler_ok)
        elif scenario in {"gui-cli-stale", "human-agent-naive"}:
            if scenario == "gui-cli-stale":
                expected_negative = (state.get("gui_status") == "Approved"
                                     and state.get("cli_note") != "Reviewed by CLI")
                report["scenario_outcome"] = "stale_cli_update_lost" if expected_negative else "stale_conflict_not_reproduced"
            else:
                expected_negative = (state.get("human_goal") == ALL_EXPECTED["human_goal"]
                                     and state.get("agent_goal") != ALL_EXPECTED["agent_goal"])
                report["scenario_outcome"] = "human_agent_focus_interference" if expected_negative else "focus_interference_not_reproduced"
            report["scenario_success"] = bool(expected_negative)
        elif scenario in QWEN_GUI_CLI_SCENARIOS:
            report["scenario_success"] = bool(report["evaluation"]["success"])
            report["scenario_outcome"] = (
                "joint_goal_success" if report["scenario_success"] else "joint_goal_failure")
            if scenario == "qwen-gui-cli-recovery":
                scheduler_count = report.get("interaction_metrics", {}).get(
                    "scheduler_refresh_count", 0)
                report["scheduler_recovery_success"] = bool(
                    scheduler_count == 1 and report["scenario_success"])
                if scheduler_count != 1:
                    report["model_failure_class"] = "scheduler_issue"
        else:
            report["scenario_success"] = bool(report["evaluation"]["success"])

        episode.copy_artifacts(out)
        # Model inference is finished before the reset validation; release its
        # CPU/GPU resources while the Guest restarts.
        if model_worker is not None and model_worker.poll() is None:
            model_worker.terminate()
            try:
                model_worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                model_worker.kill()
                model_worker.wait(timeout=5)

        before = episode.snapshot()
        old_id = before.get("guest_container_id")
        episode.reset(task_config=None)
        reset_ok = wait_for_desktop(episode)
        after = episode.snapshot()
        clean = command(["bash", "-lc",
                         "if test -e /tmp/swcub_web/state.json || test -e /tmp/swcub_office/document.fodt; "
                         "then echo task-files-remain; else echo reset-clean; fi"]) if reset_ok else ""
        reset_ok = reset_ok and clean.strip() == "reset-clean"
        episode.log.record("evaluator", "reset_check", "guest.reset_clean", before, after,
                           outcome="pass" if reset_ok else "fail",
                           details={"previous_guest_container_id": old_id,
                                    "new_guest_container_id": after.get("guest_container_id"),
                                    "task_files_absent": reset_ok})
        episode.copy_artifacts(out / "reset-check")
        report["reset_check"] = {"success": bool(reset_ok), "task_files_absent": bool(reset_ok),
                                 "previous_guest_container_id": old_id,
                                 "new_guest_container_id": after.get("guest_container_id")}
        report["success"] = bool(report["scenario_success"] and reset_ok)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        episode.log.write(out / "events.jsonl")
        print(json.dumps(report, indent=2))
        return 0 if (reset_ok or scenario in QWEN_GUI_CLI_SCENARIOS) else 1
    except Exception as exc:
        # Keep screenshots, event history, and the precise setup failure even
        # when an episode cannot reach actor scheduling or evaluator scoring.
        try:
            episode.copy_artifacts(out)
            episode.log.write(out / "events.jsonl")
            (out / "preflight-failure.json").write_text(
                json.dumps({"scenario": scenario,
                            "error_type": type(exc).__name__,
                            "error": str(exc)}, indent=2) + "\n",
                encoding="utf-8")
        except Exception:
            pass
        raise
    finally:
        if model_worker is not None and model_worker.poll() is None:
            model_worker.terminate()
            try:
                model_worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                model_worker.kill()
                model_worker.wait(timeout=5)
        episode.close()
        if report is not None and scenario in GUI_CLI_SCENARIOS:
            actor_metadata = {
                actor.actor_id: {"class": type(actor).__name__, "role": actor.role}
                for actor in actors
            }
            source_files = [Path(__file__), ROOT / "swcub/actors.py",
                            ROOT / "swcub/evaluator.py", ROOT / "swcub/orchestrator.py",
                            ROOT / "swcub/osworld_adapter.py", ROOT / "swcub/osworld_agent_actor.py",
                            ROOT / "swcub/core.py", ROOT / "swcub/provenance.py",
                            ROOT / "swcub/tasks/web_workspace.py",
                            ROOT / "tasks/task_suite_v2.json",
                            ROOT / "scripts/stamp_task_suite_v2_provenance.py",
                            ROOT / "tasks/instances/browser_gui_cli.json",
                            ROOT / "scripts/local_qwen_worker.py"]
            stamp_episode_provenance(
                out, report, repo_root=ROOT,
                task_id="SWCUB-STALE-MERGE-001", task_version=TASK_VERSION,
                condition=report["condition"], seed=instance_spec.seed,
                actor_metadata=actor_metadata,
                evaluator_class=type(evaluator).__name__, source_files=source_files,
                osworld_checkout=OSWORLD_V2_DIR,
                release_manifest=ROOT / "outputs/osworld-v2.1/environment/release_manifest.json",
                guest_image=Path(guest_image), model_metadata=report.get("model"))


if __name__ == "__main__":
    raise SystemExit(main())
