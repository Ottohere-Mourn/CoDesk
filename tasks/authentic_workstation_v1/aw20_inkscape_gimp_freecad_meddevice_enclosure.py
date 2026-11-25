"""AW-20: Zero-Spoiler ISO 13485 Medical Monitor Release — FreeCAD 3D Housing + GIMP Overlays + Live Calc Arm Balance."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
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
    cell_formula,
    evaluate_xlsx_isolated,
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
    "id": "AW-20",
    "slug": "inkscape_gimp_freecad_meddevice_enclosure",
    "title": "ISO 13485 Medical Monitor Release: FreeCAD Bezel/VESA Housing + GIMP Overlays + Coupled Arm-Balance DHR",
    "domain": "Medical Device CAD, Graphic Overlay & DHR Signoff (FreeCAD 0.20 + GIMP 2.10 + LibreOffice Calc + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19620,
    "roles": ("front_bezel_overlay_eng", "rear_vesa_chassis_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

DHR_LOT = "ISO13485-MON-772"
PC_ABS_G_MM3 = 0.00118
MG_AZ91_G_MM3 = 0.00181
LENS_PMMA_G = 95.0
LENS_GLASS_G = 185.0
SINK_VAPOR_G = 140.0
SINK_EXTRU_G = 230.0
FIXED_CORE_G = 1320.0

TICKET_A = (
    "# Work Order — Front Display Bezel & Graphic Overlay Engineer (`front_bezel_overlay_eng`)\n\n"
    "Complete the `FrontBezel` 3D solid cutouts in `/workspace/enclosure/monitor_housing.FCStd`, prepare the production display graphic overlay inside **GIMP**, and complete the Front Subassembly & Arm-Balance DHR in the open **LibreOffice Calc** workbook (`ISO13485_DHR_Checklist.xlsx`):\n\n"
    "1. Read `/workspace/enclosure/specs/ISO13485_Enclosure_Spec.pdf` and inspect the **ISO 13485 PLM & DHR Portal** in Chromium (`http://127.0.0.1:19620`, `Overview` and `Front Display & Optical Spec` views, reading the visual engineering blueprint card).\n"
    "2. Update `FrontBezel` inside `/workspace/enclosure/monitor_housing.FCStd` (preserving `RearVesaPlate`!) with the specification's LCD aperture window and corner M4 clearance through-holes, export `/workspace/enclosure/FrontBezel.step`, and write `/workspace/enclosure/front_bezel_dhr.json` (`dhr_lot`, `bezel_volume_mm3`, `bezel_mass_g`, `selected_lens_mass_g`, `front_subassy_mass_g`).\n"
    "3. In the open **GIMP** window on the desktop, select the `display_overlay_raw.xcf` tab, hide all non-production FPO/guide layers per protocol while keeping the production mask and legend layers visible, scale the image canvas to the target raster dimensions on the portal spec card, and export `/srv/studio_project/exports/display_overlay_prod.png`.\n"
    "4. In the open **LibreOffice Calc** window (`ISO13485_DHR_Checklist.xlsx`), enter `bezel_volume_mm3` in `Front_Assy!B2`, `bezel_mass_g` in `Front_Assy!B3`, your selected cover-lens mass in `Front_Assy!B4`, `=SUM(B3:B4)` in `Front_Assy!B5`, and enter `front_subassy_mass_g` in `Arm_Counterbalance!B2` so total monitor head mass (`Arm_Counterbalance!B5`) satisfies the ICU Arm Counterbalance window, then save (`Ctrl+S`).\n"
)

TICKET_B = (
    "# Work Order — Rear VESA Magnesium Chassis & Rating Decal Engineer (`rear_vesa_chassis_eng`)\n\n"
    "Complete the `RearVesaPlate` 3D solid cutouts in `/workspace/enclosure/monitor_housing.FCStd`, prepare the production rear rating decal inside **GIMP**, and complete the Rear Subassembly & Arm-Balance DHR in the open **LibreOffice Calc** workbook (`ISO13485_DHR_Checklist.xlsx`):\n\n"
    "1. Read `/workspace/enclosure/specs/ISO13485_Enclosure_Spec.pdf` and inspect the **ISO 13485 PLM & DHR Portal** in Chromium (`http://127.0.0.1:19620`, `Overview` and `Rear VESA & Thermal Spec` views, reading the visual engineering blueprint card).\n"
    "2. Update `RearVesaPlate` inside `/workspace/enclosure/monitor_housing.FCStd` (preserving `FrontBezel`!) with the specification's VESA-100 mounting pattern, recessed I/O connector opening, and upper cooling vent row, export `/workspace/enclosure/RearVesaPlate.step`, and write `/workspace/enclosure/rear_vesa_dhr.json` (`dhr_lot`, `rear_volume_mm3`, `rear_mass_g`, `selected_heatsink_mass_g`, `rear_subassy_mass_g`).\n"
    "3. In the open **GIMP** window on the desktop, select the `rear_decal_raw.xcf` tab, hide all non-production proof/grid layers per protocol while keeping the foil substrate and UDI rating layers visible, scale the image canvas to the target raster dimensions on the portal spec card, and export `/srv/studio_project/exports/rear_decal_prod.png`.\n"
    "4. In the open **LibreOffice Calc** window (`ISO13485_DHR_Checklist.xlsx`), enter `rear_volume_mm3` in `Rear_Assy!B2`, `rear_mass_g` in `Rear_Assy!B3`, your selected heatsink mass in `Rear_Assy!B4`, `=SUM(B3:B4)` in `Rear_Assy!B5`, and enter `rear_subassy_mass_g` in `Arm_Counterbalance!B3` so total monitor head mass (`Arm_Counterbalance!B5`) satisfies the ICU Arm Counterbalance window, then save (`Ctrl+S`).\n"
)


def _fc(code: str) -> str:
    env = dict(os.environ)
    env.setdefault("HOME", "/tmp")
    return subprocess.run(["freecadcmd", "-c", code], env=env, check=True, capture_output=True, text=True, timeout=60).stdout


def compute_aw20_oracle() -> dict[str, Any]:
    f_vol = round((320.0 * 220.0 - 240.0 * 150.0 - 4.0 * math.pi * (2.25 ** 2)) * 4.0, 2)
    f_mass = round(f_vol * PC_ABS_G_MM3, 2)
    r_vol = round((320.0 * 220.0 - 60.0 * 28.0 - 4.0 * math.pi * (2.6 ** 2) - 12.0 * math.pi * (5.0 ** 2)) * 3.5, 2)
    r_mass = round(r_vol * MG_AZ91_G_MM3, 2)
    return {
        "dhr_lot": DHR_LOT,
        "bezel_volume_mm3": f_vol,
        "bezel_mass_g": f_mass,
        "rear_volume_mm3": r_vol,
        "rear_mass_g": r_mass,
    }


def _spec_card_b64(title: str, lines: list[str]) -> str:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (880, 300), (15, 23, 42))
    dr = ImageDraw.Draw(im)
    try:
        f_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 21)
        f_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    except Exception:
        f_h = ImageFont.load_default()
        f_b = f_h
    dr.rectangle((14, 14, 866, 286), outline=(56, 189, 248), width=2)
    dr.text((30, 28), title, fill=(125, 211, 252), font=f_h)
    y = 74
    for ln in lines:
        dr.text((30, y), ln, fill=(241, 245, 249), font=f_b)
        y += 34
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _make_xcf800(path: Path, bg: tuple[int, int, int], core: tuple[int, int, int], ov1: tuple[int, int, int], ov2: tuple[int, int, int], n_bg: str, n_c: str, n_1: str, n_2: str) -> None:
    scm = (
        f'(let* ((img (car (gimp-image-new 800 600 RGB))) '
        f'(lb (car (gimp-layer-new img 800 600 RGB-IMAGE "{n_bg}" 100 LAYER-MODE-NORMAL))) '
        f'(lc (car (gimp-layer-new img 400 300 RGBA-IMAGE "{n_c}" 100 LAYER-MODE-NORMAL))) '
        f'(l2 (car (gimp-layer-new img 800 150 RGBA-IMAGE "{n_2}" 100 LAYER-MODE-NORMAL))) '
        f'(l1 (car (gimp-layer-new img 800 150 RGBA-IMAGE "{n_1}" 100 LAYER-MODE-NORMAL)))) '
        f'(gimp-image-insert-layer img lb 0 0) (gimp-context-set-foreground \'({bg[0]} {bg[1]} {bg[2]})) (gimp-drawable-fill lb FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img lc 0 0) (gimp-layer-set-offsets lc 200 150) (gimp-context-set-foreground \'({core[0]} {core[1]} {core[2]})) (gimp-drawable-fill lc FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img l2 0 0) (gimp-layer-set-offsets l2 0 450) (gimp-context-set-foreground \'({ov2[0]} {ov2[1]} {ov2[2]})) (gimp-drawable-fill l2 FILL-FOREGROUND) '
        f'(gimp-image-insert-layer img l1 0 0) (gimp-layer-set-offsets l1 0 0) (gimp-context-set-foreground \'({ov1[0]} {ov1[1]} {ov1[2]})) (gimp-drawable-fill l1 FILL-FOREGROUND) '
        f'(gimp-xcf-save 0 img l1 "{path}" "{path}") (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)


def build(workspace_root: Path, tickets_root: Path) -> None:
    enc = workspace_root / "shared" / "enclosure"
    (enc / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)

    _fc(
        f"""
