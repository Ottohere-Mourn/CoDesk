"""Versioned JSONL event contract checks, independent of the desktop runtime."""
from __future__ import annotations
from dataclasses import asdict
import json

import pytest

from swcub.core import EventLog, EventLogValidationError, EVENT_SCHEMA_VERSION, read_event_log


def valid_event_line() -> dict[str, object]:
    log = EventLog()
    log.record("gui_actor", "gui", "observe", {"x": 0}, {"x": 1})
    return asdict(log.events[0])


def test_event_log_round_trip_has_version_and_valid_sequence(tmp_path):
    log = EventLog()
    log.record("gui_actor", "gui", "observe", {"x": 0}, {"x": 1})
    log.record("cli_actor", "cli", "append", {"x": 1}, {"x": 2}, observed_revision=1)
    path = tmp_path / "events.jsonl"
    log.write(path)

    events = read_event_log(path)

    assert [event["schema_version"] for event in events] == [EVENT_SCHEMA_VERSION] * 2
    assert [event["seq"] for event in events] == [1, 2]
    assert events[1]["observed_revision"] == 1


@pytest.mark.parametrize("mutation, message", [
    (lambda event: event.update(schema_version=2), "unsupported schema_version"),
    (lambda event: event.update(seq=3), "seq must be 1"),
    (lambda event: event.update(before_digest="not-a-digest"), "before_digest"),
    (lambda event: event.update(unversioned_extension=True), "field mismatch"),
])
def test_event_log_rejects_invalid_contract(tmp_path, mutation, message):
    event = valid_event_line()
    mutation(event)
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(EventLogValidationError, match=message):
        read_event_log(path)


def test_event_log_rejects_malformed_json(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(EventLogValidationError, match="invalid JSON"):
        read_event_log(path)


def test_event_log_rejects_nonstandard_json_constants(tmp_path):
    event = valid_event_line()
    event["details"] = {"invalid_number": float("nan")}
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(EventLogValidationError, match="non-standard JSON constant NaN"):
        read_event_log(path)
