#!/usr/bin/env python3
"""Run a real OSWorld V2.1 two-actor shared-Guest CSV episode."""
from __future__ import annotations

import json
import os
import argparse
import shlex
import socket
import subprocess
from pathlib import Path
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

from swcub.actors import (ScriptedGuestCLIActor, ScriptedGuestFocusGUIActor,
                          ScriptedGuestGUIActor, ScriptedGuestHumanReplayActor)
from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.evaluator import GuestCsvEvaluator, GuestFocusEvaluator
from swcub.orchestrator import DualActorOrchestrator
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_agent_actor import OSWorldAgentActor
from swcub.provenance import TASK_VERSION, stamp_episode_provenance
from swcub.resource_safety import ensure_resource_identity
from mm_agents.qwen3vl_agent import Qwen3VLAgent


CSV_PATH = "/tmp/swcub_shared.csv"
FOCUS_QWEN_SCENARIOS = {"focus-qwen-solo", "focus-qwen-naive", "focus-qwen-recovery"}
EXPECTED = [
    {"actor": "gui", "value": "GUI_VALUE"},
    {"actor": "cli", "value": "CLI_VALUE"},
]


class LocalQwenInferenceClient:
    """Call the existing offline Qwen worker over loopback."""

    def __init__(self, port: int):
        self.url = f"http://127.0.0.1:{port}/infer"

    def complete(self, payload: dict[str, object], _model: str) -> str:
        request = Request(self.url, data=json.dumps({
            "messages": payload["messages"],
            "max_new_tokens": min(int(payload.get("max_tokens", 512)), 512),
        }).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=240) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError(f"invalid local model-worker reply: {result!r}")
        return result["text"]


def start_qwen_worker(out: Path) -> tuple[subprocess.Popen[bytes], int, dict[str, object]]:
    host_python = os.environ.get("SWCUB_MODEL_PYTHON", "/opt/miniconda3/bin/python")
    model_path = Path(os.environ.get(
        "SWCUB_LOCAL_VLM_PATH", "/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct"))
    device = os.environ.get("SWCUB_LOCAL_VLM_DEVICE", "auto")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    worker_log_path = out / "model_worker.log"
    worker_log = worker_log_path.open("w", encoding="utf-8")
    worker_env = os.environ.copy()
    worker_env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1"})
    worker_env.setdefault("CUDA_VISIBLE_DEVICES", "0,2,3,4,5,6,7")
    worker = subprocess.Popen(
        [host_python, str(ROOT / "scripts/local_qwen_worker.py"),
         "--model", str(model_path), "--device", device, "--port", str(port)],
        env=worker_env, stdout=worker_log, stderr=subprocess.STDOUT)
    worker_log.close()
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if worker.poll() is not None:
            raise RuntimeError(f"local Qwen worker exited; see {worker_log_path}")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                metadata = json.loads(response.read())
            break
        except Exception:
            time.sleep(2)
    else:
        worker.terminate()
        raise TimeoutError(f"local Qwen worker did not become ready; see {worker_log_path}")
    metadata.update({"device": device, "worker": "local Transformers; local_files_only",
                     "agent_framework": "OSWorld-V2.1 Qwen3VLAgent",
                     "agent_source": str(OSWORLD_V2_DIR / "mm_agents/qwen3vl_agent.py"),
                     "model_config_sha256": "6129b3f54d517a18553cf7525ff4886be6831c5806fc094d632b8ef38d859912",
                     "coordinate_type": "relative 0..999; native OSWorld parser scales to screenshot pixels"})
    return worker, port, metadata


