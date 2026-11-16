"""Host-side authenticated Responses relay preserving Codex's native SSE stream."""
from __future__ import annotations

import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class ImageHistoryError(ValueError):
    pass


def image_history_policy(keep=4, max_images=50):
    if type(keep) is not int or type(max_images) is not int or not 1 <= keep <= max_images:
        raise ValueError("Image history limit must be a positive integer no greater than the request image budget")
    return {"version": 1, "recent_tool_images": keep, "max_request_images": max_images,
        "pin_non_tool_images": True, "protect_latest_tool_output": True}


def prepare_image_history(payload, keep=4, max_images=50):
    """Window tool images without mutating native history, references or call/result pairs."""
    policy = image_history_policy(keep, max_images)
    if payload.get("previous_response_id") or payload.get("conversation"):
        raise ImageHistoryError("Image-history limiting requires full stateless input; server-side conversation history cannot be bounded")
    history = payload.get("input", [])
    if not isinstance(history, (list, str)):
        raise ImageHistoryError("Expected a list or string Responses input")

    def count_images(value):
        if isinstance(value, dict):
            return int(value.get("type") == "input_image") + sum(count_images(child) for child in value.values())
        if isinstance(value, list):
            return sum(count_images(child) for child in value)
        return 0

    original = count_images(history)
    tool_images = []
    for item_index, item in enumerate(history if isinstance(history, list) else []):
        if not isinstance(item, dict) or item.get("type") not in ("function_call_output", "custom_tool_call_output"):
            continue
        output = item.get("output")
        if isinstance(output, list):
            tool_images.extend((item_index, part_index) for part_index, part in enumerate(output)
                if isinstance(part, dict) and part.get("type") == "input_image")
    pinned = original - len(tool_images)
    latest = sum(item_index == tool_images[-1][0] for item_index, _ in tool_images) if tool_images else 0
    available = max_images - pinned
    if available < latest or available < 0:
        raise ImageHistoryError(f"Pinned input images ({pinned}) and the latest tool output ({latest}) exceed the request image budget ({max_images}); refusing to discard current observations or references")
    retain = min(available, max(keep, latest))
    removed = tool_images[:-retain] if retain else tool_images
    result = copy.deepcopy(payload) if removed else payload
    for item_index, part_index in removed:
        result["input"][item_index]["output"][part_index] = {"type": "input_text",
            "text": "[Earlier tool image omitted by the image-history policy; the original remains in the recorded trajectory.]"}
    audit = {"policy": policy, "original_images": original, "sent_images": original - len(removed),
        "omitted_images": len(removed), "pinned_images": pinned, "latest_tool_images": latest,
        "omitted_paths": [f"/input/{item}/output/{part}" for item, part in removed]}
    return result, audit


def relay_stream(response, write):
    """Forward bytes unchanged and retain the terminal response for usage records."""
    items, terminal = {}, None
    for line in response:
        write(line)
        if terminal is not None and not line.strip():
            break
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if not data or data == b"[DONE]":
            continue
        event = json.loads(data)
        kind = event.get("type")
        if kind == "response.output_item.done":
            items[event["output_index"]] = event["item"]
        elif kind in ("response.completed", "response.incomplete", "response.failed"):
            terminal = event["response"]
        elif kind == "error":
            terminal = {"status": "failed", "error": event.get("error", event)}
    if terminal is None:
        raise ValueError("Upstream stream ended without a terminal response")
    if not terminal.get("output") and items:
        terminal["output"] = [items[index] for index in sorted(items)]
    return terminal


