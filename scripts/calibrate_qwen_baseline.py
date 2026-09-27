#!/usr/bin/env python3
"""Run reproducible OSWorld V2.1 Qwen solo calibration trials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
V2_DIR = Path(os.environ.get(
    "OSWORLD_V2_DIR", ROOT.parent / "_deps/OSWorld-V2-osworld-v2.1")).resolve()
ARTIFACT_ROOT = Path(os.environ.get(
    "SWCUB_BASELINE_ARTIFACT_ROOT",
    "/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1"))
TASKS = {
    "writer": ("office", "writer-osworld-agent-solo"),
    "calc": ("office", "calc-osworld-agent-solo"),
    "browser": ("browser", "agent-qwen-solo"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=list(TASKS))
    parser.add_argument("--resume", action="store_true",
                        help="skip a trial only when its report.json already exists")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    if not V2_DIR.is_dir():
        parser.error(f"OSWorld V2.1 checkout does not exist: {V2_DIR}")

    env = os.environ.copy()
    env.update({
        "OSWORLD_V2_DIR": str(V2_DIR),
        "SWCUB_OSWORLD_GUEST_IMAGE": os.environ.get(
            "SWCUB_OSWORLD_GUEST_IMAGE", str(V2_DIR / "docker_vm_data/osworld-v2-ubuntu-x86.qcow2")),
        "SWCUB_OSWORLD_CACHE_DIR": os.environ.get(
            "SWCUB_OSWORLD_CACHE_DIR", "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/task-cache"),
        "SWCUB_OSWORLD_OVERLAY_HOST_DIR": os.environ.get(
            "SWCUB_OSWORLD_OVERLAY_HOST_DIR", "/mnt/raid1/mjh/Projects/_deps/osworld-v2.1/overlays"),
        "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE": os.environ.get(
            "SWCUB_OSWORLD_DOCKER_RUNTIME_IMAGE", "swcub/osworld-v2.1-qemu-runtime:local"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    })
    summary: dict[str, object] = {"model": "Qwen3-VL-30B-A3B-Instruct",
                                 "osworld_release": "v2.1", "trials": []}
    for task in args.tasks:
        area, scenario = TASKS[task]
        for run_no in range(1, args.repeat + 1):
            out = ARTIFACT_ROOT / area / "baseline-calibration" / task / f"run-{run_no:02d}"
            out.mkdir(parents=True, exist_ok=True)
            report_path = out / "report.json"
            if args.resume and report_path.is_file():
                candidate = json.loads(report_path.read_text(encoding="utf-8"))
            else:
                candidate = {}
            complete_report = (bool(candidate.get("model"))
                               and isinstance(candidate.get("reset_check"), dict)
                               and (out / "model_trace.jsonl").is_file()
                               and (out / "events.jsonl").is_file())
            if args.resume and complete_report:
                report = candidate
                task_success = bool(report.get("evaluation", {}).get("success"))
                return_code = 0 if report.get("success") else 1
            else:
                trial_env = env | {
                    "SWCUB_OSWORLD_RUN_DIR": str(out),
                    "SWCUB_RUN_ID": f"solo-{task}-{run_no:02d}-{uuid.uuid4().hex[:16]}",
                    "SWCUB_OWNER_TOKEN": secrets.token_hex(32),
                    "SWCUB_RESOURCE_LEDGER": str(out / "resource-events.jsonl"),
                }
                cmd = ["uv", "--project", str(V2_DIR), "run", "--frozen", "python",
                       str(ROOT / f"scripts/run_osworld_v2_1_{'browser' if area == 'browser' else 'office'}.py"),
                       "--scenario", scenario]
                with (out / "console.log").open("w", encoding="utf-8") as log:
                    log.write("command=" + json.dumps(cmd) + "\n")
                    log.flush()
                    proc = subprocess.run(cmd, cwd=ROOT, env=trial_env,
                                          stdout=log, stderr=subprocess.STDOUT, check=False)
                return_code = proc.returncode
                report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
                task_success = bool(report.get("evaluation", {}).get("success"))
            status = "success" if task_success else "failure"
            summary["trials"].append({"task": task, "run": run_no, "scenario": scenario,
                                      "success": task_success,
                                      "episode_success_including_reset": bool(report.get("success")),
                                      "reset_success": bool(report.get("reset_check", {}).get("success")),
                                      "return_code": return_code,
                                      "steps": report.get("model", {}).get("steps"),
                                      "failure_class": report.get("model_failure_class"),
                                      "report": str(report_path), "artifacts": str(out)})
            (ARTIFACT_ROOT / "baseline-calibration").mkdir(parents=True, exist_ok=True)
            (ARTIFACT_ROOT / "baseline-calibration" / "batch-progress.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            print(f"{task} run {run_no:02d}/{args.repeat}: {status} "
                  f"(exit={return_code}, steps={summary['trials'][-1]['steps']})", flush=True)
    counts = {}
    for task in args.tasks:
        entries = [x for x in summary["trials"] if x["task"] == task]
        counts[task] = {"successes": sum(bool(x["success"]) for x in entries),
                        "runs": len(entries)}
    summary["counts"] = counts
    (ARTIFACT_ROOT / "baseline-calibration" / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if all(value["runs"] == args.repeat for value in counts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
