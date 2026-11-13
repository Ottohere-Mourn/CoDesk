"""Offline episode setup, fair condition plans, evaluation, reset and provenance."""
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
from .fixtures import copy_fixture
from .oracle import evaluate
from .workbook_store import WorkbookStore


def _write_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)
    path.chmod(mode)


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(run_root)
    if root.exists() and (root.is_symlink() or not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"run root must be a new/empty non-symlink directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    public = root / "fixture"
    manifest = copy_fixture(public)
    initial = public / "initial.ods"
    store = WorkbookStore.initialize(root / "workbook_store", run_id, initial)
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
    ownership = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "run_id": run_id, "owner_user": os.environ.get("USER", "unknown"),
        "created_at_epoch": time.time(), "run_root": str(root.resolve()),
        "resources": [
            {"kind": "public_fixture", "path": str(public.resolve()), "status": "active"},
            {"kind": "versioned_ods_repository", "path": str((root / "workbook_store").resolve()), "status": "active"},
            {"kind": "actor_message_protocol", "path": str(protocol_dir.resolve()), "status": "active"},
            {"kind": "actor_credentials", "path": str((root / "secrets").resolve()), "status": "active"},
            {"kind": "actor_instructions", "path": str((root / "actor_instructions").resolve()), "status": "active"},
        ],
        "cleanup_policy": "preserve episode revisions/logs; reset only through WorkbookStore.reset_to_initial after exact ownership check",
    }
    _write_json(root / "ownership.json", ownership)
    _write_json(root / "run_config.template.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": None, "workspace_backend_id": f"{CASE_ID}/{run_id}/workbook",
        "same_version_repository_all_conditions": True,
        "budget_per_actor": spec.ROLE_BUDGET,
    }, 0o644)
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "fixture_and_store_created",
                                               "initial_sha256": store.current()["sha256"],
                                               "time_epoch": time.time()})
    return {"case_id": CASE_ID, "run_id": run_id, "run_root": str(root.resolve()),
            "initial_workbook_sha256": store.current()["sha256"],
            "workbook_store": str(root / "workbook_store"),
            "fixture_manifest": manifest}


def make_plan(condition: str, run_id: str, *, steps_per_actor: int | None = None,
              tokens_per_actor: int | None = None) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    steps = spec.ROLE_BUDGET["steps"] if steps_per_actor is None else steps_per_actor
    tokens = spec.ROLE_BUDGET["model_tokens"] if tokens_per_actor is None else tokens_per_actor
    if steps < 1 or tokens < 1:
        raise ValueError("actor budgets must be positive")
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": condition,
        "actor_ids": ["S"] if condition == "single_agent" else ["A", "B"],
        "desktop_count": {"single_agent": 1, "collaborative_isolated": 2,
                          "collaborative_shared": 1}[condition],
        "desktop_topology": {"single_agent": "one desktop, integrated actor",
                             "collaborative_isolated": "two independent GUI desktops",
                             "collaborative_shared": "one live GUI desktop/session controlled by A and B"}[condition],
        "workspace_backend_id": f"{CASE_ID}/{run_id}/workbook",
        "backend_topology": "same canonical append-only ODS version repository in every condition",
        "backend_topology_changes_between_conditions": False,
        "writer_lease": spec.SINGLE_WRITER_PROTOCOL,
        "source_facts_visible_to_all": True,
        "message_and_attachment_api": "existing Data-to-Deck ProtocolStore, same capabilities all conditions",
        "message_capabilities_equal": True,
        "actor_budgets": {actor: {"steps": steps, "model_tokens": tokens}
                          for actor in (["S"] if condition == "single_agent" else ["A", "B"])},
        "single_agent_combined_budget": {"steps": steps * 2, "model_tokens": tokens * 2}
            if condition == "single_agent" else None,
        "oracle": "same ODS structure/value/formula oracle in every condition",
        "runtime_status": "OFFLINE_FIXTURE_AND_ORACLE_READY; Guest/GUI/model pending",
    }


