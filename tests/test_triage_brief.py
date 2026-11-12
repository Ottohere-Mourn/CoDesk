from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from oscombo.human_apps.triage_brief import create_fixture, evaluate, make_server


def _post(url, values):
    req = Request(url + "/submit", data=urlencode(values).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    return urlopen(req, timeout=3)


def test_triage_fixture_does_not_expose_answer_and_oracle_starts_empty(tmp_path):
    db = tmp_path / "triage.sqlite"
    manifest = create_fixture(db, "run-1")
    assert manifest["fixture_id"] == "shift-triage-t1042-v1"
    assert "delivery_damage" not in json.dumps(manifest)
    assert "DELIVERY-EV-77" not in json.dumps(manifest)
    assert evaluate(db)["success"] is False


def test_triage_gui_accepts_brief_and_oracle_checks_saved_result(tmp_path):
    db = tmp_path / "triage.sqlite"
    create_fixture(db, "run-2")
    server = make_server(db, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    values = {"ticket_id": "T-1042", "issue_class": "delivery_damage",
              "recommendation": "prepare_item_refund",
              "source_refs": "DELIVERY-EV-77; POLICY-RET-4",
              "rationale": "The dock damage is supported by delivery evidence; prepare the item refund and exclude shipping."}
    try:
        page = urlopen(url + "/", timeout=3).read().decode()
        assert "Shift Triage Brief" in page
        assert "DELIVERY-EV-77" not in page and "POLICY-RET-4" not in page
        assert evaluate(db)["success"] is False
        response = _post(url, values).read().decode()
        assert "Triage brief saved" in response
        result = evaluate(db)
        assert result["success"] is True
        assert all(result["checks"].values())
        _post(url, {**values, "issue_class": "late_delivery"}).read()
        result = evaluate(db)
        assert result["checks"]["issue_class"] is False
        assert result["success"] is False  # latest submission governs
    finally:
        server.shutdown()
        server.server_close()
        server.access_log.close()
        thread.join(timeout=3)


def test_triage_wrong_ticket_rejected_without_success(tmp_path):
    db = tmp_path / "triage.sqlite"
    create_fixture(db, "run-3")
    server = make_server(db, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        try:
            _post(url, {"ticket_id": "T-9999", "issue_class": "delivery_damage",
                        "recommendation": "prepare_item_refund", "source_refs": "A;B",
                        "rationale": "This is a test"})
            assert False, "Expected HTTP 400"
        except HTTPError as exc:
            assert exc.code == 400
        assert evaluate(db)["success"] is False
    finally:
        server.shutdown()
        server.server_close()
        server.access_log.close()
        thread.join(timeout=3)

