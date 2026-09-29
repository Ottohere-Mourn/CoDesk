"""Stable, post-episode provenance records for reproducible SWCUB runs."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


EPISODE_METADATA_SCHEMA_VERSION = 1
TASK_SUITE_ID = "SWCUB-V2-SCRIPTED-REAL-GUEST"
TASK_VERSION = "2.0.0"


def source_path_label(path: Path, repo_root: Path,
                      external_roots: Iterable[tuple[str, Path]] = ()) -> str:
    """Return a stable source label for repository and pinned external files."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        pass
    for prefix, root in external_roots:
        try:
            return f"{prefix}/{resolved.relative_to(root.resolve()).as_posix()}"
        except ValueError:
            continue
    return f"external:{resolved}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_info(path: Path) -> dict[str, Any]:
    def git(*args: str) -> str | None:
        result = subprocess.run(["git", "-C", str(path), *args], check=False,
                                capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None

    return {"commit": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain")),
            "dirty_paths": (git("status", "--porcelain") or "").splitlines()}


def stamp_episode_provenance(
    run_dir: Path,
    report: dict[str, Any],
    *,
    repo_root: Path,
    task_id: str,
    task_version: str,
    condition: str,
    seed: int,
    actor_metadata: dict[str, dict[str, str]],
    evaluator_class: str,
    source_files: Iterable[Path],
    osworld_checkout: Path,
    release_manifest: Path,
    guest_image: Path,
    model_metadata: dict[str, Any] | None = None,
    runtime_image: str = "swcub/osworld-v2.1-qemu-runtime:local",
) -> dict[str, Any]:
    """Attach a report summary and content-addressed sidecar after Guest close."""
    run_dir = run_dir.resolve()
    repo_root = repo_root.resolve()
    osworld_checkout = osworld_checkout.resolve()
    release_manifest = release_manifest.resolve()
    guest_image = guest_image.resolve()

    report["task_id"] = task_id
    report["task_version"] = task_version
    report.setdefault("task_instance_id", f"{task_id.lower()}-{report.get('scenario', 'episode')}-seed{seed}")
    report["condition"] = condition

    ledger_path = Path(report.get("resource_ledger", run_dir / "resource-events.jsonl"))
    if not ledger_path.is_absolute():
        ledger_path = (run_dir / ledger_path).resolve()
    guest_id = (report.get("shared_guest_container_id") or report.get("same_guest_container_id"))
    ledger_rows: list[dict[str, Any]] = []
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                ledger_rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    guest_rows = [row for row in ledger_rows
                  if row.get("resource_type") == "container" and row.get("resource_id") == guest_id]
    created = next((row for row in guest_rows if row.get("event") == "created"), None)
    destroyed = next((row for row in guest_rows if row.get("event") == "destroyed"), None)
    if not created or not destroyed:
        raise RuntimeError("cannot stamp provenance: Guest container lacks ledgered create/destroy")
    if not isinstance(guest_id, str) or not re.fullmatch(r"[0-9a-f]{64}", guest_id):
        raise RuntimeError("cannot stamp provenance: report lacks a full immutable Guest ID")
    labels = created.get("labels") or {}
    if (labels.get("org.swcub.project") != "shared-workspace-benchmark-v0"
            or labels.get("org.swcub.run-id") != report.get("resource_run_id")
            or not labels.get("org.swcub.owner-token")
            or destroyed.get("labels") != labels):
        raise RuntimeError("cannot stamp provenance: Guest ownership labels are inconsistent")

    source_hashes: dict[str, str] = {}
    for source in sorted({Path(item).resolve() for item in source_files}):
        if not source.is_file():
            raise FileNotFoundError(f"provenance source does not exist: {source}")
        try:
            name = str(source.relative_to(repo_root))
        except ValueError:
            try:
                name = f"osworld-v2.1/{source.relative_to(osworld_checkout)}"
            except ValueError:
                name = str(source)
        source_hashes[name] = _sha256(source)

    release_data = json.loads(release_manifest.read_text(encoding="utf-8"))
    runtime_inspect = subprocess.run(
        ["docker", "image", "inspect", runtime_image], check=False,
        capture_output=True, text=True, timeout=20)
    runtime_id = None
    if runtime_inspect.returncode == 0:
        try:
            runtime_id = json.loads(runtime_inspect.stdout)[0].get("Id")
        except (json.JSONDecodeError, IndexError, AttributeError):
            runtime_id = None

    metadata = {
        "metadata_schema_version": EPISODE_METADATA_SCHEMA_VERSION,
        "benchmark": {"suite_id": TASK_SUITE_ID, "suite_version": TASK_VERSION},
        "task": {"task_id": task_id, "task_version": task_version,
                 "task_instance_id": report["task_instance_id"],
                 "scenario": report.get("scenario"), "condition": condition,
                 "seed": seed, "schedule": report.get("schedule")},
        "actors": [
            {"actor_id": actor_id,
             "class": actor_metadata.get(actor_id, {}).get("class", "unknown"),
             "role": actor_metadata.get(actor_id, {}).get("role", "unknown")}
            for actor_id in sorted((report.get("actors") or {}).keys())
        ],
        "evaluator": {"class": evaluator_class, "hidden_state_access": "post_episode_only"},
        "environment": {
            "adapter": "OSWorldSharedEpisode", "release": "osworld-v2.1",
            "osworld_checkout_commit": _git_info(osworld_checkout)["commit"],
            "osworld_checkout_dirty": _git_info(osworld_checkout)["dirty"],
            "release_manifest_sha256": _sha256(release_manifest),
            "guest_image_path": str(guest_image),
            "guest_image_size_bytes": guest_image.stat().st_size,
            "guest_archive_sha256": release_data["provider_images"]["docker"]["ubuntu"]["artifact_sha256"],
            "runtime_image": runtime_image, "runtime_image_id": runtime_id,
            "environment_id": report.get("environment_id"),
            "guest_container_id": guest_id,
        },
        "resources": {"run_id": report.get("resource_run_id"),
                       "owner_labels": created.get("labels"),
                       "ledger_path": str(ledger_path), "ledger_sha256": _sha256(ledger_path),
                       "guest_created_and_destroyed": True},
        "source": {"repository_commit": _git_info(repo_root)["commit"],
                   "repository_dirty": _git_info(repo_root)["dirty"],
                   "dirty_paths": _git_info(repo_root)["dirty_paths"],
                   "sha256": source_hashes},
        "host": {"platform": platform.platform(), "python": sys.version.split()[0],
                 "machine": platform.machine()},
        "model": model_metadata,
    }
    report["episode_metadata"] = metadata
    report["provenance_file"] = "provenance.json"
    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    artifact_hashes = {
        str(path.relative_to(run_dir)): _sha256(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name != "provenance.json"
    }
    sidecar = {**metadata, "artifact_sha256": artifact_hashes}
    (run_dir / "provenance.json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata
