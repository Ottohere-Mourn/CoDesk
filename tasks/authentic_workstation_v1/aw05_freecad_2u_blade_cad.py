"""AW-05: ECN-204 2U Compute Blade Release — FreeCAD Thermal Shroud Perforation vs. QSFP-DD EMC Bulkhead & Silkscreen."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    cell_float,
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
    "id": "AW-05",
    "slug": "freecad_2u_blade_cad",
    "title": "ECN-204 2U Compute Blade Release: FreeCAD Thermal Shroud Perforation vs. QSFP-DD EMC Bulkhead & Silkscreen",
    "domain": "3D Mechanical CAD & EMC Hardware Engineering (FreeCAD 0.20 + Inkscape 1.2 + LibreOffice Calc + Chromium PLM)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19605,
    "roles": ("mech_chassis_eng", "emc_bezel_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
}

ECN_CONTROL_CODE = "ECN-204-REV-C-26G"
AL6061_G_PER_MM3 = 0.00270  # 2.70 g/cm^3
SS304_G_PER_MM3 = 0.00800   # 8.00 g/cm^3
BEZEL_FIXED_MASS_G = 142.50
PAM4_FREQ_GHZ = 26.5625
ANODIZE_COATING_G = round(2.0 * (42.0 * 28.0) * 0.0065, 2)

TICKET_A = (
    "# Work Order — 2U Chassis & Thermal Mechanical Engineer (`mech_chassis_eng`)\n\n"
    "Execute the `TopShroud` perforation array modification, STEP CAD export, and thermal mass signoff for ECN-204 in `/workspace/blade_2u`:\n\n"
    "1. Review `/workspace/blade_2u/specs/Mechanical_EMC_Thermal_Spec.pdf` and inspect the **Hardware PLM ECN-204 Portal** open in Chromium (`http://127.0.0.1:19605`).\n"
    "2. Inspect `TopShroud` and `RearBulkhead` inside `/workspace/blade_2u/server_blade_2u.FCStd`: identify all elevated structural features (`Z > 2.0 mm`, including the central stiffener rib and internal sensor bosses) on `TopShroud`, omit any candidate grid hole violating the keep-out rules in the spec, and select the standard punch diameter (`6.0 mm` or `8.0 mm`) that keeps combined chassis backpressure `chassis_delta_p_pa` within `[48.0, 56.0] Pa` against `RearBulkhead` in `server_blade_2u.FCStd` (preserving `RearBulkhead` when saving!).\n"
    "3. Export the modified `TopShroud` solid to `/workspace/blade_2u/exports/TopShroud_ECN204.step` (and if `ServerBlade2U_Assy.step` already exists in `exports/`, refresh it with both solids).\n"
    "4. Update `Thermal_Shroud` and cell `B2` (`TopShroud_Coated_Mass_g`, including Type-III anodize coating mass per spec!) on `Assembly_Mass_Rollup` inside `/workspace/blade_2u/Blade_ECN204_BOM.xlsx` (preserving sibling sheets and `B3:B5`!), and write `/workspace/blade_2u/thermal_shroud_ecn.json` with:\n"
    "   - `ecn_control_code`, `selected_hole_diameter_mm`, `active_vent_hole_count`, `vent_open_area_mm2`\n"
    "   - `top_shroud_volume_mm3`, `top_shroud_coated_mass_g`, `chassis_delta_p_pa`\n"
)

TICKET_B = (
    "# Work Order — Rear Bulkhead & EMC Silkscreen Engineer (`emc_bezel_eng`)\n\n"
    "Execute the `RearBulkhead` 8-port QSFP-DD + dual-PSU CAD modification, front bezel silkscreen update, and EMC aperture signoff for ECN-204 in `/workspace/blade_2u`:\n\n"
    "1. Review `/workspace/blade_2u/specs/Mechanical_EMC_Thermal_Spec.pdf` and inspect the **Hardware PLM ECN-204 Portal** in Chromium (`http://127.0.0.1:19605`, converting imperial vendor dimensions to millimeters).\n"
    "2. Inspect `TopShroud` and `RearBulkhead` inside `/workspace/blade_2u/server_blade_2u.FCStd` (preserving `TopShroud`!): cut all `8` rectangular QSFP-DD port apertures, both redundant PSU bay openings, AND the standard `5.0 mm` upper EMI exhaust hole count (`50` or `80` holes) that keeps combined chassis backpressure `chassis_delta_p_pa` within `[48.0, 56.0] Pa` against `TopShroud`, then export `/workspace/blade_2u/exports/RearBulkhead_ECN204.step` AND `/workspace/blade_2u/exports/ServerBlade2U_Assy.step`.\n"
    "3. Update `/workspace/blade_2u/front_bezel_silkscreen.svg` to replace `PENDING_PORT_LEGEND` and `PENDING_EMC_BADGE` with `QSFP-DD PORTS 0-7 (26.5625 GHz PAM4)` and the PLM `ecn_control_code`, and export `/workspace/blade_2u/front_bezel_proof.pdf` via `inkscape`.\n"
    "4. Update `EMC_Bulkhead` and `Assembly_Mass_Rollup` cells `B3:B4` (`RearBulkhead_Mass_g`, `FrontBezel_Hardware_Mass_g`, preserving `B2` and `B5` formula `=SUM(B2:B4)`!) in `/workspace/blade_2u/Blade_ECN204_BOM.xlsx`, and write `/workspace/blade_2u/emc_bulkhead_ecn.json` with:\n"
    "   - `ecn_control_code`, `qsfp_cutout_width_mm`, `qsfp_cutout_height_mm`, `qsfp_diagonal_mm`\n"
    "   - `lambda_over_20_limit_mm`, `emc_gasket_perimeter_total_mm`, `selected_emi_hole_count`\n"
    "   - `rear_bulkhead_volume_mm3`, `rear_bulkhead_mass_g`, `chassis_delta_p_pa`\n"
)


def _active_shroud_points() -> list[tuple[float, float]]:
    xs = [30.0 + 20.0 * i for i in range(19)]
    ys = [28.0 + 20.0 * j for j in range(12)]
    pts: list[tuple[float, float]] = []
    for x in xs:
        for y in ys:
            if abs(y - 140.0) <= 14.0:
                continue
            if (72.0 <= x <= 108.0 and 50.0 <= y <= 86.0) or (312.0 <= x <= 348.0 and 194.0 <= y <= 230.0):
                continue
            pts.append((x, y))
    return pts


def compute_cad_oracle(d_vent: float = 8.0, n_emi: int = 50) -> dict[str, Any]:
    pts = _active_shroud_points()
    n_holes = len(pts)
    r_vent = d_vent / 2.0
    hole_area = math.pi * (r_vent ** 2)
    open_area_mm2 = round(n_holes * hole_area, 2)
    init_shroud_vol = 420.0 * 280.0 * 2.0 + 420.0 * 16.0 * 3.0 + 2.0 * (24.0 * 24.0 * 4.0)
    final_shroud_vol = round(init_shroud_vol - n_holes * hole_area * 2.0, 2)
    shroud_coated_mass_g = round(final_shroud_vol * AL6061_G_PER_MM3 + ANODIZE_COATING_G, 2)

    # RearBulkhead: 420 x 84 x 2.5 mm SS-304 (88,200 mm^3)
    q_w = round(780.0 * 0.0254, 4)   # 19.812 mm
    q_h = round(390.0 * 0.0254, 4)   # 9.906 mm
    q_diag = round(math.hypot(q_w, q_h), 3)
    psu_w = round(2.20 * 25.4, 4)    # 55.88 mm
    psu_h = round(1.50 * 25.4, 4)    # 38.10 mm
    lam_mm = 299792458000.0 / (PAM4_FREQ_GHZ * 1e9)
    lam_20 = round(lam_mm / 20.0, 3)
    gasket_perim = round(8.0 * 2.0 * (q_w + q_h), 2)

    emi_area = n_emi * math.pi * (2.5 ** 2)
    init_bulk_vol = 420.0 * 84.0 * 2.5
    cut_vol = (8.0 * q_w * q_h + 2.0 * psu_w * psu_h + emi_area) * 2.5
    final_bulk_vol = round(init_bulk_vol - cut_vol, 2)
    bulk_mass_g = round(final_bulk_vol * SS304_G_PER_MM3, 2)
    total_assy_mass_g = round(shroud_coated_mass_g + bulk_mass_g + BEZEL_FIXED_MASS_G, 2)
    dp_pa = round(9.6e8 / (open_area_mm2 ** 2) + 3.8e7 / (emi_area ** 2), 2)

    return {
        "ecn_control_code": ECN_CONTROL_CODE,
        "points": pts,
        "selected_hole_diameter_mm": d_vent,
        "active_vent_hole_count": n_holes,
        "vent_open_area_mm2": open_area_mm2,
        "top_shroud_volume_mm3": final_shroud_vol,
        "top_shroud_mass_g": shroud_coated_mass_g,
        "top_shroud_coated_mass_g": shroud_coated_mass_g,
        "qsfp_cutout_width_mm": round(q_w, 3),
        "qsfp_cutout_height_mm": round(q_h, 3),
        "qsfp_diagonal_mm": q_diag,
        "psu_width_mm": psu_w,
        "psu_height_mm": psu_h,
        "lambda_over_20_limit_mm": lam_20,
        "emc_gasket_perimeter_total_mm": gasket_perim,
        "selected_emi_hole_count": n_emi,
        "rear_bulkhead_volume_mm3": final_bulk_vol,
        "rear_bulkhead_mass_g": bulk_mass_g,
        "total_assy_mass_g": total_assy_mass_g,
        "chassis_delta_p_pa": dp_pa,
    }


def _run_freecad(py_code: str, timeout_s: int = 60) -> str:
    env = dict(os.environ)
    env.setdefault("HOME", "/tmp")
    cp = subprocess.run(["freecadcmd", "-c", py_code], env=env, check=True, capture_output=True, text=True, timeout=timeout_s)
    return cp.stdout


def _build_initial_fcstd(fcstd_path: Path) -> None:
    fcstd_path.parent.mkdir(parents=True, exist_ok=True)
    code = f"""
