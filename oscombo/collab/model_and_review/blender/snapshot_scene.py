"""Read-only extraction of a normalized snapshot from the currently open .blend.

This script only reads bpy data and writes a JSON snapshot to the requested
temporary path. It does not alter the project, selection, mode, view, or file.
"""
from __future__ import annotations

import json
import hashlib
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(raw) != 2 or raw[0] != "--output":
        raise SystemExit("usage: snapshot_scene.py -- --output PATH")
    return Path(raw[1]).resolve()


def _round(values):
    return [round(float(value), 6) for value in values]


def _material_names(obj):
    return [slot.material.name for slot in obj.material_slots if slot.material]


def _material_colors():
    out = {}
    for material in bpy.data.materials:
        if not material.use_nodes or not material.node_tree:
            continue
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled:
            out[material.name] = _round(principled.inputs["Base Color"].default_value)
    return out


def _shade_profile(obj):
    if not obj or obj.name != "Lamp_Shade" or obj.type != "MESH" or not obj.data.vertices:
        return {}
    scale_x, scale_y, scale_z = (abs(float(value)) for value in obj.scale)
    z_values = [float(vertex.co.z) * scale_z for vertex in obj.data.vertices]
    z_min, z_max = min(z_values), max(z_values)
    epsilon = max(1e-5, (z_max - z_min) * 1e-4)
    bottom = [vertex for vertex in obj.data.vertices if abs(float(vertex.co.z) * scale_z - z_min) <= epsilon]
    top = [vertex for vertex in obj.data.vertices if abs(float(vertex.co.z) * scale_z - z_max) <= epsilon]
    radii = lambda vertices: [math.hypot(float(v.co.x) * scale_x, float(v.co.y) * scale_y)
                              for v in vertices]
    bottom_radii, top_radii = radii(bottom), radii(top)
    return {"inner_radius_bottom_m": round(min(bottom_radii), 6),
            "outer_radius_bottom_m": round(max(bottom_radii), 6),
            "inner_radius_top_m": round(min(top_radii), 6),
            "outer_radius_top_m": round(max(top_radii), 6),
            "z_min_local_m": round(z_min, 6), "z_max_local_m": round(z_max, 6)}


def _canonical_mesh_digest(obj):
    """Hash mesh geometry independent of Blender's vertex/edge index ordering.

    Blender may emit equivalent primitive meshes with different index order in
    separate processes. Coordinates are rounded at the same 1e-6 m precision
    used by snapshots; face cycles retain winding while allowing cyclic starts.
    """
    vertices = [tuple(round(float(c), 6) for c in vertex.co) for vertex in obj.data.vertices]

    def canonical_cycle(indices):
        cycle = tuple(vertices[index] for index in indices)
        rotations = [cycle[offset:] + cycle[:offset] for offset in range(len(cycle))]
        return min(rotations)

    edges = sorted(tuple(sorted((vertices[edge.vertices[0]], vertices[edge.vertices[1]])))
                   for edge in obj.data.edges)
    faces = sorted(canonical_cycle(poly.vertices) for poly in obj.data.polygons)
    canonical = {"vertices": sorted(vertices), "edges": edges, "faces": faces}
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def snapshot():
    scene = bpy.context.scene
    rows = []
    for obj in scene.objects:
        row = {"name": obj.name, "type": obj.type,
               "location": _round(obj.matrix_world.translation),
               "dimensions": _round(obj.dimensions),
               "rotation_euler": _round(obj.matrix_world.to_euler()),
               "scale": _round(obj.scale),
               "materials": _material_names(obj)}
        if obj.type == "MESH":
            row["geometry_sha256"] = _canonical_mesh_digest(obj)
            row["mesh_vertex_count"] = len(obj.data.vertices)
            row["mesh_polygon_count"] = len(obj.data.polygons)
        if obj.type == "CAMERA":
            row["lens_mm"] = round(float(obj.data.lens), 6)
        elif obj.type == "LIGHT":
            row.update({"light_type": obj.data.type,
                        "power_w": round(float(obj.data.energy), 6),
                        "size_m": round(float(obj.data.size), 6),
                        "color": _round(obj.data.color)})
            direction = Vector((0.0, 0.0, 1.5)) - obj.matrix_world.translation
            axis = obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
            row["target_alignment_dot"] = round(float(axis.normalized().dot(direction.normalized())), 8)
        rows.append(row)

    camera = scene.camera
    alignment = -1.0
    if camera:
        target = Vector((0.0, 0.0, 1.45)) - camera.matrix_world.translation
        direction = camera.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        if target.length and direction.length:
            alignment = float(direction.normalized().dot(target.normalized()))

    return {"schema_version": 1, "scene_name": scene.name,
            "objects": sorted(rows, key=lambda row: row["name"]),
            "active_camera": camera.name if camera else None,
            "material_colors": _material_colors(),
            "shade_profile": _shade_profile(scene.objects.get("Lamp_Shade")),
            "camera_target_alignment_dot": round(alignment, 8)}


def main():
    output = _args()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"READ_ONLY_SCENE_SNAPSHOT path={output}")


if __name__ == "__main__":
    main()
