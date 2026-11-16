"""Docker-side authoring, scripted references and native inspection for p4."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


NATIVE = "HingeStudio.blend"
FRAMES = (1, 16, 31, 46, 61)


def rounded(values):
    return [round(float(value), 6) for value in values]


def linear_color(hex_color):
    channels = [int(hex_color[offset:offset + 2], 16) / 255 for offset in (0, 2, 4)]
    return [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels] + [1.0]


def material(name, color):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = (*color, 1)
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.7
    return result


def cube(name, dimensions, location, surface):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    result = bpy.context.object
    result.name = name
    result.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    result.data.materials.append(surface)
    return result


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def build(root):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    box_surface = material("BoxFinish", (0.32, 0.18, 0.07))
    cube("CaseBase", (1.6, 1.2, 0.7), (-1.5, 0, 0.35), box_surface)
    lid = cube("CaseLid", (1.7, 1.3, 0.12), (-1.5, 0.65, 0.76), box_surface)
    for vertex in lid.data.vertices:
        vertex.co.y -= 0.65
    cube("ShellBody", (1.3, 1.0, 0.9), (1.5, 0, 0.45), material("ShellFinish", (0.35, 0.35, 0.35)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.24, depth=0.08,
                                      location=(1.5, -0.54, 0.5), rotation=(math.pi / 2, 0, 0))
    dial = bpy.context.object
    dial.name = "ControlDial"
    dial.data.materials.append(material("DialFinish", (0.35, 0.35, 0.35)))
    cube("StudioFloor", (200, 200, 0.1), (0, 0, -0.05), material("FloorFinish", (0.12, 0.16, 0.22)))
    bpy.ops.object.camera_add(location=(5, -8, 5))
    camera = bpy.context.object
    camera.name = "InspectionCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 6.8
    aim(camera, (0, 0, 0.6))
    scene = bpy.context.scene
    scene.camera = camera
    for name, location, energy, size in (
            ("Key", (1, -3, 6), 650, 5), ("Fill", (-4, -1, 3), 300, 4)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.size = size
        aim(light, (0, 0, 0.5))
    scene.world = bpy.data.worlds.new("StudioWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
    scene.frame_start, scene.frame_end = 1, 61
    scene.render.fps = 24
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_gtao = True
    scene.render.resolution_x, scene.render.resolution_y = 960, 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.unit_settings.system = "METRIC"
    scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    lid.select_set(True)
    bpy.context.view_layer.objects.active = lid
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    save(root)


def save(root):
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(root / NATIVE))


def reference_a(root):
    lid = bpy.data.objects["CaseLid"]
    lid.rotation_mode = "XYZ"
    lid.animation_data_clear()
    for frame, angle in ((1, 0), (31, -60), (61, 0)):
        lid.rotation_euler = (math.radians(angle), 0, 0)
        lid.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    for curve in lid.animation_data.action.fcurves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
    bpy.context.scene.frame_set(1)
    save(root)


def reference_b(root):
    for name, color, roughness, metallic in (
            ("ShellFinish", "185B7A", 0.32, 0.15), ("DialFinish", "E6B74A", 0.22, 0.80)):
        shader = bpy.data.materials[name].node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = linear_color(color)
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Metallic"].default_value = metallic
    save(root)


def shader_state(surface):
    nodes = surface.node_tree.nodes if surface.use_nodes else []
    shaders = [node for node in nodes if node.type == "BSDF_PRINCIPLED"]
    outputs = [node for node in nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output]
    connected = bool(len(shaders) == 1 and len(outputs) == 1 and
                     any(link.from_node == shaders[0] and link.to_node == outputs[0] and
                         link.to_socket.name == "Surface" for link in surface.node_tree.links))
    values = {}
    if len(shaders) == 1:
        for socket in shaders[0].inputs:
            if hasattr(socket, "default_value"):
                value = socket.default_value
                values[socket.name] = rounded(value) if hasattr(value, "__len__") else round(float(value), 6)
    links = sorted((link.from_node.type, link.from_socket.name, link.to_node.type, link.to_socket.name)
                   for link in surface.node_tree.links) if surface.use_nodes else []
    return {"connected": connected, "nodes": sorted(node.type for node in nodes),
            "links": links, "values": values}


def inspect(root):
    scene = bpy.context.scene
    scene.frame_set(1)
    objects = {}
    for obj in bpy.data.objects:
        record = {
            "type": obj.type, "location": rounded(obj.location), "scale": rounded(obj.scale),
            "rotation_mode": obj.rotation_mode, "rotation": rounded(obj.rotation_euler),
            "parent": obj.parent.name if obj.parent else None,
            "hide_render": obj.hide_render, "hide_viewport": obj.hide_viewport,
            "modifiers": [modifier.type for modifier in obj.modifiers],
            "constraints": [constraint.type for constraint in obj.constraints],
            "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
            "drivers": len(obj.animation_data.drivers) if obj.animation_data else 0,
        }
        if obj.name == "CaseLid":
            record.pop("rotation")
        else:
            record["has_animation"] = bool(obj.animation_data and obj.animation_data.action)
        if obj.type == "MESH":
            topology = {"vertices": [rounded(vertex.co) for vertex in obj.data.vertices],
                        "faces": [list(polygon.vertices) for polygon in obj.data.polygons]}
            record["mesh_sha256"] = hashlib.sha256(json.dumps(topology, sort_keys=True).encode()).hexdigest()
        elif obj.type == "LIGHT":
            record["light"] = [obj.data.type, round(obj.data.energy, 6), round(obj.data.size, 6), rounded(obj.data.color)]
        elif obj.type == "CAMERA":
            record["camera"] = [obj.data.type, round(obj.data.ortho_scale, 6), round(obj.data.lens, 6)]
        objects[obj.name] = record
    lid = bpy.data.objects.get("CaseLid")
    samples = {}
    for frame in FRAMES:
        scene.frame_set(frame)
        if lid:
            evaluated = lid.evaluated_get(bpy.context.evaluated_depsgraph_get())
            samples[str(frame)] = rounded(evaluated.matrix_world.to_euler("XYZ"))
    curves = []
    if lid and lid.animation_data and lid.animation_data.action:
        for curve in lid.animation_data.action.fcurves:
            curves.append({"path": curve.data_path, "index": curve.array_index,
                           "modifiers": len(curve.modifiers), "muted": curve.mute,
                           "keys": [{"frame": round(point.co.x, 6), "value": round(point.co.y, 6),
                                     "interpolation": point.interpolation} for point in curve.keyframe_points]})
    materials = {surface.name: shader_state(surface) for surface in bpy.data.materials}
    fixed_materials = json.loads(json.dumps(materials))
    for name in ("ShellFinish", "DialFinish"):
        for key in ("Base Color", "Roughness", "Metallic"):
            fixed_materials.get(name, {}).get("values", {}).pop(key, None)
    background = scene.world.node_tree.nodes.get("Background") if scene.world and scene.world.use_nodes else None
    scene_state = {
        "frames": [scene.frame_start, scene.frame_end], "fps": scene.render.fps,
        "fps_base": round(scene.render.fps_base, 6),
        "camera": scene.camera.name if scene.camera else None,
        "engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
        "view_transform": scene.view_settings.view_transform,
        "units": [scene.unit_settings.system, round(scene.unit_settings.scale_length, 6)],
        "world": [rounded(background.inputs["Color"].default_value), round(background.inputs["Strength"].default_value, 6)] if background else None,
    }
    external_dependencies = [library.filepath for library in bpy.data.libraries]
    external_dependencies += [image.filepath for image in bpy.data.images
                              if image.source == "FILE" and image.filepath and not image.packed_file]
    return {
        "native_reopened": True, "blender_version": bpy.app.version_string,
        "invariants": {"objects": objects, "materials": fixed_materials, "scene": scene_state},
        "motion": {"curves": curves, "samples": samples}, "materials": materials,
        "external_dependencies": external_dependencies,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "ref-a", "ref-b", "inspect", "render"))
    parser.add_argument("workspace", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if not Path("/.dockerenv").exists():
        parser.error("Run authoring only inside the professional Docker image")
    args.workspace.mkdir(parents=True, exist_ok=True)
    if args.operation == "build":
        build(args.workspace)
    else:
        bpy.ops.wm.open_mainfile(filepath=str(args.workspace / NATIVE))
        if args.operation == "ref-a":
            reference_a(args.workspace)
        elif args.operation == "ref-b":
            reference_b(args.workspace)
        elif args.operation == "render":
            bpy.context.scene.frame_set(31)
            bpy.context.scene.render.filepath = str(args.workspace / "inspection-frame31.png")
            bpy.ops.render.render(write_still=True)
    result = inspect(args.workspace) if args.operation == "inspect" else {"operation": args.operation}
    args.report.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
