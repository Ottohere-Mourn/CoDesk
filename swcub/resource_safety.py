"""Fail-closed ownership labels, append-only resource ledger, and safe Docker removal."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from typing import Any, Callable


PROJECT_NAME = "shared-workspace-benchmark-v0"
PROJECT_LABEL = "org.swcub.project"
RUN_LABEL = "org.swcub.run-id"
OWNER_LABEL = "org.swcub.owner-token"
FULL_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ResourceIdentity:
    run_id: str
    owner_token: str
    ledger_path: Path

    @property
    def labels(self) -> dict[str, str]:
        return {PROJECT_LABEL: PROJECT_NAME,
                RUN_LABEL: self.run_id,
                OWNER_LABEL: self.owner_token}


class ResourceLedger:
    """Append-only JSONL record for one experiment run."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, resource_type: str, resource_id: str,
               identity: ResourceIdentity, **details: Any) -> None:
        row = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
               "event": event, "resource_type": resource_type,
               "resource_id": resource_id, "project": PROJECT_NAME,
               "run_id": identity.run_id, "labels": identity.labels,
               **details}
        data = (json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def created_container(self, container_id: str, identity: ResourceIdentity,
                          *, name: str, image: str) -> None:
        self.record("created", "container", container_id, identity,
                    name=name, image=image)

    def has_created_container(self, container_id: str,
                              identity: ResourceIdentity) -> bool:
        if not self.path.is_file():
            return False
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("event") == "created" and row.get("resource_type") == "container"
                    and row.get("resource_id") == container_id
                    and row.get("labels") == identity.labels):
                return True
        return False

    def has_started_run(self, identity: ResourceIdentity) -> bool:
        if not self.path.is_file():
            return False
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("event") == "run_started" and row.get("resource_type") == "run"
                    and row.get("resource_id") == identity.run_id
                    and row.get("run_id") == identity.run_id
                    and row.get("labels") == identity.labels):
                return True
        return False

    def has_created_resource(self, resource_type: str, resource_id: str,
                             identity: ResourceIdentity) -> bool:
        if not self.path.is_file():
            return False
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("event") == "created" and row.get("resource_type") == resource_type
                    and row.get("resource_id") == resource_id
                    and row.get("labels") == identity.labels):
                return True
        return False

    def record_created_resource(self, resource_type: str, resource_id: str,
                                identity: ResourceIdentity, **details: Any) -> None:
        self.record("created", resource_type, resource_id, identity, **details)

    def record_destroyed_resource(self, resource_type: str, resource_id: str,
                                  identity: ResourceIdentity, **details: Any) -> None:
        self.record("destroy_requested", resource_type, resource_id, identity, **details)
        self.record("destroyed", resource_type, resource_id, identity, **details)

    @staticmethod
    def record_from_rows(path: str | Path, container_id: str) -> dict[str, Any] | None:
        ledger_path = Path(path).expanduser().resolve()
        if not ledger_path.is_file():
            return None
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("event") == "created" and row.get("resource_type") == "container"
                    and row.get("resource_id") == container_id):
                return row
        return None


def ensure_resource_identity(default_ledger: str | Path | None = None) -> ResourceIdentity:
    """Use caller-provided per-run identity or create one; reject partial identity."""
    run_id = os.environ.get("SWCUB_RUN_ID")
    owner_token = os.environ.get("SWCUB_OWNER_TOKEN")
    ledger_path = os.environ.get("SWCUB_RESOURCE_LEDGER")
    provided = (bool(run_id), bool(owner_token), bool(ledger_path))
    if any(provided) and not all(provided):
        raise RuntimeError("SWCUB_RUN_ID, SWCUB_OWNER_TOKEN, and SWCUB_RESOURCE_LEDGER must be set together")
    if not all(provided):
        run_id = secrets.token_hex(16)
        owner_token = secrets.token_hex(32)
        base = Path(default_ledger) if default_ledger else Path("/tmp/swcub-resource-ledgers") / f"{run_id}.jsonl"
        ledger_path = str(base)
        os.environ.update({"SWCUB_RUN_ID": run_id,
                           "SWCUB_OWNER_TOKEN": owner_token,
                           "SWCUB_RESOURCE_LEDGER": ledger_path})
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", str(run_id)):
        raise RuntimeError("SWCUB_RUN_ID must be 8-128 safe ASCII characters")
    if not re.fullmatch(r"[A-Za-z0-9._-]{32,128}", str(owner_token)):
        raise RuntimeError("SWCUB_OWNER_TOKEN must be a unique token of at least 32 safe characters")
    identity = ResourceIdentity(str(run_id), str(owner_token), Path(str(ledger_path)))
    initialized = json.dumps([identity.run_id, identity.owner_token,
                              str(identity.ledger_path.resolve())])
    if os.environ.get("SWCUB_RESOURCE_IDENTITY_INITIALIZED") != initialized:
        ResourceLedger(identity.ledger_path).record("run_started", "run", identity.run_id,
                                                    identity, pid=os.getpid())
        os.environ["SWCUB_RESOURCE_IDENTITY_INITIALIZED"] = initialized
    return identity


