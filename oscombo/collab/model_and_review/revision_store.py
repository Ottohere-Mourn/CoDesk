"""Small run-scoped, single-writer revision store for Blender project bytes.

The store is local filesystem logic only; it does not mount directories into
Guests or start a service. A future executor can expose these operations over
its existing artifact channel. Generic payload mode exists only for unit
testing the lease/CAS rules and never labels test bytes as a Blender project.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from . import CASE_ID
from .blend_format import has_blend_container_header_at


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    path.chmod(0o600)


class RevisionStore:
    """An append-only revision history with a single active writer lease."""

    def __init__(self, root: str | Path, run_id: str):
        self.root = Path(root).resolve()
        self.run_id = run_id
        ledger = self.root / "ownership.json"
        if not ledger.is_file() or ledger.is_symlink():
            raise PermissionError("missing or symlinked revision-store ownership ledger")
        data = json.loads(ledger.read_text(encoding="utf-8"))
        if (data.get("case_id") != CASE_ID or data.get("run_id") != run_id
                or Path(data.get("root", "")).resolve() != self.root):
            raise PermissionError("revision-store case/run/root mismatch")
        self.kind = data["artifact_kind"]

    @classmethod
    def initialize(cls, root: str | Path, run_id: str, source: str | Path, *,
                   artifact_kind: str = "blender_project") -> "RevisionStore":
        source_input = Path(source).expanduser()
        if source_input.is_symlink():
            raise PermissionError(f"refusing symlinked initial artifact: {source_input}")
        source_path = source_input.resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"initial artifact missing or symlinked: {source_path}")
        if artifact_kind not in {"blender_project", "generic_test_payload"}:
            raise ValueError("unsupported artifact kind")
        if artifact_kind == "blender_project":
            if not has_blend_container_header_at(source_path):
                raise ValueError("initial artifact is not a genuine Blender .blend container")
        store_root = Path(root).absolute()
        if store_root.exists() and (store_root.is_symlink() or not store_root.is_dir() or any(store_root.iterdir())):
            raise FileExistsError(f"revision store must be new/empty and not symlinked: {store_root}")
        store_root.mkdir(parents=True, exist_ok=True)
        revisions = store_root / "revisions"
        revisions.mkdir()
        revision_path = revisions / "revision-000000.blob"
        shutil.copy2(source_path, revision_path)
        digest = _digest(revision_path)
        ownership = {"case_id": CASE_ID, "run_id": run_id, "root": str(store_root.resolve()),
                     "artifact_kind": artifact_kind, "created_at_epoch": time.time(),
                     "cleanup_policy": "preserve revisions; reset only with parent episode ownership check"}
        _atomic_json(store_root / "ownership.json", ownership)
        _atomic_json(store_root / "current.json", {"revision": 0, "sha256": digest,
                                                       "artifact": "revisions/revision-000000.blob"})
        (store_root / "events.jsonl").touch(mode=0o600)
        return cls(store_root, run_id)

    def _current_data(self) -> dict[str, Any]:
        data = json.loads((self.root / "current.json").read_text(encoding="utf-8"))
        artifact_input = self.root / data["artifact"]
        if artifact_input.is_symlink():
            raise PermissionError("current revision must not be a symlink")
        artifact = artifact_input.resolve()
        if artifact.parent != (self.root / "revisions").resolve() or not artifact.is_file():
            raise PermissionError("current revision path escapes the owned revision directory")
        if _digest(artifact) != data.get("sha256"):
            raise RuntimeError("current revision content hash mismatch")
        return data

    def current(self) -> dict[str, Any]:
        data = self._current_data()
        return {**data, "path": str((self.root / data["artifact"]).resolve()),
                "artifact_kind": self.kind}

    def _load_lease(self, token: str) -> dict[str, Any]:
        path = self.root / "write_lease.json"
        if not path.is_file() or path.is_symlink():
            raise PermissionError("no active write lease")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("token") != token or data.get("run_id") != self.run_id:
            raise PermissionError("write lease token/run mismatch")
        return data

    def acquire(self, actor_id: str, desktop_session_id: str) -> dict[str, Any]:
        if actor_id not in {"A", "B", "S"} or not desktop_session_id:
            raise ValueError("invalid actor or desktop session")
        current = self._current_data()
        token = uuid.uuid4().hex
        lease = {"case_id": CASE_ID, "run_id": self.run_id, "actor_id": actor_id,
                 "desktop_session_id": desktop_session_id, "token": token,
                 "base_revision": current["revision"], "base_sha256": current["sha256"],
                 "created_at_epoch": time.time()}
        path = self.root / "write_lease.json"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("another actor holds the canonical artifact write lease") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(lease, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._record({"event": "lease_acquired", "actor_id": actor_id,
                      "desktop_session_id": desktop_session_id,
                      "base_revision": current["revision"], "base_sha256": current["sha256"]})
        return {**lease, "revision": current["revision"], "sha256": current["sha256"],
                "checkout_path": str(self.checkout(token))}

    def checkout(self, token: str) -> Path:
        lease = self._load_lease(token)
        current = self._current_data()
        if current["revision"] != lease["base_revision"] or current["sha256"] != lease["base_sha256"]:
            raise RuntimeError("lease base revision is stale; acquire a fresh lease")
        directory = self.root / "checkouts" / token
        directory.mkdir(parents=True, exist_ok=False)
        suffix = ".blend" if self.kind == "blender_project" else ".payload"
        destination = directory / f"{lease['actor_id']}{suffix}"
        shutil.copy2(self.root / current["artifact"], destination)
        if _digest(destination) != current["sha256"]:
            raise RuntimeError("checkout copy hash differs from canonical revision")
        return destination

    def commit(self, token: str, candidate: str | Path) -> dict[str, Any]:
        lease = self._load_lease(token)
        source_input = Path(candidate).expanduser()
        if source_input.is_symlink():
            raise PermissionError("candidate artifact must not be a symlink")
        source = source_input.resolve()
        if not source.is_file():
            raise FileNotFoundError("candidate artifact is missing or symlinked")
        if self.kind == "blender_project":
            if not has_blend_container_header_at(source):
                raise ValueError("candidate is not a genuine Blender .blend container")
        current = self._current_data()
        if (current["revision"] != lease["base_revision"]
                or current["sha256"] != lease["base_sha256"]):
            raise RuntimeError("stale write lease; refusing a lost-update overwrite")
        revision = current["revision"] + 1
        target = self.root / "revisions" / f"revision-{revision:06d}.blob"
        if target.exists():
            raise FileExistsError(f"revision already exists; preserving it: {target}")
        temp = target.with_name(target.name + ".tmp")
        shutil.copy2(source, temp)
        digest = _digest(temp)
        os.replace(temp, target)
        new_current = {"revision": revision, "sha256": digest,
                       "artifact": f"revisions/{target.name}"}
        _atomic_json(self.root / "current.json", new_current)
        self._record({"event": "commit", "actor_id": lease["actor_id"],
                      "desktop_session_id": lease["desktop_session_id"],
                      "base_revision": lease["base_revision"], "new_revision": revision,
                      "base_sha256": lease["base_sha256"], "sha256": digest})
        self._release_lease(token)
        return {**new_current, "path": str(target), "actor_id": lease["actor_id"]}

    def abandon(self, token: str) -> None:
        lease = self._load_lease(token)
        self._record({"event": "abandon", "actor_id": lease["actor_id"],
                      "desktop_session_id": lease["desktop_session_id"],
                      "base_revision": lease["base_revision"], "sha256": lease["base_sha256"]})
        self._release_lease(token)

    def _release_lease(self, token: str) -> None:
        path = self.root / "write_lease.json"
        lease = self._load_lease(token)
        if lease.get("token") != token:
            raise PermissionError("refusing to release another actor's lease")
        path.unlink()

    def _record(self, event: dict[str, Any]) -> None:
        row = {"case_id": CASE_ID, "run_id": self.run_id,
               "timestamp_epoch": time.time(), **event}
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
