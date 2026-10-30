"""Offline checks for the optional Codex-to-provider compatibility relay."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from oscombo.responses_tool_image_relay import make_server, move_latest_tool_image
from oscombo.harness.base import AgentContext
from oscombo.harness.external import CodexHarness


def test_move_latest_tool_image_prunes_superseded_screenshots_but_keeps_task_images():
    marker = "Current desktop screenshot from the preceding tool call."
    task_image = {"type": "input_image", "image_url": "data:image/png;base64,task"}
    task = {"role": "user", "content": [
        {"type": "input_text", "text": "Complete the whole workflow."}, task_image]}
    previous = {"type": "function_call_output", "output": [
        {"type": "input_text", "text": "Earlier tool result."},
        {"type": "input_image", "image_url": "data:image/png;base64,old"}]}
    prior_screenshot_turn = {"role": "user", "content": [
        {"type": "input_text", "text": marker},
        {"type": "input_image", "image_url": "data:image/png;base64,old"}]}
    latest = {"type": "function_call_output", "output": [
        {"type": "input_text", "text": "OK."},
        {"type": "input_image", "image_url": "data:image/png;base64,new"}]}
    body = {"input": [task, previous, prior_screenshot_turn, latest]}
    assert move_latest_tool_image(body)
    assert latest["output"] == [{"type": "input_text", "text": "OK."}]
    assert previous["output"] == [{"type": "input_text", "text": "Earlier tool result."}]
    assert prior_screenshot_turn not in body["input"]
    assert task in body["input"] and task_image in task["content"]
    assert body["input"][-1]["content"][-1]["image_url"].endswith("new")
    image_urls = [part.get("image_url") for item in body["input"]
                  for part in (item.get("output", []) if item.get("type") == "function_call_output"
                               else item.get("content", []) if isinstance(item.get("content"), list) else [])
                  if isinstance(part, dict) and part.get("type") == "input_image"]
    assert image_urls == ["data:image/png;base64,task", "data:image/png;base64,new"]


def test_default_relay_keeps_body_and_strips_codex_headers(tmp_path):
    captured = {}

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            captured["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            captured["headers"] = dict(self.headers)
            response = b'data: {"type":"response.completed"}\n\n'
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    relay = make_server("127.0.0.1", 0, f"http://127.0.0.1:{upstream.server_port}/v1",
                        "test-secret", tmp_path / "events.jsonl", client_token="run-token")
    threads = [threading.Thread(target=server.serve_forever, daemon=True)
               for server in (upstream, relay)]
    for thread in threads:
        thread.start()
    try:
        raw = b'{"model":"gpt-6.1-sol","input":[{"type":"function_call_output","output":[{"type":"input_image","image_url":"data:image/png;base64,abc"}]}],"stream":true}'
        unauthorized = requests.post(f"http://127.0.0.1:{relay.server_port}/v1/responses",
                                     data=raw, timeout=5)
        assert unauthorized.status_code == 401
        assert captured == {}
        result = requests.post(f"http://127.0.0.1:{relay.server_port}/v1/responses",
                               data=raw, headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer run-token",
                                                  "originator": "codex_cli_rs",
                                                  "x-codex-beta-features": "example"}, timeout=5)
        assert result.status_code == 200
        assert "response.completed" in result.text
        assert captured["body"] == raw
        assert captured["headers"]["Authorization"] == "Bearer test-secret"
        assert "originator" not in {name.lower() for name in captured["headers"]}
        assert "x-codex-beta-features" not in {name.lower() for name in captured["headers"]}
        log = (tmp_path / "events.jsonl").read_text()
        assert "test-secret" not in log and "data:image" not in log
        assert json.loads(log)["image_moved"] is False
    finally:
        for server in (relay, upstream):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


def test_relay_cannot_bind_non_loopback():
    with pytest.raises(ValueError, match="loopback"):
        make_server("0.0.0.0", 0, "https://example.com/v1", "secret", client_token="run-token")


@pytest.mark.parametrize("failure", ["tls_before_response", "http_error", "stream_error"])
def test_relay_fails_over_only_before_upstream_response(tmp_path, monkeypatch, failure):
    calls = []

    class Response:
        headers = {"Content-Type": "text/event-stream"}

        def __init__(self, status=200, stream_error=False):
            self.status_code = status
            self.stream_error = stream_error

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def iter_content(self, **_kwargs):
            yield b'data: {"type":"response.created"}\n\n'
            if self.stream_error:
                raise requests.exceptions.SSLError("synthetic stream failure")

    def upstream_post(url, **kwargs):
        calls.append((url, kwargs["data"]))
        if len(calls) == 1 and failure == "tls_before_response":
            raise requests.exceptions.SSLError("synthetic TLS setup failure")
        return Response(503 if failure == "http_error" else 200,
                        stream_error=failure == "stream_error")

    monkeypatch.setattr(requests, "post", upstream_post)
    events = tmp_path / "events.jsonl"
    relay = make_server("127.0.0.1", 0, "https://preferred.example/v1", "test-secret",
                        events, client_token="run-token",
                        fallback_upstream="https://fallback.example/v1")
    thread = threading.Thread(target=relay.serve_forever, daemon=True)
    thread.start()
    raw = b'{"model":"test-model","input":[],"stream":true}'
    try:
        # Session.post bypasses the patched top-level upstream transport.
        with requests.Session() as client:
            result = client.post(f"http://127.0.0.1:{relay.server_port}/v1/responses",
                                 data=raw, headers={"Authorization": "Bearer run-token"}, timeout=5)
        assert result.status_code == (503 if failure == "http_error" else 200)
        assert len(calls) == (2 if failure == "tls_before_response" else 1)
        assert all(body == raw for _, body in calls)
        row = json.loads(events.read_text())
        if failure == "tls_before_response":
            assert calls[1][0] == "https://fallback.example/v1/responses"
            assert row["selected_endpoint"] == "fallback"
        if failure == "stream_error":
            assert row["response_started"] is True
            assert b"502" not in result.content
        assert "test-secret" not in events.read_text()
    finally:
        relay.shutdown()
        relay.server_close()
        thread.join(timeout=5)


def test_codex_loopback_mode_does_not_inherit_provider_key(tmp_path, monkeypatch):
    class Guest:
        url = "http://127.0.0.1:5000"

    monkeypatch.setenv("CODESK_PROVIDER_TEST_KEY", "must-not-reach-agent")
    spec = {"harness": "codex", "model": "gpt-6.1-sol", "options": {
        "base_url": "http://127.0.0.1:8000/v1", "auth_mode": "none",
        "api_key_env": "CODESK_PROVIDER_TEST_KEY", "codex_bin": "true"}}
    ctx = AgentContext(name="A", task_id="t", instruction="x", guest=Guest(),
                       out=tmp_path, max_steps=2, spec=spec)
    harness = CodexHarness(spec)
    harness.prepare(ctx)
    assert harness.env(ctx).get("CODESK_PROVIDER_TEST_KEY") is None
    assert "requires_openai_auth = false" in (tmp_path / "A/codex_home/config.toml").read_text()

    monkeypatch.setenv("CODESK_RUN_RELAY_TOKEN", "ephemeral-run-token")
    relay_spec = {"harness": "codex", "model": "gpt-6.1-sol", "options": {
        "base_url": "http://127.0.0.1:8000/v1", "api_key_env": "CODESK_RUN_RELAY_TOKEN",
        "redact_env_keys": ["CODESK_PROVIDER_TEST_KEY"], "codex_bin": "true"}}
    relay_ctx = AgentContext(name="B", task_id="t", instruction="x", guest=Guest(),
                             out=tmp_path, max_steps=2, spec=relay_spec)
    relay_harness = CodexHarness(relay_spec)
    relay_harness.prepare(relay_ctx)
    relay_env = relay_harness.env(relay_ctx)
    assert relay_env.get("CODESK_PROVIDER_TEST_KEY") is None
    assert relay_env.get("CODESK_RUN_RELAY_TOKEN") == "ephemeral-run-token"

@pytest.mark.parametrize(("payload", "expected_tokens"), [
    (b'data: {"usage":{"output_tokens":7}}\n\n', 7),
    (b'data: {"response":{"usage":{"output_tokens":9}}}\n\n', 9),
])
def test_relay_accounts_top_level_or_response_usage(tmp_path, payload, expected_tokens):
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    events = tmp_path / "events.jsonl"
    relay = make_server("127.0.0.1", 0, f"http://127.0.0.1:{upstream.server_port}/v1", "secret", events, client_token="token", output_token_budget=100)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (upstream, relay)]
    for t in threads: t.start()
    try:
        r = requests.post(f"http://127.0.0.1:{relay.server_port}/v1/responses", data=b'{}', headers={"Authorization":"Bearer token"}, timeout=5)
        assert r.status_code == 200
        row = json.loads(events.read_text())
        assert row["usage"]["output_tokens"] == expected_tokens
        assert row["output_tokens_used"] == expected_tokens
    finally:
        relay.shutdown(); upstream.shutdown()
        relay.server_close(); upstream.server_close()
        for t in threads: t.join(timeout=5)


def test_relay_accounts_usage_in_final_unterminated_data_chunk(tmp_path):
    payload = b'data: {"response":{"usage":{"output_tokens":11}}}'
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    events = tmp_path / "events.jsonl"
    relay = make_server("127.0.0.1", 0, f"http://127.0.0.1:{upstream.server_port}/v1", "secret", events, client_token="token", output_token_budget=100)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (upstream, relay)]
    for t in threads: t.start()
    try:
        r = requests.post(f"http://127.0.0.1:{relay.server_port}/v1/responses", data=b'{}', headers={"Authorization":"Bearer token"}, timeout=5)
        assert r.status_code == 200
        row = json.loads(events.read_text()); assert row["usage"]["output_tokens"] == 11
        assert row["output_tokens_used"] == 11
    finally:
        relay.shutdown(); upstream.shutdown(); relay.server_close(); upstream.server_close()
        for t in threads: t.join(timeout=5)
