"""EC2-C08: 1U Enclosure Monolithic FreeCAD .FCStd/.step, Inkscape Prepress, HttpOnly PLM & Open Calc.

Track 2 — Monolithic CAD Assembly, Unit-System Session Toggle, Clipboard & Open Calc Preload (Full GUI + CLI).
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    reload_open_libreoffice_docs,
    render_scanned_document_png,
    set_x11_clipboard,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "EC2-C08"
PORTAL_PORT = 19108
DESK_TAG = "DESK-ECN-REVC-308"
THERMAL_ECN_SEAL = make_opaque_seal("ec2_c08", "THERMAL_CFD:IEC_60297_METRIC_MM")
EMC_ECN_SEAL = make_opaque_seal("ec2_c08", "EMC_BULKHEAD:NEMA_IMPERIAL_MIL")

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "1U Sheet-Metal Enclosure FreeCAD B-Rep, Inkscape Prepress & Thermal/EMC Preload Coupling",
    "domain": "Mechanical CAD, EMC Shielding & Industrial Artwork Prepress",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "monolithic_fcstd_zip_and_step_lost_update",
        "libreoffice_calc_dirty_buffer_split_brain",
        "shared_httponly_plm_unit_toggle_and_clipboard",
        "bidirectional_fastener_preload_gasket_envelope",
    ),
    "roles": ("mech_thermal_eng", "emi_prepress_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/enclosure_revC/Thermal_EMI_BOM.xlsx", DESK_TAG, "calc"),
    ),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

RHO_AL6061_G_MM3 = 0.00270
VENT_AREA_RANGE_MM2 = (3758.0, 4600.0)
TRUE_IO_AREA_MM2 = 1650.0
TOP_TORQUE_RANGE_NCM = (108.0, 154.0)
REAR_PRELOAD_RANGE_NCM = (92.0, 138.0)
COMBINED_PRELOAD_BAND_NCM = (244.0, 252.0)

PLM_LIBRARY_MM: list[tuple[str, str, float, float]] = [
    ("THM-SLOT-STD", "Standard Top-Lid Convection Louver Slot", 36.0, 5.6),
    ("OPT-QSFP28", "QSFP28 Optical Transceiver Cage", 19.0, 10.0),
    ("ETH-RJ45-DUAL", "Dual-Stack Shielded RJ45 Block", 32.0, 15.0),
    ("USB-TYPEC-IND", "Industrial Retaining USB-C", 11.0, 6.5),
    ("DB9-RS232", "D-Sub 9-Pin Serial Console", 25.0, 12.5),
    ("SMA-GNSS-BLK", "Bulkhead GNSS Coax Port", 8.0, 8.0),
    ("OPT-QSFP-DD", "QSFP-DD 400G Cage", 21.5, 11.0),
    ("ETH-RJ45-QUAD", "Quad-Port RJ45 Gang", 60.0, 15.0),
    ("FAN-40MM-GRD", "40mm Fan Finger Guard", 38.0, 38.0),
    ("MGT-SFP-PLUS", "10G Management SFP+ Cage", 15.0, 10.0),
    ("BNC-10MHZ-SYNC", "10MHz Timing Reference Port", 12.0, 12.0),
    ("LED-LIGHTPIPE-4", "Quad Status Lightpipe Array", 14.0, 4.0),
    ("PWR-DC48V", "Telecom -48VDC Terminal Block", 16.0, 10.0),
    ("PWR-AC-C14", "IEC C14 AC Inlet", 28.0, 20.5),
]

FREECAD_SCRIPT = r"""
import json, os, sys
from pathlib import Path
for p in ("/usr/lib/freecad-python3/lib", "/usr/lib/freecad/lib"):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.append(p)
import FreeCAD, Part

fcstd_p = Path(sys.argv[1])
mode = sys.argv[2]
step_p = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None

