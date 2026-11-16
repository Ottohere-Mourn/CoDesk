from concurrent.futures import ThreadPoolExecutor
import json
import shlex
import sys
import threading
import time
import tomllib
from types import SimpleNamespace

import pytest

from experiments import professional_native as native
from experiments import professional_codex_entry as entry
from experiments.professional_native_batch import validate_preflight
from experiments.professional_shell import execute
from experiments.professional_tools import action_commands, tool_schema


def test_hybrid_config_and_entry_enable_shell_without_changing_permission_scope(tmp_path):
    args = SimpleNamespace(harness="codex", codex_permissions="container-unrestricted", interaction_mode="hybrid")
    runtime, command = native.prepare_native(tmp_path, args, {"model": "test-model"}, "http://relay/v1", "Edit own objects")
    config = tomllib.loads((runtime / "codex-home/config.toml").read_text())
    assert config["features"]["shell_tool"] is True
    assert config["sandbox_mode"] == "workspace-write"
    assert config["approval_policy"] == "on-request"
    assert command[-2:] == ["--interaction-mode", "hybrid"]
    assert "features.shell_tool=true" in entry.codex_command("container-unrestricted", "hybrid")
    assert entry.permissions("container-unrestricted", "hybrid")["scope"] == "harness-container-only"
    prompt = (runtime / "task.md").read_text()
    assert "Programming is allowed" in prompt
    assert "Do not open a terminal" not in prompt
    assert "Do not open terminals" in native.interaction_rules("gui-only")


def test_modes_have_distinct_immutable_schemas():
    hybrid = tool_schema("hybrid")
    gui = tool_schema("gui-only")
    assert "shell" in hybrid["parameters"]["properties"]["actions"]["items"]["properties"]["type"]["enum"]
    assert "shell" not in gui["parameters"]["properties"]["actions"]["items"]["properties"]["type"]["enum"]
    assert "shell" not in native.collector.TOOLS[0]["parameters"]["properties"]["actions"]["items"]["properties"]["type"]["enum"]
    with pytest.raises(ValueError):
        tool_schema("unknown")


@pytest.mark.parametrize("image_history_limit", [4, 7])
def test_freehand_hybrid_prompt_includes_target_cli_bridge(tmp_path, monkeypatch, image_history_limit):
    runtime_source = tmp_path / "source"
    harness = runtime_source / "freehand/harness"
    harness.mkdir(parents=True)
    (harness / "run.sh").write_text("exit 0\n")
    (runtime_source / "freehand/prompt.md").write_text("Manage context in /freehand/harness.")
    monkeypatch.setitem(sys.modules, "freehand.harness.agent", SimpleNamespace(DEFAULT_CONFIG={}))
    root = tmp_path / "agent"
    root.mkdir()
    args = SimpleNamespace(harness="freehand", freehand_runtime=runtime_source,
        interaction_mode="hybrid", max_turns=10, image_history_limit=image_history_limit)
    runtime, command = native.prepare_native(root, args, {"model": "test-model"}, "http://relay/v1", "Edit own layer")
    assert command == ["bash", "/session/src/run.sh"]
    assert "Programming is allowed" in (runtime / "prompt.md").read_text()
    prompt = (runtime / "task.md").read_text()
    assert "single shell action" in prompt and "/bridge/client.py" in prompt
    assert "Do not open terminals" not in prompt
    assert json.loads((runtime / "config.json").read_text())["workdir"] == "/session"
    assert json.loads((runtime / "config.json").read_text())["image_history_limit"] == image_history_limit


@pytest.mark.parametrize("action", [
    {"type": "shell"}, {"type": "shell", "command": " "},
    {"type": "shell", "command": "x\0y"}, {"type": "shell", "command": "x" * 32769},
    *[{"type": "shell", "command": "pwd", "timeout": value} for value in (0, -1, 61, True, "30", float("nan"), float("inf"))],
])
def test_hybrid_rejects_malformed_commands(action):
    with pytest.raises(ValueError):
        native.validate_actions({"actions": [action]}, 10, "hybrid")


def test_shell_requires_hybrid_and_one_action_per_call():
    shell = {"type": "shell", "command": "pwd"}
    with pytest.raises(ValueError, match="hybrid"):
        native.validate_actions({"actions": [shell]}, 10, "gui-only")
    with pytest.raises(ValueError, match="only action"):
        native.validate_actions({"actions": [shell, {"type": "screenshot"}]}, 10, "hybrid")
    with pytest.raises(ValueError, match="budget"):
        native.validate_actions({"actions": [shell]}, 0, "hybrid")
    argv = action_commands(shell, "hybrid")[0]
    assert argv[:2] == ["python3", "-c"]
    assert argv[-2:] == ["pwd", "30"]


def test_shell_captures_output_cwd_and_exit_code(tmp_path):
    result = execute("pwd; printf ok; printf failure >&2; exit 7", 2, cwd=tmp_path)
    assert result["stdout"] == str(tmp_path) + "\nok"
    assert result["stderr"] == "failure"
    assert result["exit_code"] == 7
    assert not result["timed_out"]


def test_shell_bounds_output_and_handles_invalid_utf8(tmp_path):
    result = execute("head -c 100000 /dev/zero; printf '\\377' >&2", 2, cwd=tmp_path)
    assert len(result["stdout"]) == 16384
    assert result["output_truncated"] == {"stdout": True, "stderr": False}
    assert result["stderr"] == "\ufffd"
    assert result["exit_code"] == 0


