"""Run-scoped fixture staging, condition plans, oracle and archival reset.

This adapter may invoke Blender in background mode for file parsing and the
structural oracle; it does not launch a Blender desktop GUI or OSWorld Guest.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from . import CASE_ID, CASE_VERSION, CONDITIONS
from . import spec
from .oracle import evaluate_blend_file, extract_blend_snapshot, _protected_fingerprint
from .blend_format import has_blend_container_header_at
from .revision_store import RevisionStore

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_FIXTURE = PACKAGE_ROOT / "fixtures" / "initial.blend"


def _write_json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)
    path.chmod(mode)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_real_blend(path: Path) -> Path:
    input_path = path.expanduser()
    if input_path.is_symlink():
        raise PermissionError(f"refusing symlinked Blender fixture: {input_path}")
    path = input_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"real Blender fixture is unavailable: {path}")
    if not has_blend_container_header_at(path):
        raise ValueError(f"fixture is not a Blender .blend container: {path}")
    return path


def prepare_run(run_root: str | Path, run_id: str, *, fixture_path: str | Path | None = None,
                blender_bin: str | None = None) -> dict[str, Any]:
    fixture = _require_real_blend(Path(fixture_path) if fixture_path else DEFAULT_FIXTURE)
    if not (blender_bin or shutil.which("blender")):
        raise RuntimeError("Blender executable is unavailable; fixture readiness cannot be established")
    fixture_hash = _sha256(fixture)
    initial_snapshot = extract_blend_snapshot(fixture, blender_bin=blender_bin)
    root = Path(run_root).absolute()
    if root.exists() and (root.is_symlink() or not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"run root must be new/empty and not a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    project = workspace / spec.TEMPLATE_BLEND_RELATIVE
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture, project)
    initial_hash = _sha256(project)
    if initial_hash != fixture_hash:
        raise RuntimeError("fixture copy hash mismatch; refusing to initialize this run")
    baseline_protected = {name: _protected_fingerprint(next(row for row in initial_snapshot["objects"]
                                                                if row.get("name") == name))
                          for name in spec.PROTECTED_OBJECTS}
    (workspace / spec.PUBLIC_BRIEF_RELATIVE).write_text(spec.PUBLIC_BRIEF + "\n", encoding="utf-8")
    (workspace / "scene_catalog.json").write_text(json.dumps({
        "schema_version": 1,
        "scene_name": spec.SCENE_NAME,
        "objects": list(spec.OBJECT_NAMES),
        "units": "meters",
        "visibility": "public task material; shared by A, B and S",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    tokens = {actor: secrets.token_urlsafe(32) for actor in ("A", "B", "S")}
    _write_json(root / "secrets" / "collaboration_tokens.json", tokens)
    for actor, instruction in (("A", spec.ACTOR_A_INSTRUCTION), ("B", spec.ACTOR_B_INSTRUCTION),
                               ("S", spec.SINGLE_AGENT_INSTRUCTION)):
        path = root / "actor_instructions" / f"{actor}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction + "\n", encoding="utf-8")
        path.chmod(0o600)
    _write_json(root / "oracle" / "baseline_manifest.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "initial_blend_sha256": initial_hash,
        "gold_state_sha256": _sha256(PACKAGE_ROOT / "fixtures" / "gold_state.json"),
        "baseline_protected_objects": baseline_protected,
        "oracle_visibility": "private; do not mount oracle/ or package source into Actor context",
    })
    ownership = {
        "schema_version": 1, "case_id": CASE_ID, "case_version": CASE_VERSION,
        "run_id": run_id, "owner_user": os.environ.get("USER", "unknown"),
        "created_at_epoch": time.time(), "run_root": str(root.resolve()),
        "resources": [
            {"kind": "initial_real_blend", "path": str(project.resolve()), "sha256": initial_hash},
            {"kind": "canonical_revision_store", "path": str((root / "artifact_store").resolve())},
            {"kind": "private_oracle", "path": str((root / "oracle").resolve())},
            {"kind": "collaboration_protocol", "path": str((root / "collaboration").resolve())},
            {"kind": "blender_internal_state_log", "path": str((root / "interaction_events.jsonl").resolve())},
        ],
        "cleanup_policy": "Preserve episode artifacts; reset only direct children verified by this case_id/run_id/root ledger.",
    }
    _write_json(root / "ownership.json", ownership)
    RevisionStore.initialize(root / "artifact_store", run_id, project, artifact_kind="blender_project")
    with (root / "resource_actions.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"case_id": CASE_ID, "run_id": run_id,
                                 "action": "initial_revision_store_created",
                                 "initial_blend_sha256": initial_hash,
                                 "time_epoch": time.time()}, sort_keys=True) + "\n")
    _write_json(root / "run_config.template.json", {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": None, "initial_blend_sha256": initial_hash,
        "workspace_backend_id": f"{CASE_ID}/{run_id}/canonical-blend",
        "budget": {"steps_per_actor": 180, "tokens_per_actor": 12000,
                   "status": "exploratory and uncalibrated; same accounting across collaborative conditions"},
    }, 0o644)
    event_path = root / "interaction_events.jsonl"
    event_path.touch(mode=0o600)
    return {"case_id": CASE_ID, "run_id": run_id, "run_root": str(root),
            "workspace": str(workspace), "initial_blend_sha256": initial_hash,
            "ownership": str(root / "ownership.json")}


def make_plan(condition: str, run_id: str, *, steps_per_actor: int = 180,
              tokens_per_actor: int = 12000) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if steps_per_actor < 1 or tokens_per_actor < 1:
        raise ValueError("actor budgets must be positive")
    single = condition == "single_agent"
    return {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": run_id,
        "condition": condition, "actor_ids": ["S"] if single else ["A", "B"],
        "desktop_count": {"single_agent": 1, "collaborative_isolated": 2,
                          "collaborative_shared": 1}[condition],
        "desktop_topology": spec.CONDITION_SEMANTICS[condition],
        "workspace_backend_id": f"{CASE_ID}/{run_id}/canonical-blend",
        "workspace_backend_topology": "one canonical versioned .blend artifact store and same initial bytes in every condition",
        "backend_must_not_change_between_conditions": True,
        "project_path": spec.FINAL_BLEND_RELATIVE,
        "canonical_artifact_store": "artifact_store/current.json; adapter checks out and commits the real .blend by revision",
        "project_visibility": "same scene specifications and latest saved canonical .blend revision for every actor",
        "save_policy": "single active actor lease; save a revision before handoff; compare-and-swap revision; no simultaneous file writers",
        "role_write_scopes": {"A": ["Lamp_Shade"], "B": ["Camera_Main", "Key_Light", "Fill_Light", "Rim_Light"],
                              "S": list(spec.GOLD_OBJECTS)},
        "write_scope_enforcement": "task contract plus oracle; Blender object-level write ACL is not implemented",
        "message_protocol": "existing Data-to-Deck ProtocolStore send/read and attachment API",
        "message_capabilities_same_all_conditions": True,
        "scoring": "same private bpy-derived structural oracle in all conditions; visual quality supplementary",
        "shared_application_state_of_interest": ["active object", "selected objects", "Object/Edit Mode",
                                                  "active workspace/screen/area", "3D viewport orientation/location/distance",
                                                  "active scene camera"],
        "budget": {"steps_per_actor": steps_per_actor, "tokens_per_actor": tokens_per_actor,
                   "single_agent_total_steps": steps_per_actor * 2 if single else None,
                   "single_agent_total_tokens": tokens_per_actor * 2 if single else None,
                   "calibrated": False},
        "runtime_status": "REAL_BLEND_FIXTURE_READY; GUI, Guest and model execution remain pending",
    }


def _load_owned_run(run_root: str | Path, run_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    input_root = Path(run_root)
    if input_root.is_symlink():
        raise PermissionError("run root must not be a symlink")
    root = input_root.resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing or symlinked ownership ledger")
    ownership = json.loads(ledger.read_text(encoding="utf-8"))
    if ownership.get("case_id") != CASE_ID or Path(ownership.get("run_root", "")).resolve() != root:
        raise PermissionError("case/run root ownership mismatch")
    if run_id is not None and ownership.get("run_id") != run_id:
        raise PermissionError("requested run_id does not match ownership ledger")
    return root, ownership


def configure_run(run_root: str | Path, condition: str) -> dict[str, Any]:
    root, ownership = _load_owned_run(run_root)
    config_path = root / "run_config.json"
    if config_path.exists():
        raise FileExistsError("preserving existing run_config.json; use a new run")
    plan = make_plan(condition, ownership["run_id"])
    plan["initial_blend_sha256"] = json.loads(
        (root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))["initial_blend_sha256"]
    _write_json(config_path, plan)
    return plan


def evaluate_run(run_root: str | Path, *, blender_bin: str | None = None) -> dict[str, Any]:
    root, ownership = _load_owned_run(run_root)
    config_path = root / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError("configure a condition before evaluation")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("run_id") != ownership["run_id"] or config.get("case_id") != CASE_ID:
        raise PermissionError("run config identity mismatch")
    store = RevisionStore(root / "artifact_store", ownership["run_id"])
    current_revision = store.current()
    artifact = Path(current_revision["path"])
    final_copy = root / "workspace" / spec.FINAL_BLEND_RELATIVE
    if final_copy.exists() or final_copy.is_symlink():
        raise FileExistsError("preserving an existing final .blend output")
    final_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, final_copy)
    baseline = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))
    if _sha256(root / "workspace" / spec.TEMPLATE_BLEND_RELATIVE) != baseline["initial_blend_sha256"]:
        raise RuntimeError("initial .blend was modified; preserve evidence and use the required final output path")
    result_path, provenance_path = root / "oracle_result.json", root / "provenance.json"
    if result_path.exists() or provenance_path.exists():
        raise FileExistsError("preserving prior result/provenance; evaluate in a fresh run")
    if _sha256(final_copy) != _sha256(artifact):
        raise RuntimeError("final artifact collection hash mismatch")
    result = evaluate_blend_file(final_copy, blender_bin=blender_bin,
                                 baseline_protected=baseline.get("baseline_protected_objects"))
    result.update({"run_id": ownership["run_id"], "condition": config["condition"]})
    protocol_log = root / "collaboration" / "events.jsonl"
    messages = []
    if protocol_log.is_file():
        messages = [json.loads(line) for line in protocol_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    state_events = [json.loads(line) for line in (root / "interaction_events.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
    result["process_metrics"] = {
        "message_event_count": sum(event.get("type") == "message" for event in messages),
        "attachment_event_count": sum(event.get("type") == "attachment" for event in messages),
        "application_state_event_count": len(state_events),
        "application_state_capture": "boundary samples only; atomic input-level attribution unavailable",
        "substantive_collaboration": "NOT_INFERRED_FROM_MESSAGE_COUNT",
        "scheduled_exposure": "NOT_SCHEDULED_BY_OFFLINE_RUNNER",
        "observed_interference": "NOT_VERIFIED_WITHOUT_REAL_GUI_TRACES",
        "autonomous_recovery": "NOT_VERIFIED_WITHOUT_REAL_GUI_TRACES",
    }
    _write_json(result_path, result)
    provenance = {
        "case_id": CASE_ID, "case_version": CASE_VERSION, "run_id": ownership["run_id"],
        "condition": config["condition"], "workspace_backend_id": config["workspace_backend_id"],
        "initial_blend_sha256": baseline["initial_blend_sha256"], "final_blend_sha256": _sha256(final_copy),
        "final_revision": current_revision["revision"], "revision_events_sha256": _sha256(root / "artifact_store" / "events.jsonl"),
        "collaboration_events_sha256": _sha256(protocol_log) if protocol_log.is_file() else None,
        "interaction_events_sha256": _sha256(root / "interaction_events.jsonl"),
        "oracle_result_sha256": _sha256(result_path), "created_at_epoch": time.time(),
        "blender_gui_roundtrip": "PENDING_GUEST_SMOKE",
    }
    _write_json(provenance_path, provenance)
    return result


def reset_owned_run(run_root: str | Path, run_id: str, *, fixture_path: str | Path | None = None,
                    blender_bin: str | None = None) -> dict[str, Any]:
    fixture = _require_real_blend(Path(fixture_path) if fixture_path else DEFAULT_FIXTURE)
    if not (blender_bin or shutil.which("blender")):
        raise RuntimeError("Blender executable is unavailable; reset verification cannot be completed")
    root, ownership = _load_owned_run(run_root, run_id)
    workspace = root / "workspace"
    if workspace.is_symlink() or not workspace.is_dir() or workspace.resolve().parent != root:
        raise PermissionError("refusing reset: workspace is not an owned direct child")
    lock = root / "runtime.lock"
    if lock.is_file():
        lock_data = json.loads(lock.read_text(encoding="utf-8"))
        if lock_data.get("run_id") == run_id:
            try:
                os.kill(int(lock_data["pid"]), 0)
            except (ProcessLookupError, ValueError, KeyError):
                pass
            else:
                raise RuntimeError("refusing reset while this run's runtime lock PID is active")
    archive = root / "pre_reset" / str(time.time_ns())
    archive.mkdir(parents=True, exist_ok=False)
    os.replace(workspace, archive / "workspace")
    for name in ("artifact_store", "collaboration", "interaction_events.jsonl", "oracle_result.json", "provenance.json", "run_config.json"):
        path = root / name
        if path.exists():
            if path.is_symlink() or path.resolve().parent != root:
                raise PermissionError(f"refusing to archive a path outside the owned run: {path}")
            os.replace(path, archive / name)
    recreated = root / "workspace"
    project = recreated / spec.TEMPLATE_BLEND_RELATIVE
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture, project)
    expected = json.loads((root / "oracle" / "baseline_manifest.json").read_text(encoding="utf-8"))["initial_blend_sha256"]
    if _sha256(project) != expected:
        raise RuntimeError("reset fixture hash does not match original run; preserved archive for diagnosis")
    reset_snapshot = extract_blend_snapshot(project, blender_bin=blender_bin)
    reset_protected = {name: _protected_fingerprint(next(row for row in reset_snapshot["objects"]
                                                            if row.get("name") == name))
                       for name in spec.PROTECTED_OBJECTS}
    expected_protected = json.loads((root / "oracle" / "baseline_manifest.json").read_text(
        encoding="utf-8")).get("baseline_protected_objects")
    if reset_protected != expected_protected:
        raise RuntimeError("reset scene object state differs from original fixture; archived run retained")
    RevisionStore.initialize(root / "artifact_store", run_id, project, artifact_kind="blender_project")
    (recreated / spec.PUBLIC_BRIEF_RELATIVE).write_text(spec.PUBLIC_BRIEF + "\n", encoding="utf-8")
    (recreated / "scene_catalog.json").write_text(json.dumps({"schema_version": 1, "scene_name": spec.SCENE_NAME,
        "objects": list(spec.OBJECT_NAMES), "units": "meters", "visibility": "public"}, indent=2) + "\n", encoding="utf-8")
    from oscombo.collab.data_to_deck.protocol import ProtocolStore
    ProtocolStore(root / "collaboration", run_id)
    (root / "interaction_events.jsonl").touch(mode=0o600)
    with (root / "resource_actions.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"case_id": CASE_ID, "run_id": run_id, "action": "reset_verified",
                                 "initial_blend_sha256": expected, "time_epoch": time.time()}, sort_keys=True) + "\n")
    return {"status": "RESET_VERIFIED", "run_id": run_id, "archive": str(archive),
            "initial_blend_sha256": expected, "owner_user": ownership["owner_user"]}
