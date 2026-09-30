#!/usr/bin/env python3
"""Config-driven episode coordinator for the currently registered Track A family."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swcub.runner.config import load_config, write_json

TRACK_A_RUNNER = ROOT / "scripts/run_track_a_v1.sh"
OFFICE_RUNNER = ROOT / "scripts/run_writer_calc_v1.sh"
DEFAULT_ARTIFACT_ROOT = Path("/mnt/raid1/mjh/CoDesk-V1-artifacts/experiments")
TASK_ID = "CODESK-TA-GUI-FOCUS-001"
TASK_VERSION = "1.0.0"
FAMILY_TASKS = {"track_a_v1": (TASK_ID, TASK_VERSION),
                "writer_calc_v1": ("CODESK-TA-OFFICE-001", "1.0.0")}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_snapshot() -> dict[str, Any]:
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemAvailable", "SwapFree"}:
                memory[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    try:
        load = list(os.getloadavg())
    except OSError:
        load = None
    return {"timestamp_utc": now_utc(), "logical_cpus": os.cpu_count(),
            "load_average_1_5_15": load, "memory_bytes": memory}


def guest_slots(spec: dict[str, Any], task_family: str) -> int:
    if spec["condition"] == "ma_id":
        return 2
    if task_family == "writer_calc_v1" and spec["condition"] == "solo":
        return 2  # paired Solo controls, one independent Guest per actor
    return 1


def make_specs(config: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    specs = []
    for index, item in enumerate(config["episodes"], start=1):
        condition = item["condition"]
        repeat = item["repeat"]
        run_id = f"ev1-{config['experiment_id']}-{index:04d}-{condition}-r{repeat:02d}"
        selector = ({"solo_document": "solo", "solo_chat": "solo_chat",
                     "ma_id": "ma_id", "ma_sd": "ma_sd"}[condition]
                    if config["task_family"] == "track_a_v1" else condition)
        task_id, task_version = FAMILY_TASKS[config["task_family"]]
        job_id = f"{index:04d}-{condition}-r{repeat:02d}"
        specs.append({"queue_index": index, "job_id": job_id,
                      "task_family": config["task_family"], "task_id": task_id,
                      "task_version": task_version, "condition": condition,
                      "backend_topology": config.get(
                          "backend_topology", "legacy_per_actor_clone"),
                      "selector": selector, "repeat": repeat, "run_id": run_id,
                      "guest_slots": guest_slots(item, config["task_family"]),
                      "artifact_parent": str(root / "episodes" / job_id),
                      "worker_log": str(root / "worker-logs" / f"{job_id}.log")})
    return specs


def worker(spec: dict[str, Any]) -> dict[str, Any]:
    artifact_parent = Path(spec["artifact_parent"])
    artifact_parent.mkdir(parents=True, exist_ok=False)
    log_path = Path(spec["worker_log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in ("SWCUB_RUN_ID", "SWCUB_OWNER_TOKEN", "SWCUB_RESOURCE_LEDGER",
                 "SWCUB_RESOURCE_IDENTITY_INITIALIZED"):
        env.pop(name, None)
    if spec["task_family"] == "writer_calc_v1":
        env["SWCUB_BACKEND_TOPOLOGY"] = spec["backend_topology"]
    if spec["task_family"] == "track_a_v1":
        env["CODESK_TRACK_A_ARTIFACT_PARENT"] = str(artifact_parent)
        command = ["bash", str(TRACK_A_RUNNER), "--run-id", spec["run_id"],
                   "--repeats", "5", "--only", spec["selector"],
                   "--start-repeat", str(spec["repeat"]), "--limit-episodes", "1"]
    else:
        env["CODESK_OFFICE_ARTIFACT_PARENT"] = str(artifact_parent)
        command = ["bash", str(OFFICE_RUNNER), "--run-id", spec["run_id"],
                   "--condition", spec["condition"], "--repeat", str(spec["repeat"]),
                   "--artifact-parent", str(artifact_parent)]
    start = time.monotonic()
    started_utc = now_utc()
    host_start = host_snapshot()
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        return_code = process.wait()
    return {**spec, "worker_pid": os.getpid(), "runner_pid": process.pid,
            "started_utc": started_utc, "finished_utc": now_utc(),
            "runtime_seconds": round(time.monotonic() - start, 3),
            "host_start": host_start, "host_finish": host_snapshot(),
            "exit_code": return_code, "worker_log": str(log_path)}


def report_path(spec: dict[str, Any]) -> Path:
    if spec["task_family"] == "writer_calc_v1":
        return Path(spec["artifact_parent"]) / spec["run_id"] / "report.json"
    base = Path(spec["artifact_parent"]) / spec["run_id"]
    relative = {"solo_document": "solo/document_actor",
                "solo_chat": "solo/chat_actor",
                "ma_id": "ma_id", "ma_sd": "ma_sd"}[spec["condition"]]
    return base / relative / f"repeat-{spec['repeat']:02d}" / "report.json"


def verify_episode(spec: dict[str, Any], worker_result: dict[str, Any]) -> dict[str, Any]:
    path = report_path(spec)
    result = {"job_id": spec["job_id"], "run_id": spec["run_id"],
              "condition": spec["condition"], "repeat": spec["repeat"],
              "report_path": str(path), "artifact_integrity": False,
              "episode_status": "missing_artifact", "scenario_success": None,
              "reset_success": None,
              "missing": [], "hash_mismatches": [],
              "worker_exit_code": worker_result.get("exit_code")}
    error_path = path.parent / "error.json"
    source_path = path if path.is_file() else error_path
    required = [path, path.parent / "events.jsonl", path.parent / "provenance.json",
                path.parent / "resource-events.jsonl", path.parent / "run-owner-marker.json"]
    if not path.is_file() and error_path.is_file():
        required[0] = error_path
        result["report_path"] = str(error_path)
    result["missing"] = [str(item) for item in required if not item.is_file()]
    if result["missing"]:
        result["episode_status"] = "artifact_incomplete"
        return result
    report = json.loads(source_path.read_text(encoding="utf-8"))
    provenance = json.loads((path.parent / "provenance.json").read_text(encoding="utf-8"))
    expected_condition = ("solo" if spec["condition"].startswith("solo_") else spec["condition"])
    contract = (report.get("task_id") == spec["task_id"]
                and report.get("task_version") == spec["task_version"]
                and report.get("condition") == expected_condition
                and report.get("repeat") == spec["repeat"])
    hash_mismatches = []
    for relative, expected in provenance.get("artifact_sha256", {}).items():
        artifact = path.parent / relative
        if not artifact.is_file():
            result["missing"].append(str(artifact))
            continue
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != expected:
            hash_mismatches.append(relative)
    provenance_valid = (provenance.get("task", {}).get("task_id") == spec["task_id"]
                        and provenance.get("task", {}).get("task_version") == spec["task_version"]
                        and provenance.get("model") is None
                        and bool(provenance.get("artifact_sha256")))
    lifecycle = report.get("resource_lifecycle", {})
    if spec["task_family"] == "writer_calc_v1":
        resource_lifecycle_valid = (lifecycle.get("labels_consistent") is True
            and lifecycle.get("all_containers_have_destroy_record") is True)
    else:
        resource_lifecycle_valid = (lifecycle.get("labels_consistent") is True
            and lifecycle.get("all_containers_have_destroy_record") is True)
    report_status = report.get("episode_status", "complete" if path.is_file() else "runtime_failed")
    scenario_value = report.get("scenario_success")
    if report_status == "readiness_failed":
        scenario_value = None
    elif scenario_value is None:
        scenario_value = False
    result.update({"episode_status": report_status,
                   "failure_stage": report.get("failure_stage"),
                   "failure": report.get("error"),
                   "report_contract_valid": contract,
                   "scenario_success": scenario_value,
                   "scenario_outcome": report.get("scenario_outcome"),
                   "reset_success": (report.get("reset_check", {}).get("success")
                                     if "reset_check" in report else None),
                   "resource_lifecycle_valid": resource_lifecycle_valid,
                   "provenance_valid": provenance_valid,
                   "hash_mismatches": hash_mismatches,
                   "artifact_integrity": bool(contract and provenance_valid
                                               and resource_lifecycle_valid
                                               and not result["missing"] and not hash_mismatches),
                   "episode_latency_seconds": (round((datetime.fromisoformat(report["finished_utc"])
                         - datetime.fromisoformat(report["started_utc"])).total_seconds(), 3)
                         if report.get("finished_utc") and report.get("started_utc") else None),
                   "environment_health": report.get("environment_health", {}),
                   "worker_exit_code": worker_result.get("exit_code")})
    return result


def allocate(specs: list[dict[str, Any]], config: dict[str, Any], root: Path) -> dict[str, Any]:
    max_workers = config.get("max_workers", 1)
    guest_capacity = config.get("max_concurrent_guests", 2)
    stagger = float(config.get("startup_stagger_seconds", 15))
    pending = list(specs)
    active: dict[Any, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    used_slots = 0
    last_submit = 0.0
    host_samples: list[dict[str, Any]] = [host_snapshot()]
    stop_sampler = threading.Event()

    def sample() -> None:
        while not stop_sampler.wait(5):
            host_samples.append(host_snapshot())

    sampler = threading.Thread(target=sample, name="codesk-host-sampler", daemon=True)
    sampler.start()
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            while pending or active:
                launched = False
                for index, spec in enumerate(pending):
                    if len(active) >= max_workers or used_slots + spec["guest_slots"] > guest_capacity:
                        continue
                    delay = stagger - (time.monotonic() - last_submit) if active else 0
                    if delay > 0:
                        time.sleep(delay)
                    future = pool.submit(worker, spec)
                    active[future] = spec
                    used_slots += spec["guest_slots"]
                    pending.pop(index)
                    last_submit = time.monotonic()
                    launched = True
                    break
                if active and (not launched or len(active) >= max_workers or not pending):
                    done, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in done:
                        spec = active.pop(future)
                        used_slots -= spec["guest_slots"]
                        try:
                            results.append(future.result())
                        except Exception as exc:
                            results.append({**spec, "exit_code": None,
                                            "worker_error": f"{type(exc).__name__}: {exc}"})
                elif pending and not launched:
                    raise RuntimeError("queue has no episode that fits max_concurrent_guests")
    finally:
        stop_sampler.set()
        sampler.join(timeout=10)
    host_samples.append(host_snapshot())
    results.sort(key=lambda item: item["queue_index"])
    episodes = []
    for spec in specs:
        result = next((item for item in results if item.get("job_id") == spec["job_id"]), {})
        episodes.append(verify_episode(spec, result))
    latencies = [item["episode_latency_seconds"] for item in episodes
                 if "episode_latency_seconds" in item]
    reset_checked = [item for item in episodes if item.get("reset_success") is not None]
    reset = [item.get("reset_success") is True for item in reset_checked]
    artifacts = [item.get("artifact_integrity") is True for item in episodes]
    valid_scenarios = [item for item in episodes
                       if item.get("episode_status") == "complete"]
    scenarios = [item.get("scenario_success") is True for item in valid_scenarios]
    readiness_failures = [item for item in episodes
                          if item.get("episode_status") == "readiness_failed"]
    return {"started_utc": host_samples[0]["timestamp_utc"], "finished_utc": now_utc(),
            "worker_results": results, "episodes": episodes, "host_samples": host_samples,
            "episode_latency_seconds": latencies,
            "episode_latency_median_seconds": round(statistics.median(latencies), 3) if latencies else None,
            "reset_success_count": sum(reset), "reset_episode_count": len(reset_checked),
            "artifact_integrity_count": sum(artifacts), "artifact_episode_count": len(artifacts),
            "scenario_success_count": sum(scenarios), "scenario_episode_count": len(valid_scenarios),
            "planned_episode_count": len(episodes),
            "readiness_failure_count": len(readiness_failures),
            "scenario_failure_count": sum(item.get("scenario_success") is False
                                           for item in valid_scenarios)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Version 1 experiment JSON")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate and print the episode plan without creating artifacts or Guests")
    args = parser.parse_args()
    config = load_config(args.config)
    artifact_root = Path(config["artifact_root"]).expanduser().resolve()
    run_root = artifact_root / config["experiment_id"]
    specs = make_specs(config, run_root)
    if args.validate_only:
        print(json.dumps({"experiment_id": config["experiment_id"], "episode_count": len(specs),
                          "worker_count": config.get("max_workers", 1),
                          "guest_slots_required": max(spec["guest_slots"] for spec in specs),
                          "episodes": specs}, indent=2))
        return 0
    run_root.mkdir(parents=True, exist_ok=False)
    write_json(run_root / "experiment_config.json", config)
    write_json(run_root / "experiment_owner_marker.json", {
        "project": "CoDesk", "experiment_id": config["experiment_id"],
        "created_utc": now_utc(), "purpose": "Preserved benchmark experiment artifacts"})
    specs = make_specs(config, run_root)
    start = time.monotonic()
    results = allocate(specs, config, run_root)
    task_id, task_version = FAMILY_TASKS[config["task_family"]]
    results.update({"schema_version": 1, "experiment_id": config["experiment_id"],
                    "task_family": config["task_family"], "task_id": task_id,
                    "task_version": task_version, "conditions": config["episodes"],
                    "max_workers": config.get("max_workers", 1),
                    "max_concurrent_guests": config.get("max_concurrent_guests", 2),
                    "startup_stagger_seconds": config.get("startup_stagger_seconds", 15),
                    "wall_clock_seconds": round(time.monotonic() - start, 3),
                    "artifact_root": str(run_root)})
    write_json(run_root / "experiment_summary.json", results)
    print(json.dumps({"experiment_summary": str(run_root / "experiment_summary.json"),
                      "wall_clock_seconds": results["wall_clock_seconds"],
                      "scenario_success": f"{results['scenario_success_count']}/{results['scenario_episode_count']}",
                      "planned_episodes": results["planned_episode_count"],
                      "readiness_failures_excluded_from_scenario_denominator":
                          results["readiness_failure_count"],
                      "scenario_failures": results["scenario_failure_count"],
                      "reset_success": f"{results['reset_success_count']}/{results['reset_episode_count']}",
                      "artifact_integrity": f"{results['artifact_integrity_count']}/{results['artifact_episode_count']}"}))
    return 0 if results["reset_success_count"] == len(specs) and \
        results["artifact_integrity_count"] == len(specs) and \
        results["scenario_success_count"] == results["scenario_episode_count"] and \
        results["scenario_episode_count"] == len(specs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
