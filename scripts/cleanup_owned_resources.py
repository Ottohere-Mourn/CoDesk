#!/usr/bin/env python3
"""Remove one run-owned Docker container after verifying its full ID and labels.

This command never accepts a container name, image, prefix, volume, or directory.
Without --apply it only validates and prints the exact target.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swcub.resource_safety import (  # noqa: E402
    FULL_CONTAINER_ID, PROJECT_NAME, ResourceIdentity, ResourceLedger,
    cleanup_docker_cli_container, verify_container_identity,
    verify_ledger_ownership,
)


def inspect_container(container_id: str) -> dict[str, Any]:
    proc = subprocess.run(["docker", "inspect", "--type", "container", container_id],
                          check=True, capture_output=True, text=True)
    rows = json.loads(proc.stdout)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("Docker inspect did not return exactly one container")
    return rows[0]


def clean_one(ledger_path: Path, container_id: str, *, apply: bool,
              runner=subprocess.run, inspect_fn=inspect_container) -> str:
    if not FULL_CONTAINER_ID.fullmatch(container_id):
        raise RuntimeError("pass one exact full 64-character container ID; names and prefixes are refused")
    ledger = ResourceLedger(ledger_path)
    row = ResourceLedger.record_from_rows(ledger_path, container_id)
    if not row:
        raise RuntimeError("no created-container ledger record for this full ID")
    labels = row.get("labels") or {}
    if labels.get("org.swcub.project") != PROJECT_NAME:
        raise RuntimeError("ledger project ownership label mismatch")
    run_id = row.get("run_id")
    token = labels.get("org.swcub.owner-token")
    if not isinstance(run_id, str) or not isinstance(token, str):
        raise RuntimeError("ledger is missing run ID or owner token")
    identity = ResourceIdentity(run_id, token, ledger.path)
    if not ledger.has_started_run(identity):
        raise RuntimeError("ledger has no matching current-run start record")
    verify_ledger_ownership(container_id, row, identity)
    attrs = inspect_fn(container_id)
    verify_container_identity(container_id, attrs, identity)
    status = (attrs.get("State") or {}).get("Status", "unknown")
    if not apply:
        return (f"verified project={PROJECT_NAME} run={run_id} id={container_id} "
                f"status={status}; dry run only (pass --apply to remove this exact container)")

    cleanup_docker_cli_container(container_id, identity,
                                 reason="cleanup_owned_resources.py",
                                 runner=runner, inspect_fn=inspect_fn)
    return f"removed verified project={PROJECT_NAME} run={run_id} id={container_id}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True,
                        help="the single run's resource-events.jsonl")
    parser.add_argument("--container-id", required=True,
                        help="exact full 64-character Docker container ID")
    parser.add_argument("--apply", action="store_true",
                        help="stop/remove the verified target; default is read-only dry run")
    args = parser.parse_args()
    try:
        print(clean_one(args.ledger, args.container_id, apply=args.apply))
    except (RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
