"""Synthetic Shift Triage Brief GUI app used by HA-TRIAGE.

The browser-facing page contains no expected decision or answer key. The offline
oracle checks the latest persisted, form-submitted triage brief.
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

FIXTURE_ID = "shift-triage-t1042-v1"
TICKET_ID = "T-1042"
_EXPECTED = {
    "ticket_id": TICKET_ID,
    "issue_class": "delivery_damage",
    "recommendation": "prepare_item_refund",
    "source_refs": ("DELIVERY-EV-77", "POLICY-RET-4"),
}
_INITIAL = {"ticket_id": TICKET_ID, "submission_count": 0}

def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()

def create_fixture(db_path: str | Path, run_id: str) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
            DROP TABLE IF EXISTS triage_brief;
            DROP TABLE IF EXISTS run_meta;
            CREATE TABLE run_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE triage_brief(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                issue_class TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                source_refs TEXT NOT NULL,
                rationale TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                received_utc TEXT NOT NULL
            );
        """)
        db.execute("INSERT INTO run_meta VALUES('run_id', ?)", (str(run_id),))
        db.execute("INSERT INTO run_meta VALUES('fixture_id', ?)", (FIXTURE_ID,))
        db.commit()
    public = {"fixture_id": FIXTURE_ID, "run_id": str(run_id), "schema_version": 1,
              "initial_state": dict(_INITIAL)}
    manifest = {**public, "sha256": hashlib.sha256(_canonical_bytes(public)).hexdigest()}
    path.with_suffix(path.suffix + ".fixture.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest

def evaluate(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    try:
        with sqlite3.connect(path) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute("SELECT * FROM triage_brief ORDER BY sequence")]
            fixture_id = db.execute("SELECT value FROM run_meta WHERE key='fixture_id'").fetchone()
    except (OSError, sqlite3.Error):
        return {"success": False, "checks": {"fixture_exists": False, "submitted": False}}
    latest = rows[-1] if rows else None
    refs = set((latest or {}).get("source_refs", "").upper().replace(",", " ").replace(";", " ").split())
    rationale = " ".join((latest or {}).get("rationale", "").lower().split())
    checks = {
        "fixture_exists": bool(fixture_id and fixture_id["value"] == FIXTURE_ID),
        "submitted": latest is not None,
        "ticket_id": bool(latest and latest["ticket_id"] == _EXPECTED["ticket_id"]),
        "issue_class": bool(latest and latest["issue_class"] == _EXPECTED["issue_class"]),
        "recommendation": bool(latest and latest["recommendation"] == _EXPECTED["recommendation"]),
        "delivery_evidence_cited": _EXPECTED["source_refs"][0] in refs,
        "policy_cited": _EXPECTED["source_refs"][1] in refs,
        "concise_reasoning": all(term in rationale for term in ("dock", "damage", "shipping")),
        "submitted_by_agent_role": bool(latest and latest["actor_id"] == "S"),
    }
    return {"success": all(checks.values()), "checks": checks,
            "submission_count": len(rows),
            "latest": {k: latest.get(k) for k in ("ticket_id", "issue_class", "recommendation",
                         "source_refs", "rationale", "actor_id")} if latest else None}

def _page(saved: bool = False, values: dict[str, str] | None = None) -> bytes:
    values = values or {}
    ticket = html.escape(values.get("ticket_id", TICKET_ID), quote=True)
    issue = values.get("issue_class", "")
    rec = values.get("recommendation", "")
    issue_opts = [("", "Choose an issue type"), ("delivery_damage", "Damage during delivery"),
                  ("wrong_item", "Wrong item supplied"), ("missing_item", "Item missing"),
                  ("late_delivery", "Late delivery")]
    rec_opts = [("", "Choose a next step"), ("prepare_item_refund", "Prepare an item-level refund"),
                ("request_more_evidence", "Request more evidence"),
                ("decline_request", "Decline the request under policy")]
    def options(rows, selected):
        return "".join(f'<option value="{html.escape(v, quote=True)}"{" selected" if v == selected else ""}>{html.escape(label)}</option>'
                       for v, label in rows)
    notice = '<p role="status">Triage brief saved.</p>' if saved else ""
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Shift Triage Brief</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font:17px/1.45 system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;background:#f4f6f8;color:#17212b}}
main{{background:white;padding:1.4rem;border:1px solid #cbd5df;border-radius:.5rem}}
label{{display:block;font-weight:600;margin:1rem 0 .25rem}}input,select,textarea,button{{font:inherit}}
input,select,textarea{{box-sizing:border-box;width:100%;padding:.6rem;border:1px solid #718397;border-radius:.25rem}}
textarea{{min-height:6rem}}button{{margin-top:1rem;padding:.6rem 1.2rem;background:#145a8d;color:white;border:0;border-radius:.25rem}}</style>
</head><body><main><h1>Shift Triage Brief</h1>
<p>Prepare a short internal handoff using the Case Desk source records. This brief does not execute a refund or change ticket status.</p>
{notice}<form method="post" action="/submit">
<label for="ticket_id">Ticket ID</label><input id="ticket_id" name="ticket_id" value="{ticket}" required>
<label for="issue_class">Issue classification</label><select id="issue_class" name="issue_class" required>{options(issue_opts, issue)}</select>
<label for="recommendation">Recommended next step</label><select id="recommendation" name="recommendation" required>{options(rec_opts, rec)}</select>
<label for="source_refs">Evidence and policy references</label><input id="source_refs" name="source_refs" placeholder="Enter the source record IDs you checked" value="{html.escape(values.get("source_refs", ""), quote=True)}" required>
<label for="rationale">Brief rationale</label><textarea id="rationale" name="rationale" maxlength="400" placeholder="Summarize the evidence, recommended action, and any limit to carry forward." required>{html.escape(values.get("rationale", ""))}</textarea>
<button type="submit">Save triage brief</button></form></main></body></html>"""
    return body.encode("utf-8")

def make_server(db_path: str | Path, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    path = str(Path(db_path))
    access_path = Path(db_path).with_suffix(".http.jsonl")
    access_path.parent.mkdir(parents=True, exist_ok=True)
    access = open(access_path, "a", encoding="utf-8")
    class Handler(BaseHTTPRequestHandler):
        server_version = "CoDeskTriageBrief/1.0"
        def log_message(self, fmt: str, *args: Any) -> None:
            access.write(json.dumps({"method": self.command, "path": self.path,
                         "status": getattr(self, "_status", 200)}) + "\n")
            access.flush()
        def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
            self._status = status
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send(200, b"ok", "text/plain; charset=utf-8")
            elif self.path == "/":
                self._send(200, _page())
            elif self.path == "/saved":
                self._send(200, _page(saved=True))
            else:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
        def do_POST(self) -> None:
            if self.path != "/submit":
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 8192: raise ValueError("invalid form size")
                fields = parse_qs(self.rfile.read(size).decode("utf-8"), keep_blank_values=True, strict_parsing=True)
                data = {key: fields.get(key, [""])[0].strip() for key in
                        ("ticket_id", "issue_class", "recommendation", "source_refs", "rationale")}
                if data["ticket_id"] != TICKET_ID or not all(data[k] for k in data):
                    raise ValueError("required field missing or unknown ticket")
            except (UnicodeDecodeError, ValueError, KeyError):
                self._send(400, b"Please complete all triage fields for T-1042.", "text/plain; charset=utf-8")
                return
            with sqlite3.connect(path) as db:
                db.execute("""INSERT INTO triage_brief
                    (ticket_id,issue_class,recommendation,source_refs,rationale,actor_id,received_utc)
                    VALUES(?,?,?,?,?,?,?)""",
                    (data["ticket_id"], data["issue_class"], data["recommendation"], data["source_refs"],
                     data["rationale"], "S", datetime.now(timezone.utc).isoformat()))
                db.commit()
            self._send(200, _page(saved=True, values=data))
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.access_log = access
    return server
