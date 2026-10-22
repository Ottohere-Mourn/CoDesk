"""Episode-scoped single-writer ODS revision store with compare-and-swap."""
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
from .fixtures import is_real_ods


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
    path.chmod(0o600)


class WorkbookStore:
    """Append-only ODS revisions and one exclusive editor lease per episode.

    A checkout is a genuine `.ods` file for Calc. A successful commit creates
    an immutable revision and advances the current pointer atomically. Reset
    appends the original fixture as a new revision rather than deleting history.
    """

    def __init__(self, root: str | Path, run_id: str):
        input_root = Path(root)
        if input_root.is_symlink():
            raise PermissionError("workbook store path must not be a symlink")
        self.root = input_root.resolve()
        self.run_id = run_id
        ledger = self.root / "ownership.json"
        if not ledger.is_file() or ledger.is_symlink():
            raise PermissionError("missing workbook-store ownership ledger")
        data = json.loads(ledger.read_text(encoding="utf-8"))
        if (data.get("case_id") != CASE_ID or data.get("run_id") != run_id
                or Path(data.get("root", "")).resolve() != self.root):
            raise PermissionError("workbook store ownership mismatch")

    @classmethod
    def initialize(cls, root: str | Path, run_id: str, initial_ods: str | Path) -> "WorkbookStore":
        source_input = Path(initial_ods)
        if source_input.is_symlink() or not source_input.is_file() or not is_real_ods(source_input):
            raise ValueError("initial workbook must be a real, non-symlinked ODS")
        root_path = Path(root)
        if root_path.exists() and (root_path.is_symlink() or not root_path.is_dir() or any(root_path.iterdir())):
            raise FileExistsError(f"workbook store must be a new/empty directory: {root_path}")
        root_path.mkdir(parents=True, exist_ok=True)
        revisions = root_path / "revisions"
        revisions.mkdir()
        initial = revisions / "revision-000000.ods"
        shutil.copy2(source_input, initial)
        digest = _hash(initial)
        _write_json(root_path / "ownership.json", {
            "case_id": CASE_ID, "run_id": run_id, "root": str(root_path.resolve()),
            "artifact_kind": "odf_spreadsheet", "initial_sha256": digest,
            "created_at_epoch": time.time(),
            "cleanup_policy": "retain revisions and event history; reset only by appending the initial revision",
        })
        _write_json(root_path / "current.json", {"revision": 0, "sha256": digest,
                                                    "artifact": "revisions/revision-000000.ods"})
        (root_path / "events.jsonl").touch(mode=0o600)
        return cls(root_path, run_id)

    def _record(self, event: dict[str, Any]) -> None:
        row = {"case_id": CASE_ID, "run_id": self.run_id, "timestamp_epoch": time.time(), **event}
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def _current(self) -> dict[str, Any]:
        data = json.loads((self.root / "current.json").read_text(encoding="utf-8"))
        artifact_input = self.root / data["artifact"]
        artifact = artifact_input.resolve()
        if (artifact_input.is_symlink() or artifact.parent != (self.root / "revisions").resolve()
                or not artifact.is_file() or _hash(artifact) != data.get("sha256") or not is_real_ods(artifact)):
            raise RuntimeError("current workbook pointer/hash/container is invalid")
        return {**data, "path": str(artifact)}

    def current(self) -> dict[str, Any]:
        return self._current()

    def acquire(self, actor_id: str, desktop_session_id: str) -> dict[str, Any]:
        if actor_id not in {"A", "B", "S"} or not desktop_session_id:
            raise ValueError("invalid actor or desktop session")
        current = self._current()
        token = uuid.uuid4().hex
        lease = {"run_id": self.run_id, "actor_id": actor_id, "desktop_session_id": desktop_session_id,
                 "token": token, "base_revision": current["revision"], "base_sha256": current["sha256"],
                 "created_at_epoch": time.time()}
        lease_path = self.root / "write_lease.json"
        try:
            fd = os.open(lease_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("another actor holds the workbook write lease") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(lease, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        checkout_dir = self.root / "checkouts" / token
        checkout_dir.mkdir(parents=True, exist_ok=False)
        checkout = checkout_dir / f"{actor_id}.ods"
        shutil.copy2(current["path"], checkout)
        self._record({"event": "lease_acquired", "actor_id": actor_id,
                      "desktop_session_id": desktop_session_id, "base_revision": current["revision"],
                      "base_sha256": current["sha256"]})
        return {**lease, "checkout_path": str(checkout), "sha256": current["sha256"]}

    def _lease(self, token: str) -> dict[str, Any]:
        path = self.root / "write_lease.json"
        if not path.is_file() or path.is_symlink():
            raise PermissionError("no active workbook write lease")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("run_id") != self.run_id or data.get("token") != token:
            raise PermissionError("lease token/run mismatch")
        return data

    def commit(self, token: str, candidate: str | Path) -> dict[str, Any]:
        lease = self._lease(token)
        input_path = Path(candidate)
        if input_path.is_symlink() or not input_path.is_file() or not is_real_ods(input_path):
            raise ValueError("candidate must be a real non-symlinked ODS workbook")
        current = self._current()
        if (current["revision"] != lease["base_revision"] or current["sha256"] != lease["base_sha256"]):
            raise RuntimeError("stale workbook revision; acquire a fresh lease and merge before committing")
        revision = int(current["revision"]) + 1
        target = self.root / "revisions" / f"revision-{revision:06d}.ods"
        if target.exists():
            raise FileExistsError(f"preserving existing revision: {target}")
        temp = target.with_name(target.name + f".{uuid.uuid4().hex}.tmp")
        shutil.copy2(input_path, temp)
        digest = _hash(temp)
        os.replace(temp, target)
        _write_json(self.root / "current.json", {"revision": revision, "sha256": digest,
                                                     "artifact": f"revisions/{target.name}"})
        self._record({"event": "commit", "actor_id": lease["actor_id"],
                      "desktop_session_id": lease["desktop_session_id"],
                      "base_revision": lease["base_revision"], "new_revision": revision,
                      "base_sha256": lease["base_sha256"], "sha256": digest})
        (self.root / "write_lease.json").unlink()
        return {"revision": revision, "sha256": digest, "path": str(target), "actor_id": lease["actor_id"]}

    def abandon(self, token: str) -> None:
        lease = self._lease(token)
        self._record({"event": "abandon", "actor_id": lease["actor_id"],
                      "desktop_session_id": lease["desktop_session_id"],
                      "base_revision": lease["base_revision"]})
        (self.root / "write_lease.json").unlink()

    def reset_to_initial(self) -> dict[str, Any]:
        if (self.root / "write_lease.json").exists():
            raise RuntimeError("cannot reset while an actor holds the workbook lease")
        ownership = json.loads((self.root / "ownership.json").read_text(encoding="utf-8"))
        current = self._current()
        revision = int(current["revision"]) + 1
        target = self.root / "revisions" / f"revision-{revision:06d}.ods"
        if target.exists():
            raise FileExistsError(f"preserving existing revision: {target}")
        source = self.root / "revisions" / "revision-000000.ods"
        shutil.copy2(source, target)
        digest = _hash(target)
        if digest != ownership["initial_sha256"]:
            raise RuntimeError("initial fixture hash differs from store ownership ledger")
        _write_json(self.root / "current.json", {"revision": revision, "sha256": digest,
                                                     "artifact": f"revisions/{target.name}"})
        self._record({"event": "reset_to_initial", "actor_id": "S", "new_revision": revision,
                      "sha256": digest, "history_preserved": True})
        return self._current()
