import json
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import tomllib
from types import SimpleNamespace

import pytest

from experiments import professional_bridge as bridge
from experiments import professional_native as native
from experiments import professional_codex_entry as entry
from experiments.professional_native_batch import validate_preflight
from experiments.professional_native import codex_config, validate_actions


def test_codex_permissions_remain_restricted():
    config = tomllib.loads(codex_config("gpt-6-astra", "high", "http://relay/v1"))
    assert config["approval_policy"] == "on-request"
    assert config["sandbox_mode"] == "workspace-write"
    assert config["features"]["shell_tool"] is False
    assert config["features"]["multi_agent"] is False
    assert config["mcp_servers"]["desktop"]["args"] == ["/bridge/client.py", "--mcp"]


def test_runtime_requires_package_parent(tmp_path):
    trace = tmp_path / "freehand/harness/calltrace.py"
    trace.parent.mkdir(parents=True)
    trace.write_text("")
    assert native.validate_freehand_runtime(tmp_path) == tmp_path.resolve()
    with pytest.raises(ValueError, match="parent directory"):
        native.validate_freehand_runtime(tmp_path / "freehand")


def test_bad_runtime_fails_before_creating_run_or_desktop(tmp_path):
    args = SimpleNamespace(freehand_runtime=tmp_path / "missing", out=tmp_path / "run")
    with pytest.raises(ValueError, match="freehand/harness/calltrace.py"):
        native.run(args)
    assert not args.out.exists()


def test_unrestricted_mode_is_explicit_and_never_uses_yolo_flag():
    reviewed = entry.codex_command("reviewed")
    unrestricted = entry.codex_command("container-unrestricted")
    assert "--approve-for-me" in reviewed
    assert 'sandbox_mode="danger-full-access"' not in reviewed
    assert 'sandbox_mode="workspace-write"' in unrestricted
    assert 'sandbox_mode="danger-full-access"' not in unrestricted
    assert 'approval_policy="never"' in unrestricted
    assert "--approve-for-me" not in unrestricted
    assert "--yolo" not in unrestricted
    assert "--dangerously-bypass-approvals-and-sandbox" not in unrestricted
    assert entry.permissions("container-unrestricted")["yolo_equivalent"] is False
    assert entry.permissions("container-unrestricted")["scope"] == "harness-container-only"
    with pytest.raises(ValueError):
        entry.codex_command("unknown")


def test_entry_refuses_host_before_executing_codex(monkeypatch):
    executed = []
    monkeypatch.setattr(entry.Path, "is_file", lambda path: False)
    monkeypatch.setattr(entry.os, "execv", lambda *arguments: executed.append(arguments))
    with pytest.raises(RuntimeError, match="outside Docker"):
        entry.main(["--permissions", "container-unrestricted"])
    assert executed == []


@pytest.mark.parametrize("home,codex_home,uid,cwd", [
    ("/home/user", "/session/codex-home", 1000, "/session"),
    ("/session", "/home/user/.codex", 1000, "/session"),
    ("/session", "/session/codex-home", 0, "/session"),
    ("/session", "/session/codex-home", 1000, "/home/user"),
])
def test_entry_refuses_wrong_container_environment(monkeypatch, home, codex_home, uid, cwd):
    monkeypatch.setattr(entry.Path, "is_file", lambda path: str(path) == "/.dockerenv")
    monkeypatch.setattr(entry.Path, "cwd", classmethod(lambda cls: entry.Path(cwd)))
    monkeypatch.setattr(entry.os, "getuid", lambda: uid)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("CODEX_HOME", codex_home)
    with pytest.raises(RuntimeError):
        entry.require_container()


def test_entry_accepts_only_expected_container_environment(monkeypatch):
    monkeypatch.setattr(entry.Path, "is_file", lambda path: str(path) == "/.dockerenv")
    monkeypatch.setattr(entry.Path, "cwd", classmethod(lambda cls: entry.Path("/session")))
    monkeypatch.setattr(entry.os, "getuid", lambda: 1000)
    monkeypatch.setenv("HOME", "/session")
    monkeypatch.setenv("CODEX_HOME", "/session/codex-home")
    entry.require_container()


