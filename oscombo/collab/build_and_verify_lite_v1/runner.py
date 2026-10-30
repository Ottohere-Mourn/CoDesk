"""Independent episode setup, condition planning, evaluation and reset."""
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

from . import CASE_ID, CASE_VERSION, spec
from .oracle import evaluate
from .webapp import run_server

TEMPLATE = Path(__file__).resolve().parent / "template" / "workspace"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    path.chmod(mode)


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def prepare_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root).absolute()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"run root is not empty; choose a new run path: {root}")
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    shutil.copytree(TEMPLATE, workspace,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    template_orders = json.loads((workspace / spec.DATA_FILE).read_text(encoding="utf-8"))
    if template_orders != list(spec.ORDERS):
        raise RuntimeError("case code constants and the visible order fixture have drifted")
    initial_hashes = _tree_hashes(workspace)
    orders_hash = initial_hashes[spec.DATA_FILE]
    baseline = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "orders_json_sha256": orders_hash,
        "initial_files": initial_hashes,
        "protected_files": {name: initial_hashes[name] for name in spec.PROTECTED_FILES},
        "gold_cases": [{"query": t["query"], "status": t["status"], "ids": list(t["ids"])}
                       for t in spec.ORACLE_CASES],
    }
    _write_json(root / "oracle" / "baseline_manifest.json", baseline)
    # Hex-only passwords are reliable through the Guest's physical-key GUI
    # typing path while retaining 128 bits of per-role entropy.
    credentials = {actor: secrets.token_hex(16) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "browser_credentials.json", credentials)
    bootstrap_tickets = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "browser_bootstrap.json", bootstrap_tickets)
    tokens = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "collaboration_tokens.json", tokens)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    (root / "case_brief.md").write_text(spec.PUBLIC_REQUIREMENTS, encoding="utf-8")
    for actor, instruction in (("A", spec.ACTOR_A_INSTRUCTION), ("B", spec.ACTOR_B_INSTRUCTION),
                               ("S", spec.SINGLE_AGENT_INSTRUCTION)):
        path = root / "instructions" / f"actor_{actor}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction + "\n", encoding="utf-8")
    ownership = {
        "schema_version": 1, "case_id": CASE_ID, "run_id": run_id,
        "owner_user": os.environ.get("USER", "unknown"), "created_at_epoch": time.time(),
        "run_root": str(root.resolve()), "resources": [
            {"kind": "mutable_code_workspace", "path": str(workspace.resolve()), "status": "active"},
            {"kind": "hidden_oracle_manifest", "path": str((root / "oracle" / "baseline_manifest.json").resolve()), "status": "active"},
            {"kind": "browser_credentials", "path": str((root / "secrets" / "browser_credentials.json").resolve()), "status": "active"},
            {"kind": "browser_bootstrap", "path": str((root / "secrets" / "browser_bootstrap.json").resolve()), "status": "active"},
            {"kind": "collaboration_tokens", "path": str((root / "secrets" / "collaboration_tokens.json").resolve()), "status": "active"},
            {"kind": "message_protocol", "path": str((root / "collaboration").resolve()), "status": "active"},
            {"kind": "web_event_log", "path": str((root / "web_events.jsonl").resolve()), "status": "active"},
            {"kind": "ownership_ledger", "path": str((root / "ownership.json").resolve()), "status": "active"},
        ],
        "cleanup_policy": "Preserve artifacts. Only a live runtime resource with this exact run_id and ownership may be stopped.",
    }
    _write_json(root / "ownership.json", ownership)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "workspace_fixture_created",
                                                "workspace_sha256": hashlib.sha256(json.dumps(initial_hashes, sort_keys=True).encode()).hexdigest(),
                                                "time_epoch": time.time()})
    config = {"run_id": run_id, "case_id": CASE_ID, "case_version": CASE_VERSION,
              "condition": None, "same_backend": True, "workspace_initial_sha256": initial_hashes,
              "budgets": {"per_actor_steps": spec.PAIR_MAX_STEPS, "per_actor_tokens": None,
                          "single_agent_steps": 40, "single_agent_tokens": None,
                          "status": "pilot budget; fixed across paired conditions"}}
    _write_json(root / "run_config.template.json", config, 0o644)
    return {"run_root": str(root), "case_id": CASE_ID, "run_id": run_id,
            "workspace": str(workspace), "initial_workspace_sha256": baseline["orders_json_sha256"],
            "ownership": str(root / "ownership.json")}


