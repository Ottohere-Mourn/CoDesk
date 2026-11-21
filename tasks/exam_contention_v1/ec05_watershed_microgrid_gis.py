"""EC-05: County Floodplain & Solar Microgrid GIS EIS, Draggable Flood Slider, Clipboard & Open Calc.

Contention Archetypes:
  1. SpatiaLite .gpkg Multi-Layer Overwrite + Open LibreOffice Calc Dirty Buffer Split-Brain (with unsaved docket tag).
  2. Cross-Step X11 Clipboard Zoning/Hydrology Permit Seal Transaction.
  4. Shared Authenticated Assessor Portal (Draggable BFE Flood Slider + Paginated 24-Row ~/Downloads CSV Overwrite).
  5. 150m Cross-Layer Polygon Setback Collision + Bidirectional Bond CapEx Envelope ([17900, 18200] kUSD).
"""
from __future__ import annotations

import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from tasks.exam_contention_v1.common import (
    advisory_lock,
    find_unexpected_workspace_files,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    reload_open_libreoffice_window,
    render_scanned_document_png,
    set_x11_clipboard,
    verify_prompt_driver_and_ban_clean,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC-05"
PORTAL_PORT = 18805
DESK_TAG = "DESK-EIS-DOCKET-619"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "County Floodplain & Solar Microgrid GIS EIS, Draggable BFE Slider, Clipboard & 150m Setback",
    "domain": "Geospatial Civil Planning, Stormwater Hydrology & Municipal Microgrid Engineering",
    "archetypes": (
        "gpkg_spatial_layer_overwrite_and_150m_setback",
        "interactive_drag_slider_and_shared_downloads",
        "x11_clipboard_permit_seal_race",
        "libreoffice_calc_dirty_buffer_and_bond_capex_envelope",
    ),
    "roles": ("solar_microgrid_planner", "stormwater_hydrology_planner"),
    "portal_port": PORTAL_PORT,
    "open_gui_doc": "/workspace/county_eis/Microgrid_Flood_EIS.xlsx",
    "open_gui_unsaved_tag": DESK_TAG,
    "conc_role_timeout_s": 1800,
    "seq_role_timeout_s": 1800,
}

SOLAR_SEAL = make_opaque_seal("ec05", "SOLAR_ENERGY_OVERLAY:118")
HYDRO_SEAL = make_opaque_seal("ec05", "STORMWATER_HYDRO_OVERLAY:122")
ALLOWED_EIS_FILES = {
    "watershed_parcels.gpkg",
    "county_master.qgz",
    "EIS_Permit_Seals.json",
    "Microgrid_Flood_EIS.xlsx",
    "County_Ordinance_2026.md",
    "maps/fema_bfe_ruling.png",
    "maps/substation_curtailment_notice.png",
}

SOLAR_CAPEX_RANGE_KUSD = (9200.0, 11800.0)
HYDRO_CAPEX_RANGE_KUSD = (6050.0, 8600.0)
BOND_DRAW_BAND_KUSD = (17750.0, 18150.0)

# (pid, x0, y0, w, h, slope_pct, soil_group, feeder_dist_m, feeder_id, ground_elev_ft, tax_status)
PARCELS_SPEC = [
    ("PCL-01",  200.0,  200.0, 350.0, 340.0, 4.2, "C", 320.0, "FDR-EAST", 122.0, "CLEAR"),
    ("PCL-02",  200.0,  700.0, 340.0, 320.0, 5.1, "C", 410.0, "FDR-WEST", 121.0, "CLEAR"),
    ("PCL-03",  200.0, 1500.0, 360.0, 330.0, 3.8, "B", 290.0, "FDR-EAST", 124.0, "CLEAR"),
    ("PCL-04",  200.0, 2050.0, 350.0, 330.0, 6.4, "C", 510.0, "FDR-WEST", 119.0, "CLEAR"),
    ("PCL-05", 2200.0,  200.0, 340.0, 320.0, 9.5, "A", 820.0, "FDR-EAST", 115.0, "CLEAR"),
    ("PCL-06", 2200.0,  700.0, 330.0, 310.0, 9.2, "A", 790.0, "FDR-WEST", 114.0, "CLEAR"),
    ("PCL-07", 2200.0, 1500.0, 340.0, 320.0, 8.8, "B", 740.0, "FDR-EAST", 116.0, "CLEAR"),
    ("PCL-08", 2200.0, 2050.0, 330.0, 300.0, 9.1, "B", 880.0, "FDR-WEST", 115.0, "CLEAR"),
    ("PCL-09", 1050.0,  920.0, 340.0, 300.0, 3.5, "A", 250.0, "FDR-EAST", 123.0, "CLEAR"),          # wetland violation (<120m to WET-01)
    ("PCL-10",  200.0, 2600.0, 380.0, 350.0, 3.2, "A", 210.0, "FDR-EAST", 125.0, "TAX_LIEN_HOLD"),  # tax lien trap!
    ("PCL-11", 2200.0, 2600.0, 370.0, 350.0, 4.0, "A", 300.0, "FDR-EAST", 120.0, "TAX_LIEN_HOLD"),  # tax lien trap!
    ("PCL-12", 1500.0,  200.0, 360.0, 340.0, 4.1, "C", 310.0, "FDR-WEST", 116.5, "CLEAR"),          # flood elev 116.5 < 118 trap!
    ("PCL-13", 1500.0,  700.0, 350.0, 330.0, 9.4, "C", 400.0, "FDR-EAST", 121.0, "CLEAR"),          # slope > 8.0 & soil C
    ("PCL-14", 1500.0, 1500.0, 360.0, 340.0, 4.5, "C", 780.0, "FDR-EAST", 122.0, "CLEAR"),          # feeder > 650m & soil C
    ("PCL-15",  900.0, 2050.0, 360.0, 340.0, 3.9, "C", 340.0, "FDR-EAST", 122.0, "CLEAR"),          # 60m from PCL-16 (<150m cross-layer trap)
    ("PCL-16", 1320.0, 2050.0, 350.0, 340.0, 8.9, "A", 720.0, "FDR-WEST", 115.0, "CLEAR"),          # 60m from PCL-15 (<150m cross-layer trap)
    ("PCL-17",  200.0, 3150.0, 360.0, 340.0, 4.4, "C", 380.0, "FDR-EAST", 123.0, "CLEAR"),          # 5th clean solar parcel
    ("PCL-18", 2200.0, 3150.0, 350.0, 330.0, 9.0, "A", 760.0, "FDR-EAST", 114.5, "CLEAR"),          # 5th clean hydro parcel
    ("PCL-19",  200.0, 3700.0, 370.0, 350.0, 3.6, "C", 280.0, "FDR-EAST", 124.0, "TAX_LIEN_HOLD"),  # tax lien trap!
    ("PCL-20", 2200.0, 3700.0, 360.0, 340.0, 8.7, "A", 710.0, "FDR-EAST", 115.0, "TAX_LIEN_HOLD"),  # tax lien trap!
    ("PCL-21", 2950.0,  940.0, 330.0, 300.0, 4.0, "A", 310.0, "FDR-EAST", 121.0, "CLEAR"),          # wetland violation (<120m to WET-02)
    ("PCL-22",  900.0, 3150.0, 350.0, 330.0, 4.8, "C", 420.0, "FDR-WEST", 117.0, "CLEAR"),          # flood elev 117.0 < 118 trap!
    ("PCL-23", 1500.0, 3150.0, 350.0, 330.0, 8.6, "C", 510.0, "FDR-EAST", 120.0, "CLEAR"),          # slope > 8 & soil C
    ("PCL-24", 1500.0, 3700.0, 340.0, 320.0, 4.9, "C", 690.0, "FDR-WEST", 121.0, "CLEAR"),          # feeder > 650 & soil C
]