import FreeCAD, Part
doc = FreeCAD.newDocument("ServerBlade2U")
sheet = Part.makeBox(420.0, 280.0, 2.0)
rib = Part.makeBox(420.0, 16.0, 3.0, FreeCAD.Vector(0.0, 132.0, 2.0))
bw = Part.makeBox(24.0, 24.0, 4.0, FreeCAD.Vector(78.0, 56.0, 2.0))
be = Part.makeBox(24.0, 24.0, 4.0, FreeCAD.Vector(318.0, 200.0, 2.0))
base_s = sheet.fuse(rib).fuse(bw).fuse(be)
p_holes = [Part.makeCylinder(4.0, 6.0, FreeCAD.Vector(30.0 + 18.0*i, 30.0 + 20.0*j, -1.0)) for i in range(20) for j in range(5)]
shroud_obj = doc.addObject("Part::Feature", "TopShroud")
shroud_obj.Shape = base_s.cut(Part.makeCompound(p_holes))

plate = Part.makeBox(420.0, 84.0, 2.5, FreeCAD.Vector(0.0, 0.0, 10.0))
e_holes = [Part.makeCylinder(2.5, 6.0, FreeCAD.Vector(16.0 + 8.0*k, 72.0, 8.0)) for k in range(50)]
bulk_obj = doc.addObject("Part::Feature", "RearBulkhead")
bulk_obj.Shape = plate.cut(Part.makeCompound(e_holes))
doc.recompute()
doc.saveAs({str(fcstd_path)!r})
"""
    _run_freecad(code)


INITIAL_BEZEL_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="840" height="220" viewBox="0 0 840 220">
  <rect x="0" y="0" width="840" height="220" fill="#0f172a"/>
  <rect x="20" y="20" width="800" height="180" fill="none" stroke="#38bdf8" stroke-width="2"/>
  <text id="port_legend" x="45" y="95" fill="#f8fafc" font-family="DejaVu Sans Mono" font-size="22">PENDING_PORT_LEGEND</text>
  <text id="emc_badge" x="45" y="150" fill="#94a3b8" font-family="DejaVu Sans" font-size="18">EMC Signoff: PENDING_EMC_BADGE</text>
</svg>
"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    bdir = workspace_root / "shared" / "blade_2u"
    (bdir / "exports").mkdir(parents=True, exist_ok=True)
    (bdir / "specs").mkdir(parents=True, exist_ok=True)

    _build_initial_fcstd(bdir / "server_blade_2u.FCStd")
    (bdir / "front_bezel_silkscreen.svg").write_text(INITIAL_BEZEL_SVG, encoding="utf-8")

    write_multisheet_xlsx(
        bdir / "Blade_ECN204_BOM.xlsx",
        [
            (
                "Thermal_Shroud",
                [
                    ["Metric", "Value"],
                    ["Active_Vent_Hole_Count", 0],
                    ["Vent_Open_Area_mm2", 0.0],
                    ["TopShroud_Volume_mm3", 255360.0],
                    ["TopShroud_Mass_g", 0.0],
                ],
            ),
            (
                "EMC_Bulkhead",
                [
                    ["Metric", "Value"],
                    ["QSFP_Diagonal_mm", 0.0],
                    ["Lambda_Over_20_mm", 0.0],
                    ["EMC_Gasket_Perimeter_mm", 0.0],
                    ["RearBulkhead_Mass_g", 0.0],
                ],
            ),
            (
                "Assembly_Mass_Rollup",
                [
                    ["Component", "Mass_g"],
                    ["TopShroud_Mass_g", 0.0],
                    ["RearBulkhead_Mass_g", 0.0],
                    ["FrontBezel_Hardware_Mass_g", 0.0],
                    ["Total_Blade_Enclosure_Mass_g", ("=SUM(B2:B4)", 0.0)],
                ],
            ),
        ],
    )

    write_pdf_manual(
        bdir / "specs" / "Mechanical_EMC_Thermal_Spec.pdf",
        "2U Compute Blade Mechanical & EMC Specification (ECN-204)",
        [
            (
                "1. TopShroud Perforation Array & Stiffener Rib Keep-Out",
                [
                    "Inspect TopShroud in server_blade_2u.FCStd: it comprises a 420 x 280 x 2.0 mm Al-6061-T6 base plate (density 0.00270 g/mm^3) fused with a central stiffener rib (Y = 132..148 mm) AND two internal sensor mounting bosses (Z > 2.0 mm). Replace the legacy 100-hole pilot pattern with the ECN-204 candidate grid (X = 30.0 + 20.0*i for i=0..18; Y = 28.0 + 20.0*j for j=0..11), omitting any hole center within 6.0 mm of ANY elevated Z > 2.0 mm feature footprint (both rib and sensor bosses!).",
                    "Include MIL-A-8625 Type-III hard-coat anodize mass (6.5 mg/cm^2 across the two 420 x 280 mm main faces) in top_shroud_coated_mass_g and BOM cell B2.",
                ],
            ),
            (
                "2. RearBulkhead Imperial-to-Metric Conversion & Cutout Placement",
                [
                    "RearBulkhead in server_blade_2u.FCStd is a 420 x 84 x 2.5 mm SS-304 plate (density 8.00 g/cm^3 = 0.00800 g/mm^3). Convert all imperial vendor dimensions on PLM View B using exact 1 mil = 0.0254 mm and 1 inch = 25.4 mm.",
                    "Cut 8 rectangular QSFP-DD port apertures (lower-left x = 24.0 + 28.0*k for k=0..7, y = 26.0 mm), 2 redundant PSU bay apertures (lower-left x = 270.0 and 340.0 mm, y = 22.0 mm), AND N_emi circular 5.0 mm (r=2.5 mm) upper EMI exhaust vents completely through the 2.5 mm plate.",
                ],
            ),
            (
                "3. 26.5625 GHz PAM4 EMC Rule & Coupled Chassis Static Pressure Drop",
                [
                    "Compute free-space wavelength lambda_mm = 299792458000.0 / (f_GHz * 1e9) at the PAM4 Nyquist frequency in PLM View B, and maximum unshielded slot limit lambda_over_20_limit_mm = round(lambda_mm / 20.0, 3).",
                    "Because each QSFP-DD aperture diagonal exceeds lambda/20, conductive spring-finger gaskets are mandatory around all 8 QSFP-DD ports: emc_gasket_perimeter_total_mm = round(8 * 2 * (qsfp_width_mm + qsfp_height_mm), 2).",
                    "Aero-Thermal Coupling Law: plugged QSFP-DD transceivers and PSU modules contribute zero free exhaust area. Combined chassis static pressure drop at 89 CFM is delta_P_Pa = 9.6e8 / (A_shroud_open_mm2 ^ 2) + 3.8e7 / (A_rear_emi_open_mm2 ^ 2), which MUST lie within [48.0, 56.0] Pa! Standard punch options: TopShroud hole diameter D in {6.0, 8.0} mm; RearBulkhead 5.0 mm EMI vent count N_emi in {50, 80}. Inspect the partner solid in server_blade_2u.FCStd before finalizing!",
                ],
            ),
            (
                "4. Shared FreeCAD Assembly & BOM Preservation",
                [
                    "Both TopShroud and RearBulkhead reside inside /workspace/blade_2u/server_blade_2u.FCStd. Always open the current .FCStd document, update your assigned Part::Feature solid while keeping the other solid intact, and save!",
                ],
            ),
        ],
    )

    (tickets_root / "mech_chassis_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "emc_bezel_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "mech_chassis_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "emc_bezel_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "thermal", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw05_sess" in ck) and (ck["aw05_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw05_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Hardware PLM Session Required (Inspect open Chromium)</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["thermal"])[0]
                with lock:
                    if t in ("thermal", "emc") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return

            with lock:
                cur = state["active_tab"]
            if cur == "thermal":
                body = f"""
                <h2>View A — TopShroud Perforation Redline &amp; Alloy Spec</h2>
                <p><b>ECN Control Code:</b> <code>{ECN_CONTROL_CODE}</code></p>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>Standard Turret Punch Options:</b> <code>D_vent = 6.0 mm</code> or <code>8.0 mm</code> (select to satisfy <code>48.0..56.0 Pa</code> chassis backpressure!)</li>
                  <li><b>Grid Pitch:</b> X = <code>30.0 .. 390.0 mm</code> step <code>20.0 mm</code> (19 cols); candidate Y = <code>28.0 .. 248.0 mm</code> step <code>20.0 mm</code> (12 rows)</li>
                  <li><b>3D Feature Keep-Out:</b> Omit any hole center within <code>6.0 mm</code> of any elevated <code>Z &gt; 2.0 mm</code> solid feature (rib + sensor bosses in <code>server_blade_2u.FCStd</code>)</li>
                  <li><b>Al-6061-T6 Density:</b> <code>0.00270 g/mm^3</code> + Type-III Anodize <code>6.5 mg/cm^2</code> (2 main faces)</li>
                </ul>"""
            else:
                body = f"""
                <h2>View B — RearBulkhead Imperial Connector Print &amp; EMC Spec</h2>
                <p><b>ECN Control Code:</b> <code>{ECN_CONTROL_CODE}</code></p>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>Single QSFP-DD Cutout (8x):</b> Width = <code>780 mil</code>, Height = <code>390 mil</code> (<code>1 mil = 0.0254 mm</code>)</li>
                  <li><b>Redundant PSU Bay Cutout (2x):</b> Width = <code>2.20 inch</code>, Height = <code>1.50 inch</code> (<code>1 inch = 25.4 mm</code>)</li>
                  <li><b>Upper 5.0 mm EMI Exhaust Vent Options:</b> <code>N_emi = 50</code> or <code>80</code> holes (select to satisfy <code>48.0..56.0 Pa</code> chassis backpressure!)</li>
                  <li><b>PAM4 Fundamental Frequency:</b> <code>{PAM4_FREQ_GHZ} GHz</code> | <b>SS-304 Density:</b> <code>8.00 g/cm^3</code></li>
                  <li><b>Front Bezel &amp; Latch Subassembly Fixed Mass:</b> <code>{BEZEL_FIXED_MASS_G} g</code></li>
                </ul>"""

            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Hardware PLM ECN-204</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;color:#0f172a;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .box{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>Hardware PLM ECN-204 Redline Portal ({cur.upper()})</h1>
            <div class="nav">
              <a href="/tab?id=thermal">Thermal Shroud Vent Grid</a>
              <a href="/tab?id=emc">QSFP-DD &amp; EMC Bulkhead Print</a>
            </div>
            <div class="box">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1220, 820))
    bdir = workspace_root / "shared" / "blade_2u"
    if roles & {"mech_chassis_eng", "emc_bezel_eng"}:
        launch_desktop_app_as_user(
            f"nohup freecad '{bdir / 'server_blade_2u.FCStd'}' >/tmp/aw05_fc.log 2>&1 </dev/null &",
            wait_s=4.0,
        )
        launch_desktop_app_as_user(
            f"nohup libreoffice --norestore --nologo --nofirststartwizard '{bdir / 'Blade_ECN204_BOM.xlsx'}' >/tmp/aw05_calc.log 2>&1 </dev/null &",
            wait_s=2.0,
        )
    if "emc_bezel_eng" in roles:
        launch_desktop_app_as_user(
            f"nohup inkscape '{bdir / 'front_bezel_silkscreen.svg'}' >/tmp/aw05_ink.log 2>&1 </dev/null &",
            wait_s=2.0,
        )


def _merge_assy_rollup(xlsx_path: Path, updates: dict[str, float]) -> None:
    book = evaluate_xlsx_isolated(xlsx_path)
    cur = {
        "TopShroud_Mass_g": cell_float(book, "Assembly_Mass_Rollup", "B2") or 0.0,
        "RearBulkhead_Mass_g": cell_float(book, "Assembly_Mass_Rollup", "B3") or 0.0,
        "FrontBezel_Hardware_Mass_g": cell_float(book, "Assembly_Mass_Rollup", "B4") or 0.0,
    }
    cur.update(updates)
    tot = round(sum(cur.values()), 2)
    update_single_sheet_xlsx(
        xlsx_path,
        "Assembly_Mass_Rollup",
        [
            ["Component", "Mass_g"],
            ["TopShroud_Mass_g", cur["TopShroud_Mass_g"]],
            ["RearBulkhead_Mass_g", cur["RearBulkhead_Mass_g"]],
            ["FrontBezel_Hardware_Mass_g", cur["FrontBezel_Hardware_Mass_g"]],
            ["Total_Blade_Enclosure_Mass_g", ("=SUM(B2:B4)", tot)],
        ],
    )


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    bdir = workspace_root / "shared" / "blade_2u"
    fcstd_p = bdir / "server_blade_2u.FCStd"
    xlsx_p = bdir / "Blade_ECN204_BOM.xlsx"
    pts = _active_shroud_points()

    if role == "mech_chassis_eng":
        d_choice = 8.0
        ora = compute_cad_oracle(d_vent=8.0, n_emi=50)
        r_v = 4.0
        fc_script = f"""
