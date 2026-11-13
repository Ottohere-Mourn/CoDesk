"""Offline episode preparation, condition plans, evaluation and reset."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from . import CASE_ID, CASE_VERSION, CONDITIONS, spec
from .fixture import TEMPLATE, materialize_template
from .oracle import evaluate_artifacts, tree_hashes


def _write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    path.chmod(mode)


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root).absolute()
    if root.exists() and (root.is_symlink() or any(root.iterdir())):
        raise FileExistsError(f"run root must be new/empty and not a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    materialize_template(workspace)
    initial_hashes = tree_hashes(workspace)
    required = set(spec.PROTECTED_WORKSPACE_FILES)
    if not required.issubset(initial_hashes):
        raise RuntimeError(f"fixture is missing protected files: {sorted(required - set(initial_hashes))}")
    hidden_baseline = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "initial_workspace_hashes": initial_hashes,
        "asset_catalog_sha256": initial_hashes["asset_catalog.json"],
        "gold_asset_ids": sorted(spec.GOLD_BIN_ASSETS),
        "oracle_visibility": "private; do not mount oracle/ or case package source into Actor context",
    }
    _write_json(root / "oracle" / "baseline_manifest.json", hidden_baseline)
    tokens = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "collaboration_tokens.json", tokens)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    instructions = {"A": spec.ACTOR_A_INSTRUCTION, "B": spec.ACTOR_B_INSTRUCTION,
                    "S": spec.SINGLE_AGENT_INSTRUCTION}
    for actor, instruction in instructions.items():
        p = root / "actor_instructions" / f"{actor}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(instruction + "\n", encoding="utf-8")
        p.chmod(0o600)
    ownership = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "run_id": run_id, "owner_user": os.environ.get("USER", "unknown"),
        "created_at_epoch": time.time(), "run_root": str(root.resolve()),
        "resources": [
            {"kind": "mutable_episode_workspace", "path": str(workspace.resolve()), "status": "active"},
            {"kind": "private_oracle_manifest", "path": str((root / "oracle" / "baseline_manifest.json").resolve()), "status": "active"},
            {"kind": "actor_message_protocol", "path": str((root / "collaboration").resolve()), "status": "active"},
            {"kind": "gui_app_state_event_log", "path": str((root / "interaction_events.jsonl").resolve()), "status": "active"},
            {"kind": "actor_tokens", "path": str((root / "secrets" / "collaboration_tokens.json").resolve()), "status": "active"},
        ],
        "cleanup_policy": "Preserve episode artifacts; only reset resources with exact matching case_id, run_id and root.",
    }
    _write_json(root / "ownership.json", ownership)
    _write_json(root / "run_config.template.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": None, "workspace_backend_id": f"{CASE_ID}/{run_id}/workspace",
        "same_project_backend_all_conditions": True,
        "budgets": {"per_actor_steps": 240, "per_actor_tokens": 12000,
                    "status": "exploratory default; requires real-GUI solvability calibration"},
    }, 0o644)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "fixed_fixture_created",
                                                "workspace_tree_sha256": hashlib.sha256(
                                                    json.dumps(initial_hashes, sort_keys=True).encode()).hexdigest(),
                                                "time_epoch": time.time()})
    return {"case_id": CASE_ID, "run_id": run_id, "run_root": str(root),
            "workspace": str(workspace), "initial_workspace_sha256": initial_hashes,
            "ownership": str(root / "ownership.json")}


def make_plan(condition: str, run_id: str, *, kdenlive_project: str | None = None,
              steps_per_actor: int = 240, tokens_per_actor: int = 12000) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if steps_per_actor < 1 or tokens_per_actor < 1:
        raise ValueError("actor budgets must be positive")
    single = condition == "single_agent"
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": condition,
        "actor_ids": ["S"] if single else ["A", "B"],
        "desktop_count": {"single_agent": 1, "collaborative_isolated": 2,
                          "collaborative_shared": 1}[condition],
        "desktop_topology": {"single_agent": "one desktop, one integrated actor",
                             "collaborative_isolated": "two independent desktop sessions",
                             "collaborative_shared": "one live desktop session controlled by A/B"}[condition],
        "workspace_backend_id": f"{CASE_ID}/{run_id}/workspace",
        "workspace_backend_topology": "one canonical episode workspace; same media, starter project, manifest/output paths in all conditions",
        "backend_must_not_change_between_conditions": True,
        "project_writer_role": "B; S in single_agent",
        "asset_manifest_writer_role": "A; S in single_agent",
        "application": "Kdenlive; same project profile and project build in all conditions",
        "project_path": kdenlive_project or "workspace/project/GreenLoop.kdenlive",
        "message_protocol": "existing Data-to-Deck ProtocolStore send/read messages and attachments",
        "message_capabilities_same_all_conditions": True,
        "scoring": "same private parser-based final-state Oracle in all conditions",
        "budget": {"steps_per_actor": steps_per_actor, "tokens_per_actor": tokens_per_actor,
                   "single_agent_total_steps": steps_per_actor * 2 if single else None,
                   "single_agent_total_tokens": tokens_per_actor * 2 if single else None,
                   "calibrated": False},
        "shared_state_of_interest": ["source monitor playhead", "selected project-bin clip",
                                      "active monitor/timeline context", "timeline playhead",
                                      "selected timeline clip", "active track"],
        "runtime_status": "OFFLINE_PLAN_ONLY; Guest mapping and Kdenlive application state not verified",
    }


def _load_owned_run(run_root: str | Path, run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = Path(run_root).resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing or symlinked case ownership ledger")
    data = json.loads(ledger.read_text(encoding="utf-8"))
    if data.get("case_id") != CASE_ID or Path(data.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run root ownership mismatch")
    if run_id is not None and data.get("run_id") != run_id:
        raise PermissionError("requested run_id does not match ownership ledger")
    return root, data


def configure_run(run_root: str | Path, condition: str) -> dict[str, Any]:
    root, ownership = _load_owned_run(run_root)
    target = root / "run_config.json"
    if target.exists():
        raise FileExistsError("preserving existing run_config.json; use a fresh run")
    plan = make_plan(condition, ownership["run_id"])
    plan["initial_workspace_hashes"] = json.loads(
        (root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))["initial_workspace_hashes"]
    _write_json(target, plan)
    return plan


def evaluate_run(run_root: str | Path) -> dict[str, Any]:
    root, ownership = _load_owned_run(run_root)
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure a condition before evaluation")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("run_id") != ownership["run_id"] or config.get("case_id") != CASE_ID:
        raise PermissionError("run config identity mismatch")
    result_path, prov_path = root / "oracle_result.json", root / "provenance.json"
    if result_path.exists() or prov_path.exists():
        raise FileExistsError("preserving existing evaluation; use a fresh run or ownership-checked reset")
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))
    result = evaluate_artifacts(root / "workspace", baseline_hashes=baseline["initial_workspace_hashes"])
    result.update({"run_id": ownership["run_id"], "condition": config["condition"]})
    protocol_events = root / "collaboration" / "events.jsonl"
    message_events = []
    if protocol_events.is_file():
        message_events = [json.loads(row) for row in protocol_events.read_text(encoding="utf-8").splitlines() if row.strip()]
    result["process_metrics"] = {
        "message_event_count": sum(event.get("type") == "message" for event in message_events),
        "attachment_event_count": sum(event.get("type") == "attachment" for event in message_events),
        "substantive_collaboration": "NOT_INFERRED_FROM_MESSAGE_COUNT",
        "scheduled_exposure": "NOT_SCHEDULED_BY_OFFLINE_RUNNER",
        "observed_interference": "NOT_VERIFIED_WITHOUT_REAL_GUI_TRACES",
        "autonomous_recovery": "NOT_VERIFIED_WITHOUT_REAL_GUI_TRACES",
    }
    _write_json(result_path, result)
    provenance = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": ownership["run_id"],
        "condition": config["condition"], "workspace_backend_id": config["workspace_backend_id"],
        "initial_workspace_hashes": baseline["initial_workspace_hashes"],
        "final_workspace_hashes": tree_hashes(root / "workspace"),
        "collaboration_events_sha256": _file_hash(protocol_events) if protocol_events.is_file() else None,
        "interaction_events_sha256": _file_hash(root / "interaction_events.jsonl")
            if (root / "interaction_events.jsonl").is_file() else None,
        "oracle_result_sha256": _file_hash(result_path), "created_at_epoch": time.time(),
        "gui_action_trace": "NOT_PRESENT_OFFLINE", "kdenlive_open_save_roundtrip": "PENDING_GUEST_SMOKE",
    }
    _write_json(prov_path, provenance)
    return result


def reset_owned_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root, ownership = _load_owned_run(run_root, run_id)
    workspace = root / "workspace"
    if workspace.is_symlink() or not workspace.is_dir() or workspace.resolve().parent != root:
        raise PermissionError("refusing reset: workspace is not an owned direct child")
    for name in ("collab_server.lock", "app_server.lock"):
        lock_path = root / name
        if lock_path.is_file():
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if lock.get("run_id") == run_id:
                try:
                    os.kill(int(lock["pid"]), 0)
                except (ProcessLookupError, ValueError, KeyError):
                    pass
                else:
                    raise RuntimeError(f"refusing reset while this run's {name} is active")
    stamp = str(time.time_ns())
    archive = root / "pre_reset" / stamp
    archive.mkdir(parents=True, exist_ok=False)
    shutil.copytree(workspace, archive / "workspace")
    for name in ("collaboration", "interaction_events.jsonl", "oracle_result.json", "provenance.json"):
        path = root / name
        if path.is_dir():
            shutil.copytree(path, archive / name)
        elif path.is_file():
            shutil.copy2(path, archive / name)
    shutil.rmtree(workspace)
    materialize_template(workspace)
    collab_dir = root / "collaboration"
    if collab_dir.exists():
        shutil.rmtree(collab_dir)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(collab_dir, run_id)
    event_path = root / "interaction_events.jsonl"
    event_path.write_text("", encoding="utf-8")
    event_path.chmod(0o600)
    for name in ("oracle_result.json", "provenance.json", "run_config.json"):
        (root / name).unlink(missing_ok=True)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "reset_verified",
                                                "archive": str(archive), "time_epoch": time.time()})
    ownership.setdefault("resources", []).append({"kind": "preserved_pre_reset_snapshot",
                                                     "path": str(archive.resolve()), "status": "preserved"})
    _write_json(root / "ownership.json", ownership)
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))
    hashes = tree_hashes(workspace)
    return {"status": "RESET_VERIFIED" if hashes == baseline["initial_workspace_hashes"] else "RESET_FAILED",
            "run_id": run_id, "archive": str(archive), "workspace_hashes_match": hashes == baseline["initial_workspace_hashes"]}


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CDD-TLA-001 offline case entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    p = sub.add_parser("plan"); p.add_argument("--condition", choices=CONDITIONS, required=True); p.add_argument("--run-id", required=True)
    p = sub.add_parser("configure"); p.add_argument("run_root", type=Path); p.add_argument("--condition", choices=CONDITIONS, required=True)
    p = sub.add_parser("collab-serve", help="serve the existing run-scoped message/attachment API")
    p.add_argument("--run-root", type=Path, required=True); p.add_argument("--port", type=int, default=0)
    p = sub.add_parser("evaluate"); p.add_argument("run_root", type=Path)
    p = sub.add_parser("reset"); p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        out = prepare_run(args.run_root, args.run_id)
    elif args.command == "plan":
        out = make_plan(args.condition, args.run_id)
    elif args.command == "configure":
        out = configure_run(args.run_root, args.condition)
    elif args.command == "collab-serve":
        root, owner = _load_owned_run(args.run_root)
        tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
        from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
        server = make_server(ProtocolStore(root / "collaboration", owner["run_id"]), tokens,
                             host="127.0.0.1", port=args.port)
        print(json.dumps({"ready": True, "host": "127.0.0.1", "port": server.server_port,
                          "run_id": owner["run_id"]}, flush=True))
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    elif args.command == "evaluate":
        out = evaluate_run(args.run_root)
    else:
        out = reset_owned_run(args.run_root, args.run_id)
    print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if out.get("status") in (None, "PASS", "RESET_VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(cli())