if mode == "init":
    doc = FreeCAD.newDocument("EnclosureRevC")
    lid = doc.addObject("Part::Feature", "TopVentCover")
    lid.Shape = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
    rear = doc.addObject("Part::Feature", "RearIOBulkhead")
    rear.Shape = Part.makeBox(220.0, 3.0, 41.5, FreeCAD.Vector(0.0, 157.0, 0.0))
    doc.recompute()
    doc.saveAs(str(fcstd_p))
    if step_p:
        Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True)
    os._exit(0)

doc = FreeCAD.openDocument(str(fcstd_p))
lid = doc.getObject("TopVentCover")
rear = doc.getObject("RearIOBulkhead")

if mode == "vent":
    base = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
    cuts = [Part.makeBox(36.0, 5.6, 4.0, FreeCAD.Vector(x0, 20.0 + r * 25.0, 41.0)) for x0 in (18.0, 60.0, 124.0, 166.0) for r in range(5)]
    lid.Shape = base.cut(Part.makeCompound(cuts))
    doc.recompute(); doc.save()
    if step_p: Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True); os._exit(0)
elif mode == "io":
    base = Part.makeBox(220.0, 3.0, 41.5, FreeCAD.Vector(0.0, 157.0, 0.0))
    cuts = [
        Part.makeBox(19.0, 5.0, 10.0, FreeCAD.Vector(14.0, 156.0, 14.0)),
        Part.makeBox(19.0, 5.0, 10.0, FreeCAD.Vector(40.0, 156.0, 14.0)),
        Part.makeBox(32.0, 5.0, 15.0, FreeCAD.Vector(68.0, 156.0, 12.0)),
        Part.makeBox(32.0, 5.0, 15.0, FreeCAD.Vector(108.0, 156.0, 12.0)),
        Part.makeBox(15.0, 5.0, 10.0, FreeCAD.Vector(148.0, 156.0, 14.0)),
        Part.makeBox(16.0, 5.0, 10.0, FreeCAD.Vector(172.0, 156.0, 14.0)),
    ]
    rear.Shape = base.cut(Part.makeCompound(cuts))
    doc.recompute(); doc.save()
    if step_p: Part.export([lid, rear], str(step_p))
    print("CAD_JSON:" + json.dumps({"ok": True}), flush=True); os._exit(0)
elif mode == "inspect":
    lid_vol = float(lid.Shape.Volume) if lid else -1.0
    rear_vol = float(rear.Shape.Volume) if rear else -1.0
    kv = 0.0
    if lid:
        full_lid = Part.makeBox(220.0, 160.0, 2.5, FreeCAD.Vector(0.0, 0.0, 41.5))
        rem = full_lid.cut(lid.Shape)
        perim = full_lid.cut(Part.makeBox(196.0, 136.0, 2.5, FreeCAD.Vector(12.0, 12.0, 41.5)))
        boss = Part.makeBox(16.0, 160.0, 2.5, FreeCAD.Vector(102.0, 0.0, 41.5))
        kv = float(rem.common(perim).Volume) + float(rem.common(boss).Volume)
    step_ok = False
    if step_p and step_p.is_file():
        s_sh = Part.read(str(step_p))
        step_ok = abs(float(s_sh.Volume) - (lid_vol + rear_vol)) < 25.0 and len(s_sh.Solids) >= 2
    print("CAD_JSON:" + json.dumps({
        "ok": bool(lid and rear and lid.Shape.isValid() and rear.Shape.isValid()),
        "vent_area_mm2": round((88000.0 - lid_vol) / 2.5, 2),
        "io_area_mm2": round((27390.0 - rear_vol) / 3.0, 2),
        "lid_mass_g": round(lid_vol * 0.00270, 2),
        "rear_mass_g": round(rear_vol * 0.00270, 2),
        "keepout_viol_mm3": round(kv, 3),
        "step_synced": step_ok,
    }), flush=True)
    os._exit(0)
