#!/usr/bin/env python3
"""Run scripted Writer/Calc conditions inside one real OSWorld V2.1 Guest."""
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

from swcub.actors import ScriptedCalcActor, ScriptedWriterActor
from swcub.core import EventLog
from swcub.evaluator import GuestLibreOfficeEvaluator
from swcub.instances import TaskInstanceSpec
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode


DIR = "/tmp/swcub_office"
WRITER_PATH = f"{DIR}/document.fodt"
CALC_PATH = f"{DIR}/table.fods"
WRITER_FINAL = "Approved by GUI actor"
DRAFT = "Draft"
CALC_FINAL = [["Record", "Status"], ["Quarterly", "Approved"]]
CALC_DRAFT = [["Record", "Status"], ["Quarterly", DRAFT]]
WRITER_DRAFT = "Quarterly status report"


def flat_writer() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
 <office:body><office:text><text:p>{WRITER_DRAFT}</text:p></office:text></office:body>
</office:document>'''.encode()


def flat_calc() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
 <office:body><office:spreadsheet><table:table table:name="Sheet1">
  <table:table-row><table:table-cell office:value-type="string"><text:p>Record</text:p></table:table-cell>
   <table:table-cell office:value-type="string"><text:p>Status</text:p></table:table-cell></table:table-row>
  <table:table-row><table:table-cell office:value-type="string"><text:p>Quarterly</text:p></table:table-cell>
   <table:table-cell office:value-type="string"><text:p>Draft</text:p></table:table-cell></table:table-row>
 </table:table></office:spreadsheet></office:body>
</office:document>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("writer-solo", "calc-solo", "sequential",
                                                "naive-interleaving", "focus-aware"), required=True)
    scenario = parser.parse_args().scenario
    instance_spec = TaskInstanceSpec.from_dict(json.loads(
        (ROOT / "tasks/instances/office_writer_calc.json").read_text(encoding="utf-8")))
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/office" / scenario))
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
                image_bytes = response.content
                with Image.open(io.BytesIO(image_bytes)) as image:
                    pixels = list(image.convert("RGB").resize((64, 64)).getdata())
                visible = sum(max(pixel) > 24 for pixel in pixels) / len(pixels)
                if visible > 0.05 and len(set(pixels)) > 16:
                    episode.observation = {"screenshot": image_bytes}
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
    try:
        episode.reset(task_config=None)
        if not wait_for_desktop(episode):
            raise TimeoutError("Guest desktop was not ready within 300 seconds")

        app_probe = command(["bash", "-lc",
            "for app in soffice firefox chromium chromium-browser google-chrome; do "
            "command -v $app 2>/dev/null || true; done; soffice --version 2>&1 || true"])
        (out / "guest-app-availability.txt").write_text(app_probe, encoding="utf-8")
        if "soffice" not in app_probe.lower() and "/usr/bin/libreoffice" not in app_probe:
            raise RuntimeError(f"LibreOffice is unavailable in Guest: {app_probe!r}")

        writer_b64 = base64.b64encode(flat_writer()).decode("ascii")
        calc_b64 = base64.b64encode(flat_calc()).decode("ascii")
        seed_code = (
            "from pathlib import Path; import base64; p=Path('/tmp/swcub_office'); p.mkdir(exist_ok=True); "
            f"Path('{WRITER_PATH}').write_bytes(base64.b64decode('{writer_b64}')); "
            f"Path('{CALC_PATH}').write_bytes(base64.b64decode('{calc_b64}'))"
        )
        episode.cli_action("task_setup", "python3 -c " + shlex.quote(seed_code))

        order = ([("writer", WRITER_PATH), ("calc", CALC_PATH)]
                 if scenario == "calc-solo" else [("calc", CALC_PATH), ("writer", WRITER_PATH)])
        for app, path in order:
            flag = "--calc" if app == "calc" else "--writer"
            launch = (f"soffice --nologo --norestore --nofirststartwizard {flag} {shlex.quote(path)} "
                      f">/tmp/swcub_office/{app}-launch.log 2>&1 & sleep 7")
            episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
        # LibreOffice can finish launching after the CLI process exits; wait
        # for the final app window to render before the first actor observes it.
        time.sleep(15)
        episode.refresh_observation()

        expected_writer = WRITER_DRAFT if scenario == "calc-solo" else WRITER_FINAL
        expected_calc = CALC_DRAFT if scenario == "writer-solo" else CALC_FINAL
        evaluator = GuestLibreOfficeEvaluator(
            lambda path: command(["cat", path]), expected_writer, expected_calc)
        writer = ScriptedWriterActor(recover_focus=scenario in {"sequential", "focus-aware"})
        calc = ScriptedCalcActor()
        if scenario in {"writer-solo", "calc-solo"}:
            actors = [writer] if scenario == "writer-solo" else [calc]
            schedule = ["writer_actor", "writer_actor"] if scenario == "writer-solo" else ["calc_actor"]
        elif scenario == "sequential":
            actors, schedule = [writer, calc], instance_spec.materialize_schedule()
        else:
            actors, schedule = [writer, calc], ["writer_actor", "calc_actor", "writer_actor"]
        report = DualActorOrchestrator(episode).run(actors, schedule, evaluator, out,
                                                    copy_artifacts=False)
        report["scenario"] = scenario
        report["task_id"] = instance_spec.task_id
        report["task_instance_id"] = (instance_spec.instance_id if scenario == "sequential"
                                       else f"office-v0-{scenario}-seed0")
        report["same_guest_container_id"] = episode.snapshot().get("guest_container_id")
        report["guest_apps"] = app_probe.strip().splitlines()
        report["stale_actions"] = sum(bool(event.details.get("stale_observation"))
                                      for event in episode.log.events)
        final_state = report["evaluation"].get("final_state", {})
        report["individual_goals"] = {
            "writer_actor": {"success": final_state.get("writer_text") == WRITER_FINAL,
                             "expected": WRITER_FINAL,
                             "actual": final_state.get("writer_text")},
            "calc_actor": {"success": final_state.get("calc_cells") == CALC_FINAL,
                           "expected": CALC_FINAL,
                           "actual": final_state.get("calc_cells")},
        }
        episode.copy_artifacts(out)

        before_reset = episode.snapshot()
        old_container = before_reset.get("guest_container_id")
        episode.reset(task_config=None)
        ready_after_reset = wait_for_desktop(episode)
        after_reset = episode.snapshot()
        reset_output = command(["bash", "-lc",
            f"test ! -e {WRITER_PATH} && test ! -e {CALC_PATH} && echo reset-clean"]) if ready_after_reset else ""
        reset_ok = ready_after_reset and reset_output.strip() == "reset-clean"
        episode.log.record("evaluator", "reset_check", "guest.reset_clean", before_reset, after_reset,
                           outcome="pass" if reset_ok else "fail",
                           details={"previous_guest_container_id": old_container,
                                    "new_guest_container_id": after_reset.get("guest_container_id"),
                                    "task_files_absent": reset_ok})
        episode.copy_artifacts(out / "reset-check")
        report["reset_check"] = {"success": reset_ok, "task_files_absent": reset_ok,
                                  "previous_guest_container_id": old_container,
                                  "new_guest_container_id": after_reset.get("guest_container_id")}
        task_ok = bool(report["evaluation"]["success"])
        if scenario == "naive-interleaving":
            observed = report["evaluation"].get("final_state", {})
            reproduced_focus_interference = (
                observed.get("writer_text") == WRITER_DRAFT
                and observed.get("calc_cells") != CALC_FINAL
                and any(WRITER_FINAL in cell for row in observed.get("calc_cells", [])
                        for cell in row)
            )
            scenario_ok = not task_ok and reproduced_focus_interference
            report["scenario_outcome"] = "focus_interference_detected" if scenario_ok else "interference_not_detected"
        else:
            scenario_ok = task_ok
            report["scenario_outcome"] = "joint_goals_met" if task_ok else "task_evaluation_failed"
        report["scenario_success"] = bool(scenario_ok)
        report["success"] = bool(scenario_ok and reset_ok)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        episode.log.write(out / "events.jsonl")
        print(json.dumps(report, indent=2))
        return 0 if report["success"] else 1
    finally:
        episode.close()


if __name__ == "__main__":
    raise SystemExit(main())
