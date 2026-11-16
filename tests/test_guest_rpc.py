from types import SimpleNamespace

import pytest
import requests

from experiments.guest_rpc import protect_guest_reads


def test_transient_status_read_retries_but_does_not_wrap_actions(monkeypatch, tmp_path):
    calls = []
    def read(path, timeout=20):
        calls.append(path)
        if len(calls) == 1:
            raise requests.ConnectionError("connection reset")
        return b'{"exit_code":0}'
    action = object()
    agent = SimpleNamespace(_file=read, _bash=action, session=requests.Session())
    monkeypatch.setattr("experiments.guest_rpc.time.sleep", lambda _: None)
    protect_guest_reads(agent, tmp_path)
    assert agent._file("/status.json") == b'{"exit_code":0}'
    assert calls == ["/status.json", "/status.json"] and agent._bash is action
    assert agent.session.headers["Connection"] == "close"


def test_missing_status_is_normal_but_repeated_disconnect_is_infrastructure(monkeypatch, tmp_path):
    agent = SimpleNamespace(_file=lambda path, timeout=20: None, session=requests.Session())
    protect_guest_reads(agent, tmp_path)
    assert agent._file("/not-yet-finished") is None
    def fail(path, timeout=20):
        raise requests.ConnectionError("offline")
    agent = SimpleNamespace(_file=fail, session=requests.Session())
    monkeypatch.setattr("experiments.guest_rpc.time.sleep", lambda _: None)
    protect_guest_reads(agent, tmp_path)
    with pytest.raises(RuntimeError, match="INFRA"):
        agent._file("/status.json")
