#!/usr/bin/env python3
"""Generate or verify deterministic CoDesk task instances without launching apps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swcub.task_factory import (CONTEXT_TEMPLATE_ID, MODAL_TEMPLATE_ID,
                                CLIPBOARD_TEMPLATE_ID, OFFICE_TEMPLATE_ID,
                                get_template, validate_office_candidate,
                                verify_instance_directory, write_instance)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="write immutable per-instance directories")
    gen.add_argument("--family", choices=("office_writer_calc", "clipboard",
                                           "modal_writer_calc", "browser_tab_context"),
                     required=True)
    gen.add_argument("--count", type=int, default=8, choices=range(1, 301))
    gen.add_argument("--start-seed", type=int, default=0)
    gen.add_argument("--output", type=Path, required=True)
    gen.add_argument("--dry-run", action="store_true")
    verify = commands.add_parser("verify", help="verify manifests, regeneration and file hashes")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args()

    if args.command == "generate":
        if args.start_seed < 0:
            parser.error("--start-seed must be non-negative")
        template_id = {"office_writer_calc": OFFICE_TEMPLATE_ID,
                       "clipboard": CLIPBOARD_TEMPLATE_ID,
                       "modal_writer_calc": MODAL_TEMPLATE_ID,
                       "browser_tab_context": CONTEXT_TEMPLATE_ID}[args.family]
        factory = get_template(template_id).generate
        manifests = [factory(seed) for seed in range(args.start_seed,
                                                      args.start_seed + args.count)]
        if len({item["task_id"] for item in manifests}) != len(manifests):
            raise SystemExit("generator produced duplicate task IDs")
        if len({item["content_fingerprint"] for item in manifests}) != len(manifests):
            raise SystemExit("generator produced duplicate semantic content")
        summary = {"family": args.family, "count": len(manifests),
                   "task_ids": [item["task_id"] for item in manifests],
                   "dry_run": args.dry_run}
        if not args.dry_run:
            args.output.mkdir(parents=True, exist_ok=False)
            for manifest in manifests:
                write_instance(manifest, args.output)
            (args.output / "index.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    directory = args.directory.resolve()
    manifests = sorted(directory.glob("*/manifest.json"))
    if not manifests:
        parser.error(f"no instance manifests found in {directory}")
    results = []
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        directory_result = verify_instance_directory(path.parent)
        row = {"path": str(path), "task_id": data.get("task_id"),
               "manifest_valid": directory_result["manifest_valid"],
               "files": {"success": all(item["valid"]
                                         for item in directory_result["files"]),
                         "details": directory_result["files"]}}
        if data.get("template_id") == OFFICE_TEMPLATE_ID:
            row["offline_oracle_validation"] = validate_office_candidate(data)
        results.append(row)
    data_rows = [json.loads(path.read_text(encoding="utf-8")) for path in manifests]
    task_ids = [row.get("task_id") for row in data_rows]
    fingerprints = [row.get("content_fingerprint") for row in data_rows]
    dedup_valid = len(task_ids) == len(set(task_ids)) and len(fingerprints) == len(set(fingerprints))
    ok = dedup_valid and all(row["manifest_valid"] and row["files"]["success"]
             and row.get("offline_oracle_validation", {"success": True})["success"]
             for row in results)
    print(json.dumps({"directory": str(directory), "instances": len(results),
                      "dedup_valid": dedup_valid,
                      "offline_oracle_validated_instances": sum(
                          row.get("offline_oracle_validation", {}).get("success", False)
                          for row in results),
                      "success": ok, "results": results}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
