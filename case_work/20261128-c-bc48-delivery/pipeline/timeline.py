"""Per-actor action capture and Shared millisecond timeline merge."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


TIMELINE_SCHEMA = "paragui.shared-timeline/v1"
_SECRET_FIELD = re.compile(r"(?:api[_-]?key|token|authorization|password|secret|credential)", re.I)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_SK_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")


def sanitize(value: Any, key: str = "") -> Any:
    if _SECRET_FIELD.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return _SK_TOKEN.sub("[REDACTED]", _BEARER.sub("Bearer [REDACTED]", value))
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)


def _snapshot_fields(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot or {}
    mouse = snapshot.get("mouse")
    return {
        "window_title": sanitize(snapshot.get("window_title", "")),
        "window_id": sanitize(snapshot.get("window_id")),
        "mouse": sanitize(mouse) if mouse is not None else None,
    }


def _append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def record_tool_call(
    *,
    role: str,
    server: str,
    tool: str,
    args: Any,
    operation: Callable[[], Any],
    snapshot: Callable[[], dict[str, Any]],
    actions_path: str | Path,
    event_path: str | Path,
) -> Any:
    """Capture one GUI/Guest-CLI call. Clipboard content is compared but never persisted."""
    if role not in {"A", "B"}:
        raise ValueError("role must be A or B")
    start_ms = time.time_ns() // 1_000_000
    before_raw = snapshot()
    before = _snapshot_fields(before_raw)
    started = time.perf_counter_ns()
    result: Any = None
    error_type: str | None = None
    try:
        result = operation()
    except Exception as exc:
        error_type = type(exc).__name__
    after_raw = snapshot()
    after = _snapshot_fields(after_raw)
    end_ms = time.time_ns() // 1_000_000
    event = {
        "timestamp_utc": datetime.fromtimestamp(start_ms / 1000, timezone.utc).isoformat(),
        "start_wall_ms": start_ms,
        "end_wall_ms": end_ms,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 3),
        "role": role,
        "server": server,
        "tool": tool,
        "args": sanitize(args),
        "window_before": before,
        "window_after": after,
        "window_changed": (before["window_id"], before["window_title"]) != (after["window_id"], after["window_title"]),
        "mouse_moved": before["mouse"] != after["mouse"],
        "clipboard_changed": before_raw.get("clipboard") != after_raw.get("clipboard"),
        "status": "error" if error_type else "ok",
        "error_type": error_type,
    }
    _append_jsonl(actions_path, event)
    _append_jsonl(event_path, event)
    if error_type:
        raise RuntimeError(f"{server}.{tool} failed ({error_type})")
    return result


def _read_events(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("role") not in {"A", "B"}:
                raise ValueError(f"Invalid role in {p}:{line_no}")
            if not isinstance(row.get("start_wall_ms"), int) or not isinstance(row.get("end_wall_ms"), int):
                raise ValueError(f"Missing millisecond timestamps in {p}:{line_no}")
            rows.append(row)
    return sorted(rows, key=lambda x: (x["start_wall_ms"], x["end_wall_ms"], x["role"]))


def aggregate_timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    role_switches = sum(events[i]["role"] != events[i - 1]["role"] for i in range(1, len(events)))
    overlaps = 0
    overlap_ms_pairwise = 0
    for i, left in enumerate(events):
        left_end = left["end_wall_ms"]
        for right in events[i + 1:]:
            if right["start_wall_ms"] >= left_end:
                break
            overlap = min(left_end, right["end_wall_ms"]) - max(left["start_wall_ms"], right["start_wall_ms"])
            if overlap > 0:
                overlaps += 1
                overlap_ms_pairwise += overlap
    return {
        "event_count": len(events),
        "events_by_role": {role: sum(e["role"] == role for e in events) for role in ("A", "B")},
        "role_switches_adjacent_events": role_switches,
        "window_changes": sum(e.get("window_changed") is True for e in events),
        "window_change_observed": sum(e.get("window_changed") is not None for e in events),
        "mouse_moves": sum(e.get("mouse_moved") is True for e in events),
        "mouse_change_observed": sum(e.get("mouse_moved") is not None for e in events),
        "clipboard_changes": sum(e.get("clipboard_changed") is True for e in events),
        "clipboard_change_observed": sum(e.get("clipboard_changed") is not None for e in events),
        "tool_errors": sum(e.get("status") == "error" for e in events),
        "overlapping_event_pairs": overlaps,
        "overlap_ms_pairwise": overlap_ms_pairwise,
        "metric_notes": {
            "role_switches_adjacent_events": "derived from sorted event order",
            "overlap_ms_pairwise": "sum over all overlapping event pairs; not unique wall-clock overlap",
            "window_changes": "per-call before/after snapshot difference",
            "telemetry_note": "zero observed telemetry does not mean no change when the *_observed count is zero",
        },
    }


def merge_shared_timeline(event_files: Iterable[str | Path]) -> dict[str, Any]:
    events = _read_events(event_files)
    return {
        "schema_version": TIMELINE_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "events": events,
        "aggregate": aggregate_timeline(events),
    }


def write_shared_timeline(path: str | Path, timeline: dict[str, Any]) -> None:
    if timeline.get("schema_version") != TIMELINE_SCHEMA:
        raise ValueError("Unsupported shared timeline schema")
    Path(path).write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