import FreeCAD, Part
doc = FreeCAD.newDocument("MedMonitor")
fb = doc.addObject("Part::Feature", "FrontBezel")
fb.Shape = Part.makeBox(320.0, 220.0, 4.0)
rv = doc.addObject("Part::Feature", "RearVesaPlate")
rv.Shape = Part.makeBox(320.0, 220.0, 3.5, FreeCAD.Vector(0.0, 0.0, 20.0))
doc.recompute()
doc.saveAs({str(enc / 'monitor_housing.FCStd')!r})
"""
    )
    write_multisheet_xlsx(
        seed / "ISO13485_DHR_Checklist.xlsx",
        [
            (
                "Front_Assy",
                [
                    ["Metric", "Value"],
                    ["FrontBezel_Volume_mm3", 0.0],
                    ["FrontBezel_Mass_g", 0.0],
                    ["Selected_CoverLens_Mass_g", LENS_PMMA_G],
                    ["Front_SubAssy_Total_g", 0.0],
                ],
            ),
            (
                "Rear_Assy",
                [
                    ["Metric", "Value"],
                    ["RearVesa_Volume_mm3", 0.0],
                    ["RearVesa_Mass_g", 0.0],
                    ["Selected_Heatsink_Mass_g", SINK_VAPOR_G],
                    ["Rear_SubAssy_Total_g", 0.0],
                ],
            ),
            (
                "Arm_Counterbalance",
                [
                    ["Component", "Mass_g"],
                    ["Front_SubAssy_Mass_g", 257.0],
                    ["Rear_SubAssy_Mass_g", 569.0],
                    ["Fixed_Electronics_Core_g", FIXED_CORE_G],
                    ["Total_Monitor_Head_Mass_g", ("=ROUND(SUM(B2:B4),2)", 2146.0)],
                ],
            ),
        ],
    )
    write_pdf_manual(
        enc / "specs" / "ISO13485_Enclosure_Spec.pdf",
        "ISO 13485 Bedside Monitor Housing, Graphic Overlay & Arm-Balance Specification",
        [
            (
                "1. FrontBezel & RearVesaPlate 3D Boolean Cutouts (monitor_housing.FCStd)",
                [
                    "FrontBezel base plate is 320 x 220 x 4.0 mm at z=0..4.0. Cut the rectangular active LCD window (240 x 150 mm spanning x=40..280, y=35..185) AND 4 corner M4 clearance through-holes (diameter = 4.5 mm at centers (16,16), (304,16), (16,204), (304,204)).",
                    "RearVesaPlate base plate is 320 x 220 x 3.5 mm at z=20.0..23.5. Cut the 4-hole VESA-100 pattern (diameter = 5.2 mm at (110,60), (210,60), (110,160), (210,160)), the recessed DC/Ethernet port slot (60 x 28 mm spanning x=40..100, y=24..52), AND 12 circular 10.0 mm diameter cooling vents along y = 190 at x = 140 + 14*k for k = 0..11.",
                ],
            ),
            (
                "2. GIMP Multi-Layer Prepress & Coupled ICU Arm Counterbalance",
                [
                    "In GIMP, hide all non-production layers prefixed with FPO_, CROP_, PROOF_, or GRID_ while keeping substrate/mask and legend/UDI layers visible, scale the canvas to the exact pixel dimensions shown on the PLM Portal blueprint card, and export PNG to /srv/studio_project/exports/.",
                    "Read material densities, sub-component mass options, and the mandatory ICU Articulating Arm Counterbalance window for Arm_Counterbalance!B5 from the PLM Portal views.",
                ],
            ),
        ],
    )
    (tickets_root / "front_bezel_overlay_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "rear_vesa_chassis_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "front_bezel_overlay_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "rear_vesa_chassis_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "overview", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    card_front = _spec_card_b64(
        f"FRONT DISPLAY & OVERLAY BLUEPRINT ({DHR_LOT})",
        [
            f"FrontBezel Material: PC-ABS FR | Density = {PC_ABS_G_MM3} g/mm^3",
            "GIMP Target Export Size: 480 x 360 px (display_overlay_prod.png)",
            f"Cover Lens Options: Hardcoat_PMMA = {LENS_PMMA_G} g | Gorilla_Glass = {LENS_GLASS_G} g",
            "ICU Arm Counterbalance Window (Arm_Counterbalance!B5): [2200.0, 2270.0] g",
        ],
    )
    card_rear = _spec_card_b64(
        f"REAR VESA CHASSIS & THERMAL BLUEPRINT ({DHR_LOT})",
        [
            f"RearVesaPlate Material: AZ91D Magnesium | Density = {MG_AZ91_G_MM3} g/mm^3",
            "GIMP Target Export Size: 480 x 360 px (rear_decal_prod.png)",
            f"Heatsink Options: Vapor_Chamber = {SINK_VAPOR_G} g | Extruded_Al = {SINK_EXTRU_G} g",
            "ICU Arm Counterbalance Window (Arm_Counterbalance!B5): [2200.0, 2270.0] g",
        ],
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw20_sess" in ck) and (ck["aw20_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw20_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 ISO 13485 PLM Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["overview"])[0]
                with lock:
                    if t in ("overview", "front", "rear") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "overview":
                body = (
                    f"<h2>ISO 13485 DHR Release Control</h2>"
                    f"<p>Active Production Lot (`dhr_lot`): <code>{DHR_LOT}</code></p>"
                    f"<p>ICU Articulating Arm Counterbalance Window (`Arm_Counterbalance!B5`): <code>[2200.0, 2270.0] g</code></p>"
                    f"<p>Select the Front or Rear Engineering Blueprint tab above to inspect material densities, optical/thermal component masses, and GIMP overlay raster dimensions.</p>"
                )
            elif cur == "front":
                body = f"<h2>Front Display &amp; Optical Blueprint (<code>{DHR_LOT}</code>)</h2><img src='data:image/png;base64,{card_front}' alt='Front Spec Blueprint'/>"
            else:
                body = f"<h2>Rear VESA &amp; Thermal Blueprint (<code>{DHR_LOT}</code>)</h2><img src='data:image/png;base64,{card_rear}' alt='Rear Spec Blueprint'/>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>ISO 13485 PLM &amp; DHR Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>ISO 13485 PLM &amp; DHR Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=overview">Overview</a><a href="/tab?id=front">Front Display &amp; Optical Spec</a><a href="/tab?id=rear">Rear VESA &amp; Thermal Spec</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1140, 760))
    seed = workspace_root / "_desk_seed"
    enc = workspace_root / "shared" / "enclosure"
    priv = Path("/opt/aw20_masters")
    priv.mkdir(parents=True, exist_ok=True)
    xa = priv / "display_overlay_raw.xcf"
    xb = priv / "rear_decal_raw.xcf"
    _make_xcf800(xa, (20, 24, 30), (16, 185, 129), (255, 0, 170), (250, 204, 21), "Matte_Black_Mask", "ECG_Legend_Green", "FPO_MAGENTA_BAR", "CROP_GUIDES_YELLOW")
    _make_xcf800(xb, (210, 218, 226), (29, 78, 216), (239, 68, 68), (249, 115, 22), "Silver_Foil_Bg", "UDI_Panel_Blue", "PROOF_RED_STAMP", "GRID_ORANGE_LINES")
    subprocess.run(
        [
            "bash",
            "-lc",
            f"id -u studio_ui >/dev/null 2>&1 || useradd -m -s /bin/bash studio_ui; "
            f"mkdir -p /srv/studio_project/exports && cp '{seed / 'ISO13485_DHR_Checklist.xlsx'}' /srv/studio_project/ISO13485_DHR_Checklist.xlsx && "
            f"chown -R studio_ui:studio_ui /opt/aw20_masters /srv/studio_project && chmod 700 /opt/aw20_masters /srv/studio_project",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )

    g_args = []
    if "front_bezel_overlay_eng" in roles:
        g_args.append(f"'{xa}'")
    if "rear_vesa_chassis_eng" in roles:
        g_args.append(f"'{xb}'")
    if g_args:
        launch_studio_app(f"nohup gimp --no-splash {' '.join(g_args)} >/tmp/aw20_gimp.log 2>&1 </dev/null &", wait_s=3.4)
    launch_studio_app(f"nohup freecad '{enc / 'monitor_housing.FCStd'}' >/tmp/aw20_fc.log 2>&1 </dev/null &", wait_s=3.5)
    launch_studio_app("nohup libreoffice --norestore --nologo --nofirststartwizard '/srv/studio_project/ISO13485_DHR_Checklist.xlsx' >/tmp/aw20_calc.log 2>&1 </dev/null &", wait_s=2.5)


def _scale_export(xcf_p: Path, out_p: Path) -> None:
    out_p.parent.mkdir(parents=True, exist_ok=True)
    scm = (
        f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_p}" "{xcf_p}"))) (ly (cadr (gimp-image-get-layers img)))) '
        '(gimp-item-set-visible (aref ly 0) FALSE) (gimp-item-set-visible (aref ly 1) FALSE) '
        '(gimp-image-scale img 480 360) '
        '(let ((m (car (gimp-image-merge-visible-layers img CLIP-TO-IMAGE)))) '
        f'(file-png-save-defaults RUN-NONINTERACTIVE img m "{out_p}" "{out_p}")) (gimp-quit 0))'
    )
    subprocess.run(["gimp", "-i", "-b", scm], check=True, capture_output=True, timeout=35)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    enc = workspace_root / "shared" / "enclosure"
    fc_p = enc / "monitor_housing.FCStd"
    xlsx_p = Path("/srv/studio_project/ISO13485_DHR_Checklist.xlsx")
    exp_d = Path("/srv/studio_project/exports")
    ora = compute_aw20_oracle()

    if role == "front_bezel_overlay_eng":
        _scale_export(Path("/opt/aw20_masters/display_overlay_raw.xcf"), exp_d / "display_overlay_prod.png")
        code_a = f"""
