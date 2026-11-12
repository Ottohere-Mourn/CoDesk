import json
import time
from types import SimpleNamespace

from oscombo.eventlog import EventLog
from oscombo.guest import Guest
from oscombo.human_poc import FocusMonitor


class _Response:
    ok = True
    status_code = 200
    def json(self):
        return {"status": "success", "returncode": 0, "output": "0x01400004\tRecord Receipt - Google Chrome"}


def test_guest_returns_window_id_and_title(monkeypatch):
    import oscombo.guest as guest_module
    monkeypatch.setattr(guest_module.requests, "post", lambda *args, **kwargs: _Response())
    guest = Guest(SimpleNamespace(vm_ip="127.0.0.1", server_port=5000))
    assert guest.active_window_info() == {
        "id": "0x01400004",
        "title": "Record Receipt - Google Chrome",
    }
    assert guest.active_window() == "Record Receipt - Google Chrome"


def test_page_title_change_is_not_counted_as_focus_change(tmp_path):
    class ChangingGuest:
        def __init__(self):
            self.values = [
                {"id": "0x1", "title": "Dashboard - Google Chrome"},
                {"id": "0x1", "title": "Receiving Queue - Google Chrome"},
                {"id": "0x2", "title": "Writer"},
            ]
            self.last = self.values[-1]
        def active_window_info(self):
            if self.values:
                self.last = self.values.pop(0)
            return self.last
        def screenshot(self, patience=30):
            return b"png"
        def execute(self, *args, **kwargs):
            return {"output": "window inventory"}

    path = tmp_path / "events.jsonl"
    log = EventLog(path, "window-test", tmp_path)
    monitor = FocusMonitor(ChangingGuest(), "guest", log, tmp_path / "shots", interval=.005)
    monitor.start()
    time.sleep(.03)
    monitor.stop()
    events = [json.loads(line) for line in path.read_text().splitlines()]
    types = [event["event_type"] for event in events]
    assert types.count("window_title_change") == 1
    assert types.count("focus_change") == 1
    assert monitor.transitions == 1
