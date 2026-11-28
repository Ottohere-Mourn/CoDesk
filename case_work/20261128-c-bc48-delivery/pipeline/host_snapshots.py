"""Read-only, allowlisted post-episode Guest state collection.

The production adapter supplies a trusted read callback backed by the
hypervisor/Guest transport.  This module never runs a Guest shell command and
never gives collected state back to an actor.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable


@dataclass(frozen=True)
class SnapshotItem:
    guest_path: str
    archive_path: str
    kind: str  # service_receipt, database, state_snapshot, deliverable, fixture


def validate_snapshot_items(items: Iterable[SnapshotItem]) -> list[SnapshotItem]:
    result: list[SnapshotItem] = []
    seen_guest: set[str] = set()
    seen_archive: set[str] = set()
    for item in items:
        guest = PurePosixPath(item.guest_path)
        archive = PurePosixPath(item.archive_path)
        if not guest.is_absolute() or ".." in guest.parts:
            raise ValueError("Guest snapshot path must be absolute and traversal-free")
        if item.kind not in {"service_receipt", "database", "state_snapshot", "deliverable", "fixture"}:
            raise ValueError("unsupported snapshot kind")
        expected_root = {"deliverable": "guest-output", "fixture": "guest-inputs"}.get(item.kind, "host-snapshots")
        if not archive.is_relative_to(PurePosixPath(expected_root)) or ".." in archive.parts:
            raise ValueError(f"{item.kind} archive path must stay under {expected_root}/")
        if item.guest_path in seen_guest or item.archive_path in seen_archive:
            raise ValueError("duplicate snapshot path")
        seen_guest.add(item.guest_path)
        seen_archive.add(item.archive_path)
        result.append(item)
    return result


def collect_completed_episode_snapshots(
    *, episode_state: str,
    items: Iterable[SnapshotItem],
    destination_root: str | Path,
    read_guest_file: Callable[[str], bytes],
) -> dict:
    """Copy only predeclared files from a completed Guest into a host archive.

    `read_guest_file` is an adapter callback; it must be a read operation from
    the hypervisor boundary, not an Agent-visible `guest_cli` invocation.
    """
    if episode_state != "completed":
        raise ValueError("host snapshots may only be collected after episode completion")
    normalized = validate_snapshot_items(items)
    root = Path(destination_root).resolve()
    files = []
    missing_deliverables = []
    for item in normalized:
        try:
            payload = read_guest_file(item.guest_path)
        except FileNotFoundError:
            if item.kind != "deliverable":
                raise
            missing_deliverables.append({
                "guest_path": item.guest_path,
                "archive_path": item.archive_path,
                "kind": item.kind,
                "missing": True,
            })
            continue
        if not isinstance(payload, bytes):
            raise TypeError("read_guest_file must return bytes")
        target = (root / Path(*PurePosixPath(item.archive_path).parts)).resolve()
        if not target.is_relative_to(root):
            raise ValueError("snapshot destination escaped archive root")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        files.append({
            "guest_path": item.guest_path,
            "archive_path": item.archive_path,
            "kind": item.kind,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    receipt = {
        "schema_version": "paragui.host-snapshot-receipt/v1",
        "collection": "read-only-post-episode",
        "actor_visible": False,
        "files": files,
        "missing_deliverables": missing_deliverables,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "snapshot-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def merge_directory_snapshot_items(static_items, directories, captured_items):
    """Validate dynamic pre-teardown entries against declared directory allowlists."""
    items = validate_snapshot_items(static_items)
    specs = validate_snapshot_items([SnapshotItem(**row) for row in directories])
    if any(x.kind != "deliverable" for x in specs):
        raise ValueError("Directory collection is restricted to task deliverables")
    guests = {x.guest_path for x in items}
    archives = {x.archive_path for x in items}
    for row in captured_items:
        item = SnapshotItem(**{k: row[k] for k in ("guest_path", "archive_path", "kind")})
        validate_snapshot_items([item])
        valid = False
        for spec in specs:
            try:
                rel = PurePosixPath(item.guest_path).relative_to(spec.guest_path)
            except ValueError:
                continue
            if rel.parts and item.archive_path == str(PurePosixPath(spec.archive_path) / rel) and item.kind == spec.kind:
                valid = True
        if not valid:
            raise ValueError("Captured directory item escaped declared allowlist")
        if item.guest_path in guests:
            continue  # explicit legacy archive aliases take precedence
        if item.archive_path in archives:
            raise ValueError("Directory snapshot archive collision")
        items.append(item); guests.add(item.guest_path); archives.add(item.archive_path)
    return validate_snapshot_items(items)