def make_plan(condition: str, run_id: str, *, app_url: str | None = None) -> dict[str, Any]:
    if condition not in spec.CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    actors = ["S"] if condition == "single_agent" else ["A", "B"]
    desktops = {"single_agent": 1, "collaborative_isolated": 2, "collaborative_shared": 1}[condition]
    budget = {"per_actor_steps": 40 if condition == "single_agent" else spec.PAIR_MAX_STEPS,
              "per_actor_tokens": None}
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": condition, "actor_ids": actors, "desktop_count": desktops,
        "desktop_topology": {"single_agent": "one desktop", "collaborative_isolated": "one independent desktop per actor",
                             "collaborative_shared": "one live desktop controlled by both actors"}[condition],
        "backend_topology": "one episode-scoped app server, one data fixture and one mutable code workspace shared in every condition",
        "workspace": "workspace/ (same initial code hash across conditions; shared mutable project files)",
        "application_service": "one run-scoped service; same URL/backend for all actor desktops",
        "browser_session_policy": "one independent login session/profile per actor in every condition; no cross-actor cookies",
        "message_protocol": "existing Data-to-Deck ProtocolStore; same actor-scoped capabilities in all conditions",
        "app_url": app_url, "budget": budget,
    }


def configure_run(run_root: str | Path, condition: str, app_url: str | None = None) -> dict[str, Any]:
    root = Path(run_root).resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run ownership mismatch")
    target = root / "run_config.json"
    if target.exists():
        raise FileExistsError(f"preserving existing config: {target}")
    plan = make_plan(condition, ownership["run_id"], app_url=app_url)
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))
    plan["fixture_sha256"] = baseline["orders_json_sha256"]
    plan["initial_workspace_sha256"] = baseline["initial_files"]
    _write_json(target, plan)
    return plan


def evaluate_run(run_root: str | Path) -> dict[str, Any]:
    root = Path(run_root).resolve()
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run ownership mismatch")
    oracle_out = root / "oracle_result.json"
    provenance_out = root / "provenance.json"
    if oracle_out.exists() or provenance_out.exists():
        raise FileExistsError("preserving previous evaluation/provenance; use a fresh run")
    result = evaluate(root)
    result["run_id"] = ownership["run_id"]
    _write_json(oracle_out, result)
    final_hashes = _tree_hashes(root / "workspace")
    provenance = {"case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": ownership["run_id"],
                  "condition": result["condition"], "initial_workspace_hashes": json.loads(
                      (root / "run_config.template.json").read_text(encoding="utf-8"))["workspace_initial_sha256"],
                  "final_workspace_hashes": final_hashes,
                  "web_events_sha256": _sha_or_none(root / "web_events.jsonl"),
                  "collaboration_events_sha256": _sha_or_none(root / "collaboration" / "events.jsonl"),
                  "oracle_sha256": _sha(oracle_out), "created_at_epoch": time.time(),
                  "guest_gui_action_trace": "not provided by this offline runner; attach OSWorld provenance for real Guest episodes"}
    _write_json(provenance_out, provenance)
    return result


def _sha_or_none(path: Path) -> str | None:
    return _sha(path) if path.is_file() else None


def reset_owned_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root).resolve()
    ledger_path = root / "ownership.json"
    ownership = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or ownership.get("run_id") != run_id \
            or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("refusing reset: ownership case, run ID, or root mismatch")
    for owned_dir in (root / "workspace", root / "collaboration"):
        if owned_dir.is_symlink() or not owned_dir.is_dir() or owned_dir.resolve().parent != root:
            raise PermissionError(f"refusing reset: unsafe or non-owned directory {owned_dir}")
    for lock_name in ("app_server.lock", "collab_server.lock"):
        if not (root / lock_name).exists():
            continue
        lock = json.loads((root / lock_name).read_text(encoding="utf-8"))
        if lock.get("run_id") == run_id:
            try:
                os.kill(int(lock["pid"]), 0)
            except (ProcessLookupError, ValueError, KeyError):
                pass
            else:
                raise RuntimeError(f"refusing reset while this run's {lock_name} is active")
    stamp = str(time.time_ns())
    archive = root / "pre_reset" / stamp
    archive.mkdir(parents=True, exist_ok=False)
    shutil.copytree(root / "workspace", archive / "workspace")
    for name in ("web_events.jsonl", "collaboration", "oracle_result.json", "provenance.json"):
        source = root / name
        if source.is_dir():
            shutil.copytree(source, archive / name)
        elif source.is_file():
            shutil.copy2(source, archive / name)
    shutil.rmtree(root / "workspace")
    shutil.copytree(TEMPLATE, root / "workspace",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    event_path = root / "web_events.jsonl"
    event_path.write_text("", encoding="utf-8")
    event_path.chmod(0o600)
    collab_dir = root / "collaboration"
    if collab_dir.exists():
        shutil.rmtree(collab_dir)
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(collab_dir, run_id)
    for name in ("oracle_result.json", "provenance.json"):
        (root / name).unlink(missing_ok=True)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "reset_verified",
                                                "archive": str(archive), "time_epoch": time.time()})
    ownership.setdefault("resources", []).append({"kind": "pre_reset_snapshot", "path": str(archive), "status": "preserved"})
    _write_json(ledger_path, ownership)
    return {"status": "RESET_VERIFIED", "run_id": run_id, "archive": str(archive),
            "workspace_sha256": _tree_hashes(root / "workspace")}


