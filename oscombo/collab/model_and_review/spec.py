"""Public task contract and private deterministic gold for CDD-MAR-001."""
from __future__ import annotations

from . import CASE_ID, CASE_VERSION, CONDITIONS

TEMPLATE_BLEND_RELATIVE = "project/StudioLamp_Review.blend"
FINAL_BLEND_RELATIVE = "deliverables/StudioLamp_Final.blend"
PUBLIC_BRIEF_RELATIVE = "brief.md"
SCENE_NAME = "StudioLamp_Review"

ACTOR_A_INSTRUCTION = """You are A, the geometry owner for the Studio Lamp product scene. Read the complete brief and inspect the entire supplied Blender scene. Adjust only `Lamp_Shade` so its outside dimensions are 1.50 m × 1.50 m × 0.80 m and its center is at (0, 0, 2.50 m). Preserve its material and shape; keep the stem, base, bulb, floor, camera and lights intact. Check that the bulb remains inside the shade with visible clearance. Save the current project checkpoint to the requested final project path before handing control over. You may inspect all objects and may send B a message or an attachment when useful. If B reports a concrete geometry or clearance issue, correct it and save a new checkpoint. Do not alter camera or lighting settings."""

ACTOR_B_INSTRUCTION = """You are B, the scene reviewer and presentation owner for the Studio Lamp product scene. Read the complete brief and inspect the full Blender scene, including A's geometry change. Verify the shade dimensions, its fit around the bulb, and preservation of the other lamp parts. Set `Camera_Main` to the specified presentation view and lens, and set the three specified area lights to their target positions and values. Preserve all geometry and materials. Save the finished project as `deliverables/StudioLamp_Final.blend`. You may ask A to correct a concrete geometry or clearance issue and may send a review attachment when useful; no message count or timing is prescribed. Do not infer success from the viewport alone: save the project and let the independent scene oracle check it."""

SINGLE_AGENT_INSTRUCTION = """You are S, responsible for the complete Studio Lamp scene. Follow the brief: adjust only `Lamp_Shade` to the target dimensions and position, verify its clearance around `Lamp_Bulb`, then set the specified camera and three lights. Preserve all non-target geometry and materials. Save `deliverables/StudioLamp_Final.blend`. You may use the collaboration message/attachment interface for a review note, but success is based on the saved Blender project and independent oracle, not message count or viewport appearance."""

PUBLIC_BRIEF = """# Studio Lamp: geometry review and product presentation

Complete the supplied real Blender scene as a compact product presentation. All dimensions are in meters. The scene contains a lamp base, stem, shade, bulb, floor, camera and three area lights. The scene catalog and this brief are available to every actor; no specification is hidden.

## Geometry target

Adjust `Lamp_Shade` to outside dimensions **1.50 × 1.50 × 0.80 m**, centered at **(0, 0, 2.50 m)**. Keep its existing open frustum shape and `Mat_Deep_Green` material. The bulb must remain inside the shade with at least **0.40 m radial clearance** from the inner shade wall at the bulb center, and at least **0.10 m vertical clearance** from the shade opening/rim. Preserve the base, stem, bulb and floor exactly.

## Presentation target

Use `Camera_Main` at **(4.20, -6.00, 3.20)**, aimed at the lamp center **(0, 0, 1.45)**, with **50 mm** focal length. Use area lights with these values:

| Object | Location (m) | Power | Size |
| --- | --- | ---: | ---: |
| `Key_Light` | (3, -4, 5) | 450 W | 4 m |
| `Fill_Light` | (-3, -1, 3) | 160 W | 3 m |
| `Rim_Light` | (0, 3, 4) | 320 W | 2 m |

Keep the supplied light colors and all lamp geometry/materials unchanged. Save the finished, reopenable Blender project as `deliverables/StudioLamp_Final.blend`.

## Work roles

A owns the shade geometry; B owns the camera and light setup and independently reviews the geometry. Both can inspect all specifications and scene objects. Their role split is an editing responsibility, not an information restriction. They may exchange findings or corrections when useful. No simultaneous editing, fixed message count, or forced conflict is required."""

