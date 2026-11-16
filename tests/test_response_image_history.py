import copy
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest

from experiments import professional_native as native
from experiments.professional_native_batch import validate_preflight
from experiments.professional_codex_entry import permissions
from experiments.professional_trajectories import save
from experiments.responses_relay import ImageHistoryError, ResponsesRelay, image_history_policy, prepare_image_history


def image(number):
    return {"type": "input_image", "image_url": f"data:image/png;base64,shot-{number}", "detail": "original"}


def payload_with_images(count=51, output_type="custom_tool_call_output"):
    history = [{"role": "user", "content": [{"type": "input_text", "text": "Edit only your own objects"}]}]
    for number in range(count):
        history.extend([
            {"type": "reasoning", "encrypted_content": f"opaque-{number}", "summary": []},
            {"type": "custom_tool_call" if output_type == "custom_tool_call_output" else "function_call",
                "call_id": f"call-{number}", "name": "desktop", "input": "unchanged command"},
            {"type": output_type, "call_id": f"call-{number}", "id": f"result-{number}",
                "output": [{"type": "input_text", "text": f"action result {number}"}, image(number)]},
        ])
    return {"model": "test-model", "input": history, "stream": False, "store": False,
        "instructions": "Keep the current task", "reasoning": {"effort": "high"}}


@pytest.mark.parametrize("output_type", ["custom_tool_call_output", "function_call_output"])
def test_51_image_history_keeps_recent_four_without_mutating_native_history(output_type):
    payload = payload_with_images(output_type=output_type)
    original = copy.deepcopy(payload)
    forwarded, audit = prepare_image_history(payload)
    assert payload == original
    assert audit["original_images"] == 51 and audit["sent_images"] == 4 and audit["omitted_images"] == 47
    assert len(forwarded["input"]) == len(original["input"])
    assert {key: value for key, value in forwarded.items() if key != "input"} == {
        key: value for key, value in original.items() if key != "input"}
    for previous, current in zip(original["input"], forwarded["input"]):
        if previous.get("type") != output_type:
            assert current == previous
        else:
            assert {key: value for key, value in current.items() if key != "output"} == {
                key: value for key, value in previous.items() if key != "output"}
            assert current["output"][0] == previous["output"][0]
    images = [part for item in forwarded["input"] for part in item.get("output", []) if part["type"] == "input_image"]
    assert images == [image(number) for number in range(47, 51)]
    assert forwarded["input"][3]["output"][1]["type"] == "input_text"
    assert "recorded trajectory" in forwarded["input"][3]["output"][1]["text"]


def test_repeated_full_histories_stay_bounded_past_provider_limit():
    for count in range(1, 101):
        payload = payload_with_images(count)
        forwarded, audit = prepare_image_history(payload)
        assert audit["sent_images"] == min(count, 4)
        assert forwarded["input"][-1] == payload["input"][-1]


def test_reference_images_are_pinned_and_not_confused_with_tool_schemas():
    payload = payload_with_images()
    payload["input"][0]["content"].append(image("reference"))
    payload["tools"] = [{"parameters": {"example": image("not-input")}}]
    forwarded, audit = prepare_image_history(payload)
    assert audit["pinned_images"] == 1 and audit["sent_images"] == 5
    assert forwarded["input"][0] == payload["input"][0]
    assert forwarded["tools"] == payload["tools"]


def test_keep_complete_latest_observation_even_if_it_has_more_than_four_images():
    payload = payload_with_images(10)
    payload["input"][-1]["output"].extend(image(f"current-{number}") for number in range(5))
    forwarded, audit = prepare_image_history(payload)
    assert audit["latest_tool_images"] == 6 and audit["sent_images"] == 6
    assert forwarded["input"][-1] == payload["input"][-1]


def test_references_reduce_available_tool_window_to_stay_under_hard_cap():
    payload = payload_with_images(10)
    payload["input"][0]["content"].extend(image(f"ref-{number}") for number in range(47))
    forwarded, audit = prepare_image_history(payload)
    assert audit["sent_images"] == 50 and audit["omitted_images"] == 7
    assert forwarded["input"][0] == payload["input"][0]
    assert forwarded["input"][-1] == payload["input"][-1]


