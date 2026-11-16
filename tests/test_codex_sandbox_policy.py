"""Reject sandbox bypasses even in the auto-approved Full GUI+CLI mode."""
import json

import pytest

from experiments.codesk_container_codex import (
    CONTAINER_ENTRY_SOURCE,
    container_permission_policy,
    validate_container_config_text,
    verify_container_permission_audit,
)
from experiments.astra_races_v2 import build_astra_config_template
from experiments.professional_races_v1 import build_full_cli_config_template


@pytest.mark.parametrize("template", [build_astra_config_template(), build_full_cli_config_template("test-model")])
@pytest.mark.parametrize("override", [
    '\n[profiles.bypass]\nsandbox_mode = "danger-full-access"\n',
    '\n[profiles.bypass]\nsandbox_mode = "external-sandbox"\n',
    '\n[mcp_servers.extra]\ncommand = "codex"\nargs = ["--yolo"]\n',
    '\n[mcp_servers.extra]\ncommand = "codex"\nargs = ["--dangerously-bypass-approvals-and-sandbox"]\n',
])
def test_host_and_container_reject_nested_bypass(tmp_path, template, override):
    config = template.replace("__CONTAINER_RELAY_PORT__", "18080") + override
    with pytest.raises(ValueError, match="bypass"):
        validate_container_config_text(config, "container-unrestricted")
    namespace = {"__name__": "entry_under_test"}
    exec(compile(CONTAINER_ENTRY_SOURCE, "container_entry.py", "exec"), namespace)
    path = tmp_path / "config.toml"
    path.write_text(config)
    with pytest.raises(RuntimeError, match="bypass"):
        namespace["verify_config"](path, "container-unrestricted")


@pytest.mark.parametrize("template", [build_astra_config_template(), build_full_cli_config_template("test-model")])
def test_full_cli_keeps_auto_approved_shell_and_desktop_tools(template):
    cfg = validate_container_config_text(template.replace("__CONTAINER_RELAY_PORT__", "18080"), "container-unrestricted")
    assert cfg["sandbox_mode"] == "workspace-write"
    assert cfg["approval_policy"] == "never"
    assert cfg["features"]["shell_tool"] is True
    for server in cfg["mcp_servers"].values():
        assert server["default_tools_approval_mode"] == "approve"


def write_entry_audit(tmp_path):
    audit = dict(container_permission_policy("container-unrestricted"), docker_marker=True,
        home="/session", codex_home="/session/codex-home", cwd="/session", uid=1000)
    (tmp_path / "permission-audit.json").write_text(json.dumps(audit))


@pytest.mark.parametrize("sandbox,approval,profile,model,valid", [
    ("workspace-write", "never", None, "expected", True),
    ("danger-full-access", "never", None, "expected", False),
    ("external-sandbox", "never", None, "expected", False),
    ("workspace-write", "on-request", None, "expected", False),
    ("workspace-write", "never", {"type": "disabled"}, "expected", False),
    (None, "never", None, "expected", False),
    ("workspace-write", "never", None, "other-model", False),
])
def test_audit_checks_effective_runtime_permissions(tmp_path, sandbox, approval, profile, model, valid):
    write_entry_audit(tmp_path)
    sessions = tmp_path / "codex-home/sessions"
    sessions.mkdir(parents=True)
    payload = {"model": model, "sandbox_policy": {"type": sandbox},
        "approval_policy": approval, "permission_profile": profile, "cwd": "/session/work"}
    (sessions / "rollout.jsonl").write_text(json.dumps({"type": "turn_context", "payload": payload}) + "\n")
    if valid:
        result = verify_container_permission_audit(tmp_path, "expected", "container-unrestricted")
        assert len(result["turn_contexts"]) == 1
    else:
        with pytest.raises(RuntimeError):
            verify_container_permission_audit(tmp_path, "expected", "container-unrestricted")


def test_missing_turn_context_is_not_reported_as_verified(tmp_path):
    write_entry_audit(tmp_path)
    with pytest.raises(RuntimeError, match="No Codex turn_context"):
        verify_container_permission_audit(tmp_path, "expected", "container-unrestricted")
