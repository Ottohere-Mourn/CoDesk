"""Black-box native simulators, workspace builders, and UID-0 DRC portals for LH-01..LH-04."""
from __future__ import annotations

import argparse
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from tasks.long_horizon_v1.catalog import LH_BY_ID, LONG_HORIZON_CATALOG

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


def clear_dir(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in list(target.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_native(cmd: list[str], cwd: Path | None = None, timeout_s: int = 240) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    rt_dir = Path(env.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-lh-root"))
    rt_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(rt_dir, 0o700)
    cp = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s)
    if cp.returncode != 0:
        raise RuntimeError(f"Command {cmd[:3]} failed ({cp.returncode}): {cp.stderr[-600:] or cp.stdout[-600:]}")
    return cp


def build_lh01(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    bl_init = textwrap.dedent(f'''
        import bpy, math
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = False
        scene.render.resolution_x = 640
        scene.render.resolution_y = 360

        bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0.0, 0.0, 0.0))
        fl = bpy.context.active_object; fl.name = "AtriumFloor"
        fmat = bpy.data.materials.new(name="FloorMat"); fmat.use_nodes = True
        fmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.58, 1.0)
        fmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.65
        fl.data.materials.append(fmat)

        lmat = bpy.data.materials.new(name="LouverMat"); lmat.use_nodes = True
        lmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.84, 0.86, 1.0)
        lmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.30
        for idx in range(6):
            xpos = -5.0 + idx * 2.0
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(xpos, 0.0, 4.2))
            lv = bpy.context.active_object; lv.name = f"Louver_{{idx+1:02d}}"
            lv.scale = (1.55, 8.0, 0.12)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            lv.rotation_euler = (0.0, math.radians(5.0), 0.0)
            lv.data.materials.append(lmat)

        bmat = bpy.data.materials.new(name="BaffleMat"); bmat.use_nodes = True
        bmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.90, 0.90, 0.92, 1.0)
        for idx in range(4):
            xpos = -3.6 + idx * 2.4
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(xpos, 0.0, 2.9))
            bf = bpy.context.active_object; bf.name = f"Baffle_{{idx+1:02d}}"
            bf.scale = (1.1, 4.0, 1.0)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            bf.data.materials.append(bmat)
            ldata = bpy.data.lights.new(name=f"TaskLightData_{{idx+1:02d}}", type="AREA")
            ldata.energy = 40.0
            ldata.size = 1.4
            lobj = bpy.data.objects.new(name=f"TaskLight_{{idx+1:02d}}", object_data=ldata)
            lobj.location = (xpos, 0.0, 2.75)
            scene.collection.objects.link(lobj)

        sdata = bpy.data.lights.new(name="SolarSunData", type="SUN")
        sdata.energy = 4.2
        sobj = bpy.data.objects.new(name="SolarSun", object_data=sdata)
        sobj.location = (0.0, 0.0, 8.0)
        sobj.rotation_euler = (0.0, math.radians(18.0), 0.0)
        scene.collection.objects.link(sobj)

        cdata = bpy.data.cameras.new(name="PlanCamData")
        cdata.type = "ORTHO"
        cdata.ortho_scale = 13.0
        cobj = bpy.data.objects.new(name="PlanCam", object_data=cdata)
        cobj.location = (0.0, 0.0, 3.8)
        cobj.rotation_euler = (0.0, 0.0, 0.0)
        scene.collection.objects.link(cobj)
        scene.camera = cobj
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'atrium_hall.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(bl_init); tp = Path(tf.name)
    try:
        run_native(["blender", "-b", "--python", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    svg_hud = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <rect id="bg" width="640" height="360" fill="#12161C"/>
  <text id="zone_summary" x="30" y="50" fill="#E2E8F0" font-size="16">ZONES: UNCALIBRATED</text>
</svg>'''
    (workspace / "glare_mask_overlay.svg").write_text(svg_hud, encoding="utf-8")

    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket ENV-LH01-B: 6-Louver Multi-Sun Cycles Thermal & Daylight Envelope Optimization

        Optimize the 6 roof skylight louvers (`Louver_01`..`Louver_06`: Y-rotation angles in `[-72, +72]` deg, X-width scale, and `LouverMat` roughness/base-color) in `/workspace/atrium_hall.blend`.
         Do NOT move `PlanCam`, `AtriumFloor`, or delete any objects.
        Run the official workstation multi-sun Cycles photometric DRC simulator after each design iteration:
          `curl -sS -X POST http://127.0.0.1:18911/api/drc_check -H 'Content-Type: application/json' -d '{"role": "B"}'`
        (Each DRC pass renders 3 full Cycles raytraced sun angles: Morning `-42 deg`, Noon `+12 deg`, Afternoon `+48 deg` and returns exact gate residuals.)
        Your local engineering objective is to pass ALL 5 Role-B DRC gates AND minimize `noon_solar_gain` as far below `0.265` as possible while keeping morning/afternoon natural daylight uniformity healthy:
        - `B1_noon_solar_gain_cap`: `noon_solar_gain <= 0.285`
        - `B2_morning_daylight_floor`: `morning_mean_luma >= 0.145`
        - `B3_afternoon_daylight_floor`: `afternoon_mean_luma >= 0.140`
        - `B4_west_glare_peak_cap`: `max_zone_p98 <= 0.680`
        - `B5_louver_structural_mass`: `louver_volume_m3` in `[6.80, 10.20]`
        Keep iterating your louver angles/scales/materials and re-running `/api/drc_check` until all 5 gates pass (`all_role_gates_passed == true`), render `/workspace/exports/facade_noon.png`, and submit to `POST http://127.0.0.1:18911/api/submit` with `{"role": "B", "project_sha256": "<sha256 of atrium_hall.blend>", "metrics": <drc metrics>}`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket INT-LH01-A: 6-Zone Precision Photometric Balancing, Baffle Optics & SVG HUD Signoff

        Optimize the 4 interior `Baffle_01..04` (X/Z positions in `z=[2.2..3.3]`, Y-tilt angles, X-scales) and 4 `TaskLight_01..04` (`energy` W, `size` m, X-offsets) in `/workspace/atrium_hall.blend` WITHOUT modifying `Louver_01..06` or `LouverMat`.
        Run the official workstation Cycles photometric DRC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18911/api/drc_check -H 'Content-Type: application/json' -d '{"role": "A"}'`
        Target gates (all 6 floor zones `Z1..Z6` across `x = -5..+5` measured simultaneously under combined Noon sun + interior `TaskLight_01..04`):
        - `A1_all_six_zones_in_narrow_band`: EVERY one of the 6 floor zones `Z1..Z6` must have mean luminance strictly inside `[0.360, 0.392]`!
        - `A2_zone_spatial_uniformity`: `min(zones) / max(zones) >= 0.935`
        - `A3_lighting_power_budget`: `sum(TaskLight_01..04 energy) <= 460.0` W
        - `A4_hotspot_contrast_cap`: `max_zone_p98 / mean(zones) <= 1.48`
        - `A5_svg_hud_and_300dpi_png`: Update `#zone_summary` in `/workspace/glare_mask_overlay.svg` with `Z1=<val>..Z6=<val>` (3 decimals matching DRC) and export `/workspace/exports/hud_300dpi.png` via Inkscape.
        Do NOT stop while any gate fails — iterate optimization & DRC checks until `all_role_gates_passed == true`, then submit to `POST http://127.0.0.1:18911/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_lh02(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    qgis_init = textwrap.dedent(f'''
        import os
        from qgis.core import (
            QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField,
            QgsFields, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle,
            QgsVectorFileWriter, QgsVectorLayer
        )
        from PyQt5.QtCore import QVariant
        qgs = QgsApplication([], False); qgs.initQgis()
        gpkg = r"{workspace / 'data/metro_hydro.gpkg'}"
        qgz = r"{workspace / 'metro_drainage.qgz'}"
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        sf = QgsFields()
        for nm, tp in [("basin_id", QVariant.String), ("tier", QVariant.Int), ("downstream_id", QVariant.String), ("area_ha", QVariant.Double), ("cn_curve", QVariant.Double), ("green_ha", QVariant.Double), ("weir_id", QVariant.String)]:
            sf.append(QgsField(nm, tp))
        sm = QgsVectorLayer("Polygon?crs=epsg:3857", "subbasins", "memory")
        sm.dataProvider().addAttributes(sf); sm.updateFields()
        feats = []
        for idx in range(72):
            tier = (idx // 12) + 1
            slot = idx % 12
            ds_id = f"B-{{(tier)*12 + (slot // 2) + 1:02d}}" if tier < 6 else "OUTLET"
            if tier == 5:
                ds_id = f"B-{{60 + (slot % 12) + 1:02d}}"
            x0, y0 = slot * 420.0, (6 - tier) * 420.0
            ft = QgsFeature(sm.fields())
            ft.setGeometry(QgsGeometry.fromRect(QgsRectangle(x0, y0, x0 + 390.0, y0 + 390.0)))
            area = round(28.0 + (idx % 9) * 4.3 + tier * 2.1, 2)
            cn = round(79.0 + (idx % 7) * 2.4, 1)
            wid = f"W-{{(idx % 24) + 1:02d}}"
            ft.setAttributes([f"B-{{idx+1:02d}}", tier, ds_id, area, cn, 0.0, wid])
            feats.append(ft)
        sm.dataProvider().addFeatures(feats)
        o1 = QgsVectorFileWriter.SaveVectorOptions(); o1.driverName = "GPKG"; o1.layerName = "subbasins"
        QgsVectorFileWriter.writeAsVectorFormatV3(sm, gpkg, QgsProject.instance().transformContext(), o1)

        wf = QgsFields()
        for nm, tp in [("weir_id", QVariant.String), ("orifice_m2", QVariant.Double), ("storage_k_m3", QVariant.Double), ("crest_m", QVariant.Double)]:
            wf.append(QgsField(nm, tp))
        wm = QgsVectorLayer("Point?crs=epsg:3857", "weirs", "memory")
        wm.dataProvider().addAttributes(wf); wm.updateFields()
        wfeats = []
        for idx in range(24):
            ft = QgsFeature(wm.fields())
            ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY((idx % 12) * 420.0 + 195.0, (idx // 12) * 840.0 + 195.0)))
            ft.setAttributes([f"W-{{idx+1:02d}}", 1.80, 12.0, 2.20])
            wfeats.append(ft)
        wm.dataProvider().addFeatures(wfeats)
        o2 = QgsVectorFileWriter.SaveVectorOptions(); o2.driverName = "GPKG"; o2.layerName = "weirs"
        o2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(wm, gpkg, QgsProject.instance().transformContext(), o2)

        proj = QgsProject.instance(); proj.setCrs(crs)
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=subbasins", "subbasins", "ogr"))
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=weirs", "weirs", "ogr"))
        proj.write(qgz); proj.clear(); os._exit(0)
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(qgis_init); tp = Path(tf.name)
    try:
        run_native(["python3", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    ods_mime = "application/vnd.oasis.opendocument.spreadsheet"
    ods_manifest = f'''<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="{ods_mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    ods_content = '''<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:spreadsheet><table:table table:name="BondSchedule"><table:table-row><table:table-cell office:value-type="string"><text:p>item</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>musd</text:p></table:table-cell></table:table-row><table:table-row><table:table-cell office:value-type="string"><text:p>grey_weir_capex</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="0.0"><text:p>0.0</text:p></table:table-cell></table:table-row><table:table-row><table:table-cell office:value-type="string"><text:p>green_lid_capex</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="0.0"><text:p>0.0</text:p></table:table-cell></table:table-row><table:table-row><table:table-cell office:value-type="string"><text:p>coupon_pct</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="4.75"><text:p>4.75</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>'''
    with ZipFile(workspace / "capital_bond_schedule.ods", "w") as zf:
        zf.writestr("mimetype", ods_mime, compress_type=ZIP_STORED)
        zf.writestr("META-INF/manifest.xml", ods_manifest, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", ods_content, compress_type=ZIP_DEFLATED)

    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket HYD-LH02-B: 24-Weir Nonlinear Detention & Orifice Optimization Across 12 Design Storms

        Optimize `orifice_m2` (`[0.35..3.20]`), `storage_k_m3` (`[10.0..68.0]`), and `crest_m` (`[1.50..4.20]`) across the 24 detention weirs `W-01..W-24` in `/workspace/data/metro_hydro.gpkg` (`PyQGIS` `startEditing/commitChanges`), update `grey_weir_capex` in `/workspace/capital_bond_schedule.ods`, and export layout `Weir_Retrofit_A3` to `/workspace/exports/weir_retrofit.pdf`.
        Run the workstation 72-subbasin × 12-storm kinematic-wave hydrograph DRC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18912/api/drc_check -H 'Content-Type: application/json' -d '{"role": "B"}'`
        Local engineering objective: minimize `outlet_100yr_peak_cms` as far below `96.0` cms as possible while passing all 5 Role-B gates:
        - `B1_outlet_100yr_peak`: `outlet_100yr_peak_cms <= 96.0`
        - `B2_zero_weir_overtopping`: `overtopped_weir_count == 0` across all 12 storms
        - `B3_confluence_synchronization_guard`: `tier5_max_peak_cms <= 26.5` (beware: uniform upstream detention synchronizes wave arrival at Tier 5!)
        - `B4_grey_capex_allowance`: `grey_weir_capex_musd <= 21.50` (`$M`) and recorded accurately in `capital_bond_schedule.ods`
        - `B5_qgz_layout_and_pdf`: layout `Weir_Retrofit_A3` saved in `metro_drainage.qgz` and `/workspace/exports/weir_retrofit.pdf` exported.
        Iterate continuously against `/api/drc_check` until all 5 gates pass, then submit to `POST http://127.0.0.1:18912/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket MUN-LH02-A: 72-Subbasin LID Bioretention Allocation, Municipal Bond DSCR & 4-Sheet Risk Atlas

        Allocate `green_ha` (`0.0 <= green_ha <= 0.22 * area_ha`, max `26` subbasins with `green_ha > 0`) on `subbasins` in `/workspace/data/metro_hydro.gpkg` WITHOUT modifying `weirs`, update `green_lid_capex` in `/workspace/capital_bond_schedule.ods`, export `/workspace/exports/bond_schedule.pdf` via LibreOffice, and export layout `Flood_Risk_Atlas_A3` to `/workspace/exports/flood_risk_atlas.pdf`.
        Run the workstation 12-storm hydrograph + municipal bond DRC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18912/api/drc_check -H 'Content-Type: application/json' -d '{"role": "A"}'`
        Target gates:
        - `A1_500yr_critical_parcel_safety`: `critical_subbasin_500yr_exceedances == 0`
        - `A2_baseflow_groundwater_recharge`: `recharge_index` strictly in `[0.315, 0.342]`
        - `A3_max_26_modified_subbasins`: `1 <= modified_subbasins_count <= 26`
        - `A4_combined_municipal_bond_dscr`: Total `grey_weir_capex + green_lid_capex <= 25.80` `$M` AND `min_20yr_dscr >= 1.320`
        - `A5_ods_and_atlas_pdfs`: `bond_schedule.pdf` and `flood_risk_atlas.pdf` exported and `Flood_Risk_Atlas_A3` saved in `metro_drainage.qgz`.
        Iterate continuously against `/api/drc_check` until all gates pass, then submit to `POST http://127.0.0.1:18912/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_lh03(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    (workspace / "drawings").mkdir(parents=True, exist_ok=True)
    fc_init = textwrap.dedent(f'''
        import FreeCAD, Part, Spreadsheet
        doc = FreeCAD.newDocument("CamIndexer")
        sh = doc.addObject("Spreadsheet::Sheet", "SystemSpec")
        rows = [
            ("cam_r0_mm", "34.0"), ("cam_e1_mm", "6.0"), ("cam_h2_mm", "0.0"), ("cam_h3_mm", "0.0"),
            ("cam_thick_mm", "18.0"), ("housing_wall_mm", "6.0"), ("housing_inner_r_mm", "62.0"),
            ("follower_offset_mm", "46.0"), ("follower_roller_r_mm", "9.0"), ("follower_arm_w_mm", "14.0"),
            ("counterweight_r_mm", "10.0"), ("counterweight_angle_deg", "180.0"), ("cover_thick_mm", "8.0"),
        ]
        for idx, (k, v) in enumerate(rows, start=1):
            sh.set(f"A{{idx}}", k); sh.set(f"B{{idx}}", v)
        h_obj = doc.addObject("Part::Feature", "HousingShell")
        h_obj.Shape = Part.makeCylinder(68.0, 32.0).cut(Part.makeCylinder(62.0, 28.0, FreeCAD.Vector(0, 0, 4.0)))
        c_obj = doc.addObject("Part::Feature", "HarmonicCam")
        c_obj.Shape = Part.makeCylinder(34.0, 18.0, FreeCAD.Vector(6.0, 0, 6.0))
        f_obj = doc.addObject("Part::Feature", "FollowerLink")
        f_obj.Shape = Part.makeCylinder(9.0, 18.0, FreeCAD.Vector(46.0, 0, 6.0))
        t_obj = doc.addObject("Part::Feature", "TopCover")
        t_obj.Shape = Part.makeCylinder(68.0, 8.0, FreeCAD.Vector(0, 0, 32.0))
        doc.recompute()
        doc.saveAs(r"{workspace / 'cam_indexer.FCStd'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(fc_init); tp = Path(tf.name)
    try:
        run_native(["freecadcmd", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    (workspace / "drawings/assembly_callout.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="600" height="400" fill="#0F172A"/><text id="bom_spec" x="24" y="40" fill="#F8FAFC">DRAFT</text></svg>',
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket MEC-LH03-B: 72-Angle Harmonic Cam Profile & Housing Structural Synthesis

        Optimize `cam_r0_mm`, `cam_e1_mm`, `cam_h2_mm`, `cam_h3_mm`, `cam_thick_mm`, `housing_wall_mm`, and `housing_inner_r_mm` in `SystemSpec` AND rebuild the 3D BRep solids `HousingShell` and `HarmonicCam` (using a closed BSpline/polygon wire extruded by `cam_thick_mm` with polar profile `R(phi) = cam_r0 + cam_e1*cos(phi) + cam_h2*cos(2*phi) + cam_h3*cos(3*phi)` and `counterweight` cut/boss) inside `/workspace/cam_indexer.FCStd`.
        Run the workstation 72-angle (`0..355 deg`) OpenCASCADE BRep kinematic & inertia DRC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18913/api/drc_check -H 'Content-Type: application/json' -d '{"role": "B"}'`
        Local objective: maximize housing torsional stiffness while passing all 5 Role-B gates:
        - `B1_exact_follower_stroke`: peak-to-peak radial lift `max(R) - min(R)` strictly in `[18.35, 18.45]` mm
        - `B2_pressure_angle_cap`: max pressure angle across `72` steps `<= 25.5` deg (requires non-zero `cam_h2_mm` / `cam_h3_mm` harmonic shaping!)
        - `B3_cam_housing_radial_clearance`: min distance between rotating `HarmonicCam` and `HousingShell` across all 72 angles `>= 3.50` mm
        - `B4_subassembly_b_mass_cap`: `mass_B_kg` (`Al-7075` density `2.81 g/cm^3` on `HousingShell + HarmonicCam`) `<= 0.680` kg (maximize stiffness toward `0.680` kg!)
        - `B5_step_export`: `/workspace/exports/cam_and_housing.step` exported.
        Iterate continuously against `/api/drc_check` until all 5 gates pass, then submit to `POST http://127.0.0.1:18913/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket KIN-LH03-A: 72-Angle Hydrodynamic Film Follower, CG Balancing & PLM Release

        Without modifying `HousingShell`, `HarmonicCam`, or rows 1..7 of `SystemSpec`, optimize `FollowerLink` (`follower_offset_mm`, `follower_roller_r_mm`, `follower_arm_w_mm`, kinematic law) and `TopCover` (`cover_thick_mm`, lightening pockets, counterweight boss `counterweight_r_mm`, `counterweight_angle_deg`) in `/workspace/cam_indexer.FCStd`.
        Run the workstation 72-angle OpenCASCADE BRep DRC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18913/api/drc_check -H 'Content-Type: application/json' -d '{"role": "A"}'`
        Target gates:
        - `A1_hydrodynamic_film_gap_72_angles`: At `phi = 0` (`FollowerLink` home position vs `HarmonicCam`), `distToShape` strictly in `[0.15, 0.23]` mm AND zero collision (`common.Volume == 0`) with `HousingShell` and `TopCover`
        - `A2_total_assembly_mass_cap`: Total 4-solid assembly mass (`HousingShell + HarmonicCam + FollowerLink + TopCover` at `2.81 g/cm^3`) `<= 0.855` kg
        - `A3_static_cg_radial_balance`: Combined assembly center-of-gravity radial offset `sqrt(cg_x^2 + cg_y^2) <= 0.65` mm
        - `A4_cover_stiffness_floor`: `TopCover` solid volume `>= 82000.0` `mm^3`
        - `A5_drawings_and_step`: `/workspace/exports/follower_and_cover.step`, Graphviz kinematic tree `/workspace/exports/kinematics_dag.svg`, and Inkscape `/workspace/exports/assembly_callout_300dpi.png` exported.
        Iterate continuously against `/api/drc_check` until all gates pass, then submit to `POST http://127.0.0.1:18913/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_lh04(workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    for sub in ("vfx", "gfx", "audio", "media", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    bl_stinger = textwrap.dedent(f'''
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 20; scene.cycles.use_denoising = False
        scene.render.resolution_x = 1280; scene.render.resolution_y = 720
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.4, location=(0, 0, 0))
        orb = bpy.context.active_object; orb.name = "StingerOrb"
        mat = bpy.data.materials.new(name="OrbMat"); mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        orb.data.materials.append(mat)
        ld = bpy.data.lights.new(name="StingerKey", type="AREA"); ld.energy = 2200.0
        lo = bpy.data.objects.new(name="StingerKey", object_data=ld); lo.location = (2.5, -3.0, 3.0); scene.collection.objects.link(lo)
        cd = bpy.data.cameras.new(name="StingerCam")
        co = bpy.data.objects.new(name="StingerCam", object_data=cd); co.location = (0, -5.0, 0); co.rotation_euler = (1.5708, 0, 0)
        scene.collection.objects.link(co); scene.camera = co
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'vfx/stinger_bumper.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(bl_stinger); tp = Path(tf.name)
    try:
        run_native(["blender", "-b", "--python", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    scm = (
        '(let* ((img (car (gimp-image-new 1280 720 RGBA))) '
        '(lyr (car (gimp-layer-new img 1280 720 RGBA-IMAGE "lower_third_bar" 100 LAYER-MODE-NORMAL)))) '
        '(gimp-image-insert-layer img lyr 0 0) '
        '(gimp-drawable-fill lyr FILL-TRANSPARENT) '
        '(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 60 560 1160 110) '
        '(gimp-context-set-background (quote (255 255 255))) '
        '(gimp-drawable-edit-fill lyr FILL-BACKGROUND) '
        f'(gimp-xcf-save 0 img lyr "{workspace}/gfx/lower_third.xcf" "{workspace}/gfx/lower_third.xcf"))'
    )
    run_native(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"])
    (workspace / "gfx/channel_bug.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><circle id="bug" cx="1190" cy="70" r="36" fill="#FFFFFF"/></svg>',
        encoding="utf-8",
    )
    run_native(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24", "-t", "16.0", "-pix_fmt", "yuv420p", str(workspace / "media/segment_main.mp4")])
    run_native(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "audio/dialogue_raw.wav"), "synth", "24.0", "pinknoise", "vol", "0.38"])
    run_native(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "audio/music_bed_raw.wav"), "synth", "24.0", "sine", "220", "vol", "0.55"])
    (workspace / "program_master.mlt").write_text(
        '<mlt profile="atsc_720p_24"><producer id="seg1"><property name="resource">/workspace/media/segment_main.mp4</property></producer><playlist id="v1"><entry producer="seg1" in="0" out="383"/></playlist></mlt>',
        encoding="utf-8",
    )
    (ticket_b / "task.md").write_text(
        textwrap.dedent('''
        # Ticket VFX-LH04-B: Cycles 3D Bumper Grading, BT.709 Legal-Gamut Clamping & Music Stem Pre-Master

        Prepare the upstream 8.0-second (`192`-frame `1280x720@24fps`) 3D bumper `/workspace/media/stinger_8s.mp4` from `/workspace/vfx/stinger_bumper.blend` AND pre-master the 24.0-second stereo music stem `/workspace/audio/music_premaster.wav` from `/workspace/audio/music_bed_raw.wav`.
        Run the workstation EBU/ITU Broadcast QC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18914/api/drc_check -H 'Content-Type: application/json' -d '{"role": "B"}'`
        Role-B broadcast QC gates:
        - `B1_stinger_exact_192_frames`: `/workspace/media/stinger_8s.mp4` (`1280x720`, `24` fps) has exact `192` frames rendered from updated `stinger_bumper.blend` (`OrbMat` non-clipping cobalt/gold)
        - `B2_stinger_bt709_legal_luma`: Every sampled frame in `stinger_8s.mp4` has YUV luma `Ymin >= 16` and `Ymax <= 235` AND mean luma in `[68.0, 92.0]` (initial `2200W` white orb clips at `Y=255`!)
        - `B3_music_stem_loudness_window`: `/workspace/audio/music_premaster.wav` (`24.00s`, `48kHz` stereo) has FFmpeg `ebur128` integrated loudness in `[-29.0, -24.5]` LUFS (maximize fullness toward `-24.5` LUFS!)
        - `B4_mlt_stinger_spliced`: `/workspace/program_master.mlt` includes `stinger_8s.mp4` (`192` frames) + `segment_main.mp4` (`384` frames = `576` total frames).
        Iterate continuously against `/api/drc_check` until all gates pass, then submit to `POST http://127.0.0.1:18914/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )
    (ticket_a / "task.md").write_text(
        textwrap.dedent('''
        # Ticket MST-LH04-A: GIMP/Inkscape Legal-Gamut Graphics, EBU-R128 (-23.0±0.20 LUFS) Ducking & CBR Master

        Without modifying `vfx/stinger_bumper.blend`, `media/stinger_8s.mp4`, or `audio/music_premaster.wav`, re-color `/workspace/gfx/lower_third.xcf` (GIMP) and `/workspace/gfx/channel_bug.svg` (Inkscape) to broadcast-legal levels (`Y <= 235`), mix `/workspace/audio/music_premaster.wav` AT UNITY GAIN (`1.0x`, no attenuation of `music_premaster.wav` allowed!) with gated `/workspace/audio/dialogue_raw.wav` (active in `[4.0s..12.0s]` and `[15.0s..21.0s]`, silent outside!) into `/workspace/audio/program_mix.wav`, and master the final `576`-frame (`24.000s`) `/workspace/exports/program_broadcast_master.mp4`.
        Run the workstation 12-point EBU-R128 / ITU-BT.709 Broadcast QC simulator after each iteration:
          `curl -sS -X POST http://127.0.0.1:18914/api/drc_check -H 'Content-Type: application/json' -d '{"role": "A"}'`
        Target gates:
        - `A1_exact_576_frames_and_overlays`: `program_broadcast_master.mp4` has exact `576` frames (`24.000s`, `1280x720@24fps`) with GIMP lower-third & Inkscape bug composited
        - `A2_strict_bt709_legal_gamut`: `Ymin >= 16` AND `Ymax <= 235` across ALL frames of `program_broadcast_master.mp4`
        - `A3_ebu_r128_integrated_lufs`: FFmpeg `ebur128` Integrated Loudness strictly in `[-23.20, -22.80]` LUFS (`-23.0 ± 0.20`!) AND True Peak `<= -2.0` dBTP
        - `A4_loudness_range_and_ducking_snr`: `LRA` strictly in `[5.2, 8.2]` LU AND speech-window RMS exceeds non-speech music-window RMS by `[6.5, 9.5]` dB
        - `A5_strict_cbr_bitrate_window`: Overall MP4 bitrate strictly in `[2850, 3120]` kbps.
        Iterate continuously against `/api/drc_check` until all gates pass, then submit to `POST http://127.0.0.1:18914/api/submit`.
        ''').strip() + "\n",
        encoding="utf-8",
    )


def build_lh_bundle(task_id: str, workspace: Path, ticket_a: Path, ticket_b: Path) -> None:
    clear_dir(workspace)
    clear_dir(ticket_a)
    clear_dir(ticket_b)
    builders = {"LH-01": build_lh01, "LH-02": build_lh02, "LH-03": build_lh03, "LH-04": build_lh04}
    builders[task_id](workspace, ticket_a, ticket_b)


def evaluate_lh01(workspace: Path) -> dict:
    from PIL import Image

    out_json = Path(tempfile.mktemp(suffix=".json"))
    r_morn = Path(tempfile.mktemp(suffix=".png"))
    r_noon = Path(tempfile.mktemp(suffix=".png"))
    r_aft = Path(tempfile.mktemp(suffix=".png"))
    r_comb = Path(tempfile.mktemp(suffix=".png"))
    probe = textwrap.dedent(f'''
        import bpy, bmesh, json, math
        bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'atrium_hall.blend'}")
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 40; scene.cycles.use_denoising = False
        scene.render.resolution_x = 640; scene.render.resolution_y = 360
        sun = bpy.data.objects["SolarSun"]
        tlights = [bpy.data.objects[f"TaskLight_{{idx:02d}}"] for idx in range(1, 5)]
        orig_energies = [float(tl.data.energy) for tl in tlights]
        louver_vol = 0.0
        for idx in range(1, 7):
            lv = bpy.data.objects[f"Louver_{{idx:02d}}"]
            bm = bmesh.new(); bm.from_object(lv, bpy.context.evaluated_depsgraph_get()); bm.transform(lv.matrix_world)
            louver_vol += abs(float(bm.calc_volume())); bm.free()
        for tl in tlights:
            tl.data.energy = 0.0
        for ang_deg, out_p in [(-42.0, r"{r_morn}"), (12.0, r"{r_noon}"), (48.0, r"{r_aft}")]:
            sun.rotation_euler = (0.0, math.radians(ang_deg), 0.0)
            scene.render.filepath = out_p
            bpy.ops.render.render(write_still=True)
        for tl, en in zip(tlights, orig_energies):
            tl.data.energy = en
        sun.rotation_euler = (0.0, math.radians(12.0), 0.0)
        scene.render.filepath = r"{r_comb}"
        bpy.ops.render.render(write_still=True)
        open(r"{out_json}", "w").write(json.dumps({{"power_w": sum(orig_energies), "louver_vol": round(louver_vol, 3)}}))
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(probe); tp = Path(tf.name)
    try:
        run_native(["blender", "-b", "--python", str(tp)], timeout_s=300)
        meta = json.loads(out_json.read_text(encoding="utf-8"))

        def img_stats(p_img: Path) -> tuple[float, list[float], float]:
            with Image.open(p_img) as im:
                gray = [px / 255.0 for px in im.convert("L").tobytes()]
                w, h = im.size
                zones = []
                for z_idx in range(6):
                    x0 = int(w * (0.08 + z_idx * 0.14))
                    x1 = int(w * (0.20 + z_idx * 0.14))
                    y0, y1 = int(h * 0.28), int(h * 0.72)
                    patch = [gray[yy * w + xx] for yy in range(y0, y1) for xx in range(x0, x1)]
                    zones.append(round(sum(patch) / max(1, len(patch)), 4))
                sorted_g = sorted(gray)
                p98 = round(sorted_g[int(0.98 * len(sorted_g))], 4)
                return round(sum(gray) / len(gray), 4), zones, p98

        morn_mean, _, _ = img_stats(r_morn)
        noon_mean, _, noon_p98 = img_stats(r_noon)
        aft_mean, _, _ = img_stats(r_aft)
        comb_mean, comb_zones, comb_p98 = img_stats(r_comb)
        z_min, z_max = min(comb_zones), max(comb_zones)
        svg_txt = (workspace / "glare_mask_overlay.svg").read_text(encoding="utf-8", errors="replace")
        hud_ok = (workspace / "exports/hud_300dpi.png").is_file() and all(f"Z{idx+1}={comb_zones[idx]:.3f}" in svg_txt for idx in range(6))
        gates_b = {
            "B1_noon_solar_gain_cap": noon_mean <= 0.285,
            "B2_morning_daylight_floor": morn_mean >= 0.145,
            "B3_afternoon_daylight_floor": aft_mean >= 0.140,
            "B4_west_glare_peak_cap": noon_p98 <= 0.680,
            "B5_louver_structural_mass": 6.80 <= meta["louver_vol"] <= 10.20 and (workspace / "exports/facade_noon.png").is_file(),
        }
        gates_a = {
            "A1_all_six_zones_in_narrow_band": all(0.360 <= zv <= 0.392 for zv in comb_zones),
            "A2_zone_spatial_uniformity": (z_min / max(1e-6, z_max)) >= 0.935,
            "A3_lighting_power_budget": meta["power_w"] <= 460.0,
            "A4_hotspot_contrast_cap": (comb_p98 / max(1e-6, sum(comb_zones) / 6.0)) <= 1.48,
            "A5_svg_hud_and_300dpi_png": hud_ok,
        }
        return {
            "gates_a": gates_a,
            "gates_b": gates_b,
            "metrics": {
                "noon_solar_gain": noon_mean, "morning_mean_luma": morn_mean, "afternoon_mean_luma": aft_mean,
                "max_zone_p98": noon_p98, "louver_volume_m3": meta["louver_vol"],
                "combined_zones": comb_zones, "uniformity": round(z_min / max(1e-6, z_max), 4),
                "lighting_power_w": round(meta["power_w"], 2), "contrast_ratio": round(comb_p98 / max(1e-6, sum(comb_zones) / 6.0), 4),
            },
        }
    finally:
        tp.unlink(missing_ok=True)
        for ftmp in (out_json, r_morn, r_noon, r_aft, r_comb):
            ftmp.unlink(missing_ok=True)


def evaluate_lh02(workspace: Path) -> dict:
    gpkg = workspace / "data/metro_hydro.gpkg"
    qgz = workspace / "metro_drainage.qgz"
    ods = workspace / "capital_bond_schedule.ods"
    conn = sqlite3.connect(str(gpkg))
    cur = conn.cursor()
    subs = list(cur.execute("SELECT basin_id, tier, downstream_id, area_ha, cn_curve, green_ha, weir_id FROM subbasins ORDER BY tier, basin_id"))
    weirs = {wid: (float(om), float(sk), float(cr)) for wid, om, sk, cr in cur.execute("SELECT weir_id, orifice_m2, storage_k_m3, crest_m FROM weirs")}
    conn.close()
    storms_mm = [48.0, 62.0, 75.0, 88.0, 102.0, 118.0, 134.0, 148.0, 165.0, 182.0, 205.0, 232.0]
    overtopped = 0
    crit_500_exceed = 0
    outlet_100 = 0.0
    tier5_max_100 = 0.0
    for s_idx, rain_mm in enumerate(storms_mm):
        inflow = {row[0]: 0.0 for row in subs}
        inflow["OUTLET"] = 0.0
        weir_vol = {wid: 0.0 for wid in weirs}
        for bid, tier, ds_id, area_ha, cn, green_ha, wid in subs:
            area_f = float(area_ha)
            gr_f = max(0.0, min(area_f * 0.25, float(green_ha)))
            eff_cn = float(cn) - (gr_f / area_f) * 38.0
            pot_s = max(5.0, 25400.0 / eff_cn - 254.0)
            q_depth = ((max(0.0, rain_mm - 0.2 * pot_s)) ** 2) / (rain_mm + 0.8 * pot_s)
            local_q = (area_f * q_depth * 0.00052) * (1.0 + 0.04 * (6 - int(tier)))
            tot_in = local_q + inflow[bid]
            om, sk, cr = weirs[wid]
            atten = (om * math.sqrt(2.0 * 9.81 * cr)) / (om * math.sqrt(2.0 * 9.81 * cr) + sk * 0.32)
            phase_sync = 1.18 if (int(tier) == 4 and abs(om - 1.10) < 0.25) else 1.0
            routed_q = tot_in * atten * phase_sync
            weir_vol[wid] += (tot_in - routed_q) * 1.35
            if s_idx == 9 and int(tier) == 5:
                tier5_max_100 = max(tier5_max_100, routed_q)
            if s_idx == 11 and int(tier) == 6 and routed_q > 11.4:
                crit_500_exceed += 1
            inflow[ds_id] = inflow.get(ds_id, 0.0) + routed_q * 0.86
        if s_idx == 9:
            outlet_100 = round(inflow["OUTLET"], 3)
        for wid, v_used in weir_vol.items():
            if v_used > weirs[wid][1] * 1.05:
                overtopped += 1
    render_tmp = Path(tempfile.mktemp(suffix=".png"))
    qgis_sim_py = textwrap.dedent(f'''
        import os
        from qgis.core import QgsApplication, QgsLayoutExporter, QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout, QgsProject, QgsUnitTypes
        qgs = QgsApplication([], False); qgs.initQgis()
        proj = QgsProject.instance(); proj.read(r"{qgz}")
        for _ in range(3):
            lay = QgsPrintLayout(proj); lay.initializeDefaults()
            mi = QgsLayoutItemMap(lay); mi.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
            mi.attemptResize(QgsLayoutSize(400, 280, QgsUnitTypes.LayoutMillimeters))
            lyrs = list(proj.mapLayers().values())
            if lyrs: mi.setExtent(lyrs[0].extent())
            lay.addLayoutItem(mi)
            iset = QgsLayoutExporter.ImageExportSettings(); iset.dpi = 300
            QgsLayoutExporter(lay).exportToImage(r"{render_tmp}", iset)
        proj.clear(); os._exit(0)
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(qgis_sim_py); tp = Path(tf.name)
    try:
        run_native(["python3", str(tp)], timeout_s=180)
    finally:
        tp.unlink(missing_ok=True); render_tmp.unlink(missing_ok=True)

    grey_capex = round(sum(0.014 * sk + 0.11 * cr + 0.12 * max(0.0, 2.0 - om) for om, sk, cr in weirs.values()), 3)
    mod_subs = [row for row in subs if float(row[5]) > 0.01]
    green_ha_sum = sum(float(row[5]) for row in subs)
    total_ha = sum(float(row[3]) for row in subs)
    green_capex = round(green_ha_sum * 0.036, 3)
    recharge_idx = round((green_ha_sum / total_ha) * 3.80, 4)
    ods_vals = {}
    with ZipFile(ods) as zf:
        cxml = ElementTree.fromstring(zf.read("content.xml"))
    for r_el in cxml.iter():
        if r_el.tag.endswith("table-row"):
            cells = [c for c in list(r_el) if c.tag.endswith("table-cell")]
            if len(cells) >= 2:
                lbl = "".join(cells[0].itertext()).strip()
                va = cells[1].attrib.get("{urn:oasis:names:tc:opendocument:xmlns:office:1.0}value")
                try:
                    ods_vals[lbl] = float(va if va is not None else "".join(cells[1].itertext()).strip())
                except Exception:
                    pass
    tot_capex = round(grey_capex + green_capex, 3)
    r_rate = max(0.035, ods_vals.get("coupon_pct", 4.75) / 100.0)
    ann_debt = tot_capex * (r_rate * ((1 + r_rate) ** 20)) / (((1 + r_rate) ** 20) - 1)
    dscr = round(2.68 / max(1e-6, ann_debt), 4)
    with ZipFile(qgz) as zq:
        qnames = [n for n in zq.namelist() if n.endswith(".qgs")]
        qxml = zq.read(qnames[0]).decode("utf-8", errors="replace") if qnames else ""
    gates_b = {
        "B1_outlet_100yr_peak": outlet_100 <= 96.0,
        "B2_zero_weir_overtopping": overtopped == 0,
        "B3_confluence_synchronization_guard": tier5_max_100 <= 26.5,
        "B4_grey_capex_allowance": grey_capex <= 21.50 and abs(ods_vals.get("grey_weir_capex", -99.0) - grey_capex) <= 0.25,
        "B5_qgz_layout_and_pdf": "Weir_Retrofit_A3" in qxml and (workspace / "exports/weir_retrofit.pdf").is_file(),
    }
    gates_a = {
        "A1_500yr_critical_parcel_safety": crit_500_exceed == 0,
        "A2_baseflow_groundwater_recharge": 0.315 <= recharge_idx <= 0.342,
        "A3_max_26_modified_subbasins": 1 <= len(mod_subs) <= 26 and all(0.0 <= float(r[5]) <= 0.2201 * float(r[3]) for r in subs),
        "A4_combined_municipal_bond_dscr": tot_capex <= 25.80 and dscr >= 1.320 and abs(ods_vals.get("green_lid_capex", -99.0) - green_capex) <= 0.25,
        "A5_ods_and_atlas_pdfs": "Flood_Risk_Atlas_A3" in qxml and (workspace / "exports/bond_schedule.pdf").is_file() and (workspace / "exports/flood_risk_atlas.pdf").is_file(),
    }
    return {
        "gates_a": gates_a,
        "gates_b": gates_b,
        "metrics": {
            "outlet_100yr_peak_cms": outlet_100, "overtopped_weir_count": overtopped, "tier5_max_peak_cms": round(tier5_max_100, 3),
            "grey_weir_capex_musd": grey_capex, "green_lid_capex_musd": green_capex, "total_capex_musd": tot_capex,
            "critical_subbasin_500yr_exceedances": crit_500_exceed, "recharge_index": recharge_idx,
            "modified_subbasins_count": len(mod_subs), "min_20yr_dscr": dscr,
        },
    }


def evaluate_lh03(workspace: Path) -> dict:
    out_json = Path(tempfile.mktemp(suffix=".json"))
    fc_eval = textwrap.dedent(f'''
        import sys
        for cand in ('/usr/lib/freecad-python3/lib', '/usr/lib/freecad/lib'):
            if cand not in sys.path: sys.path.append(cand)
        import json, math, FreeCAD, Part
        doc = FreeCAD.openDocument(r"{workspace / 'cam_indexer.FCStd'}")
        sh = doc.getObject("SystemSpec")
        spec = {{}}
        for idx in range(1, 14):
            k = sh.get(f"A{{idx}}"); v = float(sh.get(f"B{{idx}}"))
            spec[k] = v
        h_sh = doc.getObject("HousingShell").Shape
        c_sh = doc.getObject("HarmonicCam").Shape
        f_sh = doc.getObject("FollowerLink").Shape
        t_sh = doc.getObject("TopCover").Shape
        radii = []
        p_angles = []
        min_cam_housing = 999.0
        for step in range(72):
            phi = math.radians(step * 5.0)
            r_val = spec["cam_r0_mm"] + spec["cam_e1_mm"]*math.cos(phi) + spec["cam_h2_mm"]*math.cos(2*phi) + spec["cam_h3_mm"]*math.cos(3*phi)
            dr = -spec["cam_e1_mm"]*math.sin(phi) - 2*spec["cam_h2_mm"]*math.sin(2*phi) - 3*spec["cam_h3_mm"]*math.sin(3*phi)
            pa = math.degrees(math.atan2(abs(dr), max(1.0, r_val + spec["follower_roller_r_mm"])))
            radii.append(r_val); p_angles.append(pa)
            rot_c = c_sh.copy()
            rot_c.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), step * 5.0)
            rot_c.tessellate(0.08)
            d_ch = rot_c.distToShape(h_sh)[0]
            if rot_c.common(h_sh).Volume > 0.01:
                d_ch = 0.0
            min_cam_housing = min(min_cam_housing, float(d_ch))
        home_gap = float(c_sh.distToShape(f_sh)[0])
        coll_vol = float(c_sh.common(f_sh).Volume + f_sh.common(h_sh).Volume + f_sh.common(t_sh).Volume + t_sh.common(c_sh).Volume)
        rho = 2.81e-6
        parts = [h_sh, c_sh, f_sh, t_sh]
        sols_all = [s for p in parts for s in p.Solids]
        vols = [float(p.Volume) for p in parts]
        tot_v = sum(vols)
        cg_x = sum(float(s.CenterOfMass.x) * float(s.Volume) for s in sols_all) / max(1.0, tot_v)
        cg_y = sum(float(s.CenterOfMass.y) * float(s.Volume) for s in sols_all) / max(1.0, tot_v)
        open(r"{out_json}", "w").write(json.dumps({{
            "stroke": max(radii) - min(radii), "max_pa": max(p_angles), "min_ch": min_cam_housing,
            "mass_b": (vols[0] + vols[1]) * rho, "mass_tot": tot_v * rho,
            "home_gap": home_gap, "coll_vol": coll_vol, "cg_r": math.hypot(cg_x, cg_y), "cover_v": vols[3],
        }}))
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(fc_eval); tp = Path(tf.name)
    try:
        run_native(["python3", str(tp)], timeout_s=240)
        res = json.loads(out_json.read_text(encoding="utf-8"))
        gates_b = {
            "B1_exact_follower_stroke": 18.35 <= res["stroke"] <= 18.45,
            "B2_pressure_angle_cap": res["max_pa"] <= 25.5,
            "B3_cam_housing_radial_clearance": res["min_ch"] >= 3.50,
            "B4_subassembly_b_mass_cap": res["mass_b"] <= 0.680,
            "B5_step_export": (workspace / "exports/cam_and_housing.step").is_file(),
        }
        gates_a = {
            "A1_hydrodynamic_film_gap_72_angles": 0.15 <= res["home_gap"] <= 0.23 and res["coll_vol"] <= 0.02,
            "A2_total_assembly_mass_cap": res["mass_tot"] <= 0.855,
            "A3_static_cg_radial_balance": res["cg_r"] <= 0.65,
            "A4_cover_stiffness_floor": res["cover_v"] >= 82000.0,
            "A5_drawings_and_step": all((workspace / p).is_file() for p in ("exports/follower_and_cover.step", "exports/kinematics_dag.svg", "exports/assembly_callout_300dpi.png")),
        }
        return {"gates_a": gates_a, "gates_b": gates_b, "metrics": {k: round(v, 4) for k, v in res.items()}}
    finally:
        tp.unlink(missing_ok=True); out_json.unlink(missing_ok=True)


def probe_video_luma_and_frames(mp4_path: Path) -> tuple[int, float, float, float, float]:
    if not mp4_path.is_file():
        return 0, 0.0, 999.0, 0.0, 0.0
    fc_cp = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(mp4_path)], capture_output=True, text=True, timeout=60)
    br_cp = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=bit_rate", "-of", "default=nw=1:nk=1", str(mp4_path)], capture_output=True, text=True, timeout=30)
    st_cp = subprocess.run(["ffmpeg", "-i", str(mp4_path), "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    try:
        frames = int(fc_cp.stdout.strip().splitlines()[0])
    except Exception:
        frames = 0
    try:
        kbps = float(br_cp.stdout.strip().splitlines()[0]) / 1000.0
    except Exception:
        kbps = 0.0
    ymins = [float(x) for x in re.findall(r"YMIN=(\d+(?:\.\d+)?)", st_cp.stdout + st_cp.stderr)]
    ymaxs = [float(x) for x in re.findall(r"YMAX=(\d+(?:\.\d+)?)", st_cp.stdout + st_cp.stderr)]
    yavgs = [float(x) for x in re.findall(r"YAVG=(\d+(?:\.\d+)?)", st_cp.stdout + st_cp.stderr)]
    if not ymins:
        return frames, 0.0, 999.0, 0.0, kbps
    return frames, min(ymins), max(ymaxs), sum(yavgs) / len(yavgs), kbps


def probe_ebur128(media_path: Path) -> tuple[float, float, float]:
    if not media_path.is_file():
        return -99.0, 0.0, 99.0
    cp = subprocess.run(["ffmpeg", "-nostats", "-i", str(media_path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    txt = cp.stderr
    m_i = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", txt)
    m_lra = re.findall(r"LRA:\s*(\d+\.\d+)\s*LU", txt)
    m_pk = re.findall(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", txt)
    return (
        float(m_i[-1]) if m_i else -99.0,
        float(m_lra[-1]) if m_lra else 0.0,
        float(m_pk[-1]) if m_pk else 99.0,
    )


def evaluate_lh04(workspace: Path) -> dict:
    stinger = workspace / "media/stinger_8s.mp4"
    music_pm = workspace / "audio/music_premaster.wav"
    master_mp4 = workspace / "exports/program_broadcast_master.mp4"
    mlt_txt = (workspace / "program_master.mlt").read_text(encoding="utf-8", errors="replace")
    s_frames, s_ymin, s_ymax, s_yavg, _ = probe_video_luma_and_frames(stinger)
    m_lufs, _, _ = probe_ebur128(music_pm)
    p_frames, p_ymin, p_ymax, _, p_kbps = probe_video_luma_and_frames(master_mp4)
    p_lufs, p_lra, p_tp = probe_ebur128(master_mp4)
    snr_db = 0.0
    if master_mp4.is_file():
        sp_cp = subprocess.run(["ffmpeg", "-ss", "5", "-t", "6", "-i", str(master_mp4), "-af", "astats=metadata=1:reset=0", "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        bg_cp = subprocess.run(["ffmpeg", "-ss", "0.5", "-t", "3", "-i", str(master_mp4), "-af", "astats=metadata=1:reset=0", "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        rms_sp = [float(x) for x in re.findall(r"RMS level dB:\s*(-?\d+\.\d+)", sp_cp.stderr)]
        rms_bg = [float(x) for x in re.findall(r"RMS level dB:\s*(-?\d+\.\d+)", bg_cp.stderr)]
        if rms_sp and rms_bg:
            snr_db = round(rms_sp[-1] - rms_bg[-1], 3)
    gates_b = {
        "B1_stinger_exact_192_frames": s_frames == 192,
        "B2_stinger_bt709_legal_luma": s_ymin >= 16.0 and s_ymax <= 235.0 and 68.0 <= s_yavg <= 92.0,
        "B3_music_stem_loudness_window": -29.0 <= m_lufs <= -24.5,
        "B4_mlt_stinger_spliced": "stinger_8s.mp4" in mlt_txt,
    }
    gates_a = {
        "A1_exact_576_frames_and_overlays": p_frames == 576,
        "A2_strict_bt709_legal_gamut": p_ymin >= 16.0 and p_ymax <= 235.0,
        "A3_ebu_r128_integrated_lufs": -23.20 <= p_lufs <= -22.80 and p_tp <= -2.0,
        "A4_loudness_range_and_ducking_snr": 5.2 <= p_lra <= 8.2 and 6.5 <= snr_db <= 9.5,
        "A5_strict_cbr_bitrate_window": 2850.0 <= p_kbps <= 3120.0,
    }
    return {
        "gates_a": gates_a,
        "gates_b": gates_b,
        "metrics": {
            "stinger_frames": s_frames, "stinger_ymin": s_ymin, "stinger_ymax": s_ymax, "stinger_yavg": round(s_yavg, 2),
            "music_lufs": m_lufs, "master_frames": p_frames, "master_ymin": p_ymin, "master_ymax": p_ymax,
            "master_lufs": p_lufs, "master_lra": p_lra, "master_tp_db": p_tp, "speech_snr_db": snr_db, "master_kbps": round(p_kbps, 1),
        },
    }


def evaluate_lh_task(task_id: str, workspace: Path, portal_state: dict | None = None) -> dict:
    eval_map = {"LH-01": evaluate_lh01, "LH-02": evaluate_lh02, "LH-03": evaluate_lh03, "LH-04": evaluate_lh04}
    raw = eval_map[task_id](workspace)
    pstate = portal_state or {}
    subs = pstate.get("submissions") or {}
    canon = workspace / LH_BY_ID[task_id]["canonical_project"]
    cur_sha = sha256_file(canon) if canon.is_file() else ""
    gates_a = dict(raw["gates_a"])
    gates_b = dict(raw["gates_b"])
    if portal_state is not None:
        gates_b["B_portal_submitted"] = "B" in subs
        gates_a["A_portal_submitted_matching_final_sha"] = ("A" in subs and subs["A"].get("project_sha256") == cur_sha)
    a_passed = sum(1 for v in gates_a.values() if v)
    b_passed = sum(1 for v in gates_b.values() if v)
    return {
        "task_id": task_id,
        "role_a_pass": all(gates_a.values()),
        "role_b_pass": all(gates_b.values()),
        "joint_pass": all(gates_a.values()) and all(gates_b.values()),
        "gates_a_score": f"{a_passed}/{len(gates_a)}",
        "gates_b_score": f"{b_passed}/{len(gates_b)}",
        "total_gates_passed": a_passed + b_passed,
        "total_gates_count": len(gates_a) + len(gates_b),
        "checks_a": gates_a,
        "checks_b": gates_b,
        "metrics": raw["metrics"],
    }


def serve_lh_drc_portal(task_id: str, port: int, workspace: Path, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "portal_state.json"
    drc_log = state_dir / "drc_calls.jsonl"
    lock = threading.Lock()
    eval_lock = threading.Lock()
    state = {"task_id": task_id, "submissions": {}, "drc_call_counts": {"A": 0, "B": 0}, "last_drc": {}, "concurrent_overwrites": 0}
    write_json(state_file, state)

    class DrcHandler(BaseHTTPRequestHandler):
        def log_message(self, *_unused):
            return

        def _reply(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path.startswith("/health"):
                self._reply(200, {"ready": True, "task_id": task_id})
                return
            if self.path.startswith("/api/status"):
                with lock:
                    self._reply(200, {"task_id": task_id, "drc_call_counts": state["drc_call_counts"], "submitted": sorted(state["submissions"].keys()), "last_drc": state["last_drc"]})
                return
            with lock:
                snap = json.dumps(state, indent=2, ensure_ascii=False)
            html = (
                f"<!doctype html><html><head><meta charset='utf-8'/><title>{task_id} DRC & Signoff</title>"
                "<style>body{font:15px/1.45 sans-serif;background:#0f172a;color:#e2e8f0;margin:20px}h1{font-size:22px;color:#38bdf8}pre{background:#020617;padding:12px;border-radius:8px;color:#93c5fd;overflow:auto}</style>"
                "<script>setInterval(()=>location.reload(),1500);</script></head><body>"
                f"<h1>{task_id} Live Engineering DRC & Signoff Portal</h1>"
                "<p>POST <code>/api/drc_check</code> with <code>{\"role\": \"A|B\"}</code> or POST <code>/api/submit</code></p>"
                f"<pre>{snap}</pre></body></html>"
            ).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8", errors="replace") or "{}")
            role = str(body.get("role", "A")).upper()
            if self.path.startswith("/api/drc_check"):
                t0 = time.time()
                try:
                    with eval_lock:
                        ev = evaluate_lh_task(task_id, workspace, portal_state=None)
                    role_gates = ev["checks_a"] if role == "A" else ev["checks_b"]
                    resp = {
                        "ok": True,
                        "role": role,
                        "all_role_gates_passed": all(role_gates.values()),
                        "passed_count": sum(1 for v in role_gates.values() if v),
                        "total_count": len(role_gates),
                        "role_gates": role_gates,
                        "measured_metrics": ev["metrics"],
                        "elapsed_s": round(time.time() - t0, 2),
                    }
                except Exception as exc:
                    resp = {"ok": False, "role": role, "all_role_gates_passed": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                with lock:
                    state["drc_call_counts"][role] = state["drc_call_counts"].get(role, 0) + 1
                    state["last_drc"][role] = {"passed_count": resp.get("passed_count", 0), "total_count": resp.get("total_count", 0), "all_passed": resp.get("all_role_gates_passed", False), "elapsed_s": resp.get("elapsed_s")}
                    write_json(state_file, state)
                    with drc_log.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"timestamp": time.time(), **resp}) + "\n")
                self._reply(200, resp)
                return
            if self.path.startswith("/api/submit"):
                with lock:
                    rec = {"role": role, "project_sha256": str(body.get("project_sha256", "")), "metrics": body.get("metrics") or {}, "timestamp": time.time()}
                    state["submissions"][role] = rec
                    write_json(state_file, state)
                self._reply(200, {"ok": True, "submitted": rec})
                return
            self._reply(404, {"ok": False})

    srv = ThreadingHTTPServer(("127.0.0.1", port), DrcHandler)
    srv.daemon_threads = True
    srv.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--task", required=True); pb.add_argument("--workspace", type=Path, required=True); pb.add_argument("--ticket-a", type=Path, required=True); pb.add_argument("--ticket-b", type=Path, required=True)
    ps = sub.add_parser("serve")
    ps.add_argument("--task", required=True); ps.add_argument("--port", type=int, required=True); ps.add_argument("--workspace", type=Path, required=True); ps.add_argument("--state-dir", type=Path, required=True)
    pg = sub.add_parser("grade")
    pg.add_argument("--task", required=True); pg.add_argument("--workspace", type=Path, required=True); pg.add_argument("--portal-state", type=Path, default=None); pg.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "build":
        build_lh_bundle(args.task, args.workspace.resolve(), args.ticket_a.resolve(), args.ticket_b.resolve())
        return 0
    if args.cmd == "serve":
        serve_lh_drc_portal(args.task, args.port, args.workspace.resolve(), args.state_dir.resolve())
        return 0
    if args.cmd == "grade":
        ps_obj = json.loads(args.portal_state.read_text(encoding="utf-8")) if (args.portal_state and args.portal_state.is_file()) else {}
        try:
            res = evaluate_lh_task(args.task, args.workspace.resolve(), ps_obj)
        except Exception as exc:
            res = {"task_id": args.task, "role_a_pass": False, "role_b_pass": False, "joint_pass": False, "gates_a_score": "0/6", "gates_b_score": "0/6", "total_gates_passed": 0, "total_gates_count": 12, "checks_a": {"uncorrupted": False}, "checks_b": {"uncorrupted": False}, "metrics": {"error": str(exc)[:300]}}
        write_json(args.out.resolve(), res)
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
