"""Append-only event writer for future Guest adapters; no GUI probing here."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import CASE_ID

REQUIRED = {"schema_version", "case_id", "run_id", "seq", "actor_id", "event_type", "timestamp_monotonic_ns"}
EVENTS = {"observation", "action_start", "action_end", "save", "message", "recovery"}


def append_event(run_root: str | Path, event: dict[str, Any]) -> Path:
    """Append one actor-attributed event after checking run ownership.

    This function records caller-supplied observations; it does not inspect
    Kdenlive or claim that window/app-state samples are atomic.
    """
    root = Path(run_root).resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing/symlinked ownership ledger")
    ownership = json.loads(ledger.read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run ownership mismatch")
    if REQUIRED - event.keys():
        raise ValueError(f"event missing fields: {sorted(REQUIRED - event.keys())}")
    if event["case_id"] != CASE_ID or event["run_id"] != ownership.get("run_id"):
        raise PermissionError("event case_id/run_id mismatch")
    if event["actor_id"] not in {"A", "B", "S"} or event["event_type"] not in EVENTS:
        raise ValueError("invalid actor_id or event_type")
    if int(event["seq"]) < 1 or int(event["timestamp_monotonic_ns"]) < 0:
        raise ValueError("seq/timestamp must be nonnegative and seq must start at 1")
    path = root / "interaction_events.jsonl"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path
