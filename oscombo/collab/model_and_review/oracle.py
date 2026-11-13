"""Programmatic oracle for a Blender scene snapshot or a real .blend file.

The pure snapshot oracle is runnable without Blender. ``evaluate_blend_file``
uses Blender's own bpy API and must be run on a host with Blender installed.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from . import CASE_ID
from . import spec
from .blend_format import has_blend_container_header_at

SCHEMA_VERSION = 1
TOLERANCE = 1e-4


def _close(actual: float, expected: float, tolerance: float = TOLERANCE) -> bool:
    try:
        return math.isfinite(float(actual)) and abs(float(actual) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def _vec_close(actual: Any, expected: Any, tolerance: float = TOLERANCE) -> bool:
    return (isinstance(actual, (list, tuple)) and len(actual) == len(expected)
            and all(_close(a, b, tolerance) for a, b in zip(actual, expected)))


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _protected_fingerprint(row: dict[str, Any]) -> dict[str, Any]:
    keys = ("type", "location", "dimensions", "rotation_euler", "scale", "materials", "geometry_sha256")
    return {key: row.get(key) for key in keys}


def evaluate_snapshot(snapshot: dict[str, Any], *,
                      baseline_protected: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Evaluate a normalized scene snapshot; accepts no hidden runtime state."""
    checks: list[dict[str, Any]] = []
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        return {"case_id": CASE_ID, "status": "FAIL", "checks": [
            _check("snapshot_schema", False, f"expected schema {SCHEMA_VERSION}")],
            "actor_subscores": {"A_geometry": False, "B_review_presentation": False}}

    objects_raw = snapshot.get("objects", [])
    objects = {row.get("name"): row for row in objects_raw if isinstance(row, dict)}
    names_ok = (len(objects) == len(objects_raw) and set(objects) == set(spec.OBJECT_NAMES))
    checks.append(_check("exact_object_inventory", names_ok,
                         f"expected {sorted(spec.OBJECT_NAMES)}, got {sorted(objects)}"))

    geometry_checks: list[bool] = []
    for name, expected in spec.GOLD_OBJECTS.items():
        actual = objects.get(name, {})
        if expected["type"] == "MESH":
            ok = (actual.get("type") == "MESH"
                  and _vec_close(actual.get("location"), expected["location"])
                  and _vec_close(actual.get("dimensions"), expected["dimensions"])
                  and _vec_close(actual.get("rotation_euler", (0, 0, 0)), expected.get("rotation_euler", (0, 0, 0)))
                  and (name == "Lamp_Shade" or
                       _vec_close(actual.get("scale", (1, 1, 1)), expected.get("scale", (1, 1, 1))))
                  and tuple(actual.get("materials", ())) == expected["materials"])
            if name in spec.PROTECTED_OBJECTS and baseline_protected is not None:
                ok = ok and _protected_fingerprint(actual) == baseline_protected.get(name)
            geometry_checks.append(ok)
            checks.append(_check(f"object:{name}", ok,
                                 "type/location/dimensions/material match gold" if ok else
                                 f"expected {expected}, got {actual}"))

    material_colors = snapshot.get("material_colors", {})
    for material, expected_color in spec.GOLD_MATERIAL_COLORS.items():
        ok = _vec_close(material_colors.get(material), expected_color)
        geometry_checks.append(ok)
        checks.append(_check(f"material:{material}", ok,
                             "base color matches gold" if ok else
                             f"expected {expected_color}, got {material_colors.get(material)}"))

    profile = snapshot.get("shade_profile", {})
    profile_ok = all(_close(profile.get(key), value)
                     for key, value in spec.GOLD_SHADE_PROFILE.items())
    geometry_checks.append(profile_ok)
    checks.append(_check("shade_mesh_profile", profile_ok,
                         "inner/outer frustum radii and local z bounds match gold" if profile_ok else
                         f"expected {spec.GOLD_SHADE_PROFILE}, got {profile}"))
    bulb = objects.get("Lamp_Bulb", {})
    shade = objects.get("Lamp_Shade", {})
    shade_topology_ok = (shade.get("mesh_vertex_count") == spec.GOLD_SHADE_TOPOLOGY["vertex_count"]
                         and shade.get("mesh_polygon_count") == spec.GOLD_SHADE_TOPOLOGY["polygon_count"])
    geometry_checks.append(shade_topology_ok)
    checks.append(_check("shade_mesh_topology", shade_topology_ok,
                         "open frustum mesh topology matches generator" if shade_topology_ok else
                         f"expected {spec.GOLD_SHADE_TOPOLOGY}, got "
                         f"vertices={shade.get('mesh_vertex_count')} polygons={shade.get('mesh_polygon_count')}"))
    bulb_loc = bulb.get("location", (math.nan, math.nan, math.nan))
    bulb_dims = bulb.get("dimensions", (math.nan, math.nan, math.nan))
    shade_loc = shade.get("location", (math.nan, math.nan, math.nan))
    shade_dims = shade.get("dimensions", (math.nan, math.nan, math.nan))
    try:
        z_min = float(shade_loc[2]) - float(shade_dims[2]) / 2
        z_max = float(shade_loc[2]) + float(shade_dims[2]) / 2
        bulb_z_min = float(bulb_loc[2]) - float(bulb_dims[2]) / 2
        bulb_z_max = float(bulb_loc[2]) + float(bulb_dims[2]) / 2
        bulb_radius = max(float(bulb_dims[0]), float(bulb_dims[1])) / 2
        z_fraction = (float(bulb_loc[2]) - z_min) / (z_max - z_min)
        inner_bottom = float(profile["inner_radius_bottom_m"])
        inner_top = float(profile["inner_radius_top_m"])
        inner_at_bulb = inner_bottom + z_fraction * (inner_top - inner_bottom)
        radial_clearance = inner_at_bulb - bulb_radius
        vertical_clearance = min(bulb_z_min - z_min, z_max - bulb_z_max)
        clearance_valid = (0.0 <= z_fraction <= 1.0
                           and radial_clearance >= spec.MIN_RADIAL_CLEARANCE_M
                           and vertical_clearance >= spec.MIN_VERTICAL_CLEARANCE_M)
        clearance_detail = (f"radial={radial_clearance:.4f}m, vertical={vertical_clearance:.4f}m; "
                            f"required >= {spec.MIN_RADIAL_CLEARANCE_M:.2f}m / "
                            f"{spec.MIN_VERTICAL_CLEARANCE_M:.2f}m")
    except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
        clearance_valid, clearance_detail = False, "missing or invalid shade/bulb profile"
    geometry_checks.append(clearance_valid)
    checks.append(_check("bulb_clearance", clearance_valid, clearance_detail))

    camera = objects.get("Camera_Main", {})
    camera_expected = spec.GOLD_OBJECTS["Camera_Main"]
    camera_ok = (camera.get("type") == "CAMERA" and snapshot.get("active_camera") == "Camera_Main"
                 and _vec_close(camera.get("location"), camera_expected["location"])
                 and _close(camera.get("lens_mm"), camera_expected["lens_mm"])
                 and _close(snapshot.get("camera_target_alignment_dot", -1.0), 1.0, 1e-3))
    checks.append(_check("camera_presentation", camera_ok,
                         "location/lens and aim at target match" if camera_ok else
                         f"camera state does not match target: {camera}"))

    presentation_checks = [camera_ok]
    for name in ("Key_Light", "Fill_Light", "Rim_Light"):
        expected = spec.GOLD_OBJECTS[name]
        actual = objects.get(name, {})
        color_ok = _vec_close(actual.get("color"), spec.GOLD_LIGHT_COLORS[name])
        ok = (actual.get("type") == "LIGHT" and actual.get("light_type") == "AREA"
              and _vec_close(actual.get("location"), expected["location"])
              and _close(actual.get("power_w"), expected["power_w"])
              and _close(actual.get("size_m"), expected["size_m"]) and color_ok
              and _close(actual.get("target_alignment_dot", -1.0), 1.0, 1e-3))
        presentation_checks.append(ok)
        checks.append(_check(f"light:{name}", ok,
                             "type/location/power/size/color match gold" if ok else
                             f"expected {expected} and color {spec.GOLD_LIGHT_COLORS[name]}, got {actual}"))

    scene_ok = snapshot.get("scene_name") == spec.SCENE_NAME
    checks.append(_check("scene_identity", scene_ok,
                         f"expected {spec.SCENE_NAME}, got {snapshot.get('scene_name')}"))
    geometry_ok = bool(geometry_checks) and all(geometry_checks) and names_ok and scene_ok
    presentation_ok = all(presentation_checks) and scene_ok
    passed = geometry_ok and presentation_ok
    return {
        "case_id": CASE_ID,
        "oracle_version": "1.0.0",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "actor_subscores": {"A_geometry": geometry_ok, "B_review_presentation": presentation_ok},
        "measured": {
            "bulb_radial_clearance_m": radial_clearance if "radial_clearance" in locals() else None,
            "bulb_vertical_clearance_m": vertical_clearance if "vertical_clearance" in locals() else None,
        },
        "limitations": ["visual quality is not judged by the structural oracle",
                        "task-process collaboration is reported separately from final artifact success"],
    }


