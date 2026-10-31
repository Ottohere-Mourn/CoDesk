"""Loopback Responses relay for provider compatibility with Codex GUI requests.

By default the request body is forwarded byte-for-byte, while Codex-specific
metadata headers are omitted. Some compatible endpoints intermittently fail to
interpret screenshot tool results when these headers are forwarded. An optional
image-promotion mode exists for separate diagnostics, but is not the default.
No request body, image, or credential is written to the event log.

Use only with trusted upstreams and a run-owned loopback process. A second,
preflighted endpoint may be used once when TLS setup fails before a response is
received; HTTP errors and stream failures are never retried to avoid duplicate
model requests.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool


_upload_metrics = threading.local()


def upload_deadline_s(body_bytes: int) -> float:
    """Bound writes separately from TLS connect and response reads."""
    return min(120.0, max(15.0, 10.0 + body_bytes / (128 * 1024)))


def upload_observation() -> dict:
    return dict(getattr(_upload_metrics, 'row', {}))


class UploadDeadlineHTTPSConnection(HTTPSConnection):
    def request(self, *args, **kwargs):
        body = kwargs.get('body', args[2] if len(args) > 2 else None)
        length = len(body) if isinstance(body, (bytes, str)) else 0
        deadline = upload_deadline_s(length)
        # urllib3 validates/connects TLS before calling request(). Its usual
        # connect deadline otherwise also limits sendall() for the whole body.
        row = {'request_bytes': length, 'write_timeout_s': deadline,
               'tls_connected_before_upload': self.sock is not None,
               'upload_complete': False}
        _upload_metrics.row = row
        previous_timeout = self.timeout
        if self.sock is None:
            self.connect()
        row['tls_connected_before_upload'] = self.sock is not None
        row['connect_timeout_s'] = previous_timeout
        started = time.monotonic()
        # HTTPConnection.request() reapplies self.timeout to its socket.
        self.timeout = deadline
        try:
            result = super().request(*args, **kwargs)
            row['upload_complete'] = True
            row['socket_timeout_after_upload_s'] = self.sock.gettimeout() if self.sock else None
            return result
        finally:
            row['upload_s'] = round(time.monotonic() - started, 4)
            self.timeout = previous_timeout
            if self.sock is not None:
                self.sock.settimeout(self.timeout)


class UploadDeadlineHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = UploadDeadlineHTTPSConnection


class UploadDeadlineAdapter(HTTPAdapter):
    @staticmethod
    def configure(manager):
        manager.pool_classes_by_scheme = dict(manager.pool_classes_by_scheme)
        manager.pool_classes_by_scheme['https'] = UploadDeadlineHTTPSPool

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.configure(self.poolmanager)

    def proxy_manager_for(self, *args, **kwargs):
        manager = super().proxy_manager_for(*args, **kwargs)
        self.configure(manager)
        return manager


def make_upload_session() -> requests.Session:
    session = requests.Session()
    session.mount('https://', UploadDeadlineAdapter(max_retries=0))
    return session


def summarize_request(raw: bytes) -> dict:
    """Log model/tool/image metadata without persisting prompt or image contents."""
    try:
        body = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"request_json": False}
    tool_names = []
    for tool in body.get("tools", []):
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not name and isinstance(tool.get("function"), dict):
            name = tool["function"].get("name")
        if isinstance(name, str):
            tool_names.append(name)
    image_parts = 0
    def visit(value):
        nonlocal image_parts
        if isinstance(value, dict):
            if value.get("type") in {"input_image", "image_url"}:
                image_parts += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(body.get("input"))
    return {"request_json": True, "model": body.get("model"),
            "tool_names": tool_names, "input_image_parts": image_parts}


def move_latest_tool_image(body: dict, task_reminder: str = "") -> bool:
    """Promote the latest screenshot and prune superseded tool images.

    Codex resends the conversation history on each Responses request. Keeping
    every screenshot image in the tool transcript makes vision context grow
    quadratically over a GUI task and can crowd out the task instructions. Keep
    tool text/history intact, but include only the newest desktop screenshot.
    Explicit user-provided images are not changed.
    """
    history = body.get("input")
    if not isinstance(history, list):
        return False

    latest_item = None
    latest_images = None
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
        latest_item = item
        latest_images = images
        break
    if latest_item is None or latest_images is None:
        return False

    screenshot_marker = "Current desktop screenshot from the preceding tool call."
    pruned_history = []
    for item in history:
        if not isinstance(item, dict):
            pruned_history.append(item)
            continue
        if item.get("type") == "function_call_output":
            output = item.get("output")
            if isinstance(output, list):
                if item is latest_item:
                    item["output"] = [part for part in output if part not in latest_images]
                else:
                    item["output"] = [part for part in output if not (
                        isinstance(part, dict) and part.get("type") in {"input_image", "image_url"})]
        content = item.get("content")
        if item.get("role") == "user" and isinstance(content, list):
            has_promoted_screenshot = (
                any(isinstance(part, dict) and part.get("type") == "input_text"
                    and str(part.get("text", "")).startswith(screenshot_marker) for part in content)
                and any(isinstance(part, dict) and part.get("type") in {"input_image", "image_url"}
                        for part in content))
            if has_promoted_screenshot:
                continue
        pruned_history.append(item)

    reminder = (" Continue the original task: " + task_reminder) if task_reminder else ""
    pruned_history.append({"role": "user", "content": [
        {"type": "input_text", "text": screenshot_marker + reminder},
        *latest_images,
    ]})
    history[:] = pruned_history
    return True


def make_server(host: str, port: int, upstream: str, api_key: str,
                event_log: Path | None = None,
                promote_tool_image: bool = False,
                client_token: str | None = None,
                fallback_upstream: str | None = None,
                output_token_budget: int | None = None,
                size_aware_upload_timeout: bool = False,
                task_reminder: str = "") -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("the image relay must bind to loopback")
    url = urlparse(upstream.rstrip("/"))
    if url.scheme not in {"https", "http"} or not url.netloc:
        raise ValueError("invalid upstream Responses base URL")
    if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("unencrypted upstream must be loopback")
    upstreams = [("preferred", upstream.rstrip("/") + "/responses")]
    if fallback_upstream and fallback_upstream.rstrip("/") != upstream.rstrip("/"):
        upstreams.append(("fallback", fallback_upstream.rstrip("/") + "/responses"))
    for _, candidate in upstreams:
        parsed = urlparse(candidate)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("invalid fallback Responses base URL")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("unencrypted upstream must be loopback")
    if not client_token:
        raise ValueError("a run-scoped client token is required")
    if output_token_budget is not None and output_token_budget < 1:
        raise ValueError('output token budget must be positive')
    budget = {'output_tokens': 0, 'usage_unknown': False}
    budget_lock = threading.Lock()
    transport = make_upload_session() if size_aware_upload_timeout else None

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
            if self.path != "/v1/responses":
                self.send_error(404)
                return
            if not hmac.compare_digest(self.headers.get("Authorization", ""),
                                       f"Bearer {client_token}"):
                self.send_error(401)
                return
            started = time.monotonic()
            _upload_metrics.row = {}
            attempts = []
            response_started = False
            if output_token_budget is not None:
                budget_lock.acquire()
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 32 * 1024 * 1024:
                    self.send_error(413)
                    return
                raw = self.rfile.read(length)
                if output_token_budget is not None:
                    remaining = output_token_budget - budget['output_tokens']
                    if remaining <= 0 or budget['usage_unknown']:
                        if event_log:
                            with event_log.open('a') as log:
                                log.write(json.dumps({'time': time.time(), 'budget_stop': True,
                                    'output_tokens_used': budget['output_tokens'],
                                    'output_token_budget': output_token_budget,
                                    'usage_unknown': budget['usage_unknown']}) + '\n')
                        self.send_error(409, 'actor output token budget exhausted or usage unavailable')
                        return
                    body = json.loads(raw)
                    body['max_output_tokens'] = min(int(body.get('max_output_tokens') or remaining), remaining)
                    raw = json.dumps(body, separators=(',', ':')).encode()
                moved = False
                if promote_tool_image:
                    body = json.loads(raw)
                    moved = move_latest_tool_image(body, task_reminder)
                    if moved:
                        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
                request_meta = summarize_request(raw)
                upstream_response = None
                selected_upstream = None
                for index, (label, target) in enumerate(upstreams):
                    _upload_metrics.row = {}
                    try:
                        upstream_response = (transport or requests).post(target, headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "Accept": self.headers.get("Accept", "text/event-stream"),
                        }, data=raw, stream=True, timeout=(15, 300))
                        selected_upstream = label
                        attempts.append({"endpoint": label, "result": "response_received",
                                         "status": upstream_response.status_code})
                        break
                    except requests.exceptions.SSLError as exc:
                        attempts.append({"endpoint": label, "result": "tls_error",
                                         "error_type": type(exc).__name__})
                        if size_aware_upload_timeout and upload_observation().get('tls_connected_before_upload'):
                            # A failure after TLS may have sent request bytes.
                            # Never resend an unknown model request elsewhere.
                            attempts[-1]['fallback_suppressed_request_may_have_been_sent'] = True
                            raise
                        if index + 1 >= len(upstreams):
                            raise
                if upstream_response is None:
                    raise RuntimeError("no upstream endpoint returned a response")
                with upstream_response:
                    self.send_response(upstream_response.status_code)
                    self.send_header("Content-Type", upstream_response.headers.get(
                        "Content-Type", "text/event-stream"))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    response_started = True
                    pending = b''
                    usage = None
                    for chunk in upstream_response.iter_content(chunk_size=8192):
                        if chunk:
                            pending += chunk
                            while b'\n' in pending:
                                line, pending = pending.split(b'\n', 1)
                                if line.startswith(b'data:'):
                                    try:
                                        event = json.loads(line[5:].strip())
                                        response = event.get('response')
                                        candidate = response.get('usage') if isinstance(response, dict) else None
                                        if not isinstance(candidate, dict):
                                            candidate = event.get('usage')
                                        if isinstance(candidate, dict):
                                            usage = candidate
                                    except (ValueError, TypeError):
                                        pass
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    if usage is None and pending:
                        try:
                            final_line = pending.strip()
                            if final_line.startswith(b'data:'):
                                final_line = final_line[5:].strip()
                            final_event = json.loads(final_line)
                            final_response = final_event.get('response')
                            candidate = (final_response.get('usage')
                                         if isinstance(final_response, dict) else None)
                            usage = (candidate if isinstance(candidate, dict)
                                     else final_event.get('usage'))
                        except (ValueError, TypeError):
                            pass
                    if output_token_budget is not None:
                        if isinstance(usage, dict) and isinstance(usage.get('output_tokens'), int):
                            budget['output_tokens'] += usage['output_tokens']
                        else:
                            budget['usage_unknown'] = True
                    self.close_connection = True
                    status = upstream_response.status_code
                if event_log is not None:
                    with event_log.open("a", encoding="utf-8") as log:
                        log.write(json.dumps({"time": time.time(), **request_meta, "image_moved": moved,
                                              "request_bytes": len(raw), "upstream_status": status,
                                              "selected_endpoint": selected_upstream,
                                              "endpoint_attempts": attempts,
                                              "usage": usage,
                                              "upload": upload_observation() if size_aware_upload_timeout else None,
                                              "output_tokens_used": budget['output_tokens'] if output_token_budget else None,
                                              "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")
            except Exception as exc:
                # Retain transport phase evidence without logging request
                # bodies, headers, credentials, or exception string values.
                exception_chain = []
                pending_errors = [exc]
                seen_errors = set()
                while pending_errors and len(exception_chain) < 12:
                    error = pending_errors.pop(0)
                    if id(error) in seen_errors:
                        continue
                    seen_errors.add(id(error))
                    description = str(error).lower()
                    phase_hint = ('tls_handshake' if 'handshake operation timed out' in description
                                  else 'request_write' if 'write operation timed out' in description
                                  else None)
                    exception_chain.append({"type": type(error).__name__,
                                            "errno": getattr(error, "errno", None),
                                            "timeout_phase_hint": phase_hint})
                    for nested in (getattr(error, "__cause__", None),
                                   getattr(error, "__context__", None),
                                   getattr(error, "reason", None), *error.args):
                        if isinstance(nested, BaseException):
                            pending_errors.append(nested)
                if output_token_budget is not None:
                    budget['usage_unknown'] = True
                if event_log is not None:
                    with event_log.open("a", encoding="utf-8") as log:
                        log.write(json.dumps({"time": time.time(),
                                              **(request_meta if "request_meta" in locals() else {}),
                                              "endpoint_attempts": attempts,
                                              "response_started": response_started,
                                              "request_bytes": len(raw) if 'raw' in locals() else None,
                                              "upload": upload_observation() if size_aware_upload_timeout else None,
                                              "error_type": type(exc).__name__,
                                              "exception_chain": exception_chain,
                                              "elapsed_s": round(time.monotonic() - started, 3)}) + "\n")
                self.close_connection = True
                if not response_started:
                    try:
                        self.send_error(502, "Responses relay upstream error")
                    except OSError:
                        pass
            finally:
                if output_token_budget is not None:
                    budget_lock.release()

    class RelayServer(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            if transport is not None:
                transport.close()

    return RelayServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, help="provider base URL ending in /v1")
    parser.add_argument("--fallback-upstream", help="one preflighted fallback base URL ending in /v1")
    parser.add_argument("--api-key-env", required=True)
    parser.add_argument("--client-token-env", required=True,
                        help="run-scoped local Bearer token; distinct from provider key")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--promote-tool-image", action="store_true",
                        help="diagnostic only: move the latest tool image into a user message")
    parser.add_argument("--task-reminder-env",
                        help="environment variable containing the actor's public task instruction")
    parser.add_argument('--output-token-budget', type=int, default=None)
    parser.add_argument('--size-aware-upload-timeout', action='store_true',
                        help='separate bounded request-body writes from the 15s TLS connect deadline')
    args = parser.parse_args()
    key = os.environ.get(args.api_key_env)
    if not key:
        parser.error(f"{args.api_key_env} is unset")
    client_token = os.environ.get(args.client_token_env)
    if not client_token:
        parser.error(f"{args.client_token_env} is unset")
    server = make_server(args.host, args.port, args.upstream, key, args.event_log,
                         promote_tool_image=args.promote_tool_image,
                         client_token=client_token,
                         fallback_upstream=args.fallback_upstream,
                         output_token_budget=args.output_token_budget,
                         size_aware_upload_timeout=args.size_aware_upload_timeout,
                         task_reminder=os.environ.get(args.task_reminder_env, "")
                         if args.task_reminder_env else "")
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