WETLANDS_SPEC = [
    ("WET-01", 1000.0, 1000.0, 300.0, 300.0),
    ("WET-02", 3000.0, 1000.0, 300.0, 300.0),
]


GPKG_HELPER_PY = r"""
import json, sys
from osgeo import ogr, osr

gpkg_path = sys.argv[1]
cmd = sys.argv[2]

srs = osr.SpatialReference()
srs.ImportFromEPSG(32610)

def rect_wkt(x0, y0, w, h):
    x1, y1 = x0 + w, y0 + h
    return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"

if cmd == "init":
    spec = json.loads(sys.argv[3])
    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(gpkg_path)

    lyr_p = ds.CreateLayer("candidate_parcels", srs, ogr.wkbPolygon)
    for fn, ft in [
        ("parcel_id", ogr.OFTString),
        ("area_ha", ogr.OFTReal),
        ("mean_slope_pct", ogr.OFTReal),
        ("soil_group", ogr.OFTString),
        ("feeder_dist_m", ogr.OFTReal),
        ("feeder_id", ogr.OFTString),
    ]:
        lyr_p.CreateField(ogr.FieldDefn(fn, ft))
    for pid, x0, y0, w, h, slp, soil, fdr_d, fdr_id, elv, _tx in spec["parcels"]:
        f = ogr.Feature(lyr_p.GetLayerDefn())
        f.SetField("parcel_id", pid)
        f.SetField("area_ha", round((w * h) / 10000.0, 4))
        f.SetField("mean_slope_pct", slp)
        f.SetField("soil_group", soil)
        f.SetField("feeder_dist_m", fdr_d)
        f.SetField("feeder_id", fdr_id)
        f.SetGeometry(ogr.CreateGeometryFromWkt(rect_wkt(x0, y0, w, h)))
        lyr_p.CreateFeature(f)

    lyr_w = ds.CreateLayer("protected_wetlands", srs, ogr.wkbPolygon)
    lyr_w.CreateField(ogr.FieldDefn("wetland_id", ogr.OFTString))
    for wid, x0, y0, w, h in spec["wetlands"]:
        f = ogr.Feature(lyr_w.GetLayerDefn())
        f.SetField("wetland_id", wid)
        f.SetGeometry(ogr.CreateGeometryFromWkt(rect_wkt(x0, y0, w, h)))
        lyr_w.CreateFeature(f)

    for out_ln in ("selected_solar_arrays", "selected_detention_basins"):
        lo = ds.CreateLayer(out_ln, srs, ogr.wkbPolygon)
        lo.CreateField(ogr.FieldDefn("parcel_id", ogr.OFTString))
        lo.CreateField(ogr.FieldDefn("area_ha", ogr.OFTReal))
    ds = None

elif cmd == "select":
    layer_name = sys.argv[3]
    pids = json.loads(sys.argv[4])
    ds = ogr.Open(gpkg_path, 1)
    src = ds.GetLayerByName("candidate_parcels")
    dst = ds.GetLayerByName(layer_name)
    fids = [f.GetFID() for f in dst]
    for fid in fids:
        dst.DeleteFeature(fid)
    src.ResetReading()
    for sf in src:
        pid = sf.GetField("parcel_id")
        if pid in pids:
            df = ogr.Feature(dst.GetLayerDefn())
            df.SetField("parcel_id", pid)
            df.SetField("area_ha", sf.GetField("area_ha"))
            df.SetGeometry(sf.GetGeometryRef().Clone())
            dst.CreateFeature(df)
    ds = None

elif cmd == "inspect":
    ds = ogr.Open(gpkg_path, 0)
    wet_geoms = [f.GetGeometryRef().Clone() for f in ds.GetLayerByName("protected_wetlands")]
    p_meta = {}
    for f in ds.GetLayerByName("candidate_parcels"):
        pid = f.GetField("parcel_id")
        g = f.GetGeometryRef().Clone()
        min_w = min(g.Distance(wg) for wg in wet_geoms)
        p_meta[pid] = {
            "area_ha": float(f.GetField("area_ha")),
            "slope": float(f.GetField("mean_slope_pct")),
            "soil": str(f.GetField("soil_group")),
            "feeder": float(f.GetField("feeder_dist_m")),
            "feeder_id": str(f.GetField("feeder_id")),
            "wet_dist_m": round(float(min_w), 2),
        }
    sol_list, sol_geoms = [], []
    for f in ds.GetLayerByName("selected_solar_arrays"):
        sol_list.append(str(f.GetField("parcel_id")))
        sol_geoms.append(f.GetGeometryRef().Clone())
    hyd_list, hyd_geoms = [], []
    for f in ds.GetLayerByName("selected_detention_basins"):
        hyd_list.append(str(f.GetField("parcel_id")))
        hyd_geoms.append(f.GetGeometryRef().Clone())
    cross_min = 99999.0
    for sg in sol_geoms:
        for hg in hyd_geoms:
            cross_min = min(cross_min, float(sg.Distance(hg)))
    print("GPKG_JSON:" + json.dumps({"p_meta": p_meta, "solar": sol_list, "hydro": hyd_list, "cross_min_m": round(cross_min, 2)}))
"""