"""


def _run_freecad(fcstd_p: Path, mode: str, step_p: Path | None = None) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tf:
        tf.write(FREECAD_SCRIPT)
        sp = tf.name
    try:
        cp = subprocess.run([sys.executable, sp, str(fcstd_p), mode, str(step_p or "")], capture_output=True, text=True, timeout=90)
        for ln in cp.stdout.splitlines():
            if ln.startswith("CAD_JSON:"):
                return json.loads(ln[len("CAD_JSON:"):])
        return {"ok": False}
    finally:
        try: os.unlink(sp)
        except OSError: pass


def _make_vent_sheet(lid_mass_g: float, vent_area_mm2: float, desk_tag: str = "", ecn_seal: str = "PENDING") -> list[list]:
    return [
        ["Metric", "Value", desk_tag],
        ["TopVentCover_Mass_g", round(lid_mass_g, 2), "AL6061_RHO"],
        ["Vent_Cutout_Area_mm2", round(vent_area_mm2, 2), "THERMAL_CUTOUT"],
        ["Natural_Convection_Capacity_W", ("=0.0165*B3", round(0.0165 * vent_area_mm2, 2)), "IEC_CONVECTION"],
        ["PLM_Thermal_ECN_Seal", ecn_seal, "CLIPBOARD_ATTEST"],
    ]


def _make_emi_sheet(rear_mass_g: float, io_area_mm2: float, ecn_seal: str = "PENDING") -> list[list]:
    return [
        ["Metric", "Value", "Spec"],
        ["RearIOBulkhead_Mass_g", round(rear_mass_g, 2), "AL6061_RHO"],
        ["Rear_IO_Cutout_Area_mm2", round(io_area_mm2, 2), "BULKHEAD_6PORT"],
        ["EMC_6GHz_Attenuation_Margin_dB", ("=78.0-0.008*B3", round(78.0 - 0.008 * io_area_mm2, 2)), "WAVEGUIDE_MARGIN"],
        ["PLM_EMC_ECN_Seal", ecn_seal, "CLIPBOARD_ATTEST"],
    ]


def _make_joint_sheet(top_tq: float, rear_pl: float) -> list[list]:
    return [
        ["Parameter", "Torque_Or_Preload_Ncm", "Compliance_Ref"],
        ["Top_Cover_Torque_Spec_Ncm", round(top_tq, 2), "TOP_FLANGE"],
        ["Rear_Gasket_Preload_Ncm", round(rear_pl, 2), "BECU_GASKET"],
        ["Combined_Fastener_Preload_Ncm", ("=B2+B3", round(top_tq + rear_pl, 2)), "FRAME_FLATNESS"],
    ]


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    mech_md = "\n".join([
        f"# Mechanical & Thermal Engineering Work Order — {b}mech_thermal_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Rev-C top ventilation lid machining and thermal schedule in {b}/workspace/enclosure_revC{b}.",
        f"{b}Thermal_EMI_BOM.xlsx{b} is open in LibreOffice Calc (with ECN control tag in {b}Thermal_Vent_Schedule!C1{b}) alongside the Hardware PLM Portal at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/enclosure_revC/Engineering_Standard_IEC.md{b}, {b}scans/top_lid_keepout_revC.png{b}, and {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        f"2. Machine ventilation through-cutouts on solid {b}TopVentCover{b} in {b}chassis_housing.FCStd{b} meeting thermal dissipation ({b}>= 62.0 W{b}), area ({b}<= 4600 mm^2{b}), and outer/spine keepouts while preserving all other solids, and export {b}release/chassis_housing.step{b}.",
        f"3. In PLM ({b}DISCIPLINE = THERMAL_CFD{b}, {b}UNIT_SYSTEM = IEC_60297_METRIC_MM{b}), copy the Thermal ECN Seal to the clipboard for {b}Thermal_Vent_Schedule!B5{b}; populate {b}Thermal_Vent_Schedule!B2:B4{b} and size only {b}Joint_Compliance!B2{b} so {b}Joint_Compliance!B4{b} lands in {b}[244.0, 252.0] Ncm{b}, preserving {b}Thermal_Vent_Schedule!C1{b}.",
        "",
    ])
    emi_md = "\n".join([
        f"# EMC Shielding & Silkscreen Prepress Work Order — {b}emi_prepress_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the Rev-C rear I/O bulkhead machining, gasket preload, and front-bezel silkscreen artwork in {b}/workspace/enclosure_revC{b}.",
        f"{b}Thermal_EMI_BOM.xlsx{b} is open in LibreOffice Calc (with ECN control tag in {b}Thermal_Vent_Schedule!C1{b}) alongside {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Review {b}/workspace/enclosure_revC/Engineering_Standard_IEC.md{b}, {b}scans/rear_io_callout.png{b}, and the full 14-item PLM cutout CSV ({b}/home/user/Downloads/iec_enclosure_spec.csv{b}).",
        f"2. Machine all 6 rear bulkhead through-cutouts on {b}RearIOBulkhead{b} in {b}chassis_housing.FCStd{b} preserving all other solids, and export {b}release/chassis_housing.step{b}.",
        f"3. Update {b}front_bezel_silkscreen.svg{b} with all three required {b}<g>{b} IDs in {b}scans/rear_io_callout.png{b} and render {b}release/front_bezel_proof.png{b} ({b}1760 x 360{b}) via Inkscape.",
        f"4. Per Telcordia EMC sign-off governance, set PLM to {b}DISCIPLINE = EMC_BULKHEAD{b} and {b}UNIT_SYSTEM = NEMA_IMPERIAL_MIL{b}, copy the EMC ECN Seal to {b}EMI_Shielding_Schedule!B5{b}, populate {b}EMI_Shielding_Schedule!B2:B4{b} (metric mass/area), and size only {b}Joint_Compliance!B3{b} so {b}Joint_Compliance!B4{b} lands in {b}[244.0, 252.0] Ncm{b}, preserving {b}Thermal_Vent_Schedule!C1{b}.",
        "",
    ])
    return {"mech_thermal_eng": mech_md, "emi_prepress_eng": emi_md}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    b = chr(96)
    ws = next(iter(workspace_map.values()))
    enc = ws / "enclosure_revC"
    (enc / "release").mkdir(parents=True, exist_ok=True)
    (enc / "scans").mkdir(parents=True, exist_ok=True)
    _run_freecad(enc / "chassis_housing.FCStd", "init", enc / "release" / "chassis_housing.step")

    (enc / "Engineering_Standard_IEC.md").write_text(
        "\n".join([
            "# IEC 60297-3-101 Rev-C — 1U Enclosure Mechanical, Thermal & EMC Standard",
            f"1. Alloy Al-6061-T6 ({b}rho = 0.00270 g/mm^3{b}). All CAD/workbook geometry is metric ({b}mm, mm^2, g{b}); note {b}1000 mil = 25.4 mm{b}.",
            f"2. PLM Seal Governance: Thermal seals require {b}THERMAL_CFD + IEC_60297_METRIC_MM{b}; EMC seals require {b}EMC_BULKHEAD + NEMA_IMPERIAL_MIL{b}.",
            f"3. TopVentCover ({b}220x160x2.5 mm, Z=41.5..44.0{b}): {b}Q_conv_W = 0.0165 * Vent_Cutout_Area_mm2 >= 62.0 W{b} ({b}area in [3758, 4600] mm^2{b}), formula {b}=0.0165*B3{b} in {b}Thermal_Vent_Schedule!B4{b}.",
            f"4. RearIOBulkhead ({b}220x3.0x41.5 mm, Y=157..160{b}): machine 6 ports per {b}scans/rear_io_callout.png{b}; formula {b}=78.0-0.008*B3{b} in {b}EMI_Shielding_Schedule!B4{b}.",
            f"5. Preload Window ({b}Joint_Compliance{b}): {b}B2 in [108.0, 154.0] Ncm{b}, {b}B3 in [92.0, 138.0] Ncm{b}, {b}B4 = =B2+B3 in [244.0, 252.0] Ncm{b}.",
        ]),
        encoding="utf-8",
    )
    render_scanned_document_png(
        enc / "scans" / "top_lid_keepout_revC.png",
        "DRAWING REV-C1: TOP VENT COVER GASKET & HEATSINK BOSS KEEPOUTS",
        [
            "Solid: TopVentCover (X: 0..220 mm, Y: 0..160 mm, Z: 41.5..44.0 mm)",
            "1. Outer EMI Gasket Perimeter: 12.0 mm no-cut margin on all 4 edges",
            "   (No cutouts where X < 12, X > 208, Y < 12, or Y > 148 mm)",
            "2. Central Heatsink Standoff Spine: No cutouts in X = 102.0..118.0 mm",
        ],
    )
    render_scanned_document_png(
        enc / "scans" / "rear_io_callout.png",
        "DRAWING REV-C2: REAR BULKHEAD 6-PORT SCHEDULE & BEZEL ARTWORK",
        [
            "RearIOBulkhead (Y = 157..160 mm) — Machine 6 Non-Overlapping Ports:",
            "  - Qty 2 x OPT-QSFP28    |  Qty 2 x ETH-RJ45-DUAL",
            "  - Qty 1 x MGT-SFP-PLUS  |  Qty 1 x PWR-DC48V",
            "Front Bezel SVG Prepress (880x180 -> export 1760x360 PNG):",
            "  Include <g> IDs: iec-emc-class-a-badge, port-legend-qsfp, thermal-airflow-notice",
        ],
    )
    (enc / "front_bezel_silkscreen.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="180" viewBox="0 0 880 180">\n'
        '  <rect width="880" height="180" fill="#1e293b"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )
    write_multisheet_xlsx(
        enc / "Thermal_EMI_BOM.xlsx",
        [
            ("Thermal_Vent_Schedule", _make_vent_sheet(88000.0 * RHO_AL6061_G_MM3, 0.0, desk_tag="", ecn_seal="PENDING")),
            ("EMI_Shielding_Schedule", _make_emi_sheet(27390.0 * RHO_AL6061_G_MM3, 0.0, ecn_seal="PENDING")),
            ("Joint_Compliance", _make_joint_sheet(148.0, 134.0)),
        ],
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_plm_html(unit_mode: str, discipline: str) -> str:
    mult = (1000.0 / 25.4) if unit_mode == "NEMA_IMPERIAL_MIL" else 1.0
    rows = "".join(f"<tr><td>{c}</td><td>{d}</td><td>{w*mult:.2f}</td><td>{h*mult:.2f}</td></tr>" for c, d, w, h in PLM_LIBRARY_MM[:4])
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Atlas PLM</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{background:#e2e8f0;padding:10px 18px;display:flex;gap:8px;flex-wrap:wrap;}}button{{padding:6px 10px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px;}}th,td{{border:1px solid #cbd5e1;padding:7px 10px;}}</style></head>
<body>
<header><strong>Atlas Hardware PLM</strong><span style="font-family:monospace;">DISCIPLINE={discipline} | UNIT={unit_mode}</span></header>
<div class="bar">
  <button onclick="setP({{discipline:'THERMAL_CFD'}})">THERMAL_CFD</button>
  <button onclick="setP({{discipline:'EMC_BULKHEAD'}})">EMC_BULKHEAD</button>
  <button onclick="setP({{unit_mode:'IEC_60297_METRIC_MM'}})">IEC_60297_METRIC_MM</button>
  <button onclick="setP({{unit_mode:'NEMA_IMPERIAL_MIL'}})">NEMA_IMPERIAL_MIL</button>
  <button onclick="expP()">Export Full 14-Item Spec CSV (/home/user/Downloads/iec_enclosure_spec.csv)</button>
  <button onclick="cpE()">Copy ECN Sign-Off Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<main style="padding:14px 18px;">
  <table><thead><tr><th>PLM Code</th><th>Description</th><th>Width</th><th>Height</th></tr></thead><tbody>{rows}</tbody></table>
</main>
<script>
async function setP(p){{await fetch('/api/plm/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(p)}});location.reload();}}
async function expP(){{const r=await fetch('/api/plm/export_csv',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Saved ['+d.unit_mode+']';}}
async function cpE(){{const r=await fetch('/api/plm/copy_seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied ['+d.discipline+'/'+d.unit_mode+']';}}
</script></body></html>"""


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "discipline": "THERMAL_CFD",
        "unit_mode": "NEMA_IMPERIAL_MIL",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec2_c08_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True})
                return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302)
                self.send_header("Set-Cookie", f"ec2_c08_sso={sso_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"})
                return
            with lock:
                raw = _render_plm_html(pstate["unit_mode"], pstate["discipline"]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if self.path == "/api/plm/state":
                with lock:
                    changed = False
                    if body.get("discipline") in ("THERMAL_CFD", "EMC_BULKHEAD") and pstate["discipline"] != body["discipline"]:
                        pstate["discipline"] = body["discipline"]; changed = True
                    if body.get("unit_mode") in ("IEC_60297_METRIC_MM", "NEMA_IMPERIAL_MIL") and pstate["unit_mode"] != body["unit_mode"]:
                        pstate["unit_mode"] = body["unit_mode"]; changed = True
                    if changed:
                        pstate["session_switches"] += 1
                        write_json(state_p, pstate)
                    self._send_json(200, {"ok": True, "discipline": pstate["discipline"], "unit_mode": pstate["unit_mode"]})
                return
            if self.path == "/api/plm/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 3.5)
                dl_p = Path("/home/user/Downloads/iec_enclosure_spec.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    um = pstate["unit_mode"]
                    mult = (1000.0 / 25.4) if um == "NEMA_IMPERIAL_MIL" else 1.0
                    lines = ["plm_code,description,width,height"] + [f"{c},{d},{w*mult:.2f},{h*mult:.2f}" for c, d, w, h in PLM_LIBRARY_MM]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    os.chmod(dl_p, 0o644)
                    pstate["download_exports"] += 1
                    write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "unit_mode": um})
                return
            if self.path == "/api/plm/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.2 if is_adm else 1.2)
                with lock:
                    disc, um = pstate["discipline"], pstate["unit_mode"]
                    seal = make_opaque_seal("ec2_c08", f"{disc}:{um}")
                    pstate["clipboard_copies"] += 1
                    write_json(state_p, pstate)
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "discipline": disc, "unit_mode": um})
                return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"mode": "studio_sso", "url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    from tasks.exam_contention_v2.c06_impress_calc_actuarial import boot_desktop_apps as _boot_sso
    _boot_sso(workspace_map, state_dir)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    from PIL import Image
    ws = next(iter(workspace_map.values()))
    enc = ws / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    svg_p = enc / "front_bezel_silkscreen.svg"
    proof_p = enc / "release" / "front_bezel_proof.png"
    xp = enc / "Thermal_EMI_BOM.xlsx"

    cad = _run_freecad(fcstd_p, "inspect", step_p) if fcstd_p.is_file() else {"ok": False}
    raw_sh = read_multisheet_xlsx(xp) if xp.is_file() else {}
    ev_sh = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}

    def _v(sh: str, ref: str) -> float:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return float(val) if isinstance(val, (int, float)) else -9999.0

    def _s(sh: str, ref: str) -> str:
        val = ((ev_sh.get(sh) or {}).get(ref) or {}).get("value")
        return str(val or "").strip()

    def _f(sh: str, ref: str) -> bool:
        return bool(((raw_sh.get(sh) or {}).get(ref) or {}).get("formula"))

    va = float(cad.get("vent_area_mm2", 0.0)) if cad.get("ok") else -1.0
    ia = float(cad.get("io_area_mm2", 0.0)) if cad.get("ok") else -1.0
    kv = float(cad.get("keepout_viol_mm3", 999.0)) if cad.get("ok") else 999.0

    svg_txt = svg_p.read_text(encoding="utf-8", errors="replace") if svg_p.is_file() else ""
    svg_ok = all((f'id="{g}"' in svg_txt or f"id='{g}'" in svg_txt) for g in ("iec-emc-class-a-badge", "port-legend-qsfp", "thermal-airflow-notice"))
    proof_ok = False
    if proof_p.is_file() and proof_p.stat().st_size > 1500:
        try:
            with Image.open(proof_p) as im:
                proof_ok = (im.size == (1760, 360))
        except Exception:
            proof_ok = False

    checks_a: list[tuple[str, bool, float, str]] = [
        ("vent_area_in_range", bool(cad.get("ok")) and VENT_AREA_RANGE_MM2[0] <= va <= VENT_AREA_RANGE_MM2[1], 0.25, f"vent_area_mm2={va} outside {list(VENT_AREA_RANGE_MM2)}"),
        ("vent_keepouts_clean", bool(cad.get("ok")) and va >= 500.0 and kv <= 0.5, 0.25, f"TopVentCover unmachined or keepout violation={kv} mm3"),
        ("thermal_sheet_sync", bool(cad.get("ok")) and abs(_v("Thermal_Vent_Schedule", "B2") - float(cad["lid_mass_g"])) <= 1.5 and abs(_v("Thermal_Vent_Schedule", "B3") - va) <= 5.0 and _f("Thermal_Vent_Schedule", "B4"), 0.20, "Thermal_Vent_Schedule mass/area/formula mismatch"),
        ("thermal_ecn_seal", _s("Thermal_Vent_Schedule", "B5") == THERMAL_ECN_SEAL, 0.20, "Missing valid PLM_Thermal_ECN_Seal"),
        ("top_torque_bounds", va >= 500.0 and TOP_TORQUE_RANGE_NCM[0] <= _v("Joint_Compliance", "B2") <= TOP_TORQUE_RANGE_NCM[1], 0.10, "Top_Cover_Torque out of range"),
    ]
    checks_b: list[tuple[str, bool, float, str]] = [
        ("rear_io_area", bool(cad.get("ok")) and abs(ia - TRUE_IO_AREA_MM2) <= 25.0, 0.25, f"io_area_mm2={ia} != {TRUE_IO_AREA_MM2}"),
        ("svg_bezel_groups", svg_ok, 0.20, "front_bezel_silkscreen.svg missing required <g> IDs"),
        ("proof_png_1760x360", proof_ok, 0.15, "front_bezel_proof.png missing or != 1760x360"),
        ("emi_sheet_sync", bool(cad.get("ok")) and abs(_v("EMI_Shielding_Schedule", "B2") - float(cad["rear_mass_g"])) <= 1.5 and abs(_v("EMI_Shielding_Schedule", "B3") - ia) <= 5.0 and _f("EMI_Shielding_Schedule", "B4"), 0.15, "EMI_Shielding_Schedule mass/area/formula mismatch"),
        ("emc_ecn_seal", _s("EMI_Shielding_Schedule", "B5") == EMC_ECN_SEAL, 0.15, "Missing valid PLM_EMC_ECN_Seal"),
        ("rear_preload_bounds", ia >= 500.0 and REAR_PRELOAD_RANGE_NCM[0] <= _v("Joint_Compliance", "B3") <= REAR_PRELOAD_RANGE_NCM[1], 0.10, "Rear_Gasket_Preload out of range"),
    ]
    cb = _v("Joint_Compliance", "B4")
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("step_assembly_synced", bool(cad.get("step_synced")) and (va >= 500.0 or ia >= 500.0), 0.08, "release/chassis_housing.step out of sync with .FCStd"),
        ("calc_ecn_tag", _s("Thermal_Vent_Schedule", "C1") == DESK_TAG, 0.06, f"Lost {DESK_TAG} in C1"),
        ("combined_preload_band", _f("Joint_Compliance", "B4") and COMBINED_PRELOAD_BAND_NCM[0] <= cb <= COMBINED_PRELOAD_BAND_NCM[1], 0.11, f"Combined_Fastener_Preload={cb} outside {list(COMBINED_PRELOAD_BAND_NCM)}"),
        ("no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.05, "Open Calc held stale unsaved buffer"),
    ]
    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("mech_thermal_eng", "emi_prepress_eng")
    ws = next(iter(workspace_map.values()))
    enc = ws / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    svg_p = enc / "front_bezel_silkscreen.svg"
    proof_p = enc / "release" / "front_bezel_proof.png"
    xp = enc / "Thermal_EMI_BOM.xlsx"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_m = (role == "mech_thermal_eng")
        disc = "THERMAL_CFD" if is_m else "EMC_BULKHEAD"
        um = "IEC_60297_METRIC_MM" if is_m else "NEMA_IMPERIAL_MIL"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/plm/state", data=json.dumps({"discipline": disc, "unit_mode": um}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/plm/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/plm/copy_seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        ecn_seal = get_x11_clipboard()

        _run_freecad(fcstd_p, "vent" if is_m else "io", step_p)
        cad = _run_freecad(fcstd_p, "inspect", step_p)
        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev["Thermal_Vent_Schedule"].get("C1") or {}).get("value") or DESK_TAG)
        cur_tq = float((ev["Joint_Compliance"].get("B2") or {}).get("value") or 148.0)
        cur_pl = float((ev["Joint_Compliance"].get("B3") or {}).get("value") or 134.0)

        if is_m:
            new_tq = round(max(TOP_TORQUE_RANGE_NCM[0], min(TOP_TORQUE_RANGE_NCM[1], 248.0 - cur_pl)), 2)
            update_single_sheet_xlsx(xp, "Thermal_Vent_Schedule", _make_vent_sheet(float(cad["lid_mass_g"]), float(cad["vent_area_mm2"]), desk_tag=desk_c1, ecn_seal=ecn_seal))
            update_single_sheet_xlsx(xp, "Joint_Compliance", _make_joint_sheet(new_tq, cur_pl))
        else:
            new_pl = round(max(REAR_PRELOAD_RANGE_NCM[0], min(REAR_PRELOAD_RANGE_NCM[1], 248.0 - cur_tq)), 2)
            update_single_sheet_xlsx(xp, "EMI_Shielding_Schedule", _make_emi_sheet(float(cad["rear_mass_g"]), float(cad["io_area_mm2"]), ecn_seal=ecn_seal))
            update_single_sheet_xlsx(xp, "Joint_Compliance", _make_joint_sheet(cur_tq, new_pl))
            svg_p.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="180" viewBox="0 0 880 180">\n'
                '  <rect width="880" height="180" fill="#1e293b"/>\n'
                '  <g id="iec-emc-class-a-badge"><rect x="640" y="20" width="210" height="36" fill="#0284c7"/></g>\n'
                '  <g id="port-legend-qsfp"><text x="24" y="110" fill="#94a3b8">QSFP28</text></g>\n'
                '  <g id="thermal-airflow-notice"><text x="24" y="148" fill="#38bdf8">AIRFLOW</text></g>\n'
                '</svg>\n',
                encoding="utf-8",
            )
            subprocess.run(["inkscape", str(svg_p), f"--export-filename={proof_p}", "--export-width=1760", "--export-height=360"], check=True, capture_output=True, timeout=30)
        reload_open_libreoffice_docs([xp])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    ws = next(iter(workspace_map.values()))
    enc = ws / "enclosure_revC"
    fcstd_p = enc / "chassis_housing.FCStd"
    step_p = enc / "release" / "chassis_housing.step"
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "v0.FCStd"
        snap.write_bytes(fcstd_p.read_bytes())
        solve_role("mech_thermal_eng", workspace_map, port, careful_conc=False)
        fcstd_p.write_bytes(snap.read_bytes())
        solve_role("emi_prepress_eng", workspace_map, port, careful_conc=False)
        update_single_sheet_xlsx(enc / "Thermal_EMI_BOM.xlsx", "Joint_Compliance", _make_joint_sheet(114.0, 100.0))
        reload_open_libreoffice_docs([enc / "Thermal_EMI_BOM.xlsx"])
    _ = step_p
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)
