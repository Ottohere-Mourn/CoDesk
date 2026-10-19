import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from oscombo import analyze, cli
from oscombo.harness import AgentContext, make_harness
from oscombo.policies import make_policy, resolve
from oscombo.policies.base import normalize_action
from oscombo.policies.transports import ChatCompletionsTransport, ResponsesTransport, chat_to_responses_input


def test_normalize_action():
    assert normalize_action("DONE") == "DONE"
    assert normalize_action({"action_type": "FAIL"}) == "FAIL"
    assert normalize_action({"action_type": "click", "action": "pyautogui.click(1, 2)"}) == "pyautogui.click(1, 2)"
    assert normalize_action({"command": "pyautogui.press('a')"}) == "pyautogui.press('a')"
    with pytest.raises(ValueError):
        normalize_action({"action_type": "click"})


def test_policy_registry():
    assert resolve("scripted").__module__ == "oscombo.policies.scripted"
    assert resolve("oscombo.policies.scripted:make") is resolve("scripted")
    with pytest.raises(ValueError):
        resolve("nope")
    p = make_policy(None, {"policy": "scripted", "options": {"actions": ["pyautogui.click(1, 1)"]}})
    assert p.predict("x", {})[1] == ["pyautogui.click(1, 1)"]
    assert p.predict("x", {})[1] == ["DONE"]


def test_responses_conversion():
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": [{"type": "text", "text": "hi"},
                                         {"type": "image_url", "image_url": {"url": "data:x", "detail": "high"}}]},
            {"role": "assistant", "content": "ok"}]
    out = chat_to_responses_input(msgs)
    assert out[1]["content"][1] == {"type": "input_image", "image_url": "data:x", "detail": "high"}
    assert out[2]["content"][0]["type"] == "output_text"


class _Handler(BaseHTTPRequestHandler):
    hits: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.hits.append((self.path, body, self.headers.get("Authorization")))
        if len(_Handler.hits) == 1:  # first call rate-limited
            self.send_response(429)
            self.end_headers()
            return
        if self.path.endswith("/chat/completions"):
            payload = {"choices": [{"message": {"content": "pyautogui.click(1, 1)"}}]}
        else:
            payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "DONE"}]}]}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


@pytest.mark.parametrize("cls,expected", [(ChatCompletionsTransport, "pyautogui.click(1, 1)"),
                                          (ResponsesTransport, "DONE")])
def test_transport_retries_rate_limit(monkeypatch, cls, expected):
    monkeypatch.setattr("oscombo.policies.transports.time.sleep", lambda s: None)
    _Handler.hits = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        t = cls("m", f"http://127.0.0.1:{server.server_port}/v1", "k")
        assert t({"messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}) == expected
        assert len(_Handler.hits) == 2 and _Handler.hits[1][2] == "Bearer k"
        assert _Handler.hits[1][1]["model"] == "m"
    finally:
        server.shutdown()


class _FakeGuest:
    url = "http://localhost:5999"


def test_command_harness(tmp_path):
    script = ("import json, os\n"
              "log = os.environ['OSCOMBO_ACTION_LOG']\n"
              "open(log, 'a').write(json.dumps({'t': 0, 'tool': 'type_text', 'text': 'hi', "
              "'window_before': 'Calc'}) + '\\n')\n"
              "assert open(os.environ['OSCOMBO_INSTRUCTION_FILE']).read() == 'do it'\n")
    spec = {"harness": "command", "options": {"command": [sys.executable, "-c", script]}}
    ctx = AgentContext(name="agentA", task_id="t", instruction="do it", guest=_FakeGuest(), out=tmp_path,
                       max_steps=5, spec=spec)
    h = make_harness(spec)
    h.prepare(ctx)
    res = h.run(ctx)
    assert res.status == "done", (tmp_path / "agentA/stderr.log").read_text()
    assert res.steps == 1
    assert res.trace[0]["actions"][0] == {"t": 0.0, "window_before": "Calc", "code": "type_text(text='hi')"}


def test_command_harness_infeasible(tmp_path):
    spec = {"harness": "command", "options": {"command": "touch {agent_dir}/INFEASIBLE"}}
    ctx = AgentContext(name="agentA", task_id="t", instruction="x", guest=_FakeGuest(), out=tmp_path,
                       max_steps=5, spec=spec)
    h = make_harness(spec)
    h.prepare(ctx)
    assert h.run(ctx).status == "fail"


def test_codex_config(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    spec = {"harness": "codex", "model": "m", "options": {"base_url": "http://gateway/v1"}}
    ctx = AgentContext(name="agentB", task_id="t", instruction="x", guest=_FakeGuest(), out=tmp_path,
                       max_steps=7, spec=spec)
    make_harness(spec).prepare(ctx)
    toml = (tmp_path / "agentB/codex_home/config.toml").read_text()
    assert 'base_url = "http://gateway/v1"' in toml and "requires_openai_auth = false" in toml
    assert 'OSCOMBO_GUEST_URL = "http://localhost:5999"' in toml and 'OSCOMBO_MAX_STEPS = "7"' in toml


def _write_run(root, name, mode, tasks, scores, agents, trace=()):
    d = root / name
    d.mkdir()
    (d / "result.json").write_text(json.dumps({"mode": mode, "tasks": tasks, "task_ids": [t.split("/")[1] for t in tasks],
                                               "scores": scores, "agents": agents}))
    (d / "trace.jsonl").write_text("".join(json.dumps(r) + "\n" for r in trace))


def test_analyze(tmp_path, capsys):
    ok = {"status": "done", "steps": 3, "error": None}
    _write_run(tmp_path, "e-solo-a", "solo", ["chrome/a"], {"a": 1.0}, {"agentA": ok})
    _write_run(tmp_path, "e-par-ab", "parallel", ["chrome/a", "libreoffice_calc/b"], {"a": 1.0, "b": 0.0},
               {"agentA": ok, "agentB": ok},
               trace=[{"agent": "agentA", "step": 1, "actions": [
                   {"code": "pyautogui.typewrite('x')", "window_before": "x.xlsx - LibreOffice Calc"},
                   {"code": "pyautogui.click(1, 1)", "window_before": "x.xlsx - LibreOffice Calc"}]}])
    _write_run(tmp_path, "e-par-infra", "parallel", ["chrome/a", "libreoffice_calc/b"], {"a": None, "b": None},
               {"agentA": {**ok, "error": "InfraError: INFRA: no Guest screenshot"}})
    rows, excluded = analyze.load(str(tmp_path), ["e-"])
    assert excluded == ["e-par-infra"]
    stats = analyze.analyze(rows, 0.95, {})
    assert stats["per"][("chrome/a", "parallel-1")] == [1, 1]
    assert stats["per"][("libreoffice_calc/b", "parallel-2")] == [0, 1]
    assert stats["interf"]["parallel"] == [1, 1]  # one keystroke, typed into the other task's Calc window
    analyze.report(stats)
    assert "parallel" in capsys.readouterr().out


def test_matrix(tmp_path):
    lines = cli.matrix([["ab", "chrome/a", "calc/b"]], "e1", ["parallel:2", "sequential:1", "isolated:1"], 1)
    assert "e1-ab-par-o2-r2 parallel calc/b chrome/a" in lines
    assert sum(" isolated " in x for x in lines) == 1
    assert [x for x in lines if " solo " in x] == ["e1-solo-chrome_a-r1 solo chrome/a", "e1-solo-calc_b-r1 solo calc/b"]
    assert len(lines) == 4 + 2 + 1 + 2
