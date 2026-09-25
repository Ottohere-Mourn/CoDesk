"""Small deterministic runtime core; deliberately independent of OSWorld/model SDKs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Mapping, Sequence


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Event:
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
                f.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")


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
