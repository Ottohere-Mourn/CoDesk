"""Reuse the existing run-scoped Data-to-Deck message and attachment service."""
from __future__ import annotations

import json
from pathlib import Path

from . import CASE_ID
from .revision_store import RevisionStore


def codex_collaboration_binding(run_root: str | Path, actor: str, collaboration_url: str):
    if actor not in {"A", "B", "S"}:
        raise ValueError(f"unknown actor {actor}")
    root = Path(run_root).resolve()
    ledger_path = root / "ownership.json"
    if not ledger_path.is_file() or ledger_path.is_symlink():
        raise PermissionError("missing or symlinked ownership ledger")
    ownership = json.loads(ledger_path.read_text(encoding="utf-8"))
    if (ownership.get("case_id") != CASE_ID
            or Path(ownership.get("run_root", "")).resolve() != root):
        raise PermissionError("case/run root ownership mismatch")
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    env_key = f"CODESK_MAR_{actor}_COLLAB_TOKEN"
    binding = {"collaboration": {"actor": actor, "url": collaboration_url,
                                  "token_env": env_key}}
    return binding, {env_key: tokens[actor]}


def acquire_project_lease(run_root: str | Path, actor: str, desktop_session_id: str) -> dict:
    """Return the latest exact revision checkout under the actor's single-writer lease."""
    input_root = Path(run_root)
    if input_root.is_symlink():
        raise PermissionError("run root must not be a symlink")
    root = input_root.resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run root ownership mismatch")
    return RevisionStore(root / "artifact_store", ownership["run_id"]).acquire(actor, desktop_session_id)


def commit_project_revision(run_root: str | Path, actor: str, lease_token: str,
                            candidate_path: str | Path) -> dict:
    input_root = Path(run_root)
    if input_root.is_symlink():
        raise PermissionError("run root must not be a symlink")
    root = input_root.resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run root ownership mismatch")
    store = RevisionStore(root / "artifact_store", ownership["run_id"])
    lease = store._load_lease(lease_token)
    if lease.get("actor_id") != actor:
        raise PermissionError("actor cannot commit another actor's project lease")
    return store.commit(lease_token, candidate_path)
