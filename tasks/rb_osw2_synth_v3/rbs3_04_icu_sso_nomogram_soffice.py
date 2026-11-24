"""RBS3-04: No-CDP HttpOnly ICU Unit Toggle, QPainter 16-Bed ECG Alarms & Single soffice.bin Coupled Fluid.

Grounded in EC2-C06/C07 (80% -> 40% joint_pass) + OSW2-P1/P8 + LAW_6/7/8:
  - `studio_ui` Chromium (NO `--remote-debugging-port=9222`) hosts the HttpOnly ICU Portal (`:19504`)
    with mutually exclusive `VIEW = VASOPRESSOR_CONV` vs `VENT_RENAL_SI`, overwriting shared
    `/home/user/Downloads/icu_round_feed.csv` and single-slot X11 `CLIPBOARD` seals.
  - Live PyQt5 `BedsideWave Monitor` renders 16 ICU ECG strips purely via QPainter (`BED-03, 07, 11, 15`
    in crimson VTach alarm, invisible to AT-SPI text).
  - Single `soffice.bin` holds both `ICU_Round_Ledger.xlsx` (unsaved `ICU-CALC-804`) and
    `ICU_Shift_Brief.odt` (unsaved `ICU-WRITER-804`) with a tight `[1900.0, 1908.0] mL` coupled fluid band.
"""
from __future__ import annotations

import csv
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.rb_osw2_synth_v3.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    boot_studio_sso_chromium,
    build_grade_payload,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    read_odt_plain_text,
    reload_open_libreoffice_docs,
    render_scanned_document_png,
    set_x11_clipboard,
    stage_private_studio_script,
    write_json,
    write_simple_odt,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "RBS3-04"
