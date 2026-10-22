"""Offline run preparation, condition protocol, result and preservation-safe reset."""
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

from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server

from . import CASE_ID, CASE_VERSION, CONDITIONS, spec
from .fixtures import tree_hashes
from .oracle import evaluate


def _write_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)
    path.chmod(mode)


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root)
    if root.exists() and (root.is_symlink() or not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"run root must be a new/empty non-symlink directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).parent / "fixtures" / "initial_workspace"
    workspace = root / "workspace"
    shutil.copytree(template, workspace)
    initial_copy = root / "oracle" / "initial_workspace"
    shutil.copytree(template, initial_copy)
    source_manifest = Path(__file__).parent / "fixtures" / "fixture_manifest.json"
    public = root / "public"
    public.mkdir()
    shutil.copy2(source_manifest, public / "fixture_manifest.json")
    baseline_hashes = tree_hashes(initial_copy)
    _write_json(root / "oracle" / "baseline_manifest.json", {
        "case_id": CASE_ID, "run_id": run_id, "initial_files": baseline_hashes,
        "initial_tree_sha256": hashlib.sha256(json.dumps(baseline_hashes, sort_keys=True).encode()).hexdigest(),
        "oracle_visibility": "private; do not mount oracle/ or package fixtures/private for Actors",
    })
    protocol_dir = root / "collaboration"
    ProtocolStore(protocol_dir, run_id)
    tokens = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "collaboration_tokens.json", tokens)
    instructions = {"A": spec.ACTOR_A_INSTRUCTION, "B": spec.ACTOR_B_INSTRUCTION,
                    "S": spec.SINGLE_AGENT_INSTRUCTION}
    for actor, instruction in instructions.items():
        path = root / "actor_instructions" / f"{actor}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction + "\n", encoding="utf-8")
        path.chmod(0o600)
    owner = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "run_id": run_id, "owner_user": os.environ.get("USER", "unknown"),
        "created_at_epoch": time.time(), "run_root": str(root.resolve()),
        "resources": [
            {"kind": "mutable_workspace", "path": str(workspace.resolve()), "status": "active"},
            {"kind": "private_initial_baseline", "path": str(initial_copy.resolve()), "status": "active"},
            {"kind": "actor_message_protocol", "path": str(protocol_dir.resolve()), "status": "active"},
            {"kind": "actor_credentials", "path": str((root / "secrets").resolve()), "status": "active"},
            {"kind": "provenance_and_reset_history", "path": str((root / "resource_actions.jsonl").resolve()), "status": "active"},
        ],
        "cleanup_policy": "reset archives current workspace; no unowned path is removed",
    }
    _write_json(root / "ownership.json", owner)
    _write_json(root / "run_config.template.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id, "condition": None,
        "workspace_backend_id": f"{CASE_ID}/{run_id}/canonical-project",
        "same_backend_and_fixture_all_conditions": True,
        "actor_budgets": spec.ROLE_BUDGET,
    }, 0o644)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "fixture_created",
                                               "initial_tree_sha256": json.loads(
                                                   (root / "oracle" / "baseline_manifest.json").read_text(
                                                       encoding="utf-8"))["initial_tree_sha256"],
                                               "time_epoch": time.time()})
    return {"case_id": CASE_ID, "run_id": run_id, "workspace": str(workspace),
            "initial_tree_hashes": baseline_hashes, "ownership": str(root / "ownership.json")}


def make_plan(condition: str, run_id: str, *, steps_per_actor: int | None = None,
              tokens_per_actor: int | None = None) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    steps = spec.ROLE_BUDGET["steps"] if steps_per_actor is None else steps_per_actor
    tokens = spec.ROLE_BUDGET["model_tokens"] if tokens_per_actor is None else tokens_per_actor
    if steps < 1 or tokens < 1:
        raise ValueError("actor budgets must be positive")
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id, "condition": condition,
        "actor_ids": ["S"] if condition == "single_agent" else ["A", "B"],
        "desktop_count": {"single_agent": 1, "collaborative_isolated": 2,
                          "collaborative_shared": 1}[condition],
        "desktop_topology": {"single_agent": "one desktop, integrated actor",
                             "collaborative_isolated": "two independent desktop sessions",
                             "collaborative_shared": "one live GUI desktop controlled by both actors"}[condition],
        "workspace_backend_id": f"{CASE_ID}/{run_id}/canonical-project",
        "workspace_backend_topology": spec.CONDITION_RULES["backend"],
        "workspace_topology_changes_between_conditions": False,
        "actor_task_ownership": {"A": "file manager moves/renames plus attachment manifest",
                                 "B": "Writer report content and relative references",
                                 "S": "combined task"},
        "message_and_attachment_api": "existing Data-to-Deck ProtocolStore; same A/B capabilities in all conditions",
        "message_capabilities_equal": True,
        "actor_budgets": {actor: {"steps": steps, "model_tokens": tokens}
                          for actor in (["S"] if condition == "single_agent" else ["A", "B"])},
        "single_agent_combined_budget": {"steps": 2 * steps, "model_tokens": 2 * tokens}
            if condition == "single_agent" else None,
        "oracle": "same filesystem hash/path + ODT semantic-link oracle in every condition",
        "filesystem_state_is_not_gui_interference": True,
        "runtime_status": "OFFLINE_FIXTURE_AND_ORACLE_READY; Guest/GUI/model pending",
    }


