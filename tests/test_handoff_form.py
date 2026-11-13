from __future__ import annotations

import json
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from oscombo.human_apps.handoff_form import create_fixture, evaluate, make_server


def _serve(db_path):
    server = make_server(db_path, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def _post(url, values):
    req = Request(url + "/submit", data=urlencode(values).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    return urlopen(req, timeout=3)


def test_fixture_manifest_is_stable_public_and_evaluator_starts_unsubmitted(tmp_path):
    first = create_fixture(tmp_path / "first.sqlite", "human-run-1")
    second = create_fixture(tmp_path / "second.sqlite", "human-run-1")
    assert first["sha256"] == second["sha256"]
    assert first["fixture_id"] == "handoff-form-t1043-v2"
    public_json = json.dumps(first)
    assert "Asked carrier for Tuesday delivery window; follow up at 16:00." not in public_json
    assert "2026-11-10 16:00" not in public_json
    result = evaluate(tmp_path / "first.sqlite")
    assert not result["success"]
    assert result["checks"]["submitted"] is False
    assert result["submission_count"] == 0


def test_gui_form_is_accessible_does_not_expose_oracle_and_persists_success(tmp_path):
    db_path = tmp_path / "handoff.sqlite"
    create_fixture(db_path, "gui-pilot-1")
    server, thread, base = _serve(db_path)
    try:
        with urlopen(base + "/", timeout=3) as response:
            page = response.read().decode()
            assert response.status == 200
        assert "Shift Handoff" in page
        assert "Ticket:</strong> T-1043" in page
        assert 'name="ticket_id" value="T-1043"' in page
        assert '<textarea id="note" name="note"' in page
        assert "Internal update note" in page
        assert 'type="text" inputmode="numeric" placeholder="YYYY-MM-DD HH:MM"' in page
        assert "Follow-up date and time (local)" in page
        assert page.count("<button") == 1
        assert "autofocus" in page
        assert "Asked carrier for Tuesday delivery window" not in page
        assert "2026-11-10 16:00" not in page
        assert evaluate(db_path)["success"] is False

        fields = {
            "ticket_id": "T-1043",
            "note": "Asked carrier for Tuesday delivery window; follow up at 16:00.",
            "follow_up": "2026-11-10T16:00",
        }
        with _post(base, fields) as response:
            after = response.read().decode()
            assert response.status == 200
        assert 'role="status">Update saved.' in after
        assert "Asked carrier for Tuesday delivery window; follow up at 16:00." in after
        assert 'value="2026-11-10 16:00"' in after
        verdict = evaluate(db_path)
        assert verdict["success"] is True
        assert all(verdict["checks"].values())
        with sqlite3.connect(db_path) as db:
            stored = db.execute("SELECT ticket_id,note,follow_up,submitted FROM ticket").fetchone()
        assert stored == ("T-1043", fields["note"], "2026-11-10 16:00", 1)
        assert json.loads((tmp_path / "handoff.sqlite.fixture.json").read_text())["sha256"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_oracle_requires_http_submission_and_exact_latest_values(tmp_path):
    db_path = tmp_path / "handoff.sqlite"
    create_fixture(db_path, "gui-pilot-2")
    # Even exact values seeded directly into state cannot bypass the submitted flag/log gate.
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE ticket SET note=?, follow_up=? WHERE ticket_id='T-1043'",
                   ("Asked carrier for Tuesday delivery window; follow up at 16:00.", "2026-11-10 16:00"))
    assert not evaluate(db_path)["success"]

    server, thread, base = _serve(db_path)
    try:
        _post(base, {"ticket_id":"T-1043", "note":"A plausible but incorrect note", "follow_up":"2026-11-10T16:00"}).read()
        result = evaluate(db_path)
        assert result["checks"]["submitted"] is True
        assert result["checks"]["note"] is False
        assert result["checks"]["follow_up"] is True
        assert result["success"] is False

        # A later bad revision must make the current ticket state fail, even after a good one.
        _post(base, {"ticket_id":"T-1043", "note":"Asked carrier for Tuesday delivery window; follow up at 16:00.", "follow_up":"2026-11-10T16:00"}).read()
        assert evaluate(db_path)["success"] is True
        _post(base, {"ticket_id":"T-1043", "note":"Wrong last edit", "follow_up":"2026-11-10T16:00"}).read()
        assert evaluate(db_path)["success"] is False
        assert evaluate(db_path)["submission_count"] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_wrong_ticket_id_is_rejected_and_does_not_count_as_submission(tmp_path):
    db_path = tmp_path / "handoff.sqlite"
    create_fixture(db_path, "gui-pilot-3")
    server, thread, base = _serve(db_path)
    try:
        try:
            _post(base, {"ticket_id":"T-9999", "note":"A note", "follow_up":"2026-11-10T16:00"})
            assert False, "Expected HTTP 400"
        except HTTPError as error:
            assert error.code == 400
        assert evaluate(db_path)["submission_count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
