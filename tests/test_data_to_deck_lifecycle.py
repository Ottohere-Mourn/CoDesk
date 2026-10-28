"""The handoff scheduler uses only public collaboration state."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from oscombo.collab.data_to_deck import live_pilot
from oscombo.harness.base import AgentResult
from oscombo.harness.external import CodexHarness


class Client:
    def __init__(self):
        self.peer_revision = 0
        self.own_revision = 0
        self.peer_messages = []

    def list_saved_artifacts(self):
        return {"A": {"revision": self.peer_revision},
                "B": {"revision": self.own_revision}}

    def read_messages(self):
        return list(self.peer_messages)


def test_public_handoff_requires_both_saved_revision_and_message():
    client = Client()
    assert not live_pilot._public_handoff_state(client, "A", "B")["ready"]
    client.peer_messages = [{"actor": "A", "message_id": "m1"}]
    assert not live_pilot._public_handoff_state(client, "A", "B")["ready"]
    client.peer_revision = 1
    assert live_pilot._public_handoff_state(client, "A", "B") == {
        "ready": True, "peer_revision": 1, "own_revision": 0,
        "peer_message_ids": ["m1"]}


def test_observed_message_ids_require_completed_read_result(tmp_path):
    log = tmp_path / "stdout.log"
    log.write_text("\n".join(json.dumps(x) for x in [
        {"type": "item.started", "item": {"server": "collaboration", "tool": "read_messages"}},
        {"type": "item.completed", "item": {"server": "collaboration", "tool": "read_messages",
                                            "result": {"structured_content": {"result": [
                                                {"message_id": "m1", "actor": "A"}]}}}},
    ]) + "\n")
    assert live_pilot._observed_peer_message_ids(log) == {"m1"}


def test_early_final_suspends_then_resumes_same_actor(tmp_path, monkeypatch):
    client = Client()
    instances = []

    class FakeHarness:
        def __init__(self, spec):
            self.harness_version = "fake"
            self.resumes = 0
            instances.append(self)

        def prepare(self, ctx):
            pass

        def run(self, ctx):
            return AgentResult(status="done")

        def resume_after_external_update(self, ctx, timeout):
            assert timeout > 0
            self.resumes += 1
            return AgentResult(status="done", trace=[{"step": 1}])

    class Guest:
        guest_key = "B"

    monkeypatch.setattr("oscombo.harness.external.CodexHarness", FakeHarness)
    monkeypatch.setattr(live_pilot, "CollaborationClient", lambda *args: client)
    monkeypatch.setenv("TEST_COLLAB_TOKEN", "run-scoped")
    release = threading.Timer(0.05, lambda: (setattr(client, "peer_revision", 1),
                                           setattr(client, "peer_messages", [
                                               {"actor": "A", "message_id": "m1"}])))
    release.start()
    try:
        result = live_pilot._run_model_actor(
            "B", Guest(), "task", tmp_path, "model", "http://127.0.0.1:1/v1",
            "unused", "python", "http://127.0.0.1:2", "TEST_COLLAB_TOKEN",
            max_steps=25, timeout=10, handoff_from="A")
    finally:
        release.join()
    events = [json.loads(s) for s in (tmp_path / "actor_lifecycle.jsonl").read_text().splitlines()]
    assert [e["event"] for e in events] == [
        "suspended_for_peer_handoff", "woken_by_peer_handoff"]
    assert instances[0].resumes == 1
    assert result["status"] == "done" and result["steps"] == 1


def test_arrived_but_unread_message_still_wakes_actor(tmp_path, monkeypatch):
    client = Client()
    client.peer_revision = 1
    client.peer_messages = [{"actor": "A", "message_id": "late"}]

    class FakeHarness:
        harness_version = "fake"

        def __init__(self, spec):
            pass

        def prepare(self, ctx):
            pass

        def run(self, ctx):
            return AgentResult(status="done")

        def resume_after_external_update(self, ctx, timeout):
            return AgentResult(status="done", trace=[{"step": 1}])

    class Guest:
        guest_key = "B"

    monkeypatch.setattr("oscombo.harness.external.CodexHarness", FakeHarness)
    monkeypatch.setattr(live_pilot, "CollaborationClient", lambda *args: client)
    monkeypatch.setenv("TEST_COLLAB_TOKEN", "run-scoped")
    live_pilot._run_model_actor(
        "B", Guest(), "task", tmp_path, "model", "http://127.0.0.1:1/v1",
        "unused", "python", "http://127.0.0.1:2", "TEST_COLLAB_TOKEN",
        max_steps=25, timeout=10, handoff_from="A")
    events = [json.loads(s) for s in (tmp_path / "actor_lifecycle.jsonl").read_text().splitlines()]
    assert [e["event"] for e in events] == [
        "suspended_for_peer_handoff", "woken_by_peer_handoff"]
    assert not events[0]["newest_peer_message_seen"]


def test_resume_command_keeps_actor_private_session(tmp_path):
    harness = CodexHarness({"model": "model", "options": {}})
    harness.dir = tmp_path
    harness.binary = "codex"
    harness.harness_version = "test"
    seen = {}

    def fake_run(ctx, command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return AgentResult(status="done")

    harness._run_command = fake_run
    result = harness.resume_after_external_update(object(), 37)
    assert seen["command"][:7] == [
        "codex", "exec", "resume", "--last", "--all", "--json", "--skip-git-repo-check"]
    assert seen["kwargs"] == {"timeout": 37, "append": True}
    assert result.extra["resumed_after_external_update"]