def test_prepare_keeps_disk_config_restricted_and_uses_guarded_entry(tmp_path):
    args = SimpleNamespace(harness="codex", codex_permissions="container-unrestricted", interaction_mode="gui-only")
    runtime, command = native.prepare_native(tmp_path, args,
        {"model": "gpt-6-astra"}, "http://relay/v1", "Take a screenshot")
    config = tomllib.loads((runtime / "codex-home/config.toml").read_text())
    assert config["sandbox_mode"] == "workspace-write"
    assert config["approval_policy"] == "on-request"
    assert command == ["python3", "/bridge/codex_entry.py", "--permissions", "container-unrestricted",
        "--interaction-mode", "gui-only"]


def test_codex_launch_uses_only_isolated_mounts_and_docker_command(tmp_path):
    args = SimpleNamespace(harness="codex", out=tmp_path,
        codex_binary=tmp_path / "binary/codex", image="test-image")
    runtime = tmp_path / "agent/runtime"
    command = ["python3", "/bridge/codex_entry.py", "--permissions", "container-unrestricted"]
    launch = native.container_launch(args, runtime, "test-agent", "private-network", "http://broker/token", command)
    assert launch[:2] == ["docker", "run"]
    assert launch[launch.index(args.image) + 1:] == command
    mounts = [launch[index + 1] for index, value in enumerate(launch) if value == "-v"]
    assert mounts == [str(runtime) + ":/session", str(tmp_path / "bridge") + ":/bridge:ro",
        str(tmp_path / "binary") + ":/codex:ro"]
    assert "--privileged" not in launch
    assert launch[launch.index("--network") + 1] == "private-network"
    assert launch[launch.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in launch
    assert "--read-only" in launch
    assert "CODEX_HOME=/session/codex-home" in launch
    assert "HOME=/session" in launch
    requirement_mount = launch[launch.index("--mount") + 1]
    assert requirement_mount.endswith(",dst=/etc/codex/requirements.toml,readonly")
    assert "/configs/codex.requirements.toml," in requirement_mount


def test_preflight_must_match_container_permissions(tmp_path):
    native.collector.save(tmp_path / "validation.json", {"passed": True})
    native.collector.save(tmp_path / "manifest.json", {"harness": "codex", "smoke": True,
        "codex_permissions": entry.permissions("reviewed")})
    validate_preflight(tmp_path, "codex", "reviewed")
    with pytest.raises(ValueError, match="permissions do not match"):
        validate_preflight(tmp_path, "codex", "container-unrestricted")
    with pytest.raises(ValueError, match="selected harness"):
        validate_preflight(tmp_path, "freehand", "reviewed")
    native.collector.save(tmp_path / "validation.json", {"passed": False})
    with pytest.raises(ValueError, match="passing native screenshot"):
        validate_preflight(tmp_path, "codex", "reviewed")


@pytest.mark.parametrize("sandbox,approval,valid", [
    ("workspace-write", "never", True),
    ("danger-full-access", "never", False),
    ("external-sandbox", "never", False),
    ("workspace-write", "on-request", False),
    ("danger-full-access", "on-request", False),
])
def test_native_turn_permissions_are_verified(tmp_path, sandbox, approval, valid):
    native.collector.save(tmp_path / "permission-audit.json",
        dict(entry.permissions("container-unrestricted"), docker_marker=True, uid=1000,
            codex_home="/session/codex-home", home="/session", cwd="/session"))
    sessions = tmp_path / "codex-home/sessions"
    sessions.mkdir(parents=True)
    native.collector.append(sessions / "turn.jsonl", {"type": "turn_context", "payload": {
        "model": "gpt-6-astra", "approval_policy": approval, "sandbox_policy": {"type": sandbox}, "cwd": "/session"}})
    if valid:
        audit = native.audit_codex_permissions(tmp_path, "container-unrestricted", "gpt-6-astra")
        assert audit["effective_turn_contexts"] == [{"approval": "never", "sandbox": "workspace-write", "cwd": "/session"}]
    else:
        with pytest.raises(ValueError, match="Native Codex turn permissions"):
            native.audit_codex_permissions(tmp_path, "container-unrestricted", "gpt-6-astra")


def test_actions_reject_shell_and_excess_budget():
    with pytest.raises(ValueError):
        validate_actions({"actions": [{"type": "shell", "command": "echo unsafe"}]}, 10)
    with pytest.raises(ValueError):
        validate_actions({"actions": [{"type": "screenshot"}] * 13}, 100)
    with pytest.raises(ValueError):
        validate_actions({"actions": [{"type": "screenshot"}] * 2}, 1)
    assert validate_actions({"actions": [{"type": "click", "x": 1, "y": 2}]}, 1)


def test_mcp_returns_actual_image(monkeypatch):
    monkeypatch.setattr(bridge, "perform", lambda arguments: {"actions": [], "image": "encoded"})
    result = bridge.mcp_reply({"method": "tools/call", "params": {
        "name": "desktop", "arguments": {"actions": [{"type": "screenshot"}]}}}, {})
    assert result["content"][1] == {"type": "image", "data": "encoded", "mimeType": "image/png"}
    assert json.loads(result["content"][0]["text"]) == {"actions": []}
    assert result["isError"] is False


def test_mcp_rejects_unknown_tools():
    with pytest.raises(ValueError):
        bridge.mcp_reply({"method": "tools/call", "params": {"name": "shell"}}, {})


def test_mcp_initialization_and_schema():
    result = bridge.mcp_reply({"method": "initialize", "params": {"protocolVersion": "2025-03-26"}}, {})
    assert result["protocolVersion"] == "2025-03-26"
    schema = {"description": "desktop only", "parameters": {"type": "object"}}
    assert bridge.mcp_reply({"method": "tools/list"}, schema)["tools"][0]["inputSchema"] == schema["parameters"]


def test_network_ignores_null_ipam_and_existing_routes(monkeypatch):
    commands = []
    def command(argv, **kwargs):
        commands.append(argv)
        if argv[:3] == ["docker", "network", "ls"]:
            return SimpleNamespace(stdout="host bridge")
        if argv[:3] == ["docker", "network", "inspect"]:
            return SimpleNamespace(stdout=json.dumps([{"IPAM": {"Config": None}}]))
        if argv[0] == "ip":
            return SimpleNamespace(stdout=json.dumps([{"dst": "default"}, {"dst": "10.252.240.0/28"}]))
        return SimpleNamespace(stdout="created")
    monkeypatch.setattr(native.collector, "command", command)
    assert native.create_network("test-network") == "10.252.240.17"
    assert commands[-1] == ["docker", "network", "create", "--internal", "--subnet", "10.252.240.16/28", "test-network"]


def test_desktop_agents_really_execute_concurrently(tmp_path, monkeypatch):
    barrier = threading.Barrier(2)
    class Desktop:
        name = "one-shared-desktop"
        def focus(self):
            return "QGIS"
        def raw(self, argv, **kwargs):
            if argv[0] == "xdotool":
                barrier.wait(timeout=3)
            return SimpleNamespace(stdout=b"test screenshot")
    timeline = native.shared.Timeline(tmp_path)
    args = SimpleNamespace(max_actions=10, interaction_mode="gui-only")
    sessions = [native.DesktopSession(Desktop(), timeline, tmp_path / task, task, args)
        for task in ("p3a", "p3b")]
    for session in sessions:
        session.started_at = time.time()
        session.deadline = time.monotonic() + 30
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(session.perform, {"actions": [{"type": "key", "keys": "Escape"}]})
            for session in sessions]
        results = [future.result() for future in futures]
    assert all(result["actions"][0]["status"] == "ok" for result in results)
    assert all(session.actions == 1 for session in sessions)
    assert all(result["image"] for result in results)
    events = [json.loads(line) for line in (tmp_path / "timeline.jsonl").read_text().splitlines()]
    phases = [event["event"] for event in events if event["event"] in ("action_start", "input_end")]
    assert phases[:2] == ["action_start", "action_start"]


def test_approval_model_allowlist_does_not_replace_task_model(tmp_path):
    server = native.ResponsesRelay(("127.0.0.1", 0), tmp_path, model="gpt-6-astra",
        provider={"url": "http://unused", "headers": {}}, trace=SimpleNamespace(),
        allowed_models=["codex-auto-review"])
    try:
        assert server.model == "gpt-6-astra"
        assert server.allowed_models == {"gpt-6-astra", "codex-auto-review"}
    finally:
        server.server_close()