import FreeCAD, Part, os
if not {cooperative!r}:
    doc = FreeCAD.newDocument("ServerBlade2U")
    b0 = doc.addObject("Part::Feature", "RearBulkhead")
    b0.Shape = Part.makeBox(420.0, 84.0, 2.5, FreeCAD.Vector(0.0, 0.0, 10.0))
    s_obj = doc.addObject("Part::Feature", "TopShroud")
else:
    doc = FreeCAD.openDocument({str(fcstd_p)!r})
    s_obj = doc.getObject("TopShroud")
sheet = Part.makeBox(420.0, 280.0, 2.0)
rib = Part.makeBox(420.0, 16.0, 3.0, FreeCAD.Vector(0.0, 132.0, 2.0))
bw = Part.makeBox(24.0, 24.0, 4.0, FreeCAD.Vector(78.0, 56.0, 2.0))
be = Part.makeBox(24.0, 24.0, 4.0, FreeCAD.Vector(318.0, 200.0, 2.0))
base = sheet.fuse(rib).fuse(bw).fuse(be)
holes = [Part.makeCylinder({r_v}, 6.0, FreeCAD.Vector(x, y, -1.0)) for (x, y) in {pts!r}]
s_obj.Shape = base.cut(Part.makeCompound(holes))
doc.recompute()
Part.export([s_obj], {str(bdir / 'exports' / 'TopShroud_ECN204.step')!r})
assy_p = {str(bdir / 'exports' / 'ServerBlade2U_Assy.step')!r}
if os.path.isfile(assy_p):
    Part.export([doc.getObject("TopShroud"), doc.getObject("RearBulkhead")], assy_p)
