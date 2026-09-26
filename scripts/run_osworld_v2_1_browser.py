#!/usr/bin/env python3
"""Run real local-browser GUI/CLI/Human Replay episodes in OSWorld V2.1."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import sys
import time

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop_env.desktop_env import DesktopEnv

from swcub.actors import (ScriptedBrowserGUIActor, ScriptedBrowserHumanReplayActor,
                          ScriptedWebCacheGUIActor, ScriptedGuestCLIActor)
from swcub.core import EventLog
from swcub.evaluator import GuestWebStateEvaluator
from swcub.instances import TaskInstanceSpec
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.tasks.web_workspace import server_source


STATE_PATH = "/tmp/swcub_web/state.json"
ALL_EXPECTED = {
    "gui_status": "Approved", "cli_note": "Reviewed by CLI",
    "human_goal": "Reviewed by human", "agent_goal": "Approved by GUI actor",
}
SCENARIOS = ("gui-cli-gui-solo", "gui-cli-cli-solo", "gui-cli-refresh", "gui-cli-stale",
             "human-solo", "agent-solo", "human-agent-focus-aware", "human-agent-naive")


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
        "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2",
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
        elif scenario in {"human-solo", "agent-solo", "human-agent-focus-aware", "human-agent-naive"}:
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
        episode.close()


if __name__ == "__main__":
    raise SystemExit(main())