PORTAL_PORT = 19504
CALC_DESK_TAG = "ICU-CALC-804"
WRITER_DESK_TAG = "ICU-WRITER-804"
FLUID_BAND_ML = (1900.0, 1908.0)

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "No-CDP ICU Unit Toggle, QPainter 16-Bed VTach Monitor & Single soffice.bin Coupled Fluid Ledger",
    "domain": "Critical Care Vasopressor/Ventilator Dosing, Bedside Waveform Triage & EHR Documentation",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING",
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("vasopressor_pharmacist", "ventilator_renal_lead"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/icu_round/ICU_Round_Ledger.xlsx", CALC_DESK_TAG, "calc"),
        ("/workspace/icu_round/ICU_Shift_Brief.odt", WRITER_DESK_TAG, "writer"),
    ),
    "conc_role_timeout_s": 1080,
    "iso_role_timeout_s": 1080,
    "max_cua_calls": 42,
    "factory_blueprint": {
        "horizon_band": "non_saturated_coupled_contention",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.98,
        "role_a": {
            "slug": "vasopressor_pharmacist",
            "est_role_seconds": 520.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "twin_named_modals",
            ],
        },
        "role_b": {
            "slug": "ventilator_renal_lead",
            "est_role_seconds": 520.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "twin_named_modals",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

VTACH_BEDS = {"BED-03", "BED-07", "BED-11", "BED-15"}

# 16 ICU beds: (bed_id, wt_kg, map_mmhg, lactate_mgdl, pf_ratio, cr_umol_l)
# Non-VTach 12 beds: Role A carrier = 80 mL if map<65 else 75 mL -> exact sum = 920 mL!
# Non-VTach 12 beds: Role B hydration = 80 mL if cr_umol_l>140 else 75 mL -> exact sum = 920 mL!
ICU_BEDS: list[tuple[str, float, int, float, int, int]] = [
    ("BED-01", 80.0, 58, 28.8, 165, 162),  # active: A=80, B=80
    ("BED-02", 72.0, 71, 14.4, 240,  98),  # active: A=75, B=75
    ("BED-03", 85.0, 54, 36.0, 120, 190),  # VTACH_ALARM -> HOLD (0 mL carrier/hydration, flagged!)
    ("BED-04", 68.0, 62, 25.2, 195, 155),  # active: A=80, B=80
    ("BED-05", 76.0, 69, 16.2, 260, 110),  # active: A=75, B=75
    ("BED-06", 90.0, 60, 30.6, 150, 175),  # active: A=80, B=80
    ("BED-07", 74.0, 52, 39.6, 115, 205),  # VTACH_ALARM -> HOLD
    ("BED-08", 64.0, 74, 12.6, 280,  88),  # active: A=75, B=75
    ("BED-09", 82.0, 63, 27.0, 170, 148),  # active: A=80, B=80
    ("BED-10", 70.0, 68, 18.0, 230, 112),  # active: A=75, B=75
    ("BED-11", 88.0, 55, 34.2, 128, 184),  # VTACH_ALARM -> HOLD
    ("BED-12", 78.0, 72, 15.3, 255, 104),  # active: A=75, B=75
    ("BED-13", 84.0, 70, 17.1, 225, 118),  # active: A=75, B=75
    ("BED-14", 66.0, 73, 13.5, 275,  92),  # active: A=75, B=75
    ("BED-15", 92.0, 51, 41.4, 110, 215),  # VTACH_ALARM -> HOLD
    ("BED-16", 75.0, 76, 11.7, 290,  95),  # active: A=75, B=75
]
# Verify: among 12 non-VTach beds, 4 have map<65 (BED-01,04,06,09) -> 4*80 + 8*75 = 320 + 600 = 920.0 mL!
# Among 12 non-VTach beds, 4 have cr_umol_l>140 (BED-01,04,06,09) -> 4*80 + 8*75 = 320 + 600 = 920.0 mL!
# Norepi mcg/min for non-VTach beds: round(0.12 * wt_kg, 1) if map<65 else round(0.05 * wt_kg, 1)
TRUE_VASO_CARRIER_ML = 920.0
TRUE_RENAL_HYD_ML = 920.0
TRUE_NOREPI_SUM = round(
    sum((0.12 * b[1] if b[2] < 65 else 0.05 * b[1]) for b in ICU_BEDS if b[0] not in VTACH_BEDS),
    1,
)
TRUE_PRONE_BEDS = sorted(b[0] for b in ICU_BEDS if b[0] not in VTACH_BEDS and b[4] < 180)  # BED-01, BED-06, BED-09

VASO_SEAL = make_opaque_seal("rbs304_icu", "VASOPRESSOR_CONV:MG_DL")
VENT_SEAL = make_opaque_seal("rbs304_icu", "VENT_RENAL_SI:UMOL_L")

BEDSIDE_QT_SOURCE = f"""import math, sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

VTACH = {repr(sorted(VTACH_BEDS))}

class WaveGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(860, 460)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(10, 15, 26))
        p.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        cw, ch = 205, 105
        for idx in range(16):
            bid = f"BED-{{idx+1:02d}}"
            r, c = idx // 4, idx % 4
            x0, y0 = 16 + c * cw, 16 + r * ch
            is_vt = bid in VTACH
            bg = QColor(127, 29, 29) if is_vt else QColor(15, 38, 34)
            p.fillRect(x0, y0, cw - 10, ch - 10, bg)
            p.setPen(QPen(QColor(248, 113, 113) if is_vt else QColor(52, 211, 153), 2))
            p.drawRect(x0, y0, cw - 10, ch - 10)
            p.setPen(QColor(248, 250, 252))
            p.drawText(x0 + 8, y0 + 18, bid)
            # Draw ECG trace purely via QPainter (LAW_7: VTach sawtooth vs clean sinusoid)
            p.setPen(QPen(QColor(254, 202, 202) if is_vt else QColor(16, 185, 129), 2))
            pts = []
            for k in range(0, 175, 5):
                if is_vt:
                    dy = -24 if (k // 10) % 2 == 0 else 24
                else:
                    dy = -20 if k in (40, 115) else (6 if k in (45, 120) else 0)
                pts.append((x0 + 8 + k, y0 + 58 + dy))
            for j in range(len(pts) - 1):
                p.drawLine(pts[j][0], pts[j][1], pts[j + 1][0], pts[j + 1][1])
            if is_vt:
                p.fillRect(x0 + 115, y0 + 5, 72, 16, QColor(220, 38, 38))
                p.setPen(QColor(255, 255, 255))
                p.drawText(x0 + 120, y0 + 17, "VTACH!")
        p.end()

class BedWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BedsideWave Monitor")
        self.resize(920, 560)
        cw = QWidget(); v = QVBoxLayout(cw)
        lbl = QLabel("ICU 16-Bed Live Telemetry Strip (Red Sawtooth = VTACH_ALARM -> Hold Infusions)")
        lbl.setStyleSheet("padding:6px;background:#1e1b4b;color:#f8fafc;font-weight:bold;")
        v.addWidget(lbl); v.addWidget(WaveGrid()); self.setCentralWidget(cw)

app = QApplication(sys.argv)
w = BedWin(); w.show()
sys.exit(app.exec_())
"""


def _make_vaso_sheet(populated: bool, desk_tag: str = "") -> list[list[Any]]:
    rows: list[list[Any]] = [["Bed_ID", "Status", desk_tag, "Norepi_mcg_min", "Carrier_mL"]]
    for b in ICU_BEDS:
        if not populated:
            rows.append([b[0], "UNVERIFIED", "DRAFT", 0.0, 0.0])
        elif b[0] in VTACH_BEDS:
            rows.append([b[0], "HOLD_VTACH", "ALARM", 0.0, 0.0])
        else:
            nor = round(0.12 * b[1] if b[2] < 65 else 0.05 * b[1], 1)
            car = 80.0 if b[2] < 65 else 75.0
            rows.append([b[0], "INFUSE_ACTIVE", "OK", nor, car])
    return rows


def _make_fluid_sheet(vaso_ml: float, renal_ml: float, buf_a: float, buf_b: float, seal_a: str, seal_b: str) -> list[list[Any]]:
    tot = round(vaso_ml + renal_ml + buf_a + buf_b, 1)
    return [
        ["Fluid_Item", "Volume_mL", "Notes"],
        ["Vaso_Carrier_Volume_mL", round(vaso_ml, 1), "ACTIVE_NON_VTACH_SUM"],
        ["Renal_Hydration_Volume_mL", round(renal_ml, 1), "ACTIVE_NON_VTACH_SUM"],
        ["Flush_Buffer_A_mL", round(buf_a, 1), "PHARMACIST_SIZED_5_TO_60"],
        ["Electrolyte_Buffer_B_mL", round(buf_b, 1), "VENT_LEAD_SIZED_5_TO_60"],
        ["Total_24h_Fluid_mL", ("=SUM(B2:B5)", tot), "TARGET_1900_TO_1908"],
        ["Vasopressor_Round_Seal", seal_a, ""],
        ["Ventilator_Renal_Seal", seal_b, ""],
    ]


def _render_icu_portal_html(view_mode: str) -> str:
    if view_mode == "VASOPRESSOR_CONV":
        rows = "".join(f"<tr><td>{b[0]}</td><td>{b[1]} kg</td><td>{b[2]} mmHg</td><td>{b[3]} mg/dL</td></tr>" for b in ICU_BEDS[:6])
        hdr = "<th>Bed</th><th>Weight</th><th>MAP</th><th>Lactate (CONV mg/dL)</th>"
    else:
        rows = "".join(f"<tr><td>{b[0]}</td><td>{b[4]}</td><td>{b[5]} umol/L</td><td>SI_ACTIVE</td></tr>" for b in ICU_BEDS[:6])
        hdr = "<th>Bed</th><th>PaO2_FiO2</th><th>Creatinine (SI umol/L)</th><th>Unit_Basis</th>"
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>ICU Telemetry &amp; Lab Portal</title>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;}}
.bar{{padding:10px 16px;background:#e2e8f0;display:flex;gap:8px;flex-wrap:wrap;}}button{{padding:6px 11px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:96%;margin:10px auto;background:#fff;}}th,td{{border:1px solid #cbd5e1;padding:5px 8px;font-size:12px;}}</style></head>
<body><header><strong>ICU Rounding &amp; Unit Conversion Portal</strong><span id="vTag">VIEW={view_mode}</span></header>
<div class="bar">
  <button onclick="setV('VASOPRESSOR_CONV')">VASOPRESSOR_CONV (mg/dL)</button>
  <button onclick="setV('VENT_RENAL_SI')">VENT_RENAL_SI (umol/L)</button>
  <button onclick="expCsv()">Export Full 16-Bed CSV (~/Downloads/icu_round_feed.csv)</button>
  <button onclick="cpSeal()">Copy Active View Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<p style="padding:0 16px;font-size:12px;">Showing preview 6 of 16 beds — export CSV in your required VIEW for all 16 beds.</p>
<table><thead><tr>{hdr}</tr></thead><tbody>{rows}</tbody></table>
<script>
async function setV(v){{await fetch('/api/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{view:v}})}});location.reload();}}
async function expCsv(){{const r=await fetch('/api/export',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Exported ['+d.view+']';}}
async function cpSeal(){{const r=await fetch('/api/seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied seal ['+d.view+']';}}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# ICU Vasopressor Titration & Fluid Carrier Work Order — {b}vasopressor_pharmacist{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 16-bed vasopressor titration in {b}/workspace/icu_round/ICU_Round_Ledger.xlsx{b} (open in LibreOffice Calc with active desk tag in `Vaso_Orders!C1`, alongside `ICU_Shift_Brief.odt`), using **BedsideWave Monitor**, the **ICU Rounding Portal** at {b}http://127.0.0.1:{PORTAL_PORT}/{b}, and {b}/workspace/icu_round/Vaso_Nomogram.png{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}VIEW = VASOPRESSOR_CONV{b} in the open Chromium ICU Portal, export `/home/user/Downloads/icu_round_feed.csv` and copy the Vasopressor Round Seal to the clipboard; inspect **BedsideWave Monitor** on the desktop to identify all beds in red `VTACH!` alarm.",
        f"2. Populate `Vaso_Orders` (`A2:E17`) and `Fluid_Envelope` in `ICU_Round_Ledger.xlsx` per `Vaso_Nomogram.png` (`HOLD_VTACH` with `0.0` dose/carrier on `VTACH!` beds; active `Norepi_mcg_min` and `Carrier_mL` on non-alarm beds, preserving `Vaso_Orders!C1`), set `Fluid_Envelope!B2` to the sum of active `Carrier_mL`, set `Fluid_Envelope!B7` to the Vasopressor Round Seal, and size only `Flush_Buffer_A_mL` (`Fluid_Envelope!B4` in `[5, 60]`) so `Total_24h_Fluid_mL` (`Fluid_Envelope!B6`, formula `=SUM(B2:B5)`) lands in `[1900.0, 1908.0]` mL while keeping open LibreOffice windows in sync.",
        f"3. Export {b}/workspace/icu_round/Vasopressor_Orders.pdf{b} from `ICU_Round_Ledger.xlsx` and write {b}/workspace/icu_round/VASO_SUMMARY.json{b} (`vtach_hold_beds`, `total_norepi_mcg_min`, `vaso_carrier_ml`, `vaso_seal`).",
        "",
    ])
    role_b = "\n".join([
        f"# ICU Ventilator Prone Triage, Renal Hydration & Shift Handover Work Order — {b}ventilator_renal_lead{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 16-bed ARDS prone-positioning triage and renal hydration sizing in {b}/workspace/icu_round/ICU_Shift_Brief.odt{b} and {b}ICU_Round_Ledger.xlsx{b} (both open in LibreOffice with active session tags), using **BedsideWave Monitor**, the **ICU Rounding Portal** at {b}http://127.0.0.1:{PORTAL_PORT}/{b}, and {b}/workspace/icu_round/Vent_Renal_Nomogram.png{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}VIEW = VENT_RENAL_SI{b} in the open Chromium ICU Portal, export `/home/user/Downloads/icu_round_feed.csv` and copy the Ventilator Renal Seal to the clipboard; inspect **BedsideWave Monitor** to exclude `VTACH!` alarm beds from active hydration and prone positioning.",
        f"2. Per `Vent_Renal_Nomogram.png`, compute `Renal_Hydration_Volume_mL` across the non-alarm beds, set `Fluid_Envelope!B3` and `Fluid_Envelope!B8` (Ventilator Renal Seal) in `ICU_Round_Ledger.xlsx`, and size only `Electrolyte_Buffer_B_mL` (`Fluid_Envelope!B5` in `[5, 60]`) so `Fluid_Envelope!B6` (`=SUM(B2:B5)`) lands in `[1900.0, 1908.0]` mL (preserving `Vaso_Orders!C1` and `B2, B4, B7`).",
        f"3. Update `ICU_Shift_Brief.odt` (preserving `{WRITER_DESK_TAG}`) to record `VTACH_BEDS`, `PRONE_ELIGIBLE_BEDS` (non-VTach beds with `PaO2_FiO2 < 180`), and the Ventilator Renal Seal, export {b}/workspace/icu_round/ICU_Shift_Brief.pdf{b}, and write {b}/workspace/icu_round/VENT_SUMMARY.json{b} (`vtach_hold_beds`, `prone_eligible_beds`, `renal_hydration_ml`, `vent_seal`).",
        "",
    ])
    return {"vasopressor_pharmacist": role_a, "ventilator_renal_lead": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    ir = ws / "icu_round"
    ir.mkdir(parents=True, exist_ok=True)

    render_scanned_document_png(
        ir / "Vaso_Nomogram.png",
        "ICU VASOPRESSOR & CARRIER PROTOCOL (CONV UNITS)",
        [
            "1. Any bed showing red VTACH! sawtooth alarm on BedsideWave Monitor -> status='HOLD_VTACH', Norepi=0.0, Carrier=0.0.",
            "2. Non-alarm beds with MAP < 65 mmHg: Norepi_mcg_min = round(0.12 * Weight_kg, 1), Carrier_mL = 80.0.",
            "3. Non-alarm beds with MAP >= 65 mmHg: Norepi_mcg_min = round(0.05 * Weight_kg, 1), Carrier_mL = 75.0.",
            "4. Size Flush_Buffer_A_mL in [5.0, 60.0] so Fluid_Envelope!B6 (=SUM(B2:B5)) is within [1900.0, 1908.0] mL.",
        ],
        stamp_text="CRITICAL CARE PHARMACY 2026",
    )
    render_scanned_document_png(
        ir / "Vent_Renal_Nomogram.png",
        "ICU ARDS PRONE & RENAL HYDRATION PROTOCOL (SI UNITS)",
        [
            "1. Exclude all red VTACH! alarm beds (0.0 mL hydration; contraindicated for prone turn).",
            "2. Non-alarm beds with Creatinine_SI > 140 umol/L: Hydration = 80.0 mL; otherwise Hydration = 75.0 mL.",
            "3. Prone-eligible beds: non-alarm beds with PaO2_FiO2 < 180 (sorted Bed_ID list).",
            "4. Size Electrolyte_Buffer_B_mL in [5.0, 60.0] so Fluid_Envelope!B6 (=SUM(B2:B5)) is within [1900.0, 1908.0] mL.",
        ],
        stamp_text="PULMONARY & RENAL ICU 2026",
    )

    write_multisheet_xlsx(
        ir / "ICU_Round_Ledger.xlsx",
        [
            ("Vaso_Orders", _make_vaso_sheet(populated=False, desk_tag="")),
            ("Fluid_Envelope", _make_fluid_sheet(945.0, 945.0, 12.0, 12.0, "PENDING", "PENDING")),
        ],
    )
    write_simple_odt(
        ir / "ICU_Shift_Brief.odt",
        "ICU Shift Handover Brief (Draft)",
        [("STATUS", "PENDING_VTACH_AND_PRONE_TRIAGE")],
    )

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


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
        "view": "VASOPRESSOR_CONV",
        "session_switches": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)
    dl_p = Path("/home/user/Downloads/icu_round_feed.csv")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a: Any) -> None:
            return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("rbs304_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: Any) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True}); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302); self.send_header("Set-Cookie", f"rbs304_sso={sso_cookie}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not self._authed():
                self._send_json(401, {"error": "Use authenticated Chromium ICU Portal window on desktop"}); return
            with lock:
                vw = pstate["view"]
            raw = _render_icu_portal_html(vw).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"}); return
            ln = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln > 0 else {}
            if self.path == "/api/state":
                vw = str(body.get("view") or "")
                if vw in ("VASOPRESSOR_CONV", "VENT_RENAL_SI"):
                    with lock:
                        if pstate["view"] != vw:
                            pstate["session_switches"] += 1
                            pstate["contention_events"] += 1
                        pstate["view"] = vw
                        write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "view": vw}); return
            if self.path == "/api/export":
                is_adm = self.headers.get("X-Internal-Admin") == admin_key
                time.sleep(0.15 if is_adm else 0.9)
                with lock:
                    vw = pstate["view"]
                    buf = io.StringIO(); cw = csv.writer(buf)
                    if vw == "VASOPRESSOR_CONV":
                        cw.writerow(["bed_id", "weight_kg", "map_mmhg", "lactate_mgdl"])
                        for b in ICU_BEDS:
                            cw.writerow([b[0], b[1], b[2], b[3]])
                    else:
                        cw.writerow(["bed_id", "pao2_fio2", "creatinine_umol_l"])
                        for b in ICU_BEDS:
                            cw.writerow([b[0], b[4], b[5]])
                    dl_p.parent.mkdir(parents=True, exist_ok=True)
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(buf.getvalue(), encoding="utf-8")
                    os.chmod(dl_p, 0o644)
                    write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "view": vw}); return
            if self.path == "/api/seal":
                is_adm = self.headers.get("X-Internal-Admin") == admin_key
                time.sleep(0.15 if is_adm else 1.1)
                with lock:
                    vw = pstate["view"]
                    seal = VASO_SEAL if vw == "VASOPRESSOR_CONV" else VENT_SEAL
                    pstate["clipboard_copies"] += 1
                    write_json(state_p, pstate)
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "view": vw}); return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    stage_private_studio_script(state_dir, "bedside_ref.py", BEDSIDE_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["bedside_ref.py"], wait_s=1.8)
    boot_studio_sso_chromium(state_dir)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    ir = ws / "icu_round"
    xp = ir / "ICU_Round_Ledger.xlsx"
    odt_p = ir / "ICU_Shift_Brief.odt"
    pdf_a = ir / "Vasopressor_Orders.pdf"
    pdf_b = ir / "ICU_Shift_Brief.pdf"
    sum_a = read_json_safe(ir / "VASO_SUMMARY.json")
    sum_b = read_json_safe(ir / "VENT_SUMMARY.json")

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

    vt_holds = sum(1 for r in range(2, 18) if _s("Vaso_Orders", f"A{r}") in VTACH_BEDS and _v("Vaso_Orders", f"D{r}") == 0.0 and _v("Vaso_Orders", f"E{r}") == 0.0 and "HOLD" in _s("Vaso_Orders", f"B{r}").upper())
    act_doses = sum(
        1
        for idx, b in enumerate(ICU_BEDS, start=2)
        if b[0] not in VTACH_BEDS
        and abs(_v("Vaso_Orders", f"D{idx}") - round(0.12 * b[1] if b[2] < 65 else 0.05 * b[1], 1)) <= 0.25
    )
    pa_txt = extract_pdf_text(pdf_a)
    pb_txt = extract_pdf_text(pdf_b)
    odt_txt = read_odt_plain_text(odt_p)

    # 18 checks Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_sum_exists", (ir / "VASO_SUMMARY.json").is_file(), 0.04, "Missing VASO_SUMMARY.json"),
        ("a_vtach_json", sorted(sum_a.get("vtach_hold_beds") or []) == sorted(VTACH_BEDS), 0.07, "VASO_SUMMARY vtach_hold_beds != BED-03/07/11/15"),
        ("a_vtach_sheet4", vt_holds == 4, 0.07, f"Vaso_Orders VTach HOLD rows {vt_holds}/4 != 4"),
        ("a_doses_half6", act_doses >= 6, 0.05, f"Vaso_Orders active doses {act_doses}/12 < 6"),
        ("a_doses_10", act_doses >= 10, 0.05, f"Vaso_Orders active doses {act_doses}/12 < 10"),
        ("a_doses_all12", act_doses == 12, 0.07, f"Vaso_Orders active doses {act_doses}/12 != 12"),
        ("a_norepi_sum", isinstance(sum_a.get("total_norepi_mcg_min"), (int, float)) and abs(float(sum_a["total_norepi_mcg_min"]) - TRUE_NOREPI_SUM) <= 0.6, 0.06, f"total_norepi_mcg_min != {TRUE_NOREPI_SUM}"),
        ("a_b2_920", abs(_v("Fluid_Envelope", "B2") - TRUE_VASO_CARRIER_ML) <= 0.5, 0.08, f"Fluid_Envelope!B2={_v('Fluid_Envelope','B2')} != 920.0"),
        ("a_json_carrier_920", isinstance(sum_a.get("vaso_carrier_ml"), (int, float)) and abs(float(sum_a["vaso_carrier_ml"]) - 920.0) <= 0.5, 0.05, "vaso_carrier_ml != 920.0"),
        ("a_b4_bounds", 5.0 <= _v("Fluid_Envelope", "B4") <= 60.0, 0.06, "Flush_Buffer_A_mL outside [5, 60]"),
        ("a_b6_formula", _f("Fluid_Envelope", "B6"), 0.05, "Fluid_Envelope!B6 missing SUM formula"),
        ("a_b7_seal", _s("Fluid_Envelope", "B7") == VASO_SEAL, 0.09, "Fluid_Envelope!B7 missing Vasopressor_Round_Seal (unit collision?)"),
        ("a_json_seal", sum_a.get("vaso_seal") == VASO_SEAL, 0.06, "VASO_SUMMARY vaso_seal mismatch"),
        ("a_no_seal_swap", _s("Fluid_Envelope", "B7") != VENT_SEAL, 0.05, "Fluid_Envelope!B7 contaminated with VENT_SEAL"),
        ("a_pdf_exists", pdf_a.is_file(), 0.04, "Missing Vasopressor_Orders.pdf"),
        ("a_pdf_920", "920" in pa_txt, 0.04, "Vasopressor_Orders.pdf missing 920 carrier volume"),
        ("a_pdf_seal", VASO_SEAL[:10] in pa_txt, 0.04, "Vasopressor_Orders.pdf missing Vaso Seal"),
        ("a_bed01_dose", abs(_v("Vaso_Orders", "D2") - 9.6) <= 0.25, 0.03, "BED-01 Norepi != 9.6"),
    ]

    # 18 checks Role B
    prone_in_odt = sum(1 for b in TRUE_PRONE_BEDS if b in odt_txt)
    vt_in_odt = sum(1 for b in VTACH_BEDS if b in odt_txt)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_sum_exists", (ir / "VENT_SUMMARY.json").is_file(), 0.04, "Missing VENT_SUMMARY.json"),
        ("b_vtach_json", sorted(sum_b.get("vtach_hold_beds") or []) == sorted(VTACH_BEDS), 0.07, "VENT_SUMMARY vtach_hold_beds != BED-03/07/11/15"),
        ("b_prone_json", sorted(sum_b.get("prone_eligible_beds") or []) == TRUE_PRONE_BEDS, 0.08, f"prone_eligible_beds != {TRUE_PRONE_BEDS}"),
        ("b_no_vtach_in_prone", not any(b in (sum_b.get("prone_eligible_beds") or []) for b in VTACH_BEDS), 0.06, "Included VTach alarm bed in prone_eligible_beds"),
        ("b_b3_920", abs(_v("Fluid_Envelope", "B3") - TRUE_RENAL_HYD_ML) <= 0.5, 0.08, f"Fluid_Envelope!B3={_v('Fluid_Envelope','B3')} != 920.0"),
        ("b_json_hyd_920", isinstance(sum_b.get("renal_hydration_ml"), (int, float)) and abs(float(sum_b["renal_hydration_ml"]) - 920.0) <= 0.5, 0.05, "renal_hydration_ml != 920.0"),
        ("b_b5_bounds", 5.0 <= _v("Fluid_Envelope", "B5") <= 60.0, 0.06, "Electrolyte_Buffer_B_mL outside [5, 60]"),
        ("b_b8_seal", _s("Fluid_Envelope", "B8") == VENT_SEAL, 0.09, "Fluid_Envelope!B8 missing Ventilator_Renal_Seal (unit collision?)"),
        ("b_json_seal", sum_b.get("vent_seal") == VENT_SEAL, 0.06, "VENT_SUMMARY vent_seal mismatch"),
        ("b_no_seal_swap", _s("Fluid_Envelope", "B8") != VASO_SEAL, 0.05, "Fluid_Envelope!B8 contaminated with VASO_SEAL"),
        ("b_odt_prone3", prone_in_odt == 3, 0.06, f"ICU_Shift_Brief.odt prone beds {prone_in_odt}/3"),
        ("b_odt_vtach4", vt_in_odt == 4, 0.06, f"ICU_Shift_Brief.odt VTach beds {vt_in_odt}/4"),
        ("b_odt_seal", VENT_SEAL in odt_txt, 0.06, "ICU_Shift_Brief.odt missing Ventilator_Renal_Seal"),
        ("b_pdf_exists", pdf_b.is_file(), 0.04, "Missing ICU_Shift_Brief.pdf"),
        ("b_pdf_seal", VENT_SEAL[:10] in pb_txt, 0.05, "ICU_Shift_Brief.pdf missing Vent Seal"),
        ("b_pdf_desk_tag", WRITER_DESK_TAG in pb_txt, 0.05, f"ICU_Shift_Brief.pdf missing {WRITER_DESK_TAG}"),
        ("b_pdf_prone", all(b in pb_txt for b in TRUE_PRONE_BEDS), 0.04, "ICU_Shift_Brief.pdf missing prone beds"),
        ("b_b6_formula_kept", _f("Fluid_Envelope", "B6"), 0.00 + 0.00 or 0.02, "Fluid_Envelope!B6 formula lost"),
    ]
    checks_b[-2] = ("b_pdf_prone", all(b in pb_txt for b in TRUE_PRONE_BEDS), 0.02, "ICU_Shift_Brief.pdf missing prone beds")

    # 4 joint coupled checks -> total 40 subchecks (total weight 0.18 <= 0.20 cap!)
    tot_fl = _v("Fluid_Envelope", "B6")
    fl_ok = _f("Fluid_Envelope", "B6") and (FLUID_BAND_ML[0] <= tot_fl <= FLUID_BAND_ML[1])
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_coupled_fluid_band", fl_ok, 0.08, f"Total_24h_Fluid_mL={tot_fl} outside [1900.0, 1908.0] mL"),
        ("j_calc_desk_tag", _s("Vaso_Orders", "C1") == CALC_DESK_TAG, 0.04, f"Vaso_Orders!C1 lost {CALC_DESK_TAG}"),
        ("j_writer_desk_tag", WRITER_DESK_TAG in odt_txt, 0.03, f"ICU_Shift_Brief.odt lost {WRITER_DESK_TAG}"),
        ("j_no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.03, "Open soffice.bin held stale unsaved buffer"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.88,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("vasopressor_pharmacist", "ventilator_renal_lead")
    ws = next(iter(workspace_map.values()))
    ir = ws / "icu_round"
    xp = ir / "ICU_Round_Ledger.xlsx"
    odt_p = ir / "ICU_Shift_Brief.odt"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        flush_open_libreoffice_to_disk(odt_p)
        is_a = (role == "vasopressor_pharmacist")
        vw = "VASOPRESSOR_CONV" if is_a else "VENT_RENAL_SI"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/state", data=json.dumps({"view": vw}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/export", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_v = get_x11_clipboard()

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev.get("Vaso_Orders") or {}).get("C1", {}).get("value") or CALC_DESK_TAG)
        cur_b2 = float((ev.get("Fluid_Envelope") or {}).get("B2", {}).get("value") or 945.0)
        cur_b3 = float((ev.get("Fluid_Envelope") or {}).get("B3", {}).get("value") or 945.0)
        cur_b4 = float((ev.get("Fluid_Envelope") or {}).get("B4", {}).get("value") or 12.0)
        cur_b5 = float((ev.get("Fluid_Envelope") or {}).get("B5", {}).get("value") or 12.0)
        cur_s7 = str((ev.get("Fluid_Envelope") or {}).get("B7", {}).get("value") or "PENDING")
        cur_s8 = str((ev.get("Fluid_Envelope") or {}).get("B8", {}).get("value") or "PENDING")

        if is_a:
            new_b4 = round(max(5.0, min(60.0, 1904.0 - (TRUE_VASO_CARRIER_ML + cur_b3 + cur_b5))), 1)
            update_single_sheet_xlsx(xp, "Vaso_Orders", _make_vaso_sheet(populated=True, desk_tag=desk_c1))
            update_single_sheet_xlsx(xp, "Fluid_Envelope", _make_fluid_sheet(TRUE_VASO_CARRIER_ML, cur_b3, new_b4, cur_b5, seal_v, cur_s8))
            convert_doc_to_pdf_isolated(xp, ir / "Vasopressor_Orders.pdf")
            write_json(
                ir / "VASO_SUMMARY.json",
                {
                    "vtach_hold_beds": sorted(VTACH_BEDS),
                    "total_norepi_mcg_min": TRUE_NOREPI_SUM,
                    "vaso_carrier_ml": TRUE_VASO_CARRIER_ML,
                    "vaso_seal": seal_v,
                },
            )
        else:
            new_b5 = round(max(5.0, min(60.0, 1904.0 - (cur_b2 + TRUE_RENAL_HYD_ML + cur_b4))), 1)
            update_single_sheet_xlsx(xp, "Fluid_Envelope", _make_fluid_sheet(cur_b2, TRUE_RENAL_HYD_ML, cur_b4, new_b5, cur_s7, seal_v))
            paras = [
                ("DESK_SESSION_TAG", WRITER_DESK_TAG),
                ("VTACH_BEDS", ",".join(sorted(VTACH_BEDS))),
                ("PRONE_ELIGIBLE_BEDS", ",".join(TRUE_PRONE_BEDS)),
                ("VENTILATOR_RENAL_SEAL", seal_v),
            ]
            write_simple_odt(odt_p, "ICU Shift Handover Final", paras)
            convert_doc_to_pdf_isolated(odt_p, ir / "ICU_Shift_Brief.pdf")
            write_json(
                ir / "VENT_SUMMARY.json",
                {
                    "vtach_hold_beds": sorted(VTACH_BEDS),
                    "prone_eligible_beds": TRUE_PRONE_BEDS,
                    "renal_hydration_ml": TRUE_RENAL_HYD_ML,
                    "vent_seal": seal_v,
                },
            )
        reload_open_libreoffice_docs([xp, odt_p])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_8 + LAW_6): Stale dual-lever sizing pushes Total_24h_Fluid_mL to 1894.0 (<1900) & swaps seal."""
    ws = next(iter(workspace_map.values()))
    xp = ws / "icu_round" / "ICU_Round_Ledger.xlsx"
    solve_role("vasopressor_pharmacist", workspace_map, port, careful_conc=False)
    solve_role("ventilator_renal_lead", workspace_map, port, careful_conc=False)
    update_single_sheet_xlsx(xp, "Fluid_Envelope", _make_fluid_sheet(920.0, 920.0, 27.0, 27.0, VENT_SEAL, VENT_SEAL))
    reload_open_libreoffice_docs([xp, ws / "icu_round" / "ICU_Shift_Brief.odt"])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 5
    write_json(sp, st)
