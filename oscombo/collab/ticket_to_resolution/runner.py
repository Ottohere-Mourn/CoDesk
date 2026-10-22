"""Case preparation, topology plans, controlled reset, and evaluation entry."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from . import CASE_ID, CASE_VERSION, spec
from .database import create_database
from .oracle import evaluate
from .webapp import run_server

ORACLE_DIR = "oracle"
MANIFEST_NAME = "fixture_manifest.json"


def hidden_manifest_path(run_root: str | Path) -> Path:
    return Path(run_root) / ORACLE_DIR / MANIFEST_NAME


def _write_json(path: Path, value: Any, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    if mode is not None:
        path.chmod(mode)


def prepare_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root).absolute()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"run root is not empty; preserve it and choose a fresh run path: {root}")
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "db" / spec.FIXTURE_DB
    manifest = create_database(db_path, run_id)
    manifest_path = hidden_manifest_path(root)
    _write_json(manifest_path, manifest, 0o600)
    passwords = {actor: secrets.token_urlsafe(24) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "browser_credentials.json", passwords, 0o600)
    collaboration_tokens = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "collaboration_tokens.json", collaboration_tokens, 0o600)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    (root / "case_brief.md").write_text(
        "# Ticket-to-Resolution case brief\n\n"
        f"Case: {CASE_ID} / {CASE_VERSION}.\n\n"
        "This is a synthetic, offline support case. No real payment or customer system is connected. "
        "The application pages expose the same ticket, order, evidence, and policy to both roles. "
        "Use your assigned responsibility and the shared run message tools as useful; no message count or timing is prescribed.\n",
        encoding="utf-8")
    ownership = {"schema_version": 1, "case_id": CASE_ID, "run_id": run_id,
                 "owner_user": os.environ.get("USER", "unknown"),
                 "created_at_epoch": time.time(), "run_root": str(root.resolve()),
                 "resources": [
                     {"kind": "sqlite_database", "path": str(db_path.resolve()), "status": "active"},
                     {"kind": "hidden_fixture_manifest", "path": str(manifest_path.resolve()), "status": "active"},
                     {"kind": "browser_credentials", "path": str((root / "secrets" / "browser_credentials.json").resolve()), "status": "active"},
                     {"kind": "collaboration_tokens", "path": str((root / "secrets" / "collaboration_tokens.json").resolve()), "status": "active"},
                     {"kind": "collaboration_protocol_dir", "path": str((root / "collaboration").resolve()), "status": "active"},
                     {"kind": "case_brief", "path": str((root / "case_brief.md").resolve()), "status": "active"},
                     {"kind": "run_config_template", "path": str((root / "run_config.template.json").resolve()), "status": "active"},
                     {"kind": "resource_action_log", "path": str((root / "resource_actions.jsonl").resolve()), "status": "active"},
                 ],
                 "cleanup_policy": "Do not remove resources unless this run_id and exact path are verified."}
    _write_json(root / "ownership.json", ownership, 0o600)
    initial = {"run_id": run_id, "case_id": CASE_ID, "case_version": CASE_VERSION,
               "condition": None, "actor_ids": ["A", "B"],
               "backend": {"topology": "one episode-scoped SQLite service shared by all desktop sessions",
                           "fixture_sha256": manifest["business_state_sha256"]},
               "budget": {"steps_per_role": 240, "model_tokens_per_role": 12000,
                          "status": "exploratory defaults only; not calibrated for this task"}}
    _write_json(root / "run_config.template.json", initial)
    with (root / "resource_actions.jsonl").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"run_id": run_id, "action": "fixture_created", "path": str(db_path),
                                 "business_state_sha256": manifest["business_state_sha256"]}, sort_keys=True) + "\n")
    return {"run_root": str(root), "database": str(db_path), "fixture_manifest_hidden": str(manifest_path),
            "collaboration_tokens_hidden": str(root / "secrets" / "collaboration_tokens.json"),
            "business_state_sha256": manifest["business_state_sha256"], "ownership": str(root / "ownership.json")}


def make_plan(condition: str, run_id: str, *, app_url: str | None = None,
              steps_per_role: int = 240, tokens_per_role: int = 12000) -> dict[str, Any]:
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if steps_per_role < 1 or tokens_per_role < 1:
        raise ValueError("budgets must be positive")
    guest_count = {"single_agent": 1, "collaborative_isolated": 2, "collaborative_shared": 1}[condition]
    actor_ids = ["S"] if condition == "single_agent" else ["A", "B"]
    return {
        "run_id": run_id, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "condition": condition, "actor_ids": actor_ids, "guest_count": guest_count,
        "desktop_topology": {
            "single_agent": "one desktop, one integrated actor with verifier and processor responsibilities",
            "collaborative_isolated": "two independent desktops, one Guest per actor",
            "collaborative_shared": "one desktop, two actor-specific top-level browser windows",
        }[condition],
        "backend_topology": "one run-scoped business service and database snapshot per episode; every actor session connects to it",
        "backend_changes_between_conditions": False,
        "browser_identity_policy": "distinct A/B credentials and profiles in both collaborative conditions; S credential for single_agent",
        "source_facts_visible_to_all": True,
        "message_api": "same ProtocolStore API available in all conditions",
        "budget": {"steps_per_role": steps_per_role, "model_tokens_per_role": tokens_per_role,
                   "single_agent_total_steps": 2 * steps_per_role,
                   "single_agent_total_model_tokens": 2 * tokens_per_role,
                   "calibration_status": "exploratory defaults; calibrate GUI solvability before model comparison"},
        "app_url": app_url,
        "primary_outcome": "correct target refund + resolved target ticket + protected state",
        "separate_process_metrics": ["review_used", "message_feedback", "review_revision", "exposure",
                                     "observed_interference", "recovery", "outcome"],
    }


def reset_owned_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root).absolute()
    ownership_path = root / "ownership.json"
    if not ownership_path.is_file() or ownership_path.is_symlink():
        raise PermissionError("missing or symlinked ownership ledger; refusing reset")
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or ownership.get("run_id") != run_id:
        raise PermissionError("ownership ledger does not match this Case/run; refusing reset")
    if Path(ownership.get("run_root", "")).resolve() != root.resolve():
        raise PermissionError("ownership root mismatch; refusing reset")
    db_path = root / "db" / spec.FIXTURE_DB
    if not db_path.is_file() or db_path.is_symlink() or db_path.resolve().parent != (root / "db").resolve():
        raise PermissionError("database path is not an owned regular file; refusing reset")
    backup_dir = root / "pre_reset"
    backup_dir.mkdir(exist_ok=True)
    reset_stamp = time.time_ns()
    backup_path = backup_dir / f"case-before-reset-{reset_stamp}.sqlite3"
    manifest_backup = backup_dir / f"manifest-before-reset-{reset_stamp}.json"
    if backup_path.exists() or manifest_backup.exists():
        raise FileExistsError("pre-reset snapshot path collision")
    shutil.copy2(db_path, backup_path)
    tmp_db = root / "db" / f"reset-{secrets.token_hex(6)}.sqlite3"
    new_manifest = create_database(tmp_db, run_id)
    shutil.copy2(hidden_manifest_path(root), manifest_backup)
    os.replace(tmp_db, db_path)
    manifest_path = hidden_manifest_path(root)
    _write_json(manifest_path, new_manifest, 0o600)
    action = {"run_id": run_id, "action": "database_reset", "database": str(db_path),
              "pre_reset_snapshot": str(backup_path),
              "pre_reset_manifest": str(manifest_backup),
              "business_state_sha256": new_manifest["business_state_sha256"], "time_epoch": time.time()}
    with (root / "resource_actions.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(action, sort_keys=True) + "\n")
    ownership.setdefault("resources", []).extend([
        {"kind": "pre_reset_database_snapshot", "path": str(backup_path.resolve()), "status": "preserved"},
        {"kind": "pre_reset_manifest_snapshot", "path": str(manifest_backup.resolve()), "status": "preserved"},
    ])
    ownership_path.write_text(json.dumps(ownership, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return action


def _condition_from_run_config(root: Path) -> str:
    path = root / "run_config.json"
    if not path.is_file():
        raise FileNotFoundError(f"copy an explicit condition plan to {path} before evaluating")
    config = json.loads(path.read_text(encoding="utf-8"))
    condition = config.get("condition")
    if condition not in spec.CONDITIONS:
        raise ValueError("run_config.json has no valid condition")
    return condition


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket-to-Resolution independent case entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="create a deterministic synthetic episode under a new run root")
    p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    p = sub.add_parser("plan", help="print a condition plan without starting a Guest")
    p.add_argument("--condition", required=True, choices=spec.CONDITIONS); p.add_argument("--run-id", required=True)
    p.add_argument("--app-url"); p.add_argument("--steps-per-role", type=int, default=240)
    p.add_argument("--tokens-per-role", type=int, default=12000); p.add_argument("--output", type=Path)
    p = sub.add_parser("configure", help="write a condition plan into an owned prepared run")
    p.add_argument("run_root", type=Path); p.add_argument("--condition", required=True, choices=spec.CONDITIONS)
    p.add_argument("--app-url"); p.add_argument("--steps-per-role", type=int, default=240)
    p.add_argument("--tokens-per-role", type=int, default=12000)
    p = sub.add_parser("serve", help="serve the GUI application for a prepared episode")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("collab-serve", help="serve this run's existing message/attachment protocol")
    p.add_argument("--run-root", type=Path, required=True); p.add_argument("--port", type=int, default=0)
    p = sub.add_parser("evaluate", help="run the hidden-state business oracle")
    p.add_argument("run_root", type=Path)
    p = sub.add_parser("reset", help="snapshot and reset only a ledger-owned episode database")
    p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    p = sub.add_parser("guest-smoke", help="run the bounded scripted GUI smoke using OSWorld")
    p.add_argument("--run-root", type=Path, required=True); p.add_argument("--run-id", required=True)
    p.add_argument("--base-image", type=Path, required=True); p.add_argument("--provider", type=Path, required=True)
    p.add_argument("--runtime-image", required=True); p.add_argument("--condition", default="collaborative_shared",
        choices=("collaborative_shared", "collaborative_isolated"))
    args = parser.parse_args(argv)

    if args.command == "prepare":
        print(json.dumps(prepare_run(args.run_root, args.run_id), indent=2)); return 0
    if args.command == "plan":
        plan = make_plan(args.condition, args.run_id, app_url=args.app_url,
                         steps_per_role=args.steps_per_role, tokens_per_role=args.tokens_per_role)
        encoded = json.dumps(plan, indent=2, sort_keys=True) + "\n"
        if args.output:
            if args.output.exists():
                raise FileExistsError(f"refusing to overwrite plan: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(encoded)
        print(encoded, end=""); return 0
    if args.command == "configure":
        root = args.run_root.resolve()
        ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
        if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
            raise PermissionError("run ownership does not match this case directory")
        plan = make_plan(args.condition, ownership["run_id"], app_url=args.app_url,
                         steps_per_role=args.steps_per_role, tokens_per_role=args.tokens_per_role)
        target = root / "run_config.json"
        if target.exists():
            raise FileExistsError(f"preserving prior run configuration: {target}")
        _write_json(target, plan, 0o600)
        print(json.dumps({"run_config": str(target), "condition": args.condition,
                          "backend_topology": plan["backend_topology"]}, indent=2))
        return 0
    if args.command == "serve":
        credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
        run_server(args.db, credentials, args.host, args.port); return 0
    if args.command == "collab-serve":
        from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
        root = args.run_root.resolve()
        ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
        if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
            raise PermissionError("run ownership does not match this case directory")
        tokens_path = root / "secrets" / "collaboration_tokens.json"
        tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
        server = make_server(ProtocolStore(root / "collaboration", ownership["run_id"]), tokens,
                             host="127.0.0.1", port=args.port)
        print(json.dumps({"ready": True, "host": "127.0.0.1", "port": server.server_port,
                          "run_id": ownership["run_id"]}, flush=True))
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    if args.command == "evaluate":
        root = args.run_root
        result = evaluate(root / "db" / spec.FIXTURE_DB, hidden_manifest_path(root),
                          _condition_from_run_config(root))
        output = root / "oracle.json"
        if output.exists():
            raise FileExistsError(f"preserving prior oracle result; choose a fresh run: {output}")
        _write_json(output, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["joint_business_success"] else 2
    if args.command == "reset":
        print(json.dumps(reset_owned_run(args.run_root, args.run_id), indent=2)); return 0
    if args.command == "guest-smoke":
        from .guest_smoke import run_guest_smoke
        result = run_guest_smoke(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("oracle_pass") and result.get("reset_pass") else 2
    return 2


if __name__ == "__main__":
    sys.exit(cli())
