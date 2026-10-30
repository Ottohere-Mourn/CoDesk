"""Episode setup and final-state evaluation for Case 4 Lite."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from pathlib import Path

from . import spec
from .oracle import evaluate, project_state, sha256

TEMPLATE = Path(__file__).resolve().parent / "template" / "workspace"


def _write_json(path: Path, value: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(temporary, path)
    path.chmod(mode)


def prepare_run(run_root: str | Path, run_id: str) -> dict:
    root = Path(run_root).resolve()
    if root.exists() and (root.is_symlink() or any(root.iterdir())):
        raise FileExistsError(f"run root must be fresh: {root}")
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    shutil.copytree(TEMPLATE, workspace)
    state = project_state(workspace / spec.PROJECT)
    if state["tracks"]["playlist4"][1] != {
        "asset": "clip_04.mp4", "position": 75, "source_in": 0, "duration": 100}:
        raise RuntimeError("native starter project no longer contains the fixed outtake")
    if state["tracks"]["playlist6"] != [
        {"asset": "clip_02.mp4", "position": 275, "source_in": 0, "duration": 100}]:
        raise RuntimeError("native starter project no longer contains the staged WASH candidate")
    hashes = {p.relative_to(workspace).as_posix(): sha256(p)
              for p in sorted(workspace.rglob("*")) if p.is_file()}
    baseline = {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
                "run_id": run_id, "initial_hashes": hashes,
                "initial_project_state": state}
    _write_json(root / "oracle" / "baseline_manifest.json", baseline)
    tokens = {role: secrets.token_urlsafe(32) for role in ("A", "B")}
    _write_json(root / "secrets" / "collaboration_tokens.json", tokens)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    for role, instruction in (("A", spec.ACTOR_A_INSTRUCTION),
                              ("B", spec.ACTOR_B_INSTRUCTION)):
        target = root / "instructions" / f"actor_{role}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(instruction + "\n")
    (root / "case_brief.md").write_text(spec.PUBLIC_BRIEF)
    ownership = {"schema_version": 1, "case_id": spec.CASE_ID,
                 "case_version": spec.CASE_VERSION, "run_id": run_id,
                 "run_root": str(root), "created_epoch": time.time(),
                 "owner_user": os.environ.get("USER", "unknown")}
    _write_json(root / "ownership.json", ownership)
    return {"run_id": run_id, "workspace": str(workspace),
            "initial_project_sha256": hashes[spec.PROJECT]}


def _owned(root: Path) -> dict:
    ownership = json.loads((root / "ownership.json").read_text())
    if ownership["case_id"] != spec.CASE_ID or ownership["run_root"] != str(root) or \
       ownership["run_id"] != root.name:
        raise PermissionError("case/run ownership mismatch")
    return ownership


def configure_run(run_root: str | Path, condition: str) -> dict:
    root = Path(run_root).resolve()
    _owned(root)
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text())
    config = {"case_id": spec.CASE_ID, "case_version": spec.CASE_VERSION,
              "run_id": root.name, "condition": condition,
              "desktop_count": 2 if condition == "collaborative_isolated" else 1,
              "same_fixture_sha256": baseline["initial_hashes"],
              "project_path": spec.PROJECT,
              "per_actor_desktop_call_budget": spec.PAIR_MAX_STEPS,
              "application": "Kdenlive 21.12.3 (native saved project)",
              "message_protocol": "Data-to-Deck ProtocolStore"}
    target = root / "run_config.json"
    if target.exists():
        raise FileExistsError(target)
    _write_json(target, config, 0o644)
    return config


def evaluate_run(run_root: str | Path) -> dict:
    root = Path(run_root).resolve()
    _owned(root)
    config = json.loads((root / "run_config.json").read_text())
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text())
    events_path = root / "collaboration" / "events.jsonl"
    events = [json.loads(row) for row in events_path.read_text().splitlines() if row.strip()] \
        if events_path.exists() else []
    result = evaluate(root / "workspace", baseline["initial_hashes"], events,
                      require_collaboration=True)
    result.update({"case_id": spec.CASE_ID, "run_id": root.name,
                   "condition": config["condition"],
                   "message_event_count": sum(e.get("type") == "message" for e in events)})
    target = root / "oracle_result.json"
    if target.exists():
        raise FileExistsError(target)
    _write_json(target, result, 0o644)
    return result