def test_never_silently_discard_references_or_current_observation():
    payload = payload_with_images(1)
    payload["input"][0]["content"].extend(image(f"ref-{number}") for number in range(50))
    with pytest.raises(ImageHistoryError, match="refusing to discard"):
        prepare_image_history(payload)
    payload = payload_with_images(1)
    payload["input"][-1]["output"].extend(image(number) for number in range(50))
    with pytest.raises(ImageHistoryError, match="latest tool output"):
        prepare_image_history(payload)


@pytest.mark.parametrize("value", [0, -1, 51, True, 4.0, "4"])
def test_invalid_history_limits_are_rejected(value):
    with pytest.raises(ValueError):
        image_history_policy(value)


@pytest.mark.parametrize("key", ["previous_response_id", "conversation"])
def test_hidden_server_history_fails_closed(key):
    payload = payload_with_images()
    payload[key] = "server-state"
    with pytest.raises(ImageHistoryError, match="stateless"):
        prepare_image_history(payload)


def test_text_and_opaque_string_outputs_remain_unchanged():
    payload = {"input": "Hello"}
    assert prepare_image_history(payload)[0] == payload
    payload = {"input": [{"type": "function_call_output", "call_id": "text",
        "output": json.dumps(image("text-is-not-an-attachment"))}]}
    forwarded, audit = prepare_image_history(payload)
    assert forwarded == payload and audit["original_images"] == 0


class Trace:
    def __init__(self):
        self.requests, self.notes, self.responses = [], [], []

    def request(self, body, key, turn):
        self.requests.append(copy.deepcopy(body))
        return len(self.requests)

    def note(self, number, kind, **fields):
        self.notes.append({"number": number, "kind": kind, **fields})

    def response(self, number, ok, **fields):
        self.responses.append({"number": number, "ok": ok, **fields})


@contextmanager
def serving(server):
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.requests.append({"path": self.path, "raw": raw, "payload": json.loads(raw),
            "originator": self.headers.get("originator"), "session_id": self.headers.get("session_id")})
        status = self.server.statuses.pop(0) if self.server.statuses else 200
        if status != 200:
            body = json.dumps({"error": {"message": "retry later"}}).encode()
            content_type = "application/json"
        elif self.server.requests[-1]["payload"].get("stream"):
            body = self.server.sse
            content_type = "text/event-stream"
        else:
            body = b'{"status":"completed","output":[],"usage":{"total_tokens":1}}'
            content_type = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if status == 429:
            self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def relay_pair(tmp_path, limit=4, statuses=()):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream.requests, upstream.statuses = [], list(statuses)
    upstream.sse = b': ping\n\ndata: {"type":"response.completed","response":{"status":"completed","output":[],"usage":{"total_tokens":2}}}\n\n'
    trace = Trace()
    relay = ResponsesRelay(("127.0.0.1", 0), tmp_path, model="test-model", trace=trace,
        provider={"url": f"http://127.0.0.1:{upstream.server_port}/responses", "headers": {}}, image_history_limit=limit)
    with serving(upstream), serving(relay):
        yield upstream, relay, trace


def post(relay, payload, route="responses"):
    request = urllib.request.Request(relay.api_base + "/" + route, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "originator": "codex", "session_id": "session-a"})
    return urllib.request.urlopen(request, timeout=5)


@pytest.mark.parametrize("route", ["responses", "responses/compact"])
def test_real_http_relay_sends_bounded_images_and_archives_original(tmp_path, route):
    payload = payload_with_images()
    with relay_pair(tmp_path) as (upstream, relay, trace):
        with post(relay, payload, route) as response:
            assert response.status == 200
        sent = upstream.requests[0]
        assert sent["path"] == "/" + route
        assert sent["originator"] == "codex" and sent["session_id"] == "session-a"
        assert trace.requests == [payload]
        audit = next(note for note in trace.notes if note["kind"] == "image_history")
        assert audit["original_images"] == 51 and audit["sent_images"] == 4
        assert audit["upstream_sha256"] == hashlib.sha256(sent["raw"]).hexdigest()
        assert audit["upstream_bytes"] == len(sent["raw"])
        assert trace.responses[0]["ok"]


def test_sse_response_is_unchanged_after_request_pruning(tmp_path):
    payload = payload_with_images()
    payload["stream"] = True
    with relay_pair(tmp_path) as (upstream, relay, trace):
        with post(relay, payload) as response:
            assert response.read() == upstream.sse
        assert trace.responses[0]["usage"] == {"total_tokens": 2}


