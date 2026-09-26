#!/usr/bin/env python3
"""Run a real OSWorld V2.1 two-actor shared-Guest CSV episode."""
from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
import sys
import time

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop_env.desktop_env import DesktopEnv

from swcub.actors import ScriptedGuestCLIActor, ScriptedGuestGUIActor
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.evaluator import GuestCsvEvaluator
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode


CSV_PATH = "/tmp/swcub_shared.csv"
EXPECTED = [
    {"actor": "gui", "value": "GUI_VALUE"},
    {"actor": "cli", "value": "CLI_VALUE"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("shared-csv", "stale-overwrite"), default="shared-csv")
    scenario = parser.parse_args().scenario
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/shared-csv"))
    out.mkdir(parents=True, exist_ok=True)
    guest_image = os.environ.get(
        "SWCUB_OSWORLD_GUEST_IMAGE",
        "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/docker_vm_data/osworld-v2-ubuntu-x86.qcow2",
    )
    desktop = DesktopEnv(provider_name="docker", path_to_vm=guest_image,
                        cache_dir=os.environ.get(
                            "SWCUB_OSWORLD_CACHE_DIR",
                            "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/task-cache",
                        ),
                        os_type="Ubuntu", action_space="pyautogui")

    def command(argv: list[str]) -> str:
        response = requests.post(
            f"http://{desktop.vm_ip}:{desktop.server_port}/execute",
            json={"command": argv, "shell": False, "timeout": 30},
            timeout=(5, 40),
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {"success", "ok", "completed", None}:
            if payload.get("returncode", 0) != 0:
                raise RuntimeError(f"Guest command failed: {payload!r}")
        if payload.get("returncode", 0) not in (0, None):
            raise RuntimeError(f"Guest command failed: {payload!r}")
        return str(payload.get("output", ""))

    def wait_for_desktop(episode: OSWorldSharedEpisode, timeout: float = 300) -> bool:
        deadline = time.monotonic() + timeout
        attempts = 0
        last_reason = "screenshot endpoint not ready"
        while time.monotonic() < deadline:
            attempts += 1
            try:
                response = requests.get(
                    f"http://{desktop.vm_ip}:{desktop.server_port}/screenshot",
                    timeout=(5, 10),
                )
                response.raise_for_status()
                content = response.content
                with Image.open(__import__("io").BytesIO(content)) as image:
                    pixels = list(image.convert("RGB").resize((64, 64)).getdata())
                visible = sum(max(pixel) > 24 for pixel in pixels) / len(pixels)
                distinct = len(set(pixels))
                if visible > 0.05 and distinct > 16:
                    episode.observation = {"screenshot": content}
                    episode.log.record(
                        "environment", "healthcheck", "guest.desktop_ready",
                        {"attempts": attempts - 1}, {"attempts": attempts, "visible_ratio": visible,
                                                       "distinct_pixels": distinct},
                        outcome="ready", details={"guest_container_id": episode.snapshot().get("guest_container_id")},
                    )
                    return True
                last_reason = f"blank/near-uniform screenshot (visible={visible:.4f}, distinct={distinct})"
            except (requests.RequestException, OSError, ValueError) as exc:
                last_reason = f"{type(exc).__name__}: {exc}"
            time.sleep(5)
        episode.log.record("environment", "healthcheck", "guest.desktop_ready",
                           {"attempts": attempts}, {"ready": False}, outcome="timeout",
                           details={"guest_container_id": episode.snapshot().get("guest_container_id"),
                                    "last_reason": last_reason})
        return False

    episode = OSWorldSharedEpisode(desktop, cli_executor=lambda raw: command(__import__("shlex").split(raw)))
    episode.log = EventLog()
    try:
        episode.reset(task_config=None)
        if not wait_for_desktop(episode):
            raise TimeoutError("Guest desktop did not produce a visible screenshot within 300 seconds")
        seed = "from pathlib import Path; Path('/tmp/swcub_shared.csv').write_text('actor,value\\n', encoding='utf-8')"
        episode.cli_action("environment", f"python3 -c {__import__('shlex').quote(seed)}")

        evaluator = GuestCsvEvaluator(lambda: command(["cat", CSV_PATH]), EXPECTED)
        if scenario == "shared-csv":
            gui_command = 'python3 -c "open(\'/tmp/swcub_shared.csv\',\'a\').write(\'gui,GUI_VALUE\\\\n\')"'
        else:
            # Deliberately commit the GUI actor's stale whole-file snapshot after
            # the CLI actor has appended its independent row.
            gui_command = (
                'python3 -c "open(\'/tmp/swcub_shared.csv\',\'w\').write('
                '\'actor,value\\\\ngui,GUI_VALUE\\\\n\')"'
            )
        cli_code = "from pathlib import Path; Path('/tmp/swcub_shared.csv').open('a', encoding='utf-8').write('cli,CLI_VALUE\\n')"
        actors = [
            ScriptedGuestGUIActor(gui_command),
            ScriptedGuestCLIActor(["python3", "-c", cli_code]),
        ]
        orchestrator = DualActorOrchestrator(episode)
        report = orchestrator.run(actors, ["gui_actor", "cli_actor", "gui_actor"], evaluator,
                                  out, copy_artifacts=False)
        shared_guest_container_id = episode.snapshot().get("guest_container_id")
        report["shared_guest_container_id"] = shared_guest_container_id
        stale_actions = [event for event in episode.log.events
                         if event.details.get("stale_observation")]
        report["interaction_metrics"] = {
            "stale_actions": len(stale_actions),
            "stale_observation_revision": (stale_actions[0].observed_revision if stale_actions else None),
            "current_revision_at_first_stale_action": (
                stale_actions[0].details.get("revision_before_action") if stale_actions else None
            ),
        }
        episode.copy_artifacts(out)

        previous_container = episode.snapshot().get("guest_container_id")
        before_reset = episode.snapshot()
        episode.reset(task_config=None)
        reset_display_ready = wait_for_desktop(episode)
        after_reset = episode.snapshot()
        reset_output = command(["bash", "-lc", f"test ! -e {CSV_PATH} && echo reset-clean"]) if reset_display_ready else ""
        reset_ok = reset_display_ready and reset_output.strip() == "reset-clean"
        episode.log.record("evaluator", "reset_check", "guest.reset_clean", before_reset,
                           after_reset, outcome="pass" if reset_ok else "fail",
                           details={"previous_guest_container_id": previous_container,
                                    "new_guest_container_id": after_reset.get("guest_container_id"),
                                    "guest_file_absent": reset_ok})
        reset_dir = out / "reset-check"
        episode.copy_artifacts(reset_dir)
        report["reset_check"] = {"success": reset_ok, "guest_file_absent": reset_ok,
                                  "previous_guest_container_id": previous_container,
                                  "new_guest_container_id": after_reset.get("guest_container_id")}
        eval_success = bool(report["evaluation"].get("success"))
        if scenario == "shared-csv":
            scenario_success = eval_success
            outcome = "joint_success" if eval_success else "joint_failure"
        else:
            missing_cli = {"actor": "cli", "value": "CLI_VALUE"} in report["evaluation"].get("missing", [])
            scenario_success = (not eval_success) and missing_cli
            outcome = "stale_overwrite_detected" if scenario_success else "stale_overwrite_not_detected"
        report["scenario"] = scenario
        report["scenario_outcome"] = outcome
        report["scenario_success"] = scenario_success
        report["success"] = scenario_success and reset_ok
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        episode.log.write(out / "events.jsonl")
        print(json.dumps(report, indent=2))
        return 0 if report["success"] else 1
    finally:
        episode.close()


if __name__ == "__main__":
    raise SystemExit(main())