doc.saveAs({str(fcstd_p)!r})
"""
        if cooperative:
            with resource_lock("aw05_cad"):
                cad_locked = _inspect_cad_volumes(bdir)
                bulk_vl = float(cad_locked.get("fcstd_bulk_vol") or 85745.0)
                d_choice = 6.0 if bulk_vl < 70000.0 else 8.0
                n_peer = 80 if bulk_vl < 70000.0 else 50
                ora = compute_cad_oracle(d_vent=d_choice, n_emi=n_peer)
                fc_script_locked = fc_script.replace(f"makeCylinder({r_v},", f"makeCylinder({d_choice/2.0},")
                _run_freecad(fc_script_locked, timeout_s=90)
            with resource_lock("aw05_xlsx"):
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Thermal_Shroud",
                    [
                        ["Metric", "Value"],
                        ["Active_Vent_Hole_Count", ora["active_vent_hole_count"]],
                        ["Vent_Open_Area_mm2", ora["vent_open_area_mm2"]],
                        ["TopShroud_Volume_mm3", ora["top_shroud_volume_mm3"]],
                        ["TopShroud_Coated_Mass_g", ora["top_shroud_coated_mass_g"]],
                    ],
                )
                _merge_assy_rollup(xlsx_p, {"TopShroud_Mass_g": ora["top_shroud_coated_mass_g"]})
        else:
            _run_freecad(fc_script, timeout_s=90)
            write_multisheet_xlsx(xlsx_p, [("Thermal_Shroud", [["Metric", "Value"], ["TopShroud_Coated_Mass_g", ora["top_shroud_coated_mass_g"]]])])
        write_json(
            bdir / "thermal_shroud_ecn.json",
            {
                "ecn_control_code": ECN_CONTROL_CODE,
                "selected_hole_diameter_mm": ora["selected_hole_diameter_mm"],
                "active_vent_hole_count": ora["active_vent_hole_count"],
                "vent_open_area_mm2": ora["vent_open_area_mm2"],
                "top_shroud_volume_mm3": ora["top_shroud_volume_mm3"],
                "top_shroud_coated_mass_g": ora["top_shroud_coated_mass_g"],
                "chassis_delta_p_pa": ora["chassis_delta_p_pa"],
            },
        )
    elif role == "emc_bezel_eng":
        def _make_bulk_script(n_emi_val: int, coop_flag: bool) -> str:
            return f"""
