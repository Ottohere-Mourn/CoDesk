"""Tests for non-YOLO container Codex guard, Guest CLI confinement, MCP gate, and 19-case Sol 6.1 staging."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import threading
import time
import pytest

from experiments.codesk_19case_suite import PORTFOLIO_19, replace_model_literals
from experiments.codesk_container_codex import (
    container_permission_policy,
    non_yolo_policy,
    validate_container_config_text,
    validate_non_yolo_config_text,
)
from experiments.codesk_hybrid_v2_runtime import (
    DESKTOP_GATE_LOCK_HELPERS,
    GUEST_BASH_TOOLS_SOURCE,
    GUEST_CLI_TOOLS_SOURCE,
    verify_reconstructed_prompt_hashes,
)


def test_non_yolo_policy_forbids_yolo_and_danger_full_access():
    policy = non_yolo_policy()
    assert policy["vm_host_codex_launched"] is False
    assert policy["yolo_enabled"] is False
    assert policy["yolo_flag_used"] is False
    assert policy["yolo_equivalent"] is False
    assert policy["sandbox_mode"] == "read-only"
    assert policy["approval_policy"] == "on-request"

    valid_cfg = '''
model = "gpt-6.1-sol"
approval_policy = "on-request"
sandbox_mode = "read-only"

[features]
shell_tool = false
unified_exec = false
'''
    validate_non_yolo_config_text(valid_cfg)

    for bad_cfg in (
        valid_cfg.replace('"read-only"', '"danger-full-access"'),
        valid_cfg.replace('"on-request"', '"never"'),
        valid_cfg.replace("shell_tool = false", "shell_tool = true"),
    ):
        with pytest.raises(ValueError):
            validate_non_yolo_config_text(bad_cfg)

    unrestricted_policy = container_permission_policy("container-unrestricted")
    assert unrestricted_policy["scope"] == "docker-container-only"
    assert unrestricted_policy["vm_host_codex_launched"] is False
    assert unrestricted_policy["yolo_flag_used"] is False
    assert unrestricted_policy["yolo_enabled"] is False
    assert unrestricted_policy["yolo_equivalent"] is False
    assert unrestricted_policy["sandbox_mode"] == "workspace-write"
    assert unrestricted_policy["approval_policy"] == "never"
    assert unrestricted_policy["shell_tool"] is True

    full_cli_cfg = '''
model = "gpt-6.1-sol"
approval_policy = "never"
sandbox_mode = "workspace-write"

[features]
shell_tool = true
unified_exec = false
'''
    validate_container_config_text(full_cli_cfg, mode="container-unrestricted")
    ast.parse(GUEST_BASH_TOOLS_SOURCE)


def test_reconstructed_prompt_hashes_match_protocol_spec():
    verified = verify_reconstructed_prompt_hashes()
    assert len(verified) == 4


def test_guest_cli_rejects_disallowed_commands_and_path_traversal(tmp_path, monkeypatch):
    namespace: dict = {}
    exec(compile(GUEST_CLI_TOOLS_SOURCE, "guest_cli_tools.py", "exec"), namespace)
    run_guest_cli = namespace["run_guest_cli"]

    monkeypatch.setenv("OSCOMBO_CLI_ROOT", "/tmp/actor_a")
    monkeypatch.setenv("OSCOMBO_ACTION_LOG", str(tmp_path / "cli.jsonl"))

    bad_cmd = run_guest_cli(["rm", "-rf", "file.txt"])
    assert bad_cmd["ok"] is False
    assert "not in allowed" in bad_cmd["error"]

    escape = run_guest_cli(["cat", "../actor_b/secret.txt"])
    assert escape["ok"] is False
    assert "escapes assigned Guest CLI root" in escape["error"]

    abs_escape = run_guest_cli(["cat", "/etc/passwd"])
    assert abs_escape["ok"] is False
    assert "escapes assigned Guest CLI root" in abs_escape["error"]


def test_desktop_gate_holds_until_release(tmp_path, monkeypatch):
    import fcntl
    from contextlib import contextmanager
    namespace = {"os": os, "json": json, "time": time, "fcntl": fcntl, "contextmanager": contextmanager}
    exec(compile(DESKTOP_GATE_LOCK_HELPERS, "gate_helpers.py", "exec"), namespace)
    check_gate = namespace["_check_and_hold_gate"]
    mark_dispatched = namespace["_mark_gate_dispatched"]

    signal_dir = tmp_path / "gate_signal"
    cfg_path = tmp_path / "gate.json"
    cfg_path.write_text(json.dumps({
        "gate_id": "test-gate-1",
        "actor_id": "A",
        "tool": "click",
        "argument": "x",
        "contains_any": ["564"],
        "signal_dir": str(signal_dir),
        "timeout_seconds": 5,
    }))
    monkeypatch.setenv("OSCOMBO_MCP_GATE_CONFIG", str(cfg_path))
    monkeypatch.setenv("OSCOMBO_ACTOR_ID", "actor_a")
    monkeypatch.setenv("OSCOMBO_EPISODE_ID", "ep-1")

    assert check_gate("click", {"x": 56, "y": 249}) is None

    released_result = {}

    def worker():
        info = check_gate("click", {"x": 564, "y": 249})
        mark_dispatched(info, "click", {"x": 564, "y": 249})
        released_result["info"] = info

    thread = threading.Thread(target=worker)
    thread.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not (signal_dir / "pending.json").is_file():
        time.sleep(0.05)
    assert (signal_dir / "pending.json").is_file()
    assert not (signal_dir / "dispatched.json").exists()
    (signal_dir / "release.json").write_text('{"gate_id": "test-gate-1"}\n')
    thread.join(timeout=3.0)
    assert not thread.is_alive()
    assert (signal_dir / "dispatched.json").is_file()


def test_model_literal_replacement_and_19case_roster():
    assert len(PORTFOLIO_19) == 19
    sample = b'MODEL = "gpt-6-sol"\nOTHER = "gpt-6-sol-note"\n'
    replaced, lines = replace_model_literals(sample)
    ast.parse(replaced.decode())
    assert lines == [1]
    assert b"'gpt-6.1-sol'" in replaced
    assert b'"gpt-6-sol-note"' in replaced