import FreeCAD, Part
doc = FreeCAD.openDocument({str(fc_p)!r}) if {cooperative!r} else FreeCAD.newDocument("MedMonitor")
if not {cooperative!r}:
    rv = doc.addObject("Part::Feature", "RearVesaPlate"); rv.Shape = Part.makeBox(320.0, 220.0, 3.5, FreeCAD.Vector(0,0,20))
    fb = doc.addObject("Part::Feature", "FrontBezel")
else:
    fb = doc.getObject("FrontBezel")
base = Part.makeBox(320.0, 220.0, 4.0)
cuts = [Part.makeBox(240.0, 150.0, 8.0, FreeCAD.Vector(40.0, 35.0, -2.0))]
for cx, cy in ((16,16),(304,16),(16,204),(304,204)):
    cuts.append(Part.makeCylinder(2.25, 8.0, FreeCAD.Vector(cx, cy, -2.0)))
fb.Shape = base.cut(Part.makeCompound(cuts))
doc.recompute()
Part.export([fb], {str(enc / 'FrontBezel.step')!r})
doc.saveAs({str(fc_p)!r})
"""
        if cooperative:
            with resource_lock("aw20_all"):
                _fc(code_a)
                bk = evaluate_xlsx_isolated(xlsx_p)
                b3_rear = cell_float(bk, "Arm_Counterbalance", "B3") or 569.0
                lens_sel = LENS_PMMA_G if b3_rear > 610.0 else LENS_GLASS_G
                f_sub = round(ora["bezel_mass_g"] + lens_sel, 2)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Front_Assy",
                    [
                        ["Metric", "Value"],
                        ["FrontBezel_Volume_mm3", ora["bezel_volume_mm3"]],
                        ["FrontBezel_Mass_g", ora["bezel_mass_g"]],
                        ["Selected_CoverLens_Mass_g", lens_sel],
                        ["Front_SubAssy_Total_g", ("=SUM(B3:B4)", f_sub)],
                    ],
                )
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Arm_Counterbalance",
                    [
                        ["Component", "Mass_g"],
                        ["Front_SubAssy_Mass_g", f_sub],
                        ["Rear_SubAssy_Mass_g", b3_rear],
                        ["Fixed_Electronics_Core_g", FIXED_CORE_G],
                        ["Total_Monitor_Head_Mass_g", ("=ROUND(SUM(B2:B4),2)", round(f_sub + b3_rear + FIXED_CORE_G, 2))],
                    ],
                )
        else:
            lens_sel = LENS_GLASS_G
            f_sub = round(ora["bezel_mass_g"] + lens_sel, 2)
            _fc(code_a)
            write_multisheet_xlsx(xlsx_p, [("Front_Assy", [["Metric", "Value"], ["FrontBezel_Mass_g", ora["bezel_mass_g"]]])])
        write_json(
            enc / "front_bezel_dhr.json",
            {
                "dhr_lot": DHR_LOT,
                "bezel_volume_mm3": ora["bezel_volume_mm3"],
                "bezel_mass_g": ora["bezel_mass_g"],
                "selected_lens_mass_g": lens_sel,
                "front_subassy_mass_g": f_sub,
            },
        )
    elif role == "rear_vesa_chassis_eng":
        _scale_export(Path("/opt/aw20_masters/rear_decal_raw.xcf"), exp_d / "rear_decal_prod.png")
        code_b = f"""
