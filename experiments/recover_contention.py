"""Recover only trials that failed before model execution, after the main queue ends."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from experiments.contention_batch import available, make_report, trial_summary
from experiments.freehand_vm10 import save


def main_finished(progress):
    return bool(progress.get("total") and progress.get("finished") == progress["total"]
                and not progress.get("active")
                and len(progress.get("jobs", [])) == progress["total"]
                and all(j.get("status") in ("finished", "error", "timeout")
                        for j in progress.get("jobs", [])))


def recovery_jobs(project, jobs):
    output = []
    for job in jobs:
        result = trial_summary(project / "runs" / job["name"])
        if result and result.get("invalid_reason") in ("preparation_error_before_model", "reviewed_guest_control_interruption"):
            output.append(job)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args(argv)
    project = args.project.resolve()
    unit = json.loads((project / "active.json").read_text())["unit"]
    state = {"status": "waiting_for_main", "started_at": time.time(), "attempts": []}
    while True:
        progress = json.loads((project / "progress.json").read_text())
        active = subprocess.run(["systemctl", "show", unit, "--property=ActiveState", "--value"],
                                capture_output=True, text=True, timeout=10).stdout.strip()
        if main_finished(progress) and active not in ("active", "activating", "deactivating"):
            break
        save(project / "recovery_progress.json", state | {"main_finished": progress.get("finished"),
                                                          "updated_at": time.time()})
        time.sleep(15)
    jobs = recovery_jobs(project, progress["jobs"])
    state.update(status="recovering", planned_conditions=len(jobs))
    overrides_path = project / "effective_attempts.json"
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    for job in jobs:
        if job["name"] in overrides:
            continue
        while not available(project):
            save(project / "recovery_progress.json", state | {"waiting_for_resources": True,
                                                              "updated_at": time.time()})
            time.sleep(15)
        for attempt in (1, 2):
            directory = project / "recoveries" / f"{job['name']}-attempt{attempt}"
            if (directory / "result.json").exists():
                result = trial_summary(directory)
            else:
                directory.mkdir(parents=True, exist_ok=False)
                item = {"condition": job["name"], "directory": str(directory.relative_to(project)),
                        "attempt": attempt, "started_at": time.time(), "status": "running"}
                state["attempts"].append(item)
                save(project / "recovery_progress.json", state)
                command = [sys.executable, "-u", "-m", "experiments.contention_trial", "--project", str(project),
                    "--pair", job["pair"], "--harness", job["harness"], "--mode", job["mode"],
                    "--out", str(directory), "--timeout", "1800"]
                with (directory / "driver.log").open("w") as log:
                    process = subprocess.Popen(command, cwd=project / "CoDesk", stdout=log,
                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
                    item["pid"] = process.pid
                    save(project / "recovery_progress.json", state)
                    try:
                        code = process.wait(timeout=5400 if job["mode"] == "sequential" else 3600)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            code = process.wait(timeout=120)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            code = process.wait()
                item.update(status="ended", exit_code=code, finished_at=time.time())
                result = trial_summary(directory)
                save(project / "recovery_progress.json", state)
            if result and result.get("measurement_valid"):
                overrides[job["name"]] = {"directory": str(directory.relative_to(project)),
                    "reason": "Recovered documented infrastructure interruption; original attempt retained",
                    "recorded_at": time.time()}
                save(overrides_path, overrides)
                break
            if not result or result.get("invalid_reason") != "preparation_error_before_model":
                break  # never rerun a genuine model failure to seek a higher score
    report = make_report(project, progress["jobs"])
    state.update(status="complete" if report["valid_conditions"] == len(progress["jobs"]) else "needs_review",
                 finished_at=time.time(), valid_conditions=report["valid_conditions"],
                 recovered_conditions=report["recovered_conditions"])
    save(project / "recovery_progress.json", state)
    print(json.dumps(state), flush=True)
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
