#!/usr/bin/env python3
"""Run the fixed 18-episode Phase 4 Qwen smoke matrix without overwrites."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path(
    "/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/phase4-model-smoke")
MATRIX = [
    ("focus", "solo", "focus-qwen-solo", "shared"),
    ("focus", "naive-shared", "focus-qwen-naive", "shared"),
    ("focus", "recovery-aware", "focus-qwen-recovery", "shared"),
    ("gui-cli", "solo", "qwen-gui-cli-solo", "browser"),
    ("gui-cli", "naive-shared", "qwen-gui-cli-naive", "browser"),
    ("gui-cli", "recovery-aware", "qwen-gui-cli-recovery", "browser"),
]


def episode_dir(root: Path, task: str, condition: str, repeat: int) -> Path:
    return root / task / condition / f"repeat-{repeat:02d}"


def complete_report(path: Path, task_id: str) -> bool:
    report_path = path / "report.json"
    if not report_path.is_file():
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (report.get("task_id") == task_id and report.get("task_version") == "2.0.0"
            and isinstance(report.get("evaluation"), dict))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--start-task", choices=("focus", "gui-cli"), default="focus")
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    overlay_dir = root / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    progress_path = root / "matrix_progress.jsonl"
    start_found = args.start_task == "focus"

    for task, condition, scenario, runner in MATRIX:
        if task == args.start_task:
            start_found = True
        if not start_found:
            continue
        task_id = ("SWCUB-FOCUS-ROUTING-001" if task == "focus"
                   else "SWCUB-STALE-MERGE-001")
        for repeat in range(1, 4):
            out = episode_dir(root, task, condition, repeat)
            if complete_report(out, task_id):
                print(json.dumps({"event": "skip_complete", "episode": str(out)},
                                 ensure_ascii=False), flush=True)
                continue
            if out.exists() and any(out.iterdir()):
                print(json.dumps({"event": "preserved_incomplete_attempt",
                                  "episode": str(out)}, ensure_ascii=False), flush=True)
                continue
            out.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update({"SWCUB_OSWORLD_OVERLAY_HOST_DIR": str(overlay_dir),
                        "SWCUB_EPISODE_REPEAT": f"{repeat:02d}"})
            if runner == "shared":
                env["OSWORLD_V2_RUN_DIR"] = str(out)
                command = [str(ROOT / "scripts/run_osworld_v2_1_shared_csv.sh"),
                           "--scenario", scenario]
            else:
                env["SWCUB_OSWORLD_RUN_DIR"] = str(out)
                command = [str(ROOT / "scripts/run_osworld_v2_1_browser.sh"), scenario]
            started = datetime.now(timezone.utc).isoformat()
            console_path = out / "matrix_console.log"
            print(json.dumps({"event": "episode_started", "task": task,
                              "condition": condition, "repeat": repeat,
                              "episode": str(out), "started_utc": started},
                             ensure_ascii=False), flush=True)
            with console_path.open("wb") as console:
                proc = subprocess.run(command, cwd=ROOT, env=env,
                                      stdout=console, stderr=subprocess.STDOUT,
                                      check=False)
            record = {"task": task, "task_id": task_id, "condition": condition,
                      "scenario": scenario, "repeat": repeat, "artifact_dir": str(out),
                      "started_utc": started,
                      "finished_utc": datetime.now(timezone.utc).isoformat(),
                      "runner_exit_code": proc.returncode,
                      "report_present": complete_report(out, task_id)}
            if record["report_present"]:
                report = json.loads((out / "report.json").read_text(encoding="utf-8"))
                record.update({"evaluation_success": report.get("evaluation", {}).get("success"),
                               "reset_success": report.get("reset_check", {}).get("success"),
                               "episode_success": report.get("success"),
                               "model_failure_class": report.get("model_failure_class")})
            with progress_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps({"event": "episode_finished", **record},
                             ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
