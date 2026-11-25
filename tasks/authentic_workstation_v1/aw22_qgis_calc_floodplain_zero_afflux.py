"""AW-22: Zero-Spoiler 4-Layer QGIS Floodplain Remapping & Coupled Zero-Afflux Live Calc Ledger."""
from __future__ import annotations

import base64
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
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
    cell_formula,
    evaluate_xlsx_isolated,
    launch_desktop_app_as_user,
    launch_studio_app,
    read_json_safe,
    read_multisheet_xlsx,
    resource_lock,
    update_single_sheet_xlsx,
    write_json,
    write_multisheet_xlsx,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-22",
    "slug": "qgis_calc_floodplain_zero_afflux",
    "title": "FEMA Zero-Afflux Floodplain Filing: 4-Layer QGIS Exclusion & Visual IDF Chart vs. Live Calc Detention Weir",
    "domain": "Civil Floodplain GIS & Hydraulic Detention Permitting (QGIS 3.22 + GDAL/OGR + LibreOffice Calc + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19622,
    "roles": ("floodplain_gis_analyst", "detention_weir_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

FEMA_CASE_NO = "FEMA-CLOMR-2026-618"
RIPARIAN = (-74.1965, 40.7510, -74.1942, 40.7524)
PLUME = (-74.1938, 40.7522, -74.1920, 40.7534)

SUBBASINS = [
    ("SB-01", -74.1980, 40.7500, -74.1955, 40.7518, "industrial", "C", 1, 0, 72.0, 0.0, 210.0, 5.2, 0.0055, 260.0, 3.2),
    ("SB-02", -74.1955, 40.7500, -74.1930, 40.7518, "commercial", "B/D", 0, 1, 64.0, 10.0, 180.0, 5.6, 0.0065, 230.0, 2.8),
    ("SB-03", -74.1930, 40.7500, -74.1905, 40.7518, "residential", "B", 1, 1, 48.0, 12.0, 340.0, 4.8, 0.0045, 310.0, 3.8),
    ("SB-04", -74.1980, 40.7518, -74.1952, 40.7536, "mixed_TOD", "B/D", 0, 0, 58.0, 8.0, 290.0, 5.0, 0.0050, 285.0, 3.6),
    ("SB-05", -74.1952, 40.7518, -74.1925, 40.7536, "tech_campus", "A", 1, 1, 42.0, 14.0, 380.0, 5.4, 0.0042, 340.0, 2.9),
    ("SB-06", -74.1925, 40.7518, -74.1900, 40.7536, "logistics", "C/D", 0, 1, 68.0, 6.0, 250.0, 4.9, 0.0052, 295.0, 4.1),
]

PERV_C = {
    "industrial": {"A": 0.20, "B": 0.27, "C": 0.35, "D": 0.44},
    "commercial": {"A": 0.18, "B": 0.24, "C": 0.32, "D": 0.40},
    "residential": {"A": 0.14, "B": 0.20, "C": 0.28, "D": 0.36},
    "mixed_TOD": {"A": 0.17, "B": 0.23, "C": 0.31, "D": 0.39},
    "tech_campus": {"A": 0.12, "B": 0.18, "C": 0.25, "D": 0.33},
    "logistics": {"A": 0.19, "B": 0.26, "C": 0.34, "D": 0.42},
}
HSG_NEXT = {"A": "B", "B": "C", "C": "D", "D": "D"}
RCP_COSTS = {450: 420.0, 525: 495.0, 600: 590.0, 750: 760.0, 900: 955.0, 1050: 1180.0, 1200: 1440.0}

LID_STD_CMS = 0.85
LID_BIO_CMS = 1.65
WEIR_NARROW_CMS = 8.40
WEIR_WIDE_CMS = 9.20
PREDEV_Q_CMS = 10.00

TICKET_A = (
    "# Work Order — Floodplain GIS & Land-Surface Runoff Analyst (`floodplain_gis_analyst`)\n\n"
    "Complete the `EPSG:32618` riparian & brownfield exclusion mapping in `/workspace/floodplain`, populate the `Subbasin_GIS` and `Detention_Balance` schedules in the open **LibreOffice Calc** workbook (`Floodplain_Permit_Ledger.xlsx`), and export the GIS summary:\n\n"
    "1. Read `/workspace/floodplain/specs/FEMA_Floodplain_Manual.pdf`, inspect the GeoJSON layers open in **QGIS** (`subbasins_wgs84.geojson`, `riparian_corridor_wgs84.geojson`, `brownfield_plume_wgs84.geojson`), query `/workspace/floodplain/watershed_soils.sqlite` (`subbasin_soils`), and view the **FEMA CLOMR Portal** in Chromium (`http://127.0.0.1:19622`, `Overview` and `Pervious C & LID Credit` views).\n"
    "2. Reproject all layers to `EPSG:32618` (UTM Zone 18N), subtract **both** `riparian_corridor` and `brownfield_plume` from each subbasin, save `/workspace/floodplain/subbasins_utm18n_net.geojson`, and compute `net_ha` (3 decimals), `composite_c` (3 decimals), and `impervious_eq_ha = round(net_ha * composite_c, 3)` for `SB-01`..`SB-06`, writing `/workspace/floodplain/gis_runoff_audit.json` (`fema_case_no`, `subbasin_net_ha`, `subbasin_imp_eq_ha`, `total_net_ha`, `total_imp_eq_ha`, `selected_lid_credit_cms`).\n"
    "3. In the open **LibreOffice Calc** window (`Floodplain_Permit_Ledger.xlsx`):\n"
    "   - On `Subbasin_GIS`, enter `net_ha` in `B2:B7` and `impervious_eq_ha` in `C2:C7`, enter `=SUM(...)` formulas in `B8` and `C8`, and enter `=AVERAGE(C2:C7)` in `C9`.\n"
    "   - On `Detention_Balance`, select the approved LID Retention Credit tier in `B2` so `PostDev_Outflow_Ratio` (`B5`) lands inside the mandatory Zero-Afflux Discharge Window, and save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Stormwater Trunk & Detention Weir Engineer (`detention_weir_eng`)\n\n"
    "Size the 6 trunk RCP collectors using the visual hydrograph/IDF chart in Chromium, populate the `Trunk_Conveyance` and `Detention_Balance` schedules in the open **LibreOffice Calc** workbook (`Floodplain_Permit_Ledger.xlsx`), and export the hydraulic summary:\n\n"
    "1. Read `/workspace/floodplain/specs/FEMA_Floodplain_Manual.pdf`, query `/workspace/floodplain/watershed_soils.sqlite` (`subbasin_soils`, `trunk_reaches`), and inspect the **FEMA CLOMR Portal** in Chromium (`http://127.0.0.1:19622`, `Overview` and `Visual IDF & Weir Rating Chart` views — read the IDF parameters, RCP unit costs, and Weir Slot capacities directly from the visual chart).\n"
    "2. Using the `EPSG:32618` exclusion-clipped subbasin areas and composite runoff coefficients for `SB-01`..`SB-06`, compute Kirpich `tc_min`, climate-adjusted storm intensity, Rational `peak_q_cms` (3 decimals), commercial `rcp_mm`, and shoring-adjusted `trunk_cost_usd` (2 decimals), writing `/workspace/floodplain/weir_trunk_audit.json` (`fema_case_no`, `peak_q_cms`, `trunk_cost_usd`, `sum_peak_q_cms`, `total_trunk_cost_usd`, `selected_weir_slot_cms`).\n"
    "3. In the open **LibreOffice Calc** window (`Floodplain_Permit_Ledger.xlsx`):\n"
    "   - On `Trunk_Conveyance`, enter `peak_q_cms` in `B2:B7` and `trunk_cost_usd` in `C2:C7`, enter `=SUM(...)` formulas in `B8` and `C8`, and enter `=MAX(B2:B7)` in `B9`.\n"
    "   - On `Detention_Balance`, select the approved Outlet Weir Slot tier in `B3` so `PostDev_Outflow_Ratio` (`B5`) lands inside the mandatory Zero-Afflux Discharge Window, and save (`Ctrl+S`).\n"
)


def _wkt(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def compute_aw22_oracle() -> dict[str, Any]:
    from osgeo import ogr, osr

    s1 = osr.SpatialReference(); s1.ImportFromEPSG(4326); s1.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    s2 = osr.SpatialReference(); s2.ImportFromEPSG(32618); s2.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s1, s2)

    gr = ogr.CreateGeometryFromWkt(_wkt(*RIPARIAN)); gr.Transform(ct)
    gp = ogr.CreateGeometryFromWkt(_wkt(*PLUME)); gp.Transform(ct)
    excl = gr.Union(gp)

    ha_m, imp_m, q_m, cost_m = {}, {}, {}, {}
    feats = []
    for sbid, x0, y0, x1, y1, luse, nhsg, comp, udrain, imp_pct, rdisc, flen, edrop, pslp, plen, idepth in SUBBASINS:
        g = ogr.CreateGeometryFromWkt(_wkt(x0, y0, x1, y1)); g.Transform(ct)
        dg = g.Difference(excl)
        ha = round(dg.GetArea() / 10000.0, 3)
        h = (nhsg.split("/")[0] if udrain == 1 else nhsg.split("/")[1]) if "/" in nhsg else nhsg
        if comp == 1:
            h = HSG_NEXT[h]
        eff_imp = (imp_pct - 0.5 * rdisc) / 100.0
        c_val = round(eff_imp * 0.95 + (1.0 - eff_imp) * PERV_C[luse][h], 3)
        ieq = round(ha * c_val, 3)
        tc = round(max(5.0, 0.01947 * (flen ** 0.77) * ((edrop / flen) ** -0.385)), 2)
        inten = round((2760.0 / ((tc + 13.0) ** 0.81)) * 1.16, 2)
        qp = round(0.002778 * c_val * inten * ha, 3)
        chosen = 1200
        for dm in sorted(RCP_COSTS):
            d_m = dm / 1000.0
            qf = (1.0 / 0.013) * (math.pi * d_m * d_m / 4.0) * ((d_m / 4.0) ** (2.0 / 3.0)) * (pslp ** 0.5)
            if qf >= 1.18 * qp:
                chosen = dm
                break
        shor = 1.15 if idepth > 3.5 else 1.00
        c_usd = round(plen * RCP_COSTS[chosen] * shor, 2)
        ha_m[sbid], imp_m[sbid], q_m[sbid], cost_m[sbid] = ha, ieq, qp, c_usd
        feats.append({"type": "Feature", "properties": {"subbasin_id": sbid, "net_ha": ha, "composite_c": c_val}, "geometry": json.loads(dg.ExportToJson())})

    tot_ha = round(sum(ha_m.values()), 3)
    tot_imp = round(sum(imp_m.values()), 3)
    tot_q = round(sum(q_m.values()), 3)
    tot_cost = round(sum(cost_m.values()), 2)
    return {
        "fema_case_no": FEMA_CASE_NO,
        "subbasin_net_ha": ha_m,
        "subbasin_imp_eq_ha": imp_m,
        "total_net_ha": tot_ha,
        "total_imp_eq_ha": tot_imp,
        "mean_imp_eq_ha": round(tot_imp / len(SUBBASINS), 3),
        "peak_q_cms": q_m,
        "trunk_cost_usd": cost_m,
        "sum_peak_q_cms": tot_q,
        "max_peak_q_cms": max(q_m.values()),
        "total_trunk_cost_usd": tot_cost,
        "clean_geojson": {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}}, "features": feats},
    }