import FreeCAD, Part
if not {coop_flag!r}:
    doc = FreeCAD.newDocument("ServerBlade2U")
    s0 = doc.addObject("Part::Feature", "TopShroud")
    s0.Shape = Part.makeBox(420.0, 280.0, 2.0).fuse(Part.makeBox(420.0, 16.0, 3.0, FreeCAD.Vector(0.0, 132.0, 2.0)))
    b_obj = doc.addObject("Part::Feature", "RearBulkhead")
else:
    doc = FreeCAD.openDocument({str(fcstd_p)!r})
    b_obj = doc.getObject("RearBulkhead")
plate = Part.makeBox(420.0, 84.0, 2.5, FreeCAD.Vector(0.0, 0.0, 10.0))
cuts = []
qw, qh = 780.0 * 0.0254, 390.0 * 0.0254
for k in range(8):
    cuts.append(Part.makeBox(qw, qh, 6.0, FreeCAD.Vector(24.0 + 28.0 * k, 26.0, 8.0)))
pw, ph = 2.20 * 25.4, 1.50 * 25.4
for px in (270.0, 340.0):
    cuts.append(Part.makeBox(pw, ph, 6.0, FreeCAD.Vector(px, 22.0, 8.0)))
for m in range({n_emi_val}):
    ex = 12.0 + 9.5 * (m % 40)
    ey = 68.0 if m < 40 else 76.0
    cuts.append(Part.makeCylinder(2.5, 6.0, FreeCAD.Vector(ex, ey, 8.0)))
