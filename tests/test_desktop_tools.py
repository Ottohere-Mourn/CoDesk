import json

import pytest

from oscombo import desktop_tools


def test_failed_gui_mcp_call_is_logged(monkeypatch, tmp_path):
    action_log = tmp_path / "actions.jsonl"
    monkeypatch.setattr(desktop_tools, "LOG", str(action_log))
    monkeypatch.setattr(desktop_tools, "UNIFIED_EVENT_LOG", None)
    monkeypatch.delenv("OSCOMBO_ACTION_LOCK_FILE", raising=False)
    monkeypatch.setenv("OSCOMBO_ACTOR_ID", "agent")
    monkeypatch.setenv("OSCOMBO_GUEST_ID", "guest-shared")

    def fail(name, args, lock_info=None):
        raise TimeoutError("guest screenshot timed out")

    monkeypatch.setattr(desktop_tools, "_run_tool_unlocked", fail)
    with pytest.raises(TimeoutError, match="guest screenshot timed out"):
        desktop_tools.run_tool("screenshot", {})

    event = json.loads(action_log.read_text().splitlines()[-1])
    assert event["tool"] == "screenshot"
    assert event["actor_id"] == "agent"
    assert event["guest_id"] == "guest-shared"
    assert event["status"] == "error"
    assert event["error_type"] == "TimeoutError"
    assert "timed out" in event["error"]