def test_retry_keeps_same_original_and_forwarded_request(tmp_path):
    payload = payload_with_images()
    with relay_pair(tmp_path, statuses=(429, 200)) as (upstream, relay, trace):
        with pytest.raises(urllib.error.HTTPError) as caught:
            post(relay, payload)
        assert caught.value.code == 429 and caught.value.headers["Retry-After"] == "1"
        caught.value.close()
        with post(relay, payload) as response:
            assert response.status == 200
        assert upstream.requests[0]["raw"] == upstream.requests[1]["raw"]
        assert trace.requests == [payload, payload]


def test_policy_rejection_is_recorded_without_upstream_call(tmp_path):
    payload = payload_with_images()
    payload["previous_response_id"] = "hidden-history"
    with relay_pair(tmp_path) as (upstream, relay, trace):
        with pytest.raises(urllib.error.HTTPError) as caught:
            post(relay, payload)
        assert caught.value.code == 400
        assert json.load(caught.value)["error"]["type"] == "image_history_policy_error"
        caught.value.close()
        assert not upstream.requests
        assert trace.requests == [payload]
        assert any(note["kind"] == "image_history_rejected" for note in trace.notes)
        assert trace.responses[0]["ok"] is False


def test_generic_relay_remains_passthrough_without_explicit_policy(tmp_path):
    payload = payload_with_images()
    with relay_pair(tmp_path, limit=None) as (upstream, relay, trace):
        with post(relay, payload) as response:
            assert response.status == 200
        assert upstream.requests[0]["payload"] == payload
        assert not any(note["kind"] == "image_history" for note in trace.notes)


def test_old_preflight_cannot_authorize_new_image_policy(tmp_path):
    save(tmp_path / "validation.json", {"passed": True})
    manifest = {"harness": "codex", "smoke": True, "interaction_mode": "gui-only",
        "codex_permissions": permissions("container-unrestricted")}
    save(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="image-history policy"):
        validate_preflight(tmp_path, "codex", "container-unrestricted", image_history_limit=4)
    manifest["image_history_policy"] = image_history_policy(4)
    save(tmp_path / "manifest.json", manifest)
    validate_preflight(tmp_path, "codex", "container-unrestricted", image_history_limit=4)
    with pytest.raises(ValueError, match="image-history policy"):
        validate_preflight(tmp_path, "codex", "container-unrestricted", image_history_limit=3)


@pytest.mark.parametrize("flags,limit", [([], 4), (["--image-history-limit", "7"], 7)])
def test_native_cli_passes_image_limit_to_run(monkeypatch, flags, limit):
    monkeypatch.setattr(native, "run", lambda args: args)
    args = native.main(["--dataset", "dataset", "--credentials", "private.json", "--out", "run",
        "--harness", "codex", "--freehand-runtime", "runtime", "--codex-binary", "codex", *flags])
    assert args.image_history_limit == limit


def test_native_request_summary_includes_image_counts_and_preserves_full_audit(tmp_path, monkeypatch):
    trace = Trace()
    monkeypatch.setitem(sys.modules, "freehand.harness.calltrace", SimpleNamespace(Trace=lambda root: trace))
    events = []
    session = SimpleNamespace(task="p3b", responses=0,
        timeline=SimpleNamespace(record=lambda *event: events.append(event)))
    recorder = native.NativeTrace(tmp_path, session)
    payload = payload_with_images()
    number = recorder.request(payload, "input", 0)
    forwarded, audit = prepare_image_history(payload)
    recorder.note(number, "image_history", **audit, upstream_sha256="audit-hash")
    recorder.response(number, True, status=200, latency_s=0.1, usage={"total_tokens": 1})
    summary = json.loads((tmp_path / "requests.jsonl").read_text())
    assert summary["image_history"] == {"original_images": 51, "sent_images": 4, "omitted_images": 47,
        "pinned_images": 0, "latest_tool_images": 1}
    assert trace.requests == [payload] and trace.requests != [forwarded]
    assert trace.notes[0]["upstream_sha256"] == "audit-hash"
    assert len(trace.notes[0]["omitted_paths"]) == 47
    assert session.responses == 1 and events[-1][1] == "model_response"