b_obj.Shape = plate.cut(Part.makeCompound(cuts))
doc.recompute()
Part.export([b_obj], {str(bdir / 'exports' / 'RearBulkhead_ECN204.step')!r})
Part.export([doc.getObject("TopShroud"), b_obj], {str(bdir / 'exports' / 'ServerBlade2U_Assy.step')!r})
doc.saveAs({str(fcstd_p)!r})
"""
        if cooperative:
            with resource_lock("aw05_cad"):
                cad_locked = _inspect_cad_volumes(bdir)
                shroud_vl = float(cad_locked.get("fcstd_shroud_vol") or 249915.0)
                n_emi_choice = 50 if shroud_vl < 245000.0 else 80
                d_peer = 8.0 if shroud_vl < 245000.0 else 6.0
                ora = compute_cad_oracle(d_vent=d_peer, n_emi=n_emi_choice)
                if shroud_vl >= 248000.0:
                    emi_a = 80 * math.pi * 6.25
                    ora["chassis_delta_p_pa"] = round(9.6e8 / ((100 * math.pi * 16.0) ** 2) + 3.8e7 / (emi_a ** 2), 2)
                _run_freecad(_make_bulk_script(n_emi_choice, True), timeout_s=90)
            with resource_lock("aw05_xlsx"):
                update_single_sheet_xlsx(
                    xlsx_p,
                    "EMC_Bulkhead",
                    [
                        ["Metric", "Value"],
                        ["QSFP_Diagonal_mm", ora["qsfp_diagonal_mm"]],
                        ["Lambda_Over_20_mm", ora["lambda_over_20_limit_mm"]],
                        ["EMC_Gasket_Perimeter_mm", ora["emc_gasket_perimeter_total_mm"]],
                        ["RearBulkhead_Mass_g", ora["rear_bulkhead_mass_g"]],
                    ],
                )
                _merge_assy_rollup(
                    xlsx_p,
                    {
                        "RearBulkhead_Mass_g": ora["rear_bulkhead_mass_g"],
                        "FrontBezel_Hardware_Mass_g": BEZEL_FIXED_MASS_G,
                    },
                )
        else:
            ora = compute_cad_oracle(d_vent=8.0, n_emi=80)
            _run_freecad(_make_bulk_script(80, False), timeout_s=90)
            write_multisheet_xlsx(xlsx_p, [("EMC_Bulkhead", [["Metric", "Value"], ["RearBulkhead_Mass_g", ora["rear_bulkhead_mass_g"]]])])

        svg_p = bdir / "front_bezel_silkscreen.svg"
        svg_txt = INITIAL_BEZEL_SVG.replace("PENDING_PORT_LEGEND", "QSFP-DD PORTS 0-7 (26.5625 GHz PAM4)").replace("PENDING_EMC_BADGE", ECN_CONTROL_CODE)
        svg_p.write_text(svg_txt, encoding="utf-8")
        subprocess.run(
            ["inkscape", str(svg_p), "--export-type=pdf", f"--export-filename={bdir / 'front_bezel_proof.pdf'}"],
            check=True, capture_output=True, timeout=35,
        )
        write_json(
            bdir / "emc_bulkhead_ecn.json",
            {
                "ecn_control_code": ECN_CONTROL_CODE,
                "qsfp_cutout_width_mm": ora["qsfp_cutout_width_mm"],
                "qsfp_cutout_height_mm": ora["qsfp_cutout_height_mm"],
                "qsfp_diagonal_mm": ora["qsfp_diagonal_mm"],
                "lambda_over_20_limit_mm": ora["lambda_over_20_limit_mm"],
                "emc_gasket_perimeter_total_mm": ora["emc_gasket_perimeter_total_mm"],
                "selected_emi_hole_count": ora["selected_emi_hole_count"],
                "rear_bulkhead_volume_mm3": ora["rear_bulkhead_volume_mm3"],
                "rear_bulkhead_mass_g": ora["rear_bulkhead_mass_g"],
                "chassis_delta_p_pa": ora["chassis_delta_p_pa"],
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("mech_chassis_eng", workspace_root, cooperative=False)
    solve_role("emc_bezel_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "mech_chassis_eng", workspace_root, True)
        fb = pool.submit(solve_role, "emc_bezel_eng", workspace_root, True)
        fa.result()
        fb.result()
    bdir = workspace_root / "shared" / "blade_2u"
    with resource_lock("aw05_cad"):
        _run_freecad(
            f"""
