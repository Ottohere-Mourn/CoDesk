from __future__ import annotations

import json
import base64
import struct
import threading
import time
import urllib.request

from oscombo.local_qwen_responses import (QwenResponsesAdapter, _input_messages,
    _retain_latest_image, _retain_recent_history, serve)


def test_local_qwen_decision_maps_to_responses_function_call():
    adapter = QwenResponsesAdapter(lambda _messages, _limit: {
        "text": '{"tool_call":{"name":"mcp__desktop__click","arguments":{"x":12,"y":34}}}'})
    response = adapter.respond({"model": "qwen-local", "tools": [{"type": "function",
        "name": "mcp__desktop__click", "parameters": {"type": "object"}}]}, "A")
    item = response["output"][0]
    assert response["status"] == "completed"
    assert item["type"] == "function_call"
    assert item["name"] == "mcp__desktop__click"
    assert json.loads(item["arguments"]) == {"x": 12, "y": 34}


def test_gateway_logs_raw_model_action_and_actual_input_image_dimensions(tmp_path):
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1280, 720)
    image_url = "data:image/png;base64," + base64.b64encode(png_header).decode()
    log = tmp_path / "events.jsonl"
    adapter = QwenResponsesAdapter(lambda _messages, _limit: {
        "text": '{"tool_call":{"name":"mcp__desktop__click","arguments":{"x":12,"y":34}}}'},
        log_path=log)
    adapter.respond({"input": [{"type": "message", "role": "user", "content": [
        {"type": "input_image", "image_url": image_url}]}],
        "tools": [{"type": "function", "name": "mcp__desktop__click", "parameters": {"type": "object"}}]}, "A")
    record = json.loads(log.read_text().splitlines()[0])
    assert record["raw_model_output"].endswith('"y":34}}}')
    assert record["parsed_arguments"] == {"x": 12, "y": 34}
    assert record["qwen_input_image_sizes"] == [[1280, 720]]


def test_unknown_tool_is_never_emitted_as_function_call():
    adapter = QwenResponsesAdapter(lambda _messages, _limit: {
        "text": '{"tool_call":{"name":"rm_everything","arguments":{}}}'})
    response = adapter.respond({"tools": [{"type": "function", "name": "screenshot"}]}, "B")
    assert response["output"][0]["type"] == "message"
    assert "rm_everything" in response["output"][0]["content"][0]["text"]


def test_repeated_qwen_json_actions_dispatch_only_first_complete_action():
    adapter = QwenResponsesAdapter(lambda _messages, _limit: {"text": (
        '{"tool_call":{"name":"mcp__desktop__click","arguments":{"x":10,"y":20}}}\n'
        '{"tool_call":{"name":"mcp__desktop__wait","arguments":{"seconds":5}}}')})
    response = adapter.respond({"tools": [
        {"type": "function", "name": "mcp__desktop__click", "parameters": {"type": "object"}},
        {"type": "function", "name": "mcp__desktop__wait", "parameters": {"type": "object"}},
    ]}, "A")
    item = response["output"][0]
    assert item["type"] == "function_call"
    assert item["name"] == "mcp__desktop__click"
    assert json.loads(item["arguments"]) == {"x": 10, "y": 20}


def test_codex_namespace_mcp_tools_are_flattened_for_model_then_restored_for_router():
    adapter = QwenResponsesAdapter(lambda messages, _limit: {
        "text": '{"tool_call":{"name":"mcp__desktop__screenshot","arguments":{}}}'})
    response = adapter.respond({"tools": [{"type": "namespace", "name": "mcp__desktop",
        "description": "Desktop control", "tools": [{"name": "screenshot",
            "description": "Take a screenshot", "parameters": {"type": "object", "properties": {}}}]}]}, "S")
    item = response["output"][0]
    assert item["type"] == "function_call"
    assert item["namespace"] == "mcp__desktop"
    assert item["name"] == "screenshot"
    assert json.loads(item["arguments"]) == {}