def verify_container_identity(container_id: str, inspected: dict[str, Any],
                              identity: ResourceIdentity) -> None:
    """Raise unless an inspect payload is the exact full-ID project resource."""
    if not FULL_CONTAINER_ID.fullmatch(container_id):
        raise RuntimeError("refusing container operation without a full 64-character ID")
    if inspected.get("Id") != container_id:
        raise RuntimeError("Docker inspect ID does not exactly match the requested full ID")
    labels = (inspected.get("Config") or {}).get("Labels") or {}
    for key, value in identity.labels.items():
        if labels.get(key) != value:
            raise RuntimeError(f"refusing container operation: ownership label mismatch for {key}")


def verify_ledger_ownership(container_id: str, row: dict[str, Any] | None,
                            identity: ResourceIdentity) -> None:
    if row is None or row.get("resource_id") != container_id:
        raise RuntimeError("container full ID is not recorded as created in this run ledger")
    if row.get("labels") != identity.labels:
        raise RuntimeError("run ledger ownership labels do not match this run")


def remove_verified_container(container: Any, identity: ResourceIdentity,
                              *, reason: str) -> None:
    """Stop/remove only the exact container this run created and labeled."""
    container_id = str(getattr(container, "id", ""))
    ledger = ResourceLedger(identity.ledger_path)
    if not FULL_CONTAINER_ID.fullmatch(container_id):
        raise RuntimeError("refusing cleanup without the exact full container ID")
    if not ledger.has_created_container(container_id, identity):
        raise RuntimeError("refusing cleanup: container is absent from this run's creation ledger")
    container.reload()
    verify_container_identity(container_id, container.attrs, identity)
    ledger.record("destroy_requested", "container", container_id, identity, reason=reason)
    state = container.attrs.get("State") or {}
    if state.get("Running"):
        container.stop(timeout=10)
        container.reload()
        verify_container_identity(container_id, container.attrs, identity)
        if (container.attrs.get("State") or {}).get("Running"):
            raise RuntimeError("container remained running after verified stop request")
    container.remove()  # exact object whose full ID and labels were just verified
    ledger.record("destroyed", "container", container_id, identity, reason=reason)


def cleanup_docker_cli_container(container_id: str, identity: ResourceIdentity,
                                 *, reason: str,
                                 runner: Callable[..., Any] = subprocess.run,
                                 inspect_fn: Callable[[str], dict[str, Any]] | None = None) -> None:
    """CLI counterpart used by the X11 adapter and explicit safe cleanup script."""
    if not FULL_CONTAINER_ID.fullmatch(container_id):
        raise RuntimeError("refusing cleanup without an exact full container ID")
    ledger = ResourceLedger(identity.ledger_path)
    if not ledger.has_created_container(container_id, identity):
        raise RuntimeError("refusing cleanup: container is absent from this run's creation ledger")
    if inspect_fn is None:
        def inspect_fn(target_id: str) -> dict[str, Any]:
            proc = runner(["docker", "inspect", "--type", "container", target_id],
                          check=True, capture_output=True, text=True)
            rows = json.loads(proc.stdout)
            if len(rows) != 1 or not isinstance(rows[0], dict):
                raise RuntimeError("Docker inspect did not return exactly one container")
            return rows[0]
    attrs = inspect_fn(container_id)
    verify_container_identity(container_id, attrs, identity)
    ledger.record("destroy_requested", "container", container_id, identity, reason=reason)
    if (attrs.get("State") or {}).get("Status") == "running":
        runner(["docker", "stop", "--time", "10", container_id],
               check=True, capture_output=True, text=True)
        attrs = inspect_fn(container_id)
        verify_container_identity(container_id, attrs, identity)
        if (attrs.get("State") or {}).get("Status") == "running":
            raise RuntimeError("container remained running after stop")
    attrs = inspect_fn(container_id)
    verify_container_identity(container_id, attrs, identity)
    runner(["docker", "rm", container_id], check=True, capture_output=True, text=True)
    ledger.record("destroyed", "container", container_id, identity, reason=reason)


def verify_owned_directory(path: str | Path, marker: dict[str, Any],
                           identity: ResourceIdentity, resource_id: str) -> None:
    expected = {"project": PROJECT_NAME, "run_id": identity.run_id,
                "owner_token": identity.owner_token, "resource_id": resource_id,
                "path": str(Path(path).resolve())}
    if marker != expected:
        raise RuntimeError("refusing directory cleanup: ownership marker mismatch")
