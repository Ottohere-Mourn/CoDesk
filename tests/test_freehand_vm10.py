import json
from types import SimpleNamespace

from experiments.freehand_vm10 import FreehandHarness, outcome_status, read_trace
from oscombo.harness.base import AgentContext


def test_freehand_status_does_not_turn_timeout_or_error_into_done():
    assert outcome_status({"status": "completed"}, None) == "done"
    assert outcome_status({"status": "completed"}, "collection failed") == "error"
    assert outcome_status({"status": "time_budget_exhausted"}, None) == "timeout"
    assert outcome_status({"status": "stopped", "agent_status": "stopped_max_turns"}, None) == "max_steps"
    assert outcome_status({"status": "stopped", "agent_status": "stopped_no_tools"}, None) == "error"


def test_trace_separates_failed_api_calls_and_counts_real_responses(tmp_path):
    (tmp_path / "blobs.jsonl").write_text(json.dumps({"h": "call", "v": {
        "type": "function_call", "name": "finish", "arguments": '{"summary":"ok"}'}}) + "\n")
    events = [
        {"kind": "request", "n": 1},
        {"kind": "response", "n": 1, "ok": False, "status": 429},
        {"kind": "request", "n": 2},
        {"kind": "response", "n": 2, "ok": True, "ts": 15, "output": ["call"],
         "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}},
    ]
    (tmp_path / "requests.jsonl").write_text("\n".join(map(json.dumps, events)) + "\n")
    trace, metrics = read_trace(tmp_path, 10)
    assert len(trace) == 1 and trace[0]["done"] and trace[0]["t"] == 5
    assert trace[0]["actions"] == []
    assert metrics["model_requests"] == 2 and len(metrics["api_errors"]) == 1
    assert metrics["usage"]["total_tokens"] == 14
    assert read_trace(tmp_path / "missing", 0)[1]["usage"] is None


def test_two_freehand_agents_share_desktop_but_have_separate_histories(monkeypatch, tmp_path):
    class MiniAgent:
        def __init__(self, **kwargs):
            self.timeout_sec = kwargs["timeout_sec"]
            self.session = SimpleNamespace(headers={})

        def _file(self, path, timeout=20):
            return None

    monkeypatch.setattr("experiments.freehand_vm10.load_module", lambda *args: SimpleNamespace(
        FreehandOSWorldAgent=MiniAgent))
    desktop = SimpleNamespace(controller=object(), provider=object(), action_history=["original"])
    guest = SimpleNamespace(env=desktop)
    spec = {"model": "gpt-6-astra", "options": {"agent_path": "/unused/agent.py"}}
    harnesses = []
    for name in ("agentA", "agentB"):
        ctx = AgentContext(name=name, task_id=name, instruction=name, guest=guest,
                           out=tmp_path, max_steps=1000, spec=spec)
        harness = FreehandHarness(spec)
        harness.prepare(ctx)
        harnesses.append(harness)
    a, b = [h.agent for h in harnesses]
    assert a.env.controller is b.env.controller is desktop.controller
    a.env.action_history.append("DONE")
    assert b.env.action_history == [] and desktop.action_history == ["original"]
    assert a.result_dir != b.result_dir
