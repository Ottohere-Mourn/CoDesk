import json
import time

from oscombo.eventlog import EventLog
from oscombo.human_agent_mail_case_runner import _schedule_user_actor


def test_fixed_start_offset_is_logged_before_user_actor_runs(tmp_path):
    started = time.monotonic()
    events = EventLog(tmp_path / "events.jsonl", "mail-probe", tmp_path, started)
    actor_calls = []

    def actor():
        actor_calls.append(time.monotonic())
        events.emit("user", "actor_started", guest_id="guest-shared")
        return {"status": "done"}

    scheduled = _schedule_user_actor(actor, 0.02, events, "guest-shared")
    result = scheduled()
    rows = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]

    assert result == {"status": "done"}
    assert len(actor_calls) == 1
    assert [row["event_type"] for row in rows] == ["actor_scheduled", "actor_started"]
    assert rows[0]["start_delay_s"] == 0.02
    assert rows[0]["fixed_mechanism_probe"] is True
    assert actor_calls[0] - started >= 0.02