def stop_qwen_worker(worker: subprocess.Popen[bytes] | None) -> None:
    if worker is None or worker.poll() is not None:
        return
    worker.terminate()
    try:
        worker.wait(timeout=10)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("shared-csv", "stale-overwrite",
                                                  "focus-recovery", "focus-stale",
                                                  "focus-gui-solo", "focus-human-solo",
                                                  *sorted(FOCUS_QWEN_SCENARIOS)),
                        default="shared-csv")
    scenario = parser.parse_args().scenario
    out = Path(os.environ.get("SWCUB_OSWORLD_RUN_DIR", ROOT / "outputs/osworld-v2.1/shared-csv"))
    out.mkdir(parents=True, exist_ok=True)
    resource_identity = ensure_resource_identity(out / "resource-events.jsonl")
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
    report: dict[str, object] | None = None
    model_worker: subprocess.Popen[bytes] | None = None
    model_metadata: dict[str, object] | None = None
    qwen_actor: OSWorldAgentActor | None = None
    actors: list[object] = []
    evaluator: GuestFocusEvaluator | GuestCsvEvaluator | None = None

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
        if scenario.startswith("focus-"):
            setup_shell = (
                "gnome-terminal --title=Document --geometry=70x18+100+80 -- bash -lc "
                + shlex.quote("cat > /tmp/swcub_document.txt")
                + " >/tmp/swcub-document-launch.log 2>&1 & "
                + "gnome-terminal --title=Chat --geometry=70x18+1000+80 -- bash -lc "
                + shlex.quote("cat > /tmp/swcub_chat.txt")
                + " >/tmp/swcub-chat-launch.log 2>&1 & sleep 5"
            )
            episode.cli_action("environment", "bash -lc " + shlex.quote(setup_shell))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready = command(["bash", "-lc",
                                 "test -f /tmp/swcub_document.txt && test -f /tmp/swcub_chat.txt && echo ready"])
                if ready.strip() == "ready":
                    break
                time.sleep(1)
            else:
                raise TimeoutError("Guest focus task terminal windows did not start within 30 seconds")
            if scenario in FOCUS_QWEN_SCENARIOS:
                model_worker, model_port, model_metadata = start_qwen_worker(out)
                model_agent = Qwen3VLAgent(
                    platform="ubuntu", model="qwen3-vl", max_tokens=512,
                    action_space="pyautogui", observation_type="screenshot",
                    coordinate_type="relative")
                model_agent.call_llm = LocalQwenInferenceClient(model_port).complete

                def record_model_step(record: dict[str, object]) -> None:
                    before = episode.snapshot()
                    episode.log.record("gui_actor", "model", "osworld.qwen3vl.predict",
                                       before, before,
                                       observed_revision=record.get("observed_revision")
                                       if type(record.get("observed_revision")) is int else None,
                                       details=record)

                instruction = (
                    'In the terminal window titled "Document", enter exactly Approved and press '
                    'Enter. Do not enter text in the Chat window. Stop when the line is present.'
                )
                qwen_actor = OSWorldAgentActor(
                    model_agent, instruction, actor_id="gui_actor", max_steps=20,
                    event_callback=record_model_step)
                if scenario == "focus-qwen-solo":
                    expected_focus = {"Document": "Approved\n", "Chat": ""}
                    actors = [qwen_actor]
                    schedule = ["gui_actor"] * qwen_actor.max_steps
                else:
                    expected_focus = {"Document": "Approved\n", "Chat": "Review note\n"}
                    actors = [qwen_actor, ScriptedGuestHumanReplayActor()]
                    schedule = ["gui_actor", "human_replay"] + [
                        "gui_actor"] * (qwen_actor.max_steps - 1)
            elif scenario == "focus-gui-solo":
                expected_focus = {"Document": "Approved\n", "Chat": ""}
                actors = [ScriptedGuestFocusGUIActor(recover=True)]
                schedule = ["gui_actor", "gui_actor"]
            elif scenario == "focus-human-solo":
                expected_focus = {"Document": "", "Chat": "Review note\n"}
                actors = [ScriptedGuestHumanReplayActor()]
                schedule = ["human_replay"]
            elif scenario not in FOCUS_QWEN_SCENARIOS:
                expected_focus = {"Document": "Approved\n", "Chat": "Review note\n"}
                actors = [
                    ScriptedGuestFocusGUIActor(recover=scenario == "focus-recovery"),
                    ScriptedGuestHumanReplayActor(),
                ]
                schedule = ["gui_actor", "human_replay", "gui_actor"]
            evaluator = GuestFocusEvaluator(
                lambda path: command(["cat", path]), expected_focus)
        else:
            seed = "from pathlib import Path; Path('/tmp/swcub_shared.csv').write_text('actor,value\\n', encoding='utf-8')"
            episode.cli_action("environment", f"python3 -c {shlex.quote(seed)}")
            evaluator = GuestCsvEvaluator(lambda: command(["cat", CSV_PATH]), EXPECTED)
            if scenario == "shared-csv":
                gui_command = 'python3 -c "open(\'/tmp/swcub_shared.csv\',\'a\').write(\'gui,GUI_VALUE\\\\n\')"'
            else:
                # Deliberately commit a stale whole-file snapshot after the CLI append.
                gui_command = (
                    'python3 -c "open(\'/tmp/swcub_shared.csv\',\'w\').write('
                    '\'actor,value\\\\ngui,GUI_VALUE\\\\n\')"'
                )
            cli_code = "from pathlib import Path; Path('/tmp/swcub_shared.csv').open('a', encoding='utf-8').write('cli,CLI_VALUE\\n')"
            actors = [ScriptedGuestGUIActor(gui_command),
                      ScriptedGuestCLIActor(["python3", "-c", cli_code])]
            schedule = ["gui_actor", "cli_actor", "gui_actor"]
        orchestrator = DualActorOrchestrator(episode)

        def focus_turn_hook(actor: object, turn_index: int) -> None:
            if scenario not in FOCUS_QWEN_SCENARIOS or getattr(actor, "actor_id", None) != "gui_actor":
                return
            before = episode.snapshot()
            active_before = episode._active_window_title()
            scheduler_action = None
            if scenario == "focus-qwen-recovery":
                # Match the V2 recovery policy: re-activate the visible Document window.
                scheduler_action = "pyautogui.click(420, 220)"
                episode.gui_action("focus_scheduler", scheduler_action,
                                   source_action={"op": "scheduler_focus_reacquire",
                                                  "target_window": "Document",
                                                  "turn_index": turn_index})
            active_after = episode._active_window_title()
            episode.log.record(
                "focus_scheduler" if scheduler_action else "focus_observer", "focus",
                "qwen_actor_turn_focus", before, episode.snapshot(),
                details={"actor_id": "gui_actor", "turn_index": turn_index,
                         "policy": scenario, "target_window": "Document",
                         "active_window_before": active_before,
                         "active_window_after": active_after,
                         "scheduler_action": scheduler_action})

        report = orchestrator.run(actors, schedule, evaluator, out,
                                  copy_artifacts=False,
                                  before_actor_turn=focus_turn_hook)
        stop_qwen_worker(model_worker)
        if qwen_actor is not None:
            trace_path = out / "model_trace.jsonl"
            trace_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                             for row in qwen_actor.trace), encoding="utf-8")
            report["model"] = {**(model_metadata or {}),
                               "name": "Qwen3-VL-30B-A3B-Instruct",
                               "weights_path": os.environ.get(
                                   "SWCUB_LOCAL_VLM_PATH",
                                   "/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct"),
                               "trace": "model_trace.jsonl",
                               "steps": len(qwen_actor.trace),
                               "action_steps": sum(len(row.get("native_actions", []))
                                                   for row in qwen_actor.trace)}
            report["model_failure_class"] = "none"
            if any(event.actor == "gui_actor" and event.kind == "actor"
                   and event.outcome != "ok" for event in episode.log.events):
                report["model_failure_class"] = "grounding"
        model_events = [event for event in episode.log.events
                        if event.actor == "gui_actor" and event.kind == "model"]
        conflict_events = []
        for event in episode.log.events:
            if event.actor != "gui_actor" or event.kind != "gui":
                continue
            title = event.details.get("active_window_before")
            action = str(event.details.get("action", "")).lower()
            is_input = any(token in action for token in
                           ("pyautogui.write", "pyautogui.press", "pyautogui.hotkey"))
            if is_input and isinstance(title, str) and "document" not in title.lower():
                conflict_events.append(event)
        interference_events = [event for event in episode.log.events
                               if event.actor == "human_replay"]
        first_interference = min((event.seq for event in interference_events), default=None)
        recovery_steps = (sum(event.seq > first_interference for event in model_events)
                          if first_interference is not None else 0)
        invalid_action_count = sum(
            event.outcome != "ok" for event in episode.log.events
            if event.actor == "gui_actor" and event.kind in {"gui", "actor"})
        report["interaction_metrics"] = {
            "focus_conflict_count": len(conflict_events),
            "unknown_focus_observation_count": sum(
                event.actor == "gui_actor" and event.kind == "gui"
                and event.details.get("active_window_before") is None
                for event in episode.log.events),
            "invalid_action_count": invalid_action_count,
            "recovery_steps": recovery_steps,
            "total_steps": sum(1 for event in episode.log.events
                               if event.kind in {"gui", "cli"}
                               and event.actor not in {"environment", "task_setup"}),
            "model_decision_steps": len(model_events),
            "focus_conflict_event_sequences": [event.seq for event in conflict_events],
            "interference_event_sequence": first_interference,
        }
        if qwen_actor is not None and not report["evaluation"].get("success"):
            final = report["evaluation"].get("final_state", {})
            qwen_error = report.get("actors", {}).get("gui_actor", {}).get("error", "")
            if scenario == "focus-qwen-recovery":
                focus_checks = [event.details for event in episode.log.events
                                if event.actor == "focus_scheduler" and event.kind == "focus"]
                scheduler_ok = bool(focus_checks) and all(
                    "document" in str(row.get("active_window_after") or "").lower()
                    for row in focus_checks)
                report["scheduler_recovery_success"] = scheduler_ok
                report["model_failure_class"] = (
                    "scheduler_issue" if not scheduler_ok else "model_capability")
            elif (scenario == "focus-qwen-naive"
                  and final.get("Chat") == "Review note\nApproved\n"):
                report["model_failure_class"] = "interaction_conflict"
            elif report["interaction_metrics"]["focus_conflict_count"]:
                report["model_failure_class"] = (
                    "interaction_conflict" if scenario != "focus-qwen-solo" else "grounding")
            elif "did not terminate within" in str(qwen_error):
                report["model_failure_class"] = "model_capability"
            else:
                report["model_failure_class"] = "model_capability"
        shared_guest_container_id = episode.snapshot().get("guest_container_id")
        report["shared_guest_container_id"] = shared_guest_container_id
        report["resource_run_id"] = resource_identity.run_id
        report["resource_ledger"] = str(resource_identity.ledger_path)
        stale_actions = [event for event in episode.log.events
                         if event.details.get("stale_observation")]
        report["interaction_metrics"] = {
            "stale_actions": len(stale_actions),
            "stale_observation_revision": (stale_actions[0].observed_revision if stale_actions else None),
            "current_revision_at_first_stale_action": (
                stale_actions[0].details.get("revision_before_action") if stale_actions else None
            ),
            **report.get("interaction_metrics", {}),
        }
        episode.copy_artifacts(out)

        previous_container = episode.snapshot().get("guest_container_id")
        before_reset = episode.snapshot()
        episode.reset(task_config=None)
        reset_display_ready = wait_for_desktop(episode)
        after_reset = episode.snapshot()
        reset_paths = ([CSV_PATH] if scenario in {"shared-csv", "stale-overwrite"} else
                       ["/tmp/swcub_document.txt", "/tmp/swcub_chat.txt"])
        reset_test = " && ".join(f"test ! -e {path}" for path in reset_paths)
        reset_output = command(["bash", "-lc", reset_test + " && echo reset-clean"]) if reset_display_ready else ""
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
        elif scenario == "stale-overwrite":
            missing_cli = {"actor": "cli", "value": "CLI_VALUE"} in report["evaluation"].get("missing", [])
            scenario_success = (not eval_success) and missing_cli
            outcome = "stale_overwrite_detected" if scenario_success else "stale_overwrite_not_detected"
        elif scenario == "focus-recovery":
            scenario_success = eval_success
            outcome = "focus_recovery_success" if eval_success else "focus_recovery_failed"
        elif scenario in {"focus-gui-solo", "focus-human-solo", "focus-qwen-solo"}:
            scenario_success = eval_success
            outcome = "independent_goal_success" if eval_success else "independent_goal_failed"
        elif scenario in {"focus-qwen-naive", "focus-qwen-recovery"}:
            scenario_success = eval_success
            outcome = "joint_goal_success" if eval_success else "joint_goal_failure"
        else:
            final = report["evaluation"].get("final_state", {})
            scenario_success = (not eval_success and final.get("Document") == ""
                                and final.get("Chat") == "Review note\nApproved\n")
            outcome = "stale_focus_misdirected" if scenario_success else "stale_focus_not_reproduced"
        report["scenario"] = scenario
        report["scenario_outcome"] = outcome
        report["scenario_success"] = scenario_success
        report["success"] = scenario_success and reset_ok
        task_id = "SWCUB-FOCUS-ROUTING-001" if scenario.startswith("focus-") else "SWCUB-CSV-LEGACY-001"
        report["task_id"] = task_id
        report["task_version"] = TASK_VERSION
        repeat_id = os.environ.get("SWCUB_EPISODE_REPEAT", "01")
        report["task_instance_id"] = f"{task_id.lower()}-{scenario}-seed0-repeat{repeat_id}"
        report["condition"] = {
            "focus-gui-solo": "solo", "focus-human-solo": "solo",
            "focus-stale": "naive_shared", "focus-recovery": "recovery",
            "focus-qwen-solo": "solo", "focus-qwen-naive": "naive_shared",
            "focus-qwen-recovery": "recovery_aware",
        }.get(scenario, scenario)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        episode.log.write(out / "events.jsonl")
        print(json.dumps(report, indent=2))
        # Model/evaluator failure is data, not a runner crash; continue the repeat matrix.
        return 0 if reset_ok else 1
    finally:
        stop_qwen_worker(model_worker)
        episode.close()
        if report is not None and scenario.startswith("focus-"):
            actor_metadata = {
                actor.actor_id: {"class": type(actor).__name__, "role": actor.role}
                for actor in actors
            }
            source_files = [Path(__file__), ROOT / "swcub/actors.py",
                            ROOT / "swcub/evaluator.py", ROOT / "swcub/orchestrator.py",
                            ROOT / "swcub/osworld_adapter.py", ROOT / "swcub/core.py",
                            ROOT / "swcub/provenance.py",
                            ROOT / "swcub/osworld_agent_actor.py",
                            ROOT / "scripts/stamp_task_suite_v2_provenance.py",
                            ROOT / "tasks/task_suite_v2.json",
                            ROOT / "scripts/local_qwen_worker.py"]
            stamp_episode_provenance(
                out, report, repo_root=ROOT,
                task_id="SWCUB-FOCUS-ROUTING-001", task_version=TASK_VERSION,
                condition=report["condition"], seed=0, actor_metadata=actor_metadata,
                evaluator_class=type(evaluator).__name__, source_files=source_files,
                model_metadata=report.get("model"),
                osworld_checkout=Path(os.environ.get(
                    "OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1")),
                release_manifest=ROOT / "outputs/osworld-v2.1/environment/release_manifest.json",
                guest_image=Path(guest_image))


if __name__ == "__main__":
    raise SystemExit(main())
