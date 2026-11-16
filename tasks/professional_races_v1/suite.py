"""Deterministic fixtures, reference solvers, state probes, and graders for 4 professional-software race tasks."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ElementTree
from zipfile import ZipFile


TASK_CATALOG = [
    {
        "id": "PR-BLENDER-1",
        "software": "Blender 3.4.1",
        "canonical_project": "turntable_studio.blend",
        "gui_launch": ["blender", "/workspace/turntable_studio.blend"],
        "window_match": "Blender",
        "race_mechanisms": [
            "monolithic_blend_lost_update",
            "cycles_render_toctou_stale_frames",
            "live_gui_vs_cli_save_divergence",
        ],
        "title": "Cycles studio lighting signoff vs ECO-B304 hero bracket geometry & anodize revision",
    },
    {
        "id": "PR-QGIS-1",
        "software": "QGIS 3.22.16",
        "canonical_project": "watershed_ops.qgz",
        "gui_launch": ["qgis", "--nologo", "/workspace/watershed_ops.qgz"],
        "window_match": "QGIS",
        "race_mechanisms": [
            "qgz_project_zip_layer_or_layout_lost_update",
            "cross_table_culvert_to_runoff_stale_snapshot",
            "geopackage_sqlite_concurrent_write_contention",
        ],
        "title": "100-year subbasin runoff & PDF risk atlas vs emergency culvert blockage dispatch",
    },
    {
        "id": "PR-FREECAD-1",
        "software": "FreeCAD 0.20.2",
        "canonical_project": "actuator_mount.FCStd",
        "gui_launch": ["freecad", "/workspace/actuator_mount.FCStd"],
        "window_match": "FreeCAD",
        "race_mechanisms": [
            "fcstd_brep_archive_lost_update",
            "parametric_master_datum_step_mating_mismatch",
        ],
        "title": "Sliding-fit bearing spigot cap & STEP export vs ECO-119 thermal bore expansion",
    },
    {
        "id": "PR-INKSCAPE-1",
        "software": "Inkscape 1.2.2",
        "canonical_project": "panel_master.svg",
        "gui_launch": ["inkscape", "/workspace/panel_master.svg"],
        "window_match": "Inkscape",
        "race_mechanisms": [
            "svg_dom_read_modify_write_lost_update",
            "shared_defs_gradient_stale_dpi_proof_mismatch",
        ],
        "title": "Silkscreen callout stroke prep & 192-DPI proof vs shared brand gradient & HUD badge update",
    },
]

CATALOG_BY_ID = {entry["id"]: entry for entry in TASK_CATALOG}
SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
ElementTree.register_namespace("", SVG_NS)
ElementTree.register_namespace("inkscape", INKSCAPE_NS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_checked(command: list[str], env_extra: dict[str, str] | None = None, timeout_s: int = 180) -> subprocess.CompletedProcess:
    merged_env = dict(os.environ)
    merged_env.setdefault("QT_QPA_PLATFORM", "offscreen")
    merged_env.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-prof-races")
    runtime_dir = Path(merged_env["XDG_RUNTIME_DIR"])
    runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime_dir, 0o700)
    if env_extra:
        merged_env.update(env_extra)
    completed = subprocess.run(command, env=merged_env, capture_output=True, text=True, timeout=timeout_s)
    if completed.returncode != 0:
        raise RuntimeError(f"Command {command[:3]} failed ({completed.returncode}): {completed.stderr[-800:] or completed.stdout[-800:]}")
    return completed


def mean_rgb_diff(first_png: Path, second_png: Path) -> float:
    from PIL import Image

    with Image.open(first_png) as img_one, Image.open(second_png) as img_two:
        rgb_one = img_one.convert("RGB")
        rgb_two = img_two.convert("RGB")
        if rgb_one.size != rgb_two.size:
            return 255.0
        bytes_one = rgb_one.tobytes()
        bytes_two = rgb_two.tobytes()
        total_diff = sum(abs(val_a - val_b) for val_a, val_b in zip(bytes_one, bytes_two))
        return total_diff / max(1, len(bytes_one))


def build_blender_workspace(workspace: Path) -> dict:
    (workspace / "tickets").mkdir(parents=True, exist_ok=True)
    (workspace / "inputs").mkdir(parents=True, exist_ok=True)
    (workspace / "deliverables").mkdir(parents=True, exist_ok=True)
    write_json(
        workspace / "tickets/lighting_signoff_ticket.json",
        {
            "ticket_id": "VIZ-204",
            "scene": "/workspace/turntable_studio.blend",
            "key_light": {"object": "KeyLight", "energy_watts": 850.0, "color_rgb": [1.0, 0.90, 0.80]},
            "rim_light": {"object": "RimLight", "energy_watts": 420.0, "color_rgb": [0.80, 0.90, 1.0]},
            "camera": {"object": "TurntableCam", "focal_length_mm": 65.0},
            "render_engine": "CYCLES",
            "samples": 24,
            "use_denoising": False,
            "resolution": [640, 360],
            "frames": [1, 12],
            "output_pattern": "/workspace/deliverables/renders/frame_{frame:03d}.png",
            "signoff_json": "/workspace/deliverables/render_signoff.json",
        },
    )
    stress_rows = []
    for idx in range(1, 61):
        factor_val = 1.12 + (0.255 if idx == 42 else (idx % 7) * 0.02)
        stress_rows.append({"sample_id": f"LD-{idx:03d}", "axial_kn": round(18.0 + idx * 0.35, 2), "height_scale_factor": round(factor_val, 3)})
    with (workspace / "inputs/bracket_load_spectrum.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["sample_id", "axial_kn", "height_scale_factor"])
        writer.writeheader()
        writer.writerows(stress_rows)
    write_json(
        workspace / "tickets/eco_b304_geometry.json",
        {
            "eco_id": "ECO-B304",
            "scene": "/workspace/turntable_studio.blend",
            "target_object": "HeroBracket",
            "base_nominal_height_m": 1.20,
            "load_csv": "/workspace/inputs/bracket_load_spectrum.csv",
            "height_rule": "base_nominal_height_m * max(height_scale_factor) from load_csv",
            "bevel_width_m": 0.05,
            "material_name": "AnodizedMetal",
            "base_color_rgba": [0.10, 0.42, 0.85, 1.0],
            "roughness": 0.20,
            "verification_render_frame": 6,
            "verification_png": "/workspace/deliverables/eco_preview_f06.png",
            "summary_json": "/workspace/deliverables/eco_b304_applied.json",
        },
    )
    init_script = textwrap.dedent('''
        import bpy, math
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 24
        scene.cycles.use_denoising = False
        scene.render.resolution_x = 640
        scene.render.resolution_y = 360
        scene.render.resolution_percentage = 100
        scene.frame_start = 1
        scene.frame_end = 24

        bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0.0, 0.0, 0.0))
        floor_obj = bpy.context.active_object
        floor_obj.name = "StudioFloor"
        floor_mat = bpy.data.materials.new(name="FloorMat")
        floor_mat.use_nodes = True
        floor_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.18, 0.19, 0.21, 1.0)
        floor_obj.data.materials.append(floor_mat)

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.60))
        hero_obj = bpy.context.active_object
        hero_obj.name = "HeroBracket"
        hero_obj.scale = (0.90, 0.55, 1.20)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel_mod = hero_obj.modifiers.new(name="EdgeBevel", type="BEVEL")
        bevel_mod.width = 0.02
        bevel_mod.segments = 2
        hero_mat = bpy.data.materials.new(name="AnodizedMetal")
        hero_mat.use_nodes = True
        bsdf = hero_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.72, 0.72, 0.75, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.85
        bsdf.inputs["Roughness"].default_value = 0.45
        hero_obj.data.materials.append(hero_mat)

        hero_obj.rotation_euler = (0.0, 0.0, 0.0)
        hero_obj.keyframe_insert(data_path="rotation_euler", frame=1)
        hero_obj.rotation_euler = (0.0, 0.0, math.pi)
        hero_obj.keyframe_insert(data_path="rotation_euler", frame=24)

        key_data = bpy.data.lights.new(name="KeyLightData", type="AREA")
        key_data.energy = 150.0
        key_data.color = (1.0, 1.0, 1.0)
        key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
        key_obj.location = (2.8, -2.6, 3.2)
        key_obj.rotation_euler = (0.85, 0.0, 0.78)
        scene.collection.objects.link(key_obj)

        rim_data = bpy.data.lights.new(name="RimLightData", type="AREA")
        rim_data.energy = 80.0
        rim_data.color = (1.0, 1.0, 1.0)
        rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
        rim_obj.location = (-2.6, 2.4, 2.5)
        rim_obj.rotation_euler = (-0.75, 0.0, -0.78)
        scene.collection.objects.link(rim_obj)

        cam_data = bpy.data.cameras.new(name="TurntableCamData")
        cam_data.lens = 35.0
        cam_obj = bpy.data.objects.new(name="TurntableCam", object_data=cam_data)
        cam_obj.location = (0.0, -4.6, 1.85)
        cam_obj.rotation_euler = (1.28, 0.0, 0.0)
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj

        bpy.ops.wm.save_as_mainfile(filepath=r"''' + str(workspace / "turntable_studio.blend") + '''")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as script_file:
        script_file.write(init_script)
        script_path = Path(script_file.name)
    try:
        run_checked(["blender", "-b", "--python", str(script_path)], timeout_s=120)
    finally:
        script_path.unlink(missing_ok=True)
    return {"blend_sha256": sha256_file(workspace / "turntable_studio.blend")}


def build_qgis_workspace(workspace: Path) -> dict:
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "role_a").mkdir(parents=True, exist_ok=True)
    (workspace / "role_b").mkdir(parents=True, exist_ok=True)
    hyetograph_rows = [
        {"interval_min": idx * 10, "intensity_mm_hr": val}
        for idx, val in enumerate([12.0, 18.5, 29.0, 46.0, 31.5, 19.0], start=1)
    ]
    with (workspace / "role_a/storm_hyetograph.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["interval_min", "intensity_mm_hr"])
        writer.writeheader()
        writer.writerows(hyetograph_rows)
    dispatch_records = []
    blocked_ids = {"CV-02", "CV-05", "CV-09", "CV-11", "CV-14"}
    for idx in range(1, 17):
        cid = f"CV-{idx:02d}"
        ratio = round(0.84 + (idx % 3) * 0.05, 2) if cid in blocked_ids else round(0.18 + (idx % 5) * 0.11, 2)
        dispatch_records.append({"culvert_id": cid, "debris_blockage_ratio": ratio, "inspector": f"TEAM-{(idx % 3) + 1}"})
    write_json(
        workspace / "role_b/field_dispatch_log.json",
        {"dispatch_id": "FD-2026-88", "blockage_threshold": 0.80, "inspections": dispatch_records},
    )
    (workspace / "role_a/hydrology_runoff_spec.md").write_text(
        textwrap.dedent('''
        # Ticket HYD-401: Subbasin 100-Year Peak Runoff & Risk Atlas

        Update `/workspace/data/basin_network.gpkg` and `/workspace/watershed_ops.qgz`:
        1. Read `/workspace/role_a/storm_hyetograph.csv` and compute `rainfall_factor = max(intensity_mm_hr) / 100.0`.
        2. Join each feature in `subbasins` (`basin_id`, `area_ha`, `impervious_pct`, `culvert_id`) with its matching `culvert_id` in `culverts` (`status`, `capacity_cms`) inside `/workspace/data/basin_network.gpkg`.
        3. Compute `raw_q = area_ha * (impervious_pct / 100.0) * rainfall_factor`.
           - If the linked culvert has `status == 'OPEN'`, `q_peak_cms = round(max(0.0, raw_q - capacity_cms * 0.40), 3)`.
           - If the linked culvert has `status == 'BLOCKED'`, `q_peak_cms = round(raw_q * 1.25, 3)`.
        4. Set `risk_class` on `subbasins`: `'CRITICAL'` if `q_peak_cms >= 12.0`, `'ELEVATED'` if `q_peak_cms >= 6.0`, otherwise `'NOMINAL'`. Commit these updates to `subbasins` in `basin_network.gpkg`.
        5. In `/workspace/watershed_ops.qgz`, create or update a print layout named `Basin_Risk_Map` with a map item framing `subbasins`, save `watershed_ops.qgz`, and export `/workspace/role_a/basin_risk_map.pdf`.
        6. Write `/workspace/role_a/runoff_audit.json` as `{"rainfall_factor": <float>, "qgz_sha256": "<sha256 of saved watershed_ops.qgz>", "subbasins": {"SB-01": {"q_peak_cms": <float>, "risk_class": "..."}, ...}}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (workspace / "role_b/culvert_emergency_dispatch.md").write_text(
        textwrap.dedent('''
        # Ticket OPS-402: Emergency Culvert Blockage Buffer & Closure Atlas

        Process `/workspace/role_b/field_dispatch_log.json` against `/workspace/data/basin_network.gpkg` and `/workspace/watershed_ops.qgz`:
        1. Identify every culvert whose `debris_blockage_ratio >= blockage_threshold` (`0.80`).
        2. Before modifying `/workspace/data/basin_network.gpkg`, run a multi-radius sensitivity audit across the 6 candidate buffer radii `[125.0, 175.0, 225.0, 250.0, 300.0, 350.0]` meters: for each radius, build temporary buffer polygons around the blocked culverts, compute total intersected area (`m^2`) against all 16 `subbasins`, render a 300-DPI PNG preview `/workspace/role_b/sensitivity_r{int(r)}.png` via `QgsLayoutExporter.exportToImage`, and save the 6-radius table to `/workspace/role_b/buffer_sensitivity.json`.
        3. After completing all 6 sensitivity renders, update `/workspace/data/basin_network.gpkg` layer `culverts` so the blocked culverts have `status = 'BLOCKED'` and `capacity_cms = 0.0`.
        4. Save the `250.0` m polygon buffer layer `blocked_culverts_alert` (`culvert_id`, `status`, `debris_blockage_ratio`) into `/workspace/data/basin_network.gpkg`, register `blocked_culverts_alert` in `/workspace/watershed_ops.qgz`, add print layout `Closure_Alert_Atlas`, export `/workspace/role_b/closure_alert_atlas.pdf`, save `/workspace/watershed_ops.qgz`, and write `/workspace/role_b/closure_notice.json` as `{"dispatch_id": "FD-2026-88", "blocked_culvert_ids": [sorted IDs]}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    qgis_init = textwrap.dedent('''
        from qgis.core import (
            QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField,
            QgsFields, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle,
            QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes
        )
        from PyQt5.QtCore import QVariant

        qgs = QgsApplication([], False)
        qgs.initQgis()
        gpkg_path = r"''' + str(workspace / "data/basin_network.gpkg") + '''"
        qgz_path = r"''' + str(workspace / "watershed_ops.qgz") + '''"
        crs = QgsCoordinateReferenceSystem("EPSG:3857")

        sb_fields = QgsFields()
        sb_fields.append(QgsField("basin_id", QVariant.String))
        sb_fields.append(QgsField("area_ha", QVariant.Double))
        sb_fields.append(QgsField("impervious_pct", QVariant.Double))
        sb_fields.append(QgsField("culvert_id", QVariant.String))
        sb_fields.append(QgsField("q_peak_cms", QVariant.Double))
        sb_fields.append(QgsField("risk_class", QVariant.String))

        sb_mem = QgsVectorLayer("Polygon?crs=epsg:3857", "subbasins", "memory")
        sb_mem.dataProvider().addAttributes(sb_fields)
        sb_mem.updateFields()
        sb_feats = []
        for idx in range(16):
            row_idx = idx // 4
            col_idx = idx % 4
            x0 = col_idx * 500.0
            y0 = row_idx * 500.0
            feat = QgsFeature(sb_mem.fields())
            feat.setGeometry(QgsGeometry.fromRect(QgsRectangle(x0, y0, x0 + 480.0, y0 + 480.0)))
            area_val = round(22.0 + idx * 3.1, 2)
            imp_val = round(42.0 + (idx % 5) * 9.5, 1)
            feat.setAttributes([f"SB-{idx+1:02d}", area_val, imp_val, f"CV-{idx+1:02d}", 0.0, "UNRATED"])
            sb_feats.append(feat)
        sb_mem.dataProvider().addFeatures(sb_feats)

        opt_one = QgsVectorFileWriter.SaveVectorOptions()
        opt_one.driverName = "GPKG"
        opt_one.layerName = "subbasins"
        QgsVectorFileWriter.writeAsVectorFormatV3(sb_mem, gpkg_path, QgsProject.instance().transformContext(), opt_one)

        cv_fields = QgsFields()
        cv_fields.append(QgsField("culvert_id", QVariant.String))
        cv_fields.append(QgsField("status", QVariant.String))
        cv_fields.append(QgsField("capacity_cms", QVariant.Double))
        cv_mem = QgsVectorLayer("Point?crs=epsg:3857", "culverts", "memory")
        cv_mem.dataProvider().addAttributes(cv_fields)
        cv_mem.updateFields()
        cv_feats = []
        for idx in range(16):
            row_idx = idx // 4
            col_idx = idx % 4
            feat = QgsFeature(cv_mem.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(col_idx * 500.0 + 240.0, row_idx * 500.0 + 240.0)))
            cap_val = round(8.5 + (idx % 4) * 2.2, 2)
            feat.setAttributes([f"CV-{idx+1:02d}", "OPEN", cap_val])
            cv_feats.append(feat)
        cv_mem.dataProvider().addFeatures(cv_feats)

        opt_two = QgsVectorFileWriter.SaveVectorOptions()
        opt_two.driverName = "GPKG"
        opt_two.layerName = "culverts"
        opt_two.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(cv_mem, gpkg_path, QgsProject.instance().transformContext(), opt_two)

        proj = QgsProject.instance()
        proj.setCrs(crs)
        sb_disk = QgsVectorLayer(f"{gpkg_path}|layername=subbasins", "subbasins", "ogr")
        cv_disk = QgsVectorLayer(f"{gpkg_path}|layername=culverts", "culverts", "ogr")
        proj.addMapLayer(sb_disk)
        proj.addMapLayer(cv_disk)
        proj.write(qgz_path)
        proj.clear()
        import os as _os; _os._exit(0)
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as script_file:
        script_file.write(qgis_init)
        script_path = Path(script_file.name)
    try:
        run_checked(["python3", str(script_path)], timeout_s=90)
    finally:
        script_path.unlink(missing_ok=True)
    return {"qgz_sha256": sha256_file(workspace / "watershed_ops.qgz"), "gpkg_sha256": sha256_file(workspace / "data/basin_network.gpkg")}


def build_freecad_workspace(workspace: Path) -> dict:
    (workspace / "role_a").mkdir(parents=True, exist_ok=True)
    (workspace / "role_b").mkdir(parents=True, exist_ok=True)
    thermal_rows = [
        {"step_id": idx, "regime": "peak_overload_eco119" if idx == 48 else f"transient_{idx:02d}", "temp_c": round(25 + idx * 2.2, 1), "required_bore_mm": 48.0 if idx == 48 else round(42.0 + (idx % 9) * 0.6, 2), "bolt_circle_radius_mm": 35.0 if idx == 48 else round(30.0 + (idx % 5) * 0.9, 2)}
        for idx in range(1, 49)
    ]
    with (workspace / "role_b/thermal_expansion_table.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["step_id", "regime", "temp_c", "required_bore_mm", "bolt_circle_radius_mm"])
        writer.writeheader()
        writer.writerows(thermal_rows)
    (workspace / "role_a/cap_manufacturing_ticket.md").write_text(
        textwrap.dedent('''
        # Ticket CAD-501: Spigot Bearing Cap Fit & STEP Release

        Complete the mating `SpigotCap` solid inside `/workspace/actuator_mount.FCStd`:
        1. Read `bore_diameter` (cell `B2`) and `bolt_circle_radius` (cell `B3`) from spreadsheet `MasterSpec` in `/workspace/actuator_mount.FCStd`.
        2. Rebuild `SpigotCap` as a single solid (`Part::Feature`) composed of:
           - Top flange cylinder: radius `52.0` mm, height `8.0` mm, positioned from `z = 36.0` to `z = 44.0`.
           - Downward centering spigot cylinder: diameter `spigot_diameter = bore_diameter - 0.40` mm (radius `(bore_diameter - 0.40) / 2.0`), height `10.0` mm, positioned from `z = 26.0` to `z = 36.0` (fused with the top flange).
           - Cut 4 vertical bolt through-holes of radius `3.2` mm (`z = 24.0` to `z = 46.0`) at the 4 cardinal positions `(±bolt_circle_radius, 0)` and `(0, ±bolt_circle_radius)`.
        3. Recompute and save `/workspace/actuator_mount.FCStd`, verify zero interference (`BaseHousing.Shape.common(SpigotCap.Shape).Volume == 0`), export `SpigotCap` to `/workspace/role_a/spigot_cap.step`, and write `/workspace/role_a/cap_fit_check.json` with `{"bore_diameter_mm": <float>, "spigot_diameter_mm": <float>, "bolt_circle_radius_mm": <float>, "interference_volume_mm3": <float>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (workspace / "role_b/thermal_eco_119.md").write_text(
        textwrap.dedent('''
        # Ticket CAD-502: ECO-119 Peak-Overload Bore & Bolt-Circle Upgrade

        Before modifying `/workspace/actuator_mount.FCStd`, evaluate all 48 thermal load steps in `/workspace/role_b/thermal_expansion_table.csv` in FreeCAD: for each step, build the 3D housing solid (`outer r=52, h=36` minus central bore `required_bore_mm` and 4 `r=3.2` bolt holes at `bolt_circle_radius_mm`), apply a `0.8` mm fillet (`shape.makeFillet(0.8, shape.Edges)`), export an ASCII STL mesh `/workspace/role_b/sweeps/step_{step_id:02d}.stl` (`shape.tessellate(0.05)`), and record `step_id`, `volume_mm3`, and `facet_count` for all 48 steps to `/workspace/role_b/thermal_volume_sweep.json`. After all 48 STL sweeps finish, apply the `regime == 'peak_overload_eco119'` row (`ECO-119`) to `/workspace/actuator_mount.FCStd`:
        1. Update spreadsheet `MasterSpec` in `/workspace/actuator_mount.FCStd`: set cell `B2` (`bore_diameter`) to `48.0` and cell `B3` (`bolt_circle_radius`) to `35.0`.
        2. Rebuild `BaseHousing` (`Part::Feature`): outer cylinder radius `52.0` mm, height `36.0` mm (`z = 0.0` to `z = 36.0`), cut central through-bore of diameter `48.0` mm (`r = 24.0` mm), and cut 4 vertical bolt holes of radius `3.2` mm at `(±35.0, 0)` and `(0, ±35.0)`.
        3. Recompute and save `/workspace/actuator_mount.FCStd`, export `BaseHousing` to `/workspace/role_b/base_housing.step`, and write `/workspace/role_b/eco_119_summary.json` with `{"eco_id": "ECO-119", "bore_diameter_mm": 48.0, "bolt_circle_radius_mm": 35.0}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    fc_init = textwrap.dedent('''
        import FreeCAD, Part, Spreadsheet
        doc = FreeCAD.newDocument("ActuatorMount")
        sheet = doc.addObject("Spreadsheet::Sheet", "MasterSpec")
        sheet.set("A1", "parameter")
        sheet.set("B1", "value_mm")
        sheet.set("A2", "bore_diameter")
        sheet.set("B2", "42.0")
        sheet.set("A3", "bolt_circle_radius")
        sheet.set("B3", "30.0")

        outer = Part.makeCylinder(52.0, 36.0, FreeCAD.Vector(0, 0, 0))
        bore = Part.makeCylinder(21.0, 38.0, FreeCAD.Vector(0, 0, -1))
        housing_shape = outer.cut(bore)
        for bx, by in [(30.0, 0.0), (-30.0, 0.0), (0.0, 30.0), (0.0, -30.0)]:
            hole = Part.makeCylinder(3.2, 38.0, FreeCAD.Vector(bx, by, -1))
            housing_shape = housing_shape.cut(hole)
        housing_obj = doc.addObject("Part::Feature", "BaseHousing")
        housing_obj.Shape = housing_shape

        blank_cap = Part.makeCylinder(52.0, 8.0, FreeCAD.Vector(0, 0, 36.0))
        cap_obj = doc.addObject("Part::Feature", "SpigotCap")
        cap_obj.Shape = blank_cap
        doc.recompute()
        doc.saveAs(r"''' + str(workspace / "actuator_mount.FCStd") + '''")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as script_file:
        script_file.write(fc_init)
        script_path = Path(script_file.name)
    try:
        run_checked(["freecadcmd", str(script_path)], timeout_s=90)
    finally:
        script_path.unlink(missing_ok=True)
    return {"fcstd_sha256": sha256_file(workspace / "actuator_mount.FCStd")}


def build_inkscape_workspace(workspace: Path) -> dict:
    (workspace / "role_a").mkdir(parents=True, exist_ok=True)
    (workspace / "role_b").mkdir(parents=True, exist_ok=True)
    write_json(
        workspace / "role_b/palette_update.json",
        {
            "revision_id": "BRD-77",
            "gradient_id": "accent_grad",
            "candidates": [
                {"code": "C1", "stop_start_hex": "#003355", "stop_end_hex": "#004466"},
                {"code": "C2", "stop_start_hex": "#005588", "stop_end_hex": "#006699"},
                {"code": "C3", "stop_start_hex": "#0077AA", "stop_end_hex": "#0088BB"},
                {"code": "C4", "stop_start_hex": "#0088BB", "stop_end_hex": "#00AACC"},
                {"code": "BRD-77", "stop_start_hex": "#0099DD", "stop_end_hex": "#00DDFF"},
                {"code": "C6", "stop_start_hex": "#66EEFF", "stop_end_hex": "#AAFFFF"},
            ],
            "stop_start_hex": "#0099DD",
            "stop_end_hex": "#00DDFF",
            "badges": [
                {"id": "badge_temp", "x": 80, "y": 320, "width": 190, "height": 110},
                {"id": "badge_volt", "x": 305, "y": 320, "width": 190, "height": 110},
                {"id": "badge_lock", "x": 530, "y": 320, "width": 190, "height": 110},
            ],
        },
    )
    (workspace / "role_a/silkscreen_prep.md").write_text(
        textwrap.dedent('''
        # Ticket DES-601: Silkscreen Callout Stroke Prep & 300-DPI Ink-Coverage QA

        Prepare `/workspace/panel_master.svg` for silkscreen plate proofing:
        1. Inside group `id="layer_silkscreen"`, normalize all 6 callout paths (`callout_01`..`callout_06`) so each has `stroke-width="2.5"` and `stroke-linecap="round"` (preserving their `d` geometry and other layers/defs).
        2. Append a registration circle `<circle id="reg_mark_ne" cx="760" cy="40" r="12" fill="none" stroke="#FFFFFF" stroke-width="2.5"/>` inside `id="layer_silkscreen"`.
        3. Render a full-page proof at `300` DPI (`/workspace/role_a/panel_proof_300dpi.png`) via Inkscape, measure `non_bg_ink_ratio` on `panel_proof_300dpi.png` (fraction of pixels whose RGB is NOT `(24, 32, 40)`, rounded to 4 decimals), set or update `<desc id="qa_ink_ratio">...</desc>` as a direct child of `<svg>` in `/workspace/panel_master.svg` with that 4-decimal value, save `/workspace/panel_master.svg`, and write `/workspace/role_a/proof_manifest.json` with `{"svg_sha256": "...", "png_300_sha256": "...", "non_bg_ink_ratio": <float>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (workspace / "role_b/brand_palette_rev.md").write_text(
        textwrap.dedent('''
        # Ticket DES-602: Safety-Cyan Brand Gradient & HUD Status Badges

        Apply `/workspace/role_b/palette_update.json` (`BRD-77`) to `/workspace/panel_master.svg`:
        1. First, without modifying `/workspace/panel_master.svg`, render all 6 `candidates` in `palette_update.json` using temporary SVGs in `/workspace/role_b/trials/` at `600` DPI (`/workspace/role_b/trials/cand_{code}_600dpi.png`) via Inkscape, measure the mean RGB brightness of the badge region for each candidate, and save the 6-row audit table to `/workspace/role_b/candidate_contrast_audit.json`.
        2. After all 6 `600`-DPI candidate renders finish, update `/workspace/panel_master.svg`: set `<linearGradient id="accent_grad">` stops to `#0099DD` and `#00DDFF`, add the three `<rect>` elements (`badge_temp`, `badge_volt`, `badge_lock`) with exact `x`, `y`, `width`, `height` from `palette_update.json`, `rx="8"`, and `fill="url(#accent_grad)"` inside `id="layer_hud_badges"`, and append `<desc id="qa_brand_rev">BRD-77</desc>` as a direct child of `<svg>`.
        3. Save `/workspace/panel_master.svg`, render `/workspace/role_b/hud_badges_300dpi.png` (`300` DPI) and `/workspace/role_b/hud_badges_600dpi.png` (`600` DPI) via Inkscape, and write `/workspace/role_b/palette_applied.json` with `{"revision_id": "BRD-77", "badge_ids": ["badge_temp", "badge_volt", "badge_lock"]}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    callouts_xml = "\n".join(
        f'    <path id="callout_{idx:02d}" d="M {80 + idx * 95},110 L {125 + idx * 95},195" stroke="#EAEAEA" stroke-width="{0.6 + (idx % 3) * 0.7:.1f}" stroke-linecap="butt" fill="none"/>'
        for idx in range(1, 7)
    )
    svg_text = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="800" height="500" viewBox="0 0 800 500">
  <defs>
    <linearGradient id="accent_grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop id="accent_stop_1" offset="0%" stop-color="#FF5500"/>
      <stop id="accent_stop_2" offset="100%" stop-color="#FF8800"/>
    </linearGradient>
  </defs>
  <rect id="panel_bg" x="0" y="0" width="800" height="500" fill="#182028"/>
  <rect id="header_accent_bar" x="40" y="28" width="680" height="28" rx="4" fill="url(#accent_grad)"/>
  <g id="layer_silkscreen" inkscape:groupmode="layer" inkscape:label="Silkscreen">
{callouts_xml}
  </g>
  <g id="layer_hud_badges" inkscape:groupmode="layer" inkscape:label="HUD Badges">
    <rect id="badge_power" x="40" y="250" width="120" height="48" rx="6" fill="url(#accent_grad)"/>
  </g>
</svg>
'''
    (workspace / "panel_master.svg").write_text(svg_text, encoding="utf-8")
    return {"svg_sha256": sha256_file(workspace / "panel_master.svg")}


def build_task_workspace(task_id: str, workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    for child in list(workspace.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    if task_id == "PR-BLENDER-1":
        return build_blender_workspace(workspace)
    if task_id == "PR-QGIS-1":
        return build_qgis_workspace(workspace)
    if task_id == "PR-FREECAD-1":
        return build_freecad_workspace(workspace)
    if task_id == "PR-INKSCAPE-1":
        return build_inkscape_workspace(workspace)
    raise KeyError(f"Unknown task_id: {task_id}")


def role_prompts(task_id: str) -> dict[str, str]:
    if task_id == "PR-BLENDER-1":
        return {
            "A": (
                "Complete visualization ticket VIZ-204 in `/workspace/tickets/lighting_signoff_ticket.json` "
                "on `/workspace/turntable_studio.blend`. Update `KeyLight`, `RimLight`, and `TurntableCam` "
                "exactly per the ticket, save `/workspace/turntable_studio.blend`, render Cycles frames `1` and `12` "
                "(`640x360`, `24` samples) to `/workspace/deliverables/renders/frame_001.png` and `frame_012.png`, "
                'and write `/workspace/deliverables/render_signoff.json` with `{"frames": {"1": "<sha256>", "12": "<sha256>"}, "hero_height_m": <HeroBracket Z dimension rounded to 3 decimals>}`.'
            ),
            "B": (
                "Complete engineering change order ECO-B304 in `/workspace/tickets/eco_b304_geometry.json` "
                "on `/workspace/turntable_studio.blend`. Compute the upgraded `HeroBracket` Z height from "
                "`/workspace/inputs/bracket_load_spectrum.csv` (`base_nominal_height_m * max(height_scale_factor)`), "
                "scale/apply `HeroBracket` so its Z dimension equals that height (keeping base at `z=0`), set its bevel "
                "modifier width to `0.05`, update `AnodizedMetal` base color to `[0.10, 0.42, 0.85, 1.0]` and roughness "
                "to `0.20`, save `/workspace/turntable_studio.blend`, render frame `6` to `/workspace/deliverables/eco_preview_f06.png`, "
                'and write `/workspace/deliverables/eco_b304_applied.json` with `{"eco_id": "ECO-B304", "target_height_m": <float>}`.'
            ),
        }
    if task_id == "PR-QGIS-1":
        return {
            "A": "Read `/workspace/role_a/hydrology_runoff_spec.md` and complete Ticket HYD-401 using PyQGIS in a single clean pass (note: use PyQGIS `startEditing()/commitChanges()` rather than raw sqlite3 UPDATE due to SpatiaLite triggers, and `map_item.setExtent(layer.extent())`). Do not inspect `/workspace/role_b`.",
            "B": "Read `/workspace/role_b/culvert_emergency_dispatch.md` and complete Ticket OPS-402 on `/workspace/data/basin_network.gpkg` and `/workspace/watershed_ops.qgz`. Do not inspect `/workspace/role_a`.",
        }
    if task_id == "PR-FREECAD-1":
        return {
            "A": "Read `/workspace/role_a/cap_manufacturing_ticket.md` and complete Ticket CAD-501 on `/workspace/actuator_mount.FCStd` via `freecadcmd` (no GUI reload required once `.FCStd`, `.step`, and `.json` are verified). Do not inspect `/workspace/role_b`.",
            "B": "Read `/workspace/role_b/thermal_eco_119.md` and complete Ticket CAD-502 on `/workspace/actuator_mount.FCStd`. Do not inspect `/workspace/role_a`.",
        }
    if task_id == "PR-INKSCAPE-1":
        return {
            "A": "Read `/workspace/role_a/silkscreen_prep.md` and complete Ticket DES-601 on `/workspace/panel_master.svg`. Do not inspect `/workspace/role_b`.",
            "B": "Read `/workspace/role_b/brand_palette_rev.md` and complete Ticket DES-602 on `/workspace/panel_master.svg`. Do not inspect `/workspace/role_a`.",
        }
    raise KeyError(f"Unknown task_id: {task_id}")


def solve_reference_role(task_id: str, role: str, workspace: Path, source_snapshot: Path | None = None) -> None:
    if source_snapshot is not None:
        canon_name = CATALOG_BY_ID[task_id]["canonical_project"]
        shutil.copy2(source_snapshot / canon_name, workspace / canon_name)
        if task_id == "PR-QGIS-1" and (source_snapshot / "data/basin_network.gpkg").is_file():
            shutil.copy2(source_snapshot / "data/basin_network.gpkg", workspace / "data/basin_network.gpkg")

    if task_id == "PR-BLENDER-1" and role == "A":
        (workspace / "deliverables/renders").mkdir(parents=True, exist_ok=True)
        script_code = textwrap.dedent(f'''
            import bpy, hashlib, json
            from pathlib import Path
            ws = Path(r"{workspace}")
            bpy.ops.wm.open_mainfile(filepath=str(ws / "turntable_studio.blend"))
            scene = bpy.context.scene
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 24
            scene.cycles.use_denoising = False
            scene.render.resolution_x = 640
            scene.render.resolution_y = 360
            key_obj = bpy.data.objects["KeyLight"]
            key_obj.data.energy = 850.0
            key_obj.data.color = (1.0, 0.90, 0.80)
            rim_obj = bpy.data.objects["RimLight"]
            rim_obj.data.energy = 420.0
            rim_obj.data.color = (0.80, 0.90, 1.0)
            cam_obj = bpy.data.objects["TurntableCam"]
            cam_obj.data.lens = 65.0
            scene.camera = cam_obj
            bpy.context.view_layer.update()
            hero_z = round(float(bpy.data.objects["HeroBracket"].dimensions.z), 3)
            bpy.ops.wm.save_as_mainfile(filepath=str(ws / "turntable_studio.blend"))
            hashes = {{}}
            for frame_num in (1, 12):
                scene.frame_set(frame_num)
                out_png = ws / "deliverables/renders" / f"frame_{{frame_num:03d}}.png"
                scene.render.filepath = str(out_png)
                bpy.ops.render.render(write_still=True)
                hashes[str(frame_num)] = hashlib.sha256(out_png.read_bytes()).hexdigest()
            (ws / "deliverables/render_signoff.json").write_text(json.dumps({{"frames": hashes, "hero_height_m": hero_z}}, indent=2))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["blender", "-b", "--python", str(tmp_path)], timeout_s=180)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-BLENDER-1" and role == "B":
        script_code = textwrap.dedent(f'''
            import bpy, csv, json
            from pathlib import Path
            ws = Path(r"{workspace}")
            rows = list(csv.DictReader((ws / "inputs/bracket_load_spectrum.csv").open()))
            max_factor = max(float(item["height_scale_factor"]) for item in rows)
            target_h = round(1.20 * max_factor, 3)
            bpy.ops.wm.open_mainfile(filepath=str(ws / "turntable_studio.blend"))
            scene = bpy.context.scene
            hero = bpy.data.objects["HeroBracket"]
            bpy.context.view_layer.objects.active = hero
            hero.select_set(True)
            cur_h = float(hero.dimensions.z)
            ratio = target_h / cur_h
            hero.scale = (1.0, 1.0, ratio)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            min_z = min((hero.matrix_world @ vert.co).z for vert in hero.data.vertices)
            hero.location.z -= min_z
            for mod in hero.modifiers:
                if mod.type == "BEVEL":
                    mod.width = 0.05
            mat = bpy.data.materials["AnodizedMetal"]
            bsdf = mat.node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Base Color"].default_value = (0.10, 0.42, 0.85, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.20
            bpy.ops.wm.save_as_mainfile(filepath=str(ws / "turntable_studio.blend"))
            scene.cycles.use_denoising = False
            scene.frame_set(6)
            scene.render.filepath = str(ws / "deliverables/eco_preview_f06.png")
            bpy.ops.render.render(write_still=True)
            (ws / "deliverables/eco_b304_applied.json").write_text(json.dumps({{"eco_id": "ECO-B304", "target_height_m": target_h}}, indent=2))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["blender", "-b", "--python", str(tmp_path)], timeout_s=180)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-QGIS-1" and role == "A":
        script_code = textwrap.dedent(f'''
            import csv, hashlib, json
            from pathlib import Path
            from qgis.core import QgsApplication, QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout, QgsProject, QgsUnitTypes, QgsVectorLayer
            ws = Path(r"{workspace}")
            rows = list(csv.DictReader((ws / "role_a/storm_hyetograph.csv").open()))
            rf = max(float(item["intensity_mm_hr"]) for item in rows) / 100.0
            gpkg = ws / "data/basin_network.gpkg"
            qgs = QgsApplication([], False)
            qgs.initQgis()
            cv_lyr = QgsVectorLayer(f"{{gpkg}}|layername=culverts", "culverts", "ogr")
            culv = {{feat["culvert_id"]: (str(feat["status"]), float(feat["capacity_cms"])) for feat in cv_lyr.getFeatures()}}
            sb_lyr = QgsVectorLayer(f"{{gpkg}}|layername=subbasins", "subbasins", "ogr")
            q_idx = sb_lyr.fields().indexFromName("q_peak_cms")
            r_idx = sb_lyr.fields().indexFromName("risk_class")
            audit_map = {{}}
            sb_lyr.startEditing()
            for feat in sb_lyr.getFeatures():
                bid = str(feat["basin_id"])
                st, cap = culv[str(feat["culvert_id"])]
                raw_q = float(feat["area_ha"]) * (float(feat["impervious_pct"]) / 100.0) * rf
                net_q = round(max(0.0, raw_q - cap * 0.40), 3) if st == "OPEN" else round(raw_q * 1.25, 3)
                rclass = "CRITICAL" if net_q >= 12.0 else ("ELEVATED" if net_q >= 6.0 else "NOMINAL")
                sb_lyr.changeAttributeValue(feat.id(), q_idx, net_q)
                sb_lyr.changeAttributeValue(feat.id(), r_idx, rclass)
                audit_map[bid] = {{"q_peak_cms": net_q, "risk_class": rclass}}
            sb_lyr.commitChanges()
            proj = QgsProject.instance()
            proj.read(str(ws / "watershed_ops.qgz"))
            mgr = proj.layoutManager()
            existing = mgr.layoutByName("Basin_Risk_Map")
            if existing:
                mgr.removeLayout(existing)
            layout = QgsPrintLayout(proj)
            layout.initializeDefaults()
            layout.setName("Basin_Risk_Map")
            map_item = QgsLayoutItemMap(layout)
            map_item.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(277, 190, QgsUnitTypes.LayoutMillimeters))
            sb_layers = proj.mapLayersByName("subbasins")
            if sb_layers:
                map_item.setExtent(sb_layers[0].extent())
            layout.addLayoutItem(map_item)
            mgr.addLayout(layout)
            proj.write(str(ws / "watershed_ops.qgz"))
            exporter = QgsLayoutExporter(layout)
            exporter.exportToPdf(str(ws / "role_a/basin_risk_map.pdf"), QgsLayoutExporter.PdfExportSettings())
            qgz_sha = hashlib.sha256((ws / "watershed_ops.qgz").read_bytes()).hexdigest()
            (ws / "role_a/runoff_audit.json").write_text(json.dumps({{"rainfall_factor": rf, "qgz_sha256": qgz_sha, "subbasins": audit_map}}, indent=2))
            proj.clear()
            import os as _os; _os._exit(0)
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["python3", str(tmp_path)], timeout_s=120)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-QGIS-1" and role == "B":
        script_code = textwrap.dedent(f'''
            import json
            from pathlib import Path
            from qgis.core import QgsApplication, QgsFeature, QgsField, QgsFields, QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout, QgsProject, QgsUnitTypes, QgsVectorFileWriter, QgsVectorLayer
            from PyQt5.QtCore import QVariant
            ws = Path(r"{workspace}")
            dispatch = json.loads((ws / "role_b/field_dispatch_log.json").read_text())
            thresh = float(dispatch["blockage_threshold"])
            blocked_map = {{row["culvert_id"]: float(row["debris_blockage_ratio"]) for row in dispatch["inspections"] if float(row["debris_blockage_ratio"]) >= thresh}}
            gpkg = ws / "data/basin_network.gpkg"
            qgs = QgsApplication([], False)
            qgs.initQgis()
            src_layer = QgsVectorLayer(f"{{gpkg}}|layername=culverts", "culverts", "ogr")
            sb_ref = QgsVectorLayer(f"{{gpkg}}|layername=subbasins", "subbasins", "ogr")
            sens_rows = []
            proj_tmp = QgsProject.instance()
            proj_tmp.read(str(ws / "watershed_ops.qgz"))
            for rad in (125.0, 175.0, 225.0, 250.0, 300.0, 350.0):
                buf_geoms = [feat.geometry().buffer(rad, 12) for feat in src_layer.getFeatures() if str(feat["culvert_id"]) in blocked_map]
                area_sum = sum(bg.intersection(sf.geometry()).area() for bg in buf_geoms for sf in sb_ref.getFeatures())
                lay_s = QgsPrintLayout(proj_tmp)
                lay_s.initializeDefaults()
                mi = QgsLayoutItemMap(lay_s)
                mi.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
                mi.attemptResize(QgsLayoutSize(277, 190, QgsUnitTypes.LayoutMillimeters))
                mi.setExtent(sb_ref.extent())
                lay_s.addLayoutItem(mi)
                img_set = QgsLayoutExporter.ImageExportSettings()
                img_set.dpi = 300
                QgsLayoutExporter(lay_s).exportToImage(str(ws / f"role_b/sensitivity_r{{int(rad)}}.png"), img_set)
                sens_rows.append({{"radius_m": rad, "intersected_area_m2": round(area_sum, 2)}})
            (ws / "role_b/buffer_sensitivity.json").write_text(json.dumps(sens_rows, indent=2))
            st_idx = src_layer.fields().indexFromName("status")
            cap_idx = src_layer.fields().indexFromName("capacity_cms")
            src_layer.startEditing()
            for feat in src_layer.getFeatures():
                if str(feat["culvert_id"]) in blocked_map:
                    src_layer.changeAttributeValue(feat.id(), st_idx, "BLOCKED")
                    src_layer.changeAttributeValue(feat.id(), cap_idx, 0.0)
            src_layer.commitChanges()
            alert_mem = QgsVectorLayer("Polygon?crs=epsg:3857", "blocked_culverts_alert", "memory")
            af = QgsFields()
            af.append(QgsField("culvert_id", QVariant.String))
            af.append(QgsField("status", QVariant.String))
            af.append(QgsField("debris_blockage_ratio", QVariant.Double))
            alert_mem.dataProvider().addAttributes(af)
            alert_mem.updateFields()
            new_feats = []
            for feat in src_layer.getFeatures():
                cid = feat["culvert_id"]
                if cid in blocked_map:
                    nf = QgsFeature(alert_mem.fields())
                    nf.setGeometry(feat.geometry().buffer(250.0, 12))
                    nf.setAttributes([cid, "BLOCKED", blocked_map[cid]])
                    new_feats.append(nf)
            alert_mem.dataProvider().addFeatures(new_feats)
            opts = QgsVectorFileWriter.SaveVectorOptions()
            opts.driverName = "GPKG"
            opts.layerName = "blocked_culverts_alert"
            opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            QgsVectorFileWriter.writeAsVectorFormatV3(alert_mem, str(gpkg), QgsProject.instance().transformContext(), opts)
            proj = QgsProject.instance()
            proj.read(str(ws / "watershed_ops.qgz"))
            if not proj.mapLayersByName("blocked_culverts_alert"):
                alert_disk = QgsVectorLayer(f"{{gpkg}}|layername=blocked_culverts_alert", "blocked_culverts_alert", "ogr")
                proj.addMapLayer(alert_disk)
            mgr = proj.layoutManager()
            existing = mgr.layoutByName("Closure_Alert_Atlas")
            if existing:
                mgr.removeLayout(existing)
            layout = QgsPrintLayout(proj)
            layout.initializeDefaults()
            layout.setName("Closure_Alert_Atlas")
            map_item = QgsLayoutItemMap(layout)
            map_item.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(277, 190, QgsUnitTypes.LayoutMillimeters))
            sb_layers = proj.mapLayersByName("subbasins")
            if sb_layers:
                map_item.setExtent(sb_layers[0].extent())
            layout.addLayoutItem(map_item)
            mgr.addLayout(layout)
            proj.write(str(ws / "watershed_ops.qgz"))
            exporter = QgsLayoutExporter(layout)
            exporter.exportToPdf(str(ws / "role_b/closure_alert_atlas.pdf"), QgsLayoutExporter.PdfExportSettings())
            (ws / "role_b/closure_notice.json").write_text(json.dumps({{"dispatch_id": dispatch["dispatch_id"], "blocked_culvert_ids": sorted(blocked_map.keys())}}, indent=2))
            proj.clear()
            import os as _os; _os._exit(0)
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["python3", str(tmp_path)], timeout_s=120)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-FREECAD-1" and role == "A":
        script_code = textwrap.dedent(f'''
            import json, FreeCAD, Part
            from pathlib import Path
            ws = Path(r"{workspace}")
            doc = FreeCAD.openDocument(str(ws / "actuator_mount.FCStd"))
            sheet = doc.getObject("MasterSpec")
            bore_d = float(sheet.get("B2"))
            bcr = float(sheet.get("B3"))
            spigot_d = round(bore_d - 0.40, 4)
            flange = Part.makeCylinder(52.0, 8.0, FreeCAD.Vector(0, 0, 36.0))
            spigot = Part.makeCylinder(spigot_d / 2.0, 10.0, FreeCAD.Vector(0, 0, 26.0))
            cap_shape = flange.fuse(spigot)
            for bx, by in [(bcr, 0.0), (-bcr, 0.0), (0.0, bcr), (0.0, -bcr)]:
                hole = Part.makeCylinder(3.2, 24.0, FreeCAD.Vector(bx, by, 24.0))
                cap_shape = cap_shape.cut(hole)
            cap_obj = doc.getObject("SpigotCap")
            cap_obj.Shape = cap_shape
            doc.recompute()
            inter_vol = round(float(doc.getObject("BaseHousing").Shape.common(cap_obj.Shape).Volume), 6)
            Part.export([cap_obj], str(ws / "role_a/spigot_cap.step"))
            doc.save()
            (ws / "role_a/cap_fit_check.json").write_text(json.dumps({{"bore_diameter_mm": bore_d, "spigot_diameter_mm": spigot_d, "bolt_circle_radius_mm": bcr, "interference_volume_mm3": inter_vol}}, indent=2))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["freecadcmd", str(tmp_path)], timeout_s=120)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-FREECAD-1" and role == "B":
        script_code = textwrap.dedent(f'''
            import csv, json, FreeCAD, Part
            from pathlib import Path
            ws = Path(r"{workspace}")
            rows = list(csv.DictReader((ws / "role_b/thermal_expansion_table.csv").open()))
            (ws / "role_b/sweeps").mkdir(parents=True, exist_ok=True)
            sweep = []
            for item in rows:
                sid = int(item["step_id"])
                rb = float(item["required_bore_mm"])
                rc = float(item["bolt_circle_radius_mm"])
                sh = Part.makeCylinder(52.0, 36.0).cut(Part.makeCylinder(rb / 2.0, 38.0, FreeCAD.Vector(0, 0, -1)))
                for bx, by in [(rc, 0.0), (-rc, 0.0), (0.0, rc), (0.0, -rc)]:
                    sh = sh.cut(Part.makeCylinder(3.2, 38.0, FreeCAD.Vector(bx, by, -1)))
                sh = sh.makeFillet(0.8, sh.Edges)
                verts, facets = sh.tessellate(0.05)
                sh.exportStl(str(ws / f"role_b/sweeps/step_{{sid:02d}}.stl"))
                sweep.append({{"step_id": sid, "volume_mm3": round(float(sh.Volume), 3), "facet_count": len(facets)}})
            (ws / "role_b/thermal_volume_sweep.json").write_text(json.dumps(sweep, indent=2))
            target = next(item for item in rows if item["regime"] == "peak_overload_eco119")
            bore_d = float(target["required_bore_mm"])
            bcr = float(target["bolt_circle_radius_mm"])
            doc = FreeCAD.openDocument(str(ws / "actuator_mount.FCStd"))
            sheet = doc.getObject("MasterSpec")
            sheet.set("B2", str(bore_d))
            sheet.set("B3", str(bcr))
            outer = Part.makeCylinder(52.0, 36.0, FreeCAD.Vector(0, 0, 0))
            bore = Part.makeCylinder(bore_d / 2.0, 38.0, FreeCAD.Vector(0, 0, -1))
            housing_shape = outer.cut(bore)
            for bx, by in [(bcr, 0.0), (-bcr, 0.0), (0.0, bcr), (0.0, -bcr)]:
                hole = Part.makeCylinder(3.2, 38.0, FreeCAD.Vector(bx, by, -1))
                housing_shape = housing_shape.cut(hole)
            housing_obj = doc.getObject("BaseHousing")
            housing_obj.Shape = housing_shape
            doc.recompute()
            Part.export([housing_obj], str(ws / "role_b/base_housing.step"))
            doc.save()
            (ws / "role_b/eco_119_summary.json").write_text(json.dumps({{"eco_id": "ECO-119", "bore_diameter_mm": bore_d, "bolt_circle_radius_mm": bcr}}, indent=2))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
            tmp_f.write(script_code)
            tmp_path = Path(tmp_f.name)
        try:
            run_checked(["freecadcmd", str(tmp_path)], timeout_s=120)
        finally:
            tmp_path.unlink(missing_ok=True)
        return

    if task_id == "PR-INKSCAPE-1" and role == "A":
        from PIL import Image
        svg_path = workspace / "panel_master.svg"
        tree = ElementTree.parse(svg_path)
        root = tree.getroot()
        for elem in root.iter():
            elem_id = elem.attrib.get("id", "")
            if elem_id.startswith("callout_"):
                elem.set("stroke-width", "2.5")
                elem.set("stroke-linecap", "round")
            if elem_id == "layer_silkscreen":
                existing_reg = [child for child in list(elem) if child.attrib.get("id") == "reg_mark_ne"]
                if not existing_reg:
                    reg = ElementTree.SubElement(elem, f"{{{SVG_NS}}}circle")
                    reg.set("id", "reg_mark_ne")
                    reg.set("cx", "760")
                    reg.set("cy", "40")
                    reg.set("r", "12")
                    reg.set("fill", "none")
                    reg.set("stroke", "#FFFFFF")
                    reg.set("stroke-width", "2.5")
        tree.write(svg_path, encoding="utf-8", xml_declaration=True)
        out_300 = workspace / "role_a/panel_proof_300dpi.png"
        run_checked(["inkscape", "--export-type=png", "--export-dpi=300", f"--export-filename={out_300}", str(svg_path)], timeout_s=90)
        with Image.open(out_300) as img_300:
            rgb_bytes = img_300.convert("RGB").tobytes()
            total_px = len(rgb_bytes) // 3
            non_bg = sum(1 for idx in range(0, len(rgb_bytes), 3) if (rgb_bytes[idx], rgb_bytes[idx + 1], rgb_bytes[idx + 2]) != (24, 32, 40))
            ink_ratio = round(non_bg / max(1, total_px), 4)
        existing_qa = [child for child in list(root) if child.attrib.get("id") == "qa_ink_ratio"]
        qa_elem = existing_qa[0] if existing_qa else ElementTree.SubElement(root, f"{{{SVG_NS}}}desc", {"id": "qa_ink_ratio"})
        qa_elem.text = f"{ink_ratio:.4f}"
        tree.write(svg_path, encoding="utf-8", xml_declaration=True)
        write_json(workspace / "role_a/proof_manifest.json", {"svg_sha256": sha256_file(svg_path), "png_300_sha256": sha256_file(out_300), "non_bg_ink_ratio": ink_ratio})
        return

    if task_id == "PR-INKSCAPE-1" and role == "B":
        from PIL import Image
        svg_path = workspace / "panel_master.svg"
        spec = json.loads((workspace / "role_b/palette_update.json").read_text(encoding="utf-8"))
        (workspace / "role_b/trials").mkdir(parents=True, exist_ok=True)
        cand_rows = []
        for cand in spec["candidates"]:
            trial_svg = workspace / f"role_b/trials/cand_{cand['code']}.svg"
            shutil.copy2(svg_path, trial_svg)
            ttree = ElementTree.parse(trial_svg)
            for elem in ttree.getroot().iter():
                if elem.attrib.get("id") == "accent_grad":
                    st_list = [ch for ch in list(elem) if ch.tag.endswith("stop")]
                    st_list[0].set("stop-color", cand["stop_start_hex"])
                    st_list[1].set("stop-color", cand["stop_end_hex"])
            ttree.write(trial_svg, encoding="utf-8", xml_declaration=True)
            trial_png = workspace / f"role_b/trials/cand_{cand['code']}_600dpi.png"
            run_checked(["inkscape", "--export-type=png", "--export-dpi=600", f"--export-filename={trial_png}", str(trial_svg)], timeout_s=120)
            with Image.open(trial_png) as tim:
                crop = tim.convert("RGB").crop((250, 175, 1000, 260)).tobytes()
                cand_rows.append({"code": cand["code"], "mean_rgb": round(sum(crop) / max(1, len(crop)), 2)})
        write_json(workspace / "role_b/candidate_contrast_audit.json", {"candidates": cand_rows})
        tree = ElementTree.parse(svg_path)
        root = tree.getroot()
        for elem in root.iter():
            elem_id = elem.attrib.get("id", "")
            if elem_id == "accent_grad":
                stops = [child for child in list(elem) if child.tag.endswith("stop")]
                if len(stops) >= 2:
                    stops[0].set("stop-color", spec["stop_start_hex"])
                    stops[1].set("stop-color", spec["stop_end_hex"])
            if elem_id == "layer_hud_badges":
                existing_ids = {child.attrib.get("id") for child in list(elem)}
                for badge in spec["badges"]:
                    if badge["id"] not in existing_ids:
                        rect = ElementTree.SubElement(elem, f"{{{SVG_NS}}}rect")
                        rect.set("id", badge["id"])
                        rect.set("x", str(badge["x"]))
                        rect.set("y", str(badge["y"]))
                        rect.set("width", str(badge["width"]))
                        rect.set("height", str(badge["height"]))
                        rect.set("rx", "8")
                        rect.set("fill", "url(#accent_grad)")
        existing_rev = [child for child in list(root) if child.attrib.get("id") == "qa_brand_rev"]
        rev_elem = existing_rev[0] if existing_rev else ElementTree.SubElement(root, f"{{{SVG_NS}}}desc", {"id": "qa_brand_rev"})
        rev_elem.text = spec["revision_id"]
        tree.write(svg_path, encoding="utf-8", xml_declaration=True)
        prev_300 = workspace / "role_b/hud_badges_300dpi.png"
        prev_600 = workspace / "role_b/hud_badges_600dpi.png"
        run_checked(["inkscape", "--export-type=png", "--export-dpi=300", f"--export-filename={prev_300}", str(svg_path)], timeout_s=90)
        run_checked(["inkscape", "--export-type=png", "--export-dpi=600", f"--export-filename={prev_600}", str(svg_path)], timeout_s=120)
        write_json(workspace / "role_b/palette_applied.json", {"revision_id": spec["revision_id"], "badge_ids": [item["id"] for item in spec["badges"]]})
        return

    raise ValueError(f"Unsupported reference solve {task_id} {role}")


def probe_lightweight_signals(task_id: str, workspace: Path) -> dict:
    canon_path = workspace / CATALOG_BY_ID[task_id]["canonical_project"]
    if not canon_path.is_file():
        return {"exists": False}
    base_info = {"exists": True, "project_sha256": sha256_file(canon_path), "mtime": canon_path.stat().st_mtime}
    try:
        if task_id == "PR-INKSCAPE-1":
            raw_svg = canon_path.read_text(encoding="utf-8", errors="replace")
            base_info["role_a_in_project"] = ("reg_mark_ne" in raw_svg and 'stroke-width="2.5"' in raw_svg)
            base_info["role_b_in_project"] = ("#0099DD" in raw_svg.upper() and "badge_lock" in raw_svg)
        elif task_id == "PR-QGIS-1":
            with ZipFile(canon_path) as qgz_zip:
                qgs_names = [name for name in qgz_zip.namelist() if name.endswith(".qgs")]
                qgs_xml = qgz_zip.read(qgs_names[0]).decode("utf-8", errors="replace") if qgs_names else ""
            base_info["role_a_in_project"] = "Basin_Risk_Map" in qgs_xml
            base_info["role_b_in_project"] = "blocked_culverts_alert" in qgs_xml
            gpkg_path = workspace / "data/basin_network.gpkg"
            if gpkg_path.is_file():
                base_info["gpkg_sha256"] = sha256_file(gpkg_path)
        elif task_id == "PR-FREECAD-1":
            with ZipFile(canon_path) as fc_zip:
                doc_xml = fc_zip.read("Document.xml").decode("utf-8", errors="replace")
                brp_sizes = sorted(info.file_size for info in fc_zip.infolist() if info.filename.endswith(".brp"))
            base_info["role_a_in_project"] = bool(brp_sizes and min(brp_sizes) > 8500)
            base_info["role_b_in_project"] = "48.0" in doc_xml or "48" in doc_xml
            base_info["role_a_deliverable"] = (workspace / "role_a/spigot_cap.step").is_file()
        elif task_id == "PR-BLENDER-1":
            base_info["role_a_deliverable"] = (workspace / "deliverables/renders/frame_001.png").is_file()
            base_info["role_b_deliverable"] = (workspace / "deliverables/eco_preview_f06.png").is_file()
    except Exception as exc:
        base_info["probe_error"] = type(exc).__name__
    return base_info


def grade_workspace(task_id: str, workspace: Path) -> dict:
    if task_id == "PR-BLENDER-1":
        inspect_out = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        inspect_json = Path(inspect_out.name)
        inspect_out.close()
        rerender_png = Path(tempfile.mktemp(suffix=".png"))
        probe_code = textwrap.dedent(f'''
            import bpy, json
            bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'turntable_studio.blend'}")
            scene = bpy.context.scene
            bpy.context.view_layer.update()
            key_obj = bpy.data.objects.get("KeyLight")
            rim_obj = bpy.data.objects.get("RimLight")
            cam_obj = bpy.data.objects.get("TurntableCam")
            hero_obj = bpy.data.objects.get("HeroBracket")
            mat = bpy.data.materials.get("AnodizedMetal")
            bsdf = mat.node_tree.nodes.get("Principled BSDF") if (mat and mat.use_nodes) else None
            bevel_w = None
            if hero_obj:
                for mod in hero_obj.modifiers:
                    if mod.type == "BEVEL":
                        bevel_w = float(mod.width)
            info = {{
                "key_energy": float(key_obj.data.energy) if key_obj else None,
                "key_color": list(key_obj.data.color) if key_obj else None,
                "rim_energy": float(rim_obj.data.energy) if rim_obj else None,
                "cam_lens": float(cam_obj.data.lens) if cam_obj else None,
                "hero_z": float(hero_obj.dimensions.z) if hero_obj else None,
                "bevel_width": bevel_w,
                "base_color": list(bsdf.inputs["Base Color"].default_value)[:3] if bsdf else None,
                "roughness": float(bsdf.inputs["Roughness"].default_value) if bsdf else None,
            }}
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 24
            scene.cycles.use_denoising = False
            scene.render.resolution_x = 640
            scene.render.resolution_y = 360
            scene.frame_set(1)
            scene.render.filepath = r"{rerender_png}"
            bpy.ops.render.render(write_still=True)
            open(r"{inspect_json}", "w").write(json.dumps(info))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as py_f:
            py_f.write(probe_code)
            py_path = Path(py_f.name)
        try:
            run_checked(["blender", "-b", "--python", str(py_path)], timeout_s=180)
            scene_info = json.loads(inspect_json.read_text(encoding="utf-8"))
            f1_path = workspace / "deliverables/renders/frame_001.png"
            f12_path = workspace / "deliverables/renders/frame_012.png"
            signoff_path = workspace / "deliverables/render_signoff.json"
            signoff_data = json.loads(signoff_path.read_text(encoding="utf-8")) if signoff_path.is_file() else {}
            frames_meta = signoff_data.get("frames") or {}
            f1_diff = mean_rgb_diff(f1_path, rerender_png) if (f1_path.is_file() and rerender_png.is_file()) else 255.0
            checks_a = {
                "lights_and_camera_in_blend": (
                    scene_info.get("key_energy") is not None
                    and abs(scene_info["key_energy"] - 850.0) <= 2.0
                    and abs((scene_info.get("rim_energy") or 0.0) - 420.0) <= 2.0
                    and abs((scene_info.get("cam_lens") or 0.0) - 65.0) <= 0.5
                ),
                "frames_rendered_and_hashed": (
                    f1_path.is_file()
                    and f12_path.is_file()
                    and frames_meta.get("1") == sha256_file(f1_path)
                    and frames_meta.get("12") == sha256_file(f12_path)
                ),
                "signoff_height_matches_saved_blend": (
                    isinstance(signoff_data.get("hero_height_m"), (int, float))
                    and abs(float(signoff_data["hero_height_m"]) - (scene_info.get("hero_z") or -99.0)) <= 0.03
                ),
                "rendered_frame_matches_saved_blend": f1_diff <= 8.0,
            }
            eco_path = workspace / "deliverables/eco_b304_applied.json"
            eco_data = json.loads(eco_path.read_text(encoding="utf-8")) if eco_path.is_file() else {}
            bcol = scene_info.get("base_color") or [0.0, 0.0, 0.0]
            checks_b = {
                "hero_height_upgraded_in_blend": abs((scene_info.get("hero_z") or 0.0) - 1.65) <= 0.03,
                "bevel_and_material_in_blend": (
                    abs((scene_info.get("bevel_width") or 0.0) - 0.05) <= 0.005
                    and abs(bcol[0] - 0.10) <= 0.05
                    and abs(bcol[1] - 0.42) <= 0.05
                    and abs(bcol[2] - 0.85) <= 0.05
                    and abs((scene_info.get("roughness") or 1.0) - 0.20) <= 0.03
                ),
                "eco_preview_and_json": (
                    (workspace / "deliverables/eco_preview_f06.png").is_file()
                    and abs(float(eco_data.get("target_height_m") or 0.0) - 1.65) <= 0.02
                ),
            }
            role_a_pass = all(checks_a.values())
            role_b_pass = all(checks_b.values())
            return {
                "task_id": task_id,
                "role_a_pass": role_a_pass,
                "role_b_pass": role_b_pass,
                "joint_pass": role_a_pass and role_b_pass,
                "checks_a": checks_a,
                "checks_b": checks_b,
                "diagnostics": {"scene_info": scene_info, "frame_001_rerender_rgb_diff": round(f1_diff, 3)},
            }
        finally:
            py_path.unlink(missing_ok=True)
            inspect_json.unlink(missing_ok=True)
            rerender_png.unlink(missing_ok=True)

    if task_id == "PR-QGIS-1":
        gpkg_path = workspace / "data/basin_network.gpkg"
        qgz_path = workspace / "watershed_ops.qgz"
        conn = sqlite3.connect(str(gpkg_path))
        cur = conn.cursor()
        culverts_now = {cid: (st, float(cap)) for cid, st, cap in cur.execute("SELECT culvert_id, status, capacity_cms FROM culverts")}
        subbasins_now = {
            bid: (float(area_ha), float(imp_pct), cid, float(q_val), rclass)
            for bid, area_ha, imp_pct, cid, q_val, rclass in cur.execute("SELECT basin_id, area_ha, impervious_pct, culvert_id, q_peak_cms, risk_class FROM subbasins")
        }
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        alert_ids = sorted(row[0] for row in cur.execute("SELECT culvert_id FROM blocked_culverts_alert")) if "blocked_culverts_alert" in tables else []
        conn.close()
        expected_blocked = ["CV-02", "CV-05", "CV-09", "CV-11", "CV-14"]
        rf = 0.46
        runoff_matches_committed_culverts = True
        for bid, (area_ha, imp_pct, cid, q_val, rclass) in subbasins_now.items():
            st, cap = culverts_now[cid]
            raw_q = area_ha * (imp_pct / 100.0) * rf
            exp_q = round(max(0.0, raw_q - cap * 0.40), 3) if st == "OPEN" else round(raw_q * 1.25, 3)
            exp_cls = "CRITICAL" if exp_q >= 12.0 else ("ELEVATED" if exp_q >= 6.0 else "NOMINAL")
            if abs(q_val - exp_q) > 0.02 or rclass != exp_cls:
                runoff_matches_committed_culverts = False
                break
        with ZipFile(qgz_path) as qgz_zip:
            qgs_names = [name for name in qgz_zip.namelist() if name.endswith(".qgs")]
            qgs_xml = qgz_zip.read(qgs_names[0]).decode("utf-8", errors="replace") if qgs_names else ""
        pdf_path = workspace / "role_a/basin_risk_map.pdf"
        audit_path = workspace / "role_a/runoff_audit.json"
        audit_data = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
        audit_subs = audit_data.get("subbasins") or {}
        audit_consistent = len(audit_subs) == 16 and all(
            abs(float((audit_subs.get(bid) or {}).get("q_peak_cms", -99.0)) - subbasins_now[bid][3]) <= 0.02
            for bid in subbasins_now
        )
        checks_a = {
            "subbasins_match_committed_culverts": runoff_matches_committed_culverts,
            "layout_saved_in_qgz": "Basin_Risk_Map" in qgs_xml,
            "pdf_exported": pdf_path.is_file() and pdf_path.stat().st_size > 1500 and pdf_path.read_bytes()[:4] == b"%PDF",
            "runoff_audit_and_qgz_hash_match": audit_consistent and audit_data.get("qgz_sha256") == sha256_file(qgz_path),
        }
        closure_path = workspace / "role_b/closure_notice.json"
        b_pdf_path = workspace / "role_b/closure_alert_atlas.pdf"
        sens_path = workspace / "role_b/buffer_sensitivity.json"
        closure_data = json.loads(closure_path.read_text(encoding="utf-8")) if closure_path.is_file() else {}
        sens_ok = sens_path.is_file() and all((workspace / f"role_b/sensitivity_r{rad}.png").is_file() for rad in (125, 175, 225, 250, 300, 350))
        actual_blocked_in_culverts = sorted(cid for cid, (st, cap) in culverts_now.items() if st == "BLOCKED" and abs(cap) <= 1e-6)
        checks_b = {
            "culverts_updated_in_gpkg": actual_blocked_in_culverts == expected_blocked,
            "alert_layer_in_gpkg": alert_ids == expected_blocked,
            "alert_layer_and_layout_in_qgz": "blocked_culverts_alert" in qgs_xml and "Closure_Alert_Atlas" in qgs_xml,
            "closure_pdf_sensitivity_and_json_valid": sens_ok and b_pdf_path.is_file() and b_pdf_path.stat().st_size > 1500 and sorted(closure_data.get("blocked_culvert_ids") or []) == expected_blocked,
        }
        role_a_pass = all(checks_a.values())
        role_b_pass = all(checks_b.values())
        return {
            "task_id": task_id,
            "role_a_pass": role_a_pass,
            "role_b_pass": role_b_pass,
            "joint_pass": role_a_pass and role_b_pass,
            "checks_a": checks_a,
            "checks_b": checks_b,
            "diagnostics": {"blocked_in_culverts": actual_blocked_in_culverts, "alert_ids": alert_ids},
        }

    if task_id == "PR-FREECAD-1":
        inspect_out = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        inspect_json = Path(inspect_out.name)
        inspect_out.close()
        fc_probe = textwrap.dedent(f'''
            import json, FreeCAD, Part
            from pathlib import Path
            ws = Path(r"{workspace}")
            doc = FreeCAD.openDocument(str(ws / "actuator_mount.FCStd"))
            sheet = doc.getObject("MasterSpec")
            bore_d = float(sheet.get("B2"))
            bcr = float(sheet.get("B3"))
            housing = doc.getObject("BaseHousing").Shape
            cap = doc.getObject("SpigotCap").Shape
            common_vol = float(housing.common(cap).Volume)
            cap_bb = cap.BoundBox
            spigot_slice = Part.makeCylinder(60.0, 4.0, FreeCAD.Vector(0, 0, 28.0)).common(cap)
            spigot_bb = spigot_slice.BoundBox
            spigot_od = round(max(spigot_bb.XLength, spigot_bb.YLength), 3) if spigot_slice.Volume > 1.0 else 0.0
            pin_hits_housing = 0.0
            pin_hits_cap = 0.0
            for px, py in [(bcr, 0.0), (-bcr, 0.0), (0.0, bcr), (0.0, -bcr)]:
                pin = Part.makeCylinder(2.8, 50.0, FreeCAD.Vector(px, py, -2.0))
                pin_hits_housing += float(pin.common(housing).Volume)
                pin_hits_cap += float(pin.common(cap).Volume)
            step_cap_ok = False
            step_cap_path = ws / "role_a/spigot_cap.step"
            if step_cap_path.is_file():
                sc = Part.read(str(step_cap_path))
                step_cap_ok = abs(sc.Volume - cap.Volume) <= 5.0
            step_housing_ok = False
            step_h_path = ws / "role_b/base_housing.step"
            if step_h_path.is_file():
                sh = Part.read(str(step_h_path))
                step_housing_ok = abs(sh.Volume - housing.Volume) <= 5.0
            bore_probe = Part.makeCylinder(23.5, 20.0, FreeCAD.Vector(0, 0, 5.0))
            bore_48_clear = float(bore_probe.common(housing).Volume) <= 0.05
            out = {{
                "bore_d": bore_d, "bcr": bcr, "common_vol": common_vol,
                "cap_zmin": float(cap_bb.ZMin), "cap_zmax": float(cap_bb.ZMax),
                "spigot_od": spigot_od, "pin_hits_housing": pin_hits_housing, "pin_hits_cap": pin_hits_cap,
                "step_cap_ok": step_cap_ok, "step_housing_ok": step_housing_ok, "bore_48_clear": bore_48_clear,
            }}
            open(r"{inspect_json}", "w").write(json.dumps(out))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as py_f:
            py_f.write(fc_probe)
            py_path = Path(py_f.name)
        try:
            run_checked(["freecadcmd", str(py_path)], timeout_s=120)
            fc_info = json.loads(inspect_json.read_text(encoding="utf-8"))
            fit_path = workspace / "role_a/cap_fit_check.json"
            fit_data = json.loads(fit_path.read_text(encoding="utf-8")) if fit_path.is_file() else {}
            eco_path = workspace / "role_b/eco_119_summary.json"
            sweep_path = workspace / "role_b/thermal_volume_sweep.json"
            eco_data = json.loads(eco_path.read_text(encoding="utf-8")) if eco_path.is_file() else {}
            sweep_ok = sweep_path.is_file() and len(json.loads(sweep_path.read_text(encoding="utf-8"))) == 48 and (workspace / "role_b/sweeps/step_48.stl").is_file()
            checks_a = {
                "spigot_cap_machined_to_master_spec": (
                    abs(fc_info["cap_zmin"] - 26.0) <= 0.2
                    and abs(fc_info["cap_zmax"] - 44.0) <= 0.2
                    and abs(fc_info["spigot_od"] - (fc_info["bore_d"] - 0.40)) <= 0.15
                ),
                "bolt_holes_aligned_and_zero_interference": (
                    fc_info["common_vol"] <= 0.05 and fc_info["pin_hits_cap"] <= 0.05
                ),
                "step_and_fit_json_match_saved_doc": (
                    fc_info["step_cap_ok"]
                    and abs(float(fit_data.get("bore_diameter_mm") or 0.0) - fc_info["bore_d"]) <= 0.1
                    and abs(float(fit_data.get("bolt_circle_radius_mm") or 0.0) - fc_info["bcr"]) <= 0.1
                ),
            }
            checks_b = {
                "master_spec_upgraded_to_eco119": (
                    abs(fc_info["bore_d"] - 48.0) <= 0.05 and abs(fc_info["bcr"] - 35.0) <= 0.05
                ),
                "base_housing_48mm_bore_and_35mm_bolts": (
                    fc_info["bore_48_clear"] and fc_info["pin_hits_housing"] <= 0.05
                ),
                "housing_step_and_eco_json": (
                    fc_info["step_housing_ok"] and sweep_ok and abs(float(eco_data.get("bore_diameter_mm") or 0.0) - 48.0) <= 0.1
                ),
            }
            role_a_pass = all(checks_a.values())
            role_b_pass = all(checks_b.values())
            return {
                "task_id": task_id,
                "role_a_pass": role_a_pass,
                "role_b_pass": role_b_pass,
                "joint_pass": role_a_pass and role_b_pass,
                "checks_a": checks_a,
                "checks_b": checks_b,
                "diagnostics": fc_info,
            }
        finally:
            py_path.unlink(missing_ok=True)
            inspect_json.unlink(missing_ok=True)

    if task_id == "PR-INKSCAPE-1":
        from PIL import Image
        svg_path = workspace / "panel_master.svg"
        tree = ElementTree.parse(svg_path)
        root = tree.getroot()
        by_id = {elem.attrib.get("id"): elem for elem in root.iter() if elem.attrib.get("id")}
        callouts_ok = all(
            by_id.get(f"callout_{idx:02d}") is not None
            and abs(float(by_id[f"callout_{idx:02d}"].attrib.get("stroke-width", "0")) - 2.5) <= 0.05
            and by_id[f"callout_{idx:02d}"].attrib.get("stroke-linecap") == "round"
            for idx in range(1, 7)
        )
        reg_ok = by_id.get("reg_mark_ne") is not None
        proof_png = workspace / "role_a/panel_proof_300dpi.png"
        manifest_path = workspace / "role_a/proof_manifest.json"
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        rerender_png = Path(tempfile.mktemp(suffix=".png"))
        try:
            run_checked(["inkscape", "--export-type=png", "--export-dpi=300", f"--export-filename={rerender_png}", str(svg_path)], timeout_s=90)
            proof_diff = mean_rgb_diff(proof_png, rerender_png) if proof_png.is_file() else 255.0
            with Image.open(rerender_png) as fresh_im:
                rgb_b = fresh_im.convert("RGB").tobytes()
                fresh_ratio = round(sum(1 for idx in range(0, len(rgb_b), 3) if (rgb_b[idx], rgb_b[idx + 1], rgb_b[idx + 2]) != (24, 32, 40)) / max(1, len(rgb_b) // 3), 4)
        finally:
            rerender_png.unlink(missing_ok=True)
        svg_qa_elem = by_id.get("qa_ink_ratio")
        svg_qa_val = float(svg_qa_elem.text.strip()) if (svg_qa_elem is not None and svg_qa_elem.text) else -1.0
        checks_a = {
            "callouts_and_reg_mark_in_svg": callouts_ok and reg_ok,
            "proof_png_and_manifest_hashes": (
                proof_png.is_file()
                and manifest_data.get("png_300_sha256") == sha256_file(proof_png)
                and manifest_data.get("svg_sha256") == sha256_file(svg_path)
            ),
            "proof_and_ink_ratio_match_saved_svg": proof_diff <= 1.0 and abs(svg_qa_val - fresh_ratio) <= 0.005,
        }
        grad_elem = by_id.get("accent_grad")
        stop_colors = []
        if grad_elem is not None:
            for child in list(grad_elem):
                if child.tag.endswith("stop"):
                    scol = child.attrib.get("stop-color", "")
                    if not scol and "stop-color:" in child.attrib.get("style", ""):
                        for part in child.attrib["style"].split(";"):
                            if part.strip().startswith("stop-color:"):
                                scol = part.split(":", 1)[1].strip()
                    stop_colors.append(scol.upper())
        badges_ok = all(by_id.get(bid) is not None for bid in ("badge_temp", "badge_volt", "badge_lock"))
        rev_tag_ok = by_id.get("qa_brand_rev") is not None and (by_id["qa_brand_rev"].text or "").strip() == "BRD-77"
        pal_path = workspace / "role_b/palette_applied.json"
        cand_audit_path = workspace / "role_b/candidate_contrast_audit.json"
        cand_ok = cand_audit_path.is_file() and all((workspace / f"role_b/trials/cand_{code}_600dpi.png").is_file() for code in ("C1", "C2", "C3", "C4", "BRD-77", "C6"))
        pal_data = json.loads(pal_path.read_text(encoding="utf-8")) if pal_path.is_file() else {}
        checks_b = {
            "gradient_updated_to_cyan": stop_colors[:2] == ["#0099DD", "#00DDFF"],
            "three_hud_badges_and_rev_tag_in_svg": badges_ok and rev_tag_ok,
            "preview_png_and_palette_json": (
                (workspace / "role_b/hud_badges_300dpi.png").is_file()
                and (workspace / "role_b/hud_badges_600dpi.png").is_file()
                and cand_ok
                and pal_data.get("revision_id") == "BRD-77"
            ),
        }
        role_a_pass = all(checks_a.values())
        role_b_pass = all(checks_b.values())
        return {
            "task_id": task_id,
            "role_a_pass": role_a_pass,
            "role_b_pass": role_b_pass,
            "joint_pass": role_a_pass and role_b_pass,
            "checks_a": checks_a,
            "checks_b": checks_b,
            "diagnostics": {"stop_colors": stop_colors, "proof_rerender_rgb_diff": round(proof_diff, 3)},
        }

    raise KeyError(f"Unknown task_id: {task_id}")


def analyze_version_history(history_rows: list[dict]) -> dict:
    distinct_hashes = []
    for row in history_rows:
        sha = row.get("project_sha256")
        if sha and (not distinct_hashes or distinct_hashes[-1] != sha):
            distinct_hashes.append(sha)
    regressions = []
    for signal_key in ("role_a_in_project", "role_b_in_project"):
        seen_true = False
        true_ts = None
        for row in history_rows:
            val = row.get(signal_key)
            if val is True and not seen_true:
                seen_true = True
                true_ts = row.get("timestamp")
            elif val is False and seen_true:
                regressions.append({
                    "signal": signal_key,
                    "first_true_timestamp": true_ts,
                    "reverted_false_timestamp": row.get("timestamp"),
                    "reverted_sha256": row.get("project_sha256"),
                })
                seen_true = False
    return {
        "sample_count": len(history_rows),
        "distinct_project_versions": len(distinct_hashes),
        "version_chain": distinct_hashes,
        "lost_update_regressions": regressions,
        "lost_update_observed": bool(regressions),
    }


def self_validate_all(root_dir: Path) -> dict:
    root_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for entry in TASK_CATALOG:
        tid = entry["id"]
        tdir = root_dir / tid
        pristine_ws = tdir / "pristine"
        build_task_workspace(tid, pristine_ws)
        g_pristine = grade_workspace(tid, pristine_ws)

        a_ws = tdir / "a_only"
        shutil.copytree(pristine_ws, a_ws)
        solve_reference_role(tid, "A", a_ws)
        g_a = grade_workspace(tid, a_ws)

        b_ws = tdir / "b_only"
        shutil.copytree(pristine_ws, b_ws)
        solve_reference_role(tid, "B", b_ws)
        g_b = grade_workspace(tid, b_ws)

        seq_ba_ws = tdir / "seq_ba"
        shutil.copytree(pristine_ws, seq_ba_ws)
        solve_reference_role(tid, "B", seq_ba_ws)
        solve_reference_role(tid, "A", seq_ba_ws)
        g_seq_ba = grade_workspace(tid, seq_ba_ws)

        race_ws = tdir / "simulated_race"
        shutil.copytree(pristine_ws, race_ws)
        snaps = [probe_lightweight_signals(tid, race_ws)]
        solve_reference_role(tid, "A", race_ws, source_snapshot=pristine_ws)
        snaps.append(probe_lightweight_signals(tid, race_ws))
        solve_reference_role(tid, "B", race_ws, source_snapshot=pristine_ws)
        snaps.append(probe_lightweight_signals(tid, race_ws))
        g_race = grade_workspace(tid, race_ws)
        hist = analyze_version_history(snaps)

        checks_ok = (
            (not g_pristine["role_a_pass"] and not g_pristine["role_b_pass"])
            and (g_a["role_a_pass"] and not g_a["role_b_pass"])
            and (not g_b["role_a_pass"] and g_b["role_b_pass"])
            and g_seq_ba["joint_pass"]
            and (not g_race["joint_pass"])
        )
        summary[tid] = {
            "validation_passed": checks_ok,
            "pristine": [g_pristine["role_a_pass"], g_pristine["role_b_pass"]],
            "a_only": [g_a["role_a_pass"], g_a["role_b_pass"]],
            "b_only": [g_b["role_a_pass"], g_b["role_b_pass"]],
            "seq_ba_joint": g_seq_ba["joint_pass"],
            "simulated_race_joint": g_race["joint_pass"],
            "simulated_race_checks": {"a": g_race["checks_a"], "b": g_race["checks_b"]},
            "version_history": hist,
        }
    write_json(root_dir / "self_validation.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--task", required=True)
    p_build.add_argument("--workspace", type=Path, required=True)

    p_grade = sub.add_parser("grade")
    p_grade.add_argument("--task", required=True)
    p_grade.add_argument("--workspace", type=Path, required=True)
    p_grade.add_argument("--out", type=Path, required=True)

    p_val = sub.add_parser("self-validate")
    p_val.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "build":
        info = build_task_workspace(args.task, args.workspace.resolve())
        print(json.dumps(info, indent=2))
        return 0
    if args.cmd == "grade":
        res = grade_workspace(args.task, args.workspace.resolve())
        write_json(args.out.resolve(), res)
        print(json.dumps(res, indent=2))
        return 0
    if args.cmd == "self-validate":
        res = self_validate_all(args.out.resolve())
        print(json.dumps(res, indent=2))
        return 0 if all(item["validation_passed"] for item in res.values()) else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
