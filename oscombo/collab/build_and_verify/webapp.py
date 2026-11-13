"""Small local OrderDesk application server for the Build-and-Verify case."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_orders(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("order fixture must be a JSON array of objects")
    return rows


def _load_filtering(path: Path):
    # Each request loads the current editor-visible source to make the local
    # development server hot-reload the very code A edits.
    module_name = f"codesk_bv_filter_{time.time_ns()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load filter module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "filter_orders", None)):
        raise TypeError("filtering.py must define filter_orders(orders, query, status)")
    return module


def _append_jsonl(path: Path, value: dict, lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def make_server(workspace: str | Path, credentials: dict[str, str], event_log: str | Path,
                host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    root = Path(workspace).resolve()
    event_path = Path(event_log).resolve()
    orders_path = root / "data" / "orders.json"
    filter_path = root / "filtering.py"
    if not root.is_dir() or not orders_path.is_file() or not filter_path.is_file():
        raise FileNotFoundError("prepared OrderDesk workspace is incomplete")
    sessions: dict[str, str] = {}
    sessions_lock = threading.Lock()
    event_lock = threading.Lock()
    initial_order_ids = [row["order_id"] for row in _load_orders(orders_path)]

    class Handler(BaseHTTPRequestHandler):
        server_version = "NorthstarOrderDesk/0.1"

        def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8",
                  headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: object) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _actor(self) -> str | None:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
                token = cookie.get("bv_session").value if cookie.get("bv_session") else ""
            except Exception:
                token = ""
            with sessions_lock:
                return sessions.get(token)

        def _log(self, actor: str | None, event: str, details: dict) -> None:
            entry = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                     "timestamp_epoch": time.time(), "actor": actor, "event": event,
                     "route": urlparse(self.path).path, "details": details}
            if filter_path.is_file():
                entry["filter_source_sha256"] = _sha(filter_path)
            _append_jsonl(event_path, entry, event_lock)

        def _filtered(self, query: str, status: str) -> tuple[list[dict], str]:
            rows = _load_orders(orders_path)
            module = _load_filtering(filter_path)
            result = module.filter_orders(rows, query, status)
            if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
                raise TypeError("filter_orders must return a list of order objects")
            ids = [row.get("order_id") for row in result]
            if any(item not in initial_order_ids for item in ids) or len(ids) != len(set(ids)):
                raise ValueError("filter_orders returned unknown or duplicate order IDs")
            return result, _sha(filter_path)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            actor = self._actor()
            if parsed.path == "/health":
                try:
                    rows, source_hash = self._filtered("", "All")
                    self._json(200, {"ok": True, "app": "Northstar OrderDesk", "fixture_rows": len(rows),
                                     "filter_source_sha256": source_hash})
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
                return
            if parsed.path == "/login":
                self._log(None, "login_page", {})
                self._send(200, _login_html().encode())
                return
            if parsed.path in {"/static/app.js", "/static/style.css"}:
                name = Path(parsed.path).name
                path = root / "static" / name
                if not path.is_file():
                    self._send(404, b"not found")
                    return
                kind = "text/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8"
                self._send(200, path.read_bytes(), kind, {"X-Content-SHA256": _sha(path)})
                return
            if actor is None:
                self._send(303, b"", headers={"Location": "/login"})
                return
            if parsed.path == "/":
                self._log(actor, "page_view", {"context": "order_queue"})
                self._send(200, (root / "static" / "index.html").read_bytes())
                return
            if parsed.path == "/api/orders":
                query = parse_qs(parsed.query)
                q = query.get("query", [""])[0]
                status = query.get("status", ["All"])[0]
                try:
                    rows, source_hash = self._filtered(q, status)
                    self._log(actor, "order_filter_view", {"query": q, "status": status,
                                                               "visible_ids": [x["order_id"] for x in rows]})
                    self._json(200, {"orders": rows, "filter_source_sha256": source_hash})
                except Exception as exc:
                    self._log(actor, "filter_error", {"query": q, "status": status,
                                                       "error": f"{type(exc).__name__}: {exc}"})
                    self._json(500, {"error": f"Filter could not be applied: {exc}"})
                return
            self._send(404, b"not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/login":
                size = int(self.headers.get("Content-Length", "0"))
                form = parse_qs(self.rfile.read(min(size, 4096)).decode("utf-8", "replace"))
                actor = form.get("actor", [""])[0]
                password = form.get("password", [""])[0]
                if actor not in credentials or not secrets.compare_digest(password, credentials[actor]):
                    self._log(actor if actor in credentials else None, "login_rejected", {"actor": actor})
                    self._send(401, _login_html("Sign-in failed. Check the assigned role and password.").encode())
                    return
                token = secrets.token_urlsafe(32)
                with sessions_lock:
                    sessions[token] = actor
                self._log(actor, "login_success", {})
                self._send(303, b"", headers={"Location": "/", "Set-Cookie":
                            f"bv_session={token}; HttpOnly; SameSite=Strict; Path=/"})
                return
            actor = self._actor()
            if actor is None:
                self._json(401, {"error": "sign-in required"})
                return
            if parsed.path != "/api/test-events":
                self._json(404, {"error": "not found"})
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size > 16_384:
                self._json(413, {"error": "event too large"})
                return
            try:
                payload = json.loads(self.rfile.read(size) or b"{}")
                method = str(payload.get("method", ""))
                if method not in {"initial", "enter", "button", "clear"}:
                    raise ValueError("invalid browser interaction method")
                query = str(payload.get("query", ""))[:200]
                status = str(payload.get("status", "All"))
                rows, source_hash = self._filtered(query, status)
                server_ids = [row["order_id"] for row in rows]
                client_ids = payload.get("visible_ids", [])
                if not isinstance(client_ids, list):
                    raise ValueError("visible_ids must be an array")
                details = {"method": method, "query": query, "status": status,
                           "visible_ids_client": client_ids, "visible_ids_server": server_ids,
                           "client_server_match": client_ids == server_ids,
                           "filter_source_sha256": source_hash}
                self._log(actor, "browser_test", details)
                self._json(201, {"recorded": True, "client_server_match": client_ids == server_ids})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, fmt, *args):
            return

    return ThreadingHTTPServer((host, port), Handler)


def _login_html(message: str = "") -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>OrderDesk sign in</title>
<link rel="stylesheet" href="/static/style.css"><main><section><h1>OrderDesk sign in</h1>
<p role="alert">{safe}</p><form action="/login" method="post">
<label for="actor">Assigned role</label><select id="actor" name="actor"><option>A</option><option>B</option><option>S</option></select>
<label for="password">Run password</label><input id="password" name="password" type="password" required autofocus>
<button type="submit">Sign in</button></form></section></main></html>"""


def run_server(workspace: str | Path, credentials: dict[str, str], event_log: str | Path,
               host: str = "127.0.0.1", port: int = 8765) -> None:
    server = make_server(workspace, credentials, event_log, host, port)
    print(json.dumps({"ready": True, "host": host, "port": server.server_port,
                      "app": "Northstar OrderDesk"}, flush=True))
    try:
        server.serve_forever()
    finally:
        server.server_close()
