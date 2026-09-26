#!/usr/bin/env python3
"""Validate declarative OSWorld task instances and resolve their actor triggers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.instances import TaskInstanceError, TaskInstanceSpec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=ROOT / "tasks/instances")
    args = parser.parse_args()
    paths = [args.path] if args.path.is_file() else sorted(args.path.glob("*.json"))
    if not paths:
        parser.error(f"no instance JSON files found under {args.path}")
    results = []
    try:
        for path in paths:
            instance = TaskInstanceSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
            results.append({"path": str(path), "task_id": instance.task_id,
                            "instance_id": instance.instance_id,
                            "schedule": instance.materialize_schedule(),
                            "actor_goals": len(instance.actor_goals)})
    except (OSError, json.JSONDecodeError, TaskInstanceError) as exc:
        print(f"invalid task instance: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"valid": True, "instances": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
