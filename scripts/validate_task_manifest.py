#!/usr/bin/env python3
"""Validate the versioned task catalog before running or extending V0 cases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.task_manifest import (TaskManifestError, validate_task_manifest,
                                 validate_task_manifest_references)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=ROOT / "tasks" / "v0_manifest.json")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.path.read_text(encoding="utf-8"))
        summary = validate_task_manifest(manifest)
        summary.update(validate_task_manifest_references(manifest, ROOT))
    except (OSError, json.JSONDecodeError, TaskManifestError) as exc:
        print(f"invalid task manifest: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "manifest": str(args.path), **summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
