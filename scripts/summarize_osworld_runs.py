#!/usr/bin/env python3
"""Aggregate saved OSWorld episode reports without reading actor-hidden files."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.instances import aggregate_reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="episode directory or parent directory")
    parser.add_argument("--output", type=Path, help="write the summary JSON here")
    parser.add_argument("--successful-only", action="store_true",
                        help="include only complete episodes with scenario_success and reset success")
    args = parser.parse_args()
    if args.path.is_dir() and (args.path / "report.json").is_file():
        report_paths = [args.path / "report.json"]
    else:
        report_paths = []
        for directory, _subdirs, files in os.walk(args.path, followlinks=True):
            if "report.json" in files:
                report_paths.append(Path(directory) / "report.json")
        report_paths.sort()
    reports = []
    for report_path in report_paths:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if args.successful_only and (report.get("success") is not True
                                     or report.get("reset_check", {}).get("success") is not True):
            continue
        report.setdefault("task_id", report.get("task_instance_id", report_path.parent.name))
        reports.append(report)
    if not reports:
        parser.error(f"no report.json files found under {args.path}")
    summary = aggregate_reports(reports)
    summary["filter"] = "complete_and_reset_success" if args.successful_only else "all_saved_reports"
    summary["source_reports"] = []
    for path in report_paths:
        logical_path = path if path.is_absolute() else ROOT / path
        try:
            summary["source_reports"].append(logical_path.relative_to(ROOT).as_posix())
        except ValueError:
            summary["source_reports"].append(os.fspath(logical_path))
    serialized = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
