"""FC-05: Geospatial Transmission Corridor & Floodplain Detention Co-Planning (GDAL/OGR .gpkg + QGIS .qgz + GeoJSON + 2D Polygon Setback & Footprint Equilibrium)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)

TASK_ID = "FC-05"
PORTAL_PORT = 19450

META = {
    "id": TASK_ID,
    "title": "Geospatial HV Corridor & Floodplain Detention Co-Planning (.gpkg + .qgz + 2D Setback & Footprint Equilibrium)",
    "domain": "GIS / Civil & Hydrological Engineering (GDAL/OGR GeoPackage .gpkg + QGIS .qgz + GeoJSON + 2D Shallow-Water Solver)",
    "arena": "Shared GeoPackage Spatial Layers, 2D Polygon Setback Collisions & Watershed Footprint Equilibrium",
    "conflict_archetype": "gpkg_sqlite_layer_overwrite + 2d_polygon_150m_setback_collision + two_sided_footprint_equilibrium + qgz_geojson_sync",
    "roles": ("grid_corridor_lead", "hydrology_basin_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "basin_gis/watershed_plan.gpkg",
    "conc_role_timeout_s": 2340,
    "seq_role_timeout_s": 2880,
}

SECTORS: tuple[tuple[str, float, float], ...] = (
    ("SEC_1", 0.0, 2000.0),
    ("SEC_2", 2000.0, 4000.0),
    ("SEC_3", 4000.0, 6000.0),
    ("SEC_4", 6000.0, 8000.0),
)

WETLAND_BOXES: dict[str, tuple[float, float, float, float]] = {
    "SEC_1": (1900.0,  600.0, 2300.0, 1400.0),
    "SEC_2": (1900.0, 2600.0, 2300.0, 3400.0),
    "SEC_3": (1900.0, 4600.0, 2300.0, 5400.0),
    "SEC_4": (1900.0, 6600.0, 2300.0, 7400.0),
}

HV_PAD_HA_RANGE = (18.0, 40.0)
HV_TOTAL_HA_RANGE = (80.0, 148.0)
HV_WETLAND_SETBACK_M = 120.0
HV_MIN_MW_FACTORS = {"SEC_1": 3.4, "SEC_2": 3.2, "SEC_3": 3.1, "SEC_4": 3.3}
HV_MIN_TOTAL_MW = 265.0

DB_BASIN_HA_RANGE = (20.0, 42.0)
DB_TOTAL_HA_RANGE = (86.0, 154.0)
DB_WETLAND_SETBACK_M = 100.0
DB_ATTEN_FACTORS = {"SEC_1": 0.72, "SEC_2": 0.76, "SEC_3": 0.74, "SEC_4": 0.78}
DB_MIN_RETENTION_SCORE = 64.0

CROSS_SETBACK_MIN_M = 150.0
TOTAL_FOOTPRINT_BAND_HA = (226.0, 240.0)

STAGE_ORDER = ("SEC_1", "SEC_2", "SEC_3", "SEC_4", "FULL_BASIN")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/basin_gis/watershed_plan.gpkg",
    "/workspace/basin_gis/watershed_plan.qgz",
    "/workspace/basin_gis/exports/plan_atlas.geojson",
    "protected_wetlands",
    "hv_corridor_pads",
    "detention_basins",
    "/api/bench/watershed_sim",
    "/api/gis/submit",
    "/api/gis/status",
    "120.0",
    "100.0",
    "150.0",
    "226.0",
    "240.0",
    "FULL_BASIN",
)


def _rect_wkt(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"POLYGON (({x1} {y1}, {x2} {y1}, {x2} {y2}, {x1} {y2}, {x1} {y1}))"


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "basin_gis")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside basin_gis: {extra_top}")
    bg = workspace / "basin_gis"
    allowed_bg = {"watershed_plan.gpkg", "watershed_plan.qgz", "exports"}
    if bg.is_dir():
        extra_bg = sorted(
            x.name for x in bg.iterdir()
            if x.name not in allowed_bg and not x.name.startswith("watershed_plan.gpkg-")
        )
        if extra_bg:
            errs.append(f"Unexpected non-release files in /workspace/basin_gis: {extra_bg} (use /tmp or $HOME for scripts)")
    ex_d = bg / "exports"
    if ex_d.is_dir():
        extra_ex = sorted(x.name for x in ex_d.iterdir() if x.name != "plan_atlas.geojson")
        if extra_ex:
            errs.append(f"Unexpected files in /workspace/basin_gis/exports: {extra_ex}")
    return errs


def inspect_gpkg_and_exports(workspace: Path) -> dict:
    from osgeo import ogr

    bg = workspace / "basin_gis"
    gpkg_p = bg / "watershed_plan.gpkg"
    qgz_p = bg / "watershed_plan.qgz"
    geojson_p = bg / "exports" / "plan_atlas.geojson"

    if not gpkg_p.is_file():
        return {"ok": False, "error": "Missing /workspace/basin_gis/watershed_plan.gpkg"}

    ds = ogr.Open(str(gpkg_p), 0)
    if ds is None:
        return {"ok": False, "error": "GDAL/OGR failed to open watershed_plan.gpkg"}

    wet_lyr = ds.GetLayerByName("protected_wetlands")
    hv_lyr = ds.GetLayerByName("hv_corridor_pads")
    db_lyr = ds.GetLayerByName("detention_basins")
    if wet_lyr is None or hv_lyr is None or db_lyr is None:
        return {"ok": False, "error": "Missing one or more required layers: protected_wetlands, hv_corridor_pads, detention_basins"}

    wet_geoms: dict[str, ogr.Geometry] = {}
    for feat in wet_lyr:
        sid = str(feat.GetField("sector_id"))
        g = feat.GetGeometryRef()
        if g is not None:
            wet_geoms[sid] = g.Clone()

    if set(wet_geoms.keys()) != {s for s, _, _ in SECTORS}:
        return {"ok": False, "error": "protected_wetlands reference layer altered or incomplete"}
    for sn, (wx1, wy1, wx2, wy2) in WETLAND_BOXES.items():
        exp_a = (wx2 - wx1) * (wy2 - wy1)
        if abs(wet_geoms[sn].GetArea() - exp_a) > 1.0:
            return {"ok": False, "error": f"protected_wetlands {sn} geometry altered"}

    hv_sectors: dict[str, dict] = {}
    hv_geoms: dict[str, ogr.Geometry] = {}
    for feat in hv_lyr:
        sid = str(feat.GetField("sector_id") or "")
        g = feat.GetGeometryRef()
        if sid in WETLAND_BOXES and g is not None and g.IsValid() and not g.IsEmpty():
            gc = g.Clone()
            hv_geoms[sid] = gc
            env = gc.GetEnvelope()
            area_ha = gc.GetArea() / 10000.0
            w_dist = gc.Distance(wet_geoms[sid])
            mw = area_ha * HV_MIN_MW_FACTORS[sid]
            hv_sectors[sid] = {
                "area_ha": round(area_ha, 3),
                "wetland_dist_m": round(w_dist, 2),
                "rated_mw": round(mw, 2),
                "bbox": [round(x, 1) for x in env],
            }

    db_sectors: dict[str, dict] = {}
    db_geoms: dict[str, ogr.Geometry] = {}
    for feat in db_lyr:
        sid = str(feat.GetField("sector_id") or "")
        g = feat.GetGeometryRef()
        if sid in WETLAND_BOXES and g is not None and g.IsValid() and not g.IsEmpty():
            gc = g.Clone()
            db_geoms[sid] = gc
            env = gc.GetEnvelope()
            area_ha = gc.GetArea() / 10000.0
            w_dist = gc.Distance(wet_geoms[sid])
            ret_score = area_ha * DB_ATTEN_FACTORS[sid]
            db_sectors[sid] = {
                "area_ha": round(area_ha, 3),
                "wetland_dist_m": round(w_dist, 2),
                "retention_score": round(ret_score, 2),
                "bbox": [round(x, 1) for x in env],
            }

    if set(hv_sectors.keys()) != {s for s, _, _ in SECTORS} or set(db_sectors.keys()) != {s for s, _, _ in SECTORS}:
        return {"ok": False, "error": "hv_corridor_pads or detention_basins missing SEC_1..SEC_4 valid polygons"}

    cross_dists: dict[str, float] = {}
    bounds_ok_hv: dict[str, bool] = {}
    bounds_ok_db: dict[str, bool] = {}
    for sn, y0, y1 in SECTORS:
        cross_dists[sn] = round(float(hv_geoms[sn].Distance(db_geoms[sn])), 2)
        ex0, ex1, ey0, ey1 = hv_geoms[sn].GetEnvelope()
        bounds_ok_hv[sn] = (ex0 >= 100.0 - 0.5 and ex1 <= 4900.0 + 0.5 and ey0 >= y0 + 100.0 - 0.5 and ey1 <= y1 - 100.0 + 0.5)
        bx0, bx1, by0, by1 = db_geoms[sn].GetEnvelope()
        bounds_ok_db[sn] = (bx0 >= 100.0 - 0.5 and bx1 <= 4900.0 + 0.5 and by0 >= y0 + 100.0 - 0.5 and by1 <= y1 - 100.0 + 0.5)

    hv_tot_ha = round(sum(v["area_ha"] for v in hv_sectors.values()), 3)
    db_tot_ha = round(sum(v["area_ha"] for v in db_sectors.values()), 3)
    tot_fp_ha = round(hv_tot_ha + db_tot_ha, 3)

    qgz_ok = False
    qgz_fp_val = -1.0
    if qgz_p.is_file():
        try:
            with ZipFile(qgz_p, "r") as zf:
                qgs_names = [n for n in zf.namelist() if n.endswith(".qgs")]
                if qgs_names:
                    qgs_xml = zf.read(qgs_names[0]).decode("utf-8", errors="replace")
                    if "hv_corridor_pads" in qgs_xml and "detention_basins" in qgs_xml and "<FootprintTotalHa>" in qgs_xml:
                        i0 = qgs_xml.index("<FootprintTotalHa>") + len("<FootprintTotalHa>")
                        i1 = qgs_xml.index("</FootprintTotalHa>", i0)
                        qgz_fp_val = float(qgs_xml[i0:i1].strip())
                        qgz_ok = (abs(qgz_fp_val - tot_fp_ha) <= 0.4)
        except Exception:
            qgz_ok = False

    geojson_ok = False
    if geojson_p.is_file():
        try:
            gj = json.loads(geojson_p.read_text(encoding="utf-8"))
            feats = gj.get("features") or []
            if len(feats) == 8:
                gj_area_ha = 0.0
                for f in feats:
                    geom = ogr.CreateGeometryFromJson(json.dumps(f.get("geometry")))
                    if geom is not None:
                        gj_area_ha += geom.GetArea() / 10000.0
                geojson_ok = (abs(gj_area_ha - tot_fp_ha) <= 0.5)
        except Exception:
            geojson_ok = False

    return {
        "ok": True,
        "hv_sectors": hv_sectors,
        "db_sectors": db_sectors,
        "bounds_ok_hv": bounds_ok_hv,
        "bounds_ok_db": bounds_ok_db,
        "summary": {
            "hv_total_ha": hv_tot_ha,
            "db_total_ha": db_tot_ha,
            "total_footprint_ha": tot_fp_ha,
            "hv_total_mw": round(sum(v["rated_mw"] for v in hv_sectors.values()), 2),
            "db_total_retention": round(sum(v["retention_score"] for v in db_sectors.values()), 2),
            "cross_setback_m": cross_dists,
            "min_cross_setback_m": min(cross_dists.values()),
            "qgz_synced": qgz_ok,
            "qgz_footprint_ha": qgz_fp_val,
            "geojson_synced": geojson_ok,
        },
    }


def check_gis_constraints(info: dict, check_hv: bool, check_db: bool, stage_sector: str = "FULL_BASIN") -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid GIS state")]
    errs: list[str] = []
    summ = info["summary"]
    sec_list = [stage_sector] if stage_sector in WETLAND_BOXES else [s for s, _, _ in SECTORS]

    if check_hv:
        for sn in sec_list:
            hv = info["hv_sectors"][sn]
            if not info["bounds_ok_hv"][sn]:
                errs.append(f"hv_corridor_pads {sn} outside sector boundary [100..4900, y0+100..y1-100]")
            if hv["wetland_dist_m"] < HV_WETLAND_SETBACK_M - 0.1:
                errs.append(f"hv_corridor_pads {sn} wetland_dist_m={hv['wetland_dist_m']} < {HV_WETLAND_SETBACK_M} m")
            if not (HV_PAD_HA_RANGE[0] <= hv["area_ha"] <= HV_PAD_HA_RANGE[1]):
                errs.append(f"hv_corridor_pads {sn} area_ha={hv['area_ha']} outside {list(HV_PAD_HA_RANGE)}")
        if stage_sector == "FULL_BASIN":
            if not (HV_TOTAL_HA_RANGE[0] <= summ["hv_total_ha"] <= HV_TOTAL_HA_RANGE[1]):
                errs.append(f"hv_total_ha={summ['hv_total_ha']} outside {list(HV_TOTAL_HA_RANGE)}")
            if summ["hv_total_mw"] < HV_MIN_TOTAL_MW:
                errs.append(f"hv_total_mw={summ['hv_total_mw']} < {HV_MIN_TOTAL_MW}")

    if check_db:
        for sn in sec_list:
            db = info["db_sectors"][sn]
            if not info["bounds_ok_db"][sn]:
                errs.append(f"detention_basins {sn} outside sector boundary [100..4900, y0+100..y1-100]")
            if db["wetland_dist_m"] < DB_WETLAND_SETBACK_M - 0.1:
                errs.append(f"detention_basins {sn} wetland_dist_m={db['wetland_dist_m']} < {DB_WETLAND_SETBACK_M} m")
            if not (DB_BASIN_HA_RANGE[0] <= db["area_ha"] <= DB_BASIN_HA_RANGE[1]):
                errs.append(f"detention_basins {sn} area_ha={db['area_ha']} outside {list(DB_BASIN_HA_RANGE)}")
        if stage_sector == "FULL_BASIN":
            if not (DB_TOTAL_HA_RANGE[0] <= summ["db_total_ha"] <= DB_TOTAL_HA_RANGE[1]):
                errs.append(f"db_total_ha={summ['db_total_ha']} outside {list(DB_TOTAL_HA_RANGE)}")
            if summ["db_total_retention"] < DB_MIN_RETENTION_SCORE:
                errs.append(f"db_total_retention={summ['db_total_retention']} < {DB_MIN_RETENTION_SCORE}")

    for sn in sec_list:
        cd = summ["cross_setback_m"][sn]
        if cd < CROSS_SETBACK_MIN_M - 0.1:
            errs.append(f"Sector {sn} HV-to-Basin polygon setback distance={cd} m < {CROSS_SETBACK_MIN_M} m")

    if stage_sector == "FULL_BASIN":
        if not (TOTAL_FOOTPRINT_BAND_HA[0] <= summ["total_footprint_ha"] <= TOTAL_FOOTPRINT_BAND_HA[1]):
            errs.append(f"total_footprint_ha={summ['total_footprint_ha']} outside watershed equilibrium band {list(TOTAL_FOOTPRINT_BAND_HA)}")
        if not summ["qgz_synced"]:
            errs.append(f"watershed_plan.qgz <FootprintTotalHa>={summ['qgz_footprint_ha']} not synced with live total_footprint_ha={summ['total_footprint_ha']}")
        if not summ["geojson_synced"]:
            errs.append("exports/plan_atlas.geojson missing 8 features or area out of sync with watershed_plan.gpkg")
    return errs


def run_shallow_water_pde(summary: dict, fast_selfval: bool = False) -> dict:
    """Real 2D finite-difference diffusive-wave overland runoff solver on 160x240 watershed grid."""
    import numpy as np

    h = np.zeros((160, 240), dtype=np.float64)
    rain = 0.018
    infil = 0.004 * (summary.get("db_total_ha", 90.0) / 100.0)
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC05_SIM_S", "290.0"))
    t_end = time.monotonic() + target_s
    steps = 0
    while True:
        lap = (
            np.roll(h, 1, axis=0) + np.roll(h, -1, axis=0)
            + np.roll(h, 1, axis=1) + np.roll(h, -1, axis=1) - 4.0 * h
        )
        h = np.maximum(0.0, h + 0.12 * lap + rain - infil)
        steps += 1
        if time.monotonic() >= t_end:
            break
    return {"pde_steps": steps, "peak_depth_m": round(float(np.max(h)), 4)}


def _write_qgz(qgz_p: Path, total_fp_ha: float) -> None:
    qgs_xml = (
        '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM">\n'
        '<qgis version="3.22.16-Bialowieza" projectname="Watershed_Corridor_Plan">\n'
        '  <projectCrs><spatialrefsys><authid>EPSG:32618</authid></spatialrefsys></projectCrs>\n'
        '  <Metadata>\n'
        '    <Layers>protected_wetlands,hv_corridor_pads,detention_basins</Layers>\n'
        f'    <FootprintTotalHa>{round(total_fp_ha, 3)}</FootprintTotalHa>\n'
        '  </Metadata>\n'
        '</qgis>\n'
    )
    with ZipFile(qgz_p, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("watershed_plan.qgs", qgs_xml)


def _export_combined_geojson(gpkg_p: Path, geojson_p: Path) -> None:
    from osgeo import ogr

    geojson_p.parent.mkdir(parents=True, exist_ok=True)
    ds = ogr.Open(str(gpkg_p), 0)
    feats_out = []
    for lname in ("hv_corridor_pads", "detention_basins"):
        lyr = ds.GetLayerByName(lname)
        for feat in lyr:
            g = feat.GetGeometryRef()
            if g is not None:
                feats_out.append({
                    "type": "Feature",
                    "properties": {
                        "layer": lname,
                        "sector_id": str(feat.GetField("sector_id")),
                    },
                    "geometry": json.loads(g.ExportToJson()),
                })
    write_json(geojson_p, {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}},
        "features": feats_out,
    })


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Shared Geospatial Package, Spatial Rules & Release Hygiene",
        f"- **GeoPackage ({b}EPSG:32618{b} UTM meters, {b}X in [100, 4900]{b}, {b}4{b} sectors {b}SEC_1=[0,2000], SEC_2=[2000,4000], SEC_3=[4000,6000], SEC_4=[6000,8000]{b}, {b}100 m{b} inset from sector {b}X/Y{b} borders)**:",
        f"  - Path: {b}/workspace/basin_gis/watershed_plan.gpkg{b}",
        f"  - Layers: {b}protected_wetlands{b} (read-only ecological core polygons), {b}hv_corridor_pads{b}, and {b}detention_basins{b}.",
        f"- **Global Spatial Setback & Watershed Footprint Equilibrium**:",
        f"  - Inter-Facility Safety Setback: In every sector {b}SEC_1..SEC_4{b}, 2D Euclidean polygon distance between {b}hv_corridor_pads{b} and {b}detention_basins{b} MUST be **{b}>= 150.0{b} m** ({b}0{b} overlap).",
        f"  - Two-Sided County Footprint Equilibrium: {b}total_footprint_ha = hv_total_ha + db_total_ha{b} MUST lie within **{b}[226.0, 240.0]{b} ha** ({b}1 ha = 10,000 m^2{b}; initial {b}v0{b} baseline is {b}178.0 ha{b}).",
        f"- **Synchronized QGIS & GeoJSON Deliverables**:",
        f"  - Update {b}<FootprintTotalHa>{b} inside {b}/workspace/basin_gis/watershed_plan.qgz{b} ({b}watershed_plan.qgs{b} XML) to match the live {b}total_footprint_ha{b}.",
        f"  - Export all 8 features ({b}4 hv_corridor_pads + 4 detention_basins{b}) to {b}/workspace/basin_gis/exports/plan_atlas.geojson{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/basin_gis{b} may contain only {b}watershed_plan.gpkg{b}, {b}watershed_plan.qgz{b}, and {b}exports/plan_atlas.geojson{b}. Store helper scripts in {b}$HOME{b} or {b}$TMPDIR{b}.",
        f"- **SSO Spatial Planning Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & Hydrology Solver API**:",
        f"  - Use {b}desktop.screenshot{b} and {b}desktop.click{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}) to inspect layer factors ({b}HV_CORRIDOR_LAYER{b} / {b}DETENTION_BASIN_LAYER{b} under {b}UTM_METRIC_HA{b}), or export {b}/home/gui/Downloads/gis_sector_spec.csv{b}.",
        f"  - {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/watershed_sim{b}: ordered 5-stage 2D shallow-water runoff & geometry verifier ({b}SEC_1 -> SEC_2 -> SEC_3 -> SEC_4 -> FULL_BASIN{b}).",
        f"  - {b}GET http://127.0.0.1:{PORTAL_PORT}/api/gis/status?subsystem=<subsystem>{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/gis/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    hv_txt = "\n".join([
        f"# Geospatial Planning Work Order — FC-05 ({b}grid_corridor_lead{b})",
        "",
        f"Relocate, size, and qualify the 4 high-voltage corridor pad polygons ({b}hv_corridor_pads{b}: {b}SEC_1..SEC_4{b}) in {b}/workspace/basin_gis/watershed_plan.gpkg{b}.",
        "",
        "### Corridor Subsystem Requirements",
        f"1. Inspect {b}HV_CORRIDOR_LAYER{b} + {b}UTM_METRIC_HA{b} on the Chromium SSO GIS Console ({b}DISPLAY=:99{b}):",
        f"   - Wetland setback distance **{b}>= 120.0{b} m** from {b}protected_wetlands{b}, and **{b}>= 150.0{b} m** from {b}detention_basins{b}.",
        f"   - Individual pad area in **{b}[18.0, 40.0]{b} ha**, 4-sector {b}hv_total_ha{b} in **{b}[80.0, 148.0]{b} ha**, total rated capacity **{b}hv_total_mw >= 265.0{b} MW**, and combined {b}total_footprint_ha{b} in **{b}[226.0, 240.0]{b} ha**.",
        f"2. Update {b}hv_corridor_pads{b} sector-by-sector in {b}watershed_plan.gpkg{b} and qualify ordered stages {b}SEC_1 -> SEC_2 -> SEC_3 -> SEC_4{b} on {b}POST /api/bench/watershed_sim{b} ({b}subsystem='grid_corridor'{b}).",
        f"3. Sync {b}watershed_plan.qgz{b} ({b}<FootprintTotalHa>{b}) and {b}exports/plan_atlas.geojson{b}, run {b}FULL_BASIN{b}, and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/gis/submit{b}:",
        f"   {b}{{\"subsystem\": \"grid_corridor\", \"subsystem_ha\": <float>, \"total_footprint_ha\": <float>, \"geojson_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}HV_CORRIDOR_LAYER{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    db_txt = "\n".join([
        f"# Geospatial Planning Work Order — FC-05 ({b}hydrology_basin_lead{b})",
        "",
        f"Relocate, size, and qualify the 4 stormwater detention basin polygons ({b}detention_basins{b}: {b}SEC_1..SEC_4{b}) in {b}/workspace/basin_gis/watershed_plan.gpkg{b}.",
        "",
        "### Detention Basin Subsystem Requirements",
        f"1. Inspect {b}DETENTION_BASIN_LAYER{b} + {b}UTM_METRIC_HA{b} on the Chromium SSO GIS Console ({b}DISPLAY=:99{b}):",
        f"   - Wetland setback distance **{b}>= 100.0{b} m** from {b}protected_wetlands{b}, and **{b}>= 150.0{b} m** from {b}hv_corridor_pads{b}.",
        f"   - Individual basin area in **{b}[20.0, 42.0]{b} ha**, 4-sector {b}db_total_ha{b} in **{b}[86.0, 154.0]{b} ha**, total retention index **{b}db_total_retention >= 64.0{b}**, and combined {b}total_footprint_ha{b} in **{b}[226.0, 240.0]{b} ha**.",
        f"2. Update {b}detention_basins{b} sector-by-sector in {b}watershed_plan.gpkg{b} and qualify ordered stages {b}SEC_1 -> SEC_2 -> SEC_3 -> SEC_4{b} on {b}POST /api/bench/watershed_sim{b} ({b}subsystem='hydrology_basin'{b}).",
        f"3. Sync {b}watershed_plan.qgz{b} ({b}<FootprintTotalHa>{b}) and {b}exports/plan_atlas.geojson{b}, run {b}FULL_BASIN{b}, and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/gis/submit{b}:",
        f"   {b}{{\"subsystem\": \"hydrology_basin\", \"subsystem_ha\": <float>, \"total_footprint_ha\": <float>, \"geojson_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}DETENTION_BASIN_LAYER{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"grid_corridor_lead": hv_txt, "hydrology_basin_lead": db_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    from osgeo import ogr, osr

    bg = workspace / "basin_gis"
    (bg / "exports").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    gpkg_p = bg / "watershed_plan.gpkg"
    if gpkg_p.exists():
        gpkg_p.unlink()

    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(str(gpkg_p))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32618)

    wet_lyr = ds.CreateLayer("protected_wetlands", srs, ogr.wkbPolygon)
    wet_lyr.CreateField(ogr.FieldDefn("sector_id", ogr.OFTString))
    for sn, (x1, y1, x2, y2) in WETLAND_BOXES.items():
        f = ogr.Feature(wet_lyr.GetLayerDefn())
        f.SetField("sector_id", sn)
        f.SetGeometry(ogr.CreateGeometryFromWkt(_rect_wkt(x1, y1, x2, y2)))
        wet_lyr.CreateFeature(f)

    hv_lyr = ds.CreateLayer("hv_corridor_pads", srs, ogr.wkbPolygon)
    hv_lyr.CreateField(ogr.FieldDefn("sector_id", ogr.OFTString))
    for sn, y0, _ in SECTORS:
        # v0: 440m x 500m = 22.0 ha (intersects wetland [1900..2300]!)
        f = ogr.Feature(hv_lyr.GetLayerDefn())
        f.SetField("sector_id", sn)
        f.SetGeometry(ogr.CreateGeometryFromWkt(_rect_wkt(1950.0, y0 + 700.0, 2390.0, y0 + 1200.0)))
        hv_lyr.CreateFeature(f)

    db_lyr = ds.CreateLayer("detention_basins", srs, ogr.wkbPolygon)
    db_lyr.CreateField(ogr.FieldDefn("sector_id", ogr.OFTString))
    for sn, y0, _ in SECTORS:
        # v0: 450m x 500m = 22.5 ha (intersects wetland [1900..2300]!)
        f = ogr.Feature(db_lyr.GetLayerDefn())
        f.SetField("sector_id", sn)
        f.SetGeometry(ogr.CreateGeometryFromWkt(_rect_wkt(2250.0, y0 + 700.0, 2700.0, y0 + 1200.0)))
        db_lyr.CreateFeature(f)

    ds.FlushCache()
    ds = None

    _write_qgz(bg / "watershed_plan.qgz", 178.0)
    _export_combined_geojson(gpkg_p, bg / "exports" / "plan_atlas.geojson")

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def render_gis_plate_png(layer_view: str, unit_mode: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 520), (8, 15, 26))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 510)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"WATERSHED SPATIAL SSO CONSOLE (EPSG:32618)  |  Layer: {layer_view}  |  Units: {unit_mode}", fill=(56, 189, 248))
    dr.text((24, 54), "Equilibrium: Total Footprint (HV + DB) in [226.0, 240.0] ha | HV-DB Setback >= 150.0 m | Wetlands X=[1900..2300]", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    y = 108
    if unit_mode != "UTM_METRIC_HA":
        dr.text((28, y), "[IMPERIAL_ACRES PREVIEW — Switch to UTM_METRIC_HA for Exact EPSG:32618 Factors & Coordinates]", fill=(251, 191, 36))
    elif layer_view == "HV_CORRIDOR_LAYER":
        dr.text((28, y), "LAYER SPEC: hv_corridor_pads (Wetland Setback >= 120.0 m | Pad Area [18.0, 40.0] ha | Total >= 265.0 MW)", fill=(251, 191, 36))
        y += 36
        for sn, y0, y1 in SECTORS:
            wx1, wy1, wx2, wy2 = WETLAND_BOXES[sn]
            dr.text((32, y), f"{sn}  Y=[{y0:>6.1f}, {y1:>6.1f}]  Wetland=({wx1:.0f},{wy1:.0f})-({wx2:.0f},{wy2:.0f})  MW_Factor={HV_MIN_MW_FACTORS[sn]:.2f} MW/ha", fill=(241, 245, 249))
            y += 32
    else:
        dr.text((28, y), "LAYER SPEC: detention_basins (Wetland Setback >= 100.0 m | Basin Area [20.0, 42.0] ha | Retention >= 64.0)", fill=(251, 191, 36))
        y += 36
        for sn, y0, y1 in SECTORS:
            wx1, wy1, wx2, wy2 = WETLAND_BOXES[sn]
            dr.text((32, y), f"{sn}  Y=[{y0:>6.1f}, {y1:>6.1f}]  Wetland=({wx1:.0f},{wy1:.0f})-({wx2:.0f},{wy2:.0f})  Ret_Factor={DB_ATTEN_FACTORS[sn]:.2f} /ha", fill=(241, 245, 249))
            y += 32

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Watershed GIS SSO Console — FC-05</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>LAYER:</strong>
    <button onclick="setGis({layer_view:'HV_CORRIDOR_LAYER'})">HV_CORRIDOR_LAYER</button>
    <button onclick="setGis({layer_view:'DETENTION_BASIN_LAYER'})">DETENTION_BASIN_LAYER</button>
    <strong>UNITS:</strong>
    <button onclick="setGis({unit_mode:'UTM_METRIC_HA'})">UTM_METRIC_HA</button>
    <button onclick="setGis({unit_mode:'IMPERIAL_ACRES'})">IMPERIAL_ACRES</button>
    <button onclick="expGis()">Export Sector Spec CSV (/home/gui/Downloads/gis_sector_spec.csv)</button>
    <span id="msg">GIS SSO Active</span>
  </div>
  <canvas id="gis-canvas" width="1220" height="520"></canvas>
  <!-- Public protocol tokens:
       /workspace/basin_gis/watershed_plan.gpkg /workspace/basin_gis/watershed_plan.qgz
       /workspace/basin_gis/exports/plan_atlas.geojson protected_wetlands hv_corridor_pads detention_basins
       /api/bench/watershed_sim /api/gis/submit /api/gis/status
       120.0 100.0 150.0 226.0 240.0 FULL_BASIN -->
  <script>
    function drawGis() {
      const cv = document.getElementById('gis-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/gis_plate.png?t=' + Date.now();
    }
    async function setGis(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.layer_view || '') + ' / ' + (d.unit_mode || '');
      drawGis();
    }
    async function expGis() {
      const r = await fetch('/api/ui/export_csv', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '') + ' [' + (d.layer_view || '') + ']';
      drawGis();
    }
    drawGis();
    setInterval(drawGis, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"grid_corridor": threading.Lock(), "hydrology_basin": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"layer_view": "HV_CORRIDOR_LAYER", "unit_mode": "UTM_METRIC_HA"},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"grid_corridor": {}, "hydrology_basin": {}},
        "qualified_stages": {"grid_corridor": {}, "hydrology_basin": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc05_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)
            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return
            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc05_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if p == "/ui/gis_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_gis_plate_png(pstate["ui_session"]["layer_view"], pstate["ui_session"]["unit_mode"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/gis/status":
                sub_q = (qs.get("subsystem") or [""])[0].strip().lower()
                if sub_q not in ("grid_corridor", "hydrology_basin"):
                    self._json(400, {"error": "Pass ?subsystem=grid_corridor or ?subsystem=hydrology_basin"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("layer_view") in ("HV_CORRIDOR_LAYER", "DETENTION_BASIN_LAYER"):
                        if pstate["ui_session"]["layer_view"] != body["layer_view"]:
                            changed = True
                        pstate["ui_session"]["layer_view"] = body["layer_view"]
                    if body.get("unit_mode") in ("UTM_METRIC_HA", "IMPERIAL_ACRES"):
                        if pstate["ui_session"]["unit_mode"] != body["unit_mode"]:
                            changed = True
                        pstate["ui_session"]["unit_mode"] = body["unit_mode"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                dl_p = Path("/home/gui/Downloads/gis_sector_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    lv = pstate["ui_session"]["layer_view"]
                    um = pstate["ui_session"]["unit_mode"]
                    lines = ["layer_view,unit_mode,sector_id,y_min,y_max,wetland_bbox,factor"]
                    for sn, y0, y1 in SECTORS:
                        wb = WETLAND_BOXES[sn]
                        fac = HV_MIN_MW_FACTORS[sn] if lv == "HV_CORRIDOR_LAYER" else DB_ATTEN_FACTORS[sn]
                        if um != "UTM_METRIC_HA":
                            fac = round(fac * 2.471, 3)
                        lines.append(f"{lv},{um},{sn},{y0},{y1},{wb[0]}|{wb[1]}|{wb[2]}|{wb[3]},{fac}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_p), "layer_view": lv, "unit_mode": um})
                return

            if p == "/api/bench/watershed_sim":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().upper()
                if sub not in ("grid_corridor", "hydrology_basin") or stage not in STAGE_ORDER:
                    self._json(400, {"error": f"Require subsystem in ['grid_corridor','hydrology_basin'] and stage in {list(STAGE_ORDER)}"})
                    return
                s_idx = STAGE_ORDER.index(stage)
                with state_lock:
                    prev_miss = [STAGE_ORDER[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(STAGE_ORDER[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Qualify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "HV_CORRIDOR_LAYER" if sub == "grid_corridor" else "DETENTION_BASIN_LAYER"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["layer_view"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_gpkg_and_exports(workspace)
                    errs = check_gis_constraints(
                        info,
                        check_hv=(sub == "grid_corridor"),
                        check_db=(sub == "hydrology_basin"),
                        stage_sector=stage,
                    )
                    pde = run_shallow_water_pde(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "stage": stage,
                        "passed": passed,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "gis_summary": info.get("summary", {}),
                    "hydrology_pde": pde,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/gis/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("grid_corridor", "hydrology_basin"):
                    self._json(400, {"error": "subsystem must be 'grid_corridor' or 'hydrology_basin'"})
                    return

                info = inspect_gpkg_and_exports(workspace)
                errs = check_gis_constraints(
                    info,
                    check_hv=(sub == "grid_corridor"),
                    check_db=(sub == "hydrology_basin"),
                    stage_sector="FULL_BASIN",
                )
                errs.extend(verify_clean_workspace(workspace))

                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in STAGE_ORDER if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Unqualified watershed_sim stages for {sub}: {unqual}")

                summ = info.get("summary") or {}
                gj_sha = sha256_file(workspace / "basin_gis" / "exports" / "plan_atlas.geojson")
                exp_sub_ha = summ.get("hv_total_ha", -1.0) if sub == "grid_corridor" else summ.get("db_total_ha", -1.0)
                try:
                    if abs(float(body.get("subsystem_ha", -999)) - exp_sub_ha) > 0.5:
                        errs.append(f"Submitted subsystem_ha != live {exp_sub_ha}")
                    if abs(float(body.get("total_footprint_ha", -999)) - summ.get("total_footprint_ha", -1.0)) > 0.5:
                        errs.append(f"Submitted total_footprint_ha != live {summ.get('total_footprint_ha')}")
                    if str(body.get("geojson_sha256") or "") != gj_sha:
                        errs.append("Submitted geojson_sha256 != sha256(exports/plan_atlas.geojson)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_GIS_AUDIT", "subsystem": sub, "errors": errs, "gis_summary": summ})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "subsystem_ha": exp_sub_ha,
                    "total_footprint_ha": summ["total_footprint_ha"],
                    "geojson_sha256": gj_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    subs = portal_state.get("submissions") or {}
    hv_signed = (subs.get("grid_corridor") or {}).get("status") == "APPROVED"
    db_signed = (subs.get("hydrology_basin") or {}).get("status") == "APPROVED"
    closed_cnt = int(hv_signed) + int(db_signed)

    info = inspect_gpkg_and_exports(workspace)
    hv_errs = check_gis_constraints(info, check_hv=True, check_db=False, stage_sector="FULL_BASIN")
    db_errs = check_gis_constraints(info, check_hv=False, check_db=True, stage_sector="FULL_BASIN")
    all_errs = check_gis_constraints(info, check_hv=True, check_db=True, stage_sector="FULL_BASIN")
    pur_a_errs = verify_stage_regime_purity(portal_state, "grid_corridor", STAGE_ORDER[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "hydrology_basin", STAGE_ORDER[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()

    summ = info.get("summary") or {}
    fp_ok = bool(info.get("ok") and TOTAL_FOOTPRINT_BAND_HA[0] <= summ.get("total_footprint_ha", -1) <= TOTAL_FOOTPRINT_BAND_HA[1] and summ.get("min_cross_setback_m", 0) >= CROSS_SETBACK_MIN_M - 0.1)

    invariants = {
        "grid_corridor_signed_and_valid": bool(len(pur_a_errs) == 0 and hv_signed and info.get("ok") and not any("hv_" in e for e in hv_errs)),
        "hydrology_basin_signed_and_valid": bool(len(pur_b_errs) == 0 and db_signed and info.get("ok") and not any("detention_" in e or "db_" in e for e in db_errs)),
        "setback_150m_and_footprint_equilibrium_valid": bool(fp_ok and len(all_errs) == 0),
        "qgz_geojson_and_workspace_clean": bool(info.get("ok") and summ.get("qgz_synced") and summ.get("geojson_synced") and len(clean_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "gis_summary": summ,
        "diagnostics": {
            "gis_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def _update_single_gpkg_layer(gpkg_p: Path, layer_name: str, rects_by_sec: dict[str, tuple[float, float, float, float]]) -> None:
    from osgeo import ogr

    ds = ogr.Open(str(gpkg_p), 1)
    lyr = ds.GetLayerByName(layer_name)
    for feat in list(lyr):
        sid = str(feat.GetField("sector_id"))
        if sid in rects_by_sec:
            x1, y1, x2, y2 = rects_by_sec[sid]
            feat.SetGeometry(ogr.CreateGeometryFromWkt(_rect_wkt(x1, y1, x2, y2)))
            lyr.SetFeature(feat)
    ds.FlushCache()
    ds = None


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("grid_corridor_lead", "hydrology_basin_lead")
    bg = workspace / "basin_gis"
    gpkg_p = bg / "watershed_plan.gpkg"
    qgz_p = bg / "watershed_plan.qgz"
    gj_p = bg / "exports" / "plan_atlas.geojson"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_hv = (role == "grid_corridor_lead")
    lv = "HV_CORRIDOR_LAYER" if is_hv else "DETENTION_BASIN_LAYER"
    sub = "grid_corridor" if is_hv else "hydrology_basin"

    r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"layer_view": lv, "unit_mode": "UTM_METRIC_HA"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
    urllib.request.urlopen(r1, timeout=10).read()
    r2 = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r2, timeout=10).read()

    live0 = inspect_gpkg_and_exports(workspace)
    assert live0.get("ok"), f"Live GPKG unreadable: {live0}"
    if is_hv:
        peer_ha = live0["summary"]["db_total_ha"]
        target_tot_ha = max(84.0, min(146.0, 233.0 - peer_ha))
        per_sec_ha = target_tot_ha / 4.0
        h_m = (per_sec_ha * 10000.0) / 1000.0
        rects = {sn: (300.0, y0 + 250.0, 1300.0, y0 + 250.0 + h_m) for sn, y0, _ in SECTORS}
        _update_single_gpkg_layer(gpkg_p, "hv_corridor_pads", rects)
    else:
        peer_ha = live0["summary"]["hv_total_ha"]
        target_tot_ha = max(88.0, min(150.0, 233.0 - peer_ha))
        per_sec_ha = target_tot_ha / 4.0
        h_m = (per_sec_ha * 10000.0) / 1000.0
        rects = {sn: (2600.0, y0 + 250.0, 3600.0, y0 + 250.0 + h_m) for sn, y0, _ in SECTORS}
        _update_single_gpkg_layer(gpkg_p, "detention_basins", rects)

    live1 = inspect_gpkg_and_exports(workspace)
    _write_qgz(qgz_p, live1["summary"]["total_footprint_ha"])
    _export_combined_geojson(gpkg_p, gj_p)

    for st in STAGE_ORDER:
        code, resp = post_json(f"{base}/api/bench/watershed_sim", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    summ = inspect_gpkg_and_exports(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/gis/submit", {
        "subsystem": sub,
        "subsystem_ha": summ["hv_total_ha"] if is_hv else summ["db_total_ha"],
        "total_footprint_ha": summ["total_footprint_ha"],
        "geojson_sha256": sha256_file(gj_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    bg = workspace / "basin_gis"
    gpkg_p = bg / "watershed_plan.gpkg"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "v0.gpkg"
        shutil.copy2(gpkg_p, snap)
        solve_role("grid_corridor_lead", workspace, portal_port, strict=True)
        shutil.copy2(snap, gpkg_p)
        solve_role("hydrology_basin_lead", workspace, portal_port, strict=False)