def _owned(run_root: str | Path, run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    path = Path(run_root)
    if path.is_symlink():
        raise PermissionError("run root must not be a symlink")
    root = path.resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing or symlinked ownership ledger")
    owner = json.loads(ledger.read_text(encoding="utf-8"))
    if owner.get("case_id") != CASE_ID or Path(owner.get("run_root", "")).resolve() != root:
        raise PermissionError("workspace run ownership mismatch")
    if run_id is not None and owner.get("run_id") != run_id:
        raise PermissionError("requested run id does not match ownership ledger")
    return root, owner


def configure_run(run_root: str | Path, condition: str) -> dict[str, Any]:
    root, owner = _owned(run_root)
    target = root / "run_config.json"
    if target.exists():
        raise FileExistsError("preserving run_config.json; use a fresh run")
    plan = make_plan(condition, owner["run_id"])
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))
    plan["initial_tree_sha256"] = baseline["initial_tree_sha256"]
    _write_json(target, plan)
    return plan


def evaluate_run(run_root: str | Path) -> dict[str, Any]:
    root, owner = _owned(run_root)
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure a condition before evaluation")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("case_id") != CASE_ID or config.get("run_id") != owner["run_id"]:
        raise PermissionError("run config identity mismatch")
    result_path, provenance_path = root / "oracle_result.json", root / "provenance.json"
    if result_path.exists() or provenance_path.exists():
        raise FileExistsError("preserving existing result/provenance; evaluate in a fresh run")
    result = evaluate(root / "workspace", root / "oracle" / "initial_workspace")
    events_path = root / "collaboration" / "events.jsonl"
    protocol = ([json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if events_path.is_file() else [])
    result.update({"run_id": owner["run_id"], "condition": config["condition"],
                   "process_metrics": {
                       "message_count": sum(item.get("type") == "message" for item in protocol),
                       "attachment_count": sum(item.get("type") == "attachment" for item in protocol),
                       "scheduled_exposure": "NOT_SCHEDULED_OFFLINE",
                       "observed_interference": "NOT_MEASURED_WITHOUT_GUI_TRACE",
                       "autonomous_recovery": "NOT_MEASURED_WITHOUT_AGENT_TRACE",
                   }})
    _write_json(result_path, result)
    workspace_hashes = tree_hashes(root / "workspace")
    provenance = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": owner["run_id"],
        "condition": config["condition"], "workspace_backend_id": config["workspace_backend_id"],
        "initial_tree_sha256": config["initial_tree_sha256"],
        "final_tree_sha256": hashlib.sha256(json.dumps(workspace_hashes, sort_keys=True).encode()).hexdigest(),
        "final_file_hashes": workspace_hashes,
        "collaboration_events_sha256": _sha(events_path) if events_path.is_file() else None,
        "oracle_result_sha256": _sha(result_path),
        "created_at_epoch": time.time(), "gui_action_trace": "NOT_PRESENT_OFFLINE",
        "guest_validation": "PENDING",
    }
    _write_json(provenance_path, provenance)
    return result


def reset_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root, owner = _owned(run_root, run_id)
    workspace = root / "workspace"
    if not workspace.is_dir() or workspace.is_symlink():
        raise PermissionError("workspace is not a directory owned by this run")
    history = root / "history"
    history.mkdir(exist_ok=True)
    existing = [path for path in history.glob("workspace-before-reset-*")]
    snapshot = history / f"workspace-before-reset-{len(existing) + 1:04d}"
    if snapshot.exists():
        raise FileExistsError("preserving existing reset snapshot")
    shutil.move(str(workspace), str(snapshot))
    shutil.copytree(root / "oracle" / "initial_workspace", workspace)
    actual = tree_hashes(workspace)
    expected = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))["initial_files"]
    if actual != expected:
        raise RuntimeError("reset workspace differs from the initial fixture; snapshot was preserved")
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "reset_workspace",
                                               "snapshot": str(snapshot), "history_preserved": True,
                                               "time_epoch": time.time()})
    return {"case_id": owner["case_id"], "run_id": run_id, "reset_verified": actual == expected,
            "snapshot": str(snapshot), "history_preserved": True}


def serve_messages(run_root: str | Path, *, host: str = "127.0.0.1", port: int = 0):
    root, owner = _owned(run_root)
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    server = make_server(ProtocolStore(root / "collaboration", owner["run_id"]), tokens, host=host, port=port)
    server.codesk_run_id = owner["run_id"]
    return server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m oscombo.collab.workspace_assembly")
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("run_root", type=Path)
    prep.add_argument("--run-id", required=True)
    plan = subs.add_parser("plan")
    plan.add_argument("condition", choices=CONDITIONS)
    plan.add_argument("--run-id", default="example-run")
    config = subs.add_parser("configure")
    config.add_argument("run_root", type=Path)
    config.add_argument("condition", choices=CONDITIONS)
    score = subs.add_parser("evaluate")
    score.add_argument("run_root", type=Path)
    reset = subs.add_parser("reset")
    reset.add_argument("run_root", type=Path)
    reset.add_argument("--run-id", required=True)
    serve = subs.add_parser("serve-messages")
    serve.add_argument("run_root", type=Path)
    serve.add_argument("--port", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        result = prepare_run(args.run_root, args.run_id)
    elif args.command == "plan":
        result = make_plan(args.condition, args.run_id)
    elif args.command == "configure":
        result = configure_run(args.run_root, args.condition)
    elif args.command == "evaluate":
        result = evaluate_run(args.run_root)
    elif args.command == "reset":
        result = reset_run(args.run_root, args.run_id)
    else:
        server = serve_messages(args.run_root, port=args.port)
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}",
                          "run_id": server.codesk_run_id}))
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
