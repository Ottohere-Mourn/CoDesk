"""Copy saved role outputs between Guests; never inspect task answers.

Only the two declared deliverables are exposed. Source files and evaluator files
are outside this interface. The lock protects transfer/version bookkeeping, not
GUI input. It does not coordinate the actors' mouse or keyboard actions.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shlex
import threading
import time
import zipfile
from pathlib import Path

from . import spec


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SavedArtifactBridge:
    def __init__(self, root: Path, run_id: str, task_root: str, controllers: dict,
                 guest_ids: dict[str, str], poll_seconds: float = 2,
                 case_id: str = spec.CASE_ID):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.run_id, self.task_root = run_id, task_root
        self.controllers, self.guest_ids = controllers, guest_ids
        self.poll_seconds = poll_seconds
        self.current: dict[str, dict] = {}
        self.peer_hashes: dict[str, str] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self.errors: list[str] = []
        (self.root / "ownership.json").write_text(json.dumps({
            "run_id": run_id, "case_id": case_id,
            "outputs": spec.OUTPUTS, "writer_roles": {p: r for r, p in spec.OUTPUTS.items()},
            "guest_ids": guest_ids, "root": str(self.root.resolve()),
            "scope": "saved-file publication ownership; GUI role discipline is separate",
        }, indent=2) + "\n")

    def _record(self, **event):
        with (self.root / "events.jsonl").open("a") as stream:
            stream.write(json.dumps({"run_id": self.run_id, "time": time.time(), **event}) + "\n")

    def _read(self, role: str, path: str) -> bytes:
        data = self.controllers[role].get_file(path)
        if not data:
            raise RuntimeError(f"no saved artifact returned by Guest {self.guest_ids[role]}")
        return data

    def _write(self, role: str, path: str, data: bytes):
        # A same-directory rename avoids exposing a half-written zip container.
        temporary = path + ".codesk-sync"
        encoded = base64.b64encode(data).decode("ascii")
        script = ("set -e\numask 022\n"
                  f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(temporary)}\n"
                  f"mv -f -- {shlex.quote(temporary)} {shlex.quote(path)}\n")
        result = self.controllers[role].run_bash_script(script, timeout=30)
        if not isinstance(result, dict) or result.get("status") != "success" or result.get("returncode", 0):
            raise RuntimeError("Guest artifact transfer command failed")
        if digest(self._read(role, path)) != digest(data):
            raise RuntimeError("Guest artifact read-back hash mismatch")

    def publish(self, actor: str) -> dict:
        """Publish only this actor's fixed output; callers cannot select a path."""
        if actor not in self.controllers or actor not in spec.OUTPUTS:
            raise ValueError("no output owned by this actor")
        with self._lock:
            started = time.time()
            path = f"{self.task_root}/{spec.OUTPUTS[actor]}"
            data = self._read(actor, path)
            # Read twice and check ZIP CRCs before transferring a GUI save.
            if self._read(actor, path) != data:
                raise RuntimeError("artifact changed during save; retry after saving completes")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("saved artifact has an invalid ZIP checksum")
                expected = ("application/vnd.oasis.opendocument.spreadsheet" if actor == "A"
                            else "application/vnd.oasis.opendocument.presentation")
                if archive.read("mimetype").decode() != expected:
                    raise RuntimeError("saved artifact is not the role's ODF document type")
            sha = digest(data)
            previous = self.current.get(actor)
            peer = "B" if actor == "A" else "A"
            distinct = self.guest_ids[actor] != self.guest_ids[peer]
            if distinct:
                peer_hash = digest(self._read(peer, path))
                # Never silently overwrite an unexpected peer edit or broken sync.
                allowed = {sha, self.peer_hashes[actor]} if actor in self.peer_hashes else {sha}
                if peer_hash not in allowed:
                    self._record(event="ownership_or_sync_conflict", actor=actor, peer=peer,
                                 peer_sha256=peer_hash, source_sha256=sha)
                    raise RuntimeError("non-owner output changed or prior transfer is inconsistent")
            if not previous or previous["sha256"] != sha:
                revision = 0 if previous is None else previous["revision"] + 1
                local = self.root / actor / f"revision-{revision:06d}{Path(path).suffix}"
                local.parent.mkdir(exist_ok=True)
                with local.open("xb") as stream:
                    stream.write(data)
                self.current[actor] = {"actor": actor, "revision": revision, "sha256": sha,
                                       "bytes": len(data), "guest_path": path,
                                       "delivered": not distinct}
                self._record(event="revision_saved", **self.current[actor],
                             source_guest=self.guest_ids[actor], file=str(local.relative_to(self.root)))
            if distinct and peer_hash != sha:
                self._write(peer, path, data)
                self._record(event="transfer_verified", **{**self.current[actor], "delivered": True},
                             destination_guest=self.guest_ids[peer], elapsed_s=time.time() - started)
            self.peer_hashes[actor] = sha
            self.current[actor]["delivered"] = True
            # current.json is audit metadata only, never mounted in either Guest.
            temp = self.root / "current.tmp"
            temp.write_text(json.dumps(self.current, indent=2) + "\n")
            temp.replace(self.root / "current.json")
            return dict(self.current[actor])

    def snapshot(self) -> dict:
        with self._lock:
            return {role: dict(value) for role, value in self.current.items()}

    def sync(self):
        for role in ("A", "B"):
            self.publish(role)

    def start(self):
        self.sync()  # initial peer copies must already be byte-identical
        def loop():
            while not self._stop.wait(self.poll_seconds):
                try:
                    self.sync()
                except Exception as exc:
                    # Preserve failures; callers decide validity after final flush.
                    with self._lock:
                        self.errors.append(f"{type(exc).__name__}: {exc}")
                        self._record(event="sync_error", error=self.errors[-1])
        self._thread = threading.Thread(target=loop, name="saved-artifact-bridge", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=130)
            if self._thread.is_alive():
                raise RuntimeError("workspace bridge did not stop; preserve Guests for inspection")
        self.sync()
