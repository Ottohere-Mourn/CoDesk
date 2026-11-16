"""Small append-only JSONL event logging shared by PoC actors and GUI MCP subprocesses."""
from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    """Append one JSON line with a process-shared lock (safe for User + MCP child processes)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, data)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class EventLog:
    def __init__(self, path: str | Path, run_id: str, root: str | Path | None = None,
                 started_mono: float | None = None):
        self.path = Path(path)
        self.run_id = run_id
        self.root = Path(root).resolve() if root else self.path.parent.resolve()
        self.started_mono = started_mono if started_mono is not None else time.monotonic()

    def emit(self, actor_id: str, event_type: str, *, episode_id: str | None = None,
             guest_id: str | None = None, **fields: Any) -> dict[str, Any]:
        wall = time.time()
        mono = time.monotonic()
        row = {
            "event_id": uuid.uuid4().hex,
            "run_id": self.run_id,
            "episode_id": episode_id or actor_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "timestamp_utc": datetime.fromtimestamp(wall, timezone.utc).isoformat(),
            "wall_time": wall,
            "monotonic_time": mono,
            "run_elapsed_s": round(mono - self.started_mono, 6),
            "guest_id": guest_id,
            **fields,
        }
        append_jsonl(self.path, row)
        return row
