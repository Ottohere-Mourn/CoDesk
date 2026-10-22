"""Run-scoped provenance, GUI event logging, and artifact collection."""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Protocol


class ArtifactSource(Protocol):
    """Adapter boundary for copying an artifact from a Guest to the host."""
    def copy_from_guest(self, guest_id: str, guest_path: str, local_path: Path) -> None: ...


class RunLedger:
    def __init__(self, run_root: str | Path, metadata: dict[str, object]):
        self.root = Path(run_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.metadata = dict(metadata)
        self.metadata.setdefault("started_at", time.time())
        self.metadata_path = self.root / "provenance.json"
        if self.metadata_path.exists():
            raise FileExistsError(f"run provenance already exists: {self.metadata_path}")
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.events_path = self.root / "gui_events.jsonl"
        self._lock = threading.Lock()

    def record(self, actor: str, event_type: str, *, guest_id: str,
               window_id: str | None = None, window_title: str | None = None,
               details: dict[str, object] | None = None) -> None:
        if actor not in {"A", "B", "S", "system"}:
            raise ValueError("unknown event source")
        if event_type not in {"observe", "action_start", "action_end", "window_change", "focus_change", "yield", "resume", "save", "reset"}:
            raise ValueError("unsupported event type")
        event = {"run_id": self.metadata["run_id"], "timestamp": time.time(), "actor": actor,
                 "event_type": event_type, "guest_id": guest_id, "window_id": window_id,
                 "window_title": window_title, "details": details or {}}
        with self._lock, self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def collect_artifacts(run_root: str | Path, artifacts: list[dict[str, str]],
                      source: ArtifactSource | None = None) -> dict[str, object]:
    """Collect declared outputs only; reject path traversal and emit checksums."""
    root = Path(run_root).resolve()
    out_root = (root / "artifacts").resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "artifact_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"artifact manifest already exists: {manifest_path}")
    collected = []
    for item in artifacts:
        rel = PurePosixPath(item["local_path"])
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError(f"artifact output path must be relative: {rel}")
        dst = (out_root / Path(*rel.parts)).resolve()
        if out_root not in dst.parents:
            raise ValueError("artifact path escapes run artifact directory")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise FileExistsError(f"artifact already collected: {dst}")
        if "source_path" in item:
            src = Path(item["source_path"]).resolve()
            if not src.is_file():
                raise FileNotFoundError(src)
            shutil.copy2(src, dst)
        elif "guest_id" in item and "guest_path" in item and source is not None:
            source.copy_from_guest(item["guest_id"], item["guest_path"], dst)
        else:
            raise ValueError("artifact must declare a local source or a Guest source adapter")
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        collected.append({"actor": item["actor"], "path": str(dst.relative_to(root)),
                          "bytes": dst.stat().st_size, "sha256": digest})
    manifest = {"artifacts": collected, "collected_at": time.time()}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
