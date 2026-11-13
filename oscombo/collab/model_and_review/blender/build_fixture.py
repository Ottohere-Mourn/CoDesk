"""Build a genuine deterministic Blender fixture using Blender's bundled bpy.

Run only on a machine with Blender installed, for example:
  blender --background --factory-startup --python build_fixture.py -- \
    --output /path/to/run/workspace/project/StudioLamp_Review.blend --variant initial

This source file is not itself a .blend fixture. It writes a genuine project
only when invoked by Blender's bundled Python runtime.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT))
from oscombo.collab.model_and_review.blend_format import has_blend_container_header_at  # noqa: E402
from oscombo.collab.model_and_review import spec  # noqa: E402


def _args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--variant", choices=("initial", "gold"), default="initial")
    return parser.parse_args(raw)


def _material(name: str, color: tuple[float, float, float, float], *, metallic: float, roughness: float):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    return material


def _mesh_object(name: str, vertices: list[tuple[float, float, float]], faces: list[tuple[int, ...]], material):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def _cylinder(name: str, radius: float, z0: float, z1: float, material, segments: int = 32):
    center_z = (z0 + z1) / 2
    vertices = []
    for z in (z0, z1):
        vertices.extend((radius * math.cos(2 * math.pi * i / segments),
                         radius * math.sin(2 * math.pi * i / segments), z - center_z) for i in range(segments))
    faces = [tuple(reversed(range(segments))), tuple(range(segments, 2 * segments))]
    faces.extend((i, (i + 1) % segments, segments + (i + 1) % segments, segments + i)
                 for i in range(segments))
    obj = _mesh_object(name, vertices, faces, material)
    obj.location.z = center_z
    return obj


def _shade(name: str, z_center: float, profile: dict, segments: int = 48):
    rings = ((profile["inner_radius_bottom_m"], profile["z_min_local_m"]),
             (profile["outer_radius_bottom_m"], profile["z_min_local_m"]),
             (profile["inner_radius_top_m"], profile["z_max_local_m"]),
             (profile["outer_radius_top_m"], profile["z_max_local_m"]))
    vertices: list[tuple[float, float, float]] = []
    for radius, z in rings:
        vertices.extend((radius * math.cos(2 * math.pi * i / segments),
                         radius * math.sin(2 * math.pi * i / segments), z) for i in range(segments))
    faces = []
    # Inner and outer frustum walls plus top/bottom annular rims.
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, 2 * segments + j, 2 * segments + i))
        faces.append((segments + i, 3 * segments + i, 3 * segments + j, segments + j))
        faces.append((i, segments + i, segments + j, j))
        faces.append((2 * segments + i, 2 * segments + j, 3 * segments + j, 3 * segments + i))
    material = bpy.data.materials.get("Mat_Deep_Green")
    obj = _mesh_object(name, vertices, faces, material)
    obj.location.z = z_center
    return obj


def _area_light(name: str, location, energy: float, size: float):
    data = bpy.data.lights.new(name + "Data", type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = spec.GOLD_LIGHT_COLORS[name]
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = Vector(spec.GOLD_OBJECTS[name]["target"]) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def build_scene(variant: str) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights, bpy.data.materials):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)

    for name, color in spec.GOLD_MATERIAL_COLORS.items():
        _material(name, color, metallic=0.0, roughness=0.36)

    base = spec.GOLD_OBJECTS["Lamp_Base"]
    _cylinder("Lamp_Base", base["dimensions"][0] / 2,
              base["location"][2] - base["dimensions"][2] / 2,
              base["location"][2] + base["dimensions"][2] / 2,
              bpy.data.materials[base["materials"][0]])
    stem = spec.GOLD_OBJECTS["Lamp_Stem"]
    _cylinder("Lamp_Stem", stem["dimensions"][0] / 2,
              stem["location"][2] - stem["dimensions"][2] / 2,
              stem["location"][2] + stem["dimensions"][2] / 2,
              bpy.data.materials[stem["materials"][0]])
    bulb_spec = spec.GOLD_OBJECTS["Lamp_Bulb"]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12,
                                        radius=bulb_spec["dimensions"][0] / 2,
                                        location=bulb_spec["location"])
    bulb = bpy.context.object
    bulb.name = "Lamp_Bulb"
    bulb.data.name = "Lamp_BulbMesh"
    bulb.data.materials.append(bpy.data.materials[bulb_spec["materials"][0]])

    if variant == "gold":
        shade_spec = spec.GOLD_OBJECTS["Lamp_Shade"]
        shade = _shade("Lamp_Shade", shade_spec["location"][2], spec.GOLD_SHADE_PROFILE)
        camera_spec = spec.GOLD_OBJECTS["Camera_Main"]
        light_specs = spec.GOLD_OBJECTS
    else:
        shade_spec = {"location": (0.0, 0.0, 2.4)}
        shade = _shade("Lamp_Shade", shade_spec["location"][2], spec.INITIAL_SHADE_PROFILE)
        camera_spec = spec.INITIAL_CAMERA
        light_specs = spec.INITIAL_LIGHTS
    floor_spec = spec.GOLD_OBJECTS["Studio_Floor"]
    bpy.ops.mesh.primitive_plane_add(size=floor_spec["dimensions"][0],
                                     location=floor_spec["location"])
    floor = bpy.context.object
    floor.name = "Studio_Floor"
    floor.data.name = "Studio_FloorMesh"
    floor.data.materials.append(bpy.data.materials[floor_spec["materials"][0]])

    camera_data = bpy.data.cameras.new("Camera_MainData")
    camera_data.lens = camera_spec["lens_mm"]
    camera = bpy.data.objects.new("Camera_Main", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = camera_spec["location"]
    camera.rotation_euler = (Vector(camera_spec["target"]) - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    for name in ("Key_Light", "Fill_Light", "Rim_Light"):
        light = light_specs[name]
        _area_light(name, light["location"], light["power_w"], light["size_m"])

    scene = bpy.context.scene
    scene.name = "StudioLamp_Review"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    # Return the fixture to a predictable, easy-to-inspect Object Mode state.
    bpy.ops.object.select_all(action="DESELECT")
    shade.select_set(True)
    bpy.context.view_layer.objects.active = shade
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def main() -> None:
    args = _args()
    target = Path(args.output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    build_scene(args.variant)
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    if not has_blend_container_header_at(target):
        raise RuntimeError("Blender did not produce a valid plain or compressed .blend header")
    with target.open("rb") as stream:
        compressed = stream.read(4) == b"\x28\xb5\x2f\xfd"
    print(f"CREATED_REAL_BLEND variant={args.variant} path={target} bytes={target.stat().st_size} "
          f"compressed={compressed}")


if __name__ == "__main__":
    main()