class ResponsesRelay(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, trace_dir: Path, *, model: str, provider: dict,
                 upstream_timeout=300, trace=None, allowed_models=None, image_history_limit=None,
                 max_request_images=50):
        self.image_history_policy = (None if image_history_limit is None else
            image_history_policy(image_history_limit, max_request_images))
        if trace is None:
            from freehand.harness.calltrace import Trace
            trace = Trace(trace_dir)
        self.trace = trace
        self.lock = threading.Lock()
        self.model = model
        self.allowed_models = {model, *(allowed_models or [])}
        self.provider = provider
        self.upstream_timeout = upstream_timeout
        self.capability = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

    @property
    def api_base(self):
        return f"http://{self.server_address[0]}:{self.server_port}/{self.capability}/v1"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def route(self):
        path = urllib.parse.urlsplit(self.path).path
        prefix = f"/{self.server.capability}/v1/"
        if not secrets.compare_digest(path[:len(prefix)], prefix):
            return None
        return path[len(prefix):]

    def redact(self, value):
        text = json.dumps(value)
        for name, value in self.server.provider["headers"].items():
            if name.lower() == "authorization":
                text = text.replace(value, "[redacted]").replace(value.removeprefix("Bearer "), "[redacted]")
        return json.loads(text)

    def reply(self, status, value, retry_after=None):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if retry_after and "\n" not in retry_after and "\r" not in retry_after:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.route() != "models":
            return self.reply(404, {"error": "Unknown route"})
        # The explicitly selected model uses Codex's own bundled model metadata.
        return self.reply(200, {"object": "list", "data": [{"id": self.server.model,
            "object": "model", "owned_by": "configured-provider"}]})

    def do_POST(self):
        route = self.route()
        if route not in ("responses", "responses/compact"):
            return self.reply(404, {"error": "Unknown route"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 64 * 1024 * 1024:
                raise ValueError("Invalid request size")
            self.connection.settimeout(15)
            payload = json.loads(self.rfile.read(length))
            if payload.get("model") not in self.server.allowed_models:
                raise ValueError("This experiment is pinned to its configured model; requested " + str(payload.get("model")))
        except (ValueError, OSError) as error:
            return self.reply(400, {"error": {"message": str(error)}})
        provider = self.server.provider
        headers = dict(provider["headers"])
        for name, value in self.headers.items():
            if name.lower() in ("session_id", "originator", "version", "openai-beta") or name.lower().startswith("x-codex-"):
                headers[name] = value
        url = provider["url"] + ("/compact" if route.endswith("/compact") else "")
        with self.server.lock:
            number = self.server.trace.request(payload, "input", 0)
            self.server.trace.note(number, "route", route=route)
        started = time.monotonic()
        sent = False
        status, result = 502, {"error": {"message": "Upstream request failed"}}
        retry_after = None
        try:
            upstream_payload = payload
            if self.server.image_history_policy is not None:
                policy = self.server.image_history_policy
                upstream_payload, audit = prepare_image_history(payload,
                    policy["recent_tool_images"], policy["max_request_images"])
            body = json.dumps(upstream_payload).encode()
            if self.server.image_history_policy is not None:
                with self.server.lock:
                    self.server.trace.note(number, "image_history", **audit,
                        upstream_sha256=hashlib.sha256(body).hexdigest(), upstream_bytes=len(body))
            request = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(request, timeout=self.server.upstream_timeout) as response:
                status = response.status
                if payload.get("stream") and "text/event-stream" in response.headers.get("Content-Type", ""):
                    self.send_response(status)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    sent = True
                    def write(line):
                        self.wfile.write(line)
                        self.wfile.flush()
                    result = relay_stream(response, write)
                else:
                    result = json.load(response)
        except ImageHistoryError as error:
            status = 400
            result = {"error": {"message": str(error), "type": "image_history_policy_error"}}
            with self.server.lock:
                self.server.trace.note(number, "image_history_rejected", policy=self.server.image_history_policy,
                    reason=str(error))
        except urllib.error.HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After")
            try:
                result = self.redact(json.loads(error.read()))
            except ValueError:
                result = {"error": {"message": f"Upstream HTTP {status}"}}
        except (OSError, ValueError, TimeoutError) as error:
            status = 502
            result = {"error": {"message": "Upstream connection or stream failed", "type": type(error).__name__}}
        finally:
            ok = status == 200 and result.get("status") != "failed" and not result.get("error")
            with self.server.lock:
                self.server.trace.response(number, ok, status=status,
                    response_status=result.get("status"), output=result.get("output"),
                    usage=result.get("usage"), error=result.get("error"),
                    latency_s=round(time.monotonic() - started, 3))
        if not sent:
            self.reply(status, result, retry_after)
