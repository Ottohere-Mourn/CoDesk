"""Path-level blind-role staging and post-run audit for Shared Guests.

This deliberately does not claim Docker/UID isolation. Both Codex actors use
the same Guest and can technically reach either path; the evaluator detects
explicit cross-role path references in the recorded GUI/CLI action logs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PRIVATE_ROOT = "/home/user/workspace/private"
_PRIVATE_REF = re.compile(r"(?<![A-Za-z0-9_.-])(?:/home/user/workspace/)?private/actor_([ab])(?:/[^\s\"'<>;,)]*)?", re.I)


def actor_private_path(actor: str) -> str:
    role = actor.lower()
    if role not in {"actor_a", "actor_b"}:
        raise ValueError("actor must be actor_a or actor_b")
    return f"{PRIVATE_ROOT}/{role}"


def path_reference_audit(*, actor: str, action_files: Iterable[str | Path]) -> dict[str, Any]:
    """Find explicit attempts to address the other role's private path.

    Audit scope is action-log text/arguments only. It is not a filesystem ACL
    and cannot detect access through an alias, generic parent enumeration, or
    an unlogged side channel; those limits are surfaced in the receipt.
    """
    role = actor.lower()
    if role not in {"actor_a", "actor_b"}:
        raise ValueError("actor must be actor_a or actor_b")
    own = "a" if role == "actor_a" else "b"
    other = "b" if own == "a" else "a"
    references: list[dict[str, Any]] = []
    errors: list[str] = []
    total_rows = 0

    def scan_value(value: Any, location: str, line_number: int) -> None:
        if isinstance(value, str):
            for match in _PRIVATE_REF.finditer(value.replace("~", "/home/user")):
                target = match.group(1).lower()
                references.append({
                    "line": line_number, "field": location,
                    "target": f"actor_{target}", "cross_role": target == other,
                    "reference": match.group(0)[:200],
                })
        elif isinstance(value, dict):
            for key, child in value.items():
                scan_value(child, f"{location}.{key}", line_number)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan_value(child, f"{location}[{index}]", line_number)

    for raw_path in action_files:
        path = Path(raw_path)
        if not path.is_file():
            errors.append(f"missing_action_log:{path.name}")
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            total_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"invalid_jsonl:{path.name}:{line_number}")
                continue
            scan_value(row, "row", line_number)

    cross = [row for row in references if row["cross_role"]]
    own_only = all(row["target"] == role for row in references)
    return {
        "schema_version": "paragui.blind-path-audit/v1",
        "actor": role,
        "checked_action_rows": total_rows,
        "explicit_private_path_references": references,
        "cross_role_references": cross,
        "errors": errors,
        "pass": bool(total_rows > 0 and not errors and not cross and own_only),
        "audit_scope": "explicit path references in recorded action-log arguments/text",
        "physical_isolation": False,
        "limitations": [
            "The shared Guest CLI can technically read either role path.",
            "This audit cannot detect aliases, generic parent-directory enumeration, or unlogged access.",
        ],
    }


def merge_path_audits(audits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {"actor_a", "actor_b"}
    if set(audits) != required:
        raise ValueError("both actor path audits are required")
    return {
        "schema_version": "paragui.blind-path-audit/v1",
        "physical_isolation": False,
        "actors": audits,
        "pass": all(audits[key].get("pass") is True for key in sorted(required)),
        "audit_scope": "explicit path references in recorded action-log arguments/text",
    }
