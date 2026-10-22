"""Append-only, read-only Blender context sampling for future GUI adapters."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from . import CASE_ID

_WRITE_LOCK = threading.Lock()
EVENT_TYPES = {"observation", "action_start", "action_end", "save", "message", "recovery"}
REQUIRED_STATE = {"active_object", "selected_objects", "mode", "active_workspace", "active_screen",
                  "active_area_type", "scene_camera", "viewports"}
REQUIRED_STATE = {"active_object", "selected_objects", "mode", "active_workspace", "active_screen",
                  "active_area_type", "scene_camera", "viewports"}


def capture_blender_state(context=None) -> dict[str, Any]:
    """Read current Blender context without changing selection, mode or view.

    Call inside Blender on the UI thread. This function samples state; it does
    not install handlers, timers, operators or callbacks.
    """
    try:
        import bpy
    except ImportError as exc:
        raise RuntimeError("capture_blender_state must run inside Blender's Python") from exc
    context = context or bpy.context
    window = getattr(context, "window", None)
    screen = getattr(context, "screen", None)
    active = getattr(getattr(context, "view_layer", None), "objects", None)
    active_obj = getattr(active, "active", None)
    selected = getattr(context, "selected_objects", ()) or ()
    viewports = []
    for area in getattr(screen, "areas", ()) if screen else ():
        if area.type != "VIEW_3D":
            continue
        region_3d = getattr(area.spaces.active, "region_3d", None)
        if region_3d is None:
            continue
        viewports.append({
            "area_type": "VIEW_3D",
            "view_perspective": str(region_3d.view_perspective),
            "view_location": [round(float(x), 6) for x in region_3d.view_location],
            "view_rotation_wxyz": [round(float(x), 7) for x in region_3d.view_rotation],
            "view_distance": round(float(region_3d.view_distance), 6),
        })
    scene = getattr(context, "scene", None)
    return {
        "sampled_monotonic_ns": time.monotonic_ns(),
        "window_runtime_id": int(window.as_pointer()) if window else None,
        "active_object": active_obj.name if active_obj else None,
        "selected_objects": sorted(obj.name for obj in selected),
        "mode": str(getattr(context, "mode", "UNKNOWN")),
        "active_workspace": getattr(getattr(context, "workspace", None), "name", None),
        "active_screen": getattr(screen, "name", None),
        "active_area_type": getattr(getattr(context, "area", None), "type", None),
        "scene_camera": getattr(getattr(scene, "camera", None), "name", None),
        "viewports": viewports,
    }


def _owned_root(run_root: str | Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    root = Path(run_root).resolve()
    ledger = root / "ownership.json"
    if not ledger.is_file() or ledger.is_symlink():
        raise PermissionError("missing or symlinked case ownership ledger")
    ownership = json.loads(ledger.read_text(encoding="utf-8"))
    if (ownership.get("case_id") != CASE_ID or ownership.get("run_id") != run_id
            or Path(ownership.get("run_root", "")).resolve() != root):
        raise PermissionError("case, run ID or root ownership mismatch")
    return root, ownership


def append_event(run_root: str | Path, *, run_id: str, actor_id: str, event_type: str,
                 blender_state: dict[str, Any], seq: int | None = None,
                 action_id: str | None = None, action_label: str | None = None,
                 capture_method: str = "read_only_bpy_context_sample") -> Path:
    if actor_id not in {"A", "B", "S"} or event_type not in EVENT_TYPES:
        raise ValueError("invalid actor or event type")
    if capture_method not in {"read_only_bpy_context_sample", "caller_supplied"}:
        raise ValueError("invalid capture method")
    if REQUIRED_STATE - blender_state.keys():
        raise ValueError(f"Blender state sample missing fields: {sorted(REQUIRED_STATE - blender_state.keys())}")
    if REQUIRED_STATE - blender_state.keys():
        raise ValueError(f"Blender state sample missing fields: {sorted(REQUIRED_STATE - blender_state.keys())}")
    root, _ = _owned_root(run_root, run_id)
    path = root / "interaction_events.jsonl"
    with _WRITE_LOCK:
        if seq is None:
            seq = 1
            if path.is_file():
                with path.open("rb") as stream:
                    lines = stream.readlines()
                if lines:
                    seq = int(json.loads(lines[-1]).get("seq", 0)) + 1
        if seq < 1:
            raise ValueError("seq must be positive")
        event = {
            "schema_version": 1, "case_id": CASE_ID, "run_id": run_id,
            "seq": seq, "actor_id": actor_id, "event_type": event_type,
            "timestamp_monotonic_ns": int(blender_state.get("sampled_monotonic_ns", time.monotonic_ns())),
            "action_id": action_id, "action_label": action_label,
            "capture_method": capture_method, "atomic_with_input": False,
            "causality_limit": "state was sampled at adapter boundary; this is not an atomic key-event trace",
            "blender_state": {key: value for key, value in blender_state.items()
                              if key != "sampled_monotonic_ns"},
        }
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def append_action_boundary(run_root: str | Path, *, run_id: str, actor_id: str,
                           action_id: str, action_label: str,
                           before: dict[str, Any], after: dict[str, Any]) -> Path:
    """Log pre/post state supplied by the serialized desktop executor."""
    before_ns = int(before.get("sampled_monotonic_ns", 0))
    after_ns = int(after.get("sampled_monotonic_ns", 0))
    if after_ns < before_ns:
        raise ValueError("post-action sample predates pre-action sample")
    first = append_event(run_root, run_id=run_id, actor_id=actor_id,
                         event_type="action_start", blender_state=before,
                         action_id=action_id, action_label=action_label)
    append_event(run_root, run_id=run_id, actor_id=actor_id,
                 event_type="action_end", blender_state=after,
                 action_id=action_id, action_label=action_label)
    return first
