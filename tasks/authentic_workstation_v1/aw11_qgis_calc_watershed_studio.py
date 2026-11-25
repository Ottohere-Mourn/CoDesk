"""AW-11: Live QGIS & LibreOffice Calc Municipal Drainage Filing with Raster IDF Chart."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    evaluate_xlsx_isolated,
    launch_studio_app,
    read_json_safe,
    resource_lock,
    update_single_sheet_xlsx,
    write_json,
    write_multisheet_xlsx,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-11",
    "slug": "qgis_calc_watershed_studio",
    "title": "Live QGIS & LibreOffice Calc Municipal Drainage Filing with Raster IDF Chart",
    "domain": "Civil GIS & Stormwater Filing (QGIS 3.22 + GDAL/OGR + Live LibreOffice Calc + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19611,
    "roles": ("gis_delineation_eng", "stormwater_trunk_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
    "mount_studio_ro": True,
}

FILING_STAMP = "DEP-BASIN-2026-412"
BASINS = [
    ("BSN-1", -74.1600, 40.7400, -74.1580, 40.7416, 0.72, 180.0, 4.5, 0.0060, 240.0),
    ("BSN-2", -74.1580, 40.7400, -74.1556, 40.7418, 0.58, 320.0, 4.8, 0.0045, 310.0),
    ("BSN-3", -74.1600, 40.7416, -74.1575, 40.7434, 0.66, 260.0, 5.2, 0.0050, 275.0),
    ("BSN-4", -74.1575, 40.7418, -74.1550, 40.7436, 0.48, 410.0, 5.0, 0.0040, 360.0),
]
WETLAND_BOX = (-74.1586, 40.7410, -74.1572, 40.7422)
PIPE_COSTS = {450: 420.0, 525: 495.0, 600: 590.0, 750: 760.0, 900: 960.0, 1050: 1190.0, 1200: 1450.0}
IDF_NUM = 2650.0
IDF_OFFSET = 12.0
IDF_EXP = 0.80
IDF_CLIM = 1.15
DETENTION_UNIT_COST_USD_PER_HA_C = 18500.0

TICKET_A = (
    "# Work Order — GIS Basin Delineation Engineer (`gis_delineation_eng`)\n\n"
    "Complete the `EPSG:32618` wetland-clipped basin delineation in `/workspace/drainage` and record the official basin filing values in the live **LibreOffice Calc** workbook open on the desktop (`/srv/studio_project/Municipal_Drainage_Filing.xlsx`):\n\n"
    "1. Review `/workspace/drainage/specs/Basin_Filing_Manual.pdf`, inspect `/workspace/drainage/basins_wgs84.geojson` and `wetland_setback_wgs84.geojson` (open in **QGIS** on the desktop), and view the **DEP Basin Portal** in Chromium (`http://127.0.0.1:19611`, `Basin Fee & CRS Schedule` tab).\n"
    "2. Reproject both GeoJSON layers to `EPSG:32618` (UTM Zone 18N, meters), subtract `wetland_setback_wgs84.geojson` from `basins_wgs84.geojson`, save `/workspace/drainage/basins_utm18n_clipped.geojson`, and compute `developable_ha` (3 decimals) per basin, `total_developable_ha`, and `effective_impervious_ha = round(sum(developable_ha_i * runoff_c_i), 3)`, writing `/workspace/drainage/gis_basin_report.json` (`filing_stamp`, `total_developable_ha`, `effective_impervious_ha`, `basins`).\n"
    "3. In the open **LibreOffice Calc** window (`/srv/studio_project/Municipal_Drainage_Filing.xlsx`), enter `total_developable_ha` into `Catchment_Areas!B2`, `effective_impervious_ha` into `Catchment_Areas!B3`, AND `effective_impervious_ha` into `Filing_Rollup!B2`, then save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Stormwater Trunk Sizing Engineer (`stormwater_trunk_eng`)\n\n"
    "Complete the 100-year trunk RCP sizing in `/workspace/drainage` using the visual IDF chart in Chromium and record the official trunk CAPEX in the live **LibreOffice Calc** workbook open on the desktop (`/srv/studio_project/Municipal_Drainage_Filing.xlsx`):\n\n"
    "1. Review `/workspace/drainage/specs/Basin_Filing_Manual.pdf`, query `/workspace/drainage/reach_hydraulics.sqlite`, and inspect the **DEP Basin Portal** in Chromium (`http://127.0.0.1:19611`, `Visual IDF Curve & Pipe Cost Chart` tab — read the IDF formula parameters and pipe unit costs directly from the chart image!).\n"
    "2. Using the `EPSG:32618` wetland-clipped basin areas for `BSN-1`..`BSN-4`, compute Kirpich `tc_min` (`max(5.0, raw_tc)`), storm intensity `intensity_mm_hr`, Rational `peak_q_cms`, smallest commercial RCP diameter `rcp_mm` (`Q_full >= 1.15 * peak_q_cms`, Manning `n = 0.013`), and `total_trunk_capex_usd`, writing `/workspace/drainage/trunk_sizing_report.json` (`filing_stamp`, `sum_peak_q_cms`, `total_trunk_capex_usd`, `trunks`).\n"
    "3. In the open **LibreOffice Calc** window (`/srv/studio_project/Municipal_Drainage_Filing.xlsx`), enter `sum_peak_q_cms` into `Trunk_Pipes!B2`, `total_trunk_capex_usd` into `Trunk_Pipes!B3`, AND `total_trunk_capex_usd` into `Filing_Rollup!B3`, then save (`Ctrl+S`).\n"
)


def _poly_wkt(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def compute_aw11_oracle() -> dict[str, Any]:
    from osgeo import ogr, osr

    s4326 = osr.SpatialReference()
    s4326.ImportFromEPSG(4326)
    s4326.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    s32618 = osr.SpatialReference()
    s32618.ImportFromEPSG(32618)
    s32618.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s4326, s32618)

    wl = ogr.CreateGeometryFromWkt(_poly_wkt(*WETLAND_BOX))
    wl.Transform(ct)

    basins_map = {}
    trunks_map = {}
    feats = []
    tot_ha = 0.0
    eff_imp_ha = 0.0
    sum_q = 0.0
    tot_capex = 0.0

    for bid, x0, y0, x1, y1, rc, flen, edrop, pslope, plen in BASINS:
        g = ogr.CreateGeometryFromWkt(_poly_wkt(x0, y0, x1, y1))
        g.Transform(ct)
        dg = g.Difference(wl)
        ha = round(dg.GetArea() / 10000.0, 3)
        tot_ha += ha
        eff_imp_ha += ha * rc
        basins_map[bid] = {"developable_ha": ha, "runoff_c": rc}
        feats.append({"type": "Feature", "properties": {"basin_id": bid, "developable_ha": ha, "runoff_c": rc}, "geometry": json.loads(dg.ExportToJson())})

        tc = round(max(5.0, 0.01947 * (flen ** 0.77) * ((edrop / flen) ** -0.385)), 2)
        inten = round((IDF_NUM / ((tc + IDF_OFFSET) ** IDF_EXP)) * IDF_CLIM, 2)
        qp = round(0.002778 * rc * inten * ha, 3)
        chosen = 1200
        for dm in sorted(PIPE_COSTS):
            d_m = dm / 1000.0
            qf = (1.0 / 0.013) * (math.pi * d_m * d_m / 4.0) * ((d_m / 4.0) ** (2.0 / 3.0)) * (pslope ** 0.5)
            if qf >= 1.15 * qp:
                chosen = dm
                break
        cost = round(plen * PIPE_COSTS[chosen], 2)
        sum_q += qp
        tot_capex += cost
        trunks_map[bid] = {"tc_min": tc, "intensity_mm_hr": inten, "peak_q_cms": qp, "rcp_mm": chosen, "capex_usd": cost}

    eff_imp_r = round(eff_imp_ha, 3)
    tot_capex_r = round(tot_capex, 2)
    combined_fee_and_capex = round(eff_imp_r * DETENTION_UNIT_COST_USD_PER_HA_C + tot_capex_r, 2)
    return {
        "filing_stamp": FILING_STAMP,
        "total_developable_ha": round(tot_ha, 3),
        "effective_impervious_ha": eff_imp_r,
        "basins": basins_map,
        "sum_peak_q_cms": round(sum_q, 3),
        "total_trunk_capex_usd": tot_capex_r,
        "combined_program_budget_usd": combined_fee_and_capex,
        "trunks": trunks_map,
        "geojson": {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}}, "features": feats},
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    dr = workspace_root / "shared" / "drainage"
    (dr / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "shared" / ".studio_seed"
    seed.mkdir(parents=True, exist_ok=True)

    write_json(
        dr / "basins_wgs84.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"basin_id": r[0], "runoff_c": r[5]}, "geometry": {"type": "Polygon", "coordinates": [[[r[1], r[2]], [r[3], r[2]], [r[3], r[4]], [r[1], r[4]], [r[1], r[2]]]]}}
                for r in BASINS
            ],
        },
    )
    x0, y0, x1, y1 = WETLAND_BOX
    write_json(
        dr / "wetland_setback_wgs84.geojson",
        {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": "WL-CORE"}, "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}]},
    )
    db_p = dr / "reach_hydraulics.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE reaches (basin_id TEXT PRIMARY KEY, runoff_c REAL, flow_length_m REAL, elev_drop_m REAL, pipe_slope REAL, pipe_length_m REAL)")
    for r in BASINS:
        con.execute("INSERT INTO reaches VALUES (?,?,?,?,?,?)", (r[0], r[5], r[6], r[7], r[8], r[9]))
    con.commit()
    con.close()

    write_multisheet_xlsx(
        seed / "Municipal_Drainage_Filing.xlsx",
        [
            ("Catchment_Areas", [["Metric", "Value"], ["Total_Developable_Ha", 0.0], ["Effective_Impervious_Ha", 0.0]]),
            ("Trunk_Pipes", [["Metric", "Value"], ["Sum_Peak_Q_cms", 0.0], ["Total_Trunk_CAPEX_USD", 0.0]]),
            (
                "Filing_Rollup",
                [
                    ["Line", "Value"],
                    ["Effective_Impervious_Ha", 0.0],
                    ["Total_Trunk_CAPEX_USD", 0.0],
                    ["Combined_Program_Budget_USD", (f"=ROUND(B2*{DETENTION_UNIT_COST_USD_PER_HA_C}+B3,2)", 0.0)],
                ],
            ),
        ],
    )

    write_pdf_manual(
        dr / "specs" / "Basin_Filing_Manual.pdf",
        "Municipal Basin Delineation & Trunk Pipe Filing Manual",
        [
            (
                "1. UTM 18N Wetland Clipping & Effective Impervious Area",
                [
                    "Reproject basins_wgs84.geojson and wetland_setback_wgs84.geojson from EPSG:4326 to EPSG:32618, subtract the wetland polygon, and compute developable_ha (3 decimals) and effective_impervious_ha = round(sum(developable_ha_i * runoff_c_i), 3).",
                ],
            ),
            (
                "2. Visual IDF Chart, Manning Sizing & Live Calc Filing",
                [
                    "Read the 100-year IDF formula coefficients and RCP unit costs ($/m) from the visual engineering chart on the DEP Basin Portal in Chromium. Kirpich tc_min = round(max(5.0, 0.01947 * L^0.77 * (drop/L)^-0.385), 2); Rational peak_q_cms = round(0.002778 * C * I * developable_ha, 3); select smallest RCP diameter with Q_full(n=0.013) >= 1.15 * peak_q_cms.",
                    "Enter final values into the open LibreOffice Calc workbook /srv/studio_project/Municipal_Drainage_Filing.xlsx and save with Ctrl+S.",
                ],
            ),
        ],
    )
    (tickets_root / "gis_delineation_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "stormwater_trunk_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "gis_delineation_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "stormwater_trunk_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def _render_idf_chart_png() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (920, 520), (255, 255, 255))
    drw = ImageDraw.Draw(im)
    try:
        f_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        f_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    except Exception:
        f_lg = f_md = ImageFont.load_default()

    drw.rectangle([0, 0, 920, 52], fill=(15, 23, 42))
    drw.text((20, 14), f"DEP STORMWATER CHART | STAMP: {FILING_STAMP}", fill=(255, 255, 255), font=f_lg)
    drw.text((24, 72), "100-Yr Climate IDF Equation (mm/hr):", fill=(15, 23, 42), font=f_lg)
    drw.rectangle([24, 104, 880, 152], outline=(37, 99, 235), width=2, fill=(239, 246, 255))
    drw.text((38, 118), "I(tc) = [ 2650.0 / (tc + 12.0)^0.80 ] * 1.15   (round to 2 dec)", fill=(30, 58, 138), font=f_md)

    drw.text((24, 178), "Commercial Circular RCP Installed Unit Costs (USD / meter):", fill=(15, 23, 42), font=f_lg)
    y = 214
    for dm, cst in sorted(PIPE_COSTS.items()):
        drw.rectangle([32, y, 520, y + 32], outline=(203, 213, 225), fill=(248, 250, 252))
        drw.text((48, y + 7), f"RCP {dm:4d} mm   --->   ${cst:7.2f} / m", fill=(15, 23, 42), font=f_md)
        y += 35
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    chart_png = _render_idf_chart_png()
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "crs_fee", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw11_sess" in ck) and (ck["aw11_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw11_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 DEP Basin Portal Session Required</h3>")
                return
            if parsed.path == "/chart.png":
                self._send(200, chart_png, "image/png")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["crs_fee"])[0]
                with lock:
                    if t in ("crs_fee", "idf_chart") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "crs_fee":
                body = f"""<h2>Basin Fee &amp; CRS Filing Schedule</h2>
                <p><b>Official Filing Stamp:</b> <code>{FILING_STAMP}</code></p>
                <p><b>Target Projection:</b> <code>EPSG:32618 (UTM Zone 18N)</code> | <b>Detention Fee Rate:</b> <code>${DETENTION_UNIT_COST_USD_PER_HA_C:,.2f} / effective impervious ha</code></p>"""
            else:
                body = """<h2>Visual IDF Curve &amp; Pipe Cost Chart</h2>
                <img src="/chart.png" alt="DEP IDF Chart" style="border:1px solid #94a3b8;border-radius:8px;max-width:100%;"/>"""
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>DEP Basin Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:20px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>DEP Basin Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=crs_fee">Basin Fee &amp; CRS Schedule</a><a href="/tab?id=idf_chart">Visual IDF Curve &amp; Pipe Cost Chart</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1180, 820))
    seed = workspace_root / "shared" / ".studio_seed"
    dr = workspace_root / "shared" / "drainage"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Municipal_Drainage_Filing.xlsx", sp / "Municipal_Drainage_Filing.xlsx")
    if "gis_delineation_eng" in roles:
        launch_studio_app(f"nohup qgis --nologo '{dr / 'basins_wgs84.geojson'}' '{dr / 'wetland_setback_wgs84.geojson'}' >/tmp/aw11_qgis.log 2>&1 </dev/null &", wait_s=3.0)
    launch_studio_app("nohup libreoffice --norestore --nologo --nofirststartwizard '/srv/studio_project/Municipal_Drainage_Filing.xlsx' >/tmp/aw11_calc.log 2>&1 </dev/null &", wait_s=2.5)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    dr = workspace_root / "shared" / "drainage"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Municipal_Drainage_Filing.xlsx"
    ora = compute_aw11_oracle()
    if role == "gis_delineation_eng":
        write_json(dr / "basins_utm18n_clipped.geojson", ora["geojson"])
        write_json(dr / "gis_basin_report.json", {"filing_stamp": FILING_STAMP, "total_developable_ha": ora["total_developable_ha"], "effective_impervious_ha": ora["effective_impervious_ha"], "basins": ora["basins"]})
        if cooperative:
            with resource_lock("aw11_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3_cur = cell_float(bk, "Filing_Rollup", "B3") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Catchment_Areas", [["Metric", "Value"], ["Total_Developable_Ha", ora["total_developable_ha"]], ["Effective_Impervious_Ha", ora["effective_impervious_ha"]]])
                comb = round(ora["effective_impervious_ha"] * DETENTION_UNIT_COST_USD_PER_HA_C + b3_cur, 2)
                update_single_sheet_xlsx(xlsx_p, "Filing_Rollup", [["Line", "Value"], ["Effective_Impervious_Ha", ora["effective_impervious_ha"]], ["Total_Trunk_CAPEX_USD", b3_cur], ["Combined_Program_Budget_USD", (f"=ROUND(B2*{DETENTION_UNIT_COST_USD_PER_HA_C}+B3,2)", comb)]])
        else:
            write_multisheet_xlsx(xlsx_p, [("Catchment_Areas", [["Metric", "Value"], ["Total_Developable_Ha", ora["total_developable_ha"]]])])
    elif role == "stormwater_trunk_eng":
        write_json(dr / "trunk_sizing_report.json", {"filing_stamp": FILING_STAMP, "sum_peak_q_cms": ora["sum_peak_q_cms"], "total_trunk_capex_usd": ora["total_trunk_capex_usd"], "trunks": ora["trunks"]})
        if cooperative:
            with resource_lock("aw11_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2_cur = cell_float(bk, "Filing_Rollup", "B2") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Trunk_Pipes", [["Metric", "Value"], ["Sum_Peak_Q_cms", ora["sum_peak_q_cms"]], ["Total_Trunk_CAPEX_USD", ora["total_trunk_capex_usd"]]])
                comb = round(b2_cur * DETENTION_UNIT_COST_USD_PER_HA_C + ora["total_trunk_capex_usd"], 2)
                update_single_sheet_xlsx(xlsx_p, "Filing_Rollup", [["Line", "Value"], ["Effective_Impervious_Ha", b2_cur], ["Total_Trunk_CAPEX_USD", ora["total_trunk_capex_usd"]], ["Combined_Program_Budget_USD", (f"=ROUND(B2*{DETENTION_UNIT_COST_USD_PER_HA_C}+B3,2)", comb)]])
        else:
            write_multisheet_xlsx(xlsx_p, [("Trunk_Pipes", [["Metric", "Value"], ["Total_Trunk_CAPEX_USD", ora["total_trunk_capex_usd"]]])])
    subprocess.run(["chmod", "-R", "a+rX", str(sp)], capture_output=True, timeout=10)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("gis_delineation_eng", workspace_root, cooperative=False)
    solve_role("stormwater_trunk_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "gis_delineation_eng", workspace_root, True)
        fb = pool.submit(solve_role, "stormwater_trunk_eng", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    from osgeo import ogr

    dr = workspace_root / "shared" / "drainage"
    sp = Path("/srv/studio_project")
    ora = compute_aw11_oracle()
    ja = read_json_safe(dr / "gis_basin_report.json")
    jb = read_json_safe(dr / "trunk_sizing_report.json")
    book = evaluate_xlsx_isolated(sp / "Municipal_Drainage_Filing.xlsx")

    gj_ok = False
    gj_p = dr / "basins_utm18n_clipped.geojson"
    if gj_p.is_file():
        ds = ogr.Open(str(gj_p))
        if ds and ds.GetLayer(0) and ds.GetLayer(0).GetFeatureCount() == 4:
            f0 = ds.GetLayer(0).GetNextFeature()
            if f0 and f0.GetGeometryRef() and 500000.0 <= f0.GetGeometryRef().GetEnvelope()[0] <= 650000.0:
                gj_ok = True

    def _close(v: Any, exp: float, tol: float) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_stamp", ja.get("filing_stamp") == FILING_STAMP, 1.0, "filing_stamp mismatch"),
        ("a_utm_gj", gj_ok, 1.8, "basins_utm18n_clipped.geojson missing or not EPSG:32618"),
        ("a_tot_ha", _close(ja.get("total_developable_ha"), ora["total_developable_ha"], 0.15), 1.6, f"total_developable_ha mismatch ({ora['total_developable_ha']})"),
        ("a_eff_imp", _close(ja.get("effective_impervious_ha"), ora["effective_impervious_ha"], 0.12), 1.6, f"effective_impervious_ha mismatch ({ora['effective_impervious_ha']})"),
        ("a_gui_calc_b2", _close(cell_float(book, "Catchment_Areas", "B2"), ora["total_developable_ha"], 0.15), 2.2, "Live Calc Catchment_Areas!B2 not saved"),
        ("a_gui_rollup_b2", _close(cell_float(book, "Filing_Rollup", "B2"), ora["effective_impervious_ha"], 0.15), 2.2, "Live Calc Filing_Rollup!B2 not saved"),
    ]

    tr_got = jb.get("trunks") if isinstance(jb.get("trunks"), dict) else {}
    diams_ok = all((tr_got.get(k) or {}).get("rcp_mm") == v["rcp_mm"] for k, v in ora["trunks"].items())
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_stamp", jb.get("filing_stamp") == FILING_STAMP, 1.0, "filing_stamp mismatch"),
        ("b_sum_q", _close(jb.get("sum_peak_q_cms"), ora["sum_peak_q_cms"], 0.12), 1.8, f"sum_peak_q_cms mismatch ({ora['sum_peak_q_cms']})"),
        ("b_diams", diams_ok, 1.8, "One or more RCP trunk diameters mismatch visual IDF chart"),
        ("b_capex", _close(jb.get("total_trunk_capex_usd"), ora["total_trunk_capex_usd"], 400.0), 1.8, f"total_trunk_capex_usd mismatch ({ora['total_trunk_capex_usd']})"),
        ("b_gui_calc_b3", _close(cell_float(book, "Trunk_Pipes", "B3"), ora["total_trunk_capex_usd"], 500.0), 2.2, "Live Calc Trunk_Pipes!B3 not saved"),
        ("b_gui_rollup_b3", _close(cell_float(book, "Filing_Rollup", "B3"), ora["total_trunk_capex_usd"], 500.0), 2.2, "Live Calc Filing_Rollup!B3 not saved"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_live_calc_combined_budget_b4",
            _close(cell_float(book, "Filing_Rollup", "B4"), ora["combined_program_budget_usd"], 800.0),
            2.5,
            f"Live Calc Filing_Rollup!B4 combined budget mismatch (expected {ora['combined_program_budget_usd']}, got {cell_float(book, 'Filing_Rollup', 'B4')})",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"gis_delineation_eng": TICKET_A, "stormwater_trunk_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
