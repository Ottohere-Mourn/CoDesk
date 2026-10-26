"""Small run-scoped message and attachment service; no hidden evaluator access."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class ProtocolStore:
    def __init__(self, root: str | Path, run_id: str, max_attachment_bytes: int = 10_000_000):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.attach_dir = self.root / "attachments"
        self.attach_dir.mkdir(exist_ok=True)
        self.log_path = self.root / "events.jsonl"
        self.run_id = run_id
        self.max_attachment_bytes = max_attachment_bytes
        self._lock = threading.Lock()
        if self.log_path.exists() or any(self.attach_dir.iterdir()):
            raise FileExistsError("protocol run directory is not empty; use a new run_id/root to preserve provenance")

    def _record(self, event: dict[str, object]) -> None:
        event = {"run_id": self.run_id, "timestamp": time.time(), **event}
        with self._lock, self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")

    def send(self, actor: str, recipient: str, body: str, attachment_ids: list[str]) -> dict[str, object]:
        if actor not in {"A", "B", "S"} or recipient not in {"A", "B", "S", "all"}:
            raise ValueError("invalid actor/recipient")
        if not body.strip() and not attachment_ids:
            raise ValueError("message must contain text or an attachment")
        for aid in attachment_ids:
            if not (self.attach_dir / f"{aid}.bin").is_file():
                raise ValueError(f"unknown attachment: {aid}")
        event = {"type": "message", "message_id": str(uuid.uuid4()), "actor": actor,
                 "recipient": recipient, "body": body, "attachment_ids": attachment_ids}
        self._record(event)
        return event

    def messages(self, actor: str, after: float = 0.0) -> list[dict[str, object]]:
        if actor not in {"A", "B", "S"}:
            raise ValueError("invalid actor")
        if not self.log_path.exists():
            return []
        out = []
        with self._lock, self.log_path.open(encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if (event.get("type") == "message" and float(event["timestamp"]) > after
                        and event["recipient"] in (actor, "all") and event["actor"] != actor):
                    out.append(event)
        return out

    def put_attachment(self, actor: str, filename: str, content: bytes) -> dict[str, object]:
        if actor not in {"A", "B", "S"}:
            raise ValueError("invalid actor")
        clean_name = Path(filename).name
        if not clean_name or clean_name in {".", ".."}:
            raise ValueError("invalid filename")
        if len(content) > self.max_attachment_bytes:
            raise ValueError("attachment exceeds configured size limit")
        aid = str(uuid.uuid4())
        digest = hashlib.sha256(content).hexdigest()
        path = self.attach_dir / f"{aid}.bin"
        path.write_bytes(content)
        event = {"type": "attachment", "attachment_id": aid, "actor": actor,
                 "filename": clean_name, "bytes": len(content), "sha256": digest}
        self._record(event)
        return event

    def get_attachment(self, actor: str, attachment_id: str) -> bytes:
        if actor not in {"A", "B", "S"}:
            raise ValueError("invalid actor")
        # Any case participant can read shared attachments. IDs are UUIDs and
        # path resolution is still constrained to the run's attachment folder.
        candidate = (self.attach_dir / f"{attachment_id}.bin").resolve()
        if candidate.parent != self.attach_dir or not candidate.is_file():
            raise FileNotFoundError(attachment_id)
        return candidate.read_bytes()


def make_server(store: ProtocolStore, actor_tokens: dict[str, str], host: str = "127.0.0.1", port: int = 0):
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("protocol server must bind to loopback")

    class Handler(BaseHTTPRequestHandler):
        def _actor(self):
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            for actor, secret in actor_tokens.items():
                if secrets.compare_digest(token, secret):
                    return actor
            self.send_error(401, "invalid actor token")
            return None

        def _json(self, status: int, payload: object):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            actor = self._actor()
            if actor is None:
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n > store.max_attachment_bytes + 100_000:
                    return self._json(413, {"error": "request too large"})
                payload = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/artifacts/publish":
                    bridge = getattr(self.server, "workspace_bridge", None)
                    if bridge is None:
                        return self._json(404, {"error": "workspace bridge unavailable"})
                    if payload:
                        return self._json(400, {"error": "publication uses the authenticated actor's fixed path"})
                    try:
                        return self._json(200, bridge.publish(actor))
                    except Exception as exc:
                        return self._json(409, {"error": str(exc)})
                if self.path == "/messages":
                    event = store.send(actor, str(payload.get("recipient", "all")),
                                       str(payload.get("body", "")), list(payload.get("attachment_ids", [])))
                    return self._json(201, event)
                if self.path == "/attachments":
                    raw = base64.b64decode(payload["content_base64"], validate=True)
                    event = store.put_attachment(actor, str(payload.get("filename", "attachment.bin")), raw)
                    return self._json(201, event)
                return self._json(404, {"error": "not found"})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                return self._json(400, {"error": str(exc)})

        def do_GET(self):
            actor = self._actor()
            if actor is None:
                return
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/artifacts":
                    bridge = getattr(self.server, "workspace_bridge", None)
                    if bridge is None:
                        return self._json(404, {"error": "workspace bridge unavailable"})
                    return self._json(200, bridge.snapshot())
                if parsed.path == "/messages":
                    return self._json(200, store.messages(actor, float(query.get("after", [0])[0])))
                if parsed.path.startswith("/attachments/"):
                    aid = parsed.path.rsplit("/", 1)[-1]
                    data = store.get_attachment(actor, aid)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                return self._json(404, {"error": "not found"})
            except (ValueError, FileNotFoundError) as exc:
                return self._json(404, {"error": str(exc)})

        def log_message(self, format, *args):  # keep API logs in protocol event file only
            return

    return ThreadingHTTPServer((host, port), Handler)
