"""Honest audit of host Codex subprocesses and the shared OSWorld Guest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


AUDIT_SCHEMA = "paragui.permission-audit/v2"
VERIFIED_SCHEMA = "paragui.permission-audit-verified/v1"


def build_entry_audit(
    *, container_id: str, uid: int, gid: int, model_id: str,
    actor_pid: int, actor_role: str, role_private_path: str,
    sandbox_mode: str = "workspace-write", approval_policy: str = "never",
    permission_profile_type: str = "managed",
    tools_enabled: Iterable[str] = ("desktop", "guest_cli"),
    shell_tool: bool = False, unified_exec: bool = False,
    guest_cli_shell: bool = True, guest_cli_read_write: bool = True,
    guest_workspace: str = "/home/user/workspace", home: str | None = None,
    codex_home: str | None = None, cwd: str | None = None,
    codex_workdir: str | None = None,
    relay_port: int | None = None, host_shell_exposed: bool = False,
    host_oracle_exposed: bool = False, yolo_flag_used: bool = False,
    yolo_enabled: bool = False,
) -> dict[str, Any]:
    role = actor_role.lower()
    if role not in {"actor_a", "actor_b"}:
        raise ValueError("actor_role must be actor_a or actor_b")
    return {
        "schema_version": AUDIT_SCHEMA,
        "container_id": container_id,
        "container_runtime": "docker-shared-guest",
        "actor_process_runtime": "host-subprocess",
        "actor_pid": int(actor_pid),
        "uid": int(uid), "gid": int(gid), "model_id": model_id,
        "sandbox_mode": sandbox_mode, "approval_policy": approval_policy,
        # Codex reports the permission profile separately from sandbox_policy.
        # On the installed managed-runtime configuration, `managed` is the
        # profile envelope and its nested filesystem/network fields carry the
        # actual profile details. It is not a synonym for workspace-write.
        "permission_profile_type": permission_profile_type,
        "tools_enabled": sorted(set(tools_enabled)),
        "shell_tool": bool(shell_tool), "unified_exec": bool(unified_exec),
        "guest_cli_shell": bool(guest_cli_shell),
        "guest_cli_read_write": bool(guest_cli_read_write),
        "guest_workspace": guest_workspace, "home": home,
        "codex_home": codex_home, "cwd": cwd, "codex_workdir": codex_workdir,
        "relay_port": int(relay_port) if relay_port is not None else None,
        "host_shell_exposed": bool(host_shell_exposed),
        "host_oracle_exposed": bool(host_oracle_exposed),
        "yolo_flag_used": bool(yolo_flag_used), "yolo_enabled": bool(yolo_enabled),
        "role_private_path": {
            "actor": role, "guest_path": role_private_path,
            "physical_isolation": False,
            "verification": "post-run action-log path audit",
        },
        "actor_role": role,
        "no_new_privileges": None,
        "no_new_privileges_scope": "not_asserted_for_host_subprocess",
    }


def verify_entry_audit(entry: dict[str, Any], *, expected_model: str | None = None) -> None:
    if entry.get("schema_version") != AUDIT_SCHEMA or entry.get("container_runtime") != "docker-shared-guest":
        raise ValueError("Missing shared Guest / host Actor permission audit record")
    if entry.get("actor_process_runtime") != "host-subprocess" or int(entry.get("actor_pid") or 0) <= 0:
        raise ValueError("Actor must be recorded as an observed host subprocess")
    if not entry.get("container_id") or int(entry.get("uid", 0)) <= 0:
        raise ValueError("Shared Guest container identity and non-root host UID are required")
    if expected_model and entry.get("model_id") != expected_model:
        raise ValueError("Entry audit model does not match the episode model")
    if entry.get("sandbox_mode") != "workspace-write" or entry.get("approval_policy") != "never":
        raise ValueError("Entry audit does not match workspace-write / never approval policy")
    if entry.get("permission_profile_type") != "managed":
        raise ValueError("Entry audit does not declare the observed managed Codex permission profile")
    tools = set(entry.get("tools_enabled", []))
    if not {"desktop", "guest_cli"}.issubset(tools):
        raise ValueError("Desktop and Guest CLI must both be enabled")
    if entry.get("shell_tool") is not False or entry.get("unified_exec") is not False:
        raise ValueError("Host shell and unified_exec must remain disabled")
    if entry.get("guest_cli_shell") is not True or entry.get("guest_cli_read_write") is not True:
        raise ValueError("Guest CLI must provide read/write/execute inside the Guest workspace")
    if entry.get("host_shell_exposed") or entry.get("host_oracle_exposed"):
        raise ValueError("Host shell/Oracle must remain outside the Guest tool surface")
    if entry.get("yolo_flag_used") or entry.get("yolo_enabled"):
        raise ValueError("YOLO/bypass mode is forbidden")
    if entry.get("no_new_privileges") is not None or entry.get("no_new_privileges_scope") != "not_asserted_for_host_subprocess":
        raise ValueError("Do not claim container NoNewPrivs for a host subprocess")
    role_path = entry.get("role_private_path") or {}
    role = entry.get("actor_role")
    if role not in {"actor_a", "actor_b"} or role_path.get("actor") != role:
        raise ValueError("Actor role-private path record is incomplete")
    if role_path.get("physical_isolation") is not False:
        raise ValueError("Path-based role separation must not claim physical isolation")


def _path_scope(path: Any) -> str | None:
    if not isinstance(path, dict):
        return None
    if path.get("type") == "path" and isinstance(path.get("path"), str):
        return path["path"]
    if path.get("type") == "special":
        value = path.get("value") or {}
        if isinstance(value, dict) and value.get("kind") in {"root", "slash_tmp", "tmpdir"}:
            return "$" + str(value["kind"])
    return None


def _managed_permission_summary(payload: dict[str, Any], expected_cwd: str | None) -> dict[str, Any]:
    """Validate the managed profile independently of the sandbox declaration.

    `permission_profile.type` describes the Codex permission-profile envelope;
    `sandbox_policy.type` describes the sandbox mode. They are separate fields
    and must not be compared as if they were the same enum.
    """
    profile = payload.get("permission_profile") or {}
    if not isinstance(profile, dict) or profile.get("type") != "managed":
        raise ValueError("turn_context is missing the declared managed permission profile")
    fs_profile = profile.get("file_system") or {}
    fs_observed = payload.get("file_system_sandbox_policy") or {}
    if not isinstance(fs_profile, dict) or fs_profile.get("type") != "restricted":
        raise ValueError("managed permission profile filesystem policy is not restricted")
    if not isinstance(fs_observed, dict) or fs_observed.get("kind") != "restricted":
        raise ValueError("turn_context filesystem sandbox policy is not restricted")
    if profile.get("network") != "restricted":
        raise ValueError("managed permission profile network policy is not restricted")

    profile_entries = fs_profile.get("entries") or []
    observed_entries = fs_observed.get("entries") or []
    if not isinstance(profile_entries, list) or not isinstance(observed_entries, list):
        raise ValueError("turn_context managed filesystem entries are malformed")
    if profile_entries != observed_entries:
        raise ValueError("managed permission profile and effective filesystem entries differ")

    writable: set[str] = set()
    readable: set[str] = set()
    for item in profile_entries:
        if not isinstance(item, dict):
            raise ValueError("turn_context filesystem entry is malformed")
        access = item.get("access")
        if access in {"read", "write"}:
            scope = _path_scope(item.get("path"))
            if scope is None:
                raise ValueError("managed profile contains an unrecognized filesystem scope")
            if access == "write":
                writable.add(scope)
            else:
                readable.add(scope)
    allowed = {"$slash_tmp", "$tmpdir"}
    if expected_cwd:
        allowed.add(expected_cwd)
    if writable != allowed:
        raise ValueError("managed profile writable scopes differ from the declared Actor workspace and temp scopes")
    if not expected_cwd or not str(expected_cwd).startswith("/"):
        raise ValueError("Actor Codex work directory is required to verify managed profile write scope")
    return {
        "type": "managed", "network": "restricted",
        "file_system_type": "restricted",
        "read_scopes": sorted(readable),
        "write_scopes": sorted(writable),
    }


def _read_turn_contexts(
    paths: Iterable[str | Path], expected_model: str | None,
    expected_sandbox_mode: str, expected_approval_policy: str,
    expected_permission_profile_type: str,
    expected_cwd: str | None,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("type") != "turn_context":
                continue
            payload = row.get("payload") or {}
            sandbox = (payload.get("sandbox_policy") or {}).get("type")
            approval = payload.get("approval_policy")
            permission = (payload.get("permission_profile") or {}).get("type")
            if (sandbox != expected_sandbox_mode or approval != expected_approval_policy
                    or permission != expected_permission_profile_type):
                raise ValueError(f"turn_context policy mismatch ({path}:{line_number})")
            if expected_model and payload.get("model") != expected_model:
                raise ValueError(f"turn_context model mismatch ({path}:{line_number})")
            context_cwd = payload.get("cwd")
            if expected_cwd and context_cwd != expected_cwd:
                raise ValueError(f"turn_context cwd mismatch ({path}:{line_number})")
            managed = _managed_permission_summary(payload, expected_cwd)
            contexts.append({
                "source": str(path), "sandbox_mode": sandbox,
                "approval_policy": approval,
                "permission_profile": managed,
                "model_id": payload.get("model"), "cwd": context_cwd,
            })
    if not contexts:
        raise ValueError("No Codex session turn_context records were found")
    return contexts


def verify_episode_permissions(
    entry_audit: dict[str, Any], *, session_event_files: Iterable[str | Path],
    expected_model: str | None = None,
) -> dict[str, Any]:
    verify_entry_audit(entry_audit, expected_model=expected_model)
    contexts = _read_turn_contexts(
        session_event_files, expected_model,
        expected_sandbox_mode=str(entry_audit["sandbox_mode"]),
        expected_approval_policy=str(entry_audit["approval_policy"]),
        expected_permission_profile_type=str(entry_audit["permission_profile_type"]),
        expected_cwd=entry_audit.get("codex_workdir"),
    )
    return {
        "schema_version": VERIFIED_SCHEMA, "verified": True,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_audit": entry_audit, "turn_contexts": contexts,
        "evidence_scope": "shared Guest identity, host actor process metadata, launch policy and recorded Codex turn_context; no per-Actor container claim",
    }


def write_verified_certificate(path: str | Path, certificate: dict[str, Any]) -> None:
    if certificate.get("schema_version") != VERIFIED_SCHEMA or certificate.get("verified") is not True:
        raise ValueError("Refusing to write an unverified permission certificate")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(certificate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
