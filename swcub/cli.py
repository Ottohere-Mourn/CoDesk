"""Command line entry point for deterministic scripted episodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import EventLogValidationError, prepare_output, read_event_log
from .tasks import csv_shared, focus


def main() -> int:
    parser = argparse.ArgumentParser(prog="swcub")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run one deterministic scenario")
    run_parser.add_argument("task", choices=("focus", "csv"))
    run_parser.add_argument("--out", type=Path, required=True)
    all_parser = sub.add_parser("run-all", help="run all scripted scenarios")
    all_parser.add_argument("--out", type=Path, required=True)
    validate_parser = sub.add_parser("validate-events", help="validate a versioned JSONL event log")
    validate_parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate-events":
        try:
            events = read_event_log(args.path)
        except (OSError, EventLogValidationError) as exc:
            print(f"invalid event log: {exc}", file=sys.stderr)
            return 2
        versions = sorted({event["schema_version"] for event in events})
        print(json.dumps({"valid": True, "events": len(events), "schema_versions": versions}))
        return 0
    if args.command == "run":
        prepare_output(args.out)
        report = (focus if args.task == "focus" else csv_shared).run(args.out)
        print(json.dumps({"task": args.task, "success": report["joint"]["success"],
                          "report": str(args.out / "report.json")}, ensure_ascii=False))
        return 0 if report["joint"]["success"] and all(
            x["success"] for x in report["independent"].values()) else 1
    prepare_output(args.out)
    summary = {}
    for task_name, task_module in (("focus", focus), ("csv", csv_shared)):
        task_out = args.out / task_name
        task_out.mkdir(parents=True, exist_ok=True)
        report = task_module.run(task_out)
        summary[task_name] = {"joint_success": report["joint"]["success"],
                              "independent_success": all(x["success"] for x in report["independent"].values()),
                              "actions": report["metrics"]["total_actions"]}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if all(v["joint_success"] and v["independent_success"] for v in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
