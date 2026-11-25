"""AW-16: Live QGIS 3-Layer Exclusion & Pure-GUI LibreOffice Calc Transmission Corridor Schedule."""
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
    cell_formula,
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
    "id": "AW-16",
    "slug": "qgis_calc_corridor_easement",
    "title": "Live QGIS 3-Layer Exclusion & Pure-GUI LibreOffice Calc Transmission Corridor Schedule",
    "domain": "Civil Transmission GIS & Live Calc Permitting (QGIS 3.22 + GDAL/OGR + LibreOffice Calc + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19616,
    "roles": ("easement_gis_specialist", "culvert_crossing_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

DOCKET_NO = "PUC-2026-ROW-519"
PARCELS = [
    ("PCL-01", -74.2100, 40.7600, -74.2078, 40.7618, "agricultural", 42000.0),
    ("PCL-02", -74.2078, 40.7600, -74.2054, 40.7618, "industrial", 95000.0),
    ("PCL-03", -74.2100, 40.7618, -74.2074, 40.7636, "woodland", 54000.0),
    ("PCL-04", -74.2074, 40.7618, -74.2048, 40.7636, "commercial", 118000.0),
]
WETLAND_W = (-74.2085, 40.7606, -74.2068, 40.7616)
HISTORIC_H = (-74.2082, 40.7622, -74.2066, 40.7632)
CROSSINGS = [
    ("XING-1", "PCL-01", 0.55, 220.0, 5.5, 0.0050, 28.0),
    ("XING-2", "PCL-02", 0.78, 160.0, 4.8, 0.0065, 34.0),
    ("XING-3", "PCL-03", 0.46, 310.0, 6.2, 0.0045, 26.0),
    ("XING-4", "PCL-04", 0.82, 190.0, 5.0, 0.0055, 38.0),
]
CULVERT_RATES = {600: 640.0, 750: 820.0, 900: 1040.0, 1050: 1290.0, 1200: 1580.0}

TICKET_A = (
    "# Work Order — Transmission Easement GIS Specialist (`easement_gis_specialist`)\n\n"
    "Complete the 3-layer `EPSG:32618` corridor easement exclusion in `/workspace/corridor` and enter all parcel compensation cells + `=SUM` formula into the live **LibreOffice Calc** workbook open on the desktop (`Corridor_Permit_Schedule.xlsx`):\n\n"
    "1. Read `/workspace/corridor/specs/Corridor_ROW_Manual.pdf`, inspect the 3 GeoJSON layers (`corridor_parcels_wgs84.geojson`, `wetland_reserve_wgs84.geojson`, `historic_sites_wgs84.geojson`) open in **QGIS**, and view the **PUC ROW Portal** in Chromium (`http://127.0.0.1:19616`, `Easement Multiplier` tab).\n"
    "2. Reproject all 3 layers to `EPSG:32618`, subtract BOTH `wetland_reserve` and `historic_sites` from each parcel, save `/workspace/corridor/net_easements_utm18n.geojson`, and compute `net_ha` (3 decimals) and `easement_fee_usd = round(net_ha * base_rate_usd_ha * severance_multiplier, 2)` for `PCL-01`..`PCL-04`, writing `/workspace/corridor/easement_summary.json` (`docket_no`, `parcel_fees_usd` dict, `total_easement_fee_usd`).\n"
    "3. In the open **LibreOffice Calc** window (`Corridor_Permit_Schedule.xlsx`), enter the 4 parcel fees into `Easement_Parcels!B2:B5`, enter `=SUM(B2:B5)` into `Easement_Parcels!B6`, enter `total_easement_fee_usd` into `Bond_Summary!B2`, and save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Access-Road Culvert Crossing Engineer (`culvert_crossing_eng`)\n\n"
    "Size the 4 access-road stream crossings in `/workspace/corridor` using the visual PUC chart in Chromium and enter all crossing CAPEX cells + `=SUM` formula into the live **LibreOffice Calc** workbook open on the desktop (`Corridor_Permit_Schedule.xlsx`):\n\n"
    "1. Read `/workspace/corridor/specs/Corridor_ROW_Manual.pdf`, query `/workspace/corridor/crossings.sqlite`, and view the **PUC ROW Portal** in Chromium (`http://127.0.0.1:19616`, `Visual IDF & Culvert Cost Chart` tab).\n"
    "2. Using the `EPSG:32618` net easement areas of `PCL-01`..`PCL-04` scaled by `tributary_scale = 0.55` per manual (`tributary_area_ha = 0.55 * host_parcel_net_ha`), compute Kirpich `tc_min` (`max(5.0, raw_tc)`), visual-chart `intensity_mm_hr`, `peak_q_cms`, smallest commercial culvert diameter `culvert_mm` (`Q_full(n=0.013) >= 1.20 * peak_q_cms`), and `crossing_cost_usd` for `XING-1`..`XING-4`, writing `/workspace/corridor/culvert_summary.json` (`docket_no`, `crossing_costs_usd` dict, `total_culvert_cost_usd`).\n"
    "3. In the open **LibreOffice Calc** window (`Corridor_Permit_Schedule.xlsx`), enter the 4 crossing costs into `Culvert_Crossings!B2:B5`, enter `=SUM(B2:B5)` into `Culvert_Crossings!B6`, enter `total_culvert_cost_usd` into `Bond_Summary!B3`, and save (`Ctrl+S`).\n"
)


def _wkt(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def compute_aw16_oracle() -> dict[str, Any]:
    from osgeo import ogr, osr

    s1 = osr.SpatialReference(); s1.ImportFromEPSG(4326); s1.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    s2 = osr.SpatialReference(); s2.ImportFromEPSG(32618); s2.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s1, s2)
    g_w = ogr.CreateGeometryFromWkt(_wkt(*WETLAND_W)); g_w.Transform(ct)
    g_h = ogr.CreateGeometryFromWkt(_wkt(*HISTORIC_H)); g_h.Transform(ct)
    excl = g_w.Union(g_h)

    sev_mult = 1.25
    p_ha = {}
    p_fees = {}
    feats = []
    for pid, x0, y0, x1, y1, ztype, rate in PARCELS:
        g = ogr.CreateGeometryFromWkt(_wkt(x0, y0, x1, y1)); g.Transform(ct)
        dg = g.Difference(excl)
        ha = round(dg.GetArea() / 10000.0, 3)
        p_ha[pid] = ha
        p_fees[pid] = round(ha * rate * sev_mult, 2)
        feats.append({"type": "Feature", "properties": {"parcel_id": pid, "net_ha": ha}, "geometry": json.loads(dg.ExportToJson())})

    x_costs = {}
    for xid, pid, rc, flen, edrop, slp, clen in CROSSINGS:
        trib_ha = p_ha[pid] * 0.55
        tc = round(max(5.0, 0.01947 * (flen ** 0.77) * ((edrop / flen) ** -0.385)), 2)
        inten = round((2500.0 / ((tc + 10.0) ** 0.78)) * 1.12, 2)
        qp = round(0.002778 * rc * inten * trib_ha, 3)
        chosen = 1200
        for dm in sorted(CULVERT_RATES):
            d_m = dm / 1000.0
            qf = (1.0 / 0.013) * (math.pi * d_m * d_m / 4.0) * ((d_m / 4.0) ** (2.0 / 3.0)) * (slp ** 0.5)
            if qf >= 1.20 * qp:
                chosen = dm
                break
        x_costs[xid] = round(clen * CULVERT_RATES[chosen], 2)

    tot_e = round(sum(p_fees.values()), 2)
    tot_c = round(sum(x_costs.values()), 2)
    return {
        "docket_no": DOCKET_NO,
        "parcel_fees_usd": p_fees,
        "total_easement_fee_usd": tot_e,
        "crossing_costs_usd": x_costs,
        "total_culvert_cost_usd": tot_c,
        "bond_110pct_usd": round((tot_e + tot_c) * 1.10, 2),
        "geojson": {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}}, "features": feats},
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    cd = workspace_root / "shared" / "corridor"
    (cd / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    write_json(cd / "corridor_parcels_wgs84.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"parcel_id": r[0], "zone": r[5], "base_rate_usd_ha": r[6]}, "geometry": {"type": "Polygon", "coordinates": [[[r[1], r[2]], [r[3], r[2]], [r[3], r[4]], [r[1], r[4]], [r[1], r[2]]]]}} for r in PARCELS]})
    for fn, bx in (("wetland_reserve_wgs84.geojson", WETLAND_W), ("historic_sites_wgs84.geojson", HISTORIC_H)):
        write_json(cd / fn, {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": fn[:4]}, "geometry": {"type": "Polygon", "coordinates": [[[bx[0], bx[1]], [bx[2], bx[1]], [bx[2], bx[3]], [bx[0], bx[3]], [bx[0], bx[1]]]]}}]})

    db_p = cd / "crossings.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE stream_crossings (crossing_id TEXT PRIMARY KEY, host_parcel_id TEXT, runoff_c REAL, flow_length_m REAL, elev_drop_m REAL, culvert_slope REAL, culvert_length_m REAL)")
    con.executemany("INSERT INTO stream_crossings VALUES (?,?,?,?,?,?,?)", CROSSINGS)
    con.commit()
    con.close()

    write_multisheet_xlsx(
        seed / "Corridor_Permit_Schedule.xlsx",
        [
            ("Easement_Parcels", [["Parcel_ID", "Easement_Fee_USD"], *[[r[0], 0.0] for r in PARCELS], ["TOTAL_EASEMENT", 0.0]]),
            ("Culvert_Crossings", [["Crossing_ID", "Crossing_Cost_USD"], *[[x[0], 0.0] for x in CROSSINGS], ["TOTAL_CULVERT", 0.0]]),
            ("Bond_Summary", [["Line", "USD"], ["Total_Easement_Fee_USD", 0.0], ["Total_Culvert_Cost_USD", 0.0], ["Surety_Bond_110pct_USD", ("=ROUND((B2+B3)*1.10,2)", 0.0)]]),
        ],
    )

    write_pdf_manual(
        cd / "specs" / "Corridor_ROW_Manual.pdf",
        "PUC Transmission Right-of-Way & Culvert Permitting Manual",
        [
            ("1. 3-Layer UTM 18N Easement Valuation", ["Reproject parcels, wetland_reserve, and historic_sites to EPSG:32618, subtract both exclusion layers, round net_ha to 3 decimals, and multiply net_ha * base_rate_usd_ha * severance_multiplier (from PUC Portal)."]),
            ("2. Tributary Culvert Sizing & Live Calc Schedule", ["Each stream crossing drains tributary_area_ha = 0.55 * host_parcel_net_ha. Read the IDF equation and culvert $/m rates from the visual PUC chart, enforce Kirpich floor tc_min = max(5.0, raw_tc) and Q_full(n=0.013) >= 1.20 * peak_q_cms, and enter all cells + =SUM(B2:B5) formulas directly in the open LibreOffice Calc window (Corridor_Permit_Schedule.xlsx)."]),
        ],
    )
    (tickets_root / "easement_gis_specialist").mkdir(parents=True, exist_ok=True)
    (tickets_root / "culvert_crossing_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "easement_gis_specialist" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "culvert_crossing_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def _render_puc_chart() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (900, 480), (255, 255, 255))
    drw = ImageDraw.Draw(im)
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)
        fm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    except Exception:
        fb = fm = ImageFont.load_default()
    drw.rectangle([0, 0, 900, 48], fill=(30, 41, 59))
    drw.text((18, 12), f"PUC ENGINEERING CHART | DOCKET: {DOCKET_NO}", fill=(255, 255, 255), font=fb)
    drw.text((22, 68), "Design Storm IDF Equation (mm/hr):", fill=(15, 23, 42), font=fb)
    drw.text((32, 102), "I(tc) = [ 2500.0 / (tc + 10.0)^0.78 ] * 1.12   (2 dec)", fill=(29, 78, 216), font=fm)
    drw.text((22, 152), "Heavy-Duty Class-IV Culvert Unit Cost (USD / m):", fill=(15, 23, 42), font=fb)
    y = 188
    for dm, rate in sorted(CULVERT_RATES.items()):
        drw.text((40, y), f"Diameter {dm:4d} mm   --->   ${rate:7.2f} / m", fill=(15, 23, 42), font=fm)
        y += 34
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    png = _render_puc_chart()
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "mult", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw16_sess" in ck) and (ck["aw16_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw16_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 PUC Portal Session Required</h3>")
                return
            if parsed.path == "/puc_chart.png":
                self._send(200, png, "image/png")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["mult"])[0]
                with lock:
                    if t in ("mult", "chart") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "mult":
                body = f"<h2>Easement Multiplier ({DOCKET_NO})</h2><p><code>severance_multiplier = 1.25</code></p>"
            else:
                body = "<h2>Visual IDF &amp; Culvert Cost Chart</h2><img src='/puc_chart.png' style='border:1px solid #cbd5e1;border-radius:8px;max-width:100%;'/>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>PUC ROW Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:20px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>PUC ROW Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=mult">Easement Multiplier</a><a href="/tab?id=chart">Visual IDF &amp; Culvert Cost Chart</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1160, 780))
    seed = workspace_root / "_desk_seed"
    cd = workspace_root / "shared" / "corridor"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Corridor_Permit_Schedule.xlsx", sp / "Corridor_Permit_Schedule.xlsx")
    if "easement_gis_specialist" in roles:
        launch_studio_app(f"nohup qgis --nologo '{cd / 'corridor_parcels_wgs84.geojson'}' '{cd / 'wetland_reserve_wgs84.geojson'}' '{cd / 'historic_sites_wgs84.geojson'}' >/tmp/aw16_qgis.log 2>&1 </dev/null &", wait_s=3.0)
    launch_studio_app("nohup libreoffice --norestore --nologo --nofirststartwizard '/srv/studio_project/Corridor_Permit_Schedule.xlsx' >/tmp/aw16_calc.log 2>&1 </dev/null &", wait_s=2.5)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    cd = workspace_root / "shared" / "corridor"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Corridor_Permit_Schedule.xlsx"
    ora = compute_aw16_oracle()
    if role == "easement_gis_specialist":
        write_json(cd / "net_easements_utm18n.geojson", ora["geojson"])
        write_json(cd / "easement_summary.json", {"docket_no": DOCKET_NO, "parcel_fees_usd": ora["parcel_fees_usd"], "total_easement_fee_usd": ora["total_easement_fee_usd"]})
        e_rows = [["Parcel_ID", "Easement_Fee_USD"], *[[r[0], ora["parcel_fees_usd"][r[0]]] for r in PARCELS], ["TOTAL_EASEMENT", ("=SUM(B2:B5)", ora["total_easement_fee_usd"])]]
        if cooperative:
            with resource_lock("aw16_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3_c = cell_float(bk, "Bond_Summary", "B3") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Easement_Parcels", e_rows)
                update_single_sheet_xlsx(xlsx_p, "Bond_Summary", [["Line", "USD"], ["Total_Easement_Fee_USD", ora["total_easement_fee_usd"]], ["Total_Culvert_Cost_USD", b3_c], ["Surety_Bond_110pct_USD", ("=ROUND((B2+B3)*1.10,2)", round((ora["total_easement_fee_usd"] + b3_c) * 1.10, 2))]])
        else:
            write_multisheet_xlsx(xlsx_p, [("Easement_Parcels", e_rows)])
    elif role == "culvert_crossing_eng":
        write_json(cd / "culvert_summary.json", {"docket_no": DOCKET_NO, "crossing_costs_usd": ora["crossing_costs_usd"], "total_culvert_cost_usd": ora["total_culvert_cost_usd"]})
        c_rows = [["Crossing_ID", "Crossing_Cost_USD"], *[[x[0], ora["crossing_costs_usd"][x[0]]] for x in CROSSINGS], ["TOTAL_CULVERT", ("=SUM(B2:B5)", ora["total_culvert_cost_usd"])]]
        if cooperative:
            with resource_lock("aw16_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2_c = cell_float(bk, "Bond_Summary", "B2") or 0.0
                update_single_sheet_xlsx(xlsx_p, "Culvert_Crossings", c_rows)
                update_single_sheet_xlsx(xlsx_p, "Bond_Summary", [["Line", "USD"], ["Total_Easement_Fee_USD", b2_c], ["Total_Culvert_Cost_USD", ora["total_culvert_cost_usd"]], ["Surety_Bond_110pct_USD", ("=ROUND((B2+B3)*1.10,2)", round((b2_c + ora["total_culvert_cost_usd"]) * 1.10, 2))]])
        else:
            write_multisheet_xlsx(xlsx_p, [("Culvert_Crossings", c_rows)])


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("easement_gis_specialist", workspace_root, cooperative=False)
    solve_role("culvert_crossing_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "easement_gis_specialist", workspace_root, True)
        fb = pool.submit(solve_role, "culvert_crossing_eng", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    from osgeo import ogr
    from tasks.authentic_workstation_v1.common import read_multisheet_xlsx

    cd = workspace_root / "shared" / "corridor"
    sp = Path("/srv/studio_project")
    ora = compute_aw16_oracle()
    ja = read_json_safe(cd / "easement_summary.json")
    jb = read_json_safe(cd / "culvert_summary.json")
    book = evaluate_xlsx_isolated(sp / "Corridor_Permit_Schedule.xlsx")
    f_book = read_multisheet_xlsx(sp / "Corridor_Permit_Schedule.xlsx") if (sp / "Corridor_Permit_Schedule.xlsx").is_file() else {}

    gj_ok = False
    gp = cd / "net_easements_utm18n.geojson"
    if gp.is_file():
        ds = ogr.Open(str(gp))
        if ds and ds.GetLayer(0) and ds.GetLayer(0).GetFeatureCount() == 4:
            f0 = ds.GetLayer(0).GetNextFeature()
            if f0 and f0.GetGeometryRef() and 500000.0 <= f0.GetGeometryRef().GetEnvelope()[0] <= 650000.0:
                gj_ok = True

    def _close(v: Any, exp: float, tol: float = 250.0) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_gj_utm", gj_ok, 1.8, "net_easements_utm18n.geojson missing or not EPSG:32618"),
        ("a_json_tot", _close(ja.get("total_easement_fee_usd"), ora["total_easement_fee_usd"], 500.0) and ja.get("docket_no") == DOCKET_NO, 1.8, "easement_summary.json mismatch"),
        *[(f"a_pcl_{i}", _close(cell_float(book, "Easement_Parcels", f"B{i}"), ora["parcel_fees_usd"][r[0]], 350.0), 1.2, f"Live Calc Easement_Parcels!B{i} mismatch") for i, r in enumerate(PARCELS, start=2)],
        ("a_sum_b6", "SUM" in cell_formula(f_book, "Easement_Parcels", "B6").upper() and _close(cell_float(book, "Easement_Parcels", "B6"), ora["total_easement_fee_usd"], 600.0), 1.8, "Easement_Parcels!B6 missing =SUM(B2:B5) or wrong sum"),
        ("a_bond_b2", _close(cell_float(book, "Bond_Summary", "B2"), ora["total_easement_fee_usd"], 600.0), 1.8, "Bond_Summary!B2 mismatch"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_tot", _close(jb.get("total_culvert_cost_usd"), ora["total_culvert_cost_usd"], 350.0) and jb.get("docket_no") == DOCKET_NO, 1.8, "culvert_summary.json mismatch"),
        *[(f"b_xing_{i}", _close(cell_float(book, "Culvert_Crossings", f"B{i}"), ora["crossing_costs_usd"][x[0]], 250.0), 1.2, f"Live Calc Culvert_Crossings!B{i} mismatch") for i, x in enumerate(CROSSINGS, start=2)],
        ("b_sum_b6", "SUM" in cell_formula(f_book, "Culvert_Crossings", "B6").upper() and _close(cell_float(book, "Culvert_Crossings", "B6"), ora["total_culvert_cost_usd"], 400.0), 1.8, "Culvert_Crossings!B6 missing =SUM(B2:B5) or wrong sum"),
        ("b_bond_b3", _close(cell_float(book, "Bond_Summary", "B3"), ora["total_culvert_cost_usd"], 400.0), 1.8, "Bond_Summary!B3 mismatch"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_bond_summary_b4_surety",
            _close(cell_float(book, "Bond_Summary", "B4"), ora["bond_110pct_usd"], 900.0),
            2.5,
            f"Live Calc Bond_Summary!B4 surety bond mismatch (expected {ora['bond_110pct_usd']}, got {cell_float(book, 'Bond_Summary', 'B4')})",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"easement_gis_specialist": TICKET_A, "culvert_crossing_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
