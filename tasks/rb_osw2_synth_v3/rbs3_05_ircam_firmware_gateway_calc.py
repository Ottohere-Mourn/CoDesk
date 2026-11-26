"""RBS3-05: No-CDP Compliance Portal, QPainter IRCam PCB Heatmap, Live :19515 Daemon & Calc Power BOM.

Grounded in EC2-C08/C09 + RB-B5 Thermal Canvas + OSW2-P14/P15 + LAW_6/7/8:
  - `studio_ui` Chromium (NO CDP port) hosts the HttpOnly Hardware & Bus Compliance Portal (`:19505`)
    with mutually exclusive `MODE = VRM_THERMAL_SPEC` vs `CAN_FD_VECTOR_SPEC`, sharing
    `/home/user/Downloads/board_compliance.csv` and single-slot X11 `CLIPBOARD` seals.
  - Live PyQt5 `IRCam PCB Analyzer` renders an 8-zone PCB thermal map purely via QPainter (`Z2, Z5, Z7`
    white-hot hotspots >=92C, invisible to AT-SPI text).
  - Both roles co-operate on live `:19515` `/workspace/gateway/` daemon + open `LibreOffice Calc`
    `Board_Thermal_BOM.xlsx` (unsaved `PWR-CALC-805`) under a tight `[190.0, 190.8] W` coupled TDP band.
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
import subprocess
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
    reload_open_libreoffice_docs,
    set_x11_clipboard,
    stage_private_studio_script,
    write_json,
)
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "RBS3-05"
PORTAL_PORT = 19505
GATEWAY_PORT = 19515
CALC_DESK_TAG = "PWR-CALC-805"
POWER_BAND_W = (190.0, 190.8)

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "No-CDP Bus/VRM Portal, QPainter IRCam PCB Hotspots, Live :19515 Gateway & Coupled Calc TDP BOM",
    "domain": "Embedded Power/Thermal Engineering, CAN-FD Firmware Daemon Remediation & BOM Coordination",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_8_LIVE_STATE_INVALIDATION_AND_ZERO_SPOILER_COUPLING",
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("thermal_power_eng", "protocol_firmware_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (GATEWAY_PORT,),
    "open_gui_docs": (
        ("/workspace/gateway/Board_Thermal_BOM.xlsx", CALC_DESK_TAG, "calc"),
    ),
    "conc_role_timeout_s": 1080,
    "iso_role_timeout_s": 1080,
    "max_cua_calls": 42,
    "factory_blueprint": {
        "horizon_band": "non_saturated_coupled_contention",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.98,
        "role_a": {
            "slug": "thermal_power_eng",
            "est_role_seconds": 510.0,
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
            "slug": "protocol_firmware_eng",
            "est_role_seconds": 510.0,
            "traits": [
                "zero_spoiler_multi_surface_discovery",
                "live_pixel_or_mutable_session_invalidation",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "twin_named_modals",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

HOTSPOT_ZONES = ["Z2", "Z5", "Z7"]
VRM_ZONES: list[tuple[str, str, float, float]] = [
    ("Z1", "VDD_CORE_0", 13.0, 10.5),
    ("Z2", "VDD_CORE_1", 15.5, 11.0),
    ("Z3", "VDD_SOC",    11.5,  9.0),
    ("Z4", "VDD_DDR",    10.5,  8.5),
    ("Z5", "VDD_SERDES", 14.5, 11.5),
    ("Z6", "VDD_PCIE",   12.0,  9.5),
    ("Z7", "VDD_NPU",    15.0, 11.0),
    ("Z8", "VDD_MGMT",   11.5,  9.0),
]
TRUE_VRM_RAIL_W = 92.0

ASIC_RAILS: list[tuple[str, int, float, str]] = [
    ("IO-01", 1, 16.0, "FD_CH0"),
    ("IO-02", 1, 15.5, "FD_CH1"),
    ("IO-03", 0, 14.0, "DISABLED_SPARE"),
    ("IO-04", 1, 15.0, "FD_CH2"),
    ("IO-05", 1, 14.5, "FD_CH3"),
    ("IO-06", 0, 11.0, "DISABLED_TEST"),
    ("IO-07", 1, 16.0, "FD_SWITCH"),
    ("IO-08", 1, 15.0, "FD_PHY_SYNC"),
]
TRUE_ASIC_IO_W = 92.0

VRM_SEAL = make_opaque_seal("rbs305_hw", "VRM_THERMAL_SPEC:DERATED_85PWM")
CAN_SEAL = make_opaque_seal("rbs305_hw", "CAN_FD_VECTOR_SPEC:CRC16_CCITT")


def crc16_ccitt(hex_payload: str) -> str:
    data = bytes.fromhex(hex_payload)
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)
    return f"{crc:04X}"


IRCAM_QT_SOURCE = f"""import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QMainWindow, QPushButton, QShortcut, QVBoxLayout, QWidget

