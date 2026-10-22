"""Bind the existing Data-to-Deck actor-scoped message tools to this case."""
from __future__ import annotations

import json
from pathlib import Path

from . import CASE_ID


def codex_collaboration_binding(run_root: str | Path, actor: str, collaboration_url: str):
    if actor not in {"A", "B", "S"}:
        raise ValueError(f"unknown actor {actor}")
    root = Path(run_root).resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run ownership mismatch")
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    key = f"CODESK_TLA_{actor}_COLLAB_TOKEN"
    return ({"collaboration": {"actor": actor, "url": collaboration_url, "token_env": key}},
            {key: tokens[actor]})
