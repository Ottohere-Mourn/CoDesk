#!/usr/bin/env python3
"""Run real local-browser GUI/CLI/Human Replay episodes in OSWorld V2.1."""
from __future__ import annotations

import argparse
import base64
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
                          ScriptedWebCacheGUIActor, ScriptedGuestCLIActor)
from swcub.core import EventLog
from swcub.evaluator import GuestWebStateEvaluator
from swcub.instances import TaskInstanceSpec
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_agent_actor import OSWorldAgentActor
from swcub.tasks.web_workspace import server_source


STATE_PATH = "/tmp/swcub_web/state.json"
ALL_EXPECTED = {
    "gui_status": "Approved", "cli_note": "Reviewed by CLI",
    "human_goal": "Reviewed by human", "agent_goal": "Approved by GUI actor",
}
SCENARIOS = ("gui-cli-gui-solo", "gui-cli-cli-solo", "gui-cli-refresh", "gui-cli-stale",
             "human-solo", "agent-solo", "agent-qwen-solo",
             "human-agent-focus-aware", "human-agent-naive")


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
                     if scenario.startswith("gui-cli-") else
                     ROOT / "tasks/instances/browser_human_gui.json")
    instance_spec = TaskInstanceSpec.from_dict(json.loads(instance_path.read_text(encoding="utf-8")))
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/browser" / scenario))
    out.mkdir(parents=True, exist_ok=True)
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
            json={"command": argv, "shell": False, "timeout": 45}, timeout=(5, 55))
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

        start = ("python3 /tmp/swcub_web/server.py >/tmp/swcub_web/server.log 2>&1 & "
                 "for n in $(seq 1 30); do curl -fsS http://127.0.0.1:8765/health >/dev/null && exit 0; sleep 1; done; exit 1")
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(start))
        launch = ("google-chrome --no-sandbox --disable-dev-shm-usage --no-first-run "
                  "--remote-debugging-port=9223 --user-data-dir=/tmp/swcub_web/chrome "
                  "--kiosk http://127.0.0.1:8765/ >/tmp/swcub_web/chrome.log 2>&1 & "
                  "for n in $(seq 1 60); do "
                  "curl -fsS http://127.0.0.1:9223/json/list 2>/dev/null | grep -q 'Shared Workspace' && exit 0; "
                  "sleep 1; done; exit 1")
        episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
        episode.refresh_observation()

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
        elif scenario == "agent-qwen-solo":
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

            task = ('In the browser review form, enter exactly "Approved by GUI actor" '
                    'in the GUI Agent Goal field and submit it.')
            qwen_actor = OSWorldAgentActor(model_agent, task, actor_id="gui_actor", max_steps=20,
                                           event_callback=record_model_step)
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
        evaluator = GuestWebStateEvaluator(lambda: command(["cat", STATE_PATH]), expected)
        report = DualActorOrchestrator(episode).run(actors, schedule, evaluator, out,
                                                    copy_artifacts=False)
        report["scenario"] = scenario
        report["task_id"] = instance_spec.task_id
        report["task_instance_id"] = (instance_spec.instance_id if scenario in {
            "gui-cli-refresh", "human-agent-focus-aware"} else f"browser-v0-{scenario}-seed0")
        report["same_guest_container_id"] = episode.snapshot().get("guest_container_id")
        report["guest_apps"] = probe.strip().splitlines()
        if scenario == "agent-qwen-solo":
            trace_path = out / "model_trace.jsonl"
            trace_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                                 for item in qwen_actor.trace), encoding="utf-8")
            report["model"] = {**model_metadata, "trace": "model_trace.jsonl",
                               "steps": len(qwen_actor.trace),
                               "action_steps": sum(len(item.get("native_actions", []))
                                                   for item in qwen_actor.trace)}
            actor_result = report["actors"].get("gui_actor", {})
            if report["evaluation"]["success"]:
                report["model_failure_class"] = "none"
            elif "did not terminate within" in str(actor_result.get("error", "")):
                report["model_failure_class"] = "model_task_failure"
            elif actor_result.get("error"):
                report["model_failure_class"] = "environment_or_action_execution_failure"
            else:
                report["model_failure_class"] = "model_task_failure"
        state = report["evaluation"].get("final_state", {})
        active_actor_ids = {actor.actor_id for actor in actors}
        if scenario.startswith("gui-cli-"):
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
        if scenario in {"gui-cli-stale", "human-agent-naive"}:
            if scenario == "gui-cli-stale":
                expected_negative = (state.get("gui_status") == "Approved"
                                     and state.get("cli_note") != "Reviewed by CLI")
                report["scenario_outcome"] = "stale_cli_update_lost" if expected_negative else "stale_conflict_not_reproduced"
            else:
                expected_negative = (state.get("human_goal") == ALL_EXPECTED["human_goal"]
                                     and state.get("agent_goal") != ALL_EXPECTED["agent_goal"])
                report["scenario_outcome"] = "human_agent_focus_interference" if expected_negative else "focus_interference_not_reproduced"
            report["scenario_success"] = bool(expected_negative)
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
                         "if test -e /tmp/swcub_web/state.json; then echo task-files-remain; "
                         "else echo reset-clean; fi"]) if reset_ok else ""
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
        return 0 if report["success"] else 1
    finally:
        if model_worker is not None and model_worker.poll() is None:
            model_worker.terminate()
            try:
                model_worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                model_worker.kill()
                model_worker.wait(timeout=5)
        episode.close()


if __name__ == "__main__":
    raise SystemExit(main())
