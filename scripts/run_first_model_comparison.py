#!/usr/bin/env python3
"""Run the fixed Browser + scripted Writer comparison sequentially.

Each episode gets a fresh output directory and a new OSWorld Guest. This driver
does not remove resources; the pinned provider records and safely closes only
containers created by each episode.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_osworld_v2_1_browser.sh"
CONDITION_SCENARIOS = {
    "agent-solo": "comparison-agent-solo",
    "writer-solo": "comparison-writer-solo",
    "sequential": "comparison-sequential",
    "naive-shared": "comparison-naive-shared",
    "focus-aware": "comparison-focus-aware",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path(
        "/mnt/raid1/mjh/Shared-Workspace-Benchmark-V0-artifacts/osworld-v2.1/first-model-comparison/runs"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--conditions", nargs="+", choices=tuple(CONDITION_SCENARIOS),
                        default=list(CONDITION_SCENARIOS))
    parser.add_argument("--first-repeat", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.first_repeat < 1 or args.first_repeat > args.repeats:
        parser.error("repeats/first-repeat must define a non-empty positive range")

    artifact_root = args.artifact_root.expanduser().resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    manifest = artifact_root / "run-manifest.jsonl"
    selected = list(args.conditions)
    shared_conditions = {"sequential", "naive-shared", "focus-aware"}
    if shared_conditions.intersection(selected):
        selected = [name for name in ("agent-solo", "writer-solo") if name not in selected] + selected
    ordered = list(dict.fromkeys(selected))
    for condition in ordered:
        if condition in shared_conditions and not args.dry_run:
            missing_or_failed = []
            for solo_condition in ("agent-solo", "writer-solo"):
                for repeat in range(1, args.repeats + 1):
                    report_path = artifact_root / solo_condition / f"run-{repeat:02d}" / "report.json"
                    try:
                        solo_report = json.loads(report_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        missing_or_failed.append({"condition": solo_condition,
                                                  "repeat": repeat, "reason": "missing report"})
                        continue
                    if not solo_report.get("success"):
                        missing_or_failed.append({"condition": solo_condition,
                                                  "repeat": repeat, "reason": "solo goal/reset failed"})
            if missing_or_failed:
                row = {"started_utc": utc_now(), "condition": condition,
                       "status": "blocked_solo_control", "failures": missing_or_failed}
                with manifest.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(json.dumps(row, ensure_ascii=False), flush=True)
                return 2
        scenario = CONDITION_SCENARIOS[condition]
        for repeat in range(args.first_repeat, args.repeats + 1):
            out = artifact_root / condition / f"run-{repeat:02d}"
            command = [str(RUNNER), scenario]
            row = {"started_utc": utc_now(), "condition": condition,
                   "scenario": scenario, "repeat": repeat, "artifact_dir": str(out),
                   "command": command, "status": "planned"}
            if args.dry_run:
                print(json.dumps(row, ensure_ascii=False))
                continue
            report_path = out / "report.json"
            if report_path.is_file():
                try:
                    existing_report = json.loads(report_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    existing_report = None
                if existing_report is not None and "reset_check" in existing_report:
                    row.update({"status": "reused_existing_report",
                                "success": existing_report.get("success"),
                                "report": str(report_path)})
                    with manifest.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                    continue
            if out.exists() and any(out.iterdir()):
                row["status"] = "refused_existing_artifacts"
                with manifest.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(json.dumps(row, ensure_ascii=False), flush=True)
                return 2
            out.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["SWCUB_OSWORLD_RUN_DIR"] = str(out)
            row["status"] = "running"
            with manifest.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
            proc = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (out / "driver-output.txt").write_text(proc.stdout, encoding="utf-8")
            report_path = out / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
            is_final_report = report is not None and "reset_check" in report
            row.update({"finished_utc": utc_now(), "exit_code": proc.returncode,
                        "status": ("finished" if is_final_report else
                                   "incomplete_report" if report is not None else "no_report"),
                        "success": report.get("success") if report else None,
                        "scenario_success": report.get("scenario_success") if report else None,
                        "report": str(report_path) if report else None})
            with manifest.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