def extract_blend_snapshot(blend_path: str | Path, blender_bin: str | None = None) -> dict[str, Any]:
    """Open a genuine .blend in background Blender and return its read-only snapshot."""
    input_blend = Path(blend_path)
    if input_blend.is_symlink():
        raise PermissionError(f"refusing symlinked Blender artifact: {input_blend}")
    blend = input_blend.resolve()
    if not blend.is_file():
        raise FileNotFoundError(f"missing or symlinked Blender artifact: {blend}")
    if not has_blend_container_header_at(blend):
        raise ValueError(f"artifact is not a Blender .blend container: {blend}")
    executable = blender_bin or shutil.which("blender")
    if not executable:
        raise RuntimeError("Blender executable is unavailable; real .blend oracle is pending")
    snapshot_script = Path(__file__).with_name("blender") / "snapshot_scene.py"
    with tempfile.TemporaryDirectory(prefix="codesk-mar-oracle-") as temp_dir:
        staged_blend = Path(temp_dir) / "input.blend"
        shutil.copy2(blend, staged_blend)
        output = Path(temp_dir) / "scene_snapshot.json"
        command = [executable, "--background", str(staged_blend), "--python", str(snapshot_script),
                   "--", "--output", str(output)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError("Blender snapshot extraction failed: " +
                               (completed.stderr[-4000:] or completed.stdout[-4000:]))
        return json.loads(output.read_text(encoding="utf-8"))


def evaluate_blend_file(blend_path: str | Path, blender_bin: str | None = None, *,
                        baseline_protected: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Open a genuine .blend with Blender, then evaluate its bpy-derived snapshot."""
    snapshot = extract_blend_snapshot(blend_path, blender_bin)
    return evaluate_snapshot(snapshot, baseline_protected=baseline_protected)