import FreeCAD, Part
doc = FreeCAD.openDocument({str(fc_p)!r}) if {cooperative!r} else FreeCAD.newDocument("MedMonitor")
if not {cooperative!r}:
    fb = doc.addObject("Part::Feature", "FrontBezel"); fb.Shape = Part.makeBox(320.0, 220.0, 4.0)
    rv = doc.addObject("Part::Feature", "RearVesaPlate")
else:
    rv = doc.getObject("RearVesaPlate")
base = Part.makeBox(320.0, 220.0, 3.5, FreeCAD.Vector(0.0, 0.0, 20.0))
cuts = [Part.makeBox(60.0, 28.0, 8.0, FreeCAD.Vector(40.0, 24.0, 18.0))]
for vx, vy in ((110,60),(210,60),(110,160),(210,160)):
    cuts.append(Part.makeCylinder(2.6, 8.0, FreeCAD.Vector(vx, vy, 18.0)))
for k in range(12):
    cuts.append(Part.makeCylinder(5.0, 8.0, FreeCAD.Vector(140.0 + 14.0*k, 190.0, 18.0)))
rv.Shape = base.cut(Part.makeCompound(cuts))
doc.recompute()
Part.export([rv], {str(enc / 'RearVesaPlate.step')!r})
doc.saveAs({str(fc_p)!r})
"""
        if cooperative:
            with resource_lock("aw20_all"):
                _fc(code_b)
                bk = evaluate_xlsx_isolated(xlsx_p)
                b2_front = cell_float(bk, "Arm_Counterbalance", "B2") or 257.0
                sink_sel = SINK_VAPOR_G if b2_front > 300.0 else SINK_EXTRU_G
                r_sub = round(ora["rear_mass_g"] + sink_sel, 2)
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Rear_Assy",
                    [
                        ["Metric", "Value"],
                        ["RearVesa_Volume_mm3", ora["rear_volume_mm3"]],
                        ["RearVesa_Mass_g", ora["rear_mass_g"]],
                        ["Selected_Heatsink_Mass_g", sink_sel],
                        ["Rear_SubAssy_Total_g", ("=SUM(B3:B4)", r_sub)],
                    ],
                )
                update_single_sheet_xlsx(
                    xlsx_p,
                    "Arm_Counterbalance",
                    [
                        ["Component", "Mass_g"],
                        ["Front_SubAssy_Mass_g", b2_front],
                        ["Rear_SubAssy_Mass_g", r_sub],
                        ["Fixed_Electronics_Core_g", FIXED_CORE_G],
                        ["Total_Monitor_Head_Mass_g", ("=ROUND(SUM(B2:B4),2)", round(b2_front + r_sub + FIXED_CORE_G, 2))],
                    ],
                )
        else:
            sink_sel = SINK_EXTRU_G
            r_sub = round(ora["rear_mass_g"] + sink_sel, 2)
            _fc(code_b)
            write_multisheet_xlsx(xlsx_p, [("Rear_Assy", [["Metric", "Value"], ["RearVesa_Mass_g", ora["rear_mass_g"]]])])
        write_json(
            enc / "rear_vesa_dhr.json",
            {
                "dhr_lot": DHR_LOT,
                "rear_volume_mm3": ora["rear_volume_mm3"],
                "rear_mass_g": ora["rear_mass_g"],
                "selected_heatsink_mass_g": sink_sel,
                "rear_subassy_mass_g": r_sub,
            },
        )


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("front_bezel_overlay_eng", workspace_root, cooperative=False)
    solve_role("rear_vesa_chassis_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "front_bezel_overlay_eng", workspace_root, True)
        fb = pool.submit(solve_role, "rear_vesa_chassis_eng", workspace_root, True)
        fa.result()
        fb.result()


def _chk_png480(p: Path, bg: tuple[int, int, int], core: tuple[int, int, int]) -> tuple[bool, bool]:
    from PIL import Image

    if not p.is_file():
        return False, False
    try:
        im = Image.open(p).convert("RGB")
        sz = im.size == (480, 360)
        w, h = im.size
        pt, pb, pm = im.getpixel((w // 2, int(h * 0.08))), im.getpixel((w // 2, int(h * 0.92))), im.getpixel((w // 2, h // 2))
        ly = all(abs(int(pt[i]) - bg[i]) <= 26 for i in range(3)) and all(abs(int(pb[i]) - bg[i]) <= 26 for i in range(3)) and all(abs(int(pm[i]) - core[i]) <= 26 for i in range(3))
        return sz, ly
    except Exception:
        return False, False


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    import json as _j

    enc = workspace_root / "shared" / "enclosure"
    exp_d = Path("/srv/studio_project/exports")
    xlsx_p = Path("/srv/studio_project/ISO13485_DHR_Checklist.xlsx")
    ora = compute_aw20_oracle()
    ja = read_json_safe(enc / "front_bezel_dhr.json")
    jb = read_json_safe(enc / "rear_vesa_dhr.json")
    book = evaluate_xlsx_isolated(xlsx_p)
    f_book = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}

    cad = {}
    try:
        out = _fc(
            f"""
