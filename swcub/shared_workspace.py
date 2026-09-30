"""Explicit shared-workspace identity and OSWorld 9p mount helpers.

This module validates topology metadata; it does not inspect actor-visible task state.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shlex
from pathlib import Path
from typing import Mapping


SHARED_WORKSPACE_TAG = "codesk_workspace"
GUEST_WORKSPACE_MOUNT = "/tmp/swcub_office"
HOST_MOUNT_PATH = "/codesk-workspace"


class WorkspaceTopologyError(ValueError):
    """Raised when a condition does not preserve its declared workspace topology."""


@dataclass(frozen=True)
class ActorSession:
    actor_id: str
    backend_id: str
    desktop_session_id: str


def validate_condition_topology(condition: str,
                                sessions: Mapping[str, ActorSession]) -> dict[str, object]:
    """Require equal backend identity and the condition-specific desktop identity."""
    if condition not in {"ma_id", "ma_sd"}:
        raise WorkspaceTopologyError(f"same-workspace validation does not support {condition!r}")
    required = {"writer_actor", "calc_actor"}
    if set(sessions) != required:
        raise WorkspaceTopologyError(f"expected exactly {sorted(required)} actor sessions")
    a, b = sessions["writer_actor"], sessions["calc_actor"]
    if not a.backend_id or a.backend_id != b.backend_id:
        raise WorkspaceTopologyError("actors must bind to the same authoritative backend id")
    same_desktop = bool(a.desktop_session_id) and a.desktop_session_id == b.desktop_session_id
    distinct_desktops = (bool(a.desktop_session_id) and bool(b.desktop_session_id)
                         and a.desktop_session_id != b.desktop_session_id)
    if condition == "ma_id" and not distinct_desktops:
        raise WorkspaceTopologyError("MA-ID requires distinct desktop session identities")
    if condition == "ma_sd" and not same_desktop:
        raise WorkspaceTopologyError("MA-SD requires one shared desktop session identity")
    return {
        "condition": condition,
        "backend_id": a.backend_id,
        "desktop_session_ids": {
            "writer_actor": a.desktop_session_id,
            "calc_actor": b.desktop_session_id,
        },
        "same_authoritative_backend": True,
        "same_desktop_session": same_desktop,
        "topology_valid": True,
    }


def write_backend_marker(root: Path, *, backend_id: str, run_id: str,
                         condition: str, generation: str = "task") -> Path:
    """Create a new, run-owned backend directory and non-secret ownership marker."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,80}", backend_id):
        raise WorkspaceTopologyError("backend id has an invalid format")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,80}", run_id):
        raise WorkspaceTopologyError("run id has an invalid format")
    root.mkdir(parents=True, exist_ok=False)
    # QEMU exports this run-scoped directory with 9p security_model=none,
    # which preserves the Guest UID. The Guest's stock user UID differs from
    # the host account; allow Guest actors to write only inside this fresh
    # export. Its parent run directory is private (0750), so this does not
    # expose the backend to other host users.
    root.chmod(0o777)
    marker = root.parent / f".{root.name}.ownership.json"
    marker.write_text(json.dumps({
        "project": "CoDesk",
        "run_id": run_id,
        "backend_id": backend_id,
        "condition": condition,
        "generation": generation,
        "purpose": "shared 9p workspace for one benchmark episode"
    }, indent=2) + "\n", encoding="utf-8")
    return marker


def qemu_virtfs_device(host_container_path: str = HOST_MOUNT_PATH,
                       tag: str = SHARED_WORKSPACE_TAG) -> list[str]:
    """Return the QEMU argv pair for a 9p export inside the runtime container."""
    if not tag or not re.fullmatch(r"[A-Za-z0-9_.-]+", tag):
        raise WorkspaceTopologyError("invalid 9p mount tag")
    if not host_container_path.startswith("/") or "," in host_container_path:
        raise WorkspaceTopologyError("QEMU export path must be absolute and comma-free")
    export = (f"local,path={host_container_path},mount_tag={tag},"
              f"security_model=none,id={tag}")
    return ["-virtfs", export]


def guest_mount_command(tag: str = SHARED_WORKSPACE_TAG,
                        mountpoint: str = GUEST_WORKSPACE_MOUNT,
                        sudo_password: str | None = None) -> str:
    """Return a safely quoted Guest-side 9p mount command.

    OSWorld's stock Guest does not grant passwordless sudo. The optional password
    must come from that DesktopEnv instance's configured client_password and is
    passed only to the short-lived Guest command; callers must not log the command.
    """
    if not tag or not re.fullmatch(r"[A-Za-z0-9_.-]+", tag):
        raise WorkspaceTopologyError("invalid 9p mount tag")
    if not mountpoint.startswith("/") or "\n" in mountpoint:
        raise WorkspaceTopologyError("Guest mountpoint must be an absolute path")
    q_mount = shlex.quote(mountpoint)
    q_tag = shlex.quote(tag)
    mount = (f"mount -t 9p -o trans=virtio,version=9p2000.L,access=any "
             f"{q_tag} {q_mount}")
    if sudo_password is None:
        privileged_mount = f"sudo -n {mount}"
    else:
        if "\n" in sudo_password or "\x00" in sudo_password:
            raise WorkspaceTopologyError("Guest sudo password must be a single line")
        printf_format = "%s" + chr(92) + "n"
        privileged_mount = (f"printf '{printf_format}' {shlex.quote(sudo_password)} | "
                            f"sudo -S -p '' {mount}")
    return (f"mkdir -p {q_mount} && "
            f"if ! mountpoint -q {q_mount}; then "
            f"{privileged_mount}; fi && mountpoint -q {q_mount}")
