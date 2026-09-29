#!/usr/bin/env python3
"""Run the CoDesk Track A scripted Solo / MA-ID / MA-SD matrix on OSWorld V2.1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any
import uuid
import requests


ROOT = Path(__file__).resolve().parents[1]
OSWORLD_V2_DIR = Path(os.environ.get(
    "OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1")).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(OSWORLD_V2_DIR))

from desktop_env.desktop_env import DesktopEnv

from swcub.core import EventLog
from swcub.environment import ActorContext
from swcub.osworld_adapter import OSWorldSharedEpisode
from swcub.osworld_readiness import wait_for_guest_desktop
from swcub.resource_safety import PROJECT_NAME, ResourceLedger, ensure_resource_identity
from swcub.tasks.track_a import (EXPECTED_VALUES, STATE_PATHS, TASK_ID, TASK_VERSION,
                                 TrackAFocusEvaluatorV1, ScriptedChatActor,
                                 ScriptedDocumentActor)


GUEST_IMAGE = Path(os.environ.get(
    "SWCUB_OSWORLD_GUEST_IMAGE",
    OSWORLD_V2_DIR / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2")).resolve()
RUNTIME_IMAGE = os.environ.get("SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE",
                               "swcub/osworld-v2.1-qemu-runtime:local")
DEFAULT_ARTIFACT_PARENT = Path("/mnt/raid1/mjh/CoDesk-V1-artifacts/track-a")
RELEASE_MANIFEST = ROOT / "outputs/osworld-v2.1/environment/release_manifest.json"


class BoundEnvironments(dict[str, OSWorldSharedEpisode]):
    """Named per-desktop episodes, all writing into one episode event log."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_source_state() -> dict[str, Any]:
    def git(*args: str) -> str | None:
        proc = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, check=False, timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else None
    return {"commit": git("rev-parse", "HEAD"),
            "dirty_paths": (git("status", "--porcelain") or "").splitlines()}


def configure_episode_identity(out: Path) -> None:
    run_id = f"tracka-{uuid.uuid4().hex}"
    owner = secrets.token_hex(32)
    ledger = (out / "resource-events.jsonl").resolve()
    os.environ["SWCUB_RUN_ID"] = run_id
    os.environ["SWCUB_OWNER_TOKEN"] = owner
    os.environ["SWCUB_RESOURCE_LEDGER"] = str(ledger)
    os.environ.pop("SWCUB_RESOURCE_IDENTITY_INITIALIZED", None)
    os.environ["SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE"] = RUNTIME_IMAGE
    os.environ["SWCUB_OSWORLD_OVERLAY_HOST_DIR"] = str((out / "overlays").resolve())
    (out / "overlays").mkdir(parents=True, exist_ok=False)
    (out / "run-owner-marker.json").write_text(json.dumps({
        "project": "CoDesk", "historical_project_label": PROJECT_NAME,
        "run_id": run_id, "owner_token": owner,
        "purpose": "OSWorld V2.1 copy-on-write guest overlays for this Track A episode",
    }, indent=2) + "\n", encoding="utf-8")


