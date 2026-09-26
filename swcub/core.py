"""Small deterministic runtime core; deliberately independent of OSWorld/model SDKs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Mapping, Sequence


EVENT_SCHEMA_VERSION = 1
_EVENT_FIELDS = {
    "schema_version", "seq", "ts_utc", "elapsed_ms", "actor", "kind", "action",
    "observed_revision", "before_digest", "after_digest", "outcome", "details",
}
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Event:
    schema_version: int
    seq: int
    ts_utc: str
    elapsed_ms: float
    actor: str
    kind: str
    action: str
    observed_revision: int | None
    before_digest: str
    after_digest: str
    outcome: str
    details: dict[str, Any]


class EventLog:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.started = time.monotonic()

    def record(self, actor: str, kind: str, action: str, before: Any, after: Any,
               observed_revision: int | None = None, outcome: str = "ok",
               details: dict[str, Any] | None = None) -> None:
        self.events.append(Event(
            schema_version=EVENT_SCHEMA_VERSION,
            seq=len(self.events) + 1,
            ts_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_ms=round((time.monotonic() - self.started) * 1000, 3),
            actor=actor, kind=kind, action=action,
            observed_revision=observed_revision,
            before_digest=canonical_digest(before), after_digest=canonical_digest(after),
            outcome=outcome, details=details or {},
        ))

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True,
                                    allow_nan=False) + "\n")


class EventLogValidationError(ValueError):
    """Raised when a JSONL event stream does not match a supported schema."""


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value}")


def read_event_log(path: Path) -> list[dict[str, Any]]:
    """Load and validate a V0 event stream, including its version and sequence."""
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                event = json.loads(line, parse_constant=_reject_nonstandard_constant)
            except (json.JSONDecodeError, ValueError) as exc:
                raise EventLogValidationError(f"line {line_number}: invalid JSON: {exc}") from exc
            _validate_event(event, line_number, expected_seq=len(events) + 1)
            events.append(event)
    return events


def _validate_event(event: Any, line_number: int, expected_seq: int) -> None:
    def invalid(message: str) -> None:
        raise EventLogValidationError(f"line {line_number}: {message}")

    if not isinstance(event, dict):
        invalid("event must be a JSON object")
    fields = set(event)
    if fields != _EVENT_FIELDS:
        missing, extra = sorted(_EVENT_FIELDS - fields), sorted(fields - _EVENT_FIELDS)
        invalid(f"field mismatch (missing={missing}, extra={extra})")
    if type(event["schema_version"]) is not int or event["schema_version"] != EVENT_SCHEMA_VERSION:
        invalid(f"unsupported schema_version: {event['schema_version']!r}")
    if type(event["seq"]) is not int or event["seq"] != expected_seq:
        invalid(f"seq must be {expected_seq}")
    for field in ("actor", "kind", "action", "outcome"):
        if not isinstance(event[field], str) or not event[field]:
            invalid(f"{field} must be a non-empty string")
    if not isinstance(event["ts_utc"], str):
        invalid("ts_utc must be a string")
    try:
        parsed_timestamp = datetime.fromisoformat(event["ts_utc"])
    except ValueError:
        invalid("ts_utc must be an ISO-8601 timestamp")
    if parsed_timestamp.tzinfo is None:
        invalid("ts_utc must include a timezone")
    elapsed = event["elapsed_ms"]
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        invalid("elapsed_ms must be a finite non-negative number")
    revision = event["observed_revision"]
    if revision is not None and (type(revision) is not int or revision < 0):
        invalid("observed_revision must be null or a non-negative integer")
    for field in ("before_digest", "after_digest"):
        if not isinstance(event[field], str) or not _DIGEST_PATTERN.fullmatch(event[field]):
            invalid(f"{field} must be a lowercase SHA-256 hex digest")
    if not isinstance(event["details"], dict):
        invalid("details must be a JSON object")


class Episode:
    """Episode lifecycle and outputs, shared by the local harness and future VM adapter."""
    def __init__(self, state: Any):
        self.state = state
        self.log = EventLog()
        self.action_counts: dict[str, int] = {}

    def act(self, actor: str, kind: str, action: str, operation: Callable[[], Any],
            observed_revision: int | None = None) -> Any:
        before = self.snapshot()
        try:
            result = operation()
            outcome = "ok"
        except Exception as exc:
            result, outcome = None, f"error:{type(exc).__name__}:{exc}"
        after = self.snapshot()
        self.action_counts[actor] = self.action_counts.get(actor, 0) + 1
        self.log.record(actor, kind, action, before, after, observed_revision, outcome)
        if outcome != "ok":
            raise RuntimeError(outcome)
        return result

    def snapshot(self) -> Any:
        raise NotImplementedError

    def write_artifacts(self, out: Path, report: dict[str, Any]) -> None:
        out.mkdir(parents=True, exist_ok=True)
        self.log.write(out / "events.jsonl")
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")


class ScriptedOrchestrator:
    """Run independently named actor steps in an explicit, replayable total order."""

    def run(self, episode: Episode, steps: Mapping[str, Callable[[], Any]],
            schedule: Sequence[str]) -> list[Any]:
        results = []
        for turn, step_name in enumerate(schedule, start=1):
            if step_name not in steps:
                raise KeyError(f"schedule references unknown step: {step_name}")
            before = episode.snapshot()
            result = steps[step_name]()
            after = episode.snapshot()
            episode.log.record("orchestrator", "schedule", step_name, before, after,
                               details={"turn": turn, "schedule_length": len(schedule)})
            results.append(result)
        return results


def prepare_output(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
