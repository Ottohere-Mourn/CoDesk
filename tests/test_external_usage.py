import json

from oscombo.harness.external import codex_usage_from_stdout


def test_codex_usage_aggregates_completed_turns_only(tmp_path):
    path = tmp_path / "stdout.log"
    events = [
        {"type": "thread.started", "thread_id": "x"},
        {"type": "turn.completed", "usage": {
            "input_tokens": 100, "cached_input_tokens": 40, "cache_write_input_tokens": 2,
            "output_tokens": 10, "reasoning_output_tokens": 3}},
        {"type": "item.completed", "item": {"type": "mcp_tool_call", "result": {"usage": {"input_tokens": 999}}}},
        {"type": "turn.completed", "usage": {
            "input_tokens": 80, "cached_input_tokens": 25, "cache_write_input_tokens": 0,
            "output_tokens": 8, "reasoning_output_tokens": 2}},
    ]
    path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    result = codex_usage_from_stdout(path)
    assert result == {
        "available": True, "usage_event_count": 2,
        "input_tokens": 180, "cached_input_tokens": 65,
        "cache_write_input_tokens": 2, "output_tokens": 18,
        "reasoning_output_tokens": 5, "uncached_input_tokens": 115,
    }


def test_codex_usage_missing_stdout_is_explicit(tmp_path):
    result = codex_usage_from_stdout(tmp_path / "not-created.log")
    assert result["available"] is False
    assert result["usage_event_count"] == 0
    assert result["input_tokens"] == 0


from types import SimpleNamespace
from oscombo.harness.external import CodexHarness
from oscombo.human_agent_case_runner import _codex_no_tool_infra_failure


def _codex_config(tmp_path, required):
    spec = {"harness": "codex", "model": "gpt-6-sol", "effort": "low",
            "options": {"mcp_required": required}}
    harness = CodexHarness(spec)
    harness.opts = spec["options"]
    harness.action_log = tmp_path / "actions.jsonl"
    ctx = SimpleNamespace(guest=SimpleNamespace(url="http://127.0.0.1:9000"),
                          out=tmp_path, name="agent", max_steps=12,
                          action_lock_file=None, spec=spec)
    return harness.config(ctx)


def test_codex_desktop_mcp_can_be_required_without_changing_default(tmp_path):
    assert "required = true" not in _codex_config(tmp_path, False)
    required_config = _codex_config(tmp_path, True)
    assert "required = true" in required_config
    assert "OSCOMBO_GUEST_ID" in required_config


def test_zero_call_explicit_missing_tool_reply_is_infrastructure_invalid(tmp_path):
    stdout = tmp_path / "stdout.log"
    stdout.write_text("I can't complete this because the desktop screenshot and control tools aren?t available in this session.")
    result = {"status": "done", "steps": 0}
    assert _codex_no_tool_infra_failure("codex", True, result, 0, stdout)
    stdout.write_text("I cannot complete the task as requested.")
    assert not _codex_no_tool_infra_failure("codex", True, result, 0, stdout)
