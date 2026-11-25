"""NF2-10: Live QGIS 3.22 GUI (`--code` Telemetry) + Live Calc — Subsea Pipeline Bathymetry/UXO vs. DNV-RP-B401 Cathodic Protection."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import os
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import urlparse

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_qgis_readonly,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    launch_qgis_gui_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_qgis_gui_project,
    reload_uno_pipe_documents,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-10"
PORTAL_PORT = 19610

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `QGIS 3.22` Desktop GIS & Open Calc: North Sea Bathymetry/UXO Reprojection vs. DNV-RP-B401 Sacrificial Anode Sizing",
    "domain": "Offshore Marine Geomatics (`QGIS 3.22` + `GDAL/PROJ`) & Subsea Pipeline Cathodic Protection (`LibreOffice Calc`)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("marine_bathymetry_gis_lead", "cathodic_protection_engineer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

QGIS_DATUM_CODE = make_canary_code("UKHO-LAT", "utm31n-epsg32631")
DNV_ANODE_CODE = make_canary_code("DNV-B401", "al-zn-in-25yr")


def _generate_soundings() -> list[dict[str, Any]]:
    # 300 25m stations along trench: target trench bottom = -42.50 m LAT; side slope 1:2 (z=2.0), bottom width b=3.0 m!
    # Cut depth d = max(0, seabed_lat_m - (-42.50)); trapezoidal cross-section A = (b + z*d)*d!
    # Raw echosounder measures depth relative to MSL; secondary SQLite table tidal_lat_datum gives msl_to_lat_offset_m = -1.35 m!
    rows = []
    for kp_i in range(300):
        msl_z = round(-39.20 - 1.8 * ((kp_i % 13) / 12.0), 3)
        rows.append({
            "station_idx": kp_i, "chainage_m": kp_i * 25.0, "seabed_msl_m": msl_z,
            "beam_quality": "IHO_ORDER_1A" if (kp_i % 29 != 0) else "KELP_FALSE_ECHO",
        })
    return rows


def _generate_pipeline_joints() -> list[dict[str, Any]]:
    zones = [("BURIAL_TRENCH", 0.020, 0.045), ("EXPOSED_SEABED", 0.050, 0.095), ("RISER_SPLASH", 0.065, 0.120)]
    rows = []
    for j in range(1, 321):
        zn, f_mean, f_fin = zones[(j - 1) % 3]
        area_m2 = round(38.4 + (j % 7) * 1.2, 2)
        rows.append({"joint_no": j, "exposure_zone": zn, "outer_area_m2": area_m2, "f_cbm_mean": f_mean, "f_cbf_final": f_fin, "joint_state": "INSTALLED" if (j % 31 != 0) else "SPARE_YARD"})
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    # Role A: Exclude KELP_FALSE_ECHO, convert seabed_lat_m = seabed_msl_m + (-1.35) -> deeper!Wait: if seabed_msl_m = -39.20 m and LAT is 1.35 m below MSL, then seabed elevation above LAT is -39.20 - (-1.35) = -37.85 m LAT! Let's make column explicit: seabed_lat_m = seabed_msl_m + lat_elevation_shift_m (+1.35 m) so cut depth above -42.50 m LAT is max(0, seabed_lat_m - (-42.50))!
    srows = [r for r in _generate_soundings() if r["beam_quality"] == "IHO_ORDER_1A"]
    areas = []
    for r in srows:
        lat_z = r["seabed_msl_m"] + 1.35
        d = max(0.0, lat_z - (-42.50))
        areas.append((3.0 + 2.0 * d) * d)
    # Mean cross-sectional area * 7475.0 m corridor length, multiplied by 1.12 bulking swell factor!
    dredge_m3 = (sum(areas) / len(areas)) * 7475.0 * 1.12
    or_a = {
        "valid_sounding_count": len(srows),
        "verified_ferrous_uxo_count": 9,
        "bulked_dredge_volume_m3": round(dredge_m3, 1),
        "project_crs_authid": "EPSG:32631",
        "qgis_datum_code": QGIS_DATUM_CODE,
    }

    # Role B: DNV-RP-B401 net Al-Zn-In anode mass M = (I_cm * t_f * 8760) / (u * epsilon),
    # where I_cm = sum(area * i_cm * f_cbm_mean), t_f = 25 yr, utilization u = 0.85, electrochemical capacity epsilon = 2000 Ah/kg (cold seawater 6C derated to 1840 Ah/kg in SQLite anode_alloy_derating!)
    # Mean current density i_cm = 0.070 A/m2 on BURIAL_TRENCH, 0.150 A/m2 on EXPOSED_SEABED, 0.180 A/m2 on RISER_SPLASH!
    ic_map = {"BURIAL_TRENCH": 0.070, "EXPOSED_SEABED": 0.150, "RISER_SPLASH": 0.180}
    jrows = [r for r in _generate_pipeline_joints() if r["joint_state"] == "INSTALLED"]
    by_z_mass: dict[str, float] = {k: 0.0 for k in ic_map}
    for r in jrows:
        zn = r["exposure_zone"]
        i_amp = r["outer_area_m2"] * ic_map[zn] * r["f_cbm_mean"]
        mass_kg = (i_amp * 25.0 * 8760.0) / (0.85 * 1840.0)
        by_z_mass[zn] += mass_kg
    by_z_r = {k: round(v, 2) for k, v in by_z_mass.items()}
    or_b = {
        "installed_joint_count": len(jrows),
        "zone_anode_mass_kg": by_z_r,
        "total_net_anode_mass_kg": round(sum(by_z_r.values()), 2),
        "dnv_anode_code": DNV_ANODE_CODE,
    }
    return or_a, or_b


BATHY_ORACLE, ANODE_ORACLE = _compute_oracles()

PORTAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>North Sea Pipeline Geomatics & DNV-RP-B401</title>
<style>body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace} .box{background:#1e293b;padding:16px;border:1px solid #334155;margin-top:12px}</style></head><body>
<h2>North Sea Trunkline Engineering Console</h2>
<div class="box">
  <h3>QGIS 3.22 Route Geomatics (`north_sea_route.qgs`)</h3>
  <p>Set live QGIS project CRS to <code>EPSG:32631</code> (WGS 84 / UTM zone 31N), apply layer filter <code>"verified_ferrous" = 1</code> on layer <code>uxo_contacts</code>, and save the QGIS project cleanly.</p>
  <p>Trench Design: Bottom elevation <code>-42.50 m LAT</code>, bottom width <code>b = 3.0 m</code>, side slopes <code>1:2 (z = 2.0)</code>, corridor length <code>7475.0 m</code>.</p>
  <p>UKHO Datum Code: <strong style="color:#4ade80">__QG__</strong></p>
</div>
<div class="box">
  <h3>DNV-RP-B401 25-Year Sacrificial Anode Design</h3>
  <p>Design life <code>t_f = 25.0 yr</code> (8760 h/yr), slender stand-off utilization factor <code>u = 0.85</code>.</p>
  <p>Mean bare-steel current densities: <code>BURIAL_TRENCH = 0.070 A/m^2</code>, <code>EXPOSED_SEABED = 0.150 A/m^2</code>, <code>RISER_SPLASH = 0.180 A/m^2</code>.</p>
  <p>DNV Qualification Code: <strong style="color:#38bdf8">__DNV__</strong></p>
</div>
</body></html>""".replace("__QG__", QGIS_DATUM_CODE).replace("__DNV__", DNV_ANODE_CODE)


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — North Sea UTM31N QGIS Project & Trench Dredge Volume (`marine_bathymetry_gis_lead`)",
        "",
        "## Objective",
        f"Update `{b}/workspace/gis/north_sea_route.qgs{b}` in the live **QGIS 3.22** window per `http://127.0.0.1:{PORTAL_PORT}/offshore` (keeping QGIS saved and synchronized), reconcile `{b}/workspace/survey/multibeam_soundings.sqlite{b}` per `{b}/workspace/docs/SOP_Bathymetry.pdf{b}`, and write `{b}/workspace/bathymetry_uxo_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — DNV-RP-B401 25-Year Al-Zn-In Anode Mass Schedule (`cathodic_protection_engineer`)",
        "",
        "## Objective",
        f"Size sacrificial anode mass across `{b}/workspace/cp/pipeline_spans.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/offshore` and `{b}/workspace/docs/SOP_DNV_B401.pdf{b}`, populate `{b}/workspace/Anode_Mass_Schedule.xlsx{b}` in LibreOffice Calc, and write `{b}/workspace/cathodic_anode_audit.json{b}`.",
    ])
    return {"marine_bathymetry_gis_lead": ta, "cathodic_protection_engineer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["marine_bathymetry_gis_lead"]
    ws_b = workspace_map["cathodic_protection_engineer"]
    for d in (ws_a / "gis", ws_a / "survey", ws_a / "docs", ws_b / "cp", ws_b / "docs"):
        d.mkdir(parents=True, exist_ok=True)

    feats = []
    for k in range(1, 16):
        feats.append({
            "type": "Feature",
            "properties": {"uxo_id": f"UXO-{k:02d}", "verified_ferrous": 1 if k <= 9 else 0, "mag_nt": 45 + k * 8},
            "geometry": {"type": "Point", "coordinates": [2.15 + k * 0.01, 56.40 + k * 0.005]},
        })
    gjson_p = ws_a / "gis/uxo_contacts.geojson"
    write_json(gjson_p, {"type": "FeatureCollection", "features": feats})
    qgs_p = ws_a / "gis/north_sea_route.qgs"
    subprocess.run([
        "python3", "-c",
        "from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem; "
        "app = QgsApplication([], False); app.initQgis(); "
        "prj = QgsProject.instance(); prj.setCrs(QgsCoordinateReferenceSystem('EPSG:4326')); "
        f"lyr = QgsVectorLayer({json.dumps(str(gjson_p))}, 'uxo_contacts', 'ogr'); prj.addMapLayer(lyr); "
        f"prj.write({json.dumps(str(qgs_p))}); app.exitQgis()",
    ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)

    with sqlite3.connect(str(ws_a / "survey/multibeam_soundings.sqlite")) as conn:
        conn.execute("CREATE TABLE echosounder_profile (station_idx INTEGER PRIMARY KEY, chainage_m REAL, seabed_msl_m REAL, beam_quality TEXT)")
        for r in _generate_soundings():
            conn.execute("INSERT INTO echosounder_profile VALUES (?,?,?,?)", (r["station_idx"], r["chainage_m"], r["seabed_msl_m"], r["beam_quality"]))
        conn.execute("CREATE TABLE geotechnical_datum_rules (msl_to_lat_elevation_shift_m REAL, boulder_clay_bulking_factor REAL)")
        conn.execute("INSERT INTO geotechnical_datum_rules VALUES (1.35, 1.12)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_Bathymetry.pdf", "SOP-GEO-1010A: QGIS UTM31N Project & Trench Dredge Volume", [
        ("1. QGIS Reprojection, UXO Filtering & Bulked Dredge Cut", [
            "1.1 Configure north_sea_route.qgs in QGIS 3.22 to EPSG:32631 with subset filter \"verified_ferrous\" = 1 on uxo_contacts.",
            "1.2 Filter multibeam_soundings.sqlite to IHO_ORDER_1A soundings, convert MSL elevations to LAT and apply boulder-clay bulking from geotechnical_datum_rules in SQLite, and compute bulked_dredge_volume_m3 = mean_trapezoidal_area * 7475.0 * bulking_factor.",
        ]),
        ("2. JSON Schema (/workspace/bathymetry_uxo_audit.json)", [
            "Keys: valid_sounding_count (int), verified_ferrous_uxo_count (int), bulked_dredge_volume_m3 (float, 1 dec), project_crs_authid (str), qgis_datum_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "cp/pipeline_spans.sqlite")) as conn:
        conn.execute("CREATE TABLE joints (joint_no INTEGER PRIMARY KEY, exposure_zone TEXT, outer_area_m2 REAL, f_cbm_mean REAL, f_cbf_final REAL, joint_state TEXT)")
        for r in _generate_pipeline_joints():
            conn.execute("INSERT INTO joints VALUES (?,?,?,?,?,?)", (r["joint_no"], r["exposure_zone"], r["outer_area_m2"], r["f_cbm_mean"], r["f_cbf_final"], r["joint_state"]))
        conn.execute("CREATE TABLE anode_alloy_seawater_derating (seabed_temp_c REAL, nominal_20c_ah_per_kg REAL, derated_6c_ah_per_kg REAL)")
        conn.execute("INSERT INTO anode_alloy_seawater_derating VALUES (6.0, 2000.0, 1840.0)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_DNV_B401.pdf", "SOP-CP-1010B: DNV-RP-B401 Net Anode Mass Qualification", [
        ("1. Electrochemical Anode Sizing", [
            "1.1 Retain INSTALLED joints in /workspace/cp/pipeline_spans.sqlite and compute net Al-Zn-In anode mass per exposure zone using DNV-RP-B401 mean current demand and North Sea 6C seabed alloy capacity in SQLite.",
            "1.2 Populate Anode_Mass_Schedule.xlsx Sheet 'ZoneMass': B2..B4 = BURIAL_TRENCH, EXPOSED_SEABED, RISER_SPLASH net mass kg; B5 = '=SUM(B2:B4)'; B6 = dnv_anode_code. Preserve Control!B2 = 'DNV-NORTHSEA-10' and save in Calc.",
        ]),
        ("2. JSON Schema (/workspace/cathodic_anode_audit.json)", [
            "Keys: installed_joint_count (int), zone_anode_mass_kg (dict), total_net_anode_mass_kg (float, 2 dec), dnv_anode_code (str).",
        ]),
    ])
    write_multisheet_xlsx(ws_b / "Anode_Mass_Schedule.xlsx", [
        ("Control", [["Field", "Value"], ["Marker", "DNV-NORTHSEA-10"]]),
        ("ZoneMass", [
            ["Exposure_Zone", "Net_Anode_Mass_kg"],
            ["BURIAL_TRENCH", 0.0], ["EXPOSED_SEABED", 0.0], ["RISER_SPLASH", 0.0],
            ["Total_Net_Mass_kg", ("=SUM(B2:B4)", 0.0)],
            ["DNV_Code", "PENDING"],
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                raw = b"<html><body><script>location.href='/offshore';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"off_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "off_sso" not in c or c["off_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            raw = PORTAL_HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    if "marine_bathymetry_gis_lead" in roles:
        launch_qgis_gui_natural(workspace_map["marine_bathymetry_gis_lead"] / "gis/north_sea_route.qgs")
    if "cathodic_protection_engineer" in roles:
        launch_libreoffice_uno_natural([workspace_map["cathodic_protection_engineer"] / "Anode_Mass_Schedule.xlsx"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["marine_bathymetry_gis_lead"]
    ws_b = workspace_map["cathodic_protection_engineer"]
    ja = read_json_safe(ws_a / "bathymetry_uxo_audit.json")
    jb = read_json_safe(ws_b / "cathodic_anode_audit.json")
    qg_live = inspect_live_qgis_readonly()
    uno_st = inspect_live_uno_documents_readonly()
    qgs_txt = (ws_a / "gis/north_sea_route.qgs").read_text(errors="ignore") if (ws_a / "gis/north_sea_route.qgs").is_file() else ""

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    live_uxo = (qg_live.get("layers") or {}).get("uxo_contacts") or {}
    qgis_synced = bool(qg_live.get("running")) and (not qg_live.get("is_dirty")) and (qg_live.get("crs") == "EPSG:32631") and (live_uxo.get("count") == 9)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing bathymetry_uxo_audit.json"),
        ("a_qgs_crs", "EPSG:32631" in qgs_txt and ja.get("project_crs_authid") == "EPSG:32631", 0.14, "north_sea_route.qgs not reprojected to EPSG:32631"),
        ("a_uxo_filt", ja.get("verified_ferrous_uxo_count") == 9 and ("verified_ferrous" in qgs_txt), 0.14, "uxo_contacts verified_ferrous=1 filter missing"),
        ("a_qgis_live_sync", bool(ja) and qgis_synced, 0.14, "Live open QGIS 3.22 GUI out-of-sync with disk north_sea_route.qgs"),
        ("a_cnt", ja.get("valid_sounding_count") == BATHY_ORACLE["valid_sounding_count"], 0.10, "valid_sounding_count mismatch"),
        ("a_code", ja.get("qgis_datum_code") == QGIS_DATUM_CODE, 0.12, "qgis_datum_code mismatch"),
        ("a_fine_lat_bulked_vol", abs(_f(ja.get("bulked_dredge_volume_m3")) - BATHY_ORACLE["bulked_dredge_volume_m3"]) <= 25.0, 0.28, f"bulked_dredge_volume_m3 != {BATHY_ORACLE['bulked_dredge_volume_m3']} (check +1.35m LAT shift & 1.12x bulking in geotechnical_datum_rules)"),
    ]

    xp = ws_b / "Anode_Mass_Schedule.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    calc_sync = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Anode_Mass_Schedule.xlsx" in u_url:
            calc_sync = (not u_doc.get("is_modified")) and (DNV_ANODE_CODE in json.dumps(u_doc.get("sheets") or {}))

    zm = jb.get("zone_anode_mass_kg") if isinstance(jb.get("zone_anode_mass_kg"), dict) else {}
    exp_zm = ANODE_ORACLE["zone_anode_mass_kg"]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing cathodic_anode_audit.json"),
        ("b_cnt", jb.get("installed_joint_count") == ANODE_ORACLE["installed_joint_count"], 0.12, "installed_joint_count mismatch"),
        ("b_mass_coarse", abs(_f(jb.get("total_net_anode_mass_kg")) - ANODE_ORACLE["total_net_anode_mass_kg"]) <= ANODE_ORACLE["total_net_anode_mass_kg"] * 0.12, 0.14, "total_net_anode_mass_kg coarse off"),
        ("b_xlsx_sum", "SUM(B2:B4)" in str(((shs.get("ZoneMass") or {}).get("B5") or {}).get("formula") or "").upper(), 0.12, "ZoneMass!B5 =SUM(B2:B4) formula missing"),
        ("b_code", jb.get("dnv_anode_code") == DNV_ANODE_CODE, 0.12, "dnv_anode_code mismatch"),
        ("b_calc_sync", bool(jb) and calc_sync, 0.12, "Open Calc window out-of-sync with disk .xlsx"),
        ("b_fine_1840_derating", sum(1 for k, v in exp_zm.items() if abs(_f(zm.get(k)) - v) <= 1.0) == 3 and abs(_f(jb.get("total_net_anode_mass_kg")) - ANODE_ORACLE["total_net_anode_mass_kg"]) <= 2.0, 0.30, "Missed 6C seawater 1840 Ah/kg alloy derating in anode_alloy_seawater_derating"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "marine_bathymetry_gis_lead":
        qgs_p = ws / "gis/north_sea_route.qgs"
        subprocess.run([
            "python3", "-c",
            "from qgis.core import QgsApplication, QgsProject, QgsCoordinateReferenceSystem\n"
            "app = QgsApplication([], False)\napp.initQgis()\n"
            f"prj = QgsProject.instance()\nprj.read({json.dumps(str(qgs_p))})\n"
            "prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32631'))\n"
            "for lyr in prj.mapLayers().values():\n"
            "    if lyr.name() == 'uxo_contacts': lyr.setSubsetString('\"verified_ferrous\" = 1')\n"
            f"prj.write({json.dumps(str(qgs_p))})\napp.exitQgis()\n",
        ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)
        reload_qgis_gui_project(qgs_p)
        write_json(ws / "bathymetry_uxo_audit.json", BATHY_ORACLE)
    else:
        xp = ws / "Anode_Mass_Schedule.xlsx"
        zm = ANODE_ORACLE["zone_anode_mass_kg"]
        write_multisheet_xlsx(xp, [
            ("Control", [["Field", "Value"], ["Marker", "DNV-NORTHSEA-10"]]),
            ("ZoneMass", [
                ["Exposure_Zone", "Net_Anode_Mass_kg"],
                ["BURIAL_TRENCH", zm["BURIAL_TRENCH"]],
                ["EXPOSED_SEABED", zm["EXPOSED_SEABED"]],
                ["RISER_SPLASH", zm["RISER_SPLASH"]],
                ["Total_Net_Mass_kg", ("=SUM(B2:B4)", ANODE_ORACLE["total_net_anode_mass_kg"])],
                ["DNV_Code", DNV_ANODE_CODE],
            ]),
        ])
        with file_atomic_lock("nf210_uno"):
            reload_uno_pipe_documents([xp])
        write_json(ws / "cathodic_anode_audit.json", ANODE_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("marine_bathymetry_gis_lead", workspace_map, port)
    solve_role("cathodic_protection_engineer", workspace_map, port)
    update_single_sheet_xlsx(workspace_map["cathodic_protection_engineer"] / "Anode_Mass_Schedule.xlsx", "ZoneMass", [
        ["Exposure_Zone", "Net_Anode_Mass_kg"], ["BURIAL_TRENCH", 0.0],
    ])
    jb = read_json_safe(workspace_map["cathodic_protection_engineer"] / "cathodic_anode_audit.json")
    jb["total_net_anode_mass_kg"] = 0.0
    write_json(workspace_map["cathodic_protection_engineer"] / "cathodic_anode_audit.json", jb)
