"""AW-03: Municipal Watershed Capital Plan — QGIS UTM Reprojection & Wetland Setbacks vs. Kirpich IDF & Manning RCP."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    convert_to_pdf_headless,
    evaluate_xlsx_isolated,
    extract_pdf_text,
    launch_desktop_app_as_user,
    read_json_safe,
    resource_lock,
    update_single_sheet_xlsx,
    write_json,
    write_multisheet_xlsx,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-03",
    "slug": "qgis_stormwater_watershed",
    "title": "Municipal Watershed Capital Plan: QGIS UTM Reprojection & Wetland Setbacks vs. Kirpich IDF & Manning RCP",
    "domain": "Civil GIS & Stormwater Hydraulics (QGIS 3.22 + GDAL/OGR + LibreOffice Calc + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19603,
    "roles": ("gis_landuse_analyst", "hydraulic_basin_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

# (id, lon_min, lat_min, lon_max, lat_max, land_use, native_hsg, compacted_fill, underdrain_present, imp_pct, disconn_roof_pct, flow_len_m, elev_drop_m, pipe_slope, pipe_len_m, invert_depth_m)
# Realistic 1.8..4.5 ha urban subcatchments so peak Q spans ~0.35..1.75 m^3/s and RCP diameters span 525..1050 mm!
SUBCATCHMENTS_RAW: list[tuple[Any, ...]] = [
    ("SC-01", -74.1800, 40.7200, -74.1782, 40.7215, "commercial", "B", 1, 1, 74.0, 0.0, 125.0, 6.2, 0.0085, 210.0, 2.8),
    ("SC-02", -74.1782, 40.7200, -74.1758, 40.7219, "residential_med", "B/D", 0, 0, 44.0, 12.0, 390.0, 5.1, 0.0045, 340.0, 3.9),
    ("SC-03", -74.1758, 40.7200, -74.1735, 40.7218, "industrial", "C", 1, 0, 68.0, 0.0, 460.0, 4.9, 0.0042, 390.0, 4.1),
    ("SC-04", -74.1800, 40.7215, -74.1780, 40.7231, "mixed_transit", "A", 1, 1, 62.0, 8.0, 115.0, 7.0, 0.0090, 185.0, 2.6),
    ("SC-05", -74.1780, 40.7219, -74.1752, 40.7240, "park_campus", "C/D", 0, 1, 30.0, 10.0, 540.0, 5.6, 0.0038, 460.0, 3.2),
    ("SC-06", -74.1752, 40.7218, -74.1728, 40.7237, "residential_high", "C", 0, 0, 58.0, 6.0, 420.0, 5.8, 0.0055, 315.0, 3.8),
]

# Protected Class-I wetland setback boxes overlapping SC-02 and SC-05
WETLAND_BOXES: list[tuple[str, float, float, float, float]] = [
    ("WL-NORTH", -74.1772, 40.7226, -74.1760, 40.7236),
    ("WL-SOUTH", -74.1775, 40.7204, -74.1764, 40.7213),
]

PERVIOUS_C_TABLE: dict[str, dict[str, float]] = {
    "commercial": {"A": 0.18, "B": 0.24, "C": 0.32, "D": 0.40},
    "residential_med": {"A": 0.14, "B": 0.20, "C": 0.28, "D": 0.36},
    "residential_high": {"A": 0.16, "B": 0.22, "C": 0.30, "D": 0.38},
    "industrial": {"A": 0.20, "B": 0.27, "C": 0.35, "D": 0.44},
    "mixed_transit": {"A": 0.17, "B": 0.23, "C": 0.31, "D": 0.39},
    "park_campus": {"A": 0.10, "B": 0.15, "C": 0.22, "D": 0.30},
}

RCP_COST_PER_M: dict[int, float] = {
    300: 290.0,
    375: 345.0,
    450: 410.0,
    525: 485.0,
    600: 575.0,
    750: 740.0,
    900: 935.0,
    1050: 1160.0,
    1200: 1420.0,
    1350: 1710.0,
    1500: 2050.0,
}

IDF_A = 2840.0
IDF_B = 14.5
IDF_C = 0.82
CLIMATE_FACTOR_100YR = 1.18
PORTAL_PERMIT_CODE = "NJDEP-SWM-2026-884"

TICKET_A = (
    "# Work Order — GIS Land-Use & Runoff Analyst (`gis_landuse_analyst`)\n\n"
    "Complete the UTM Zone 18N watershed reprojection, Class-I wetland exclusion clipping, and runoff coefficient schedule in `/workspace/watershed`:\n\n"
    "1. Review `/workspace/watershed/specs/Stormwater_Design_Manual.pdf`, query `/workspace/watershed/soil_survey.sqlite` (`parcels_soil`), and inspect the **Metro Stormwater Portal** open in Chromium (`http://127.0.0.1:19603`, `Pervious C & Soil Rules` tab).\n"
    "2. Reproject `/workspace/watershed/subcatchments_wgs84.geojson` and `/workspace/watershed/wetland_buffers_wgs84.geojson` from `EPSG:4326` to `EPSG:32618` (UTM Zone 18N, meters), subtract the Class-I wetland setback polygons from the subcatchments to compute developable drainage area (`developable_area_ha`, rounded to 3 decimals), and write `/workspace/watershed/subcatchments_utm18n_clean.geojson` in `EPSG:32618`.\n"
    "3. Determine `effective_hsg` (applying both dual-HSG drainage rules and compacted-fill rules from the manual) and `composite_c` (accounting for connected impervious, disconnected rooftop credit, and pervious fractions, rounded to 3 decimals) for `SC-01`..`SC-06`, along with `total_developable_ha` and `area_weighted_c`.\n"
    "4. Update the `LandUse_Runoff` sheet in `/workspace/watershed/Watershed_Capital_Model.xlsx` (preserving all other sheets; also refresh `Capital_Summary` cell `B2`=`total_developable_ha` and `B3`=`area_weighted_c`), and write `/workspace/watershed/gis_delineation_summary.json` with:\n"
    "   - `permit_authority_code`, `crs_epsg` (`32618`), `total_developable_ha`, `area_weighted_c`\n"
    "   - `subcatchments`: mapping `SC-01`..`SC-06` -> `{\"developable_area_ha\": ..., \"effective_hsg\": ..., \"composite_c\": ...}`\n"
)

TICKET_B = (
    "# Work Order — Stormwater Hydraulic & Capital Engineer (`hydraulic_basin_eng`)\n\n"
    "Complete the 100-year climate-adjusted Kirpich IDF peak-flow analysis, Manning circular RCP trunk sizing, and capital schedule in `/workspace/watershed`:\n\n"
    "1. Review `/workspace/watershed/specs/Stormwater_Design_Manual.pdf`, query `/workspace/watershed/soil_survey.sqlite` (`parcels_soil`, `hydraulic_reaches`), and inspect the **Metro Stormwater Portal** in Chromium (`http://127.0.0.1:19603`) across its hydrology and unit-cost views.\n"
    "2. Using the `EPSG:32618` wetland-clipped developable areas and adjusted `composite_c` values for `SC-01`..`SC-06`, compute Kirpich `tc_min`, 100-year climate-adjusted intensity `intensity_mm_hr`, Rational peak flow `peak_q_cms` ($\\text{m}^3/\\text{s}$), smallest commercial RCP diameter `rcp_diameter_mm` satisfying the manual's Manning freeboard & velocity criteria, and installed trunk cost `pipe_capex_usd` (including deep-trench shoring where applicable).\n"
    "3. Update `Pipe_Hydraulics` and `Capital_Summary` (`B4`=`sum_peak_q_cms`, `B5`=`total_pipe_capex_usd`, `B6`=`permit_authority_code`, preserving `LandUse_Runoff` and `B2:B3`!) in `/workspace/watershed/Watershed_Capital_Model.xlsx`, and export `/workspace/watershed/Watershed_Capital_Schedule.pdf`.\n"
    "4. Write `/workspace/watershed/hydraulic_design_summary.json` with:\n"
    "   - `permit_authority_code`, `sum_peak_q_cms`, `total_pipe_capex_usd`\n"
    "   - `reaches`: mapping `SC-01`..`SC-06` -> `{\"tc_min\": ..., \"intensity_mm_hr\": ..., \"peak_q_cms\": ..., \"rcp_diameter_mm\": ..., \"pipe_capex_usd\": ...}`\n"
)


def _box_wkt(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def compute_watershed_oracle() -> dict[str, Any]:
    from osgeo import ogr, osr

    s_src = osr.SpatialReference()
    s_src.ImportFromEPSG(4326)
    s_src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    s_dst = osr.SpatialReference()
    s_dst.ImportFromEPSG(32618)
    s_dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s_src, s_dst)

    wl_union = ogr.Geometry(ogr.wkbMultiPolygon)
    for _wid, x0, y0, x1, y1 in WETLAND_BOXES:
        g = ogr.CreateGeometryFromWkt(_box_wkt(x0, y0, x1, y1))
        g.Transform(ct)
        wl_union.AddGeometry(g)
    wl_geom = wl_union.UnionCascaded()

    sub_out: dict[str, dict[str, Any]] = {}
    reaches_out: dict[str, dict[str, Any]] = {}
    clean_features: list[dict[str, Any]] = []

    tot_ha = 0.0
    weighted_c_num = 0.0
    sum_qp = 0.0
    tot_capex = 0.0

    for sid, x0, y0, x1, y1, lu, nhsg, comp, udrain, imp_pct, disconn_pct, flen, edrop, pslope, plen, inv_d in SUBCATCHMENTS_RAW:
        g = ogr.CreateGeometryFromWkt(_box_wkt(x0, y0, x1, y1))
        g.Transform(ct)
        diff_g = g.Difference(wl_geom)
        dev_ha = round(diff_g.GetArea() / 10000.0, 3)
        if int(comp) == 1:
            eff_hsg = "D"
        elif "/" in str(nhsg):
            drained_g, undrained_g = str(nhsg).split("/", 1)
            eff_hsg = drained_g if int(udrain) == 1 else undrained_g
        else:
            eff_hsg = str(nhsg)
        perv_c = PERVIOUS_C_TABLE[lu][eff_hsg]
        conn_imp_frac = max(0.0, (imp_pct - disconn_pct) / 100.0)
        disc_imp_frac = disconn_pct / 100.0
        perv_frac = max(0.0, 1.0 - imp_pct / 100.0)
        disc_c = 0.50 * 0.92 + 0.50 * perv_c
        comp_c = round(conn_imp_frac * 0.92 + disc_imp_frac * disc_c + perv_frac * perv_c, 3)

        tot_ha += dev_ha
        weighted_c_num += dev_ha * comp_c
        sub_out[sid] = {
            "developable_area_ha": dev_ha,
            "effective_hsg": eff_hsg,
            "composite_c": comp_c,
        }
        clean_features.append(
            {
                "type": "Feature",
                "properties": {
                    "subcatchment_id": sid,
                    "developable_area_ha": dev_ha,
                    "effective_hsg": eff_hsg,
                    "composite_c": comp_c,
                },
                "geometry": json.loads(diff_g.ExportToJson()),
            }
        )

        s_ov = edrop / flen
        tc_raw = 0.01947 * (flen ** 0.77) * (s_ov ** -0.385)
        tc_min = round(max(5.0, tc_raw), 2)
        intens = round((IDF_A / ((tc_min + IDF_B) ** IDF_C)) * CLIMATE_FACTOR_100YR, 2)
        qp = round(0.002778 * comp_c * intens * dev_ha, 3)

        chosen_d = 1500
        for d_mm in sorted(RCP_COST_PER_M):
            d_m = d_mm / 1000.0
            area_p = math.pi * (d_m ** 2) / 4.0
            r_hyd = d_m / 4.0
            q_full = (1.0 / 0.013) * area_p * (r_hyd ** (2.0 / 3.0)) * (pslope ** 0.5)
            v_full = q_full / area_p
            if q_full >= 1.15 * qp and v_full >= 0.90:
                chosen_d = d_mm
                break
        shoring_mult = 1.18 if inv_d > 3.5 else 1.00
        capex = round(plen * RCP_COST_PER_M[chosen_d] * shoring_mult, 2)
        sum_qp += qp
        tot_capex += capex
        reaches_out[sid] = {
            "tc_min": tc_min,
            "intensity_mm_hr": intens,
            "peak_q_cms": qp,
            "rcp_diameter_mm": chosen_d,
            "pipe_capex_usd": capex,
        }

    tot_ha_r = round(tot_ha, 3)
    aw_c = round(weighted_c_num / tot_ha, 3)
    return {
        "permit_authority_code": PORTAL_PERMIT_CODE,
        "total_developable_ha": tot_ha_r,
        "area_weighted_c": aw_c,
        "subcatchments": sub_out,
        "sum_peak_q_cms": round(sum_qp, 3),
        "total_pipe_capex_usd": round(tot_capex, 2),
        "reaches": reaches_out,
        "clean_geojson": {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}},
            "features": clean_features,
        },
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    ws = workspace_root / "shared" / "watershed"
    (ws / "specs").mkdir(parents=True, exist_ok=True)

    sub_gj = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
        "features": [
            {
                "type": "Feature",
                "properties": {"subcatchment_id": r[0], "land_use": r[5]},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[r[1], r[2]], [r[3], r[2]], [r[3], r[4]], [r[1], r[4]], [r[1], r[2]]]],
                },
            }
            for r in SUBCATCHMENTS_RAW
        ],
    }
    wl_gj = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
        "features": [
            {
                "type": "Feature",
                "properties": {"wetland_id": wid, "class": "Class_I_Protected"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
                },
            }
            for wid, x0, y0, x1, y1 in WETLAND_BOXES
        ],
    }
    write_json(ws / "subcatchments_wgs84.geojson", sub_gj)
    write_json(ws / "wetland_buffers_wgs84.geojson", wl_gj)

    db_p = ws / "soil_survey.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute(
        "CREATE TABLE parcels_soil (subcatchment_id TEXT PRIMARY KEY, land_use TEXT, native_hsg TEXT, "
        "compacted_industrial_fill INTEGER, underdrain_installed INTEGER, total_impervious_pct REAL, disconnected_roof_pct REAL)"
    )
    con.execute(
        "CREATE TABLE hydraulic_reaches (subcatchment_id TEXT PRIMARY KEY, overland_flow_length_m REAL, "
        "overland_elev_drop_m REAL, pipe_slope_m_m REAL, pipe_length_m REAL, avg_invert_depth_m REAL)"
    )
    for r in SUBCATCHMENTS_RAW:
        con.execute("INSERT INTO parcels_soil VALUES (?,?,?,?,?,?,?)", (r[0], r[5], r[6], r[7], r[8], r[9], r[10]))
        con.execute("INSERT INTO hydraulic_reaches VALUES (?,?,?,?,?,?)", (r[0], r[11], r[12], r[13], r[14], r[15]))
    con.commit()
    con.close()

    write_multisheet_xlsx(
        ws / "Watershed_Capital_Model.xlsx",
        [
            (
                "LandUse_Runoff",
                [
                    ["Subcatchment_ID", "Developable_Area_Ha", "Effective_HSG", "Composite_C"],
                    *[[r[0], 0.0, "TBD", 0.0] for r in SUBCATCHMENTS_RAW],
                    ["TOTAL_OR_WEIGHTED", 0.0, "", 0.0],
                ],
            ),
            (
                "Pipe_Hydraulics",
                [
                    ["Subcatchment_ID", "Tc_Min", "Intensity_mm_hr", "Peak_Q_cms", "RCP_Diameter_mm", "Pipe_CAPEX_USD"],
                    *[[r[0], 0.0, 0.0, 0.0, 0, 0.0] for r in SUBCATCHMENTS_RAW],
                    ["SUM_TOTALS", "", "", 0.0, "", 0.0],
                ],
            ),
            (
                "Capital_Summary",
                [
                    ["Metric", "Value"],
                    ["Total_Developable_Ha", 0.0],
                    ["Area_Weighted_C", 0.0],
                    ["Sum_Peak_Q_cms", 0.0],
                    ["Total_Pipe_CAPEX_USD", 0.0],
                    ["Permit_Authority_Code", "PENDING"],
                ],
            ),
        ],
    )

    write_pdf_manual(
        ws / "specs" / "Stormwater_Design_Manual.pdf",
        "Municipal Stormwater Drainage & GIS Submission Manual (2026)",
        [
            (
                "1. Coordinate System & Protected Class-I Wetland Exclusion",
                [
                    "All municipal drainage submissions must reproject WGS84 (EPSG:4326) layers into NAD83 / WGS84 UTM Zone 18N (EPSG:32618, planar meters).",
                    "Subtract (geometric difference) all polygons in wetland_buffers_wgs84.geojson from subcatchments_wgs84.geojson in EPSG:32618 before computing developable_area_ha = round(area_m2 / 10000.0, 3).",
                ],
            ),
            (
                "2. Compacted Urban Fill Soil Override & Composite Rational C",
                [
                    "Compacted industrial fill (compacted_industrial_fill = 1) always overrides soil classification to effective_hsg = 'D'. Otherwise, for NRCS dual soil groups ('B/D' or 'C/D'), assign the drained first letter ('B' or 'C') ONLY when underdrain_installed = 1, and assign undrained 'D' when underdrain_installed = 0.",
                    "Partition total_impervious_pct into connected impervious (total_impervious_pct - disconnected_roof_pct, using C_imp = 0.92) and disconnected rooftop runoff (disconnected_roof_pct, credited at the 50/50 blend 0.50*0.92 + 0.50*C_perv), with the remaining pervious fraction (100 - total_impervious_pct)% at C_perv(land_use, effective_hsg). Round composite_c to 3 decimals.",
                ],
            ),
            (
                "3. Kirpich Time of Concentration & 100-Yr Climate-Adjusted IDF",
                [
                    "Overland slope S_ov = overland_elev_drop_m / overland_flow_length_m. Raw Kirpich time (minutes): tc_raw = 0.01947 * (L ** 0.77) * (S_ov ** -0.385). Enforce the municipal inlet floor: tc_min = round(max(5.0, tc_raw), 2).",
                    "Use the 100-year climate-adjusted IDF curve from the Metro Stormwater Portal (do not use the 10-yr or 25-yr curves!): intensity_mm_hr = round((a / ((tc_min + b) ** c)) * climate_factor, 2).",
                    "Rational peak discharge (m^3/s): peak_q_cms = round(0.002778 * composite_c * intensity_mm_hr * developable_area_ha, 3).",
                ],
            ),
            (
                "4. Manning Circular Concrete Pipe (RCP) Freeboard Sizing",
                [
                    "Use Manning roughness n = 0.013 for reinforced concrete pipe. For circular diameter D_m = D_mm / 1000, full-flow capacity Q_full = (1 / 0.013) * (pi * D_m^2 / 4) * ((D_m / 4) ** (2/3)) * sqrt(pipe_slope_m_m).",
                    "Select the smallest commercial RCP diameter D_mm satisfying BOTH Q_full >= 1.15 * peak_q_cms (15% freeboard) AND full-flow self-cleansing velocity V_full = Q_full / A_pipe >= 0.90 m/s. Reaches with avg_invert_depth_m > 3.5 m require OSHA trench shoring (+18% multiplier on installed unit cost per meter).",
                ],
            ),
        ],
    )

    (tickets_root / "gis_landuse_analyst").mkdir(parents=True, exist_ok=True)
    (tickets_root / "hydraulic_basin_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "gis_landuse_analyst" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "hydraulic_basin_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_view": "landuse", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw03_sess" in ck) and (ck["aw03_sess"].value == tok)

        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", hdrs: list[tuple[str, str]] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for hk, hv in (hdrs or []):
                self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(200, b'{"ok":true}', "application/json")
                return
            if parsed.path == "/auth":
                if (qs.get("token") or [""])[0] == tok:
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw03_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Authenticated Metro Stormwater Session Required (Use open Chromium)</h3>")
                return
            if parsed.path == "/view":
                v = (qs.get("tab") or ["landuse"])[0]
                with lock:
                    if v in ("landuse", "idf") and v != state["active_view"]:
                        state["active_view"] = v
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return

            with lock:
                cur = state["active_view"]
            if cur == "landuse":
                rows = "".join(
                    f"<tr><td>{lu}</td><td>{mp['A']}</td><td>{mp['B']}</td><td>{mp['C']}</td><td>{mp['D']}</td></tr>"
                    for lu, mp in PERVIOUS_C_TABLE.items()
                )
                body_html = f"""
                <h2>Pervious Rational Runoff Coefficients C_perv(land_use, HSG)</h2>
                <p><b>Permit Authority Code:</b> <code>{PORTAL_PERMIT_CODE}</code> | <b>Impervious C_imp:</b> <code>0.92</code></p>
                <table border="1" cellpadding="8" style="border-collapse:collapse;margin-top:12px;">
                  <tr><th>Land Use</th><th>HSG A</th><th>HSG B</th><th>HSG C</th><th>HSG D</th></tr>
                  {rows}
                </table>"""
            else:
                rcp_rows = "".join(f"<tr><td>{d}</td><td>${u:.2f}</td></tr>" for d, u in sorted(RCP_COST_PER_M.items()))
                body_html = f"""
                <h2>100-Yr Climate-Adjusted NOAA IDF &amp; Commercial RCP Unit Cost Schedule</h2>
                <p><b>Permit Authority Code:</b> <code>{PORTAL_PERMIT_CODE}</code></p>
                <p style="margin-top:8px;"><b>100-Yr IDF Parameters:</b> <code>a = {IDF_A}</code>, <code>b = {IDF_B}</code>, <code>c = {IDF_C}</code>, <code>climate_factor = {CLIMATE_FACTOR_100YR}</code> (Note: unadjusted historical 25-yr uses a=1920, factor=1.00 — DO NOT USE for Capital Plan).</p>
                <table border="1" cellpadding="6" style="border-collapse:collapse;margin-top:12px;">
                  <tr><th>Commercial RCP Diameter (mm)</th><th>Installed Unit Cost (USD / m)</th></tr>
                  {rcp_rows}
                </table>"""

            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Metro Stormwater Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;color:#0f172a;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Metro Stormwater Engineering Portal ({cur.upper()})</h1>
            <div class="nav">
              <a href="/view?tab=landuse">Pervious C &amp; Soil Compaction</a>
              <a href="/view?tab=idf">100-Yr Climate IDF &amp; RCP Unit Costs</a>
            </div>
            <div class="card">{body_html}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1240, 840))
    ws = workspace_root / "shared" / "watershed"
    if "gis_landuse_analyst" in roles:
        launch_desktop_app_as_user(
            f"nohup qgis --nologo '{ws / 'subcatchments_wgs84.geojson'}' '{ws / 'wetland_buffers_wgs84.geojson'}' >/tmp/aw03_qgis.log 2>&1 </dev/null &",
            wait_s=3.5,
        )
    if roles & {"gis_landuse_analyst", "hydraulic_basin_eng"}:
        launch_desktop_app_as_user(
            f"nohup libreoffice --norestore --nologo --nofirststartwizard '{ws / 'Watershed_Capital_Model.xlsx'}' >/tmp/aw03_calc.log 2>&1 </dev/null &",
            wait_s=2.2,
        )


def _merge_capital_summary(xlsx_path: Path, updates: dict[str, Any]) -> None:
    book = evaluate_xlsx_isolated(xlsx_path)
    cur = {
        "Total_Developable_Ha": cell_float(book, "Capital_Summary", "B2") or 0.0,
        "Area_Weighted_C": cell_float(book, "Capital_Summary", "B3") or 0.0,
        "Sum_Peak_Q_cms": cell_float(book, "Capital_Summary", "B4") or 0.0,
        "Total_Pipe_CAPEX_USD": cell_float(book, "Capital_Summary", "B5") or 0.0,
        "Permit_Authority_Code": str(((book.get("Capital_Summary") or {}).get("B6") or {}).get("value") or "PENDING"),
    }
    cur.update(updates)
    rows = [
        ["Metric", "Value"],
        ["Total_Developable_Ha", cur["Total_Developable_Ha"]],
        ["Area_Weighted_C", cur["Area_Weighted_C"]],
        ["Sum_Peak_Q_cms", cur["Sum_Peak_Q_cms"]],
        ["Total_Pipe_CAPEX_USD", cur["Total_Pipe_CAPEX_USD"]],
        ["Permit_Authority_Code", cur["Permit_Authority_Code"]],
    ]
    update_single_sheet_xlsx(xlsx_path, "Capital_Summary", rows)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    ws = workspace_root / "shared" / "watershed"
    xlsx_p = ws / "Watershed_Capital_Model.xlsx"
    ora = compute_watershed_oracle()
    if role == "gis_landuse_analyst":
        write_json(ws / "subcatchments_utm18n_clean.geojson", ora["clean_geojson"])
        lu_rows = [["Subcatchment_ID", "Developable_Area_Ha", "Effective_HSG", "Composite_C"]]
        for sid, info in ora["subcatchments"].items():
            lu_rows.append([sid, info["developable_area_ha"], info["effective_hsg"], info["composite_c"]])
        lu_rows.append(["TOTAL_OR_WEIGHTED", ora["total_developable_ha"], "", ora["area_weighted_c"]])
        if cooperative:
            with resource_lock("aw03_xlsx"):
                update_single_sheet_xlsx(xlsx_p, "LandUse_Runoff", lu_rows)
                _merge_capital_summary(
                    xlsx_p,
                    {
                        "Total_Developable_Ha": ora["total_developable_ha"],
                        "Area_Weighted_C": ora["area_weighted_c"],
                        "Permit_Authority_Code": PORTAL_PERMIT_CODE,
                    },
                )
                if (ws / "Watershed_Capital_Schedule.pdf").is_file():
                    convert_to_pdf_headless(xlsx_p, ws / "Watershed_Capital_Schedule.pdf")
        else:
            write_multisheet_xlsx(xlsx_p, [("LandUse_Runoff", lu_rows)])
        write_json(
            ws / "gis_delineation_summary.json",
            {
                "permit_authority_code": PORTAL_PERMIT_CODE,
                "crs_epsg": 32618,
                "total_developable_ha": ora["total_developable_ha"],
                "area_weighted_c": ora["area_weighted_c"],
                "subcatchments": ora["subcatchments"],
            },
        )
    elif role == "hydraulic_basin_eng":
        hy_rows = [["Subcatchment_ID", "Tc_Min", "Intensity_mm_hr", "Peak_Q_cms", "RCP_Diameter_mm", "Pipe_CAPEX_USD"]]
        for sid, info in ora["reaches"].items():
            hy_rows.append([sid, info["tc_min"], info["intensity_mm_hr"], info["peak_q_cms"], info["rcp_diameter_mm"], info["pipe_capex_usd"]])
        hy_rows.append(["SUM_TOTALS", "", "", ora["sum_peak_q_cms"], "", ora["total_pipe_capex_usd"]])
        if cooperative:
            with resource_lock("aw03_xlsx"):
                update_single_sheet_xlsx(xlsx_p, "Pipe_Hydraulics", hy_rows)
                _merge_capital_summary(
                    xlsx_p,
                    {
                        "Sum_Peak_Q_cms": ora["sum_peak_q_cms"],
                        "Total_Pipe_CAPEX_USD": ora["total_pipe_capex_usd"],
                        "Permit_Authority_Code": PORTAL_PERMIT_CODE,
                    },
                )
                convert_to_pdf_headless(xlsx_p, ws / "Watershed_Capital_Schedule.pdf")
        else:
            write_multisheet_xlsx(xlsx_p, [("Pipe_Hydraulics", hy_rows)])
            convert_to_pdf_headless(xlsx_p, ws / "Watershed_Capital_Schedule.pdf")
        write_json(
            ws / "hydraulic_design_summary.json",
            {
                "permit_authority_code": PORTAL_PERMIT_CODE,
                "sum_peak_q_cms": ora["sum_peak_q_cms"],
                "total_pipe_capex_usd": ora["total_pipe_capex_usd"],
                "reaches": ora["reaches"],
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("gis_landuse_analyst", workspace_root, cooperative=False)
    solve_role("hydraulic_basin_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "gis_landuse_analyst", workspace_root, True)
        fb = pool.submit(solve_role, "hydraulic_basin_eng", workspace_root, True)
        fa.result()
        fb.result()
    ws = workspace_root / "shared" / "watershed"
    with resource_lock("aw03_xlsx"):
        convert_to_pdf_headless(ws / "Watershed_Capital_Model.xlsx", ws / "Watershed_Capital_Schedule.pdf")


def _check_utm_geojson(path: Path, ora: dict[str, Any]) -> tuple[bool, bool]:
    from osgeo import ogr

    if not path.is_file():
        return False, False
    try:
        ds = ogr.Open(str(path))
        if ds is None:
            return False, False
        lyr = ds.GetLayer(0)
        if lyr is None or lyr.GetFeatureCount() != 6:
            return False, False
        srs = lyr.GetSpatialRef()
        crs_txt = (srs.ExportToWkt() if srs else "") + path.read_text(encoding="utf-8", errors="replace")[:500]
        crs_ok = ("32618" in crs_txt) or ("UTM zone 18N" in crs_txt)
        areas_ok = True
        for feat in lyr:
            geom = feat.GetGeometryRef()
            if geom is None:
                areas_ok = False
                break
            env = geom.GetEnvelope()
            # UTM 18N Easting around 565,000..575,000 m, Northing around 4,505,000..4,515,000 m
            if not (500000.0 <= env[0] <= 650000.0 and 4400000.0 <= env[2] <= 4600000.0):
                crs_ok = False
            sid = feat.GetField("subcatchment_id") if feat.GetFieldIndex("subcatchment_id") >= 0 else None
            if sid in ora["subcatchments"]:
                ha = geom.GetArea() / 10000.0
                if abs(ha - ora["subcatchments"][sid]["developable_area_ha"]) > 0.15:
                    areas_ok = False
        return crs_ok, areas_ok
    except Exception:
        return False, False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    ws = workspace_root / "shared" / "watershed"
    ora = compute_watershed_oracle()
    ja = read_json_safe(ws / "gis_delineation_summary.json")
    jb = read_json_safe(ws / "hydraulic_design_summary.json")
    book = evaluate_xlsx_isolated(ws / "Watershed_Capital_Model.xlsx")
    pdf_txt = extract_pdf_text(ws / "Watershed_Capital_Schedule.pdf")
    crs_ok, geom_areas_ok = _check_utm_geojson(ws / "subcatchments_utm18n_clean.geojson", ora)

    subs_got = ja.get("subcatchments") if isinstance(ja.get("subcatchments"), dict) else {}
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_utm_crs", crs_ok, 2.0, "subcatchments_utm18n_clean.geojson missing or not in EPSG:32618 meter coordinates"),
        ("a_wetland_clipped_geom", geom_areas_ok, 2.0, "subcatchments_utm18n_clean.geojson polygon areas do not reflect Class-I wetland clipping"),
        ("a_permit_code", str(ja.get("permit_authority_code", "")).strip() == PORTAL_PERMIT_CODE, 1.2, "permit_authority_code missing/wrong"),
        (
            "a_tot_ha",
            isinstance(ja.get("total_developable_ha"), (int, float))
            and abs(float(ja["total_developable_ha"]) - ora["total_developable_ha"]) <= 0.25,
            1.8,
            f"total_developable_ha mismatch (expected {ora['total_developable_ha']})",
        ),
        (
            "a_aw_c",
            isinstance(ja.get("area_weighted_c"), (int, float))
            and abs(float(ja["area_weighted_c"]) - ora["area_weighted_c"]) <= 0.012,
            1.8,
            f"area_weighted_c mismatch (expected {ora['area_weighted_c']}, check compacted fill HSG->D)",
        ),
    ]
    for sid, exp_s in ora["subcatchments"].items():
        got_s = subs_got.get(sid) if isinstance(subs_got.get(sid), dict) else {}
        ok_s = (
            str(got_s.get("effective_hsg", "")).strip() == exp_s["effective_hsg"]
            and isinstance(got_s.get("composite_c"), (int, float))
            and abs(float(got_s["composite_c"]) - exp_s["composite_c"]) <= 0.012
            and isinstance(got_s.get("developable_area_ha"), (int, float))
            and abs(float(got_s["developable_area_ha"]) - exp_s["developable_area_ha"]) <= 0.15
        )
        checks_a.append((f"a_{sid.lower()}", ok_s, 1.2, f"{sid} GIS area/HSG/C mismatch"))
    checks_a.append(
        (
            "a_xlsx_landuse",
            (cell_float(book, "LandUse_Runoff", "B8") is not None)
            and abs(float(cell_float(book, "LandUse_Runoff", "B8") or 0.0) - ora["total_developable_ha"]) <= 0.3,
            1.5,
            "Watershed_Capital_Model.xlsx LandUse_Runoff!B8 total_developable_ha missing/wrong",
        )
    )

    reaches_got = jb.get("reaches") if isinstance(jb.get("reaches"), dict) else {}
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_permit_code", str(jb.get("permit_authority_code", "")).strip() == PORTAL_PERMIT_CODE, 1.0, "permit_authority_code missing/wrong"),
        (
            "b_sum_qp",
            isinstance(jb.get("sum_peak_q_cms"), (int, float))
            and abs(float(jb["sum_peak_q_cms"]) - ora["sum_peak_q_cms"]) <= 0.18,
            2.0,
            f"sum_peak_q_cms mismatch (expected {ora['sum_peak_q_cms']})",
        ),
        (
            "b_tot_capex",
            isinstance(jb.get("total_pipe_capex_usd"), (int, float))
            and abs(float(jb["total_pipe_capex_usd"]) - ora["total_pipe_capex_usd"]) <= 500.0,
            2.0,
            f"total_pipe_capex_usd mismatch (expected {ora['total_pipe_capex_usd']})",
        ),
    ]
    for sid, exp_r in ora["reaches"].items():
        got_r = reaches_got.get(sid) if isinstance(reaches_got.get(sid), dict) else {}
        ok_d = got_r.get("rcp_diameter_mm") == exp_r["rcp_diameter_mm"]
        ok_q = (
            isinstance(got_r.get("tc_min"), (int, float))
            and abs(float(got_r["tc_min"]) - exp_r["tc_min"]) <= 0.25
            and isinstance(got_r.get("peak_q_cms"), (int, float))
            and abs(float(got_r["peak_q_cms"]) - exp_r["peak_q_cms"]) <= 0.06
        )
        checks_b.append((f"b_{sid.lower()}_hyd", ok_q, 1.0, f"{sid} tc_min/peak_q_cms mismatch (check 5-min floor & climate factor)"))
        checks_b.append((f"b_{sid.lower()}_rcp", ok_d, 1.0, f"{sid} RCP diameter mismatch (expected {exp_r['rcp_diameter_mm']} mm)"))

    checks_b.extend(
        [
            (
                "b_xlsx_hyd",
                (cell_float(book, "Pipe_Hydraulics", "F8") is not None)
                and abs(float(cell_float(book, "Pipe_Hydraulics", "F8") or 0.0) - ora["total_pipe_capex_usd"]) <= 500.0,
                1.5,
                "Watershed_Capital_Model.xlsx Pipe_Hydraulics!F8 total CAPEX missing/wrong",
            ),
            ("b_schedule_pdf", len(pdf_txt.strip()) > 60 and PORTAL_PERMIT_CODE in pdf_txt, 1.2, "Watershed_Capital_Schedule.pdf missing permit code or tables"),
        ]
    )

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_workbook_preserves_all_3_sheets",
            (cell_float(book, "LandUse_Runoff", "B8") is not None)
            and abs(float(cell_float(book, "LandUse_Runoff", "B8") or 0.0) - ora["total_developable_ha"]) <= 0.3
            and (cell_float(book, "Pipe_Hydraulics", "F8") is not None)
            and abs(float(cell_float(book, "Pipe_Hydraulics", "F8") or 0.0) - ora["total_pipe_capex_usd"]) <= 500.0,
            2.0,
            "Shared Watershed_Capital_Model.xlsx lost either LandUse_Runoff or Pipe_Hydraulics sheet due to concurrent overwrite",
        ),
        (
            "j_capital_summary_complete",
            (cell_float(book, "Capital_Summary", "B2") is not None)
            and abs(float(cell_float(book, "Capital_Summary", "B2") or 0.0) - ora["total_developable_ha"]) <= 0.3
            and (cell_float(book, "Capital_Summary", "B5") is not None)
            and abs(float(cell_float(book, "Capital_Summary", "B5") or 0.0) - ora["total_pipe_capex_usd"]) <= 500.0,
            2.0,
            "Shared Capital_Summary sheet lacks merged GIS area + hydraulic CAPEX metrics",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"gis_landuse_analyst": TICKET_A, "hydraulic_basin_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