def guest_command(desktop: DesktopEnv, argv: list[str], timeout: int = 45) -> str:
    response = requests.post(
        f"http://{desktop.vm_ip}:{desktop.server_port}/execute",
        json={"command": argv, "shell": False, "timeout": timeout},
        timeout=(5, timeout + 10),
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("returncode", 0) not in (0, None):
        raise RuntimeError(f"Guest command failed: {payload!r}")
    return str(payload.get("output", ""))


def wait_for_desktop(episode: OSWorldSharedEpisode, desktop: DesktopEnv,
                     timeout: float = 300) -> bytes:
    return wait_for_guest_desktop(episode, desktop, timeout=timeout)


def make_environment(binding: str, log: EventLog) -> tuple[OSWorldSharedEpisode, DesktopEnv]:
    desktop = DesktopEnv(provider_name="docker", path_to_vm=str(GUEST_IMAGE),
                         cache_dir=os.environ.get(
                             "SWCUB_OSWORLD_CACHE_DIR",
                             str(OSWORLD_V2_DIR / "task-cache")),
                         os_type="Ubuntu", action_space="pyautogui")
    episode = OSWorldSharedEpisode(
        desktop,
        cli_executor=lambda raw, desktop=desktop: guest_command(desktop, shlex.split(raw)))
    episode.log = log
    try:
        episode.reset(task_config=None)
        wait_for_desktop(episode, desktop)
    except Exception:
        # A failed readiness check must not orphan the newly created Guest.
        # Preserve any visual evidence before the provider performs its
        # ownership-verified close from the current episode ledger.
        try:
            episode.copy_artifacts(Path(os.environ["SWCUB_RESOURCE_LEDGER"]).parent
                                   / "partial-artifacts" / binding)
        except Exception as artifact_exc:
            log.record("environment", "artifact_preservation", "guest.readiness_artifact_copy",
                       {"copied": False}, {"copied": False}, outcome="failed",
                       details={"desktop_binding": binding,
                                "error": f"{type(artifact_exc).__name__}: {artifact_exc}"})
        try:
            episode.close()
        except Exception as close_exc:
            log.record("environment", "lifecycle", "guest.readiness_close",
                       {"closed": False}, {"closed": False}, outcome="failed",
                       details={"desktop_binding": binding,
                                "guest_container_id": episode.snapshot().get("guest_container_id"),
                                "error": f"{type(close_exc).__name__}: {close_exc}"})
        raise
    return episode, desktop


def setup_focus_desktop(episode: OSWorldSharedEpisode, desktop: DesktopEnv) -> None:
    launch = (
        "gnome-terminal --title=Document --geometry=70x18+100+80 -- bash -lc "
        + shlex.quote(f"cat > {STATE_PATHS['Document']}")
        + " >/tmp/codesk-track-a-document-launch.log 2>&1 & "
        + "gnome-terminal --title=Chat --geometry=70x18+1000+80 -- bash -lc "
        + shlex.quote(f"cat > {STATE_PATHS['Chat']}")
        + " >/tmp/codesk-track-a-chat-launch.log 2>&1 & sleep 5"
    )
    episode.cli_action("task_setup", "bash -lc " + shlex.quote(launch))
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        probe = guest_command(desktop, ["bash", "-lc",
            f"if test -f {STATE_PATHS['Document']} && test -f {STATE_PATHS['Chat']}; "
            "then echo ready; else echo waiting; fi"])
        if probe.strip() == "ready":
            break
        time.sleep(1)
    else:
        raise TimeoutError("Track A terminal windows/files did not start")
    # Establish one fixed initial focus in every condition. B must take its
    # own valid Chat turn to create the MA-SD control event.
    episode.gui_action("task_setup", "pyautogui.click(420, 220)", pause=0.5,
                       source_action={"op": "initial_focus", "target_window": "Document"})
    episode.refresh_observation(source="task_setup")


def active_ids(episode: OSWorldSharedEpisode) -> dict[str, str | None]:
    return {"environment_id": episode.environment_id,
            "guest_container_id": episode.snapshot().get("guest_container_id")}


def run_schedule(environments: BoundEnvironments, actor_bindings: dict[str, str],
                 active_actors: list[str], schedule: list[str], log: EventLog) -> dict[str, Any]:
    actors = {"document_actor": ScriptedDocumentActor(),
              "chat_actor": ScriptedChatActor()}
    contexts = {actor_id: ActorContext(actor_id, environments[actor_bindings[actor_id]], "gui")
                for actor_id in active_actors}
    results: dict[str, dict[str, Any]] = {
        actor_id: {"success": True, "completed": False, "turns": 0,
                   "environment_id": contexts[actor_id].environment_id,
                   "desktop_binding": actor_bindings[actor_id]}
        for actor_id in active_actors
    }
    completed: set[str] = set()
    for turn_index, actor_id in enumerate(schedule, start=1):
        if actor_id in completed:
            continue
        env = environments[actor_bindings[actor_id]]
        before = env.snapshot()
        try:
            actor = actors[actor_id]
            step = getattr(actor, "run_step", None)
            done = bool(step(contexts[actor_id])) if callable(step) else (actor.run(contexts[actor_id]) is None)
            results[actor_id]["turns"] += 1
            results[actor_id]["completed"] = done
            if done:
                completed.add(actor_id)
            log.record("orchestrator", "schedule", "track_a.actor_turn", before, env.snapshot(),
                       details={"turn_index": turn_index, "actor_id": actor_id,
                                "desktop_binding": actor_bindings[actor_id],
                                "schedule": schedule, "completed": done})
        except Exception as exc:
            results[actor_id]["success"] = False
            results[actor_id]["error"] = f"{type(exc).__name__}: {exc}"
            log.record(actor_id, "actor", "track_a.turn", before, env.snapshot(),
                       outcome="failed", details={"error": results[actor_id]["error"],
                                                   "desktop_binding": actor_bindings[actor_id]})
            break
    for actor_id in active_actors:
        if not results[actor_id]["completed"] and results[actor_id]["success"]:
            results[actor_id]["success"] = False
            results[actor_id]["error"] = "actor did not complete within its declared turn budget"
    return results


def verify_ledger(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    container_ids = {row["resource_id"] for row in rows
                     if row.get("resource_type") == "container" and row.get("event") == "created"}
    destroyed_ids = {row["resource_id"] for row in rows
                     if row.get("resource_type") == "container" and row.get("event") == "destroyed"}
    return {"container_count": len(container_ids),
            "all_containers_have_destroy_record": bool(container_ids) and container_ids <= destroyed_ids,
            "container_ids": sorted(container_ids),
            "labels_consistent": all(row.get("labels", {}).get("org.swcub.project") == PROJECT_NAME
                                      for row in rows if row.get("resource_type") == "container")}


def write_provenance(out: Path, report: dict[str, Any], source_files: list[Path]) -> None:
    artifact_hashes: dict[str, str] = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file() or path.name == "provenance.json" or "overlays" in path.parts:
            continue
        artifact_hashes[str(path.relative_to(out))] = sha256_file(path)
    runtime = subprocess.run(["docker", "image", "inspect", RUNTIME_IMAGE],
                             capture_output=True, text=True, check=False, timeout=20)
    runtime_id = None
    if runtime.returncode == 0:
        runtime_id = json.loads(runtime.stdout)[0].get("Id")
    release_sha = sha256_file(RELEASE_MANIFEST) if RELEASE_MANIFEST.is_file() else None
    source_hashes = {str(path.resolve().relative_to(ROOT)): sha256_file(path)
                     for path in source_files if path.is_file()}
    ledger = out / "resource-events.jsonl"
    overlays = [{"path": str(path.relative_to(out)), "size_bytes": path.stat().st_size}
                for path in sorted((out / "overlays").rglob("*")) if path.is_file()]
    sidecar = {
        "metadata_schema_version": 1,
        "benchmark": {"name": "CoDesk", "suite": "CoDesk-V1-Track-A", "suite_version": "1"},
        "task": {"task_id": TASK_ID, "task_version": TASK_VERSION,
                 "instance_id": "two-terminal-independent-goals-v1",
                 "condition": report["condition"], "seed": report["repeat"],
                 "schedule": report["schedule"]},
        "actors": report["actors"],
        "evaluator": {"class": "TrackAFocusEvaluatorV1", "hidden_state_access": "post_episode_only"},
        "environment": {"release": "osworld-v2.1", "adapter": "OSWorldSharedEpisode",
                         "guest_image": str(GUEST_IMAGE), "guest_image_size_bytes": GUEST_IMAGE.stat().st_size,
                         "runtime_image": RUNTIME_IMAGE, "runtime_image_id": runtime_id,
                         "release_manifest_sha256": release_sha,
                         "desktop_bindings": report["desktop_bindings"],
                         "overlay_files": overlays},
        "resources": {"run_id": os.environ["SWCUB_RUN_ID"],
                      "owner_labels": ensure_resource_identity(ledger).labels,
                      "ledger_path": str(ledger.resolve()),
                      "ledger_sha256": sha256_file(ledger),
                      "lifecycle": report["resource_lifecycle"]},
        "source": {"repository": git_source_state(), "sha256": source_hashes},
        "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        "model": None,
        "artifact_sha256": artifact_hashes,
    }
    (out / "provenance.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")


def run_episode(out: Path, condition: str, repeat: int, solo_actor: str | None = None) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=False)
    configure_episode_identity(out)
    identity = ensure_resource_identity(out / "resource-events.jsonl")
    log = EventLog()
    raw_environments: dict[str, tuple[OSWorldSharedEpisode, DesktopEnv]] = {}
    report: dict[str, Any] = {
        "task_id": TASK_ID, "task_version": TASK_VERSION,
        "scenario": condition, "condition": condition, "repeat": repeat,
        "started_utc": utc_now(), "resource_run_id": identity.run_id,
        "resource_ledger": str(identity.ledger_path),
        "model": None, "reset_check": {"success": False},
    }
    try:
        if condition == "solo":
            assert solo_actor in {"document_actor", "chat_actor"}
            bindings = {"document_actor": "document_desktop" if solo_actor == "document_actor" else "inactive",
                        "chat_actor": "chat_desktop" if solo_actor == "chat_actor" else "inactive"}
            selected = solo_actor
            binding = bindings[selected]
            episode, desktop = make_environment(binding, log)
            raw_environments[binding] = (episode, desktop)
            setup_focus_desktop(episode, desktop)
            active_actors = [selected]
            schedule = (["document_actor", "document_actor"] if selected == "document_actor"
                        else ["chat_actor"])
            actor_bindings = {selected: binding}
        elif condition == "ma_id":
            active_actors = ["document_actor", "chat_actor"]
            actor_bindings = {"document_actor": "document_desktop", "chat_actor": "chat_desktop"}
            for binding in ("document_desktop", "chat_desktop"):
                episode, desktop = make_environment(binding, log)
                raw_environments[binding] = (episode, desktop)
                setup_focus_desktop(episode, desktop)
            schedule = ["document_actor", "chat_actor", "document_actor"]
        elif condition == "ma_sd":
            active_actors = ["document_actor", "chat_actor"]
            actor_bindings = {"document_actor": "shared_desktop", "chat_actor": "shared_desktop"}
            episode, desktop = make_environment("shared_desktop", log)
            raw_environments["shared_desktop"] = (episode, desktop)
            setup_focus_desktop(episode, desktop)
            schedule = ["document_actor", "chat_actor", "document_actor"]
        else:
            raise ValueError(f"unknown Track A condition {condition!r}")

        environments = BoundEnvironments({key: pair[0] for key, pair in raw_environments.items()})
        environments.actor_bindings = actor_bindings  # type: ignore[attr-defined]
        for binding, (episode, _) in raw_environments.items():
            episode.copy_artifacts(out / "screenshots" / binding)
        actor_results = run_schedule(environments, actor_bindings, active_actors, schedule, log)
        report.update({"actors": {actor_id: {
                            "class": "ScriptedDocumentActor" if actor_id == "document_actor" else "ScriptedChatActor",
                            "role": "gui_agent", "goal": EXPECTED_VALUES[actor_id][1].strip(),
                            **actor_results[actor_id]}
                            for actor_id in active_actors},
                       "active_actors": active_actors,
                       "actor_bindings": actor_bindings,
                       "schedule": schedule,
                       "desktop_bindings": {binding: active_ids(episode)
                                            for binding, (episode, _) in raw_environments.items()}})
        evaluation = TrackAFocusEvaluatorV1().evaluate(environments, active_actors,
                                                       actor_bindings, log.events)
        report.update({"evaluation": evaluation,
                       "interaction_metrics": {
                           "focus_transition_count": len(evaluation["focus_transitions"]),
                           "keyboard_action_count": len(evaluation["keyboard_routing"]),
                           "misrouted_keyboard_action_count": evaluation["contamination_count"],
                           "contamination_event_count": evaluation["contamination_count"],
                           "actor_action_count": sum(1 for event in log.events
                               if event.kind == "gui" and event.actor in active_actors),
                           "total_logged_actions": sum(1 for event in log.events
                               if event.actor in active_actors and event.kind == "gui"),
                       }})
        task_guest_ids = {binding: pair[0].snapshot().get("guest_container_id")
                          for binding, pair in raw_environments.items()}
        report["task_guest_container_ids"] = task_guest_ids

        # A conflict is a valid Track A negative outcome only when the
        # Document actor's keyboard input was observed in Chat and the
        # programmatic goals/integrity evaluator rejected the final state.
        reproduced = any(row["actor_id"] == "document_actor"
                         and row["intended_window"] == "Document"
                         and row["routed_window"] is not None
                         and "chat" in row["routed_window"].lower()
                         for row in evaluation["contamination_events"])
        if condition == "ma_sd":
            scenario_success = reproduced and not evaluation["joint_success"]
            report["scenario_outcome"] = ("shared_focus_conflict_detected" if scenario_success
                                          else "expected_shared_focus_conflict_not_detected")
        else:
            scenario_success = bool(evaluation["joint_success"])
            report["scenario_outcome"] = "goals_pass" if scenario_success else "unexpected_goal_failure"
        report["scenario_success"] = scenario_success

        # Preserve task screenshots and evaluator output before clean reset.
        for binding, (episode, _) in raw_environments.items():
            episode.copy_artifacts(out / "screenshots" / binding)

        reset_bindings: dict[str, Any] = {}
        reset_ok = True
        for binding, (episode, desktop) in raw_environments.items():
            before_reset = episode.snapshot()
            old_id = before_reset.get("guest_container_id")
            episode.reset(task_config=None)
            wait_for_desktop(episode, desktop)
            clean_screen = episode.refresh_observation(source="reset_check")
            output = guest_command(desktop, ["bash", "-lc",
                "if test ! -e /tmp/codesk_track_a_document.txt && "
                "test ! -e /tmp/codesk_track_a_chat.txt; "
                "then echo reset-clean; else echo reset-dirty; fi"])
            new_snapshot = episode.snapshot()
            new_id = new_snapshot.get("guest_container_id")
            binding_ok = output.strip() == "reset-clean" and bool(old_id) and old_id != new_id
            reset_ok = reset_ok and binding_ok
            log.record("evaluator", "reset_check", "track_a.clean_reset", before_reset,
                       new_snapshot, outcome="pass" if binding_ok else "fail",
                       details={"desktop_binding": binding,
                                "previous_guest_container_id": old_id,
                                "new_guest_container_id": new_id,
                                "task_files_absent": output.strip() == "reset-clean"})
            episode.copy_artifacts(out / "reset-check" / binding)
            reset_bindings[binding] = {"success": binding_ok,
                                       "previous_guest_container_id": old_id,
                                       "new_guest_container_id": new_id,
                                       "task_files_absent": output.strip() == "reset-clean",
                                       "reset_screenshot_bytes": len(clean_screen.get("screenshot", b""))}
        report["reset_check"] = {"success": reset_ok, "desktop_bindings": reset_bindings}
        report["environment_health"] = {
            binding: dict(episode.environment_health)
            for binding, (episode, _) in raw_environments.items()
        }
        report["readiness_retry_count"] = sum(
            item.get("readiness_retry_count", 0)
            for item in report["environment_health"].values())
        report["transient_observation_failure_count"] = sum(
            item.get("observation_transient_failures", 0)
            for item in report["environment_health"].values())
        report["transient_accessibility_failure_count"] = sum(
            item.get("readiness_accessibility_failures", 0)
            + item.get("accessibility_tree_failures", 0)
            for item in report["environment_health"].values())

        for binding, (episode, _) in raw_environments.items():
            log.record("environment", "lifecycle", "track_a.close_after_reset",
                       episode.snapshot(), episode.snapshot(),
                       details={"desktop_binding": binding,
                                "guest_container_id": episode.snapshot().get("guest_container_id")})
            episode.close()
        raw_environments.clear()

        ledger_state = verify_ledger(identity.ledger_path)
        report["resource_lifecycle"] = ledger_state
        report["success"] = bool(scenario_success and reset_ok and
                                  ledger_state["all_containers_have_destroy_record"] and
                                  ledger_state["labels_consistent"])
        report["finished_utc"] = utc_now()
        log.write(out / "events.jsonl")
        report_path = out / "report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        source_files = [ROOT / "tasks/codesk_track_a_v1.json",
                        ROOT / "swcub/tasks/track_a.py",
                        ROOT / "scripts/run_track_a_v1.py",
                        ROOT / "swcub/osworld_adapter.py",
                        ROOT / "swcub/environment.py"]
        write_provenance(out, report, source_files)
        return report
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["environment_health"] = {
            binding: dict(episode.environment_health)
            for binding, (episode, _) in raw_environments.items()
        }
        report["readiness_retry_count"] = sum(
            1 for event in log.events if event.action == "guest.readiness_retry")
        report["transient_observation_failure_count"] = sum(
            1 for event in log.events if event.action == "osworld.observation_retry")
        report["transient_accessibility_failure_count"] = sum(
            1 for event in log.events
            if event.action == "osworld.observation_retry"
            or (event.action == "guest.readiness_retry"
                and "accessibility" in str(event.details.get("reason", "")).lower()))
        report["finished_utc"] = utc_now()
        log.record("runner", "failure", "track_a.episode_error", {"failed": False},
                   {"failed": True}, outcome="failed",
                   details={"error": report["error"]})
        for binding, (episode, _) in raw_environments.items():
            try:
                episode.copy_artifacts(out / "partial-artifacts" / binding)
            except Exception as artifact_exc:
                report.setdefault("artifact_errors", []).append(
                    f"{binding}: {type(artifact_exc).__name__}: {artifact_exc}")
            try:
                episode.close()
            except Exception as close_exc:
                report.setdefault("cleanup_errors", []).append(
                    f"{type(close_exc).__name__}: {close_exc}")
        raw_environments.clear()
        if (out / "resource-events.jsonl").is_file():
            report["resource_lifecycle"] = verify_ledger(out / "resource-events.jsonl")
        if log.events:
            log.write(out / "events.jsonl")
        (out / "error.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
        raise


def build_plan(repeats: int) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    # Five solo episodes per actor makes both independent goals directly auditable.
    for actor_id in ("document_actor", "chat_actor"):
        for repeat in range(1, repeats + 1):
            plan.append({"condition": "solo", "solo_actor": actor_id, "repeat": repeat,
                         "relative_dir": f"solo/{actor_id}/repeat-{repeat:02d}"})
    for condition in ("ma_id", "ma_sd"):
        for repeat in range(1, repeats + 1):
            plan.append({"condition": condition, "solo_actor": None, "repeat": repeat,
                         "relative_dir": f"{condition}/repeat-{repeat:02d}"})
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-parent", type=Path,
                        default=Path(os.environ.get("CODESK_TRACK_A_ARTIFACT_PARENT",
                                                  str(DEFAULT_ARTIFACT_PARENT))))
    parser.add_argument("--run-id", default=f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--repeats", type=int, default=5,
                        help="Repeats per actor for Solo and per condition for MA-ID/MA-SD")
    parser.add_argument("--only", choices=("all", "solo", "solo_chat", "ma_id", "ma_sd"), default="all",
                        help="Run one condition; solo_chat selects only the independent Chat actor baseline")
    parser.add_argument("--limit-episodes", type=int,
                        help="Optional pilot/resume slice; the full matrix is used when omitted")
    parser.add_argument("--start-repeat", type=int, default=1,
                        help="Start from this repeat number within the selected condition/actor")
    args = parser.parse_args()
    if args.repeats < 5:
        parser.error("Track A requires at least five repeats per condition/solo actor")
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,80}", args.run_id):
        parser.error("--run-id must contain 8-80 safe ASCII letters, digits, dot, underscore or hyphen")
    if not GUEST_IMAGE.is_file():
        parser.error(f"pinned OSWorld Guest image is unavailable: {GUEST_IMAGE}")
    if not RELEASE_MANIFEST.is_file():
        parser.error(f"pinned OSWorld release manifest is unavailable: {RELEASE_MANIFEST}")
    root = args.artifact_parent.resolve() / args.run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "run-owner-marker.json").write_text(json.dumps({
        "project": "CoDesk", "task_id": TASK_ID, "run_id": args.run_id,
        "created_utc": utc_now(), "purpose": "Track A scripted validation artifacts",
        "preserve": True,
    }, indent=2) + "\n", encoding="utf-8")
    progress = root / "matrix_progress.jsonl"
    results: list[dict[str, Any]] = []
    plan = build_plan(args.repeats)
    if args.start_repeat < 1 or args.start_repeat > args.repeats:
        parser.error("--start-repeat must be between 1 and --repeats")
    if args.only == "solo_chat":
        plan = [item for item in plan
                if item["condition"] == "solo" and item["solo_actor"] == "chat_actor"]
    elif args.only != "all":
        plan = [item for item in plan if item["condition"] == args.only]
    plan = [item for item in plan if item["repeat"] >= args.start_repeat]
    if args.limit_episodes is not None:
        if args.limit_episodes < 1:
            parser.error("--limit-episodes must be positive")
        plan = plan[:args.limit_episodes]
    for item in plan:
        out = root / item["relative_dir"]
        try:
            report = run_episode(out, item["condition"], item["repeat"], item["solo_actor"])
            row = {"condition": item["condition"], "solo_actor": item["solo_actor"],
                   "repeat": item["repeat"], "episode_dir": str(out),
                   "success": report.get("success"),
                   "evaluation_success": (report.get("evaluation") or {}).get("success"),
                   "scenario_outcome": report.get("scenario_outcome"),
                   "reset_success": (report.get("reset_check") or {}).get("success"),
                   "guest_count": (report.get("resource_lifecycle") or {}).get("container_count")}
        except Exception as exc:
            row = {"condition": item["condition"], "solo_actor": item["solo_actor"],
                   "repeat": item["repeat"], "episode_dir": str(out),
                   "success": False, "error": f"{type(exc).__name__}: {exc}"}
        results.append(row)
        with progress.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {"task_id": TASK_ID, "task_version": TASK_VERSION,
               "run_id": args.run_id, "artifact_root": str(root),
               "requested_repeats": args.repeats,
               "selected_episode_count": len(plan),
               "completed_episodes": len(results), "results": results,
               "all_scenario_checks_passed": bool(results) and all(r.get("success") for r in results),
               "finished_utc": utc_now()}
    (root / "matrix_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    return 0 if summary["all_scenario_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
