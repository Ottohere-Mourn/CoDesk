import copy
import hashlib
import json

import pytest
from PIL import Image

from experiments.professional_trajectories import action_commands, image_history
from experiments.summarize_professional_trajectories import summarize


def test_literal_typing_cannot_become_host_shell_or_xdotool_options():
    text = '--window 123 $(touch /tmp/should-not-exist)\n`id`'
    argv = action_commands({"type": "type", "text": text})[0]
    assert argv[-2:] == ["--", text]
    assert argv[0] == "xdotool"
    with pytest.raises(ValueError):
        action_commands({"type": "key", "keys": "--window 123"})


def test_invalid_action_batch_is_detectable_before_execution():
    for action in [{"type": "click", "x": 1280, "y": 10},
                   {"type": "drag", "x": 10, "y": 10, "x2": -1, "y2": 12},
                   {"type": "scroll", "x": 10, "y": 20, "amount": 200},
                   {"type": "shell", "command": "anything"}]:
        with pytest.raises(ValueError):
            action_commands(action)


def test_image_window_preserves_tool_pairs_and_original_history():
    history = [{"type": "reasoning", "encrypted_content": "opaque"}]
    for n in range(5):
        history.extend([
            {"type": "function_call", "call_id": str(n), "name": "desktop", "arguments": "{}"},
            {"type": "function_call_output", "call_id": str(n), "output": "OK"},
            {"role": "user", "content": [{"type": "input_image", "image_url": f"shots/{n}.png"}]},
        ])
    original = copy.deepcopy(history)
    reduced = image_history(history, 2)
    images = [p["image_url"] for item in reduced for p in item.get("content", []) if p["type"] == "input_image"]
    assert images == ["shots/3.png", "shots/4.png"]
    assert history == original
    assert [i for i in reduced if "call_id" in i] == [i for i in history if "call_id" in i]
    assert reduced[0] == history[0]


def test_modified_click_releases_keys_and_rejects_unknown_modifiers():
    commands = action_commands({"type": "click", "x": 10, "y": 20, "modifiers": ["ctrl", "shift"]})
    assert commands[1] == ["xdotool", "keydown", "ctrl", "shift"]
    assert commands[-1] == ["xdotool", "keyup", "ctrl", "shift"]
    with pytest.raises(ValueError):
        action_commands({"type": "click", "x": 10, "y": 20, "modifiers": ["--window"]})


def test_report_detects_action_not_requested_by_model(tmp_path):
    trial = tmp_path / "p1a"
    (trial / "screenshots").mkdir(parents=True)
    (trial / "responses").mkdir()
    for n in range(2):
        Image.new("RGB", (8, 8), "white").save(trial / f"screenshots/{n:04d}.png")
    action = {"type": "key", "keys": "ctrl+s"}
    (trial / "result.json").write_text(json.dumps({"task": "p1a", "software": "Blender", "actions": 1,
        "model_responses": 1, "score": 0.0, "status": "completed"}))
    event = {"step": 1, "turn": 1, "call_id": "call-1", "action": action,
             "status": "ok", "screenshot_after": "screenshots/0001.png"}
    (trial / "actions.jsonl").write_text(json.dumps(event) + "\n")
    response = {"output": [{"type": "function_call", "call_id": "call-1", "arguments": json.dumps({"actions": [action]})}]}
    (trial / "responses/001.json").write_text(json.dumps(response))
    assert summarize(tmp_path)["integrity_passed"]
    event["action"] = {"type": "key", "keys": "alt+F4"}
    (trial / "actions.jsonl").write_text(json.dumps(event) + "\n")
    report = summarize(tmp_path)
    assert not report["integrity_passed"]
    assert "not grounded" in report["integrity_errors"][0]
    event["action"] = action
    (trial / "actions.jsonl").write_text(json.dumps(event) + "\n")
    (trial / "screenshots/0001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assert "Missing/invalid screenshots" in summarize(tmp_path)["integrity_errors"][0]


def test_report_rejects_reordered_or_duplicated_actions(tmp_path):
    trial = tmp_path / "p1a"
    (trial / "screenshots").mkdir(parents=True)
    (trial / "responses").mkdir()
    for n in range(3):
        Image.new("RGB", (8, 8), "white").save(trial / f"screenshots/{n:04d}.png")
    (trial / "result.json").write_text(json.dumps({"task": "p1a", "software": "Blender", "actions": 2,
        "model_responses": 1, "score": 0.0, "status": "completed"}))
    save, close = {"type": "key", "keys": "ctrl+s"}, {"type": "key", "keys": "alt+F4"}
    (trial / "responses/001.json").write_text(json.dumps({"output": [{"type": "function_call",
        "call_id": "call-1", "arguments": json.dumps({"actions": [save, close]})}]}))
    for sequence, valid in [([save, close], True), ([close, save], False), ([save, save], False)]:
        events = [{"step": n, "turn": 1, "call_id": "call-1", "action": action,
                   "status": "ok", "screenshot_after": f"screenshots/{n:04d}.png"}
                  for n, action in enumerate(sequence, 1)]
        (trial / "actions.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        assert summarize(tmp_path)["integrity_passed"] is valid


def test_report_checks_source_inputs_and_collector_manifest(tmp_path):
    root, dataset = tmp_path / "run", tmp_path / "source"
    trial = root / "p1a"
    (trial / "screenshots").mkdir(parents=True)
    (trial / "responses").mkdir()
    Image.new("RGB", (8, 8), "white").save(trial / "screenshots/0000.png")
    inputs = dataset / "dataset/pairs/p1/inputs"
    inputs.mkdir(parents=True)
    (inputs / "model.blend").write_bytes(b"original")
    (trial / "result.json").write_text(json.dumps({"task": "p1a", "software": "Blender", "actions": 0,
        "model_responses": 0, "score": 0.0, "status": "error",
        "input_hashes": {"model.blend": hashlib.sha256(b"original").hexdigest()}}))
    (root / "collector.py").write_bytes(b"collector")
    (root / "manifest.json").write_text(json.dumps({"tasks": ["p1a"],
        "runner_sha256": hashlib.sha256(b"collector").hexdigest()}))
    report = summarize(root, dataset)
    assert report["integrity_passed"] and report["input_hashes_checked"]
    (inputs / "model.blend").write_bytes(b"changed")
    (root / "collector.py").write_bytes(b"changed")
    errors = summarize(root, dataset)["integrity_errors"]
    assert any("Input hashes" in error for error in errors)
    assert any("Collector hash" in error for error in errors)