import FreeCAD, Part
doc = FreeCAD.openDocument({str(bdir / 'server_blade_2u.FCStd')!r})
Part.export([doc.getObject("TopShroud"), doc.getObject("RearBulkhead")], {str(bdir / 'exports' / 'ServerBlade2U_Assy.step')!r})
""",
            timeout_s=45,
        )


def _inspect_cad_volumes(bdir: Path) -> dict[str, float]:
    fc_p = bdir / "server_blade_2u.FCStd"
    s_step = bdir / "exports" / "TopShroud_ECN204.step"
    b_step = bdir / "exports" / "RearBulkhead_ECN204.step"
    a_step = bdir / "exports" / "ServerBlade2U_Assy.step"
    probe = f"""
import json, os, FreeCAD, Part
out = {{}}
if os.path.isfile({str(fc_p)!r}):
    doc = FreeCAD.openDocument({str(fc_p)!r})
    if doc.getObject("TopShroud"):
        out["fcstd_shroud_vol"] = round(doc.getObject("TopShroud").Shape.Volume, 2)
    if doc.getObject("RearBulkhead"):
        out["fcstd_bulk_vol"] = round(doc.getObject("RearBulkhead").Shape.Volume, 2)
for key, sp in (("step_shroud_vol", {str(s_step)!r}), ("step_bulk_vol", {str(b_step)!r}), ("step_assy_vol", {str(a_step)!r})):
    if os.path.isfile(sp):
        sh = Part.read(sp)
        out[key] = round(sh.Volume, 2)
