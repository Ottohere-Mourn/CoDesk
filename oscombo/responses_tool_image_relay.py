"""Loopback Responses relay for provider compatibility with Codex GUI requests.

By default the request body is forwarded byte-for-byte, while Codex-specific
metadata headers are omitted. Some compatible endpoints intermittently fail to
interpret screenshot tool results when these headers are forwarded. An optional
image-promotion mode exists for separate diagnostics, but is not the default.
No request body, image, or credential is written to the event log.

Use only with a trusted upstream and a run-owned loopback process. Codex's
request/stream retry policy remains responsible for transient transport errors.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests


def move_latest_tool_image(body: dict) -> bool:
    """Move one latest tool screenshot to a standard image-bearing user turn."""
    history = body.get("input")
    if not isinstance(history, list):
        return False
    for item in reversed(history):
        if not isinstance(item, dict) or item.get("type") != "function_call_output":
            continue
        output = item.get("output")
        if not isinstance(output, list):
            continue
        images = [part for part in output if isinstance(part, dict)
                  and part.get("type") == "input_image"]
        if not images:
            continue
        item["output"] = [part for part in output if part not in images]
        history.append({"role": "user", "content": [
            {"type": "input_text", "text": "Current desktop screenshot from the preceding tool call."},
            *images,
        ]})
        return True
    return False


def make_server(host: str, port: int, upstream: str, api_key: str,
                event_log: Path | None = None,
                promote_tool_image: bool = False,
                client_token: str | None = None) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("the image relay must bind to loopback")
    url = urlparse(upstream.rstrip("/"))
    if url.scheme not in {"https", "http"} or not url.netloc:
        raise ValueError("invalid upstream Responses base URL")
    if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("unencrypted upstream must be loopback")
    target = upstream.rstrip("/") + "/responses"
    if not client_token:
        raise ValueError("a run-scoped client token is required")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            raw = b'{"ready":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            route = re.fullmatch(r"/(?:actor/([ABS])/)?v1/responses", self.path)
            if route is None:
                self.send_error(404)
                return
            if not hmac.compare_digest(self.headers.get("Authorization", ""),
                                       f"Bearer {client_token}"):
                self.send_error(401)
                return
            started = time.monotonic()
            started_at = time.time()
            actor = route.group(1)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 32 * 1024 * 1024:
                    self.send_error(413)
                    return
                raw = self.rfile.read(length)
                model = json.loads(raw).get("model")
                moved = False
                if promote_tool_image:
                    body = json.loads(raw)
                    moved = move_latest_tool_image(body)
                    if moved:
                        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
                with requests.post(target, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": self.headers.get("Accept", "text/event-stream"),
                }, data=raw, stream=True, timeout=(15, 300)) as upstream_response:
                    self.send_response(upstream_response.status_code)
                    self.send_header("Content-Type", upstream_response.headers.get(
                        "Content-Type", "text/event-stream"))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    first_byte_at = None
                    response_tail = b""
                    for chunk in upstream_response.iter_content(chunk_size=8192):
                        if chunk:
                            if first_byte_at is None:
                                first_byte_at = time.time()
                            response_tail = (response_tail + chunk)[-2 * 1024 * 1024:]
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    self.close_connection = True
                    status = upstream_response.status_code
                    usage = None
                    candidates = [response_tail] if "text/event-stream" not in upstream_response.headers.get("Content-Type", "") else [
                        line[6:] for line in response_tail.splitlines() if line.startswith(b"data: ")]
                    for candidate in candidates:
                        try:
                            item = json.loads(candidate)
                            record = item.get("response", item)
                            if isinstance(record.get("usage"), dict):
                                usage = record["usage"]
                        except (ValueError, AttributeError):
                            pass
                if event_log is not None:
                    with event_log.open("a", encoding="utf-8") as log:
                        log.write(json.dumps({"time": time.time(), "started_at": started_at,
                                              "first_byte_at": first_byte_at, "actor": actor,
                                              "model": model, "usage": usage, "image_moved": moved,
                                              "request_bytes": len(raw), "upstream_status": status,
                                              "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")
            except Exception as exc:
                if event_log is not None:
                    with event_log.open("a", encoding="utf-8") as log:
                        log.write(json.dumps({"time": time.time(), "started_at": started_at,
                                              "actor": actor, "error_type": type(exc).__name__,
                                              "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")
                try:
                    self.send_error(502, "Responses relay upstream error")
                except OSError:
                    pass

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, help="provider base URL ending in /v1")
    parser.add_argument("--api-key-env", required=True)
    parser.add_argument("--client-token-env", required=True,
                        help="run-scoped local Bearer token; distinct from provider key")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--promote-tool-image", action="store_true",
                        help="diagnostic only: move the latest tool image into a user message")
    args = parser.parse_args()
    key = os.environ.get(args.api_key_env)
    if not key:
        parser.error(f"{args.api_key_env} is unset")
    client_token = os.environ.get(args.client_token_env)
    if not client_token:
        parser.error(f"{args.client_token_env} is unset")
    server = make_server(args.host, args.port, args.upstream, key, args.event_log,
                         promote_tool_image=args.promote_tool_image,
                         client_token=client_token)
    if args.ready_file:
        args.ready_file.write_text(json.dumps({"pid": os.getpid(),
                                               "host": args.host,
                                               "port": server.server_port}) + "\n")
        args.ready_file.chmod(0o600)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
