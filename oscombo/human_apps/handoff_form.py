"""Deterministic local handoff form used as a scripted-human GUI fixture.

This module serves only the ordinary ticket UI. The evaluation target is private
server-side state and is never included in rendered HTML or HTTP responses.
"""
from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

FIXTURE_ID = "handoff-form-t1043-v2"
TICKET_ID = "T-1043"
# Evaluation answers are intentionally not rendered into the web page or exposed
# by an HTTP route. Keep this tuple in the offline evaluator only.
_EXPECTED = {
    "ticket_id": TICKET_ID,
    "note": "Asked carrier for Tuesday delivery window; follow up at 16:00.",
    "follow_up": "2026-11-10 16:00",
}
_INITIAL_TICKET = {
    "ticket_id": TICKET_ID,
    "customer": "Maya Chen",
    "subject": "Replacement USB-C cable shipment",
    "summary": "The replacement shipment is in progress. The customer asked us to keep the ticket updated.",
    "note": "",
    "follow_up": "",
    "submitted": 0,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_fixture(db_path: str | Path, run_id: str) -> dict[str, Any]:
    """Create/reset the deterministic T-1043 fixture and return its public hash manifest.

    The companion ``<db suffix>.fixture.json`` file records only the initial
    public application state; it does not contain evaluator targets.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
            DROP TABLE IF EXISTS submissions;
            DROP TABLE IF EXISTS ticket;
            DROP TABLE IF EXISTS run_meta;
            CREATE TABLE run_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE ticket (
                ticket_id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                subject TEXT NOT NULL,
                summary TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                follow_up TEXT NOT NULL DEFAULT '',
                submitted INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE submissions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                note TEXT NOT NULL,
                follow_up TEXT NOT NULL,
                received_utc TEXT NOT NULL
            );
        """)
        db.execute("INSERT INTO run_meta(key, value) VALUES ('run_id', ?)", (str(run_id),))
        db.execute("INSERT INTO run_meta(key, value) VALUES ('fixture_id', ?)", (FIXTURE_ID,))
        db.execute(
            """INSERT INTO ticket(ticket_id, customer, subject, summary, note, follow_up, submitted)
               VALUES (:ticket_id, :customer, :subject, :summary, :note, :follow_up, :submitted)""",
            _INITIAL_TICKET,
        )
        db.commit()
    public_manifest = {
        "fixture_id": FIXTURE_ID,
        "run_id": str(run_id),
        "schema_version": 1,
        "initial_state": dict(_INITIAL_TICKET),
    }
    digest = hashlib.sha256(_canonical_bytes(public_manifest)).hexdigest()
    manifest = {**public_manifest, "sha256": digest}
    manifest_path = path.with_suffix(path.suffix + ".fixture.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def _read_ticket(db_path: str | Path) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM ticket WHERE ticket_id = ?", (TICKET_ID,)).fetchone()
            return dict(row) if row is not None else None
    except (sqlite3.Error, OSError):
        return None


def evaluate(db_path: str | Path) -> dict[str, Any]:
    """Evaluate the last persisted form submission, never pre-submit fixture state."""
    state = _read_ticket(db_path)
    if state is None:
        return {"success": False, "checks": {"fixture_exists": False, "submitted": False,
                "ticket_id": False, "note": False, "follow_up": False}}
    with sqlite3.connect(db_path) as db:
        count = db.execute("SELECT COUNT(*) FROM submissions WHERE ticket_id = ?", (TICKET_ID,)).fetchone()[0]
    submitted = bool(state["submitted"] and count > 0)
    checks = {
        "fixture_exists": True,
        "submitted": submitted,
        "ticket_id": state["ticket_id"] == _EXPECTED["ticket_id"],
        "note": state["note"] == _EXPECTED["note"],
        "follow_up": state["follow_up"] == _EXPECTED["follow_up"],
    }
    success = all(checks.values())
    return {"success": success, "checks": checks,
            "submission_count": int(count), "revision": int(state["revision"])}


def _render_page(state: dict[str, Any] | None, saved: bool = False) -> bytes:
    if state is None:
        return b"<!doctype html><title>Shift Handoff - {ticket_id}</title><p>Ticket fixture is unavailable.</p>"
    ticket_id = html.escape(str(state["ticket_id"]), quote=True)
    customer = html.escape(str(state["customer"]), quote=True)
    subject = html.escape(str(state["subject"]), quote=True)
    summary = html.escape(str(state["summary"]), quote=True)
    note = html.escape(str(state["note"]), quote=True)
    # Keep a stable ISO-like text field: native datetime-local keyboard input is
    # locale-segmented and the scripted User must not inherit host locale quirks.
    follow_up = html.escape(str(state["follow_up"]), quote=True)
    saved_notice = '<p role="status">Update saved.</p>' if saved else ""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shift Handoff - {ticket_id}</title>
