"""Unit tests for the DeepSeek V4.1 8-task race-awareness harness & Responses bridge."""
from __future__ import annotations

import json
from experiments.deepseek_v41_eval import (
    EVAL_MATRIX_8,
    analyze_race_awareness,
    chat_completion_to_responses_sse,
    responses_req_to_chat_completions,
)


def test_eight_task_four_category_matrix():
    assert len(EVAL_MATRIX_8) == 8
    cats = {}
    for row in EVAL_MATRIX_8:
        cats[row["category"]] = cats.get(row["category"], 0) + 1
    assert len(cats) == 4 and all(v == 2 for v in cats.values())


def test_responses_to_chat_completions_and_sse_roundtrip():
    req = {
        "model": "deepseek-v4.1",
        "instructions": "You are an agent.",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "Check screen"}, {"type": "input_image", "image_url": "data:image/png;base64,AAAA"}]},
            {"type": "function_call", "call_id": "call_1", "name": "guest_bash", "arguments": '{"command":"ls"}'},
            {"type": "function_call_output", "call_id": "call_1", "output": "file.txt"},
        ],
        "tools": [{"type": "function", "name": "guest_bash", "description": "run", "parameters": {"type": "object"}}],
    }
    chat_req = responses_req_to_chat_completions(req, "deepseek-v4.1-upstream")
    assert chat_req["model"] == "deepseek-v4.1-upstream"
    assert chat_req["messages"][0]["role"] == "system"
    assert chat_req["messages"][2]["tool_calls"][0]["id"] == "call_1"
    assert chat_req["messages"][3]["role"] == "tool"

    sse = chat_completion_to_responses_sse({
        "id": "chatcmpl-1",
        "choices": [{"message": {"content": "Checking", "tool_calls": [{"id": "c2", "function": {"name": "guest_bash", "arguments": "{}"}}]}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }, "deepseek-v4.1").decode()
    assert "response.created" in sse
    assert "response.completed" in sse
    assert '"name": "guest_bash"' in sse


def test_race_awareness_analyzer_detects_spontaneous_locking(tmp_path):
    a_dir = tmp_path / "actor_A"
    b_dir = tmp_path / "actor_B"
    a_dir.mkdir(); b_dir.mkdir()
    (a_dir / "actions.jsonl").write_text(json.dumps({"tool": "guest_bash.guest_bash", "args": {"command": "echo A > /tmp/GUI_OWNER"}}) + "\n")
    (a_dir / "stdout.log").write_text('{"type":"agent_message","text":"Detected concurrent tab switch by another agent."}\n')
    (b_dir / "actions.jsonl").write_text(json.dumps({"tool": "guest_bash.guest_bash", "args": {"command": "ls /workspace"}}) + "\n")
    res = analyze_race_awareness(tmp_path, ("A", "B"))
    assert res["autonomous_race_aware"] is True
    assert res["spontaneous_ipc_or_locking"] is True
    assert res["explicit_contention_verbalized"] is True
