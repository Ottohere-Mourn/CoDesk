#!/usr/bin/env python3
"""Compare serial and two-process execution of the same Track A episodes."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import threading
import time
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_track_a_v1.sh"
DEFAULT_ARTIFACT_ROOT = Path("/mnt/raid1/mjh/CoDesk-V1-artifacts/parallel-pilot")
TASK_ID = "CODESK-TA-GUI-FOCUS-001"
TASK_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def host_snapshot() -> dict[str, Any]:
    mem: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value = line.split(":", 1)
            if key in {"MemAvailable", "SwapTotal", "SwapFree"}:
                mem[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    try:
        load = os.getloadavg()
    except OSError:
        load = None
    return {"timestamp_utc": utc_now(), "logical_cpus": os.cpu_count(),
            "load_average_1_5_15": list(load) if load else None,
            "memory_bytes": mem}


def job_spec(pilot_id: str, mode: str, condition: str, repeat: int,
             artifact_root: Path) -> dict[str, Any]:
    selector = {"solo_document": "solo", "solo_chat": "solo_chat",
                "ma_id": "ma_id", "ma_sd": "ma_sd"}[condition]
    safe_pilot_id = pilot_id[:30]
    run_id = f"tp-{safe_pilot_id}-{mode}-{condition}-r{repeat:02d}"
    return {"pilot_id": pilot_id, "mode": mode, "condition": condition,
            "selector": selector, "repeat": repeat, "run_id": run_id,
            "artifact_parent": str(artifact_root / mode),
            "submitted_utc": utc_now()}


def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    """One worker owns one runner subprocess and a unique run/artifact root."""
    parent = Path(job["artifact_parent"])
    parent.mkdir(parents=True, exist_ok=True)
    log_path = parent / "worker-logs" / f"{job['run_id']}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CODESK_TRACK_A_ARTIFACT_PARENT"] = str(parent)
    command = ["bash", str(RUNNER), "--run-id", job["run_id"],
               "--repeats", "5", "--only", job["selector"],
               "--start-repeat", str(job["repeat"]), "--limit-episodes", "1"]
    start_utc = utc_now()
    start = time.monotonic()
    host_start = host_snapshot()
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        runner_pid = process.pid
        return_code = process.wait()
    end_utc = utc_now()
    return {**job, "worker_pid": os.getpid(), "runner_pid": runner_pid,
            "worker_started_utc": start_utc, "worker_finished_utc": end_utc,
            "host_start": host_start, "host_finish": host_snapshot(),
            "worker_runtime_seconds": round(time.monotonic() - start, 3),
            "exit_code": return_code, "worker_log": str(log_path)}


def report_path(job: dict[str, Any]) -> Path:
    episode_dir = Path(job["artifact_parent"]) / job["run_id"] / job["selector"]
    # Runner writes Solo under solo/<actor>/repeat-N and paired tasks under
    # <condition>/repeat-N. Keep path derivation explicit to avoid globs.
    if job["condition"] == "solo_document":
        episode_dir = Path(job["artifact_parent"]) / job["run_id"] / "solo/document_actor"
    elif job["condition"] == "solo_chat":
        episode_dir = Path(job["artifact_parent"]) / job["run_id"] / "solo/chat_actor"
    elif job["condition"] == "ma_id":
        episode_dir = Path(job["artifact_parent"]) / job["run_id"] / "ma_id"
    else:
        episode_dir = Path(job["artifact_parent"]) / job["run_id"] / "ma_sd"
    return episode_dir / f"repeat-{job['repeat']:02d}" / "report.json"


def verify_artifacts(job: dict[str, Any], worker_result: dict[str, Any]) -> dict[str, Any]:
    rp = report_path(job)
    result: dict[str, Any] = {"episode_dir": str(rp.parent), "correct": False,
                              "missing": [], "hash_mismatches": []}
    required = [rp, rp.parent / "events.jsonl", rp.parent / "provenance.json",
                rp.parent / "resource-events.jsonl", rp.parent / "run-owner-marker.json"]
    result["missing"] = [str(path) for path in required if not path.is_file()]
    if result["missing"]:
        result["worker_exit_code"] = worker_result.get("exit_code")
        return result
    report = json.loads(rp.read_text(encoding="utf-8"))
    provenance = json.loads((rp.parent / "provenance.json").read_text(encoding="utf-8"))
    environment_health = report.get("environment_health", {})
    accessibility_failures = sum(
        int(health.get("readiness_accessibility_failures", 0))
        + int(health.get("accessibility_tree_failures", 0))
        for health in environment_health.values())
    observation_failures = sum(int(health.get("observation_transient_failures", 0))
                               for health in environment_health.values())
    readiness_retries = sum(int(health.get("readiness_retry_count", 0))
                            for health in environment_health.values())
    expected_condition = "solo" if job["condition"].startswith("solo_") else job["condition"]
    report_contract_ok = (report.get("task_id") == TASK_ID
                 and report.get("task_version") == TASK_VERSION
                 and report.get("condition") == expected_condition
                 and report.get("repeat") == job["repeat"])
    reset_ok = (report.get("reset_check", {}).get("success") is True
                 and report.get("resource_lifecycle", {}).get("labels_consistent") is True
                 and report.get("resource_lifecycle", {}).get("all_containers_have_destroy_record") is True)
    scenario_ok = report.get("scenario_success") is True
    prov_ok = (provenance.get("task", {}).get("task_id") == TASK_ID
               and provenance.get("task", {}).get("task_version") == TASK_VERSION
               and provenance.get("model") is None
               and bool(provenance.get("artifact_sha256")))
    mismatches = []
    for relative_path, expected in provenance.get("artifact_sha256", {}).items():
        path = rp.parent / relative_path
        if not path.is_file():
            result["missing"].append(str(path))
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            mismatches.append(relative_path)
    artifact_integrity_ok = bool(report_contract_ok and prov_ok and not result["missing"]
                                 and not mismatches)
    result.update({"report_contract_valid": report_contract_ok,
                   "scenario_success": report.get("scenario_success") is True,
                   "episode_success": report.get("success") is True,
                   "scenario_outcome_valid": scenario_ok,
                   "reset_lifecycle_valid": reset_ok,
                   "artifact_integrity_valid": artifact_integrity_ok,
                   "report_valid": report_contract_ok, "provenance_valid": prov_ok,
                   "artifact_hash_count": len(provenance.get("artifact_sha256", {})),
                   "screenshot_count": sum(1 for name in provenance.get("artifact_sha256", {})
                                           if name.startswith("screenshots/")
                                           or name.startswith("reset-check/")),
                   "hash_mismatches": mismatches,
                   "worker_exit_code": worker_result.get("exit_code"),
                   "correct": artifact_integrity_ok})
    result["episode_latency_seconds"] = round(
        (datetime.fromisoformat(report["finished_utc"])
         - datetime.fromisoformat(report["started_utc"])).total_seconds(), 3)
    result["reset_success"] = report.get("reset_check", {}).get("success") is True
    result["scenario_outcome"] = report.get("scenario_outcome")
    result["transient_failure_count"] = accessibility_failures + observation_failures
    result["transient_accessibility_failure_count"] = accessibility_failures
    result["transient_observation_failure_count"] = observation_failures
    result["boot_readiness_retry_count"] = readiness_retries
    result["joint_goal_success"] = report.get("evaluation", {}).get("joint_success")
    result["condition"] = report.get("condition")
    result["repeat"] = report.get("repeat")
    return result


def readiness_latencies(job: dict[str, Any]) -> list[dict[str, Any]]:
    rp = report_path(job)
    if not rp.is_file():
        return []
    episode_dir = rp.parent
    report = json.loads(rp.read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (episode_dir / "events.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    resources = [json.loads(line) for line in (episode_dir / "resource-events.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    created = {row["resource_id"]: row["timestamp_utc"] for row in resources
               if row.get("event") == "created" and row.get("resource_type") == "container"}
    ready = {event.get("details", {}).get("guest_container_id"): event["ts_utc"]
             for event in events if event.get("action") == "guest.desktop_ready"}
    task_ids = set((report.get("task_guest_container_ids") or {}).values())
    reset_ids = {entry.get("new_guest_container_id")
                 for entry in report.get("reset_check", {}).get("desktop_bindings", {}).values()}
    out = []
    for guest_id in sorted(task_ids | reset_ids):
        if guest_id in created and guest_id in ready:
            elapsed = (datetime.fromisoformat(ready[guest_id])
                       - datetime.fromisoformat(created[guest_id])).total_seconds()
            out.append({"guest_container_id": guest_id,
                        "phase": "task_guest" if guest_id in task_ids else "reset_guest",
                        "readiness_seconds": round(elapsed, 3)})
    return out


def run_mode(mode: str, jobs: list[dict[str, Any]], workers: int,
             startup_stagger_seconds: float = 0) -> dict[str, Any]:
    start_utc = utc_now()
    start = time.monotonic()
    results: list[dict[str, Any]] = []
    if mode == "sequential":
        results = [execute_job(job) for job in jobs]
    else:
        # The future set is the worker queue; only this coordinator aggregates results.
        host_samples = [host_snapshot()]
        stop_sampling = threading.Event()

        def sample_host() -> None:
            while not stop_sampling.wait(5):
                host_samples.append(host_snapshot())

        sampler = threading.Thread(target=sample_host, name="codesk-host-sampler", daemon=True)
        sampler.start()
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                future_map = {}
                for index, job in enumerate(jobs):
                    future_map[pool.submit(execute_job, job)] = job
                    if startup_stagger_seconds and index + 1 < len(jobs):
                        time.sleep(startup_stagger_seconds)
                for future in as_completed(future_map):
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        job = future_map[future]
                        results.append({**job, "exit_code": None,
                                        "worker_error": f"{type(exc).__name__}: {exc}"})
        finally:
            stop_sampling.set()
            sampler.join(timeout=10)
        host_samples.append(host_snapshot())
    if mode == "sequential":
        host_samples = []
    end_utc = utc_now()
    return {"mode": mode, "started_utc": start_utc, "finished_utc": end_utc,
            "wall_clock_seconds": round(time.monotonic() - start, 3),
            "worker_count": 1 if mode == "sequential" else workers,
            "startup_stagger_seconds": startup_stagger_seconds if mode != "sequential" else 0,
            "host_samples": host_samples,
            "jobs": results}


def summarize_mode(run: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    reports = []
    readiness = []
    for job in jobs:
        worker = next((row for row in run["jobs"] if row.get("run_id") == job["run_id"]), {})
        reports.append(verify_artifacts(job, worker))
        readiness.extend(readiness_latencies(job))
    episode_latencies = [row["episode_latency_seconds"] for row in reports
                         if "episode_latency_seconds" in row]
    resets = [row.get("reset_success") is True for row in reports if "reset_success" in row]
    transient_episodes = [row for row in reports
                          if row.get("transient_failure_count", 0) > 0]
    readiness_retry_episodes = [row for row in reports
                                if row.get("boot_readiness_retry_count", 0) > 0]
    run.update({"episode_reports": reports,
                "readiness": readiness,
                "episode_latency_median_seconds": round(statistics.median(episode_latencies), 3)
                if episode_latencies else None,
                "episode_latency_seconds": episode_latencies,
                "guest_readiness_median_seconds": round(statistics.median(
                    row["readiness_seconds"] for row in readiness), 3) if readiness else None,
                "reset_success_count": sum(resets), "reset_episode_count": len(resets),
                "reset_success_rate": sum(resets) / len(resets) if resets else None,
                "scenario_success_count": sum(row.get("scenario_success") is True for row in reports),
                "scenario_episode_count": len(reports),
                "transient_failure_count": sum(row.get("transient_failure_count", 0)
                                                for row in reports),
                "transient_failure_episode_count": len(transient_episodes),
                "transient_failure_rate": len(transient_episodes) / len(reports) if reports else None,
                "boot_readiness_retry_count": sum(row.get("boot_readiness_retry_count", 0)
                                                   for row in reports),
                "boot_readiness_retry_episode_count": len(readiness_retry_episodes),
                "artifact_correct_count": sum(row.get("correct") is True for row in reports),
                "artifact_episode_count": len(reports),
                "artifact_correct_rate": (sum(row.get("correct") is True for row in reports)
                                           / len(reports)) if reports else None})
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        + "-" + uuid.uuid4().hex[:6])
    parser.add_argument("--episodes", type=int, default=2,
                        help="Same number of matched repeats per mode (default: 2; maximum: 2)")
    parser.add_argument("--condition", choices=("solo_document", "solo_chat", "ma_id", "ma_sd"),
                        default="ma_sd")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--workers", type=int, default=2, choices=(2,))
    parser.add_argument("--startup-stagger-seconds", type=float, default=15,
                        help="Delay between submitting parallel Guest jobs (default: 15; max: 120)")
    parser.add_argument("--recheck-summary", type=Path,
                        help="Recompute integrity/reset/scenario checks from an existing pilot JSON; do not run Guests")
    args = parser.parse_args()
    if not 0 <= args.startup_stagger_seconds <= 120:
        parser.error("--startup-stagger-seconds must be between 0 and 120")
    if args.recheck_summary:
        summary_path = args.recheck_summary.resolve()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for key in ("sequential", "parallel_two_workers"):
            mode = summary[key]
            jobs = mode["jobs"]
            summary[key] = summarize_mode(mode, jobs)
        summary["posthoc_recheck_utc"] = utc_now()
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
        print(json.dumps({"pilot_summary": str(summary_path),
                          "sequential_artifact_integrity": summary["sequential"]["artifact_correct_count"],
                          "parallel_artifact_integrity": summary["parallel_two_workers"]["artifact_correct_count"],
                          "parallel_scenario_success": summary["parallel_two_workers"]["scenario_success_count"],
                          "parallel_transient_accessibility_failure_rate": (
                              summary["parallel_two_workers"]["transient_failure_rate"])},
                         ensure_ascii=False))
        return 0
    if args.episodes != 2:
        parser.error("this bounded prototype intentionally runs exactly two matched episodes per mode")
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,30}", args.pilot_id):
        parser.error("--pilot-id must contain 8-30 safe ASCII characters")
    pilot_started = utc_now()
    root = args.artifact_root.resolve() / args.pilot_id
    root.mkdir(parents=True, exist_ok=False)
    host_start = host_snapshot()
    (root / "pilot-owner-marker.json").write_text(json.dumps({
        "project": "CoDesk", "pilot_id": args.pilot_id, "created_utc": utc_now(),
        "purpose": "Sequential versus two-worker Track A pilot artifacts; preserve",
    }, indent=2) + "\n", encoding="utf-8")

    sequential_jobs = [job_spec(args.pilot_id, "sequential", args.condition, repeat, root / "artifacts")
                       for repeat in (1, 2)]
    parallel_jobs = [job_spec(args.pilot_id, "parallel2", args.condition, repeat, root / "artifacts")
                     for repeat in (1, 2)]
    # Run the serial baseline first, then the same repeats under two worker processes.
    sequential = run_mode("sequential", sequential_jobs, args.workers)
    sequential = summarize_mode(sequential, sequential_jobs)
    host_between_modes = host_snapshot()
    parallel = run_mode("parallel2", parallel_jobs, args.workers,
                        startup_stagger_seconds=args.startup_stagger_seconds)
    parallel = summarize_mode(parallel, parallel_jobs)
    host_end = host_snapshot()
    parallel_wall = parallel["wall_clock_seconds"]
    sequential_wall = sequential["wall_clock_seconds"]
    summary = {"pilot_id": args.pilot_id, "task_id": TASK_ID,
               "task_version": TASK_VERSION, "condition": args.condition,
               "episode_count_per_mode": args.episodes, "actor_order": [
                   "document_actor", "chat_actor", "document_actor"] if args.condition in ("ma_id", "ma_sd") else None,
               "created_utc": pilot_started, "finished_utc": utc_now(),
               "host_snapshots": {"start": host_start,
                                  "between_modes": host_between_modes,
                                  "end": host_end},
               "comparison": {
                   "wall_speedup_sequential_over_parallel": round(
                       sequential_wall / parallel_wall, 3) if parallel_wall > 0 else None,
                   "wall_time_reduction_percent": round(
                       100 * (1 - parallel_wall / sequential_wall), 2)
                       if sequential_wall > 0 else None,
                   "sequential_episodes_per_hour": round(
                       args.episodes * 3600 / sequential_wall, 3) if sequential_wall > 0 else None,
                   "parallel_episodes_per_hour": round(
                       args.episodes * 3600 / parallel_wall, 3) if parallel_wall > 0 else None,
               },
               "artifact_root": str(root), "sequential": sequential,
               "parallel_two_workers": parallel}
    summary_path = root / "pilot_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print(json.dumps({"pilot_summary": str(summary_path),
                      "sequential_wall_seconds": sequential["wall_clock_seconds"],
                      "parallel_wall_seconds": parallel["wall_clock_seconds"],
                      "sequential_reset_rate": sequential["reset_success_rate"],
                      "parallel_reset_rate": parallel["reset_success_rate"],
                          "sequential_artifacts_ok": sequential["artifact_correct_count"],
                      "parallel_artifacts_ok": parallel["artifact_correct_count"],
                      "sequential_scenarios_ok": sequential["scenario_success_count"],
                      "parallel_scenarios_ok": parallel["scenario_success_count"]}, ensure_ascii=False))
    return 0 if (sequential["reset_success_count"] == args.episodes
                 and parallel["reset_success_count"] == args.episodes
                 and sequential["artifact_correct_count"] == args.episodes
                 and parallel["artifact_correct_count"] == args.episodes
                 and sequential["scenario_success_count"] == args.episodes
                 and parallel["scenario_success_count"] == args.episodes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