print("AW05_CAD_JSON:" + json.dumps(out))
"""
    try:
        stdout = _run_freecad(probe, timeout_s=60)
        for ln in stdout.splitlines():
            if ln.startswith("AW05_CAD_JSON:"):
                return json.loads(ln.split("AW05_CAD_JSON:", 1)[1])
    except Exception:
        pass
    return {}


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    bdir = workspace_root / "shared" / "blade_2u"
    ora_8_50 = compute_cad_oracle(8.0, 50)
    ora_6_80 = compute_cad_oracle(6.0, 80)
    ja = read_json_safe(bdir / "thermal_shroud_ecn.json")
    jb = read_json_safe(bdir / "emc_bulkhead_ecn.json")
    cad = _inspect_cad_volumes(bdir)
    book = evaluate_xlsx_isolated(bdir / "Blade_ECN204_BOM.xlsx")
    svg_txt = (bdir / "front_bezel_silkscreen.svg").read_text(encoding="utf-8", errors="replace") if (bdir / "front_bezel_silkscreen.svg").is_file() else ""
    pdf_txt = extract_pdf_text(bdir / "front_bezel_proof.pdf")

    def _close(v: Any, exp: float, tol: float) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    d_sel = float(ja.get("selected_hole_diameter_mm") or 8.0)
    ora_a = ora_6_80 if abs(d_sel - 6.0) < 0.5 else ora_8_50
    n_emi_sel = int(jb.get("selected_emi_hole_count") or (80 if active_mode == "isolated" else 50))
    ora_b = ora_6_80 if n_emi_sel == 80 else ora_8_50

    init_s_vol = 420.0 * 280.0 * 2.0 + 420.0 * 16.0 * 3.0 + 2.0 * (24.0 * 24.0 * 4.0)
    init_b_vol_after_ports = 420.0 * 84.0 * 2.5 - (8.0 * (780 * 0.0254) * (390 * 0.0254) + 2.0 * (2.2 * 25.4) * (1.5 * 25.4)) * 2.5
    fc_s_vol = cad.get("fcstd_shroud_vol")
    fc_b_vol = cad.get("fcstd_bulk_vol")
    live_dp_ok = False
    if isinstance(fc_s_vol, (int, float)) and isinstance(fc_b_vol, (int, float)):
        a_s_live = max(1.0, (init_s_vol - float(fc_s_vol)) / 2.0)
        if float(fc_b_vol) > 84000.0:
            a_r_live = 50.0 * math.pi * 6.25
        else:
            a_r_live = max(1.0, (init_b_vol_after_ports - float(fc_b_vol)) / 2.5)
        dp_live = 9.6e8 / (a_s_live ** 2) + 3.8e7 / (a_r_live ** 2)
        live_dp_ok = 48.0 <= dp_live <= 56.0

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_ecn_code", str(ja.get("ecn_control_code", "")).strip() == ECN_CONTROL_CODE, 1.0, "ecn_control_code missing/wrong"),
        ("a_hole_count", ja.get("active_vent_hole_count") == ora_a["active_vent_hole_count"], 2.0, f"active_vent_hole_count mismatch (expected {ora_a['active_vent_hole_count']} after rib + 2 sensor boss keep-outs)"),
        ("a_open_area", _close(ja.get("vent_open_area_mm2"), ora_a["vent_open_area_mm2"], 15.0), 1.5, f"vent_open_area_mm2 mismatch (expected {ora_a['vent_open_area_mm2']})"),
        ("a_json_vol", _close(ja.get("top_shroud_volume_mm3"), ora_a["top_shroud_volume_mm3"], 450.0), 1.8, f"top_shroud_volume_mm3 mismatch (expected {ora_a['top_shroud_volume_mm3']})"),
        ("a_json_coated_mass", _close(ja.get("top_shroud_coated_mass_g"), ora_a["top_shroud_coated_mass_g"], 1.5), 1.8, f"top_shroud_coated_mass_g mismatch (expected {ora_a['top_shroud_coated_mass_g']} including anodize)"),
        ("a_fcstd_shroud", _close(cad.get("fcstd_shroud_vol"), ora_a["top_shroud_volume_mm3"], 600.0), 2.2, f"server_blade_2u.FCStd TopShroud volume mismatch (got {cad.get('fcstd_shroud_vol')})"),
        ("a_step_shroud", _close(cad.get("step_shroud_vol"), ora_a["top_shroud_volume_mm3"], 600.0), 2.0, "exports/TopShroud_ECN204.step missing or wrong solid volume"),
        ("a_dp_band", isinstance(ja.get("chassis_delta_p_pa"), (int, float)) and 48.0 <= float(ja["chassis_delta_p_pa"]) <= 56.0, 1.5, "reported chassis_delta_p_pa outside [48.0, 56.0] Pa"),
        (
            "a_xlsx_shroud",
            _close(cell_float(book, "Assembly_Mass_Rollup", "B2"), ora_a["top_shroud_coated_mass_g"], 1.5),
            1.5,
            "Blade_ECN204_BOM.xlsx Assembly_Mass_Rollup!B2 TopShroud_Coated_Mass_g missing/wrong",
        ),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_ecn_code", str(jb.get("ecn_control_code", "")).strip() == ECN_CONTROL_CODE, 1.0, "ecn_control_code missing/wrong"),
        ("b_qsfp_dims", _close(jb.get("qsfp_cutout_width_mm"), ora_b["qsfp_cutout_width_mm"], 0.15) and _close(jb.get("qsfp_cutout_height_mm"), ora_b["qsfp_cutout_height_mm"], 0.15), 2.0, "QSFP-DD mil->mm dimensions mismatch"),
        ("b_lam20", _close(jb.get("lambda_over_20_limit_mm"), ora_b["lambda_over_20_limit_mm"], 0.025), 1.6, f"lambda_over_20_limit_mm mismatch (expected {ora_b['lambda_over_20_limit_mm']})"),
        ("b_gasket_perim", _close(jb.get("emc_gasket_perimeter_total_mm"), ora_b["emc_gasket_perimeter_total_mm"], 2.5), 1.6, f"emc_gasket_perimeter_total_mm mismatch (expected {ora_b['emc_gasket_perimeter_total_mm']})"),
        ("b_json_vol_mass", _close(jb.get("rear_bulkhead_volume_mm3"), ora_b["rear_bulkhead_volume_mm3"], 450.0) and _close(jb.get("rear_bulkhead_mass_g"), ora_b["rear_bulkhead_mass_g"], 3.5), 1.8, "rear_bulkhead volume/mass mismatch"),
        ("b_fcstd_bulk", _close(cad.get("fcstd_bulk_vol"), ora_b["rear_bulkhead_volume_mm3"], 600.0), 2.2, f"server_blade_2u.FCStd RearBulkhead volume mismatch (got {cad.get('fcstd_bulk_vol')})"),
        ("b_step_bulk", _close(cad.get("step_bulk_vol"), ora_b["rear_bulkhead_volume_mm3"], 600.0), 2.0, "exports/RearBulkhead_ECN204.step missing or wrong solid volume"),
        ("b_dp_band", isinstance(jb.get("chassis_delta_p_pa"), (int, float)) and 48.0 <= float(jb["chassis_delta_p_pa"]) <= 56.0, 1.5, "reported chassis_delta_p_pa outside [48.0, 56.0] Pa"),
        ("b_silkscreen_svg_pdf", ECN_CONTROL_CODE in svg_txt and "PENDING_PORT_LEGEND" not in svg_txt and ECN_CONTROL_CODE in pdf_txt, 1.5, "front_bezel_silkscreen.svg / front_bezel_proof.pdf missing ECN-204 silkscreen"),
        (
            "b_xlsx_bulk",
            _close(cell_float(book, "Assembly_Mass_Rollup", "B3"), ora_b["rear_bulkhead_mass_g"], 3.5)
            and _close(cell_float(book, "Assembly_Mass_Rollup", "B4"), BEZEL_FIXED_MASS_G, 0.5),
            1.5,
            "Blade_ECN204_BOM.xlsx Assembly_Mass_Rollup!B3:B4 missing/wrong",
        ),
    ]

    exp_assy_vol = ora_a["top_shroud_volume_mm3"] + ora_b["rear_bulkhead_volume_mm3"]
    exp_assy_mass = round(ora_a["top_shroud_coated_mass_g"] + ora_b["rear_bulkhead_mass_g"] + BEZEL_FIXED_MASS_G, 2)
    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_fcstd_contains_both_modified_solids",
            _close(cad.get("fcstd_shroud_vol"), ora_a["top_shroud_volume_mm3"], 600.0)
            and _close(cad.get("fcstd_bulk_vol"), ora_b["rear_bulkhead_volume_mm3"], 600.0),
            2.0,
            "Shared server_blade_2u.FCStd lost either TopShroud perforation or RearBulkhead cutouts due to concurrent CAD overwrite",
        ),
        (
            "j_coupled_chassis_delta_p_in_band",
            live_dp_ok,
            2.5,
            "Combined TopShroud + RearBulkhead open areas violate [48.0, 56.0] Pa coupled chassis static pressure window",
        ),
        (
            "j_assy_step_and_bom_rollup",
            _close(cad.get("step_assy_vol"), exp_assy_vol, 1000.0)
            and _close(cell_float(book, "Assembly_Mass_Rollup", "B5"), exp_assy_mass, 4.5),
            1.8,
            "ServerBlade2U_Assy.step volume or BOM B5 total mass does not combine both ECN-204 solids",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"mech_chassis_eng": TICKET_A, "emc_bezel_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