def _run_gpkg(gpkg_p: Path, cmd: str, *extra: str) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tf:
        tf.write(GPKG_HELPER_PY)
        sp = tf.name
    try:
        cp = subprocess.run(["python3", sp, str(gpkg_p), cmd, *extra], capture_output=True, text=True, timeout=30)
        for ln in cp.stdout.splitlines():
            if ln.startswith("GPKG_JSON:"):
                return json.loads(ln[len("GPKG_JSON:"):])
        return {"ok": cp.returncode == 0, "stderr": cp.stderr[-400:]}
    finally:
        try:
            os.unlink(sp)
        except OSError:
            pass


def _write_qgz(qgz_p: Path, total_bond_kusd: float) -> None:
    xml_s = (
        '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM">\n'
        '<qgis version="3.22.16-Bialowieza" projectname="County_Microgrid_Flood_EIS">\n'
        '  <Title>County EIS Master Plan</Title>\n'
        f'  <TotalBondDrawKUSD>{total_bond_kusd:.2f}</TotalBondDrawKUSD>\n'
        '</qgis>\n'
    )
    with ZipFile(qgz_p, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("county_master.qgs", xml_s)


def _read_qgz_bond(qgz_p: Path) -> float:
    if not qgz_p.is_file():
        return -1.0
    try:
        with ZipFile(qgz_p, "r") as zf:
            names = [n for n in zf.namelist() if n.endswith(".qgs")]
            root = ET.fromstring(zf.read(names[0]))
        el = root.find("TotalBondDrawKUSD")
        return float(el.text.strip()) if (el is not None and el.text) else -1.0
    except Exception:
        return -1.0


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    sol_md = "\n".join([
        f"# Geospatial Solar Microgrid Siting Work Order — {b}solar_microgrid_planner{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 5-parcel municipal solar microgrid siting and capital bond sizing in {b}/workspace/county_eis{b}.",
        f"The EIS workbook {b}/workspace/county_eis/Microgrid_Flood_EIS.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active docket tag in {b}Solar_Siting!C1{b}) alongside the County Assessor & Floodplain Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/county_eis/County_Ordinance_2026.md{b}, scanned engineering rulings in {b}/workspace/county_eis/maps/{b} ({b}fema_bfe_ruling.png{b}, {b}substation_curtailment_notice.png{b}), and the full 24-parcel Assessor CSV from {b}http://127.0.0.1:{PORTAL_PORT}{b} at the ruling 100-year Base Flood Elevation.",
        f"2. Populate layer {b}selected_solar_arrays{b} in {b}/workspace/county_eis/watershed_parcels.gpkg{b} with **5** eligible parcels from {b}candidate_parcels{b} meeting all wetland, flood, slope, feeder, tax-lien, inter-facility setback, and derated net export MWac requirements while preserving all other GeoPackage layers.",
        f"3. Copy the Solar Zoning Permit Seal from the Assessor Portal ({b}OVERLAY = SOLAR_ENERGY_OVERLAY{b} at the 100-year {b}BFE = 118 ft{b}) via the system clipboard, paste/record it in {b}Solar_Siting!B3{b} of {b}Microgrid_Flood_EIS.xlsx{b}, and sync key {b}\"solar_permit_seal\"{b} in {b}/workspace/county_eis/EIS_Permit_Seals.json{b}.",
        f"4. Record total net exportable solar capacity ({b}MWac{b}) in {b}Solar_Siting!B2{b}, size only {b}Bond_Budget!B2{b} ({b}Solar_Equip_CapEx_kUSD{b}) so {b}Bond_Budget!B4{b} satisfies the municipal bond authorization window, sync {b}<TotalBondDrawKUSD>{b} in {b}/workspace/county_eis/county_master.qgz{b}, and save {b}Microgrid_Flood_EIS.xlsx{b} preserving all sheets, formulas, and {b}Solar_Siting!C1{b}. Keep {b}/workspace/county_eis{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])

    hyd_md = "\n".join([
        f"# Stormwater Detention Siting Work Order — {b}stormwater_hydrology_planner{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 5-parcel 100-year stormwater detention siting and capital bond sizing in {b}/workspace/county_eis{b}.",
        f"The EIS workbook {b}/workspace/county_eis/Microgrid_Flood_EIS.xlsx{b} is currently open in LibreOffice Calc on the workstation (with an active docket tag in {b}Solar_Siting!C1{b}) alongside the County Assessor & Floodplain Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/county_eis/County_Ordinance_2026.md{b}, scanned engineering rulings in {b}/workspace/county_eis/maps/{b} ({b}fema_bfe_ruling.png{b}, {b}substation_curtailment_notice.png{b}), and the full 24-parcel Assessor CSV from {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        f"2. Populate layer {b}selected_detention_basins{b} in {b}/workspace/county_eis/watershed_parcels.gpkg{b} with **5** eligible parcels from {b}candidate_parcels{b} meeting all wetland, hydrologic soil group, tax-lien, inter-facility setback, and freeboard-adjusted runoff storage requirements while preserving all other GeoPackage layers.",
        f"3. Copy the Stormwater Hydrology Permit Seal from the Assessor Portal ({b}OVERLAY = STORMWATER_HYDRO_OVERLAY{b} at the 500-year Dam Safety Spillway Check {b}BFE = 122 ft{b}) via the system clipboard, paste/record it in {b}Detention_Siting!B3{b} of {b}Microgrid_Flood_EIS.xlsx{b}, and sync key {b}\"hydro_permit_seal\"{b} in {b}/workspace/county_eis/EIS_Permit_Seals.json{b}.",
        f"4. Record total effective detention storage ({b}m^3{b}) in {b}Detention_Siting!B2{b}, size only {b}Bond_Budget!B3{b} ({b}Hydro_Excavation_CapEx_kUSD{b}) so {b}Bond_Budget!B4{b} satisfies the municipal bond authorization window, sync {b}<TotalBondDrawKUSD>{b} in {b}/workspace/county_eis/county_master.qgz{b}, and save {b}Microgrid_Flood_EIS.xlsx{b} preserving all sheets, formulas, and {b}Solar_Siting!C1{b}. Keep {b}/workspace/county_eis{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])
    return {"solar_microgrid_planner": sol_md, "stormwater_hydrology_planner": hyd_md}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    b = chr(96)
    ce = workspace / "county_eis"
    (ce / "maps").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    gpkg_p = ce / "watershed_parcels.gpkg"
    if gpkg_p.exists():
        gpkg_p.unlink()
    _run_gpkg(gpkg_p, "init", json.dumps({"parcels": PARCELS_SPEC, "wetlands": WETLANDS_SPEC}))

    (ce / "County_Ordinance_2026.md").write_text(
        "\n".join([
            "# Cedar County Ordinance 2026-09 — Watershed Floodplain, Solar Microgrid & Bond EIS Rules",
            "",
            f"1. **Assessor Tax Roll & Floodplain Portal ({b}http://127.0.0.1:{PORTAL_PORT}{b})**:",
            f"   - The portal screen previews only {b}PCL-01..PCL-06{b}; export {b}/home/gui/Downloads/county_parcel_assessor.csv{b} to inspect all 24 candidate parcels.",
            f"   - **Permit Seal BFE Governance**: Solar Microgrid Zoning Permit Seals require {b}OVERLAY = SOLAR_ENERGY_OVERLAY{b} at the adopted 100-year electrical pad elevation ({b}BFE = 118 ft{b} per {b}maps/fema_bfe_ruling.png{b}), whereas Stormwater Hydrology Permit Seals require {b}OVERLAY = STORMWATER_HYDRO_OVERLAY{b} at the 500-year Dam Safety Spillway stage ({b}BFE = 122 ft{b} per {b}maps/substation_curtailment_notice.png{b}).",
            f"   - Exclude any parcel with {b}tax_status = 'TAX_LIEN_HOLD'{b} from both municipal siting layers.",
            "",
            "2. **Wetland & Cross-Facility Euclidean Setbacks (`watershed_parcels.gpkg`, EPSG:32610 meters)**:",
            f"   - Every selected parcel in {b}selected_solar_arrays{b} (exactly **5** parcels) and {b}selected_detention_basins{b} (exactly **5** parcels) MUST maintain **>= 120.0 m** polygon-to-polygon distance from {b}protected_wetlands{b}.",
            f"   - Every polygon in {b}selected_solar_arrays{b} MUST maintain **>= 150.0 m** polygon-to-polygon clearance from every polygon in {b}selected_detention_basins{b}.",
            "",
            "3. **Solar Microgrid Eligibility & Net Capacity (`Solar_Siting!B2`)**:",
            f"   - Eligible solar parcels require {b}flood_status = 'ABOVE_BFE'{b} when evaluated at the adopted 100-year BFE in {b}maps/fema_bfe_ruling.png{b}, {b}mean_slope_pct <= 8.0{b}, and {b}feeder_dist_m <= 650.0{b}.",
            f"   - Nameplate density is {b}0.62 MWac / ha{b}, multiplied by the feeder export factor in {b}maps/substation_curtailment_notice.png{b}. Total net exportable capacity across the 5 selected solar parcels MUST be **>= 31.0 MWac**.",
            "",
            "4. **Stormwater Detention Eligibility & Effective Storage (`Detention_Siting!B2`)**:",
            f"   - Eligible detention parcels require hydrologic {b}soil_group IN ('A', 'B'){b} (detention basins are permitted below BFE).",
            f"   - Gross excavation yield is {b}2100.0 m^3 / ha{b} for Soil Group {b}A{b} and {b}1650.0 m^3 / ha{b} for Soil Group {b}B{b}; multiply by the freeboard factor in {b}maps/substation_curtailment_notice.png{b} to obtain effective storage, which MUST total **>= 78,000.0 m^3** across the 5 selected basins.",
            "",
            "5. **Municipal Green Bond Envelope (`Bond_Budget` & `county_master.qgz`)**:",
            f"   - {b}Solar_Equip_CapEx_kUSD{b} ({b}B2{b}): permitted range **{b}[9200.0, 11800.0] kUSD{b}**.",
            f"   - {b}Hydro_Excavation_CapEx_kUSD{b} ({b}B3{b}): permitted range **{b}[6050.0, 8600.0] kUSD{b}**.",
            f"   - {b}Total_Bond_Draw_kUSD{b} ({b}B4 = =B2+B3{b}) MUST evaluate within **{b}[17750.0, 18150.0] kUSD{b}**, and {b}<TotalBondDrawKUSD>{b} inside {b}county_master.qgz{b} must match {b}Bond_Budget!B4{b}.",
            "",
        ]),
        encoding="utf-8",
    )

    render_scanned_document_png(
        ce / "maps" / "fema_bfe_ruling.png",
        "FEMA REGION X — LETTER OF MAP REVISION (ADOPTED 2026)",
        [
            "Watershed: Cedar Creek Basin (UTM Zone 10N, EPSG:32610)",
            "Superseded Preliminary Study BFE: 114.0 ft NAVD88",
            "ADOPTED BINDING 100-YEAR BASE FLOOD ELEVATION: 118.0 ft NAVD88",
            "All electrical/solar pads and county permit seals require BFE = 118 ft.",
        ],
        stamp_text="FEMA LOMR EFFECTIVE",
        tilt_deg=-1.6,
    )
    render_scanned_document_png(
        ce / "maps" / "substation_curtailment_notice.png",
        "PUBLIC WORKS & UTILITY INTERCONNECTION ENGINEERING ADDENDUM",
        [
            "1. Substation Feeder Export Factor (Solar Net MWac):",
            "   - Feeder FDR-EAST : 1.00x (full 0.62 MWac/ha export capacity)",
            "   - Feeder FDR-WEST : 0.85x thermal transformer derating factor",
            "     (effective net export = area_ha * 0.62 * 0.85 MWac)",
            "2. Detention Basin Freeboard & 500-Yr Spillway Permit Stage:",
            "   - Effective_Storage_m3 = Gross_Storage_m3 * 0.90 (10% crest freeboard).",
            "   - Stormwater Hydrology Permit Seal requires BFE_SLIDER = 122 ft.",
        ],
        stamp_text="UTILITY & HYDRO SIGNED",
        tilt_deg=1.7,
    )

    write_json(ce / "EIS_Permit_Seals.json", {"solar_permit_seal": "PENDING", "hydro_permit_seal": "PENDING"})
    _write_qgz(ce / "county_master.qgz", 19800.0)
    write_multisheet_xlsx(
        ce / "Microgrid_Flood_EIS.xlsx",
        [
            ("Solar_Siting", [["Metric", "Value", ""], ["Total_Solar_Capacity_MWac", 0.0, ""], ["Solar_Permit_Seal", "PENDING", ""]]),
            ("Detention_Siting", [["Metric", "Value"], ["Total_Detention_Storage_m3", 0.0], ["Hydro_Permit_Seal", "PENDING"]]),
            ("Bond_Budget", [["Component", "CapEx_kUSD"], ["Solar_Equip_CapEx_kUSD", 11500.0], ["Hydro_Excavation_CapEx_kUSD", 8300.0], ["Total_Bond_Draw_kUSD", ("=B2+B3", 19800.0)]]),
        ],
    )

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_assessor_html(overlay: str, bfe_ft: int, view_tab: str = "ROLL") -> str:
    rows = []
    for pid, _x, _y, w, h, slp, soil, fd_d, fd_id, elv, tx in PARCELS_SPEC[:6]:
        flood = "INUNDATED_BELOW_BFE" if elv < bfe_ft else "ABOVE_BFE"
        rows.append(
            f"<tr><td>{pid}</td><td>{(w*h)/10000.0:.2f}</td><td>{elv:.1f}</td><td>{flood}</td>"
            f"<td>{slp:.1f}%</td><td>{soil}</td><td>{fd_id} ({fd_d:.0f}m)</td><td><strong>{tx}</strong></td></tr>"
        )
    if view_tab == "RULINGS":
        main_html = (
            "<h3>Authenticated FEMA & Public Works Scanned Engineering Rulings</h3>"
            "<p><img src='/maps/fema_bfe_ruling.png' style='max-width:860px;border:1px solid #94a3b8;margin-bottom:10px;'/></p>"
            "<p><img src='/maps/substation_curtailment_notice.png' style='max-width:860px;border:1px solid #94a3b8;'/></p>"
        )
    else:
        main_html = (
            "<p style='font-size:13px;color:#064e3b;'><strong>Previewing 6 of 24 Candidate Parcels</strong> — Set BFE Slider and click <strong>Export All 24 Parcels CSV</strong> for complete tax-lien and flood-stage roll.</p>"
            f"<table><thead><tr><th>Parcel</th><th>Area (ha)</th><th>Elev (ft)</th><th>Flood (@ {bfe_ft}ft)</th><th>Slope</th><th>Soil</th><th>Feeder</th><th>Tax Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Cedar County Assessor & Floodplain GIS Portal</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: #064e3b; color: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    .toolbar {{ background: #d1fae5; padding: 10px 20px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    button {{ background: #ffffff; border: 1px solid #047857; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-weight: 600; }}
    button.active {{ background: #064e3b; color: #ffffff; }}
    main {{ padding: 16px 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; font-size: 13px; text-align: left; }}
    th {{ background: #ecfdf5; }}
  </style>
</head>
<body>
  <header>
    <div><strong>Cedar County GIS Assessor & Floodplain Permit Portal</strong></div>
    <div style="font-family:monospace;" id="gis-banner">OVERLAY={overlay} | BFE_SLIDER={bfe_ft}ft</div>
  </header>
  <div class="toolbar">
    <strong>Overlay:</strong>
    <button class="{'active' if overlay == 'SOLAR_ENERGY_OVERLAY' else ''}" onclick="setGis({{overlay:'SOLAR_ENERGY_OVERLAY'}})">SOLAR_ENERGY_OVERLAY</button>
    <button class="{'active' if overlay == 'STORMWATER_HYDRO_OVERLAY' else ''}" onclick="setGis({{overlay:'STORMWATER_HYDRO_OVERLAY'}})">STORMWATER_HYDRO_OVERLAY</button>
    <label><strong>BFE Slider (<span id="bfe-lbl">{bfe_ft}</span> ft):</strong>
      <input id="bfe-slider" type="range" min="112" max="126" step="1" value="{bfe_ft}" onchange="setGis({{bfe_ft: parseInt(this.value)}})" />
    </label>
    <button class="{'active' if view_tab == 'ROLL' else ''}" onclick="setGis({{view_tab:'ROLL'}})">Assessor Roll (6/24)</button>
    <button class="{'active' if view_tab == 'RULINGS' else ''}" onclick="setGis({{view_tab:'RULINGS'}})">Rulings (2 Scans)</button>
    <button onclick="expAssessor()">Export All 24 Parcels CSV (/home/gui/Downloads/county_parcel_assessor.csv)</button>
    <button onclick="copyPermit()">Copy Signed County Permit Seal to Clipboard</button>
    <span id="msg" style="font-family:monospace;font-size:12px;color:#065f46;">Ready</span>
  </div>
  <main>
    {main_html}
  </main>
  <script>
    async function setGis(p) {{
      await fetch('/api/assessor/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(p)}});
      window.location.reload();
    }}
    async function expAssessor() {{
      document.getElementById('msg').textContent = 'Exporting 24-parcel tax/flood roll...';
      const r = await fetch('/api/assessor/export_csv', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Exported 24 parcels @ BFE=' + d.bfe_ft + 'ft') : 'Error';
    }}
    async function copyPermit() {{
      const r = await fetch('/api/assessor/copy_seal', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Copied ' + d.overlay + ' seal') : 'Error';
    }}
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "overlay": "SOLAR_ENERGY_OVERLAY",
        "bfe_ft": 114,
        "view_tab": "ROLL",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
    }

    def persist() -> None:
        write_json(state_p, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec05_gis_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "task_id": TASK_ID})
                return
            if parsed.path == "/":
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"ec05_gis_sso={sso_cookie}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated Assessor session required"})
                    return
                with lock:
                    html = _render_assessor_html(pstate["overlay"], int(pstate["bfe_ft"]), pstate["view_tab"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path.startswith("/maps/"):
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated Assessor session required"})
                    return
                fn = Path(parsed.path).name
                fp = workspace / "county_eis" / "maps" / fn
                if fp.is_file() and fp.suffix == ".png":
                    raw_png = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw_png)))
                    self.end_headers()
                    self.wfile.write(raw_png)
                    return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._authed():
                self._send_json(401, {"error": "Authenticated Assessor session required"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if parsed.path == "/api/assessor/state":
                with lock:
                    changed = False
                    if body.get("overlay") in ("SOLAR_ENERGY_OVERLAY", "STORMWATER_HYDRO_OVERLAY"):
                        if pstate["overlay"] != body["overlay"]:
                            changed = True
                        pstate["overlay"] = body["overlay"]
                    if isinstance(body.get("bfe_ft"), (int, float)):
                        nv = max(112, min(126, int(body["bfe_ft"])))
                        if pstate["bfe_ft"] != nv:
                            changed = True
                        pstate["bfe_ft"] = nv
                    if body.get("view_tab") in ("ROLL", "RULINGS"):
                        if pstate["view_tab"] != body["view_tab"]:
                            changed = True
                        pstate["view_tab"] = body["view_tab"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "overlay": pstate["overlay"], "bfe_ft": pstate["bfe_ft"]})
                return

            if parsed.path == "/api/assessor/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.4 if is_adm else 4.2)
                dl_p = Path("/home/gui/Downloads/county_parcel_assessor.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    bfe = int(pstate["bfe_ft"])
                    lines = ["parcel_id,area_ha,flood_status,feeder_id,tax_status"]
                    for pid, _x, _y, w, h, _sl, _so, _fd_d, fd_id, elv, tx in PARCELS_SPEC:
                        fst = "INUNDATED_BELOW_BFE" if elv < bfe else "ABOVE_BFE"
                        lines.append(f"{pid},{(w*h)/10000.0:.2f},{fst},{fd_id},{tx}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "path": str(dl_p), "bfe_ft": bfe})
                return

            if parsed.path == "/api/assessor/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 1.5)
                with lock:
                    ov = pstate["overlay"]
                    bfe = int(pstate["bfe_ft"])
                    seal = make_opaque_seal("ec05", f"{ov}:{bfe}")
                    pstate["clipboard_copies"] += 1
                    persist()
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "overlay": ov, "bfe_ft": bfe})
                return

            self._send_json(404, {"error": "Not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def grade(workspace: Path, service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ce = workspace / "county_eis"
    gpkg_p = ce / "watershed_parcels.gpkg"
    qgz_p = ce / "county_master.qgz"
    seals_p = ce / "EIS_Permit_Seals.json"
    xp = ce / "Microgrid_Flood_EIS.xlsx"

    errs_a: list[str] = []
    errs_b: list[str] = []
    errs_joint: list[str] = []

    tax_map = {p[0]: p[10] for p in PARCELS_SPEC}
    elev_map = {p[0]: float(p[9]) for p in PARCELS_SPEC}
    gis = _run_gpkg(gpkg_p, "inspect") if gpkg_p.is_file() else {}
    p_meta = gis.get("p_meta") or {}
    sol_ids = sorted(set(gis.get("solar") or []))
    hyd_ids = sorted(set(gis.get("hydro") or []))

    exp_mw = 0.0
    if len(sol_ids) != 5:
        errs_a.append(f"selected_solar_arrays count={len(sol_ids)} != 5")
    for pid in sol_ids:
        pm = p_meta.get(pid)
        if not pm:
            errs_a.append(f"Unknown solar parcel {pid}")
            continue
        if tax_map.get(pid) != "CLEAR":
            errs_a.append(f"Solar parcel {pid} has TAX_LIEN_HOLD")
        if pm["wet_dist_m"] < 120.0:
            errs_a.append(f"Solar parcel {pid} within {pm['wet_dist_m']}m < 120m of wetland")
        if elev_map.get(pid, 0.0) < 118.0 or pm["slope"] > 8.0 or pm["feeder"] > 650.0:
            errs_a.append(f"Solar parcel {pid} violates elev/slope/feeder rules")
        derate = 0.85 if pm["feeder_id"] == "FDR-WEST" else 1.00
        exp_mw += pm["area_ha"] * 0.62 * derate
    if exp_mw < 31.0:
        errs_a.append(f"Total net solar capacity={exp_mw:.2f} MWac < 31.0 MWac")

    exp_m3 = 0.0
    if len(hyd_ids) != 5:
        errs_b.append(f"selected_detention_basins count={len(hyd_ids)} != 5")
    for pid in hyd_ids:
        pm = p_meta.get(pid)
        if not pm:
            errs_b.append(f"Unknown hydro parcel {pid}")
            continue
        if tax_map.get(pid) != "CLEAR":
            errs_b.append(f"Hydro parcel {pid} has TAX_LIEN_HOLD")
        if pm["wet_dist_m"] < 120.0:
            errs_b.append(f"Hydro parcel {pid} within {pm['wet_dist_m']}m < 120m of wetland")
        if pm["soil"] not in ("A", "B"):
            errs_b.append(f"Hydro parcel {pid} invalid soil_group={pm['soil']}")
        exp_m3 += pm["area_ha"] * (2100.0 if pm["soil"] == "A" else 1650.0) * 0.90
    if exp_m3 < 78000.0:
        errs_b.append(f"Total effective detention storage={exp_m3:.1f} m3 < 78000 m3")

    if sol_ids and hyd_ids and float(gis.get("cross_min_m", 0.0)) < 150.0:
        errs_joint.append(f"Inter-facility clearance={gis.get('cross_min_m')}m < 150.0m")

    seals = json.loads(seals_p.read_text(encoding="utf-8")) if seals_p.is_file() else {}
    if seals.get("solar_permit_seal") != SOLAR_SEAL:
        errs_a.append("EIS_Permit_Seals.json missing valid solar_permit_seal")
    if seals.get("hydro_permit_seal") != HYDRO_SEAL:
        errs_b.append("EIS_Permit_Seals.json missing valid hydro_permit_seal")

    if not xp.is_file():
        errs_joint.append("Missing Microgrid_Flood_EIS.xlsx")
    else:
        raw_sh = read_multisheet_xlsx(xp)
        ev_sh = evaluate_xlsx_via_libreoffice(xp)

        def _v(sh: str, ref: str) -> float:
            val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
            return float(val) if isinstance(val, (int, float)) else -99999.0

        def _s(sh: str, ref: str) -> str:
            val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
            return str(val or "").strip()

        def _f(sh: str, ref: str) -> bool:
            return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

        if _s("Solar_Siting", "C1") != DESK_TAG:
            errs_joint.append(f"Solar_Siting!C1 lost live Calc docket tag ({_s('Solar_Siting', 'C1')!r} != {DESK_TAG!r})")
        if abs(_v("Solar_Siting", "B2") - exp_mw) > 0.35:
            errs_a.append(f"Solar_Siting!B2={_v('Solar_Siting', 'B2')} out of sync with derated MWac={exp_mw:.3f}")
        if _s("Solar_Siting", "B3") != SOLAR_SEAL:
            errs_a.append(f"Solar_Siting!B3 missing valid Solar_Permit_Seal ({_s('Solar_Siting', 'B3')!r})")
        if abs(_v("Detention_Siting", "B2") - exp_m3) > 60.0:
            errs_b.append(f"Detention_Siting!B2={_v('Detention_Siting', 'B2')} out of sync with freeboard m3={exp_m3:.1f}")
        if _s("Detention_Siting", "B3") != HYDRO_SEAL:
            errs_b.append(f"Detention_Siting!B3 missing valid Hydro_Permit_Seal ({_s('Detention_Siting', 'B3')!r})")

        sc_v = _v("Bond_Budget", "B2")
        hc_v = _v("Bond_Budget", "B3")
        tb_v = _v("Bond_Budget", "B4")
        if not (SOLAR_CAPEX_RANGE_KUSD[0] <= sc_v <= SOLAR_CAPEX_RANGE_KUSD[1]):
            errs_a.append(f"Solar_Equip_CapEx={sc_v} outside {list(SOLAR_CAPEX_RANGE_KUSD)}")
        if not (HYDRO_CAPEX_RANGE_KUSD[0] <= hc_v <= HYDRO_CAPEX_RANGE_KUSD[1]):
            errs_b.append(f"Hydro_Excavation_CapEx={hc_v} outside {list(HYDRO_CAPEX_RANGE_KUSD)}")
        if not _f("Bond_Budget", "B4") or not (BOND_DRAW_BAND_KUSD[0] <= tb_v <= BOND_DRAW_BAND_KUSD[1]):
            errs_joint.append(f"Total_Bond_Draw={tb_v} outside {list(BOND_DRAW_BAND_KUSD)} or missing formula")
        if abs(_read_qgz_bond(qgz_p) - tb_v) > 2.0:
            errs_joint.append("county_master.qgz <TotalBondDrawKUSD> out of sync with Bond_Budget!B4")

    if service_state.get("open_gui_split_brain") is True:
        errs_joint.append("Open LibreOffice Calc window held stale unsaved buffer inconsistent with disk")
    extra_files = find_unexpected_workspace_files(ce, ALLOWED_EIS_FILES)
    if extra_files:
        errs_joint.append(f"Unexpected scratch/coordination files in /workspace/county_eis: {extra_files[:5]}")

    pass_a = len(errs_a) == 0 and len(errs_joint) == 0
    pass_b = len(errs_b) == 0 and len(errs_joint) == 0
    return {
        "task_id": TASK_ID,
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": pass_a and pass_b,
        "errors_a": errs_a,
        "errors_b": errs_b,
        "errors_joint": errs_joint,
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_driver_and_ban_clean(build_tickets_by_role()),
        "telemetry": service_state,
    }


def solve_role(role: str, workspace: Path, port: int, careful_conc: bool = False) -> None:
    assert role in ("solar_microgrid_planner", "stormwater_hydrology_planner")
    ce = workspace / "county_eis"
    gpkg_p = ce / "watershed_parcels.gpkg"
    qgz_p = ce / "county_master.qgz"
    seals_p = ce / "EIS_Permit_Seals.json"
    xp = ce / "Microgrid_Flood_EIS.xlsx"
    adm_p = Path("/opt/ec_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_s = (role == "solar_microgrid_planner")
        ov = "SOLAR_ENERGY_OVERLAY" if is_s else "STORMWATER_HYDRO_OVERLAY"
        req_bfe = 118 if is_s else 122
        urllib.request.urlopen(
            urllib.request.Request(
                f"{base}/api/assessor/state",
                data=json.dumps({"overlay": ov, "bfe_ft": req_bfe}).encode("utf-8"),
                headers={"Content-Type": "application/json", **adm_hdr},
                method="POST",
            ),
            timeout=10,
        ).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/assessor/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/assessor/copy_seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_val = get_x11_clipboard()

        seals = json.loads(seals_p.read_text(encoding="utf-8"))
        if is_s:
            seals["solar_permit_seal"] = seal_val
            _run_gpkg(gpkg_p, "select", "selected_solar_arrays", json.dumps(["PCL-01", "PCL-02", "PCL-03", "PCL-04", "PCL-17"]))
        else:
            seals["hydro_permit_seal"] = seal_val
            _run_gpkg(gpkg_p, "select", "selected_detention_basins", json.dumps(["PCL-05", "PCL-06", "PCL-07", "PCL-08", "PCL-18"]))
        write_json(seals_p, seals)

        gis = _run_gpkg(gpkg_p, "inspect")
        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["Solar_Siting"].get("C1") or {}).get("value") or DESK_TAG)
        cur_sc = float((ev["Bond_Budget"].get("B2") or {}).get("value") or 11500.0)
        cur_hc = float((ev["Bond_Budget"].get("B3") or {}).get("value") or 8300.0)

        if is_s:
            mw = round(
                sum(gis["p_meta"][p]["area_ha"] * 0.62 * (0.85 if gis["p_meta"][p]["feeder_id"] == "FDR-WEST" else 1.0) for p in gis["solar"]),
                3,
            )
            tgt_b = 17950.0
            new_sc = round(max(SOLAR_CAPEX_RANGE_KUSD[0], min(SOLAR_CAPEX_RANGE_KUSD[1], tgt_b - cur_hc)), 2)
            tot_b = round(new_sc + cur_hc, 2)
            update_single_sheet_xlsx(xp, "Solar_Siting", [["Metric", "Value", desk_c1], ["Total_Solar_Capacity_MWac", mw, ""], ["Solar_Permit_Seal", seal_val, ""]])
            update_single_sheet_xlsx(xp, "Bond_Budget", [["Component", "CapEx_kUSD"], ["Solar_Equip_CapEx_kUSD", new_sc], ["Hydro_Excavation_CapEx_kUSD", cur_hc], ["Total_Bond_Draw_kUSD", ("=B2+B3", tot_b)]])
        else:
            m3 = round(
                sum(gis["p_meta"][p]["area_ha"] * (2100.0 if gis["p_meta"][p]["soil"] == "A" else 1650.0) * 0.90 for p in gis["hydro"]),
                2,
            )
            tgt_b = 17950.0
            new_hc = round(max(HYDRO_CAPEX_RANGE_KUSD[0], min(HYDRO_CAPEX_RANGE_KUSD[1], tgt_b - cur_sc)), 2)
            tot_b = round(cur_sc + new_hc, 2)
            update_single_sheet_xlsx(xp, "Detention_Siting", [["Metric", "Value"], ["Total_Detention_Storage_m3", m3], ["Hydro_Permit_Seal", seal_val]])
            update_single_sheet_xlsx(xp, "Bond_Budget", [["Component", "CapEx_kUSD"], ["Solar_Equip_CapEx_kUSD", cur_sc], ["Hydro_Excavation_CapEx_kUSD", new_hc], ["Total_Bond_Draw_kUSD", ("=B2+B3", tot_b)]])

        _write_qgz(qgz_p, tot_b)
        reload_open_libreoffice_window(xp)

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_naive_race(workspace: Path, port: int) -> None:
    ce = workspace / "county_eis"
    gpkg_p = ce / "watershed_parcels.gpkg"
    solve_role("solar_microgrid_planner", workspace, port, careful_conc=False)
    solve_role("stormwater_hydrology_planner", workspace, port, careful_conc=False)
    _run_gpkg(gpkg_p, "select", "selected_solar_arrays", json.dumps(["PCL-01", "PCL-02", "PCL-03", "PCL-04", "PCL-15"]))
    _run_gpkg(gpkg_p, "select", "selected_detention_basins", json.dumps(["PCL-05", "PCL-06", "PCL-07", "PCL-08", "PCL-16"]))
