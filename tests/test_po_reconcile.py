from __future__ import annotations

import hashlib
import http.client
import json
import threading
from pathlib import Path
from urllib.request import urlopen

from oscombo.human_apps.po_reconcile import (
    USER_FILE, USER_FILE_CONTENT, create_fixture, evaluate_agent, evaluate_user, make_server,
)

def _multipart(fields, filename, content):
    boundary = "----CoDeskBoundary7MA4YWxkTrZu0gW"
    chunks = []
    for name, value in fields.items():
        chunks.extend([f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(), b"\r\n"])
    chunks.extend([f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="attachment"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: text/csv\r\n\r\n", content, b"\r\n",
        f"--{boundary}--\r\n".encode()])
    return boundary, b"".join(chunks)

def _post(url, path, body, ctype):
    host_port = url.removeprefix("http://")
    host, port = host_port.rsplit(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=4)
    conn.request("POST", path, body, {"Content-Type": ctype, "Content-Length": str(len(body))})
    response = conn.getresponse()
    payload = response.read()
    result = response.status, payload
    conn.close()
    return result

def _agent_form():
    return {"case_id": "INV-4831", "decision": "hold_for_variance",
        "accepted_units": "11", "freight_over_cap": "26.00",
        "source_refs": "PO-4831; RCV-4831; INV-4831; POL-FRT-2",
        "rationale": "Hold the invoice: one unit is damaged, and freight exceeds the PO cap."}

def test_fixture_hides_answer_and_initial_oracles_fail(tmp_path):
    db = tmp_path / "case.sqlite3"
    manifest = create_fixture(db, "run-1")
    assert manifest["fixture_id"] == "po-reconcile-and-receipt-archive-v1"
    assert "hold_for_variance" not in json.dumps(manifest)
    assert "26.00" not in json.dumps(manifest)
    assert evaluate_agent(db)["success"] is False
    assert evaluate_user(db)["success"] is False

def test_agent_source_grounded_reconciliation_oracle(tmp_path):
    db = tmp_path / "case.sqlite3"
    create_fixture(db, "run-2")
    server = make_server(db, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        page = urlopen(url + "/agent", timeout=3).read().decode()
        assert "INV-4831" in page and "POL-FRT-2" in page
        assert "hold_for_variance" not in page and "26.00" not in page
        for path in ("/po/PO-4831", "/receiving/RCV-4831", "/invoice/INV-4831", "/policy/POL-FRT-2"):
            assert urlopen(url + path, timeout=3).status == 200
        agent = _agent_form()
        body = "&".join(f"{k}={__import__('urllib.parse').parse.quote(v)}" for k, v in agent.items()).encode()
        status, response = _post(url, "/resolution/submit", body, "application/x-www-form-urlencoded")
        assert status == 200 and b"Reconciliation saved" in response
        assert evaluate_agent(db)["success"] is True
        assert all(evaluate_agent(db)["checks"].values())
        # The User's separate task legitimately writes to the archive in Shared mode;
        # that must not be classified as mutation of the Agent's protected sources.
        boundary, body = _multipart({"folder": "Finance/November 2026"}, USER_FILE, USER_FILE_CONTENT)
        assert _post(url, "/archive/submit", body, f"multipart/form-data; boundary={boundary}")[0] == 200
        assert evaluate_agent(db)["success"] is True
        # Meaning-equivalent wording from the GUI Agent must not be rejected by a
        # brittle literal-only Oracle: the source itself describes the carton as crushed.
        alternative = {**agent, "rationale":
            "Hold: one crushed carton was quarantined and is not payable; freight is $26 above the policy cap."}
        body = "&".join(f"{k}={__import__('urllib.parse').parse.quote(v)}" for k, v in alternative.items()).encode()
        assert _post(url, "/resolution/submit", body, "application/x-www-form-urlencoded")[0] == 200
        assert evaluate_agent(db)["success"] is True
        wrong = {**alternative, "rationale": "Hold invoice for freight review; the quantity is fine."}
        body = "&".join(f"{k}={__import__('urllib.parse').parse.quote(v)}" for k, v in wrong.items()).encode()
        assert _post(url, "/resolution/submit", body, "application/x-www-form-urlencoded")[0] == 200
        assert evaluate_agent(db)["success"] is False
        assert evaluate_user(db)["success"] is True
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)

def test_user_attachment_archive_oracle_checks_role_folder_and_hash(tmp_path):
    db = tmp_path / "case.sqlite3"
    create_fixture(db, "run-3")
    server = make_server(db, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        portal = urlopen(url + "/portal", timeout=3).read().decode()
        assert "Download receiving acknowledgement D-4831" in portal
        resp = urlopen(url + "/download/receipt", timeout=3)
        assert resp.headers.get_filename() == USER_FILE
        assert resp.read() == USER_FILE_CONTENT
        boundary, body = _multipart({"folder": "Finance/November 2026"}, USER_FILE, USER_FILE_CONTENT)
        status, response = _post(url, "/archive/submit", body, f"multipart/form-data; boundary={boundary}")
        assert status == 200 and b"Receipt archived" in response
        result = evaluate_user(db)
        assert result["success"] is True
        assert result["latest"]["content_sha256"] == hashlib.sha256(USER_FILE_CONTENT).hexdigest()
        assert evaluate_agent(db)["success"] is False
        boundary, body = _multipart({"folder": "Finance/October 2026"}, USER_FILE, b"altered")
        assert _post(url, "/archive/submit", body, f"multipart/form-data; boundary={boundary}")[0] == 200
        assert evaluate_user(db)["success"] is False
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)

