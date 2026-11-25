"""AW-18: FreeCAD 3D Turbine Foundation + QGIS Karst Clipping + Live Calc Coupled Bearing SF [2.10, 2.28]."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import shutil
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
    "id": "AW-18",
    "slug": "freecad_qgis_turbine_foundation",
    "title": "Wind-Turbine Foundation Release: QGIS Karst Grout Stabilization vs. FreeCAD Pedestal Pad & Bearing SF",
    "domain": "Civil/Mechanical CAD & Geotechnical GIS (FreeCAD 0.20 + QGIS 3.22 + Live LibreOffice Calc + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19618,
    "roles": ("geotech_gis_eng", "foundation_cad_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

TURBINE_CERT = "IEC61400-FDN-309"
PAD_SITE_BOX = (-74.2400, 40.7800, -74.2376, 40.7818)
KARST_BOX = (-74.2392, 40.7805, -74.2382, 40.7813)
TURBINE_TOWER_DEADLOAD_KN = 19800.0
CONCRETE_KN_M3 = 24.5

TICKET_A = (
    "# Work Order — Geotechnical GIS & Subgrade Stabilization Engineer (`geotech_gis_eng`)\n\n"
    "Complete the `EPSG:32618` karst exclusion mapping in `/workspace/turbine_pad` and select the subgrade bearing option inside the live **LibreOffice Calc** signoff sheet open on the desktop (`Geotech_Foundation_Signoff.xlsx`):\n\n"
    "1. Read `/workspace/turbine_pad/specs/IEC61400_Foundation_Manual.pdf`, inspect `turbine_lease_wgs84.geojson` and `karst_sinkhole_wgs84.geojson` (open in **QGIS**), and check the **IEC 61400 Portal** in Chromium (`http://127.0.0.1:19618`, `Subgrade Stabilization Options` tab).\n"
    "2. Reproject both GeoJSON layers to `EPSG:32618`, subtract the karst buffer from the lease parcel, save `/workspace/turbine_pad/buildable_pad_utm18n.geojson`, compute `buildable_area_ha` (3 decimals), and select between `Standard_Compaction` (`300.0 kPa`) and `Vibro_Stone_Columns` (`350.0 kPa`) so that `Bearing_Check!B4` (`Bearing_SF = Allowable_Bearing_kPa / Applied_Pressure_kPa`) in the open **LibreOffice Calc** window (`Geotech_Foundation_Signoff.xlsx`) lands inside **`[2.100, 2.280]`**!\n"
    "3. In the open **LibreOffice Calc** window (`Geotech_Foundation_Signoff.xlsx`), enter `buildable_area_ha` into `Geotech_GIS!B2` and your selected `allowable_bearing_kpa` into `Bearing_Check!B2`, save (`Ctrl+S`), and write `/workspace/turbine_pad/geotech_report.json` (`cert_code`, `buildable_area_ha`, `selected_allowable_kpa`, `bearing_sf`).\n"
)

TICKET_B = (
    "# Work Order — 3D Foundation CAD & Structural Engineer (`foundation_cad_eng`)\n\n"
    "Size and model the reinforced concrete foundation pad with 12 anchor bolt holes in **FreeCAD** (`/workspace/turbine_pad/foundation_assy.FCStd`) and record the applied bearing pressure in the live **LibreOffice Calc** signoff sheet open on the desktop (`Geotech_Foundation_Signoff.xlsx`):\n\n"
    "1. Read `/workspace/turbine_pad/specs/IEC61400_Foundation_Manual.pdf` and inspect the **IEC 61400 Portal** in Chromium (`http://127.0.0.1:19618`, `Tower Deadload & Pad Geometry` tab).\n"
    "2. Choose between candidate circular pad radii `R_pad = 7.5 m` or `R_pad = 8.2 m` (thickness `H_pad = 2.4 m`, minus `12` vertical anchor-bolt through-holes of radius `0.15 m` on bolt-circle radius `2.6 m`), computing `net_concrete_m3`, `applied_pressure_kpa = round((tower_deadload_kn + net_concrete_m3 * 24.5) / (pi * R_pad^2), 2)`, such that `Bearing_SF` on `Bearing_Check!B4` in the open **LibreOffice Calc** window (`Geotech_Foundation_Signoff.xlsx`) lands inside **`[2.100, 2.280]`**!\n"
    "3. Update `PedestalPad` inside `/workspace/turbine_pad/foundation_assy.FCStd` (modeling dimensions in meters: cylinder radius `R_pad`, height `2.4`, cut by the 12 bolt cylinders), export `/workspace/turbine_pad/Foundation_Pedestal.step`, enter `net_concrete_m3` in `Pad_CAD!B2` and `applied_pressure_kpa` in `Bearing_Check!B3` inside **LibreOffice Calc** (`Ctrl+S`), and write `/workspace/turbine_pad/foundation_cad_report.json` (`cert_code`, `selected_radius_m`, `net_concrete_m3`, `applied_pressure_kpa`, `bearing_sf`).\n"
)


def _fc_exec(code: str) -> str:
    env = dict(os.environ)
    env.setdefault("HOME", "/tmp")
    return subprocess.run(["freecadcmd", "-c", code], env=env, check=True, capture_output=True, text=True, timeout=60).stdout


def compute_aw18_options() -> dict[str, Any]:
    from osgeo import ogr, osr

    s1 = osr.SpatialReference(); s1.ImportFromEPSG(4326); s1.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    s2 = osr.SpatialReference(); s2.ImportFromEPSG(32618); s2.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s1, s2)
    x0, y0, x1, y1 = PAD_SITE_BOX
    kx0, ky0, kx1, ky1 = KARST_BOX
    gp = ogr.CreateGeometryFromWkt(f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"); gp.Transform(ct)
    gk = ogr.CreateGeometryFromWkt(f"POLYGON (({kx0} {ky0}, {kx1} {ky0}, {kx1} {ky1}, {kx0} {ky1}, {kx0} {ky0}))"); gk.Transform(ct)
    dg = gp.Difference(gk)
    ha = round(dg.GetArea() / 10000.0, 3)

    opts = {}
    for r_m in (7.5, 8.2):
        area_m2 = math.pi * (r_m ** 2)
        vol_m3 = round((area_m2 - 12.0 * math.pi * (0.15 ** 2)) * 2.4, 3)
        q_app = round((TURBINE_TOWER_DEADLOAD_KN + vol_m3 * CONCRETE_KN_M3) / area_m2, 2)
        opts[r_m] = {"vol_m3": vol_m3, "q_app": q_app}
    # Check SFs:
    # r=7.5 -> vol ~ 422.07 m^3 -> weight = 19800 + 10340.8 = 30140.8 kN -> q_app = 30140.8 / 176.71 = 170.56 kPa!
    # Wait: 300 / 170.56 = 1.759 (<2.10!); 375 / 170.56 = 2.199 (in [2.10, 2.28]!)
    # r=8.5 -> area = 226.98 -> vol = 542.72 -> weight = 19800 + 13296.6 = 33096.6 -> q_app = 145.81 -> 320 / 145.81 = 2.195!
    return {
        "ha": ha,
        "geojson": {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32618"}}, "features": [{"type": "Feature", "properties": {"buildable_area_ha": ha}, "geometry": json.loads(dg.ExportToJson())}]},
        "opts": opts,
    }


# Let's use exact clean bearing options: Standard_Compaction = 315.0 kPa, Vibro_Stone_Columns = 375.0 kPa; R_pad in {7.5, 8.6} m!
# Check: R=7.5 -> q_app=170.56 kPa: 315/170.56 = 1.847 (v0 FAIL), 375/170.56 = 2.199 (PASS in [2.100, 2.280]!)
# R=8.6 -> area=232.35, vol=555.61, wt=33412.4, q_app=143.80 kPa: 315/143.80 = 2.191 (PASS in [2.100, 2.280]!), while 375/143.80 = 2.608 (> 2.280 FAIL!)
STD_ALLOW_KPA = 315.0
VIBRO_ALLOW_KPA = 375.0
R_SMALL = 7.5
R_LARGE = 8.6

TICKET_A = TICKET_A.replace("300.0 kPa", "315.0 kPa").replace("350.0 kPa", "375.0 kPa")
TICKET_B = TICKET_B.replace("R_pad = 8.2 m", "R_pad = 8.6 m")


def _pad_metrics(r_m: float) -> tuple[float, float]:
    area_m2 = math.pi * (r_m ** 2)
    vol_m3 = round((area_m2 - 12.0 * math.pi * (0.15 ** 2)) * 2.4, 3)
    q_app = round((TURBINE_TOWER_DEADLOAD_KN + vol_m3 * CONCRETE_KN_M3) / area_m2, 2)
    return vol_m3, q_app


def _write_pad_fcstd(fc_p: Path, step_p: Path | None, r_m: float) -> None:
    step_line = f"Part.export([obj], {str(step_p)!r})" if step_p else ""
    _fc_exec(
        f"""