def _serve_owned(root: Path, host: str, port: int) -> None:
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure this run before serving it")
    lock = root / "app_server.lock"
    if lock.exists():
        raise FileExistsError("app server lock exists; preserve and audit it before starting")
    _write_json(lock, {"case_id": CASE_ID, "run_id": ownership["run_id"], "pid": os.getpid(),
                       "started_at_epoch": time.time()}, 0o600)
    credentials = json.loads((root / "secrets" / "browser_credentials.json").read_text(encoding="utf-8"))
    try:
        run_server(root / "workspace", credentials, root / "web_events.jsonl", host, port)
    finally:
        if lock.exists():
            state = json.loads(lock.read_text(encoding="utf-8"))
            if state.get("run_id") == ownership["run_id"] and state.get("pid") == os.getpid():
                lock.unlink()


def _serve_collaboration(root: Path, port: int) -> None:
    from oscombo.collab.data_to_deck.protocol import ProtocolStore, make_server
    ownership = json.loads((root / "ownership.json").read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("run ownership mismatch")
    lock = root / "collab_server.lock"
    if lock.exists():
        raise FileExistsError("collaboration server lock exists; preserve and audit it before starting")
    _write_json(lock, {"case_id": CASE_ID, "run_id": ownership["run_id"], "pid": os.getpid(),
                       "started_at_epoch": time.time()}, 0o600)
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    server = make_server(ProtocolStore(root / "collaboration", ownership["run_id"]), tokens, port=port)
    print(json.dumps({"ready": True, "host": "127.0.0.1", "port": server.server_port}, flush=True))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if lock.exists():
            state = json.loads(lock.read_text(encoding="utf-8"))
            if state.get("run_id") == ownership["run_id"] and state.get("pid") == os.getpid():
                lock.unlink()


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CDD-BV-LITE-001 independent case runner")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    p = sub.add_parser("plan"); p.add_argument("--condition", required=True, choices=spec.CONDITIONS); p.add_argument("--run-id", required=True); p.add_argument("--app-url")
    p = sub.add_parser("configure"); p.add_argument("run_root", type=Path); p.add_argument("--condition", required=True, choices=spec.CONDITIONS); p.add_argument("--app-url")
    p = sub.add_parser("serve"); p.add_argument("--run-root", type=Path, required=True); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8766)
    p = sub.add_parser("collab-serve"); p.add_argument("--run-root", type=Path, required=True); p.add_argument("--port", type=int, default=0)
    p = sub.add_parser("evaluate"); p.add_argument("run_root", type=Path)
    p = sub.add_parser("reset"); p.add_argument("run_root", type=Path); p.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_run(args.run_root, args.run_id)
    elif args.command == "plan":
        result = make_plan(args.condition, args.run_id, app_url=args.app_url)
    elif args.command == "configure":
        result = configure_run(args.run_root, args.condition, args.app_url)
    elif args.command == "serve":
        _serve_owned(args.run_root.resolve(), args.host, args.port)
        return 0
    elif args.command == "collab-serve":
        root = args.run_root.resolve()
        _serve_collaboration(root, args.port)
        return 0
    elif args.command == "evaluate":
        result = evaluate_run(args.run_root)
    else:
        result = reset_owned_run(args.run_root, args.run_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