<style>
body{{font:16px/1.45 system-ui,sans-serif;max-width:48rem;margin:2rem auto;padding:0 1rem;color:#17212b;background:#f5f7fa}}
main{{background:white;border:1px solid #d4dce5;border-radius:.5rem;padding:1.25rem}}
label{{display:block;font-weight:600;margin:.9rem 0 .3rem}}input,textarea,button{{font:inherit}}input,textarea{{box-sizing:border-box;width:100%;padding:.65rem;border:1px solid #66788a;border-radius:.25rem}}
button{{margin-top:1rem;padding:.65rem 1.2rem;background:#145a8d;color:white;border:0;border-radius:.25rem;cursor:pointer}}
.summary{{padding:.8rem;background:#edf3f8;border-radius:.25rem}}
</style></head><body><main>
<h1>Shift Handoff</h1><p><strong>Ticket:</strong> {ticket_id}</p>
<section aria-label="Ticket details" class="summary"><p><strong>Customer:</strong> {customer}</p><p><strong>Subject:</strong> {subject}</p><p>{summary}</p></section>
{saved_notice}
<form method="post" action="/submit">
<input type="hidden" name="ticket_id" value="{ticket_id}">
<label for="note">Internal update note</label>
<textarea id="note" name="note" rows="4" maxlength="500" aria-describedby="note-help" autofocus>{note}</textarea>
<p id="note-help">Record the latest carrier follow-up in a concise note.</p>
<label for="follow_up">Follow-up date and time (local)</label>
<input id="follow_up" name="follow_up" type="text" inputmode="numeric" placeholder="YYYY-MM-DD HH:MM" aria-describedby="follow-up-help" value="{follow_up}" required>
<p id="follow-up-help">Enter the local date and time in YYYY-MM-DD HH:MM format.</p>
<button type="submit">Save ticket update</button>
</form></main></body></html>"""
    return page.encode("utf-8")


def make_server(db_path: str | Path, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Build the ordinary GUI-facing web app, bound to caller-specified host/port.

    Pass ``port=0`` to let the OS choose an ephemeral port, then use
    ``server.server_address`` to discover the actual address.
    """
    path = str(Path(db_path))

    class Handler(BaseHTTPRequestHandler):
        server_version = "CoDeskHandoff/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            # Avoid writing request text/contents to stdout; callers own event logging.
            return

        def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8",
                  extra_headers: tuple[tuple[str, str], ...] = ()) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            for key, value in extra_headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send(200, b"ok", "text/plain; charset=utf-8")
            elif self.path == "/":
                self._send(200, _render_page(_read_ticket(path), saved=False))
            else:
                self._send(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            if self.path != "/submit":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            if size <= 0 or size > 8192:
                self._send(400, b"Invalid form submission", "text/plain; charset=utf-8")
                return
            raw = self.rfile.read(size)
            try:
                fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
                ticket_id = fields.get("ticket_id", [""])[0].strip()
                note_value = fields.get("note", [""])[0].strip()
                follow_value = fields.get("follow_up", [""])[0].strip().replace("T", " ")
                datetime.strptime(follow_value, "%Y-%m-%d %H:%M")
            except (UnicodeDecodeError, ValueError, KeyError):
                self._send(400, b"Please provide a valid date and time.", "text/plain; charset=utf-8")
                return
            if ticket_id != TICKET_ID or not note_value or len(note_value) > 500:
                self._send(400, b"Please complete the ticket update.", "text/plain; charset=utf-8")
                return
            received = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                with sqlite3.connect(path, timeout=5) as db:
                    db.execute("BEGIN IMMEDIATE")
                    changed = db.execute(
                        "UPDATE ticket SET note=?, follow_up=?, submitted=1, revision=revision+1 WHERE ticket_id=?",
                        (note_value, follow_value, ticket_id),
                    ).rowcount
                    if changed != 1:
                        db.rollback()
                        self._send(503, b"Ticket fixture is unavailable.", "text/plain; charset=utf-8")
                        return
                    db.execute(
                        "INSERT INTO submissions(ticket_id,note,follow_up,received_utc) VALUES (?,?,?,?)",
                        (ticket_id, note_value, follow_value, received),
                    )
                    db.commit()
            except sqlite3.Error:
                self._send(503, b"Could not save this update.", "text/plain; charset=utf-8")
                return
            body = _render_page(_read_ticket(path), saved=True)
            self._send(200, body)

    return ThreadingHTTPServer((host, int(port)), Handler)