def test_shell_deadline_terminates_descendants(tmp_path):
    marker = tmp_path / "must-not-exist"
    started = time.monotonic()
    result = execute(f"(sleep .4; touch {shlex.quote(str(marker))}) & wait", .1, cwd=tmp_path)
    assert result["timed_out"]
    assert result["exit_code"] != 0
    assert time.monotonic() - started < 2
    time.sleep(.5)
    assert not marker.exists()


def test_shell_cleans_detached_output_children_on_return(tmp_path):
    marker = tmp_path / "must-not-exist"
    result = execute(f"(sleep .3; touch {shlex.quote(str(marker))}) >/dev/null 2>&1 & printf ok", 2, cwd=tmp_path)
    assert result["exit_code"] == 0
    assert result["stdout"] == "ok"
    time.sleep(.4)
    assert not marker.exists()


@pytest.mark.parametrize("exit_code", [0, 3])
def test_broker_routes_shell_to_desktop_and_records_results(tmp_path, exit_code):
    commands = []
    shell_result = {"stdout": "target workspace", "stderr": "diagnostic", "exit_code": exit_code, "timed_out": False}
    class Desktop:
        name = "shared-desktop"
        def focus(self):
            return "Blender"
        def raw(self, argv, **kwargs):
            commands.append((argv, kwargs))
            if argv[:2] == ["python3", "-c"] and len(argv) == 5:
                return SimpleNamespace(stdout=json.dumps(shell_result).encode())
            return SimpleNamespace(stdout=b"screenshot")
    timeline = native.shared.Timeline(tmp_path)
    session = native.DesktopSession(Desktop(), timeline, tmp_path / "p1a", "p1a",
        SimpleNamespace(max_actions=2, interaction_mode="hybrid"))
    session.started_at = time.time()
    session.deadline = time.monotonic() + 5
    result = session.perform({"actions": [{"type": "shell", "command": "pwd", "timeout": 60}]})
    assert result["actions"][0]["shell_result"] == shell_result
    assert result["actions"][0]["status"] == ("error" if exit_code else "ok")
    assert result["actions_remaining"] == 1
    assert result["image"]
    assert session.action_counts == {"cli": 1}
    shell_call = next(call for call in commands if len(call[0]) == 5)
    assert 0 < float(shell_call[0][-1]) <= 5
    assert shell_call[1]["timeout"] <= 15
    event = json.loads((tmp_path / "p1a/actions.jsonl").read_text())
    assert event["shell_result"] == shell_result
    assert event["channel"] == "cli"


def test_hybrid_agents_do_not_share_an_execution_lock(tmp_path):
    barrier = threading.Barrier(2)
    class Desktop:
        name = "shared-desktop"
        def focus(self):
            return "Blender"
        def raw(self, argv, **kwargs):
            if len(argv) == 5:
                barrier.wait(timeout=3)
                return SimpleNamespace(stdout=b'{"stdout":"ok","stderr":"","exit_code":0,"timed_out":false}')
            return SimpleNamespace(stdout=b"screenshot")
    timeline = native.shared.Timeline(tmp_path)
    sessions = [native.DesktopSession(Desktop(), timeline, tmp_path / task, task,
        SimpleNamespace(max_actions=2, interaction_mode="hybrid")) for task in ("p1a", "p1b")]
    for session in sessions:
        session.started_at = time.time()
        session.deadline = time.monotonic() + 10
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda session: session.perform(
            {"actions": [{"type": "shell", "command": "pwd"}]}), sessions))
    assert all(result["actions"][0]["status"] == "ok" for result in results)


def test_gui_preflight_cannot_authorize_hybrid_and_cli_evidence_is_required(tmp_path):
    native.collector.save(tmp_path / "validation.json", {"passed": True})
    manifest = {"harness": "codex", "smoke": True, "tasks": ["p1a", "p1b"],
        "codex_permissions": entry.permissions("container-unrestricted")}
    native.collector.save(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="interaction mode"):
        validate_preflight(tmp_path, "codex", "container-unrestricted", "hybrid")
    manifest.update(interaction_mode="hybrid", codex_permissions=entry.permissions("container-unrestricted", "hybrid"))
    native.collector.save(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="both agents"):
        validate_preflight(tmp_path, "codex", "container-unrestricted", "hybrid")
    for task in manifest["tasks"]:
        root = tmp_path / task
        root.mkdir()
        native.collector.append(root / "actions.jsonl", {"action": {"type": "screenshot"}, "status": "ok"})
        assert not native.hybrid_smoke_passed(root)
        native.collector.append(root / "actions.jsonl", {"action": {"type": "shell"}, "status": "ok",
            "shell_result": {"stdout": "paragui-hybrid-ok/workspace\n1000\n", "exit_code": 0, "timed_out": False}})
        assert native.hybrid_smoke_passed(root)
    validate_preflight(tmp_path, "codex", "container-unrestricted", "hybrid")


def test_native_cli_defaults_to_hybrid_without_enabling_unrestricted_permissions(monkeypatch):
    monkeypatch.setattr(native, "run", lambda args: args)
    args = native.main(["--dataset", "dataset", "--credentials", "credentials", "--out", "run",
        "--harness", "codex", "--freehand-runtime", "runtime", "--codex-binary", "codex"])
    assert args.interaction_mode == "hybrid"
    assert args.codex_permissions == "reviewed"


def test_hybrid_permission_audit_rejects_gui_only_entry(tmp_path):
    native.collector.save(tmp_path / "permission-audit.json", dict(
        entry.permissions("container-unrestricted", "gui-only"), docker_marker=True, uid=1000,
        codex_home="/session/codex-home", home="/session", cwd="/session"))
    with pytest.raises(ValueError, match="entry permission audit"):
        native.audit_codex_permissions(tmp_path, "container-unrestricted", "test-model", "hybrid")