def _chart_png_b64() -> str:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (920, 340), (15, 23, 42))
    dr = ImageDraw.Draw(im)
    try:
        fh = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
    except Exception:
        fh = ImageFont.load_default()
        fb = fh
    dr.rectangle((14, 14, 906, 326), outline=(56, 189, 248), width=2)
    dr.text((28, 26), f"FEMA 100-YR IDF CURVE, RCP COST & WEIR RATING ({FEMA_CASE_NO})", fill=(125, 211, 252), font=fh)
    lines = [
        "IDF Equation: I_mm_hr = round((2760.0 / ((tc_min + 13.0) ** 0.81)) * 1.16, 2)",
        "Manning RCP Design Margin: Q_full(n=0.013) >= 1.18 * peak_q_cms",
        "Deep-Trench Shoring Factor: +15% (x1.15) when invert_depth_m > 3.5 m",
        "RCP $/m: 450=$420 | 525=$495 | 600=$590 | 750=$760 | 900=$955 | 1050=$1180 | 1200=$1440",
        f"Outlet Weir Slot Options (Detention_Balance!B3): Narrow = {WEIR_NARROW_CMS} cms | Wide = {WEIR_WIDE_CMS} cms",
        "Zero-Afflux Outflow Ratio Window (Detention_Balance!B5): [0.745, 0.785]",
    ]
    y = 70
    for ln in lines:
        dr.text((28, y), ln, fill=(241, 245, 249), font=fb)
        y += 40
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _fc_box(coords: tuple[float, float, float, float], prop: dict[str, Any]) -> dict[str, Any]:
    x0, y0, x1, y1 = coords
    return {"type": "Feature", "properties": prop, "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}


def build(workspace_root: Path, tickets_root: Path) -> None:
    fp = workspace_root / "shared" / "floodplain"
    (fp / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    wgs_crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}}
    write_json(fp / "subbasins_wgs84.geojson", {"type": "FeatureCollection", "crs": wgs_crs, "features": [_fc_box((s[1], s[2], s[3], s[4]), {"subbasin_id": s[0], "land_use": s[5]}) for s in SUBBASINS]})
    write_json(fp / "riparian_corridor_wgs84.geojson", {"type": "FeatureCollection", "crs": wgs_crs, "features": [_fc_box(RIPARIAN, {"zone": "Class_I_Riparian"})]})
    write_json(fp / "brownfield_plume_wgs84.geojson", {"type": "FeatureCollection", "crs": wgs_crs, "features": [_fc_box(PLUME, {"zone": "EPA_Plume_NoInfil"})]})

    db_p = fp / "watershed_soils.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE subbasin_soils (subbasin_id TEXT PRIMARY KEY, land_use TEXT, native_hsg TEXT, compacted_fill INTEGER, underdrain_active INTEGER, impervious_pct REAL, disconn_roof_pct REAL)")
    con.executemany("INSERT INTO subbasin_soils VALUES (?,?,?,?,?,?,?)", [(s[0], s[5], s[6], s[7], s[8], s[9], s[10]) for s in SUBBASINS])
    con.execute("CREATE TABLE trunk_reaches (subbasin_id TEXT PRIMARY KEY, flow_length_m REAL, elev_drop_m REAL, pipe_slope REAL, pipe_length_m REAL, invert_depth_m REAL)")
    con.executemany("INSERT INTO trunk_reaches VALUES (?,?,?,?,?,?)", [(s[0], s[11], s[12], s[13], s[14], s[15]) for s in SUBBASINS])
    con.commit()
    con.close()

    write_multisheet_xlsx(
        seed / "Floodplain_Permit_Ledger.xlsx",
        [
            ("Subbasin_GIS", [["Subbasin_ID", "Net_Area_ha", "Impervious_Eq_ha"], *[[s[0], 0.0, 0.0] for s in SUBBASINS], ["TOTAL_WATERSHED", 0.0, 0.0], ["MEAN_IMP_EQ_HA", "", 0.0]]),
            ("Trunk_Conveyance", [["Subbasin_ID", "Peak_Q_cms", "Installed_Cost_USD"], *[[s[0], 0.0, 0.0] for s in SUBBASINS], ["TOTAL_CONVEYANCE", 0.0, 0.0], ["MAX_PEAK_Q_CMS", 0.0, ""]]),
            (
                "Detention_Balance",
                [
                    ["Parameter", "Value_cms"],
                    ["Selected_LID_Credit_cms", LID_STD_CMS],
                    ["Selected_Weir_Slot_cms", WEIR_WIDE_CMS],
                    ["PreDev_Allowable_Peak_cms", PREDEV_Q_CMS],
                    ["PostDev_Outflow_Ratio", ("=ROUND((B3-B2)/B4,3)", 0.835)],
                ],
            ),
        ],
    )

    write_pdf_manual(
        fp / "specs" / "FEMA_Floodplain_Manual.pdf",
        "FEMA CLOMR Zero-Afflux Floodplain & Stormwater Design Manual",
        [
            (
                "1. Hydrologic Soil Group (HSG) & Disconnected Rooftop Rules",
                [
                    "Dual HSG codes (B/D, C/D) resolve to the drained letter (B or C) when underdrain_active = 1, otherwise D. Afterward, if compacted_fill = 1, downgrade one HSG class (A->B, B->C, C->D, D->D).",
                    "Effective impervious fraction eff_imp = (impervious_pct - 0.5 * disconn_roof_pct) / 100. Composite runoff coefficient C = round(eff_imp * 0.95 + (1 - eff_imp) * C_pervious(land_use, effective_hsg), 3).",
                ],
            ),
            (
                "2. Kirpich Time of Concentration, Rational Q & Coupled Detention Balance",
                [
                    "Kirpich tc_min = round(max(5.0, 0.01947 * (flow_length_m ** 0.77) * ((elev_drop_m / flow_length_m) ** -0.385)), 2). Rational peak_q_cms = round(0.002778 * composite_c * I_mm_hr * net_ha, 3).",
                    "Detention_Balance!B5 computes PostDev_Outflow_Ratio = ROUND((B3 - B2) / B4, 3), which MUST lie strictly inside [0.745, 0.785] (above 0.785 causes downstream afflux; below 0.745 surcharges the emergency spillway).",
                ],
            ),
        ],
    )
    (tickets_root / "floodplain_gis_analyst").mkdir(parents=True, exist_ok=True)
    (tickets_root / "detention_weir_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "floodplain_gis_analyst" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "detention_weir_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "overview", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})
    chart_b64 = _chart_png_b64()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw22_sess" in ck) and (ck["aw22_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw22_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 FEMA CLOMR Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["overview"])[0]
                with lock:
                    if t in ("overview", "gis_lid", "weir_idf") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "overview":
                body = (
                    f"<h2>FEMA CLOMR Filing Control</h2>"
                    f"<p>Active Case Number (`fema_case_no`): <code>{FEMA_CASE_NO}</code></p>"
                    f"<p>Mandatory Zero-Afflux Outflow Ratio (`Detention_Balance!B5`): <code>[0.745, 0.785]</code></p>"
                )
            elif cur == "gis_lid":
                rows = "".join(
                    f"<tr><td>{lu}</td><td>{mp['A']}</td><td>{mp['B']}</td><td>{mp['C']}</td><td>{mp['D']}</td></tr>"
                    for lu, mp in PERV_C.items()
                )
                body = (
                    f"<h2>Pervious Runoff C Matrix &amp; LID Credit Tiers (<code>{FEMA_CASE_NO}</code>)</h2>"
                    f"<table border='1' cellpadding='6' style='border-collapse:collapse;margin-bottom:12px;'><tr><th>Land Use</th><th>A</th><th>B</th><th>C</th><th>D</th></tr>{rows}</table>"
                    f"<p>Approved LID Retention Credit Tiers (`Detention_Balance!B2`): <code>{LID_STD_CMS}</code> cms (Standard) or <code>{LID_BIO_CMS}</code> cms (Bioretention)</p>"
                )
            else:
                body = f"<h2>Visual IDF &amp; Weir Rating Chart (<code>{FEMA_CASE_NO}</code>)</h2><img src='data:image/png;base64,{chart_b64}' alt='IDF and Weir Chart'/>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>FEMA CLOMR Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>FEMA CLOMR Zero-Afflux Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=overview">Overview</a><a href="/tab?id=gis_lid">Pervious C &amp; LID Credit</a><a href="/tab?id=weir_idf">Visual IDF &amp; Weir Rating Chart</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    fp = workspace_root / "shared" / "floodplain"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Floodplain_Permit_Ledger.xlsx", sp / "Floodplain_Permit_Ledger.xlsx")
    if "floodplain_gis_analyst" in roles:
        launch_desktop_app_as_user(
            f"nohup qgis --nologo '{fp / 'subbasins_wgs84.geojson'}' '{fp / 'riparian_corridor_wgs84.geojson'}' '{fp / 'brownfield_plume_wgs84.geojson'}' >/tmp/aw22_qgis.log 2>&1 </dev/null &",
            wait_s=2.6,
        )
    launch_studio_app("nohup libreoffice --norestore --nologo --nofirststartwizard '/srv/studio_project/Floodplain_Permit_Ledger.xlsx' >/tmp/aw22_calc.log 2>&1 </dev/null &", wait_s=2.6)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    fp = workspace_root / "shared" / "floodplain"
    xlsx_p = Path("/srv/studio_project/Floodplain_Permit_Ledger.xlsx")
    ora = compute_aw22_oracle()
    if role == "floodplain_gis_analyst":
        write_json(fp / "subbasins_utm18n_net.geojson", ora["clean_geojson"])
        rows = [
            ["Subbasin_ID", "Net_Area_ha", "Impervious_Eq_ha"],
            *[[s[0], ora["subbasin_net_ha"][s[0]], ora["subbasin_imp_eq_ha"][s[0]]] for s in SUBBASINS],
            ["TOTAL_WATERSHED", ("=SUM(B2:B7)", ora["total_net_ha"]), ("=SUM(C2:C7)", ora["total_imp_eq_ha"])],
            ["MEAN_IMP_EQ_HA", "", ("=AVERAGE(C2:C7)", ora["mean_imp_eq_ha"])],
        ]
        if cooperative:
            with resource_lock("aw22_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                w_cur = cell_float(bk, "Detention_Balance", "B3") or WEIR_WIDE_CMS
                lid_sel = LID_STD_CMS if abs(w_cur - WEIR_NARROW_CMS) < 0.2 else LID_BIO_CMS
                update_single_sheet_xlsx(xlsx_p, "Subbasin_GIS", rows)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Detention_Balance",
                    [
                        ["Parameter", "Value_cms"],
                        ["Selected_LID_Credit_cms", lid_sel],
                        ["Selected_Weir_Slot_cms", w_cur],
                        ["PreDev_Allowable_Peak_cms", PREDEV_Q_CMS],
                        ["PostDev_Outflow_Ratio", ("=ROUND((B3-B2)/B4,3)", round((w_cur - lid_sel) / PREDEV_Q_CMS, 3))],
                    ],
                )
        else:
            lid_sel = LID_BIO_CMS
            write_multisheet_xlsx(xlsx_p, [("Subbasin_GIS", rows)])
        write_json(
            fp / "gis_runoff_audit.json",
            {
                "fema_case_no": FEMA_CASE_NO,
                "subbasin_net_ha": ora["subbasin_net_ha"],
                "subbasin_imp_eq_ha": ora["subbasin_imp_eq_ha"],
                "total_net_ha": ora["total_net_ha"],
                "total_imp_eq_ha": ora["total_imp_eq_ha"],
                "selected_lid_credit_cms": lid_sel,
            },
        )
    elif role == "detention_weir_eng":
        rows = [
            ["Subbasin_ID", "Peak_Q_cms", "Installed_Cost_USD"],
            *[[s[0], ora["peak_q_cms"][s[0]], ora["trunk_cost_usd"][s[0]]] for s in SUBBASINS],
            ["TOTAL_CONVEYANCE", ("=SUM(B2:B7)", ora["sum_peak_q_cms"]), ("=SUM(C2:C7)", ora["total_trunk_cost_usd"])],
            ["MAX_PEAK_Q_CMS", ("=MAX(B2:B7)", ora["max_peak_q_cms"]), ""],
        ]
        if cooperative:
            with resource_lock("aw22_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                lid_cur = cell_float(bk, "Detention_Balance", "B2") or LID_STD_CMS
                w_sel = WEIR_WIDE_CMS if abs(lid_cur - LID_BIO_CMS) < 0.2 else WEIR_NARROW_CMS
                update_single_sheet_xlsx(xlsx_p, "Trunk_Conveyance", rows)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Detention_Balance",
                    [
                        ["Parameter", "Value_cms"],
                        ["Selected_LID_Credit_cms", lid_cur],
                        ["Selected_Weir_Slot_cms", w_sel],
                        ["PreDev_Allowable_Peak_cms", PREDEV_Q_CMS],
                        ["PostDev_Outflow_Ratio", ("=ROUND((B3-B2)/B4,3)", round((w_sel - lid_cur) / PREDEV_Q_CMS, 3))],
                    ],
                )
        else:
            w_sel = WEIR_NARROW_CMS
            write_multisheet_xlsx(xlsx_p, [("Trunk_Conveyance", rows)])
        write_json(
            fp / "weir_trunk_audit.json",
            {
                "fema_case_no": FEMA_CASE_NO,
                "peak_q_cms": ora["peak_q_cms"],
                "trunk_cost_usd": ora["trunk_cost_usd"],
                "sum_peak_q_cms": ora["sum_peak_q_cms"],
                "total_trunk_cost_usd": ora["total_trunk_cost_usd"],
                "selected_weir_slot_cms": w_sel,
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("floodplain_gis_analyst", workspace_root, cooperative=False)
    solve_role("detention_weir_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "floodplain_gis_analyst", workspace_root, True)
        fb = pool.submit(solve_role, "detention_weir_eng", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    from osgeo import ogr

    fp = workspace_root / "shared" / "floodplain"
    xlsx_p = Path("/srv/studio_project/Floodplain_Permit_Ledger.xlsx")
    ora = compute_aw22_oracle()
    ja = read_json_safe(fp / "gis_runoff_audit.json")
    jb = read_json_safe(fp / "weir_trunk_audit.json")
    book = evaluate_xlsx_isolated(xlsx_p)
    f_book = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}

    gj_ok = False
    gjp = fp / "subbasins_utm18n_net.geojson"
    if gjp.is_file():
        ds = ogr.Open(str(gjp))
        if ds is not None and ds.GetLayerCount() > 0:
            lyr = ds.GetLayer(0)
            srs = lyr.GetSpatialRef()
            area_s = sum(ft.GetGeometryRef().GetArea() / 10000.0 for ft in lyr if ft.GetGeometryRef() is not None)
            gj_ok = ("32618" in (srs.ExportToWkt() if srs else "") or "32618" in gjp.read_text(encoding="utf-8", errors="replace")) and abs(area_s - ora["total_net_ha"]) <= 0.12

    def _close(v: Any, exp: float, tol: float = 0.03) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    b5_rat = cell_float(book, "Detention_Balance", "B5")
    aff_ok = (b5_rat is not None) and (0.745 <= float(b5_rat) <= 0.785)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_geojson_32618", gj_ok, 1.8, "subbasins_utm18n_net.geojson missing or wrong EPSG:32618 clipped area"),
        ("a_json", ja.get("fema_case_no") == FEMA_CASE_NO and _close(ja.get("total_net_ha"), ora["total_net_ha"], 0.06) and _close(ja.get("total_imp_eq_ha"), ora["total_imp_eq_ha"], 0.06), 1.8, f"gis_runoff_audit.json mismatch (expected imp_eq={ora['total_imp_eq_ha']})"),
        *[(f"a_imp_{i}", _close(cell_float(book, "Subbasin_GIS", f"C{i}"), ora["subbasin_imp_eq_ha"][s[0]], 0.03), 0.7, f"Subbasin_GIS!C{i} mismatch") for i, s in enumerate(SUBBASINS, start=2)],
        ("a_sum_bc8", "SUM" in cell_formula(f_book, "Subbasin_GIS", "B8").upper() and "SUM" in cell_formula(f_book, "Subbasin_GIS", "C8").upper() and _close(cell_float(book, "Subbasin_GIS", "C8"), ora["total_imp_eq_ha"], 0.06), 1.5, "Subbasin_GIS!B8:C8 missing =SUM or wrong total"),
        ("a_avg_c9", "AVERAGE" in cell_formula(f_book, "Subbasin_GIS", "C9").upper() and _close(cell_float(book, "Subbasin_GIS", "C9"), ora["mean_imp_eq_ha"], 0.03), 1.2, "Subbasin_GIS!C9 missing =AVERAGE formula"),
        ("a_afflux", aff_ok, 1.8, f"Live Calc PostDev_Outflow_Ratio ({b5_rat}) outside [0.745, 0.785]"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", jb.get("fema_case_no") == FEMA_CASE_NO and _close(jb.get("sum_peak_q_cms"), ora["sum_peak_q_cms"], 0.08) and _close(jb.get("total_trunk_cost_usd"), ora["total_trunk_cost_usd"], 1500.0), 1.8, f"weir_trunk_audit.json mismatch (expected cost={ora['total_trunk_cost_usd']})"),
        *[(f"b_cost_{i}", _close(cell_float(book, "Trunk_Conveyance", f"C{i}"), ora["trunk_cost_usd"][s[0]], 500.0), 0.7, f"Trunk_Conveyance!C{i} cost mismatch") for i, s in enumerate(SUBBASINS, start=2)],
        ("b_sum_bc8", "SUM" in cell_formula(f_book, "Trunk_Conveyance", "B8").upper() and "SUM" in cell_formula(f_book, "Trunk_Conveyance", "C8").upper() and _close(cell_float(book, "Trunk_Conveyance", "C8"), ora["total_trunk_cost_usd"], 1500.0), 1.5, "Trunk_Conveyance!B8:C8 missing =SUM or wrong total"),
        ("b_max_b9", "MAX" in cell_formula(f_book, "Trunk_Conveyance", "B9").upper() and _close(cell_float(book, "Trunk_Conveyance", "B9"), ora["max_peak_q_cms"], 0.04), 1.2, "Trunk_Conveyance!B9 missing =MAX formula"),
        ("b_afflux", aff_ok, 1.8, f"Live Calc PostDev_Outflow_Ratio ({b5_rat}) outside [0.745, 0.785]"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_zero_afflux_coupled_ledger_intact",
            aff_ok
            and _close(cell_float(book, "Subbasin_GIS", "C8"), ora["total_imp_eq_ha"], 0.06)
            and _close(cell_float(book, "Trunk_Conveyance", "C8"), ora["total_trunk_cost_usd"], 1500.0),
            2.5,
            f"Uncoordinated LID/Weir selection pushed PostDev_Outflow_Ratio ({b5_rat}) outside [0.745, 0.785] or Live Calc sheets collided",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"floodplain_gis_analyst": TICKET_A, "detention_weir_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
