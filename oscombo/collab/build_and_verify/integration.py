"""Actor-scoped reuse of the existing Data-to-Deck/CodexHarness message tools."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import spec


def codex_collaboration_binding(run_root: str | Path, actor: str, collaboration_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    if actor not in {"A", "B", "S"}:
        raise ValueError(f"unknown actor {actor}")
    root = Path(run_root).resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != spec.CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("run ownership mismatch")
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    key = f"CODESK_BV_{actor}_COLLAB_TOKEN"
    return ({"collaboration": {"actor": actor, "url": collaboration_url, "token_env": key}}, {key: tokens[actor]})


def actor_ids(condition: str) -> tuple[str, ...]:
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition {condition}")
    return ("S",) if condition == "single_agent" else ("A", "B")