import FreeCAD, Part, math
doc = FreeCAD.newDocument("TurbinePad")
cyl = Part.makeCylinder({r_m}, 2.4)
bolts = [Part.makeCylinder(0.15, 3.0, FreeCAD.Vector(2.6*math.cos(2*math.pi*k/12.0), 2.6*math.sin(2*math.pi*k/12.0), -0.3)) for k in range(12)]
obj = doc.addObject("Part::Feature", "PedestalPad")
obj.Shape = cyl.cut(Part.makeCompound(bolts))
doc.recompute()
{step_line}
doc.saveAs({str(fc_p)!r})
"""
    )


def build(workspace_root: Path, tickets_root: Path) -> None:
    tp = workspace_root / "shared" / "turbine_pad"
    (tp / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    x0, y0, x1, y1 = PAD_SITE_BOX
    kx0, ky0, kx1, ky1 = KARST_BOX
    write_json(tp / "turbine_lease_wgs84.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": "LEASE-09"}, "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}]})
    write_json(tp / "karst_sinkhole_wgs84.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": "KARST-1"}, "geometry": {"type": "Polygon", "coordinates": [[[kx0, ky0], [kx1, ky0], [kx1, ky1], [kx0, ky1], [kx0, ky0]]]}}]})
    # Initial FCStd has uncut solid R=7.5 cylinder (no bolt holes yet!)
    _fc_exec(f"import FreeCAD,Part; doc=FreeCAD.newDocument('TurbinePad'); o=doc.addObject('Part::Feature','PedestalPad'); o.Shape=Part.makeCylinder(7.5, 2.4); doc.recompute(); doc.saveAs({str(tp / 'foundation_assy.FCStd')!r})")

    _, q_v0 = _pad_metrics(R_SMALL)  # 170.56 kPa; v0 SF = 315 / 170.56 = 1.847 (< 2.10!)
    write_multisheet_xlsx(
        seed / "Geotech_Foundation_Signoff.xlsx",
        [
            ("Geotech_GIS", [["Metric", "Value"], ["Buildable_Area_Ha", 0.0]]),
            ("Pad_CAD", [["Metric", "Value"], ["Net_Concrete_Volume_m3", 0.0]]),
            ("Bearing_Check", [["Parameter", "Value"], ["Allowable_Bearing_kPa", STD_ALLOW_KPA], ["Applied_Pressure_kPa", q_v0], ["Bearing_SF", ("=ROUND(B2/B3,3)", round(STD_ALLOW_KPA / q_v0, 3))]]),
        ],
    )

    write_pdf_manual(
        tp / "specs" / "IEC61400_Foundation_Manual.pdf",
        "IEC 61400-6 Wind Turbine Gravity Foundation & Karst Subgrade Manual",
        [
            ("1. Karst Sinkhole Exclusion & Subgrade Stabilization", ["Reproject turbine_lease_wgs84.geojson and karst_sinkhole_wgs84.geojson to EPSG:32618 and subtract the karst polygon to obtain buildable_area_ha (3 decimals). Approved subgrade options: Standard_Compaction = 315.0 kPa or Vibro_Stone_Columns = 375.0 kPa."]),
            ("2. Pedestal Pad 3D CAD & Coupled Bearing SF [2.100, 2.280]", ["Candidate circular pedestal radii: R_pad = 7.5 m or R_pad = 8.6 m (height 2.4 m, minus 12 vertical bolt holes of radius 0.15 m on bolt circle R = 2.6 m). Tower deadload = 19,800.0 kN; reinforced concrete unit weight = 24.5 kN/m^3. Bearing_SF = round(Allowable_Bearing_kPa / Applied_Pressure_kPa, 3) on Bearing_Check!B4 MUST lie inside [2.100, 2.280] (below 2.100 fails IEC stability; above 2.280 exceeds CAPEX limit)."]),
        ],
    )
    (tickets_root / "geotech_gis_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "foundation_cad_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "geotech_gis_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "foundation_cad_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "soil", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw18_sess" in ck) and (ck["aw18_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw18_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 IEC 61400 Portal Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["soil"])[0]
                with lock:
                    if t in ("soil", "loads") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "soil":
                body = f"<h2>Subgrade Stabilization ({TURBINE_CERT})</h2><p><code>Standard_Compaction = 315.0 kPa</code> | <code>Vibro_Stone_Columns = 375.0 kPa</code> | Target SF: <code>[2.100, 2.280]</code></p>"
            else:
                body = f"<h2>Tower Deadload &amp; Pad Geometry ({TURBINE_CERT})</h2><p><code>Tower_Deadload = 19,800.0 kN</code> | <code>Concrete = 24.5 kN/m^3</code> | Candidate Radii: <code>7.5 m</code> or <code>8.6 m</code></p>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>IEC 61400 Foundation Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>IEC 61400 Foundation Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=soil">Subgrade Stabilization Options</a><a href="/tab?id=loads">Tower Deadload &amp; Pad Geometry</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    tp = workspace_root / "shared" / "turbine_pad"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "Geotech_Foundation_Signoff.xlsx", sp / "Geotech_Foundation_Signoff.xlsx")
    if "geotech_gis_eng" in roles:
        launch_studio_app(f"nohup qgis --nologo '{tp / 'turbine_lease_wgs84.geojson'}' '{tp / 'karst_sinkhole_wgs84.geojson'}' >/tmp/aw18_qgis.log 2>&1 </dev/null &", wait_s=3.0)
    if "foundation_cad_eng" in roles:
        launch_studio_app(f"nohup freecad '{tp / 'foundation_assy.FCStd'}' >/tmp/aw18_fc.log 2>&1 </dev/null &", wait_s=3.5)
    launch_studio_app("nohup libreoffice --norestore --nologo --nofirststartwizard '/srv/studio_project/Geotech_Foundation_Signoff.xlsx' >/tmp/aw18_calc.log 2>&1 </dev/null &", wait_s=2.5)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    tp = workspace_root / "shared" / "turbine_pad"
    sp = Path("/srv/studio_project")
    xlsx_p = sp / "Geotech_Foundation_Signoff.xlsx"
    info = compute_aw18_options()
    _, q_sm = _pad_metrics(R_SMALL)
    _, q_lg = _pad_metrics(R_LARGE)

    if role == "geotech_gis_eng":
        write_json(tp / "buildable_pad_utm18n.geojson", info["geojson"])
        if cooperative:
            with resource_lock("aw18_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                q_cur = cell_float(bk, "Bearing_Check", "B3") or q_sm
                allow_sel = STD_ALLOW_KPA if abs(q_cur - q_lg) < 5.0 else VIBRO_ALLOW_KPA
                sf = round(allow_sel / q_cur, 3)
                update_single_sheet_xlsx(xlsx_p, "Geotech_GIS", [["Metric", "Value"], ["Buildable_Area_Ha", info["ha"]]])
                update_single_sheet_xlsx(xlsx_p, "Bearing_Check", [["Parameter", "Value"], ["Allowable_Bearing_kPa", allow_sel], ["Applied_Pressure_kPa", q_cur], ["Bearing_SF", ("=ROUND(B2/B3,3)", sf)]])
        else:
            allow_sel = VIBRO_ALLOW_KPA
            bk = evaluate_xlsx_isolated(xlsx_p)
            q_cur = cell_float(bk, "Bearing_Check", "B3") or q_sm
            sf = round(allow_sel / q_cur, 3)
            update_single_sheet_xlsx(xlsx_p, "Geotech_GIS", [["Metric", "Value"], ["Buildable_Area_Ha", info["ha"]]])
            update_single_sheet_xlsx(xlsx_p, "Bearing_Check", [["Parameter", "Value"], ["Allowable_Bearing_kPa", allow_sel], ["Applied_Pressure_kPa", q_cur], ["Bearing_SF", ("=ROUND(B2/B3,3)", sf)]])
        write_json(tp / "geotech_report.json", {"cert_code": TURBINE_CERT, "buildable_area_ha": info["ha"], "selected_allowable_kpa": allow_sel, "bearing_sf": sf})
    elif role == "foundation_cad_eng":
        if cooperative:
            with resource_lock("aw18_calc"):
                bk = evaluate_xlsx_isolated(xlsx_p)
                al_cur = cell_float(bk, "Bearing_Check", "B2") or STD_ALLOW_KPA
                r_sel = R_SMALL if abs(al_cur - VIBRO_ALLOW_KPA) < 5.0 else R_LARGE
                vol_m3, q_app = _pad_metrics(r_sel)
                sf = round(al_cur / q_app, 3)
                _write_pad_fcstd(tp / "foundation_assy.FCStd", tp / "Foundation_Pedestal.step", r_sel)
                update_single_sheet_xlsx(xlsx_p, "Pad_CAD", [["Metric", "Value"], ["Net_Concrete_Volume_m3", vol_m3]])
                update_single_sheet_xlsx(xlsx_p, "Bearing_Check", [["Parameter", "Value"], ["Allowable_Bearing_kPa", al_cur], ["Applied_Pressure_kPa", q_app], ["Bearing_SF", ("=ROUND(B2/B3,3)", sf)]])
        else:
            r_sel = R_LARGE
            vol_m3, q_app = _pad_metrics(r_sel)
            _write_pad_fcstd(tp / "foundation_assy.FCStd", tp / "Foundation_Pedestal.step", r_sel)
            bk = evaluate_xlsx_isolated(xlsx_p)
            al_cur = cell_float(bk, "Bearing_Check", "B2") or STD_ALLOW_KPA
            sf = round(al_cur / q_app, 3)
            update_single_sheet_xlsx(xlsx_p, "Pad_CAD", [["Metric", "Value"], ["Net_Concrete_Volume_m3", vol_m3]])
            update_single_sheet_xlsx(xlsx_p, "Bearing_Check", [["Parameter", "Value"], ["Allowable_Bearing_kPa", al_cur], ["Applied_Pressure_kPa", q_app], ["Bearing_SF", ("=ROUND(B2/B3,3)", sf)]])
        write_json(tp / "foundation_cad_report.json", {"cert_code": TURBINE_CERT, "selected_radius_m": r_sel, "net_concrete_m3": vol_m3, "applied_pressure_kpa": q_app, "bearing_sf": sf})


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    """Gate 4: both apply solo upgrades (375 kPa and R=8.6m -> SF=2.608 > 2.280 CAPEX ceiling!)."""
    solve_role("geotech_gis_eng", workspace_root, cooperative=False)
    solve_role("foundation_cad_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "geotech_gis_eng", workspace_root, True)
        fb = pool.submit(solve_role, "foundation_cad_eng", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    from osgeo import ogr

    tp = workspace_root / "shared" / "turbine_pad"
    sp = Path("/srv/studio_project")
    info = compute_aw18_options()
    ja = read_json_safe(tp / "geotech_report.json")
    jb = read_json_safe(tp / "foundation_cad_report.json")
    book = evaluate_xlsx_isolated(sp / "Geotech_Foundation_Signoff.xlsx")

    gj_ok = False
    gp = tp / "buildable_pad_utm18n.geojson"
    if gp.is_file():
        ds = ogr.Open(str(gp))
        if ds and ds.GetLayer(0) and ds.GetLayer(0).GetFeatureCount() == 1:
            f0 = ds.GetLayer(0).GetNextFeature()
            if f0 and f0.GetGeometryRef() and 500000.0 <= f0.GetGeometryRef().GetEnvelope()[0] <= 650000.0:
                gj_ok = abs(f0.GetGeometryRef().GetArea() / 10000.0 - info["ha"]) <= 0.12

    step_vol = None
    st_p = tp / "Foundation_Pedestal.step"
    if st_p.is_file():
        try:
            out = _fc_exec(f"import Part; s=Part.read({str(st_p)!r}); print('VOL:' + str(round(s.Volume, 3)))")
            for ln in out.splitlines():
                if ln.startswith("VOL:"):
                    step_vol = float(ln.split("VOL:", 1)[1])
        except Exception:
            pass
    # Accept CAD models either in meters (vol ~ 422 or 555) or mm (vol / 1e9 ~ 422 or 555)!
    if step_vol is not None and step_vol > 1e6:
        step_vol = round(step_vol / 1e9, 3)

    r_sel = float(jb.get("selected_radius_m") or R_LARGE)
    exp_vol, exp_q = _pad_metrics(R_SMALL if abs(r_sel - R_SMALL) < 0.3 else R_LARGE)
    b4_sf = cell_float(book, "Bearing_Check", "B4")
    sf_in_band = (b4_sf is not None) and (2.100 <= float(b4_sf) <= 2.280)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_cert", ja.get("cert_code") == TURBINE_CERT, 1.0, "cert_code mismatch"),
        ("a_gj_utm", gj_ok, 2.0, "buildable_pad_utm18n.geojson missing or wrong EPSG:32618 karst-clipped area"),
        ("a_ha_json_calc", isinstance(ja.get("buildable_area_ha"), (int, float)) and abs(float(ja["buildable_area_ha"]) - info["ha"]) <= 0.12 and (cell_float(book, "Geotech_GIS", "B2") is not None) and abs(float(cell_float(book, "Geotech_GIS", "B2") or 0.0) - info["ha"]) <= 0.12, 2.0, "buildable_area_ha mismatch in JSON or Live Calc"),
        ("a_allow_b2", (cell_float(book, "Bearing_Check", "B2") in (STD_ALLOW_KPA, VIBRO_ALLOW_KPA)), 1.6, "Bearing_Check!B2 allowable kPa invalid"),
        ("a_sf_band", sf_in_band, 2.4, f"Live Calc Bearing_SF ({b4_sf}) outside [2.100, 2.280]"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_cert", jb.get("cert_code") == TURBINE_CERT, 1.0, "cert_code mismatch"),
        ("b_step_vol", (step_vol is not None) and abs(step_vol - exp_vol) <= 3.5, 2.2, f"Foundation_Pedestal.step solid volume mismatch (expected {exp_vol}, got {step_vol})"),
        ("b_vol_calc", (cell_float(book, "Pad_CAD", "B2") is not None) and abs(float(cell_float(book, "Pad_CAD", "B2") or 0.0) - exp_vol) <= 2.5, 1.8, "Live Calc Pad_CAD!B2 net_concrete_m3 missing/wrong"),
        ("b_q_calc", (cell_float(book, "Bearing_Check", "B3") is not None) and abs(float(cell_float(book, "Bearing_Check", "B3") or 0.0) - exp_q) <= 1.5, 1.8, "Live Calc Bearing_Check!B3 applied_pressure_kpa missing/wrong"),
        ("b_sf_band", sf_in_band, 2.4, f"Live Calc Bearing_SF ({b4_sf}) outside [2.100, 2.280]"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_coupled_bearing_sf_satisfied",
            sf_in_band,
            2.5,
            f"Uncoordinated dual-role soil + CAD sizing pushed Bearing_SF to {b4_sf} outside [2.100, 2.280]",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"geotech_gis_eng": TICKET_A, "foundation_cad_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