HOTS = {repr(HOTSPOT_ZONES)}

class IrCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(840, 380)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(12, 16, 28))
        p.setFont(QFont("DejaVu Sans Mono", 11, QFont.Bold))
        cw, ch = 195, 155
        for i in range(8):
            zid = f"Z{{i+1}}"
            r, c = i // 4, i % 4
            x0, y0 = 24 + c * cw, 24 + r * ch
            hot = zid in HOTS
            p.fillRect(x0, y0, cw - 14, ch - 14, QColor(220, 38, 38) if hot else QColor(30, 58, 138))
            if hot:
                p.fillRect(x0 + 28, y0 + 36, cw - 70, ch - 82, QColor(254, 240, 138))
            p.setPen(QPen(QColor(254, 249, 195) if hot else QColor(96, 165, 250), 2))
            p.drawRect(x0, y0, cw - 14, ch - 14)
            p.setPen(QColor(255, 255, 255))
            p.drawText(x0 + 10, y0 + 24, zid)
        p.setPen(QColor(226, 232, 240))
        p.drawText(24, 360, "Scale: Blue=58C (Steady) | Red+Yellow Core = HOTSPOT >=92C (Apply Derated Power + 85% PWM)")
        p.end()

class IrWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IRCam PCB Analyzer")
        self.resize(920, 540)
        cw = QWidget(); v = QVBoxLayout(cw)
        lbl = QLabel("IRCam 8-Zone Radiometric PCB View (Press Ctrl+P for Thermal Derating Policy)")
        lbl.setStyleSheet("padding:6px;background:#0f172a;color:#f8fafc;font-weight:bold;")
        v.addWidget(lbl); v.addWidget(IrCanvas())
        bp = QPushButton("&Preferences (Ctrl+P)"); bp.clicked.connect(self.open_prefs); v.addWidget(bp)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)

    def open_prefs(self):
        d = QDialog(self); d.setWindowTitle("Preferences"); d.setModal(True); d.resize(450, 190)
        dv = QVBoxLayout(d)
        dv.addWidget(QLabel("IRCam Thermal Derating Policy"))
        dv.addWidget(QLabel("Hotspot zones (>=92C) MUST use derated_hotspot_w; cool zones use steady_w."))
        dv.addWidget(QLabel("Required gateway fan_pwm_duty_pct = 85"))
        bc = QPushButton("Close"); bc.clicked.connect(d.accept); dv.addWidget(bc)
        d.exec_()

app = QApplication(sys.argv)
w = IrWin(); w.show()
sys.exit(app.exec_())
"""

INITIAL_GATEWAY_PY = '''#!/usr/bin/env python3
"""Shared board telemetry & CAN-FD frame verification daemon on 127.0.0.1:19515."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parent / "power_thermal_cfg.json"

def compute_crc(hex_payload: str) -> str:
    data = bytes.fromhex(hex_payload)
    return f"{sum(data) & 0xFFFF:04X}"

