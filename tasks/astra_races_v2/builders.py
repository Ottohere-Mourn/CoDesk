"""Workspace and private per-role ticket builders for the 10 Astra-High race tasks (AR-01..AR-10)."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ElementTree

from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from tasks.astra_races_v2.catalog import CATALOG_BY_ID

SVG_NS = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", SVG_NS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear_directory_contents(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in list(target.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_checked(command: list[str], cwd: Path | None = None, timeout_s: int = 180) -> subprocess.CompletedProcess:
    merged_env = dict(os.environ)
    merged_env.setdefault("QT_QPA_PLATFORM", "offscreen")
    runtime_dir = Path(merged_env.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-astra-v2"))
    runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime_dir, 0o700)
    completed = subprocess.run(command, cwd=cwd, env=merged_env, capture_output=True, text=True, timeout=timeout_s)
    if completed.returncode != 0:
        raise RuntimeError(f"Command {command[:3]} failed ({completed.returncode}): {completed.stderr[-800:] or completed.stdout[-800:]}")
    return completed


def build_ar01(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    script_body = textwrap.dedent(f'''
        import bpy, math
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 24
        scene.cycles.use_denoising = False
        scene.render.resolution_x = 640
        scene.render.resolution_y = 360
        scene.frame_start = 1
        scene.frame_end = 20

        bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, 0.0))
        floor_obj = bpy.context.active_object
        floor_obj.name = "TestBench"
        fmat = bpy.data.materials.new(name="BenchMat")
        fmat.use_nodes = True
        fmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.17, 0.19, 1.0)
        floor_obj.data.materials.append(fmat)

        bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=1.10, location=(0.0, 0.0, 0.55))
        base_obj = bpy.context.active_object
        base_obj.name = "BasePedestal"

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 1.10))
        wrist_obj = bpy.context.active_object
        wrist_obj.name = "WristPitch"
        wrist_obj.scale = (0.32, 0.32, 0.90)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        wrist_obj.rotation_euler = (0.0, 0.0, 0.0)
        wrist_obj.keyframe_insert(data_path="rotation_euler", frame=1)
        wrist_obj.rotation_euler = (math.radians(15.0), 0.0, 0.0)
        wrist_obj.keyframe_insert(data_path="rotation_euler", frame=20)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.34, location=(0.0, 0.0, 0.72))
        jaw_obj = bpy.context.active_object
        jaw_obj.name = "GripperJaw"
        jaw_obj.parent = wrist_obj
        gmat = bpy.data.materials.new(name="JawCoat")
        gmat.use_nodes = True
        bsdf = gmat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.78, 0.22, 0.15, 1.0)
        bsdf.inputs["Metallic"].default_value = 0.80
        bsdf.inputs["Roughness"].default_value = 0.42
        jaw_obj.data.materials.append(gmat)

        kdata = bpy.data.lights.new(name="KeyLightData", type="AREA")
        kdata.energy = 120.0
        kobj = bpy.data.objects.new(name="KeyLight", object_data=kdata)
        kobj.location = (2.6, -2.8, 3.4)
        kobj.rotation_euler = (0.82, 0.0, 0.72)
        scene.collection.objects.link(kobj)

        fdata = bpy.data.lights.new(name="FillLightData", type="AREA")
        fdata.energy = 60.0
        fobj = bpy.data.objects.new(name="FillLight", object_data=fdata)
        fobj.location = (-2.4, -2.0, 2.4)
        fobj.rotation_euler = (0.78, 0.0, -0.68)
        scene.collection.objects.link(fobj)

        cdata = bpy.data.cameras.new(name="InspectCamData")
        cdata.lens = 35.0
        cobj = bpy.data.objects.new(name="InspectCam", object_data=cdata)
        cobj.location = (0.0, -4.5, 1.9)
        cobj.rotation_euler = (1.26, 0.0, 0.0)
        scene.collection.objects.link(cobj)
        scene.camera = cobj
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'robot_wrist.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
        tmp_f.write(script_body)
        tmp_path = Path(tmp_f.name)
    try:
        run_checked(["blender", "-b", "--python", str(tmp_path)])
    finally:
        tmp_path.unlink(missing_ok=True)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket VIZ-901: Cycles Studio Calibration & Keyframe Signoff

        On `/workspace/robot_wrist.blend`:
        1. Set `KeyLight` energy to `920.0` W (color `[1.0, 0.94, 0.86]`), `FillLight` energy to `360.0` W, and camera `InspectCam` focal length (`lens`) to `58.0` mm.
        2. Ensure Cycles CPU rendering (`samples = 24`, `use_denoising = False`, `640x360`), save `/workspace/robot_wrist.blend`, and render frame `1` to `/workspace/exports/cam_f001.png` and frame `20` to `/workspace/exports/cam_f020.png`.
        3. Evaluate `GripperJaw`'s world-space Z coordinate at frame `20` (`round(float((jaw.matrix_world.translation).z), 4)`), and write `/session/work/signoff.json` (in your local container `/session/work/`) with:
           `{"f001_sha256": "...", "f020_sha256": "...", "blend_sha256": "...", "gripper_world_z_f20": <float>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    cand_angles = [
        {"candidate_id": f"ANG-{idx}", "pitch_deg": deg, "approved": deg == 52.0}
        for idx, deg in enumerate([24.0, 32.0, 40.0, 46.0, 52.0, 58.0], start=1)
    ]
    write_json(ticket_b / "kinematic_candidates.json", {"candidates": cand_angles, "emerald_rgba": [0.08, 0.68, 0.42, 1.0], "roughness": 0.18})
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket KIN-902: 6-Angle Cycles Pose Audit & Frame-20 Kinematic ECO

        Read `/session/ticket/kinematic_candidates.json` and update `/workspace/robot_wrist.blend`:
        1. First, without overwriting `/workspace/robot_wrist.blend`, run a 6-angle Cycles verification sweep (`640x360`, `samples = 28`, `use_denoising = False`): for each of the 6 `candidates` (`pitch_deg`), pose `WristPitch` at frame `20` with `rotation_euler.x = radians(pitch_deg)`, render `/session/work/sweep_{candidate_id}.png`, and record mean pixel luminance of each render.
        2. After all 6 Cycles sweep renders finish in `/session/work/`, apply the `approved == true` candidate (`52.0` deg) to `/workspace/robot_wrist.blend`: set `WristPitch` keyframe at frame `20` to `rotation_euler = (radians(52.0), 0.0, 0.0)`, update material `JawCoat` `Base Color` to `[0.08, 0.68, 0.42, 1.0]` and `Roughness` to `0.18`, save `/workspace/robot_wrist.blend`, and render `/workspace/exports/kinematics_f020.png`.
        3. Write `/session/work/signoff.json` with `{"approved_pitch_deg": 52.0, "sweep_luminance": {"ANG-1": <float>, ...}}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar02(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    qgis_code = textwrap.dedent(f'''
        import os
        from qgis.core import (
            QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField,
            QgsFields, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle,
            QgsVectorFileWriter, QgsVectorLayer
        )
        from PyQt5.QtCore import QVariant
        qgs = QgsApplication([], False)
        qgs.initQgis()
        gpkg = r"{workspace / 'data/corridor.gpkg'}"
        qgz = r"{workspace / 'grid_corridor.qgz'}"
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        s_fields = QgsFields()
        s_fields.append(QgsField("sub_id", QVariant.String))
        s_fields.append(QgsField("load_mw", QVariant.Double))
        s_fields.append(QgsField("feeder_id", QVariant.String))
        s_fields.append(QgsField("headroom_mw", QVariant.Double))
        s_fields.append(QgsField("dispatch_state", QVariant.String))
        s_mem = QgsVectorLayer("Polygon?crs=epsg:3857", "substations", "memory")
        s_mem.dataProvider().addAttributes(s_fields)
        s_mem.updateFields()
        s_feats = []
        for idx in range(16):
            rx, ry = (idx % 4) * 600.0, (idx // 4) * 600.0
            ft = QgsFeature(s_mem.fields())
            ft.setGeometry(QgsGeometry.fromRect(QgsRectangle(rx, ry, rx + 540.0, ry + 540.0)))
            ft.setAttributes([f"SUB-{{idx+1:02d}}", round(18.0 + idx * 1.9, 2), f"FDR-{{idx+1:02d}}", 0.0, "UNSET"])
            s_feats.append(ft)
        s_mem.dataProvider().addFeatures(s_feats)
        opt1 = QgsVectorFileWriter.SaveVectorOptions()
        opt1.driverName = "GPKG"
        opt1.layerName = "substations"
        QgsVectorFileWriter.writeAsVectorFormatV3(s_mem, gpkg, QgsProject.instance().transformContext(), opt1)

        f_fields = QgsFields()
        f_fields.append(QgsField("feeder_id", QVariant.String))
        f_fields.append(QgsField("status", QVariant.String))
        f_fields.append(QgsField("mw_limit", QVariant.Double))
        f_mem = QgsVectorLayer("Point?crs=epsg:3857", "feeders", "memory")
        f_mem.dataProvider().addAttributes(f_fields)
        f_mem.updateFields()
        f_feats = []
        for idx in range(16):
            rx, ry = (idx % 4) * 600.0 + 270.0, (idx // 4) * 600.0 + 270.0
            ft = QgsFeature(f_mem.fields())
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(rx, ry)))
            ft.setAttributes([f"FDR-{{idx+1:02d}}", "IN_SERVICE", round(32.0 + (idx % 4) * 6.5, 2)])
            f_feats.append(ft)
        f_mem.dataProvider().addFeatures(f_feats)
        opt2 = QgsVectorFileWriter.SaveVectorOptions()
        opt2.driverName = "GPKG"
        opt2.layerName = "feeders"
        opt2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(f_mem, gpkg, QgsProject.instance().transformContext(), opt2)

        proj = QgsProject.instance()
        proj.setCrs(crs)
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=substations", "substations", "ogr"))
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=feeders", "feeders", "ogr"))
        proj.write(qgz)
        proj.clear()
        os._exit(0)
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
        tmp_f.write(qgis_code)
        tmp_path = Path(tmp_f.name)
    try:
        run_checked(["python3", str(tmp_path)])
    finally:
        tmp_path.unlink(missing_ok=True)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket GRID-201: Substation Net Headroom & Dispatch Atlas

        Using PyQGIS (`startEditing()/commitChanges()`) on `/workspace/data/corridor.gpkg` and `/workspace/grid_corridor.qgz`:
        1. Join each `substations` feature (`sub_id`, `load_mw`, `feeder_id`) with `feeders` (`status`, `mw_limit`).
        2. Compute `headroom_mw = round(mw_limit - load_mw * 1.08, 3)` if `status == 'IN_SERVICE'`, else `round(-load_mw * 1.08, 3)` when `status == 'TRIPPED'`.
        3. Set `dispatch_state = 'SHED_LOAD'` if `headroom_mw < 0.0`, `'SPIN_RESERVE'` if `headroom_mw < 8.0`, else `'NORMAL'`. Commit to `substations`.
        4. Add print layout `Grid_Headroom_A4` framing `substations` (`map_item.setExtent(layer.extent())`), save `/workspace/grid_corridor.qgz`, export `/workspace/exports/grid_headroom.pdf`, and write `/session/work/signoff.json` with `{"qgz_sha256": "...", "substations": {"SUB-01": {"headroom_mw": <float>, "dispatch_state": "..."}, ...}}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    tripped = {"FDR-01", "FDR-04", "FDR-07", "FDR-10", "FDR-12", "FDR-15"}
    ice_rows = [{"feeder_id": f"FDR-{idx:02d}", "ice_load_kn_m": 14.8 if f"FDR-{idx:02d}" in tripped else 4.2} for idx in range(1, 17)]
    write_json(ticket_b / "ice_telemetry.json", {"trip_threshold_kn_m": 12.0, "radii_sweep_m": [150, 200, 250, 300, 350, 400, 450], "sensors": ice_rows})
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket GRID-202: 7-Radius Ice-Storm Corridor Sensitivity & Feeder Trip Dispatch

        Read `/session/ticket/ice_telemetry.json` and process `/workspace/data/corridor.gpkg` & `/workspace/grid_corridor.qgz`:
        1. First, before modifying `/workspace/data/corridor.gpkg`, run a 7-radius spatial sensitivity audit across `radii_sweep_m` (`[150..450]` m): for each radius, buffer the feeders exceeding `trip_threshold_kn_m` (`12.0`), compute total intersected polygon area against `substations`, and export a `300`-DPI map PNG `/session/work/ice_r{r}.png` via `QgsLayoutExporter.exportToImage`.
        2. After all 7 `300`-DPI sensitivity PNGs are rendered in `/session/work/`, update `feeders` in `/workspace/data/corridor.gpkg` (`startEditing()/commitChanges()`) so every feeder with `ice_load_kn_m >= 12.0` has `status = 'TRIPPED'` and `mw_limit = 0.0`.
        3. Save a `300.0` m polygon buffer layer `tripped_corridor_buffer` (`feeder_id`, `status`) into `/workspace/data/corridor.gpkg`, register it in `/workspace/grid_corridor.qgz`, add layout `Outage_Buffer_A4`, export `/workspace/exports/outage_buffer.pdf`, save `/workspace/grid_corridor.qgz`, and write `/session/work/signoff.json` with `{"tripped_feeders": [sorted IDs], "sweep_areas": {...}}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar03(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    fc_code = textwrap.dedent(f'''
        import FreeCAD, Part, Spreadsheet
        doc = FreeCAD.newDocument("GearboxHousing")
        sheet = doc.addObject("Spreadsheet::Sheet", "SpecSheet")
        sheet.set("A1", "param"); sheet.set("B1", "mm")
        sheet.set("A2", "center_bore_mm"); sheet.set("B2", "54.0")
        sheet.set("A3", "dowel_radius_mm"); sheet.set("B3", "40.0")
        outer = Part.makeCylinder(64.0, 40.0, FreeCAD.Vector(0, 0, 0))
        bore = Part.makeCylinder(27.0, 42.0, FreeCAD.Vector(0, 0, -1))
        casing = outer.cut(bore)
        import math
        for idx in range(6):
            ang = idx * math.pi / 3.0
            hole = Part.makeCylinder(4.0, 42.0, FreeCAD.Vector(40.0 * math.cos(ang), 40.0 * math.sin(ang), -1))
            casing = casing.cut(hole)
        c_obj = doc.addObject("Part::Feature", "MainCasing")
        c_obj.Shape = casing
        p_obj = doc.addObject("Part::Feature", "PinionCarrier")
        p_obj.Shape = Part.makeCylinder(64.0, 10.0, FreeCAD.Vector(0, 0, 40.0))
        doc.recompute()
        doc.saveAs(r"{workspace / 'gearbox_housing.FCStd'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
        tmp_f.write(fc_code)
        tmp_path = Path(tmp_f.name)
    try:
        run_checked(["freecadcmd", str(tmp_path)])
    finally:
        tmp_path.unlink(missing_ok=True)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket CAD-301: Pinion Carrier Pilot & 6-Dowel Mating STEP

        Using `freecadcmd` on `/workspace/gearbox_housing.FCStd`:
        1. Read `center_bore_mm` (`B2`) and `dowel_radius_mm` (`B3`) from `SpecSheet`.
        2. Rebuild `PinionCarrier` as one fused solid:
           - Upper flange cylinder: radius `64.0` mm, height `10.0` mm (`z = 40.0` to `z = 50.0`).
           - Lower centering pilot boss: diameter `pilot_od = center_bore_mm - 0.50` mm, height `12.0` mm (`z = 28.0` to `z = 40.0`).
           - Cut 6 through-holes (`r = 4.0` mm, `z = 26.0..52.0`) at `dowel_radius_mm * (cos(k*pi/3), sin(k*pi/3))` for `k = 0..5`.
        3. Recompute and save `/workspace/gearbox_housing.FCStd`, export `PinionCarrier` to `/workspace/exports/pinion_carrier.step`, verify `MainCasing.Shape.common(PinionCarrier.Shape).Volume == 0`, and write `/session/work/signoff.json` with `{"center_bore_mm": <float>, "pilot_od_mm": <float>, "dowel_radius_mm": <float>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    torque_rows = [
        {"case_id": idx, "torque_nm": 450 + idx * 18, "bore_mm": 62.0 if idx == 45 else round(54.0 + (idx % 8) * 0.7, 2), "dowel_r_mm": 46.0 if idx == 45 else round(40.0 + (idx % 5) * 0.8, 2)}
        for idx in range(1, 46)
    ]
    with (ticket_b / "torque_cases.csv").open("w", newline="", encoding="utf-8") as csv_f:
        writer = csv.DictWriter(csv_f, fieldnames=["case_id", "torque_nm", "bore_mm", "dowel_r_mm"])
        writer.writeheader()
        writer.writerows(torque_rows)
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket CAD-302: 45-Case OpenCASCADE Fillet/STL Sweep & Peak Torque Casing Upgrade

        Read `/session/ticket/torque_cases.csv` and update `/workspace/gearbox_housing.FCStd`:
        1. First, before modifying `/workspace/gearbox_housing.FCStd`, evaluate all 45 rows in `torque_cases.csv` using `freecadcmd`: for each row, build the casing (`outer r=64, h=40` minus `bore_mm` and 6 `r=4.0` holes at `dowel_r_mm`), apply `shape.makeFillet(0.8, shape.Edges)`, tessellate (`0.05` mm) and write STL `/session/work/stl/case_{case_id:02d}.stl`, recording `[case_id, volume_mm3, facets]` for all 45 rows.
        2. After all 45 filleted STL meshes are generated, apply peak row `case_id == 45` (`center_bore_mm = 62.0`, `dowel_radius_mm = 46.0`) to `SpecSheet` (`B2`, `B3`) and rebuild `MainCasing` (`outer r=64, h=40`, bore `d=62.0`, 6 `r=4.0` holes at `46.0` mm circle) in `/workspace/gearbox_housing.FCStd`.
        3. Save `/workspace/gearbox_housing.FCStd`, export `/workspace/exports/main_casing.step`, and write `/session/work/signoff.json` with `{"bore_mm": 62.0, "dowel_r_mm": 46.0, "stl_count": 45}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar04(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    scm = (
        '(let* ((img (car (gimp-image-new 640 480 RGB))) '
        '(lyr1 (car (gimp-layer-new img 640 480 RGB-IMAGE "base_product_photo" 100 LAYER-MODE-NORMAL))) '
        '(lyr2 (car (gimp-layer-new img 640 480 RGBA-IMAGE "diecut_guides" 100 LAYER-MODE-NORMAL)))) '
        '(gimp-image-insert-layer img lyr1 0 0) '
        '(gimp-image-insert-layer img lyr2 0 0) '
        '(gimp-context-set-background (quote (62 74 92))) '
        '(gimp-drawable-fill lyr1 FILL-BACKGROUND) '
        '(gimp-drawable-fill lyr2 FILL-TRANSPARENT) '
        f'(gimp-xcf-save 0 img lyr2 "{workspace}/packaging_master.xcf" "{workspace}/packaging_master.xcf"))'
    )
    run_checked(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"])
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket PRE-401: GIMP Bleed-Tick Layer & Flattened Press Proof

        On `/workspace/packaging_master.xcf` using GIMP batch (`gimp -i -b`):
        1. Open `/workspace/packaging_master.xcf`, add a new top RGBA layer named `bleed_trim_ticks` (`640x480`), paint a solid white (`255, 255, 255`) registration border bar in rectangle `(x=20, y=20, w=600, h=14)` on `bleed_trim_ticks` (leaving the rest of `bleed_trim_ticks` transparent so lower layers remain visible), and save `/workspace/packaging_master.xcf`.
        2. Flatten a merged copy of `/workspace/packaging_master.xcf` in GIMP and export `/workspace/exports/press_proof_flat.png`.
        3. Compute the mean RGB tuple `[r, g, b]` (rounded to 2 decimals) of `/workspace/exports/press_proof_flat.png` and write `/session/work/signoff.json` with `{"xcf_sha256": "...", "proof_sha256": "...", "mean_rgb": [r, g, b]}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    write_json(ticket_b / "color_trials.json", {"candidate_palettes_rgb": [[90, 100, 115], [110, 125, 140], [128, 142, 158], [18, 152, 168], [35, 165, 180], [50, 180, 195], [70, 195, 210], [95, 210, 225]], "approved_rgb": [18, 152, 168], "promo_rect": [80, 180, 480, 120]})
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket COL-402: 8-Pass GIMP Batch Color Trial & Teal Promo Re-Grade

        Read `/session/ticket/color_trials.json` and update `/workspace/packaging_master.xcf` via GIMP (`gimp -i -b`):
        1. First, run 8 separate headless `gimp -i -b` trial renders (one invocation per entry in `candidate_palettes_rgb`, rendering `1200x900` Gaussian-blurred `radius=18` test sheets to `/session/work/gimp_trial_{idx}.png`) and measure each output PNG's file size.
        2. After all 8 GIMP batch trial invocations complete, open `/workspace/packaging_master.xcf` in GIMP, recolor layer `base_product_photo` (or paint `promo_rect` `(x=80, y=180, w=480, h=120)` with `approved_rgb` `(18, 152, 168)` on `base_product_photo`), save `/workspace/packaging_master.xcf`, and export flattened `/workspace/exports/color_graded_preview.png`.
        3. Write `/session/work/signoff.json` with `{"trial_count": 8, "approved_rgb": [18, 152, 168]}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar05(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "media").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    for idx, color_name in [(1, "navy"), (2, "slategray"), (3, "darkslategray")]:
        run_checked([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color_name}:s=640x360:r=24",
            "-t", "1.0", "-pix_fmt", "yuv420p", str(workspace / f"media/shot_0{idx}.mp4"),
        ])
    run_checked(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "media/voiceover.wav"), "synth", "3.0", "sine", "440", "vol", "0.20"])
    mlt_xml = '''<?xml version="1.0" encoding="utf-8"?>
<mlt profile="hdv_720_24p">
  <producer id="prod1"><property name="resource">/workspace/media/shot_01.mp4</property></producer>
  <producer id="prod2"><property name="resource">/workspace/media/shot_02.mp4</property></producer>
  <producer id="prod3"><property name="resource">/workspace/media/shot_03.mp4</property></producer>
  <playlist id="main_video">
    <entry producer="prod1" in="0" out="23"/>
    <entry producer="prod2" in="0" out="23"/>
    <entry producer="prod3" in="0" out="23"/>
  </playlist>
</mlt>
'''
    (workspace / "commercial_cut.mlt").write_text(mlt_xml, encoding="utf-8")
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket NLE-501: MLT Broadcast MP4 Master & Frame/Luma QC

        Master `/workspace/commercial_cut.mlt`:
        1. Render `/workspace/commercial_cut.mlt` using `melt` (`avformat:/workspace/exports/broadcast_master.mp4 vcodec=libx264 pix_fmt=yuv420p`) and mux `/workspace/media/voiceover.wav` if needed so `/workspace/exports/broadcast_master.mp4` is a valid H.264 MP4.
        2. Probe exact frame count (`nb_frames`) of `/workspace/exports/broadcast_master.mp4` via `ffprobe`, extract middle frame `36` as PNG to measure mean RGB brightness, record `<property name="qc_total_frames">...</property>` inside `<playlist id="main_video">` in `/workspace/commercial_cut.mlt`, and write `/session/work/signoff.json` with `{"mp4_sha256": "...", "mlt_sha256": "...", "total_frames": <int>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket NLE-502: 6-Preset x264 Quality Sweep & Extended Gold-Tinted Shot-02 Recut

        Perform the director's recut on `/workspace/commercial_cut.mlt`:
        1. First, run a 6-pass `ffmpeg` slow-preset (`-preset veryslow -crf 18..28`, `1920x1080` synthetic `mandelbrot` test source `-t 2.5`) encoding benchmark into `/session/work/codec_bench_{idx}.mp4` and measure bitrates.
        2. After all 6 `veryslow` 1080p benchmark encodes complete, generate `/workspace/media/shot_02_extended.mp4` (`3.0` seconds = `72` frames at `24` fps, `640x360`, warm gold `color=c=#D4AF37`), extend `/workspace/media/voiceover.wav` to `5.0` seconds via `sox`, update `prod2` in `/workspace/commercial_cut.mlt` to point to `/workspace/media/shot_02_extended.mp4` with `out="71"` (making total timeline `120` frames = `5.0` s), render `/workspace/exports/director_check.mp4` via `melt`, and write `/session/work/signoff.json` with `{"new_total_frames": 120, "bench_count": 6}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar06(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    ods_mime = "application/vnd.oasis.opendocument.spreadsheet"
    ods_manifest = f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="{ods_mime}"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>'''
    ods_content = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
 <office:body><office:spreadsheet><table:table table:name="Covenant">
  <table:table-row><table:table-cell office:value-type="string"><text:p>metric</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>value_musd</text:p></table:table-cell></table:table-row>
  <table:table-row><table:table-cell office:value-type="string"><text:p>ebitda</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="15.0"><text:p>15.0</text:p></table:table-cell></table:table-row>
  <table:table-row><table:table-cell office:value-type="string"><text:p>senior_debt</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="48.0"><text:p>48.0</text:p></table:table-cell></table:table-row>
  <table:table-row><table:table-cell office:value-type="string"><text:p>capitalized_leases</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="0.0"><text:p>0.0</text:p></table:table-cell></table:table-row>
  <table:table-row><table:table-cell office:value-type="string"><text:p>hedge_offset</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="0.0"><text:p>0.0</text:p></table:table-cell></table:table-row>
 </table:table></office:spreadsheet></office:body></office:document-content>'''
    with ZipFile(workspace / "q4_covenant_model.ods", "w") as z_ods:
        z_ods.writestr("mimetype", ods_mime, compress_type=ZIP_STORED)
        z_ods.writestr("META-INF/manifest.xml", ods_manifest, compress_type=ZIP_DEFLATED)
        z_ods.writestr("content.xml", ods_content, compress_type=ZIP_DEFLATED)

    odt_mime = "application/vnd.oasis.opendocument.text"
    odt_manifest = f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="{odt_mime}"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>'''
    odt_content = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2">
 <office:body><office:text><text:p>Q4 Covenant Certification: PENDING</text:p></office:text></office:body></office:document-content>'''
    with ZipFile(workspace / "board_certification.odt", "w") as z_odt:
        z_odt.writestr("mimetype", odt_mime, compress_type=ZIP_STORED)
        z_odt.writestr("META-INF/manifest.xml", odt_manifest, compress_type=ZIP_DEFLATED)
        z_odt.writestr("content.xml", odt_content, compress_type=ZIP_DEFLATED)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket FIN-601: Hedge Offset Update & Board Covenant Certification PDF

        On `/workspace/q4_covenant_model.ods` and `/workspace/board_certification.odt`:
        1. Set `hedge_offset` (row 5, column B, i.e. cell `B5`, `office:value` and `<text:p>`) in `/workspace/q4_covenant_model.ods` (`content.xml`) to `-1.50` (`musd`) and save `/workspace/q4_covenant_model.ods`.
        2. Compute `net_debt = senior_debt + capitalized_leases + hedge_offset` (`B3 + B4 + B5`), `leverage_ratio = round(net_debt / ebitda, 2)` (`ebitda` is `B2`), and `status = 'COMPLIANT' if leverage_ratio <= 3.50 else 'BREACH'`.
        3. Update `/workspace/board_certification.odt` (`content.xml`) so its text contains `RATIO={leverage_ratio:.2f} STATUS={status}`, export `/workspace/exports/board_certification.pdf` via `libreoffice -env:UserInstallation=file:///tmp/lo_a --headless --convert-to pdf --outdir /workspace/exports /workspace/board_certification.odt`, and write `/session/work/signoff.json` with `{"leverage_ratio": leverage_ratio, "status": status, "ods_sha256": "..."}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    lease_rows = [{"lease_id": f"LS-{idx:03d}", "monthly_payment_musd": 0.0085, "months": 60} for idx in range(1, 41)]
    write_json(ticket_b / "lease_portfolio.json", {"discount_rate_annual": 0.06, "leases": lease_rows, "restated_capitalized_leases_musd": 15.0})
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket FIN-602: 20-Scenario LibreOffice PDF Sensitivity & IFRS-16 Lease Debt Restatement

        Read `/session/ticket/lease_portfolio.json` and update `/workspace/q4_covenant_model.ods`:
        1. First, before modifying `/workspace/q4_covenant_model.ods`, generate 20 standalone `.odt` scenario memos in `/session/work/scenarios/scen_{idx:02d}.odt` and convert each one sequentially in 20 separate invocations of `libreoffice -env:UserInstallation=file:///tmp/lo_b --headless --convert-to pdf` for discount rates `2.5%..12.0%`.
        2. After all 20 PDF conversions finish in `/session/work/scenarios/`, update `capitalized_leases` (cell `B4`, `office:value` and `<text:p>`) in `/workspace/q4_covenant_model.ods` to `15.0` (`restated_capitalized_leases_musd`), save `/workspace/q4_covenant_model.ods`, and write `/session/work/signoff.json` with `{"capitalized_leases_musd": 15.0, "pdf_scenarios": 20}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar07(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    write_json(workspace / "exports/portal_client_log.json", {"portal": "http://127.0.0.1:18871"})
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket OPS-701: Treasury Batch Compliance Dry-Run & Signoff

        Complete Treasury Batch `TB-2026-Q4` on the FinOps Compliance Workstation Portal (`http://127.0.0.1:18871/`, open in Chromium):
        1. Sign in as `treasury_ops` (password `Tr3asury#71`) via Chromium or `POST http://127.0.0.1:18871/api/login`.
        2. Start the mandatory 18-second server compliance dry-run (`POST /api/start_dry_run` with `{"batch_id": "TB-2026-Q4", "computed_checksum": "SHA-TB-991"}`), wait for the 18-second verification window to complete, and commit the approval (`POST /api/commit_approval` with `{"dry_run_id": "..."}`).
        3. Verify `treasury_ops` appears under `approvals` in `GET http://127.0.0.1:18871/api/status`, and write `/session/work/signoff.json` with `{"operator": "treasury_ops", "committed": true}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket RSK-702: Risk Exposure Batch Compliance Dry-Run & Signoff

        Complete Risk Batch `RB-2026-Q4` on the FinOps Compliance Workstation Portal (`http://127.0.0.1:18871/`, open in Chromium):
        1. Sign in as `risk_officer` (password `R1sk#89`) via Chromium or `POST http://127.0.0.1:18871/api/login`.
        2. Start the mandatory 18-second server compliance dry-run (`POST /api/start_dry_run` with `{"batch_id": "RB-2026-Q4", "computed_checksum": "SHA-RB-442"}`), wait for the 18-second verification window to complete, and commit the approval (`POST /api/commit_approval` with `{"dry_run_id": "..."}`).
        3. Verify `risk_officer` appears under `approvals` in `GET http://127.0.0.1:18871/api/status`, and write `/session/work/signoff.json` with `{"operator": "risk_officer", "committed": true}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar08(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    svg_init = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="256" viewBox="0 0 512 256">
  <defs><style id="theme_css">.glyph { stroke: #1E293B; fill: none; }</style></defs>
  <rect id="bg" x="0" y="0" width="512" height="256" fill="#F8FAFC"/>
  <g id="nav_group">
    <circle id="nav_home" class="glyph" cx="64" cy="64" r="24" stroke-width="1.0"/>
    <circle id="nav_search" class="glyph" cx="160" cy="64" r="24" stroke-width="1.0"/>
  </g>
  <g id="alert_group"/>
</svg>
'''
    (workspace / "icons_sprite.svg").write_text(svg_init, encoding="utf-8")
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket UI-801: Nav Glyph Stroke Normalization & Design-System Portal Release

        Update `/workspace/icons_sprite.svg` and publish via `http://127.0.0.1:18872/`:
        1. In `/workspace/icons_sprite.svg`, set `stroke-width="2.5"` on `nav_home` and `nav_search`, add `<rect id="nav_menu" class="glyph" x="236" y="40" width="48" height="48" stroke-width="2.5"/>` inside `nav_group`, save `/workspace/icons_sprite.svg`, and export `/workspace/exports/nav_sheet_300dpi.png` (`--export-dpi=300`) via Inkscape.
        2. Stage the updated SVG in the Design System Console (`POST http://127.0.0.1:18872/api/stage_svg` with `{"ticket_id": "UI-801", "svg_content": <full SVG text>}`), wait `14.5` seconds for the visual check, and publish release `REL-NAV` (`POST /api/publish_staged` with `{"release_tag": "REL-NAV"}`).
        3. Write `/session/work/signoff.json` with `{"release_tag": "REL-NAV", "svg_sha256": "..."}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket UI-802: Theme Stroke Palette, Alert Glyphs & Design-System Portal Release

        Update `/workspace/icons_sprite.svg` and publish via `http://127.0.0.1:18872/`:
        1. First, without modifying `/workspace/icons_sprite.svg`, render 8 high-DPI hinting checks (`150, 300, 450, 600, 750, 900, 1050, 1200` DPI) of `/workspace/icons_sprite.svg` to `/session/work/hint_{dpi}.png` via Inkscape.
        2. After all 8 hinting PNGs finish, update `#theme_css` in `/workspace/icons_sprite.svg` from `#1E293B` to `#0EA5E9`, add `<rect id="alert_banner" x="20" y="135" width="472" height="100" rx="8" fill="#0EA5E9"/>`, `<polygon id="alert_warn" class="glyph" points="64,160 40,210 88,210" stroke-width="2.5"/>`, and `<circle id="alert_ok" class="glyph" cx="160" cy="185" r="24" stroke-width="2.5"/>` inside `alert_group`, and save `/workspace/icons_sprite.svg`.
        3. Stage the updated SVG (`POST http://127.0.0.1:18872/api/stage_svg` with `{"ticket_id": "UI-802", "svg_content": <full SVG text>}`), wait `14.5` seconds, publish release `REL-ALERT` (`POST /api/publish_staged` with `{"release_tag": "REL-ALERT"}`), and write `/session/work/signoff.json` with `{"release_tag": "REL-ALERT"}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar09(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    bl_code = textwrap.dedent(f'''
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 20
        scene.cycles.use_denoising = False
        scene.render.resolution_x = 480
        scene.render.resolution_y = 320
        bpy.ops.mesh.primitive_cylinder_add(radius=2.0, depth=5.0, location=(0, 0, 2.5))
        valve = bpy.context.active_object
        valve.name = "ValveBody"
        mat = bpy.data.materials.new(name="AlloyMat")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.76, 0.78, 1.0)
        valve.data.materials.append(mat)
        ldata = bpy.data.lights.new(name="SunL", type="AREA")
        ldata.energy = 500.0
        lobj = bpy.data.objects.new(name="SunL", object_data=ldata)
        lobj.location = (4.0, -4.0, 6.0)
        scene.collection.objects.link(lobj)
        cdata = bpy.data.cameras.new(name="Cam")
        cobj = bpy.data.objects.new(name="Cam", object_data=cdata)
        cobj.location = (0.0, -10.0, 3.5)
        cobj.rotation_euler = (1.35, 0.0, 0.0)
        scene.collection.objects.link(cobj)
        scene.camera = cobj
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'valve_assembly.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_f:
        tmp_f.write(bl_code)
        tmp_path = Path(tmp_f.name)
    try:
        run_checked(["blender", "-b", "--python", str(tmp_path)])
    finally:
        tmp_path.unlink(missing_ok=True)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket CPQ-901: Valve Mesh Volume Beauty Render & CPQ Quote Lock

        Generate and lock customer quote `QT-904` from `/workspace/valve_assembly.blend` and `http://127.0.0.1:18873/`:
        1. In Blender (`bmesh`), compute the exact closed mesh volume (`cm^3`, where `1 Blender unit = 1 cm`, rounded to 2 decimals) of `ValveBody` in `/workspace/valve_assembly.blend`, and render `/workspace/exports/quote_render.png` using the existing scene camera & resolution (`480x320`, `CYCLES`, `samples = 20`, `use_denoising = False`, without moving camera or lights).
        2. Lock Quote `QT-904` via `POST http://127.0.0.1:18873/api/lock_quote` with `{"quote_id": "QT-904", "volume_cm3": <float>, "render_sha256": "<sha256 of quote_render.png>"}` (the portal multiplies `volume_cm3` by its active alloy rate).
        3. Write `/session/work/signoff.json` with the returned quote object.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket MET-902: 6-Pressure Cycles Audit, Heavy-Wall ValveBody & Inconel-625 Rate Update

        Upgrade `/workspace/valve_assembly.blend` and update alloy pricing on `http://127.0.0.1:18873/`:
        1. First, run 6 Cycles test renders (`samples=28`, `640x480`) across candidate scale factors `[1.05, 1.10, 1.15, 1.20, 1.25, 1.30]` into `/session/work/valve_scale_{idx}.png` without modifying `/workspace/valve_assembly.blend`.
        2. After all 6 renders finish, uniformly scale `ValveBody` by `(1.25, 1.25, 1.20)` and apply scale (`transform_apply`), recolor `AlloyMat` to `[0.28, 0.35, 0.45, 1.0]`, and save `/workspace/valve_assembly.blend`.
        3. Post Alloy Change Notice `ACN-625` to `POST http://127.0.0.1:18873/api/update_alloy` with `{"acn_id": "ACN-625", "alloy_code": "INCONEL-625", "rate_usd_per_cm3": 4.80}`, and write `/session/work/signoff.json` with `{"alloy_code": "INCONEL-625"}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_ar10(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    repo = workspace / "service_repo"
    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    (repo / "app/__init__.py").write_text("", encoding="utf-8")
    (repo / "app/registry.py").write_text(
        textwrap.dedent('''
        ENABLED_MODULES = ["core"]
        ROUNDING_EPSILON = 0.01

        def summary() -> dict:
            return {"modules": list(ENABLED_MODULES), "epsilon": ROUNDING_EPSILON}
        ''').strip() + "\n",
        encoding="utf-8",
    )
    run_checked(["git", "init", "-b", "main"], cwd=repo)
    run_checked(["git", "config", "user.email", "eng@studio.local"], cwd=repo)
    run_checked(["git", "config", "user.name", "Studio Eng"], cwd=repo)
    run_checked(["git", "add", "."], cwd=repo)
    run_checked(["git", "commit", "-m", "initial main"], cwd=repo)

    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket DEV-1001: Feature Branch `feat/telemetry-dag` & Staging Release Gate

        In `/workspace/service_repo`:
        1. Create and switch to git branch `feat/telemetry-dag` (`git checkout -b feat/telemetry-dag`), wait/work on that branch while generating `/workspace/service_repo/docs/pipeline.dot` (`digraph Pipeline { ingest -> transform -> publish; }`) and rendering BOTH `/workspace/service_repo/docs/pipeline.svg` and `/workspace/service_repo/docs/pipeline.png` (`-Gdpi=300`) via `dot`.
        2. Add `"telemetry_dag"` to `ENABLED_MODULES` in `app/registry.py` (preserving any existing modules and `ROUNDING_EPSILON`), commit on `feat/telemetry-dag`, sleep `12` seconds to simulate staging smoke soak while on `feat/telemetry-dag`, then checkout `main` and merge `feat/telemetry-dag` (`--no-ff`).
        3. Deploy the resulting `main` HEAD SHA via `POST http://127.0.0.1:18874/api/deploy` with `{"ticket_id": "DEV-1001", "commit_sha": "<HEAD sha>", "branch": "main"}`, and write `/session/work/signoff.json` with `{"head_sha": "..."}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket DEV-1002: Hotfix Branch `fix/ledger-rounding`, SQLite Audit & Staging Release Gate

        In `/workspace/service_repo`:
        1. Create and switch to git branch `fix/ledger-rounding` (`git checkout -b fix/ledger-rounding`), build `/workspace/service_repo/docs/reconciliation.sqlite3` containing table `reconciled_batches(batch_id INT PRIMARY KEY, delta REAL)` populated with 500 deterministic rows (`delta = round((batch_id * 0.00037) % 0.005, 6)`), sleep `12` seconds on `fix/ledger-rounding` during audit verification.
        2. Update `ROUNDING_EPSILON = 0.0005` and append `"ledger_guard"` to `ENABLED_MODULES` in `app/registry.py` (preserving existing items), commit on `fix/ledger-rounding`, checkout `main`, and merge `fix/ledger-rounding` (`--no-ff`).
        3. Deploy `main` HEAD SHA via `POST http://127.0.0.1:18874/api/deploy` with `{"ticket_id": "DEV-1002", "commit_sha": "<HEAD sha>", "branch": "main"}`, and write `/session/work/signoff.json` with `{"head_sha": "..."}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_task_bundle(task_id: str, workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    clear_directory_contents(workspace)
    clear_directory_contents(ticket_a)
    clear_directory_contents(ticket_b)
    dispatch = {
        "AR-01": build_ar01,
        "AR-02": build_ar02,
        "AR-03": build_ar03,
        "AR-04": build_ar04,
        "AR-05": build_ar05,
        "AR-06": build_ar06,
        "AR-07": build_ar07,
        "AR-08": build_ar08,
        "AR-09": build_ar09,
        "AR-10": build_ar10,
    }
    if task_id not in dispatch:
        raise KeyError(f"Unknown task_id: {task_id}")
    dispatch[task_id](workspace, ticket_a, ticket_b)