def test_codex_mcp_tool_output_preserves_text_and_screenshot_image_for_qwen():
    messages = _input_messages({"input": [
        {"type": "function_call", "namespace": "mcp__desktop", "name": "screenshot", "arguments": "{}"},
        {"type": "function_call_output", "name": "mcp__desktop__screenshot", "output": [
            {"type": "text", "text": "OK."},
            {"type": "image", "data": "cG5n", "mimeType": "image/png"},
        ]},
    ]})
    assert messages[0]["role"] == "assistant"
    assert json.loads(messages[0]["content"]) == {"tool_call": {
        "name": "mcp__desktop__screenshot", "arguments": {}}}
    assert messages[1]["role"] == "tool"
    assert messages[1]["content"][0]["text"] == "OK."
    assert messages[1]["content"][1]["image_url"]["url"] == "data:image/png;base64,cG5n"


def test_codex_normalized_input_image_in_function_output_is_not_dropped():
    messages = _input_messages({"input": [
        {"type": "function_call_output", "name": "mcp__desktop__screenshot", "output": [
            {"type": "input_text", "text": "OK."},
            {"type": "input_image", "image_url": "data:image/png;base64,cG5n"},
        ]},
    ]})
    assert messages[0]["content"][0]["text"] == "OK."
    assert messages[0]["content"][1] == {
        "type": "image_url", "image_url": {"url": "data:image/png;base64,cG5n"}}


def test_latest_screenshot_is_kept_while_action_and_text_history_remains():
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "task"},
                                         {"type": "image_url", "image_url": {"url": "data:image/png;base64,old"}}]},
        {"role": "assistant", "content": '{"tool_call":{"name":"click","arguments":{}}}'},
        {"role": "tool", "content": [{"type": "text", "text": "clicked"},
                                         {"type": "image_url", "image_url": {"url": "data:image/png;base64,new"}}]},
    ]
    result = _retain_latest_image(messages)
    assert result[0]["content"] == [{"type": "text", "text": "task"}]
    assert result[1]["content"].startswith('{"tool_call"')
    assert result[2]["content"][0]["text"] == "clicked"
    assert result[2]["content"][1]["image_url"]["url"] == "data:image/png;base64,new"


def test_recent_history_retains_system_and_initial_task_plus_bounded_recent_turns():
    messages = ([{"role": "system", "content": "system prompt"},
                {"role": "user", "content": "original task"}] +
               [{"role": "assistant", "content": f"action-{i}"} for i in range(20)])
    result = _retain_recent_history(messages, recent_messages=4)
    assert result[:2] == messages[:2]
    assert [m["content"] for m in result[2:]] == ["action-16", "action-17", "action-18", "action-19"]


def test_shared_qwen_runtime_serializes_inference_and_tokenizer_access():
    state_lock = threading.Lock()
    active = 0
    overlaps = []

    def guarded_use():
        nonlocal active
        with state_lock:
            if active:
                overlaps.append(True)
            active += 1
        time.sleep(0.01)
        with state_lock:
            active -= 1

    def infer(_messages, _limit):
        guarded_use()
        return {"text": '{"message":"done"}'}

    def count_tokens(text):
        guarded_use()
        return len(text)

    adapter = QwenResponsesAdapter(infer, count_tokens=count_tokens)
    body = {"input": [{"type": "message", "role": "user", "content": "inspect"}]}
    threads = [threading.Thread(target=adapter.respond, args=(body, actor)) for actor in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
    assert not any(thread.is_alive() for thread in threads)
    assert not overlaps


def test_responses_route_streams_and_actor_routes_are_isolated():
    seen = []
    adapter = QwenResponsesAdapter(lambda messages, _limit: (seen.append(messages) or {"text": "{\"message\":\"done\"}"}))
    server = serve(adapter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = {"model": "qwen-local", "stream": True, "instructions": "task prompt",
                "input": [{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "inspect"},
                    {"type": "input_image", "image_url": "data:image/png;base64,AA=="}]}], "tools": []}
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/actor/A/v1/responses",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode()
        assert "response.created" in raw and "response.completed" in raw and "[DONE]" in raw
        assert seen[0][0]["role"] == "system"
        assert seen[0][1]["content"][1]["type"] == "image_url"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
