import json
import threading
import time
from types import SimpleNamespace

from PIL import Image
import pytest

from experiments import professional_shared as shared
from experiments import professional_trajectories as collector


def test_overlap_counts_distinct_agents_not_nested_requests():
    assert shared.overlap_seconds([("a", 0, 3), ("a", 1, 4)]) == 0
    assert shared.overlap_seconds([("a", 0, 3), ("b", 1, 4), ("b", 2, 5)]) == 2
    assert shared.overlap_seconds([("a", 0, 1), ("b", 1, 2)]) == 0


def test_timeline_tracks_foreign_input_without_own_input_false_positives(tmp_path):
    timeline = shared.Timeline(tmp_path)
    observation = timeline.observation_start("p3a")
    timeline.observation_end("p3a", observation, "p3a/screenshots/0000.png", "QGIS")
    timeline.record("p3a", "model_request", {"turn": 1})
    own = {"action": {"type": "key", "keys": "ctrl+s"}}
    timeline.record("p3a", "action_start", own)
    timeline.record("p3a", "input_end", own)
    assert own["foreign_mutations_since_observation"] == 0
    observation = timeline.observation_start("p3b")
    timeline.observation_end("p3b", observation, "p3b/screenshots/0000.png", "QGIS")
    timeline.record("p3b", "model_request", {"turn": 1})
    foreign = {"action": {"type": "key", "keys": "Escape"}}
    timeline.record("p3b", "action_start", foreign)
    following = {"action": {"type": "key", "keys": "Return"}}
    timeline.record("p3a", "action_start", following)
    assert following["foreign_mutations_since_observation"] == 1
    assert following["foreign_input_inflight"]
    assert following["model_observation"] == "p3a/screenshots/0000.png"


@pytest.mark.parametrize("mode", ["parallel", "sequential"])
def test_shared_agents_use_one_desktop_and_evaluate_only_after_both_stop(tmp_path, monkeypatch, mode):
    dataset, output = tmp_path / "dataset", tmp_path / mode
    source = dataset / "dataset/pairs/p3"
    (source / "inputs").mkdir(parents=True)
    (source / "inputs/HarborDrainage.qgz").write_bytes(b"initial-project")
    (source / "task_a.md").write_text("ONLY_A_RISK_TASK")
    (source / "task_b.md").write_text("ONLY_B_LAYOUT_TASK")
    model_barrier = threading.Barrier(2) if mode == "parallel" else None
    input_barrier = threading.Barrier(2) if mode == "parallel" else None
    instances, evaluations, instructions = [], [], {}

    class FakeDesktop:
        def __init__(self, root, pair, image):
            self.root, self.name, self.stopped = root, "one-shared-container", False
            self.started = False
            self.calls = []
            instances.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def focus(self):
            return "QGIS shared project"

        def raw(self, argv, **kwargs):
            assert self.started and not self.stopped
            if input_barrier:
                input_barrier.wait(timeout=5)
            threading.Event().wait(.02)
            self.calls.append(argv)
            (self.root / "workspace" / (threading.current_thread().name + ".txt")).write_text("saved")
            return SimpleNamespace(stdout=b"")

    def screenshot(adapter, path):
        observation = adapter.timeline.observation_start(adapter.task)
        Image.new("RGB", (8, 8), "white").save(path)
        adapter.timeline.observation_end(adapter.task, observation,
            str(path.relative_to(output)), adapter.focus())

    def call_model(config, payload, root, turn, deadline):
        started = time.time()
        if model_barrier:
            model_barrier.wait(timeout=5)
        threading.Event().wait(.02)
        instructions[root.name] = payload["input"][0]["content"][0]["text"]
        if turn == 1:
            arguments = {"actions": [{"type": "key", "keys": "ctrl+s"}]}
            name = "desktop"
        else:
            arguments, name = {"summary": "Saved", "complete": True}, "finish"
        response = {"output": [{"type": "function_call", "name": name,
            "call_id": root.name + str(turn), "arguments": json.dumps(arguments)}]}
        collector.save(root / "responses" / f"{turn:03d}.json", response)
        collector.append(root / "requests.jsonl", {"ok": True, "started_at": started,
            "latency_s": time.time() - started, "turn": turn})
        return response

    def evaluate(root, pair, source_dataset, image):
        assert instances[0].stopped
        assert len(instances[0].calls) == 2
        stopped = [json.loads(line) for line in (output / "timeline.jsonl").read_text().splitlines()
                   if json.loads(line)["event"] == "agent_stopped"]
        assert {event["task"] for event in stopped} == {"p3a", "p3b"}
        evaluations.append(root)
        return {side: {"score": 1.0, "checks": {"saved": {"passed": True}}} for side in "ab"}

    monkeypatch.setattr(collector, "Desktop", FakeDesktop)
    monkeypatch.setattr(collector, "command", lambda *args, **kwargs: SimpleNamespace(stdout="test-image"))
    monkeypatch.setattr(collector, "call_model", call_model)
    monkeypatch.setattr(collector, "evaluate", evaluate)
    monkeypatch.setattr(shared.AgentDesktop, "screenshot", screenshot)
    args = SimpleNamespace(dataset=dataset, out=output, pair="p3", mode=mode, image="image", access="gui",
                           max_actions=10, max_turns=3, timeout=30)
    assert shared.run(args, {"model": "test-model"}) == 0
    assert len(instances) == len(evaluations) == 1
    assert instructions == {"p3a": "ONLY_A_RISK_TASK", "p3b": "ONLY_B_LAYOUT_TASK"}
    results = json.loads((output / "summary.json").read_text())
    assert results[0]["output_hashes"] == results[1]["output_hashes"]
    assert all(not result["pending_shared_evaluation"] for result in results)
    assert all(result["frozen_at"] >= result["finished_at"] for result in results)
    metrics = json.loads((output / "concurrency.json").read_text())
    assert metrics["shared_container"] and metrics["timeline_sequence_contiguous"]
    assert metrics["parallel_activity_observed"] is (mode == "parallel")
    assert (metrics["input_dispatch_overlap_s"] > 0) is (mode == "parallel")
    assert metrics["unmatched_action_starts"] == 0
    assert not metrics["integrity_errors"]
    assert json.loads((output / "trajectory-summary.json").read_text())["integrity_passed"]
    if mode == "sequential":
        assert metrics["potentially_stale_actions"] == 0
    records = [json.loads(line) for line in (output / "timeline.jsonl").read_text().splitlines()]
    damaged = [record for record in records if record["event"] != "input_end"]
    assert any("lack start" in error for error in shared.verify_timeline(output, damaged, results))
    complete = next(record for record in records if record["event"] == "action_end")
    complete["action"] = {"type": "key", "keys": "alt+F4"}
    assert any("identity changed" in error for error in shared.verify_timeline(output, records, results))


def test_concurrent_screenshots_use_private_temporary_files(tmp_path):
    timeline = shared.Timeline(tmp_path)
    scripts = []

    class Desktop:
        name = "shared"

        def raw(self, argv, **kwargs):
            scripts.append(argv[-1])
            return SimpleNamespace(stdout=b"png-placeholder")

        def focus(self):
            return "QGIS"

    adapter = shared.AgentDesktop(Desktop(), "p3a", timeline)
    adapter.screenshot(tmp_path / "screen.png")
    assert "TemporaryDirectory" in scripts[0]
    assert "/tmp/trajectory.png" not in scripts[0]