def _load_owned_run(run_root: str | Path, run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    input_root = Path(run_root)
    if input_root.is_symlink():
        raise PermissionError("run root must not be a symlink")
    root = input_root.resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing or symlinked ownership ledger")
    owner = json.loads(ledger.read_text(encoding="utf-8"))
    if owner.get("case_id") != CASE_ID or Path(owner.get("run_root", "")).resolve() != root:
        raise PermissionError("run ownership mismatch")
    if run_id is not None and owner.get("run_id") != run_id:
        raise PermissionError("run_id does not match ownership ledger")
    return root, owner


def configure_run(run_root: str | Path, condition: str) -> dict[str, Any]:
    root, owner = _load_owned_run(run_root)
    target = root / "run_config.json"
    if target.exists():
        raise FileExistsError("preserving existing run_config.json; use a fresh run")
    plan = make_plan(condition, owner["run_id"])
    plan["initial_workbook_sha256"] = WorkbookStore(root / "workbook_store", owner["run_id"]).current()["sha256"]
    _write_json(target, plan)
    return plan


def evaluate_run(run_root: str | Path) -> dict[str, Any]:
    root, owner = _load_owned_run(run_root)
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure the run condition first")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("case_id") != CASE_ID or config.get("run_id") != owner["run_id"]:
        raise PermissionError("run config identity mismatch")
    result_path, provenance_path = root / "oracle_result.json", root / "provenance.json"
    if result_path.exists() or provenance_path.exists():
        raise FileExistsError("preserving prior result/provenance; evaluate in a fresh run")
    store = WorkbookStore(root / "workbook_store", owner["run_id"])
    initial = root / "workbook_store" / "revisions" / "revision-000000.ods"
    current = store.current()
    result = evaluate(current["path"], initial)
    result.update({"run_id": owner["run_id"], "condition": config["condition"],
                   "workbook_revision": current["revision"]})
    events_path = root / "collaboration" / "events.jsonl"
    protocol = ([json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if events_path.is_file() else [])
    result["process_metrics"] = {
        "message_count": sum(row.get("type") == "message" for row in protocol),
        "attachment_count": sum(row.get("type") == "attachment" for row in protocol),
        "scheduled_exposure": "NOT_SCHEDULED_OFFLINE",
        "observed_interference": "NOT_MEASURED_WITHOUT_GUI_TRACE",
        "autonomous_recovery": "NOT_MEASURED_WITHOUT_AGENT_TRACE",
    }
    _write_json(result_path, result)
    provenance = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": owner["run_id"],
        "condition": config["condition"], "workspace_backend_id": config["workspace_backend_id"],
        "fixture_manifest_sha256": _sha(root / "fixture" / "fixture_manifest.json"),
        "initial_workbook_sha256": _sha(initial), "final_workbook_sha256": current["sha256"],
        "workbook_events_sha256": _sha(root / "workbook_store" / "events.jsonl"),
        "collaboration_events_sha256": _sha(events_path) if events_path.is_file() else None,
        "oracle_result_sha256": _sha(result_path), "created_at_epoch": time.time(),
        "gui_action_trace": "NOT_PRESENT_OFFLINE", "guest_validation": "PENDING",
    }
    _write_json(provenance_path, provenance)
    return result


def reset_run(run_root: str | Path, run_id: str) -> dict[str, Any]:
    root, owner = _load_owned_run(run_root, run_id)
    store = WorkbookStore(root / "workbook_store", run_id)
    state = store.reset_to_initial()
    _append(root / "resource_actions.jsonl", {"run_id": run_id, "action": "reset_to_initial",
                                               "revision": state["revision"], "time_epoch": time.time(),
                                               "history_preserved": True})
    return {"case_id": owner["case_id"], "run_id": run_id, "revision": state["revision"],
            "sha256": state["sha256"], "initial_sha256": store.current()["sha256"],
            "history_preserved": True}


def serve_messages(run_root: str | Path, *, host: str = "127.0.0.1", port: int = 0):
    root, owner = _load_owned_run(run_root)
    tokens = json.loads((root / "secrets" / "collaboration_tokens.json").read_text(encoding="utf-8"))
    server = make_server(ProtocolStore(root / "collaboration", owner["run_id"]), tokens, host=host, port=port)
    server.codesk_run_id = owner["run_id"]
    return server


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m oscombo.collab.spreadsheet_handoff")
    subs = parser.add_subparsers(dest="command", required=True)
    build = subs.add_parser("build-fixture")
    build.add_argument("output", type=Path)
    prep = subs.add_parser("prepare")
    prep.add_argument("run_root", type=Path)
    prep.add_argument("--run-id", required=True)
    plan = subs.add_parser("plan")
    plan.add_argument("condition", choices=CONDITIONS)
    plan.add_argument("--run-id", default="example-run")
    configure = subs.add_parser("configure")
    configure.add_argument("run_root", type=Path)
    configure.add_argument("condition", choices=CONDITIONS)
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
    if args.command == "build-fixture":
        from .fixtures import build_fixture
        result = build_fixture(args.output)
    elif args.command == "prepare":
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
