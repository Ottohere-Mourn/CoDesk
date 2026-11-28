"""Local single-session demo portal for BC-01."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import html
import io
import json
import secrets
import threading
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PORT = 8090
INVOICES = [
    {
        "invoice_id": "INV-5107", "vendor": "Northstar Components",
        "invoice_date": "2026-10-04", "po_id": "PO-7104",
        "amount_usd": "1280.50", "match_status": "MATCHED",
        "approval_status": "PENDING",
    },
    {
        "invoice_id": "INV-5112", "vendor": "Meridian Office",
        "invoice_date": "2026-10-08", "po_id": "PO-7118",
        "amount_usd": "642.00", "match_status": "MATCHED",
        "approval_status": "PENDING",
    },
    {
        "invoice_id": "INV-5121", "vendor": "Pine Ridge Logistics",
        "invoice_date": "2026-10-15", "po_id": "PO-7131",
        "amount_usd": "2395.75", "match_status": "MATCHED",
        "approval_status": "PENDING",
    },
]
VENDORS = [
    {
        "vendor_id": "V-204", "vendor_name": "Northstar Components",
        "certificate_id": "ISO-9001-204", "certificate_expiry": "2027-08-31",
        "compliance_status": "REVIEW", "reviewer_note": "",
    },
    {
        "vendor_id": "V-219", "vendor_name": "Meridian Office",
        "certificate_id": "SOC2-219", "certificate_expiry": "2027-03-31",
        "compliance_status": "PENDING", "reviewer_note": "",
    },
    {
        "vendor_id": "V-233", "vendor_name": "Pine Ridge Logistics",
        "certificate_id": "C-TPAT-233", "certificate_expiry": "2027-01-31",
        "compliance_status": "REVIEW", "reviewer_note": "",
    },
]

# PBKDF2 verifiers keep the other role's plaintext credential out of shared files.
USERS = {
    "fin_auditor": {
        "role": "finance", "salt": "626330312d66696e2d612d73616c74",
        "digest": "a4f3ed38642aaf52f37156d65748743e054972fdc7382e92be0ffae8244a4630",
    },
    "ops_buyer": {
        "role": "procurement", "salt": "626330312d6f70732d622d73616c74",
        "digest": "8806f3fbeadb3e295435176f281406d9b70570a01dec3e50f954337a0748eabe",
    },
}


def initial_state() -> dict:
    return {"invoices": [dict(row) for row in INVOICES], "vendors": [dict(row) for row in VENDORS], "revision": 0}


def _verify_password(username: str, password: str) -> str | None:
    user = USERS.get(username)
    if user is None:
        return None
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(user["salt"]), 120000
    ).hex()
    return user["role"] if hmac.compare_digest(digest, user["digest"]) else None


class PortalState:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.lock = threading.RLock()
        self.active_session: str | None = None
        self.session_role: str | None = None
        self.state = initial_state()
        if state_path.exists():
            try:
                loaded = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(loaded.get("invoices"), list) and isinstance(loaded.get("vendors"), list):
                    self.state = loaded
            except (OSError, json.JSONDecodeError):
                pass
        else:
            self.save()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.state_path)

    def role_for(self, token: str | None) -> str | None:
        if token and token == self.active_session:
            return self.session_role
        return None


def _table(headers: list[str], rows: list[dict], actions: str = "") -> str:
    th = "".join(f"<th>{html.escape(name)}</th>" for name in headers)
    tr = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(name, '')))}</td>" for name in headers)
        tr.append(f"<tr>{cells}{actions.format(id=html.escape(str(row.get(headers[0], ''))))}</tr>")
    return f"<table><thead><tr>{th}<th>Action</th></tr></thead><tbody>{''.join(tr)}</tbody></table>"


def _page(title: str, content: str, role: str | None = None) -> bytes:
    nav = ""
    if role:
        nav = (
            '<nav><a href="/">Portal Home</a> · '
            '<a href="/finance/invoices">Finance</a> · '
            '<a href="/procurement/vendors">Procurement</a></nav>'
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{font:16px Arial,sans-serif;margin:32px;background:#f5f7fb;color:#172033}}main{{max-width:1100px;margin:auto;background:white;padding:24px;border-radius:12px;box-shadow:0 2px 12px #0001}}
nav{{margin-bottom:20px}}a{{color:#1357a6}}table{{width:100%;border-collapse:collapse;margin:18px 0}}th,td{{border:1px solid #d8deea;padding:10px;text-align:left}}th{{background:#e9eef7}}button{{padding:8px 12px;background:#155cbd;color:white;border:0;border-radius:5px}}label{{display:block;margin:12px 0}}input,select{{padding:8px}}.status{{font-weight:bold;color:#185d33}}.note{{color:#586276}}
</style></head><body><main>{nav}<h1>{html.escape(title)}</h1>{content}</main></body></html>"""
    return document.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "BC01Portal/1.0"
    portal: PortalState

    def log_message(self, fmt: str, *args) -> None:
        return

    def _cookie(self) -> str | None:
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        morsel = cookies.get("portal_session")
        return morsel.value if morsel else None

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8", headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, headers: dict | None = None):
        self.send_response(303)
        self.send_header("Location", location)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _login_page(self, message: str = ""):
        note = f'<p class="note">{html.escape(message)}</p>' if message else ""
        body = note + """<p>Sign in to the enterprise portal.</p>
<form method="post" action="/login"><label>Username <input name="username" autocomplete="username" required></label>
<label>Password <input type="password" name="password" autocomplete="current-password" required></label>
<button type="submit">Sign in</button></form>"""
        self._send(200, _page("Enterprise Portal Sign In", body))

    def _current_role(self) -> str | None:
        return self.portal.role_for(self._cookie())

    def do_GET(self):
        path = urlparse(self.path).path
        role = self._current_role()
        if path == "/" and not role:
            self._login_page()
            return
        if not role:
            self._login_page("Your session needs to be refreshed. Sign in to continue.")
            return
        if path == "/":
            body = (
                '<p class="status">Signed in successfully.</p>'
                '<p><a href="/finance/invoices">Open Finance Invoices</a></p>'
                '<p><a href="/procurement/vendors">Open Procurement Vendors</a></p>'
            )
            self._send(200, _page("Enterprise Portal", body, role))
            return
        if path == "/finance/invoices" and role == "finance":
            with self.portal.lock:
                rows = [dict(row) for row in self.portal.state["invoices"]]
            actions = '<td><form method="post" action="/invoice/approve"><input type="hidden" name="invoice_id" value="{id}"><button type="submit">Approve</button></form></td>'
            content = _table(
                ["invoice_id", "vendor", "invoice_date", "po_id", "amount_usd", "match_status", "approval_status"],
                rows, actions,
            )
            content += '<p><a href="/export/finance.csv">Export Finance Ledger CSV</a></p>'
            self._send(200, _page("Finance · Invoices", content, role))
            return
        if path == "/procurement/vendors" and role == "procurement":
            with self.portal.lock:
                rows = [dict(row) for row in self.portal.state["vendors"]]
            actions = '<td><form method="post" action="/vendor/status"><input type="hidden" name="vendor_id" value="{id}"><select name="status"><option>COMPLIANT</option><option>REVIEW</option><option>PENDING</option></select><button type="submit">Update</button></form></td>'
            content = _table(
                ["vendor_id", "vendor_name", "certificate_id", "certificate_expiry", "compliance_status", "reviewer_note"],
                rows, actions,
            )
            content += '<p><a href="/export/vendors.csv">Export Supplier Compliance List CSV</a></p>'
            self._send(200, _page("Procurement · Vendors", content, role))
            return
        if path == "/export/finance.csv" and role == "finance":
            with self.portal.lock:
                rows = [dict(row) for row in self.portal.state["invoices"]]
            self._csv(["invoice_id", "vendor", "invoice_date", "po_id", "amount_usd", "approval_status"], rows)
            return
        if path == "/export/vendors.csv" and role == "procurement":
            with self.portal.lock:
                rows = [dict(row) for row in self.portal.state["vendors"]]
            self._csv(["vendor_id", "vendor_name", "certificate_id", "certificate_expiry", "compliance_status"], rows)
            return
        self._send(404, _page("Not Found", "<p>The requested page is not available for this account.</p>", role))

    def _csv(self, columns: list[str], rows: list[dict]):
        buff = io.StringIO(newline="")
        writer = csv.DictWriter(buff, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self._send(
            200, buff.getvalue().encode("utf-8"), "text/csv; charset=utf-8",
            {"Content-Disposition": 'attachment; filename="export_report.csv"'},
        )

    def do_POST(self):
        path = urlparse(self.path).path
        length = min(int(self.headers.get("Content-Length", "0")), 65536)
        fields = parse_qs(self.rfile.read(length).decode("utf-8", "replace"), keep_blank_values=True)
        get = lambda key: fields.get(key, [""])[0]
        if path == "/login":
            role = _verify_password(get("username"), get("password"))
            if role is None:
                self._login_page("The username or password was not recognized.")
                return
            token = secrets.token_urlsafe(24)
            with self.portal.lock:
                self.portal.active_session = token
                self.portal.session_role = role
            self._redirect(
                "/" if role == "finance" else "/procurement/vendors",
                {"Set-Cookie": f"portal_session={token}; Path=/; HttpOnly; SameSite=Lax"},
            )
            return
        role = self._current_role()
        if not role:
            self._login_page("Your session needs to be refreshed. Sign in to continue.")
            return
        if path == "/invoice/approve" and role == "finance":
            invoice_id = get("invoice_id")
            with self.portal.lock:
                for row in self.portal.state["invoices"]:
                    if row["invoice_id"] == invoice_id:
                        row["approval_status"] = "APPROVED"
                        self.portal.state["revision"] = int(self.portal.state.get("revision", 0)) + 1
                        self.portal.save()
                        break
            self._redirect("/finance/invoices")
            return
        if path == "/vendor/status" and role == "procurement":
            vendor_id, status = get("vendor_id"), get("status")
            if status not in {"COMPLIANT", "REVIEW", "PENDING"}:
                self._send(400, _page("Invalid Status", "<p>Select a valid status.</p>", role))
                return
            with self.portal.lock:
                for row in self.portal.state["vendors"]:
                    if row["vendor_id"] == vendor_id:
                        row["compliance_status"] = status
                        self.portal.state["revision"] = int(self.portal.state.get("revision", 0)) + 1
                        self.portal.save()
                        break
            self._redirect("/procurement/vendors")
            return
        self._send(404, _page("Not Found", "<p>The requested action is not available.</p>", role))


def make_server(state_path: Path, port: int = PORT) -> ThreadingHTTPServer:
    portal = PortalState(state_path)
    handler = type("PortalHandler", (Handler,), {"portal": portal})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-path", type=Path, default=Path.home() / "workspace/bc01/.portal_state.json")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    server = make_server(args.state_path, args.port)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