class GwHandler(BaseHTTPRequestHandler):
    def log_message(self, *_a): return

    def _send(self, code: int, obj: dict):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/status":
            cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
            self._send(200, {"ok": True, "config": cfg}); return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln > 0 else {}
        if self.path == "/api/frame":
            payload = str(body.get("payload_hex") or "")
            crc_in = str(body.get("crc_hex") or "").upper()
            seq_burst = int(body.get("burst_index") or 1)
            if seq_burst > 999:
                self._send(200, {"accepted": False, "status": "RATE_LIMITED"}); return
            exp = compute_crc(payload)
            ok = (crc_in == exp)
            self._send(200, {"accepted": ok, "status": "ACCEPTED" if ok else "BAD_CRC", "expected_crc": exp}); return
        self._send(404, {"error": "not found"})

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("127.0.0.1", 19515), GwHandler).serve_forever()
'''


def _make_vrm_sheet(populated: bool, desk_tag: str = "") -> list[list[Any]]:
    rows: list[list[Any]] = [["Zone_ID", "Thermal_Class", desk_tag, "Assigned_W"]]
    for zid, _rn, st_w, dr_w in VRM_ZONES:
        if not populated:
            rows.append([zid, "UNVERIFIED", "DRAFT", 0.0])
        elif zid in HOTSPOT_ZONES:
            rows.append([zid, "HOTSPOT_DERATED", "DERATED", dr_w])
        else:
            rows.append([zid, "COOL_STEADY", "STEADY", st_w])
    return rows


def _make_power_sheet(vrm_w: float, asic_w: float, gb_a: float, gb_b: float, seal_a: str, seal_b: str) -> list[list[Any]]:
    tot = round(vrm_w + asic_w + gb_a + gb_b, 2)
    return [
        ["Power_Item", "Watts_W", "Notes"],
        ["VRM_Derated_Rail_W", round(vrm_w, 2), "8_ZONE_SUM"],
        ["ASIC_Enabled_IO_W", round(asic_w, 2), "ENABLED_RAILS_SUM"],
        ["Thermal_Guardband_A_W", round(gb_a, 2), "THERMAL_ENG_0.5_TO_6.0"],
        ["Protocol_Guardband_B_W", round(gb_b, 2), "FIRMWARE_ENG_0.5_TO_6.0"],
        ["Total_Board_Power_W", ("=SUM(B2:B5)", tot), "TARGET_190.0_TO_190.8"],
        ["VRM_Thermal_Seal", seal_a, ""],
        ["CAN_Protocol_Seal", seal_b, ""],
    ]


def _render_hw_portal_html(mode: str) -> str:
    if mode == "VRM_THERMAL_SPEC":
        rows = "".join(f"<tr><td>{z[0]}</td><td>{z[1]}</td><td>{z[2]} W</td><td>{z[3]} W</td></tr>" for z in VRM_ZONES[:4])
        hdr = "<th>Zone</th><th>Rail</th><th>Steady_W</th><th>Derated_Hotspot_W</th>"
    else:
        rows = "".join(f"<tr><td>{a[0]}</td><td>{a[1]}</td><td>{a[2]} W</td><td>{a[3]}</td></tr>" for a in ASIC_RAILS[:4])
        hdr = "<th>IO_ID</th><th>Enabled</th><th>Load_W</th><th>Channel</th>"
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Hardware &amp; Bus Compliance Portal</title>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;}}header{{background:#0f172a;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;}}
.bar{{padding:10px 16px;background:#e2e8f0;display:flex;gap:8px;flex-wrap:wrap;}}button{{padding:6px 11px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:96%;margin:10px auto;background:#fff;}}th,td{{border:1px solid #cbd5e1;padding:5px 8px;font-size:12px;}}</style></head>
<body><header><strong>Hardware Thermal &amp; CAN-FD Compliance Portal</strong><span>MODE={mode}</span></header>
<div class="bar">
  <button onclick="setM('VRM_THERMAL_SPEC')">VRM_THERMAL_SPEC</button>
  <button onclick="setM('CAN_FD_VECTOR_SPEC')">CAN_FD_VECTOR_SPEC</button>
  <button onclick="expCsv()">Export Full Spec CSV (~/Downloads/board_compliance.csv)</button>
  <button onclick="cpSeal()">Copy Active Mode Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<p style="padding:0 16px;font-size:12px;">CAN-FD Spec: CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF); reject burst_index &gt; 8 as RATE_LIMITED.</p>
<table><thead><tr>{hdr}</tr></thead><tbody>{rows}</tbody></table>
<script>
async function setM(m){{await fetch('/api/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{mode:m}})}});location.reload();}}
async function expCsv(){{const r=await fetch('/api/export',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Exported ['+d.mode+']';}}
async function cpSeal(){{const r=await fetch('/api/seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied seal ['+d.mode+']';}}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# PCB Thermal Derating & Power Envelope Work Order — {b}thermal_power_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Complete the 8-zone VRM thermal derating in {b}/workspace/gateway/Board_Thermal_BOM.xlsx{b} (open in LibreOffice Calc with active desk tag in `VRM_Zones!C1`) and {b}/workspace/gateway/power_thermal_cfg.json{b}, using **IRCam PCB Analyzer** and the **Hardware Compliance Portal** at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Inspect **IRCam PCB Analyzer** (`Ctrl+P` Preferences) on the desktop to identify all white-hot/red hotspot zones (`>=92C`) and required `fan_pwm_duty_pct`; under {b}MODE = VRM_THERMAL_SPEC{b} in the open Chromium portal, export `/home/user/Downloads/board_compliance.csv` and copy the VRM Thermal Seal to the clipboard.",
        f"2. Update `/workspace/gateway/power_thermal_cfg.json` (`hotspot_zones` sorted list, `fan_pwm_duty_pct`, `vrm_derated_rail_w`, `vrm_seal`) so live `GET http://127.0.0.1:{GATEWAY_PORT}/status` serves the updated thermal config.",
        f"3. Populate `VRM_Zones` (`A2:D9`, preserving `VRM_Zones!C1`) and `Power_Envelope!B2` (`VRM_Derated_Rail_W`), `B7` (`VRM_Thermal_Seal`), and size `Thermal_Guardband_A_W` (`B4` in `[0.5, 6.0]`) so `Total_Board_Power_W` (`B6`, formula `=SUM(B2:B5)`) lands in `[190.0, 190.8]` W while keeping Calc in sync, and export {b}/workspace/gateway/Thermal_Report.pdf{b}.",
        "",
    ])
    role_b = "\n".join([
        f"# CAN-FD Gateway Firmware Remediation & ASIC Power Envelope Work Order — {b}protocol_firmware_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Remediate the live `:19515` CAN-FD daemon in {b}/workspace/gateway/gateway_daemon.py{b} and finalize the ASIC IO rail budget in {b}/workspace/gateway/Board_Thermal_BOM.xlsx{b} (open in LibreOffice Calc with active desk tag in `VRM_Zones!C1`), using the **Hardware Compliance Portal** at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Under {b}MODE = CAN_FD_VECTOR_SPEC{b} in the open Chromium portal, export `/home/user/Downloads/board_compliance.csv` and copy the CAN Protocol Seal to the clipboard.",
        f"2. Fix `/workspace/gateway/gateway_daemon.py` so `POST http://127.0.0.1:{GATEWAY_PORT}/api/frame` enforces `CRC-16/CCITT-FALSE` (`poly=0x1021, init=0xFFFF`) and rejects `burst_index > 8` with `accepted=false, status='RATE_LIMITED'`, and restart the live daemon on `127.0.0.1:{GATEWAY_PORT}` (preserving `GET /status`).",
        f"3. Sum `load_w` across `enabled=1` rails from `CAN_FD_VECTOR_SPEC` into `Power_Envelope!B3` (`ASIC_Enabled_IO_W`), set `Power_Envelope!B8` to the CAN Protocol Seal, size `Protocol_Guardband_B_W` (`B5` in `[0.5, 6.0]`) so `Power_Envelope!B6` (`=SUM(B2:B5)`) lands in `[190.0, 190.8]` W (preserving `VRM_Zones!C1` and `B2, B4, B7`), export {b}/workspace/gateway/Protocol_Compliance.pdf{b}, and write {b}/workspace/gateway/FIRMWARE_SUMMARY.json{b} (`asic_enabled_io_w`, `can_seal`).",
        "",
    ])
    return {"thermal_power_eng": role_a, "protocol_firmware_eng": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    gw = ws / "gateway"
    gw.mkdir(parents=True, exist_ok=True)

    (gw / "gateway_daemon.py").write_text(INITIAL_GATEWAY_PY, encoding="utf-8")
    os.chmod(gw / "gateway_daemon.py", 0o755)
    write_json(
        gw / "power_thermal_cfg.json",
        {"hotspot_zones": [], "fan_pwm_duty_pct": 40, "vrm_derated_rail_w": 94.5, "vrm_seal": "PENDING"},
    )
    write_multisheet_xlsx(
        gw / "Board_Thermal_BOM.xlsx",
        [
            ("VRM_Zones", _make_vrm_sheet(populated=False, desk_tag="")),
            ("Power_Envelope", _make_power_sheet(94.5, 94.5, 1.2, 1.2, "PENDING", "PENDING")),
        ],
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
        "mode": "VRM_THERMAL_SPEC",
        "session_switches": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)
    dl_p = Path("/home/user/Downloads/board_compliance.csv")

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
                m = c.get("rbs305_sso")
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
                self.send_response(302); self.send_header("Set-Cookie", f"rbs305_sso={sso_cookie}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers(); return
            if not self._authed():
                self._send_json(401, {"error": "Use authenticated Chromium portal window on desktop"}); return
            with lock:
                md = pstate["mode"]
            raw = _render_hw_portal_html(md).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"}); return
            ln = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln > 0 else {}
            if self.path == "/api/state":
                md = str(body.get("mode") or "")
                if md in ("VRM_THERMAL_SPEC", "CAN_FD_VECTOR_SPEC"):
                    with lock:
                        if pstate["mode"] != md:
                            pstate["session_switches"] += 1
                            pstate["contention_events"] += 1
                        pstate["mode"] = md
                        write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "mode": md}); return
            if self.path == "/api/export":
                is_adm = self.headers.get("X-Internal-Admin") == admin_key
                time.sleep(0.15 if is_adm else 0.9)
                with lock:
                    md = pstate["mode"]
                    buf = io.StringIO(); cw = csv.writer(buf)
                    if md == "VRM_THERMAL_SPEC":
                        cw.writerow(["zone_id", "rail_name", "steady_w", "derated_hotspot_w"])
                        for z in VRM_ZONES:
                            cw.writerow(list(z))
                    else:
                        cw.writerow(["io_id", "enabled", "load_w", "channel"])
                        for a in ASIC_RAILS:
                            cw.writerow(list(a))
                    dl_p.parent.mkdir(parents=True, exist_ok=True)
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(buf.getvalue(), encoding="utf-8")
                    os.chmod(dl_p, 0o644)
                    write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "mode": md}); return
            if self.path == "/api/seal":
                is_adm = self.headers.get("X-Internal-Admin") == admin_key
                time.sleep(0.15 if is_adm else 1.1)
                with lock:
                    md = pstate["mode"]
                    seal = VRM_SEAL if md == "VRM_THERMAL_SPEC" else CAN_SEAL
                    pstate["clipboard_copies"] += 1
                    write_json(state_p, pstate)
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "mode": md}); return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    ws = next(iter(workspace_map.values()))
    gw_py = ws / "gateway" / "gateway_daemon.py"
    subprocess.run(
        ["su", "-s", "/bin/bash", "user", "-c", f"nohup python3 {gw_py} >/tmp/gw19515.log 2>&1 </dev/null &"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    stage_private_studio_script(state_dir, "ircam_ref.py", IRCAM_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["ircam_ref.py"], wait_s=1.8)
    boot_studio_sso_chromium(state_dir)


def _probe_gateway_live() -> dict[str, Any]:
    out: dict[str, Any] = {"status_ok": False, "cfg": {}, "valid_vectors_ok": 0, "bad_crc_rejected": False, "burst_limited": False}
    try:
        st = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{GATEWAY_PORT}/status", timeout=3).read().decode("utf-8"))
        out["status_ok"] = bool(st.get("ok"))
        out["cfg"] = st.get("config") or {}
    except Exception:
        return out

    test_hexes = ["11223344", "DEADBEEF01", "CAFEBABE0055", "0102030405060708", "A55A0F00", "7F8099AA"]
    hits = 0
    for idx, hx in enumerate(test_hexes, start=1):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{GATEWAY_PORT}/api/frame",
                data=json.dumps({"payload_hex": hx, "crc_hex": crc16_ccitt(hx), "burst_index": idx}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            r = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
            if r.get("accepted") is True and r.get("status") == "ACCEPTED":
                hits += 1
        except Exception:
            pass
    out["valid_vectors_ok"] = hits
    try:
        r_bad = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{GATEWAY_PORT}/api/frame",
                    data=json.dumps({"payload_hex": "11223344", "crc_hex": "00AA", "burst_index": 2}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=3,
            ).read().decode("utf-8")
        )
        out["bad_crc_rejected"] = r_bad.get("accepted") is False and r_bad.get("status") == "BAD_CRC"
        r_lim = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{GATEWAY_PORT}/api/frame",
                    data=json.dumps({"payload_hex": "11223344", "crc_hex": crc16_ccitt("11223344"), "burst_index": 9}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=3,
            ).read().decode("utf-8")
        )
        out["burst_limited"] = r_lim.get("accepted") is False and r_lim.get("status") == "RATE_LIMITED"
    except Exception:
        pass
    return out


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    gw = ws / "gateway"
    xp = gw / "Board_Thermal_BOM.xlsx"
    cfg = read_json_safe(gw / "power_thermal_cfg.json")
    fw_sum = read_json_safe(gw / "FIRMWARE_SUMMARY.json")
    pdf_a = gw / "Thermal_Report.pdf"
    pdf_b = gw / "Protocol_Compliance.pdf"
    live = _probe_gateway_live()

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

    zone_hits = sum(
        1
        for idx, (zid, _rn, st_w, dr_w) in enumerate(VRM_ZONES, start=2)
        if abs(_v("VRM_Zones", f"D{idx}") - (dr_w if zid in HOTSPOT_ZONES else st_w)) <= 0.1
    )
    hot_rows = sum(1 for r in range(2, 10) if _s("VRM_Zones", f"A{r}") in HOTSPOT_ZONES and "HOT" in _s("VRM_Zones", f"B{r}").upper())
    pa_txt = extract_pdf_text(pdf_a)
    pb_txt = extract_pdf_text(pdf_b)
    lcfg = live.get("cfg") or {}

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_cfg_hotspots", sorted(cfg.get("hotspot_zones") or []) == HOTSPOT_ZONES, 0.08, "power_thermal_cfg hotspot_zones != ['Z2','Z5','Z7']"),
        ("a_cfg_pwm85", cfg.get("fan_pwm_duty_pct") == 85, 0.06, "fan_pwm_duty_pct != 85"),
        ("a_cfg_rail92", isinstance(cfg.get("vrm_derated_rail_w"), (int, float)) and abs(float(cfg["vrm_derated_rail_w"]) - 92.0) <= 0.1, 0.06, "cfg vrm_derated_rail_w != 92.0"),
        ("a_live_status_hotspots", sorted(lcfg.get("hotspot_zones") or []) == HOTSPOT_ZONES and lcfg.get("fan_pwm_duty_pct") == 85, 0.06, "Live :19515 /status missing updated thermal config"),
        ("a_sheet_hot3", hot_rows == 3, 0.06, f"VRM_Zones HOTSPOT rows {hot_rows}/3"),
        ("a_sheet_zones5", zone_hits >= 5, 0.05, f"VRM_Zones power rows accurate {zone_hits}/8 < 5"),
        ("a_sheet_zones8", zone_hits == 8, 0.07, f"VRM_Zones power rows accurate {zone_hits}/8 != 8"),
        ("a_b2_92", abs(_v("Power_Envelope", "B2") - TRUE_VRM_RAIL_W) <= 0.15, 0.08, f"Power_Envelope!B2={_v('Power_Envelope','B2')} != 92.0"),
        ("a_b4_bounds", abs(_v("Power_Envelope", "B2") - TRUE_VRM_RAIL_W) <= 0.15 and 0.5 <= _v("Power_Envelope", "B4") <= 6.0, 0.06, "Thermal_Guardband_A_W uncalibrated or outside [0.5, 6.0]"),
        ("a_b6_formula", _f("Power_Envelope", "B6"), 0.05, "Power_Envelope!B6 missing SUM formula"),
        ("a_b7_seal", _s("Power_Envelope", "B7") == VRM_SEAL, 0.09, "Power_Envelope!B7 missing VRM_Thermal_Seal (mode collision?)"),
        ("a_cfg_seal", cfg.get("vrm_seal") == VRM_SEAL, 0.06, "power_thermal_cfg vrm_seal mismatch"),
        ("a_no_seal_swap", _s("Power_Envelope", "B7").startswith("ATTEST-") and _s("Power_Envelope", "B7") != CAN_SEAL, 0.05, "Power_Envelope!B7 missing or contaminated with CAN_SEAL"),
        ("a_pdf_exists", pdf_a.is_file(), 0.04, "Missing Thermal_Report.pdf"),
        ("a_pdf_92", "92" in pa_txt, 0.04, "Thermal_Report.pdf missing 92.0 W"),
        ("a_pdf_seal", VRM_SEAL[:10] in pa_txt, 0.04, "Thermal_Report.pdf missing VRM Seal"),
        ("a_z2_derated", abs(_v("VRM_Zones", "D3") - 11.0) <= 0.1, 0.03, "Z2 not derated to 11.0 W"),
        ("a_z1_steady", abs(_v("VRM_Zones", "D2") - 13.0) <= 0.1, 0.02, "Z1 not kept at 13.0 W"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_fw_sum_exists", (gw / "FIRMWARE_SUMMARY.json").is_file(), 0.04, "Missing FIRMWARE_SUMMARY.json"),
        ("b_live_up", bool(live["status_ok"]), 0.06, "Live :19515 gateway daemon down"),
        ("b_crc_half3", int(live["valid_vectors_ok"]) >= 3, 0.06, f"Live CRC-16/CCITT vectors {live['valid_vectors_ok']}/6 < 3"),
        ("b_crc_all6", int(live["valid_vectors_ok"]) == 6, 0.09, f"Live CRC-16/CCITT vectors {live['valid_vectors_ok']}/6 != 6"),
        ("b_bad_crc_rej", bool(live["bad_crc_rejected"]), 0.07, "Live :19515 failed to reject bad CRC with BAD_CRC"),
        ("b_burst_lim8", bool(live["burst_limited"]), 0.08, "Live :19515 failed to reject burst_index=9 with RATE_LIMITED"),
        ("b_b3_92", abs(_v("Power_Envelope", "B3") - TRUE_ASIC_IO_W) <= 0.15, 0.08, f"Power_Envelope!B3={_v('Power_Envelope','B3')} != 92.0"),
        ("b_json_io92", isinstance(fw_sum.get("asic_enabled_io_w"), (int, float)) and abs(float(fw_sum["asic_enabled_io_w"]) - 92.0) <= 0.15, 0.06, "FIRMWARE_SUMMARY asic_enabled_io_w != 92.0"),
        ("b_b5_bounds", abs(_v("Power_Envelope", "B3") - TRUE_ASIC_IO_W) <= 0.15 and 0.5 <= _v("Power_Envelope", "B5") <= 6.0, 0.06, "Protocol_Guardband_B_W uncalibrated or outside [0.5, 6.0]"),
        ("b_b8_seal", _s("Power_Envelope", "B8") == CAN_SEAL, 0.09, "Power_Envelope!B8 missing CAN_Protocol_Seal (mode collision?)"),
        ("b_json_seal", fw_sum.get("can_seal") == CAN_SEAL, 0.06, "FIRMWARE_SUMMARY can_seal mismatch"),
        ("b_no_seal_swap", _s("Power_Envelope", "B8").startswith("ATTEST-") and _s("Power_Envelope", "B8") != VRM_SEAL, 0.05, "Power_Envelope!B8 missing or contaminated with VRM_SEAL"),
        ("b_pdf_exists", pdf_b.is_file(), 0.04, "Missing Protocol_Compliance.pdf"),
        ("b_pdf_92", "92" in pb_txt, 0.04, "Protocol_Compliance.pdf missing 92.0 W"),
        ("b_pdf_seal", CAN_SEAL[:10] in pb_txt, 0.05, "Protocol_Compliance.pdf missing CAN Seal"),
        ("b_b6_formula_kept", _f("Power_Envelope", "B6"), 0.03, "Power_Envelope!B6 formula lost"),
        ("b_gw_file_exists", (gw / "gateway_daemon.py").is_file(), 0.02, "gateway_daemon.py missing"),
        ("b_cfg_preserved", (gw / "power_thermal_cfg.json").is_file(), 0.02, "power_thermal_cfg.json missing"),
    ]

    tot_w = _v("Power_Envelope", "B6")
    w_ok = _f("Power_Envelope", "B6") and (POWER_BAND_W[0] <= tot_w <= POWER_BAND_W[1])
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_coupled_tdp_band", w_ok, 0.08, f"Total_Board_Power_W={tot_w} outside [190.0, 190.8] W"),
        ("j_calc_desk_tag", _s("VRM_Zones", "C1") == CALC_DESK_TAG, 0.04, f"VRM_Zones!C1 lost {CALC_DESK_TAG}"),
        ("j_live_daemon_healthy", bool(live["status_ok"]), 0.03, "Live :19515 daemon unhealthy at grading"),
        ("j_no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.03, "Open LibreOffice Calc held stale unsaved buffer"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


FIXED_GATEWAY_PY = INITIAL_GATEWAY_PY.replace(
    '    data = bytes.fromhex(hex_payload)\n    return f"{sum(data) & 0xFFFF:04X}"',
    '    data = bytes.fromhex(hex_payload)\n    crc = 0xFFFF\n    for b in data:\n        crc ^= b << 8\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else ((crc << 1) & 0xFFFF)\n    return f"{crc:04X}"',
).replace("if seq_burst > 999:", "if seq_burst > 8:")


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("thermal_power_eng", "protocol_firmware_eng")
    ws = next(iter(workspace_map.values()))
    gw = ws / "gateway"
    xp = gw / "Board_Thermal_BOM.xlsx"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        is_a = (role == "thermal_power_eng")
        md = "VRM_THERMAL_SPEC" if is_a else "CAN_FD_VECTOR_SPEC"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/state", data=json.dumps({"mode": md}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/export", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_v = get_x11_clipboard()

        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev.get("VRM_Zones") or {}).get("C1", {}).get("value") or CALC_DESK_TAG)
        cur_b2 = float((ev.get("Power_Envelope") or {}).get("B2", {}).get("value") or 94.5)
        cur_b3 = float((ev.get("Power_Envelope") or {}).get("B3", {}).get("value") or 94.5)
        cur_b4 = float((ev.get("Power_Envelope") or {}).get("B4", {}).get("value") or 1.2)
        cur_b5 = float((ev.get("Power_Envelope") or {}).get("B5", {}).get("value") or 1.2)
        cur_s7 = str((ev.get("Power_Envelope") or {}).get("B7", {}).get("value") or "PENDING")
        cur_s8 = str((ev.get("Power_Envelope") or {}).get("B8", {}).get("value") or "PENDING")

        if is_a:
            write_json(
                gw / "power_thermal_cfg.json",
                {"hotspot_zones": HOTSPOT_ZONES, "fan_pwm_duty_pct": 85, "vrm_derated_rail_w": TRUE_VRM_RAIL_W, "vrm_seal": seal_v},
            )
            new_b4 = round(max(0.5, min(6.0, 190.4 - (TRUE_VRM_RAIL_W + cur_b3 + cur_b5))), 2)
            update_single_sheet_xlsx(xp, "VRM_Zones", _make_vrm_sheet(populated=True, desk_tag=desk_c1))
            update_single_sheet_xlsx(xp, "Power_Envelope", _make_power_sheet(TRUE_VRM_RAIL_W, cur_b3, new_b4, cur_b5, seal_v, cur_s8))
            convert_doc_to_pdf_isolated(xp, gw / "Thermal_Report.pdf")
        else:
            (gw / "gateway_daemon.py").write_text(FIXED_GATEWAY_PY, encoding="utf-8")
            subprocess.run(
                ["bash", "-lc", "pkill -9 -f gateway_daemon.py 2>/dev/null || true; sleep 0.2"],
                check=False, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["su", "-s", "/bin/bash", "user", "-c", f"nohup python3 {gw / 'gateway_daemon.py'} >/tmp/gw19515.log 2>&1 </dev/null & sleep 0.5"],
                check=True, capture_output=True, timeout=15,
            )
            new_b5 = round(max(0.5, min(6.0, 190.4 - (cur_b2 + TRUE_ASIC_IO_W + cur_b4))), 2)
            update_single_sheet_xlsx(xp, "Power_Envelope", _make_power_sheet(cur_b2, TRUE_ASIC_IO_W, cur_b4, new_b5, cur_s7, seal_v))
            convert_doc_to_pdf_isolated(xp, gw / "Protocol_Compliance.pdf")
            write_json(gw / "FIRMWARE_SUMMARY.json", {"asic_enabled_io_w": TRUE_ASIC_IO_W, "can_seal": seal_v})
        reload_open_libreoffice_docs([xp])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_8 + LAW_6): Stale guardbands push TDP to 189.4 W (<190.0) & contaminate VRM seal."""
    ws = next(iter(workspace_map.values()))
    xp = ws / "gateway" / "Board_Thermal_BOM.xlsx"
    solve_role("thermal_power_eng", workspace_map, port, careful_conc=False)
    solve_role("protocol_firmware_eng", workspace_map, port, careful_conc=False)
    update_single_sheet_xlsx(xp, "Power_Envelope", _make_power_sheet(92.0, 92.0, 2.7, 2.7, CAN_SEAL, CAN_SEAL))
    reload_open_libreoffice_docs([xp])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 5
    write_json(sp, st)