import json, os, FreeCAD, Part
d = {{}}
if os.path.isfile({str(enc / 'monitor_housing.FCStd')!r}):
    doc = FreeCAD.openDocument({str(enc / 'monitor_housing.FCStd')!r})
    if doc.getObject("FrontBezel"): d["fc_f"] = round(doc.getObject("FrontBezel").Shape.Volume, 2)
    if doc.getObject("RearVesaPlate"): d["fc_r"] = round(doc.getObject("RearVesaPlate").Shape.Volume, 2)
if os.path.isfile({str(enc / 'FrontBezel.step')!r}): d["st_f"] = round(Part.read({str(enc / 'FrontBezel.step')!r}).Volume, 2)
if os.path.isfile({str(enc / 'RearVesaPlate.step')!r}): d["st_r"] = round(Part.read({str(enc / 'RearVesaPlate.step')!r}).Volume, 2)
print("AW20_CAD:" + json.dumps(d))
"""
        )
        for ln in out.splitlines():
            if ln.startswith("AW20_CAD:"):
                cad = _j.loads(ln.split("AW20_CAD:", 1)[1])
    except Exception:
        pass

    sz_a, ly_a = _chk_png480(exp_d / "display_overlay_prod.png", (20, 24, 30), (16, 185, 129))
    sz_b, ly_b = _chk_png480(exp_d / "rear_decal_prod.png", (210, 218, 226), (29, 78, 216))

    def _close(v: Any, exp: float, tol: float = 350.0) -> bool:
        return isinstance(v, (int, float)) and abs(float(v) - exp) <= tol

    head_mass = cell_float(book, "Arm_Counterbalance", "B5")
    arm_ok = (head_mass is not None) and (2200.0 <= float(head_mass) <= 2270.0)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_cad_step", _close(cad.get("st_f"), ora["bezel_volume_mm3"], 450.0) and _close(cad.get("fc_f"), ora["bezel_volume_mm3"], 450.0), 2.0, f"FrontBezel CAD volume mismatch ({cad.get('fc_f')})"),
        ("a_json", ja.get("dhr_lot") == DHR_LOT and _close(ja.get("bezel_mass_g"), ora["bezel_mass_g"], 1.2), 1.4, "front_bezel_dhr.json mismatch"),
        ("a_gimp_ly", ly_a, 2.2, "display_overlay_prod.png missing or still has magenta/yellow FPO layers"),
        ("a_gimp_sz", sz_a, 2.0, "display_overlay_prod.png not scaled to 480x360 in GIMP"),
        ("a_calc_sum", "SUM" in cell_formula(f_book, "Front_Assy", "B5").upper() and _close(cell_float(book, "Front_Assy", "B3"), ora["bezel_mass_g"], 1.5), 1.4, "Live Calc Front_Assy!B3/B5 missing"),
        ("a_arm_bal", arm_ok, 1.8, f"Live Calc Arm_Counterbalance!B5 ({head_mass}) outside [2200.0, 2270.0] g"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_cad_step", _close(cad.get("st_r"), ora["rear_volume_mm3"], 450.0) and _close(cad.get("fc_r"), ora["rear_volume_mm3"], 450.0), 2.0, f"RearVesaPlate CAD volume mismatch ({cad.get('fc_r')})"),
        ("b_json", jb.get("dhr_lot") == DHR_LOT and _close(jb.get("rear_mass_g"), ora["rear_mass_g"], 1.5), 1.4, "rear_vesa_dhr.json mismatch"),
        ("b_gimp_ly", ly_b, 2.2, "rear_decal_prod.png missing or still has red/orange layers"),
        ("b_gimp_sz", sz_b, 2.0, "rear_decal_prod.png not scaled to 480x360 in GIMP"),
        ("b_calc_sum", "SUM" in cell_formula(f_book, "Rear_Assy", "B5").upper() and _close(cell_float(book, "Rear_Assy", "B3"), ora["rear_mass_g"], 1.8), 1.4, "Live Calc Rear_Assy!B3/B5 missing"),
        ("b_arm_bal", arm_ok, 1.8, f"Live Calc Arm_Counterbalance!B5 ({head_mass}) outside [2200.0, 2270.0] g"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_fcstd_gimp_and_coupled_arm_balance",
            _close(cad.get("fc_f"), ora["bezel_volume_mm3"], 450.0)
            and _close(cad.get("fc_r"), ora["rear_volume_mm3"], 450.0)
            and sz_a and ly_a and sz_b and ly_b
            and arm_ok,
            2.5,
            f"Shared monitor_housing.FCStd, GIMP tabs, or Arm_Counterbalance!B5 ({head_mass}) collided",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"front_bezel_overlay_eng": TICKET_A, "rear_vesa_chassis_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
