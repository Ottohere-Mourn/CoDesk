#!/usr/bin/env python3
"""Run scripted Writer/Calc conditions inside one real OSWorld V2.1 Guest."""
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

from swcub.actors import ScriptedCalcActor, ScriptedWriterActor
from swcub.core import EventLog
from swcub.evaluator import GuestLibreOfficeEvaluator
from swcub.instances import TaskInstanceSpec
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_agent_actor import OSWorldAgentActor


DIR = "/tmp/swcub_office"
WRITER_PATH = f"{DIR}/document.fodt"
CALC_PATH = f"{DIR}/table.fods"
WRITER_FINAL = "Approved by GUI actor"
DRAFT = "Draft"
CALC_FINAL = [["Record", "Status"], ["Quarterly", "Approved"]]
CALC_DRAFT = [["Record", "Status"], ["Quarterly", DRAFT]]
WRITER_DRAFT = "Quarterly status report"


class LocalQwenInferenceClient:
    """Transport only: forward the official OSWorld agent's prompt to local weights."""

    def __init__(self, port: int):
        self.url = f"http://127.0.0.1:{port}/infer"

    def complete(self, payload: dict[str, object], _model: str) -> str:
        request_body = json.dumps({
            "messages": payload["messages"],
            "max_new_tokens": min(int(payload.get("max_tokens", 512)), 512),
        }).encode("utf-8")
        request = Request(self.url, data=request_body,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=240) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError(f"invalid local model-worker reply: {result!r}")
        return result["text"]


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
                                                "naive-interleaving", "focus-aware",
                                                "writer-osworld-agent-solo",
                                                "calc-osworld-agent-solo",
                                                "writer-agent-calc-scripted-sequential"), required=True)
    scenario = parser.parse_args().scenario
    instance_spec = TaskInstanceSpec.from_dict(json.loads(
        (ROOT / "tasks/instances/office_writer_calc.json").read_text(encoding="utf-8")))
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/office" / scenario))
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
    model_worker: subprocess.Popen[bytes] | None = None
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
                 if scenario in {"calc-solo", "calc-osworld-agent-solo"}
                 else [("calc", CALC_PATH), ("writer", WRITER_PATH)])
        for app, path in order:
            flag = "--calc" if app == "calc" else "--writer"
            launch = (f"soffice --nologo --norestore --nofirststartwizard {flag} {shlex.quote(path)} "
                      f">/tmp/swcub_office/{app}-launch.log 2>&1 & sleep 7")
            episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
        # LibreOffice can finish launching after the CLI process exits; wait
        # for the final app window to render before the first actor observes it.
        time.sleep(15)
        episode.refresh_observation()

        expected_writer = WRITER_DRAFT if scenario in {"calc-solo", "calc-osworld-agent-solo"} else WRITER_FINAL
        expected_calc = CALC_DRAFT if scenario in {"writer-solo", "writer-osworld-agent-solo"} else CALC_FINAL
        evaluator = GuestLibreOfficeEvaluator(
            lambda path: command(["cat", path]), expected_writer, expected_calc)
        writer = ScriptedWriterActor(recover_focus=scenario in {"sequential", "focus-aware"})
        calc = ScriptedCalcActor()
        model_actors: list[OSWorldAgentActor] = []
        model_metadata: dict[str, object] | None = None
        if scenario in {"writer-osworld-agent-solo", "calc-osworld-agent-solo",
                        "writer-agent-calc-scripted-sequential"}:
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
            health_url = f"http://127.0.0.1:{port}/health"
            while time.monotonic() < deadline:
                if model_worker.poll() is not None:
                    raise RuntimeError(f"local Qwen worker exited; see {out / 'model_worker.log'}")
                try:
                    with urlopen(health_url, timeout=5) as response:
                        model_metadata = json.loads(response.read())
                    break
                except Exception:
                    time.sleep(2)
            else:
                model_worker.terminate()
                raise TimeoutError("local Qwen worker did not become ready within 600 seconds")
            worker_client = LocalQwenInferenceClient(port)
            model_agent = Qwen3VLAgent(
                platform="ubuntu", model="qwen3-vl", max_tokens=512,
                action_space="pyautogui", observation_type="screenshot",
                coordinate_type="relative")
            # Keep OSWorld's official prompt, multi-image history, action schema,
            # coordinate conversion, and parser; replace only its hosted transport.
            model_agent.call_llm = worker_client.complete

            def record_model_step(record: dict[str, object]) -> None:
                before = episode.snapshot()
                episode.log.record(str(record.get("actor_id", "gui_actor")), "model",
                                   "osworld.qwen3vl.predict", before, before,
                                   observed_revision=record.get("observed_revision")
                                   if type(record.get("observed_revision")) is int else None,
                                   details=record)

            task = ("In LibreOffice Writer, first click inside the visible existing paragraph "
                    '"Quarterly status report" to put the text cursor in the document. Then '
                    'replace all document text with exactly "Approved by GUI actor" and save. '
                    "Do not edit the spreadsheet."
                    if scenario in {"writer-osworld-agent-solo",
                                    "writer-agent-calc-scripted-sequential"} else
                    'In the Calc spreadsheet, change cell B2 from "Draft" to "Approved" and save. '
                    'Keep all other cells unchanged.')
            actor = OSWorldAgentActor(model_agent, task, actor_id="gui_actor", max_steps=20,
                                      event_callback=record_model_step)
            model_actors = [actor]
            if scenario == "writer-agent-calc-scripted-sequential":
                actors, schedule = [actor, calc], ["gui_actor"] * actor.max_steps + ["calc_actor"]
            else:
                actors, schedule = model_actors, ["gui_actor"] * actor.max_steps
            model_metadata = {"name": model_metadata["model"], "device": device,
                              "worker": "local Transformers inference; local_files_only",
                              "agent_framework": "OSWorld-V2.1 Qwen3VLAgent",
                              "agent_source": str(OSWORLD_V2_DIR / "mm_agents/qwen3vl_agent.py"),
                              "coordinate_type": "relative 0..999; native OSWorld parser scales to screenshot pixels"}
        elif scenario in {"writer-solo", "calc-solo"}:
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
        active_ids = {actor.actor_id for actor in actors}
        report["individual_goals"] = {}
        if "writer_actor" in active_ids or scenario in {
                "writer-osworld-agent-solo", "writer-agent-calc-scripted-sequential"}:
            writer_id = ("gui_actor" if scenario in {
                "writer-osworld-agent-solo", "writer-agent-calc-scripted-sequential"}
                else "writer_actor")
            report["individual_goals"][writer_id] = {
                "success": final_state.get("writer_text") == expected_writer,
                "expected": expected_writer, "actual": final_state.get("writer_text")}
        if "calc_actor" in active_ids or scenario == "calc-osworld-agent-solo":
            calc_id = ("gui_actor" if scenario == "calc-osworld-agent-solo" else "calc_actor")
            report["individual_goals"][calc_id] = {
                "success": final_state.get("calc_cells") == expected_calc,
                "expected": expected_calc, "actual": final_state.get("calc_cells")}
        if model_actors:
            trace_path = out / "model_trace.jsonl"
            all_traces = [item for actor in model_actors for item in actor.trace]
            trace_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                                             for item in all_traces), encoding="utf-8")
            report["model"] = {**model_metadata, "trace": "model_trace.jsonl",
                               "steps": len(all_traces),
                               "action_steps": sum(len(item.get("native_actions", [])) for item in all_traces)}
        episode.copy_artifacts(out)

        # The model is no longer needed for grading or the reset check; release
        # CPU/GPU resources so Guest reset is not competing with inference.
        if model_worker is not None and model_worker.poll() is None:
            model_worker.terminate()
            try:
                model_worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                model_worker.kill()
                model_worker.wait(timeout=5)

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
        if model_actors:
            model_actor_results = [report["actors"].get(actor.actor_id, {})
                                   for actor in model_actors]
            if report["evaluation"]["success"]:
                report["model_failure_class"] = "none"
            elif (all(result.get("success") for result in model_actor_results)
                  or any("did not terminate within" in str(result.get("error", ""))
                         for result in model_actor_results)):
                report["model_failure_class"] = "model_task_failure"
            else:
                report["model_failure_class"] = "model_or_action_execution_failure"
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