# Private oracle values. Do not mount this module or fixtures/gold_state.json into
# an Actor's workspace. Values are duplicated in a readable private manifest.
GOLD_OBJECTS = {
    "Lamp_Base": {"type": "MESH", "location": (0.0, 0.0, 0.09),
                   "dimensions": (1.2, 1.2, 0.18), "rotation_euler": (0.0, 0.0, 0.0),
                   "scale": (1.0, 1.0, 1.0), "materials": ("Mat_Porcelain",)},
    "Lamp_Stem": {"type": "MESH", "location": (0.0, 0.0, 1.14),
                   "dimensions": (0.12, 0.12, 1.92), "rotation_euler": (0.0, 0.0, 0.0),
                   "scale": (1.0, 1.0, 1.0), "materials": ("Mat_Brass",)},
    "Lamp_Shade": {"type": "MESH", "location": (0.0, 0.0, 2.5),
                    "dimensions": (1.5, 1.5, 0.8), "rotation_euler": (0.0, 0.0, 0.0),
                    "scale": (1.0, 1.0, 1.0), "materials": ("Mat_Deep_Green",)},
    "Lamp_Bulb": {"type": "MESH", "location": (0.0, 0.0, 2.35),
                   "dimensions": (0.24, 0.24, 0.24), "rotation_euler": (0.0, 0.0, 0.0),
                   "scale": (1.0, 1.0, 1.0), "materials": ("Mat_Warm_Glass",)},
    "Studio_Floor": {"type": "MESH", "location": (0.0, 0.0, 0.0),
                      "dimensions": (12.0, 12.0, 0.0), "rotation_euler": (0.0, 0.0, 0.0),
                      "scale": (1.0, 1.0, 1.0), "materials": ("Mat_Floor",)},
    "Camera_Main": {"type": "CAMERA", "location": (4.2, -6.0, 3.2), "lens_mm": 50.0,
                    "target": (0.0, 0.0, 1.45)},
    "Key_Light": {"type": "LIGHT", "location": (3.0, -4.0, 5.0), "light_type": "AREA",
                   "power_w": 450.0, "size_m": 4.0, "target": (0.0, 0.0, 1.5)},
    "Fill_Light": {"type": "LIGHT", "location": (-3.0, -1.0, 3.0), "light_type": "AREA",
                    "power_w": 160.0, "size_m": 3.0, "target": (0.0, 0.0, 1.5)},
    "Rim_Light": {"type": "LIGHT", "location": (0.0, 3.0, 4.0), "light_type": "AREA",
                   "power_w": 320.0, "size_m": 2.0, "target": (0.0, 0.0, 1.5)},
}

GOLD_LIGHT_COLORS = {
    "Key_Light": (1.0, 0.92, 0.82),
    "Fill_Light": (0.72, 0.82, 1.0),
    "Rim_Light": (1.0, 0.72, 0.48),
}

GOLD_MATERIAL_COLORS = {
    "Mat_Porcelain": (0.78, 0.84, 0.88, 1.0),
    "Mat_Brass": (0.62, 0.36, 0.12, 1.0),
    "Mat_Deep_Green": (0.035, 0.20, 0.12, 1.0),
    "Mat_Warm_Glass": (1.0, 0.66, 0.28, 1.0),
    "Mat_Floor": (0.24, 0.27, 0.30, 1.0),
}

GOLD_SHADE_PROFILE = {
    "inner_radius_bottom_m": 0.56,
    "outer_radius_bottom_m": 0.60,
    "inner_radius_top_m": 0.70,
    "outer_radius_top_m": 0.75,
    "z_min_local_m": -0.4,
    "z_max_local_m": 0.4,
}
GOLD_SHADE_TOPOLOGY = {"vertex_count": 192, "polygon_count": 192}
INITIAL_SHADE_PROFILE = {
    "inner_radius_bottom_m": 0.448,
    "outer_radius_bottom_m": 0.48,
    "inner_radius_top_m": 0.56,
    "outer_radius_top_m": 0.60,
    "z_min_local_m": -0.3,
    "z_max_local_m": 0.3,
}
INITIAL_CAMERA = {"location": (5.0, -7.0, 4.0), "lens_mm": 38.0,
                  "target": (0.0, 0.0, 1.45)}
INITIAL_LIGHTS = {
    "Key_Light": {"location": (3.0, -4.0, 5.0), "power_w": 320.0, "size_m": 4.0},
    "Fill_Light": {"location": (-3.0, -1.0, 3.0), "power_w": 120.0, "size_m": 3.0},
    "Rim_Light": {"location": (0.0, 3.0, 4.0), "power_w": 220.0, "size_m": 2.0},
}
BULB_RADIUS_M = 0.12
MIN_RADIAL_CLEARANCE_M = 0.40
MIN_VERTICAL_CLEARANCE_M = 0.10
PROTECTED_OBJECTS = ("Lamp_Base", "Lamp_Stem", "Lamp_Bulb", "Studio_Floor")
PROTECTED_MATERIALS = tuple(GOLD_MATERIAL_COLORS)
OBJECT_NAMES = tuple(GOLD_OBJECTS)

CONDITION_SEMANTICS = {
    "single_agent": "one desktop and one integrated actor; same canonical episode artifact store",
    "collaborative_isolated": "two independent Blender desktop sessions; same canonical saved .blend artifact store and serialized save lease",
    "collaborative_shared": "one live Blender desktop session alternated between A and B; same canonical saved .blend artifact store and serialized save lease",
}
