"""Builders, 4-role graders, and zero-LLM self-validation for QH-01..QH-04."""
from __future__ import annotations

import argparse
import csv
import hashlib
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
import xml.etree.ElementTree as ElementTree
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from tasks.quad_hybrid_v1.catalog import QH_BY_ID, QUAD_HYBRID_CATALOG, QUAD_ROLES

SVG_NS = "http://www.w3.org/2000/svg"
ElementTree.register_namespace("", SVG_NS)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in list(path.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_cmd(cmd: list[str], timeout_s: int = 180) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    rt = Path(env.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-quad-build"))
    rt.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(rt, 0o700)
    cp = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s)
    if cp.returncode != 0:
        raise RuntimeError(f"Command {cmd[:3]} failed ({cp.returncode}): {cp.stderr[-600:] or cp.stdout[-600:]}")
    return cp


def make_simple_ods(path: Path, table_name: str, rows: list[tuple[str, float | str]]) -> None:
    mime = "application/vnd.oasis.opendocument.spreadsheet"
    manifest = f'''<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    row_xml = []
    for k, v in rows:
        if isinstance(v, (int, float)):
            row_xml.append(f'<table:table-row><table:table-cell office:value-type="string"><text:p>{k}</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="{v}"><text:p>{v}</text:p></table:table-cell></table:table-row>')
        else:
            row_xml.append(f'<table:table-row><table:table-cell office:value-type="string"><text:p>{k}</text:p></table:table-cell><table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell></table:table-row>')
    content = f'''<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:spreadsheet><table:table table:name="{table_name}">''' + "".join(row_xml) + "</table:table></office:spreadsheet></office:body></office:document-content>"
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", mime, compress_type=ZIP_STORED)
        zf.writestr("META-INF/manifest.xml", manifest, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content, compress_type=ZIP_DEFLATED)


def read_simple_ods(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with ZipFile(path) as zf:
        cxml = ElementTree.fromstring(zf.read("content.xml"))
    for r_el in cxml.iter():
        if r_el.tag.endswith("table-row"):
            cells = [c for c in list(r_el) if c.tag.endswith("table-cell")]
            if len(cells) >= 2:
                k = "".join(cells[0].itertext()).strip()
                va = cells[1].attrib.get("{urn:oasis:names:tc:opendocument:xmlns:office:1.0}value")
                vt = "".join(cells[1].itertext()).strip()
                out[k] = va if va is not None else vt
    return out


def make_simple_odt(path: Path, body_text: str) -> None:
    mime = "application/vnd.oasis.opendocument.text"
    manifest = f'''<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    content = f'''<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:text><text:p>{body_text}</text:p></office:text></office:body></office:document-content>'''
    with ZipFile(path, "w") as zf:
        zf.writestr("mimetype", mime, compress_type=ZIP_STORED)
        zf.writestr("META-INF/manifest.xml", manifest, compress_type=ZIP_DEFLATED)
        zf.writestr("content.xml", content, compress_type=ZIP_DEFLATED)


def build_qh01(workspace: Path, tickets: dict[str, Path]) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    bl_py = textwrap.dedent(f'''
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 16; sc.cycles.use_denoising = False
        sc.render.resolution_x = 640; sc.render.resolution_y = 360
        bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=1.10, location=(0.0, 0.0, 0.55))
        sp = bpy.context.active_object; sp.name = "SpeakerShell"
        mat = bpy.data.materials.new(name="ShellMat"); mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.65, 0.65, 0.68, 1.0)
        sp.data.materials.append(mat)
        ld = bpy.data.lights.new("KeyLight", type="AREA"); ld.energy = 600.0
        lo = bpy.data.objects.new("KeyLight", ld); lo.location = (2.2, -2.5, 2.8); sc.collection.objects.link(lo)
        cd = bpy.data.cameras.new("MainCam"); cd.lens = 35.0
        co = bpy.data.objects.new("MainCam", cd); co.location = (0.0, -3.8, 1.1); co.rotation_euler = (1.38, 0.0, 0.0)
        sc.collection.objects.link(co); sc.camera = co
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'hero_device.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(bl_py); tp = Path(tf.name)
    try:
        run_cmd(["blender", "-b", "--python", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    scm = (
        '(let* ((img (car (gimp-image-new 640 360 RGB))) '
        '(lyr (car (gimp-layer-new img 640 360 RGB-IMAGE "hero_bg" 100 LAYER-MODE-NORMAL)))) '
        '(gimp-image-insert-layer img lyr 0 0) '
        '(gimp-context-set-background (quote (40 48 64))) '
        '(gimp-drawable-fill lyr FILL-BACKGROUND) '
        f'(gimp-xcf-save 0 img lyr "{workspace}/key_visual.xcf" "{workspace}/key_visual.xcf"))'
    )
    run_cmd(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"])
    (workspace / "spec_badges.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="120"><rect width="640" height="120" fill="#0F172A"/><circle id="badge_1" cx="80" cy="60" r="32" stroke="#94A3B8" stroke-width="1.0" fill="none"/><circle id="badge_2" cx="200" cy="60" r="32" stroke="#94A3B8" stroke-width="1.0" fill="none"/><text id="promo_tag" x="300" y="68" fill="#F8FAFC" font-size="24">DRAFT</text></svg>',
        encoding="utf-8",
    )
    make_simple_ods(workspace / "launch_pricing.ods", "Pricing", [("sku", "TBD"), ("msrp_usd", 0.0), ("unit_cost_usd", 132.0), ("net_margin_usd", 0.0)])
    write_json(tickets["D"] / "cost_basis.json", {"unit_cost_usd": 132.0, "channel_fee_usd": 18.0})

    (tickets["B"] / "task.md").write_text(textwrap.dedent('''
        # Role B Ticket — 3D Industrial Design (`hero_device.blend` + Launch Studio GUI)

        1. **Open Role B Workbench via GUI**: On `DISPLAY=:99`, click `Module 1 tab` in the open Chromium Launch Studio Console (`desktop.click` + `desktop.screenshot`) to read your visual specification card (`TARGET HEIGHT`, `CAMERA LENS`, `SHELL RGB`).
        2. **CLI 3D Engineering (`guest_bash`)**: First run an 8-angle (`0..315` deg, `640x360`, `24` Cycles samples) turntable illumination sweep on `/workspace/hero_device.blend` into `/tmp/angle_{idx}.png` before modifying the scene. After all 8 Cycles renders complete, update `/workspace/hero_device.blend` so `SpeakerShell` Z-dimension equals `TARGET HEIGHT` (bottom at `z=0`), `MainCam` focal length equals `CAMERA LENS`, and `ShellMat` Base Color equals `[R/255, G/255, B/255, 1.0]`. Save `/workspace/hero_device.blend` and render `/workspace/exports/hero_render.png` (`640x360`, Cycles).
        3. **GUI Commit**: On `Module 1 tab` (re-click `TAB B` if needed), enter `<TARGET_HEIGHT>` (`2` decimals, e.g. `1.50`) into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["C"] / "task.md").write_text(textwrap.dedent('''
        # Role C Ticket — Brand Packaging (`key_visual.xcf` + `spec_badges.svg` + Launch Studio GUI)

        1. **Open Role C Workbench via GUI**: Click `Module 2 tab` in the Chromium Launch Studio Console (`desktop.click` + `desktop.screenshot`) to read your visual specification card (`RIBBON RGB`, `BADGE STROKE`, `PROMO TAG`).
        2. **CLI GIMP & Inkscape Production (`guest_bash`)**: First run 6 separate headless GIMP (`1024x768`) Gaussian-blur test renders into `/tmp/trial_{idx}.png`. After all 6 GIMP batch runs finish, add a top RGBA layer `launch_ribbon` in `/workspace/key_visual.xcf` with rectangle `(x=40, y=140, w=560, h=80)` filled with `RIBBON RGB`, save `/workspace/key_visual.xcf`, and export flattened `/workspace/exports/banner_flat.png`. Update `/workspace/spec_badges.svg` (`badge_1` & `badge_2` `stroke-width` = `BADGE STROKE`, `#promo_tag` = `PROMO TAG`) and export `/workspace/exports/badges_300dpi.png` (`--export-dpi=300`).
        3. **GUI Commit**: On `Module 2 tab`, type `PROMO TAG` into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["D"] / "task.md").write_text(textwrap.dedent('''
        # Role D Ticket — Commercial Pricing (`launch_pricing.ods` + Launch Studio GUI)

        1. **Open Role D Workbench via GUI**: Click `Module 3 tab` in the Chromium Launch Studio Console (`desktop.click` + `desktop.screenshot`) to read your visual specification card (`APPROVED MSRP` and `PRODUCT SKU`).
        2. **CLI Spreadsheet & PDF (`guest_bash`)**: Read `/session/ticket/cost_basis.json` (`unit_cost_usd = 132.0`, `channel_fee_usd = 18.0`), compute `net_margin_usd = MSRP - unit_cost_usd - channel_fee_usd`, update `sku`, `msrp_usd`, and `net_margin_usd` in `/workspace/launch_pricing.ods`, and export `/workspace/exports/pricing_sheet.pdf` via `libreoffice --headless --convert-to pdf`.
        3. **GUI Commit**: On `Module 3 tab`, type `PRODUCT SKU` into **Code / Tag** and `net_margin_usd` into **Computed Value**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["A"] / "task.md").write_text(textwrap.dedent('''
        # Role A Ticket — Launch QA Lead (Cross-Asset Verification + Launch Studio GUI)

        1. **Open Role A Workbench via GUI**: Click `Module 4 tab` in the Chromium Launch Studio Console (`desktop.click` + `desktop.screenshot`) to read your QA specification card (`PRESS CARD` size & `SAMPLES`).
        2. **CLI Cross-Asset Composite & Render (`guest_bash`)**: Measure `SpeakerShell` Z-height (`m`, 2 decimals) in `/workspace/hero_device.blend`, render `/workspace/exports/hero_render.png` (`640x360`, Cycles `16` samples) from `/workspace/hero_device.blend`, flatten `/workspace/key_visual.xcf` (`640x360` top) stacked above a `640x120` PNG export of `/workspace/spec_badges.svg` into `/workspace/exports/press_kit_card.png` (`640x480`), and compute the first 12 hex chars of `sha256(/workspace/hero_device.blend)`.
        3. **GUI Final Lock**: On `Module 4 tab`, enter the 12-char `hero_device.blend` SHA256 prefix into **Canonical SHA256 (first 12 hex)** and the measured `SpeakerShell` Z-height (`2` decimals) into **Final Summary Metric**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")


def build_qh02(workspace: Path, tickets: dict[str, Path]) -> None:
    (workspace / "data").mkdir(parents=True, exist_ok=True)
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    qgis_py = textwrap.dedent(f'''
        import os
        from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle, QgsVectorFileWriter, QgsVectorLayer
        from PyQt5.QtCore import QVariant
        qgs = QgsApplication([], False); qgs.initQgis()
        gpkg = r"{workspace / 'data/grid.gpkg'}"; qgz = r"{workspace / 'metro_grid.qgz'}"
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        ff = QgsFields()
        for nm, tp in [("feeder_id", QVariant.String), ("sub_id", QVariant.String), ("status", QVariant.String), ("mw_flow", QVariant.Double)]:
            ff.append(QgsField(nm, tp))
        fl = QgsVectorLayer("LineString?crs=epsg:3857", "feeders", "memory"); fl.dataProvider().addAttributes(ff); fl.updateFields()
        ffeats = []
        for idx in range(1, 17):
            ft = QgsFeature(fl.fields())
            ft.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(idx*200.0, 0.0), QgsPointXY(idx*200.0, 900.0)]))
            ft.setAttributes([f"F-{{idx:02d}}", f"SUB-{{((idx-1)//2)+1:02d}}", "IN_SERVICE", 20.0])
            ffeats.append(ft)
        fl.dataProvider().addFeatures(ffeats)
        o1 = QgsVectorFileWriter.SaveVectorOptions(); o1.driverName = "GPKG"; o1.layerName = "feeders"
        QgsVectorFileWriter.writeAsVectorFormatV3(fl, gpkg, QgsProject.instance().transformContext(), o1)

        sf = QgsFields()
        for nm, tp in [("sub_id", QVariant.String), ("demand_mw", QVariant.Double), ("tie_bonus_mw", QVariant.Double), ("net_headroom_mw", QVariant.Double)]:
            sf.append(QgsField(nm, tp))
        sl = QgsVectorLayer("Polygon?crs=epsg:3857", "substations", "memory"); sl.dataProvider().addAttributes(sf); sl.updateFields()
        sfeats = []
        for idx in range(1, 9):
            ft = QgsFeature(sl.fields())
            ft.setGeometry(QgsGeometry.fromRect(QgsRectangle(idx*350.0, 100.0, idx*350.0+260.0, 360.0)))
            ft.setAttributes([f"SUB-{{idx:02d}}", 28.0, 0.0, 12.0])
            sfeats.append(ft)
        sl.dataProvider().addFeatures(sfeats)
        o2 = QgsVectorFileWriter.SaveVectorOptions(); o2.driverName = "GPKG"; o2.layerName = "substations"
        o2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(sl, gpkg, QgsProject.instance().transformContext(), o2)

        proj = QgsProject.instance(); proj.setCrs(crs)
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=feeders", "feeders", "ogr"))
        proj.addMapLayer(QgsVectorLayer(f"{{gpkg}}|layername=substations", "substations", "ogr"))
        proj.write(qgz); proj.clear(); os._exit(0)
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(qgis_py); tp = Path(tf.name)
    try:
        run_cmd(["python3", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    make_simple_ods(workspace / "dispatch_tariff.ods", "Tariff", [("surge_mult", 1.0), ("base_mwh", 400.0), ("rate_usd", 80.0), ("reserve_cost_usd", 32000.0)])
    make_simple_odt(workspace / "switching_order.odt", "DEFICIT_SUBS=0")

    (tickets["B"] / "task.md").write_text(textwrap.dedent('''
        # Role B Ticket — Fault Isolation GIS (`grid.gpkg` + `metro_grid.qgz` + Grid Console GUI)

        1. **Open Role B Workbench via GUI**: Click `Module 1 tab` in the Chromium Grid Console (`desktop.click` + `desktop.screenshot`) to read your visual card listing the 4 faulted feeders.
        2. **CLI PyQGIS Fault Trip (`guest_bash`)**: First run a 6-radius (`150..900m`, `300` DPI) PyQGIS buffer sensitivity render sweep into `/tmp/buf_{r}.png` before editing `grid.gpkg`. Then in `/workspace/data/grid.gpkg` (`feeders`), set `status = 'TRIPPED'` and `mw_flow = 0.0` for those 4 feeders, add layout `Storm_Isolation` in `/workspace/metro_grid.qgz`, save it, and export `/workspace/exports/isolation_map.pdf`.
        3. **GUI Commit**: On `Module 1 tab`, type the comma-joined tripped feeder IDs into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["C"] / "task.md").write_text(textwrap.dedent('''
        # Role C Ticket — Tie-Line Rerouting (`grid.gpkg` + Graphviz + Grid Console GUI)

        1. **Open Role C Workbench via GUI**: Click `Module 2 tab` in the Chromium Grid Console (`desktop.click` + `desktop.screenshot`) to read your visual card (`TIE CODE`, `BONUS`, `TARGET`).
        2. **CLI Graphviz & GPKG Update (`guest_bash`)**: Render an 8-substation rerouting DAG diagram with `TIE-NORTH-7` highlighted to `/workspace/exports/reroute_topology.svg` via Graphviz `dot`. Then update `tie_bonus_mw = 18.0` on target substation `SUB-04` in `substations` inside `/workspace/data/grid.gpkg` (using PyQGIS `startEditing/commitChanges`).
        3. **GUI Commit**: On `Module 2 tab`, type `TIE CODE` into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["D"] / "task.md").write_text(textwrap.dedent('''
        # Role D Ticket — Emergency Tariff Reserve (`dispatch_tariff.ods` + Grid Console GUI)

        1. **Open Role D Workbench via GUI**: Click `Module 3 tab` in the Chromium Grid Console (`desktop.click` + `desktop.screenshot`) to read your visual card (`SURGE MULT`, `BASE MWH`, `BASE RATE`).
        2. **CLI Calc Reserve Schedule (`guest_bash`)**: Compute `reserve_cost_usd = SURGE_MULT * BASE_MWH * BASE_RATE`, update `surge_mult` and `reserve_cost_usd` in `/workspace/dispatch_tariff.ods`, and export `/workspace/exports/tariff_schedule.pdf` via LibreOffice.
        3. **GUI Commit**: On `Module 3 tab`, enter `SURGE MULT` into **Code / Tag** and `reserve_cost_usd` into **Computed Value**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["A"] / "task.md").write_text(textwrap.dedent('''
        # Role A Ticket — Chief Dispatcher (`metro_grid.qgz` + `switching_order.odt` + Grid Console GUI)

        1. **Open Role A Workbench via GUI**: Click `Module 4 tab` in the Chromium Grid Console (`desktop.click` + `desktop.screenshot`) to read your dispatch card (`LAYOUT` name & `TAG` format).
        2. **CLI Headroom Atlas & Switching Order (`guest_bash`)**: For every substation `SUB-01..SUB-08` in `/workspace/data/grid.gpkg`, recompute `net_headroom_mw = sum(mw_flow of feeders serving sub_id) + tie_bonus_mw - demand_mw` via PyQGIS, add layout `Grid_Headroom_Atlas` to `/workspace/metro_grid.qgz`, save `/workspace/metro_grid.qgz`, and export `/workspace/exports/headroom_atlas.pdf`. Count substations with `net_headroom_mw < 0` (`DEFICIT_SUBS=<int>`), write `DEFICIT_SUBS=<int>` into `/workspace/switching_order.odt`, and export `/workspace/exports/switching_order.pdf` via LibreOffice.
        3. **GUI Final Lock**: On `Module 4 tab`, enter the first 12 hex chars of `sha256(/workspace/metro_grid.qgz)` into **Canonical SHA256 (first 12 hex)** and `DEFICIT_SUBS=<int>` into **Final Summary Metric**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")


def build_qh03(workspace: Path, tickets: dict[str, Path]) -> None:
    (workspace / "exports").mkdir(parents=True, exist_ok=True)
    fc_py = textwrap.dedent(f'''
        import sys, math
        for c in ('/usr/lib/freecad-python3/lib', '/usr/lib/freecad/lib'):
            if c not in sys.path: sys.path.append(c)
        import FreeCAD, Part, Spreadsheet
        doc = FreeCAD.newDocument("WorkcellAssy")
        sh = doc.addObject("Spreadsheet::Sheet", "MasterSpec")
        sh.set("A1", "bore_mm"); sh.set("B1", "50.0")
        sh.set("A2", "bolt_r_mm"); sh.set("B2", "38.0")
        sh.set("A3", "sensor_z_mm"); sh.set("B3", "60.0")
        base = Part.makeCylinder(64.0, 24.0).cut(Part.makeCylinder(25.0, 28.0, FreeCAD.Vector(0,0,-2)))
        for k in range(6):
            ang = k * math.pi / 3.0
            base = base.cut(Part.makeCylinder(3.5, 28.0, FreeCAD.Vector(38.0*math.cos(ang), 38.0*math.sin(ang), -2)))
        b_obj = doc.addObject("Part::Feature", "BasePlate"); b_obj.Shape = base
        m_obj = doc.addObject("Part::Feature", "MotorMount"); m_obj.Shape = Part.makeCylinder(64.0, 10.0, FreeCAD.Vector(0,0,24.0))
        s_obj = doc.addObject("Part::Feature", "SensorBridge"); s_obj.Shape = Part.makeBox(20.0, 20.0, 8.0, FreeCAD.Vector(-10,-10,60.0))
        doc.recompute(); doc.saveAs(r"{workspace / 'workcell_assy.FCStd'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(fc_py); tp = Path(tf.name)
    try:
        run_cmd(["python3", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    bl_py = textwrap.dedent(f'''
        import bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 16; sc.cycles.use_denoising = False
        sc.render.resolution_x = 640; sc.render.resolution_y = 360
        bpy.ops.mesh.primitive_cylinder_add(radius=0.50, depth=0.24, location=(0,0,0.12))
        bp = bpy.context.active_object; bp.name = "TwinBase"
        bpy.ops.mesh.primitive_cube_add(size=0.20, location=(0,0,0.60))
        sb = bpy.context.active_object; sb.name = "TwinSensor"
        ld = bpy.data.lights.new("Sun", type="SUN"); ld.energy = 5.0
        lo = bpy.data.objects.new("Sun", ld); sc.collection.objects.link(lo)
        cd = bpy.data.cameras.new("Cam"); co = bpy.data.objects.new("Cam", cd)
        co.location = (0, -2.4, 1.1); co.rotation_euler = (1.25, 0, 0); sc.collection.objects.link(co); sc.camera = co
        bpy.ops.wm.save_as_mainfile(filepath=r"{workspace / 'workcell_viz.blend'}")
    ''')
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(bl_py); tp = Path(tf.name)
    try:
        run_cmd(["blender", "-b", "--python", str(tp)])
    finally:
        tp.unlink(missing_ok=True)

    (workspace / "wiring_panel.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="256"><rect width="512" height="256" fill="#0F172A"/><rect id="accent_frame" x="20" y="20" width="472" height="216" stroke="#64748B" stroke-width="1.0" fill="none"/><text id="safety_badge" x="48" y="76" fill="#F8FAFC" font-size="24">INIT</text></svg>',
        encoding="utf-8",
    )

    (tickets["B"] / "task.md").write_text(textwrap.dedent('''
        # Role B Ticket — Base CAD ECO (`workcell_assy.FCStd` + PLM Console GUI)

        1. **Open Role B Workbench via GUI**: Click `Module 1 tab` in the Chromium PLM Console (`desktop.click` + `desktop.screenshot`) to read your visual blueprint card (`NEW BORE`, `NEW BOLT R`, `ECO TAG`).
        2. **CLI OpenCASCADE Sweep & Base Rebuild (`guest_bash`)**: First run a 36-case 3D filleted (`makeFillet(0.8, shape.Edges)`) STL stress sweep (`0.05` mm tessellation) saving `/tmp/mesh_{idx:02d}.stl` BEFORE modifying `workcell_assy.FCStd`. After all 36 filleted `.stl` meshes are generated, update `MasterSpec` (`B1` = `NEW BORE`, `B2` = `NEW BOLT R`) and rebuild `BasePlate` (`outer r=64, h=24` minus center bore **diameter** `NEW BORE` and 6 `r=3.5` bolt holes at `NEW BOLT R`) in `/workspace/workcell_assy.FCStd`, save it, and export `/workspace/exports/base_plate.step`.
        3. **GUI Commit**: On `Module 1 tab`, type `ECO TAG` into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["C"] / "task.md").write_text(textwrap.dedent('''
        # Role C Ticket — Mating Mount & Sensor Bridge (`workcell_assy.FCStd` + PLM Console GUI)

        1. **Open Role C Workbench via GUI**: Click `Module 2 tab` in the Chromium PLM Console (`desktop.click` + `desktop.screenshot`) to read your visual blueprint card (`CLEARANCE` and `SENSOR Z`).
        2. **CLI Mating CAD Solids (`guest_bash`)**: Read current `bore_mm` (`B1`) and `bolt_r_mm` (`B2`) from `MasterSpec` in `/workspace/workcell_assy.FCStd`, set `B3` (`sensor_z_mm`) to `SENSOR Z`, rebuild `MotorMount` (upper flange `r=64, z=24..34` fused with lower pilot boss of **diameter** `bore_mm - CLEARANCE`, `z=14..24`, cut with 6 `r=3.5` holes at `bolt_r_mm`) and `SensorBridge` (`20x20x8` box at `z = SENSOR Z`), save `/workspace/workcell_assy.FCStd`, and export `/workspace/exports/motor_mount.step`.
        3. **GUI Commit**: On `Module 2 tab`, type `Z=<SENSOR_Z>` (e.g. `Z=72.0`) into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["D"] / "task.md").write_text(textwrap.dedent('''
        # Role D Ticket — Safety Panel SVG (`wiring_panel.svg` + PLM Console GUI)

        1. **Open Role D Workbench via GUI**: Click `Module 3 tab` in the Chromium PLM Console (`desktop.click` + `desktop.screenshot`) to read your visual blueprint card (`ACCENT HEX`, `FRAME STROKE`, `BADGE TEXT`).
        2. **CLI Inkscape Production (`guest_bash`)**: Update `#accent_frame` in `/workspace/wiring_panel.svg` to `stroke=ACCENT HEX` and `stroke-width=FRAME STROKE`, set `#safety_badge` text to `BADGE TEXT`, save `/workspace/wiring_panel.svg`, and export `/workspace/exports/wiring_panel_300dpi.png` (`--export-dpi=300`).
        3. **GUI Commit**: On `Module 3 tab`, enter `BADGE TEXT` into **Code / Tag** and `FRAME STROKE` into **Computed Value**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["A"] / "task.md").write_text(textwrap.dedent('''
        # Role A Ticket — Digital Twin Sync & PLM Release (`workcell_viz.blend` + PLM Console GUI)

        1. **Open Role A Workbench via GUI**: Click `Module 4 tab` in the Chromium PLM Console (`desktop.click` + `desktop.screenshot`) to read your QA card (`TWIN RES` & `SCALE`).
        2. **CLI Digital Twin Sync (`guest_bash`)**: Read committed `bore_mm` (`B1`) and `sensor_z_mm` (`B3`) from `MasterSpec` in `/workspace/workcell_assy.FCStd`, update `/workspace/workcell_viz.blend` so `TwinBase` X/Y diameter in meters equals `bore_mm / 100.0` (e.g. `0.58` m for `58.0` mm) and `TwinSensor` `location.z` equals `sensor_z_mm / 100.0` (e.g. `0.72` m), save `/workspace/workcell_viz.blend`, and render `/workspace/exports/workcell_beauty.png` (`640x360`).
        3. **GUI Final Lock**: On `Module 4 tab`, enter the first 12 hex chars of `sha256(/workspace/workcell_assy.FCStd)` into **Canonical SHA256 (first 12 hex)** and `bore_mm` (`1` decimal) into **Final Summary Metric**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")


def build_qh04(workspace: Path, tickets: dict[str, Path]) -> None:
    for sub in ("media", "gfx", "audio", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    for idx, col in [(1, "midnightblue"), (2, "slategray"), (3, "darkslateblue")]:
        run_cmd(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={col}:s=640x360:r=24", "-t", "2.0", "-pix_fmt", "yuv420p", str(workspace / f"media/seg{idx}.mp4")])
    run_cmd(["sox", "-n", "-r", "48000", "-c", "2", str(workspace / "audio/raw_bed.wav"), "synth", "8.0", "sine", "330", "vol", "0.35"])
    scm = (
        '(let* ((img (car (gimp-image-new 640 360 RGBA))) '
        '(lyr (car (gimp-layer-new img 640 360 RGBA-IMAGE "lower_third" 100 LAYER-MODE-NORMAL)))) '
        '(gimp-image-insert-layer img lyr 0 0) '
        '(gimp-drawable-fill lyr FILL-TRANSPARENT) '
        f'(gimp-xcf-save 0 img lyr "{workspace}/gfx/lower_third.xcf" "{workspace}/gfx/lower_third.xcf"))'
    )
    run_cmd(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"])
    mlt = '''<?xml version="1.0" encoding="utf-8"?><mlt profile="hdv_720_24p"><producer id="p1"><property name="resource">/workspace/media/seg1.mp4</property></producer><producer id="p2"><property name="resource">/workspace/media/seg2.mp4</property></producer><producer id="p3"><property name="resource">/workspace/media/seg3.mp4</property></producer><playlist id="main"><entry producer="p1" in="0" out="47"/><entry producer="p2" in="0" out="47"/><entry producer="p3" in="0" out="47"/></playlist></mlt>'''
    (workspace / "live_show.mlt").write_text(mlt, encoding="utf-8")
    make_simple_ods(workspace / "cue_sheet.ods", "CueSheet", [("show_code", "INIT"), ("target_lufs", -16.0), ("duration_s", 6.0)])

    (tickets["B"] / "task.md").write_text(textwrap.dedent('''
        # Role B Ticket — Segment-2 Slow-Mo Conform (`live_show.mlt` + MCR Console GUI)

        1. **Open Role B Workbench via GUI**: Click `Module 1 tab` in the Chromium MCR Console (`desktop.click` + `desktop.screenshot`) to read your visual card (`SEG-2` frames, `COLOR`, `NEW TOTAL`).
        2. **CLI FFmpeg Benchmark & MLT Update (`guest_bash`)**: First run a 6-pass `x264` `-preset veryslow` (`1280x720`, `2.5s` `mandelbrot` test source, `crf=18..28`) encoding benchmark into `/tmp/bench_{idx}.mp4` BEFORE modifying `live_show.mlt`. After all 6 `veryslow` benchmark encodes finish, generate `/workspace/media/seg2_gold.mp4` (`4.0` s = `96` frames at `24` fps, `640x360`, `color=c=#D4AF37`), update producer `p2` in `/workspace/live_show.mlt` to `/workspace/media/seg2_gold.mp4` with `out="95"` (`192` total frames), and save `/workspace/live_show.mlt`.
        3. **GUI Commit**: On `Module 1 tab`, type `NEW TOTAL` into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["C"] / "task.md").write_text(textwrap.dedent('''
        # Role C Ticket — GIMP Broadcast Lower-Third (`lower_third.xcf` + MCR Console GUI)

        1. **Open Role C Workbench via GUI**: Click `Module 2 tab` in the Chromium MCR Console (`desktop.click` + `desktop.screenshot`) to read your visual card (`BAR RGB`, `RECT`, `TAG`).
        2. **CLI GIMP Batch Overlay (`guest_bash`)**: First run 5 GIMP Gaussian-blur test renders (`1024x576`) into `/tmp/gfx_test_{idx}.png`. Then paint `BAR RGB` inside `RECT` on layer `lower_third` in `/workspace/gfx/lower_third.xcf` (surrounding pixels transparent), save `/workspace/gfx/lower_third.xcf`, and export `/workspace/exports/lower_third.png`.
        3. **GUI Commit**: On `Module 2 tab`, type `TAG` into **Primary Tag / Metric** and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["D"] / "task.md").write_text(textwrap.dedent('''
        # Role D Ticket — Audio Normalization & Cue Sheet (`master_audio.wav` + `cue_sheet.ods` + MCR Console GUI)

        1. **Open Role D Workbench via GUI**: Click `Module 3 tab` in the Chromium MCR Console (`desktop.click` + `desktop.screenshot`) to read your visual card (`TARGET`, `DURATION`, `SHOW CODE`).
        2. **CLI Audio Loudness & Calc (`guest_bash`)**: Normalize `/workspace/audio/raw_bed.wav` into `/workspace/audio/master_audio.wav` (`DURATION`, `48kHz` stereo) with FFmpeg `ebur128` integrated loudness within `TARGET ± 0.5` LUFS. Update `show_code`, `target_lufs`, and `duration_s` in `/workspace/cue_sheet.ods`, and export `/workspace/exports/cue_sheet.pdf` via LibreOffice.
        3. **GUI Commit**: On `Module 3 tab`, enter `SHOW CODE` into **Code / Tag** and `TARGET` numeric value (`-23.0`) into **Computed Value**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")

    (tickets["A"] / "task.md").write_text(textwrap.dedent('''
        # Role A Ticket — On-Air Master Director (`on_air_master.mp4` + MCR Console GUI)

        1. **Open Role A Workbench via GUI**: Click `Module 4 tab` in the Chromium MCR Console (`desktop.click` + `desktop.screenshot`) to read your broadcast master card (`RESOLUTION` & `FPS`).
        2. **CLI Master Render & Overlay (`guest_bash`)**: Render `/workspace/live_show.mlt` via `melt`, overlay `/workspace/exports/lower_third.png` (if present, or export from `gfx/lower_third.xcf`) and mux `/workspace/audio/master_audio.wav` (if present, else `raw_bed.wav`) into `/workspace/exports/on_air_master.mp4` (`640x360`, `24` fps, `yuv420p`). Measure exact video frame count via `ffprobe` and compute the first 12 hex chars of `sha256(/workspace/live_show.mlt)`.
        3. **GUI Final Lock**: On `Module 4 tab`, enter the 12-char `live_show.mlt` SHA256 prefix into **Canonical SHA256 (first 12 hex)** and the rendered frame count into **Final Summary Metric**, and click **[1] Stage Preview (8s)**, wait 8.5s via desktop.wait, and click **[2] Commit Verified**.
    ''').strip() + "\n", encoding="utf-8")


def build_quad_bundle(task_id: str, workspace: Path, tickets_root: Path) -> dict[str, Path]:
    clear_dir(workspace)
    clear_dir(tickets_root)
    tmap = {r: tickets_root / r for r in QUAD_ROLES}
    for p in tmap.values():
        p.mkdir(parents=True, exist_ok=True)
    {"QH-01": build_qh01, "QH-02": build_qh02, "QH-03": build_qh03, "QH-04": build_qh04}[task_id](workspace, tmap)
    return tmap


def mean_rgb_diff(p1: Path, p2: Path) -> float:
    from PIL import Image
    if not p1.is_file() or not p2.is_file():
        return 255.0
    with Image.open(p1) as i1, Image.open(p2) as i2:
        r1, r2 = i1.convert("RGB"), i2.convert("RGB")
        if r1.size != r2.size:
            return 255.0
        b1, b2 = r1.tobytes(), r2.tobytes()
        return sum(abs(x - y) for x, y in zip(b1, b2)) / max(1, len(b1))


def grade_quad_task(task_id: str, workspace: Path, portal_state: dict) -> dict:
    subs = (portal_state or {}).get("submissions") or {}
    tainted = bool((portal_state or {}).get("buffer_tainted"))
    side_notes = [p.name for p in workspace.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".md", ".lock"}]
    sub_val = {r: str((subs.get(r) or {}).get("value", "")).strip() for r in QUAD_ROLES}
    canon_sha12 = sha256_file(workspace / QH_BY_ID[task_id]["canonical_project"])[:12] if (workspace / QH_BY_ID[task_id]["canonical_project"]).is_file() else "NONE"

    if task_id == "QH-01":
        from PIL import Image
        out_j = Path(tempfile.mktemp(suffix=".json"))
        reren = Path(tempfile.mktemp(suffix=".png"))
        bl_chk = textwrap.dedent(f'''
            import bpy, json
            bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'hero_device.blend'}")
            sp = bpy.data.objects["SpeakerShell"]; cam = bpy.data.objects["MainCam"]
            col = list(bpy.data.materials["ShellMat"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)[:3]
            sc = bpy.context.scene; sc.render.filepath = r"{reren}"; bpy.ops.render.render(write_still=True)
            open(r"{out_j}", "w").write(json.dumps({{"hz": float(sp.dimensions.z), "lens": float(cam.data.lens), "col": col}}))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(bl_chk); tp = Path(tf.name)
        try:
            run_cmd(["blender", "-b", "--python", str(tp)])
            bi = json.loads(out_j.read_text())
            h_diff = mean_rgb_diff(workspace / "exports/hero_render.png", reren)
        finally:
            tp.unlink(missing_ok=True); out_j.unlink(missing_ok=True); reren.unlink(missing_ok=True)
        banner_ok = False
        if (workspace / "exports/banner_flat.png").is_file():
            with Image.open(workspace / "exports/banner_flat.png") as im:
                px = im.convert("RGB").getpixel((320, 180))
                banner_ok = abs(px[0] - 20) <= 18 and abs(px[1] - 150) <= 18 and abs(px[2] - 168) <= 18
        svg_txt = (workspace / "spec_badges.svg").read_text(encoding="utf-8", errors="replace")
        ods_v = read_simple_ods(workspace / "launch_pricing.ods")
        try:
            margin_v = float(ods_v.get("net_margin_usd", 0.0))
        except ValueError:
            margin_v = 0.0
        checks = {
            "B": abs(bi["hz"] - 1.50) <= 0.03 and abs(bi["lens"] - 55.0) <= 0.5 and abs(bi["col"][1] - 150/255) <= 0.08 and "1.5" in sub_val["B"],
            "C": banner_ok and "LAUNCH-26" in svg_txt and 'stroke-width="3' in svg_txt and (workspace / "exports/badges_300dpi.png").is_file() and "LAUNCH-26" in sub_val["C"],
            "D": ods_v.get("sku") == "AX-900" and abs(margin_v - 90.0) <= 0.5 and (workspace / "exports/pricing_sheet.pdf").is_file() and "AX-900" in sub_val["D"] and "90" in sub_val["D"],
            "A": h_diff <= 6.0 and (workspace / "exports/press_kit_card.png").is_file() and sub_val["A"].startswith(canon_sha12) and "1.50" in sub_val["A"],
        }
        diag = {"blend_info": bi, "hero_rerender_diff": round(h_diff, 3), "banner_teal_ok": banner_ok, "margin_usd": margin_v, "canon_sha12": canon_sha12, "ui_submissions": sub_val}

    elif task_id == "QH-02":
        conn = sqlite3.connect(str(workspace / "data/grid.gpkg"))
        f_rows = dict(conn.execute("SELECT feeder_id, status FROM feeders").fetchall())
        f_mw = dict(conn.execute("SELECT feeder_id, mw_flow FROM feeders").fetchall())
        s_rows = {sid: ( float(dem), float(tb), float(nh) ) for sid, dem, tb, nh in conn.execute("SELECT sub_id, demand_mw, tie_bonus_mw, net_headroom_mw FROM substations")}
        conn.close()
        tripped_set = {k for k, st in f_rows.items() if st == "TRIPPED" and float(f_mw[k]) == 0.0}
        expected_trip = {"F-02", "F-06", "F-11", "F-15"}
        exp_head = {}
        for idx in range(1, 9):
            sid = f"SUB-{idx:02d}"
            f1, f2 = f"F-{2*idx-1:02d}", f"F-{2*idx:02d}"
            inflow = (0.0 if f_rows.get(f1) == "TRIPPED" else float(f_mw.get(f1, 20.0))) + (0.0 if f_rows.get(f2) == "TRIPPED" else float(f_mw.get(f2, 20.0)))
            dem, tb, _ = s_rows[sid]
            exp_head[sid] = inflow + tb - dem
        head_match = all(abs(s_rows[sid][2] - exp_head[sid]) <= 0.2 for sid in exp_head)
        exp_def = sum(1 for v in exp_head.values() if v < 0.0)
        with ZipFile(workspace / "switching_order.odt") as zodt:
            odt_txt = "".join(ElementTree.fromstring(zodt.read("content.xml")).itertext())
        ods_v = read_simple_ods(workspace / "dispatch_tariff.ods")
        try:
            res_cost = float(ods_v.get("reserve_cost_usd", 0.0))
        except ValueError:
            res_cost = 0.0
        checks = {
            "B": tripped_set == expected_trip and (workspace / "exports/isolation_map.pdf").is_file() and all(x in sub_val["B"] for x in ("F-02", "F-15")),
            "C": abs(s_rows["SUB-04"][1] - 18.0) <= 0.2 and (workspace / "exports/reroute_topology.svg").is_file() and "TIE-NORTH-7" in sub_val["C"],
            "D": abs(res_cost - 43200.0) <= 1.0 and (workspace / "exports/tariff_schedule.pdf").is_file() and "43200" in sub_val["D"],
            "A": head_match and f"DEFICIT_SUBS={exp_def}" in odt_txt and (workspace / "exports/headroom_atlas.pdf").is_file() and sub_val["A"].startswith(canon_sha12) and f"DEFICIT_SUBS={exp_def}" in sub_val["A"],
        }
        diag = {"tripped": sorted(tripped_set), "sub04_tie_mw": s_rows["SUB-04"][1], "head_match": head_match, "expected_deficit": exp_def, "reserve_cost": res_cost, "canon_sha12": canon_sha12, "ui_submissions": sub_val}

    elif task_id == "QH-03":
        out_j = Path(tempfile.mktemp(suffix=".json"))
        fc_chk = textwrap.dedent(f'''
            import sys, json, math
            for c in ('/usr/lib/freecad-python3/lib', '/usr/lib/freecad/lib'):
                if c not in sys.path: sys.path.append(c)
            import FreeCAD, Part
            doc = FreeCAD.openDocument(r"{workspace / 'workcell_assy.FCStd'}")
            sh = doc.getObject("MasterSpec")
            bore = float(sh.get("B1")); bolt_r = float(sh.get("B2")); sz = float(sh.get("B3"))
            bp = doc.getObject("BasePlate").Shape; mm = doc.getObject("MotorMount").Shape; sb = doc.getObject("SensorBridge").Shape
            inter = float(bp.common(mm).Volume)
            pin_hit = 0.0
            for k in range(6):
                ang = k * math.pi / 3.0
                pin = Part.makeCylinder(3.4, 40.0, FreeCAD.Vector(bolt_r*math.cos(ang), bolt_r*math.sin(ang), 0.0))
                pin_hit += float(pin.common(bp).Volume) + float(pin.common(mm).Volume)
            open(r"{out_j}", "w").write(json.dumps({{"bore": bore, "bolt_r": bolt_r, "sz": sz, "inter": inter, "pin_hit": pin_hit, "sb_zmin": float(sb.BoundBox.ZMin), "mm_zmin": float(mm.BoundBox.ZMin)}}))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(fc_chk); tp = Path(tf.name)
        try:
            run_cmd(["python3", str(tp)])
            fi = json.loads(out_j.read_text())
        finally:
            tp.unlink(missing_ok=True); out_j.unlink(missing_ok=True)
        out_b = Path(tempfile.mktemp(suffix=".json"))
        bl_chk = textwrap.dedent(f'''
            import bpy, json
            bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'workcell_viz.blend'}")
            tb = bpy.data.objects["TwinBase"]; ts = bpy.data.objects["TwinSensor"]
            open(r"{out_b}", "w").write(json.dumps({{"dx": float(tb.dimensions.x), "sz": float(ts.location.z)}}))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(bl_chk); tp = Path(tf.name)
        try:
            run_cmd(["blender", "-b", "--python", str(tp)])
            bi = json.loads(out_b.read_text())
        finally:
            tp.unlink(missing_ok=True); out_b.unlink(missing_ok=True)
        svg_txt = (workspace / "wiring_panel.svg").read_text(encoding="utf-8", errors="replace")
        checks = {
            "B": abs(fi["bore"] - 58.0) <= 0.1 and abs(fi["bolt_r"] - 44.0) <= 0.1 and (workspace / "exports/base_plate.step").is_file() and "ECO-5844" in sub_val["B"],
            "C": fi["mm_zmin"] <= 15.0 and fi["inter"] <= 0.05 and fi["pin_hit"] <= 0.05 and abs(fi["sb_zmin"] - 72.0) <= 0.5 and (workspace / "exports/motor_mount.step").is_file() and "72" in sub_val["C"],
            "D": "#0EA5E9" in svg_txt.upper() and "SAFE-72" in svg_txt and (workspace / "exports/wiring_panel_300dpi.png").is_file() and "SAFE-72" in sub_val["D"],
            "A": abs(bi["dx"] - fi["bore"] / 100.0) <= 0.02 and abs(bi["sz"] - fi["sz"] / 100.0) <= 0.02 and (workspace / "exports/workcell_beauty.png").is_file() and sub_val["A"].startswith(canon_sha12) and f"{fi['bore']:.1f}" in sub_val["A"],
        }
        diag = {"freecad": fi, "blender": bi, "canon_sha12": canon_sha12, "ui_submissions": sub_val}

    elif task_id == "QH-04":
        from PIL import Image
        mlt_txt = (workspace / "live_show.mlt").read_text(encoding="utf-8", errors="replace")
        exp_frames = 192 if "seg2_gold.mp4" in mlt_txt else 144
        mp4 = workspace / "exports/on_air_master.mp4"
        frames_a = 0
        if mp4.is_file():
            cp = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(mp4)], capture_output=True, text=True, timeout=30)
            try:
                frames_a = int(cp.stdout.strip().splitlines()[0])
            except Exception:
                frames_a = 0
        lt_ok = False
        if (workspace / "exports/lower_third.png").is_file():
            with Image.open(workspace / "exports/lower_third.png") as im:
                px = im.convert("RGBA").getpixel((320, 320))
                lt_ok = abs(px[0] - 16) <= 18 and abs(px[1] - 185) <= 18 and abs(px[2] - 129) <= 18 and px[3] >= 200
        wav = workspace / "audio/master_audio.wav"
        lufs = -99.0
        if wav.is_file():
            eb = subprocess.run(["ffmpeg", "-nostats", "-i", str(wav), "-filter_complex", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=30)
            ms = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", eb.stderr)
            if ms:
                lufs = float(ms[-1])
        ods_v = read_simple_ods(workspace / "cue_sheet.ods")
        checks = {
            "B": "seg2_gold.mp4" in mlt_txt and 'out="95"' in mlt_txt and "192" in sub_val["B"],
            "C": lt_ok and "10B981" in sub_val["C"].upper(),
            "D": abs(lufs - (-23.0)) <= 0.6 and ods_v.get("show_code") == "SHOW-904" and (workspace / "exports/cue_sheet.pdf").is_file() and "SHOW-904" in sub_val["D"],
            "A": mp4.is_file() and abs(frames_a - exp_frames) <= 2 and sub_val["A"].startswith(canon_sha12) and str(exp_frames) in sub_val["A"],
        }
        diag = {"exp_frames": exp_frames, "frames_a": frames_a, "lower_third_ok": lt_ok, "audio_lufs": lufs, "canon_sha12": canon_sha12, "ui_submissions": sub_val}
    else:
        raise KeyError(task_id)

    return {
        "task_id": task_id,
        "role_passes": {k: bool(v and not tainted and not side_notes) for k, v in checks.items()},
        "raw_artifact_passes": checks,
        "passed_roles_count": sum(1 for v in checks.values() if v and not tainted and not side_notes),
        "joint_pass": (not tainted) and (not side_notes) and all(checks.values()),
        "diagnostics": {**diag, "buffer_tainted": tainted, "preview_aborts": (portal_state or {}).get("preview_aborts", 0), "side_notes": side_notes},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--task", required=True)
    pb.add_argument("--workspace", type=Path, required=True)
    pb.add_argument("--tickets-root", type=Path, required=True)
    pg = sub.add_parser("grade")
    pg.add_argument("--task", required=True)
    pg.add_argument("--workspace", type=Path, required=True)
    pg.add_argument("--portal-state", type=Path, required=True)
    pg.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "build":
        build_quad_bundle(args.task, args.workspace.resolve(), args.tickets_root.resolve())
        return 0
    if args.cmd == "grade":
        pstate = json.loads(args.portal_state.read_text(encoding="utf-8")) if args.portal_state.is_file() else {}
        res = grade_quad_task(args.task, args.workspace.resolve(), pstate)
        write_json(args.out.resolve(), res)
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
