"""Bindings to the existing OSWorld/Codex and Data-to-Deck collaboration APIs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import spec


def codex_collaboration_binding(run_root: str | Path, actor: str,
                                collaboration_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Return CodexHarness options and the actor-scoped environment for MCP tools.

    This deliberately delegates message storage, attachment validation, HTTP
    protocol, and MCP tool exposure to the existing Data-to-Deck components.
    The returned token must be passed only to the matching actor process.
    """
    if actor not in {"A", "B", "S"}:
        raise ValueError(f"unknown Ticket-to-Resolution actor: {actor}")
    root = Path(run_root).resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != spec.CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("run ownership does not match this case directory")
    tokens_path = root / "secrets" / "collaboration_tokens.json"
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    if actor not in tokens or not tokens[actor]:
        raise PermissionError(f"no collaboration capability token for actor {actor}")
    token_env = f"CODESK_TTR_{actor}_COLLAB_TOKEN"
    return ({"collaboration": {"actor": actor, "url": collaboration_url,
                               "token_env": token_env}},
            {token_env: tokens[actor]})


def condition_actor_ids(condition: str) -> tuple[str, ...]:
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    return ("S",) if condition == "single_agent" else ("A", "B")
