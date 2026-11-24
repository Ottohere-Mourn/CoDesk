"""RBS2-05: Meridian LoanHub 16-Packet Underwriting vs. GateSim 12-Circuit Waveform TA Bench.

Grounded in OSWorld-V2 (OSW2-P7 LoanHub + TA Logisim Digital Logic) & RecreationBench (LAW_7 + LAW_4 + LAW_2 + LAW_1):
  - LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI: GateSim Digital Logic renders 8-cycle 4-channel
    timing waveforms (`CLK`, `IN_BUS`, `GOLD_REF`, `STUDENT_OUT`) and glitch/inversion/race
    fault signatures purely onto a custom QPainter oscilloscope canvas (zero defect names in AT-SPI).
  - LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE: One singleton `:9222` Chromium hosts
    both `Meridian LoanHub` (`:19405`, HttpOnly `lh_sid`) and `CS240 CourseGradebook` (`:19415`,
    HttpOnly `gb_sid`), sharing active tab focus, `/home/user/Downloads/portal_packet_export.csv`,
    and X11 `CLIPBOARD` seals alongside live PyQt5 `GateSim Digital Logic` on `:99`.
  - LAW_2 + LAW_1: Twin `"Preferences"` modals (`Ctrl+P`) and single-key circuit/tab hotkeys
    (`1..9`, `0`, `-`, `=`, `Space`, `Ctrl+B`) collide across `:99`.
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
import sqlite3
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.rb_osw2_synth_v2.common import (
    advisory_lock,
    boot_isolated_studio_scripts,
    boot_singleton_cdp_chromium,
    build_grade_payload,
    cdp_eval_js,
    cdp_list_targets,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    render_scanned_document_png,
    set_x11_clipboard,
    stage_private_studio_script,
    write_json,
)

TASK_ID = "RBS2-05"
PORTAL_PORT = 19405
GRADEBOOK_PORT = 19415

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Meridian LoanHub 16-Packet Underwriting vs. GateSim 12-Circuit Waveform Oscilloscope TA Bench",
    "domain": "Mortgage Credit/Title/FEMA Underwriting & Digital Logic Timing Waveform Grading",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("mortgage_underwriter", "digital_logic_ta"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (GRADEBOOK_PORT,),
    "open_gui_docs": (),
    "conc_role_timeout_s": 1680,
    "iso_role_timeout_s": 1680,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "high_granularity_visual_recreation",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.96,
        "role_a": {
            "slug": "mortgage_underwriter",
            "est_role_seconds": 550.0,
            "traits": [
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "twin_named_modals",
                "modal_file_or_rule_dialog",
                "atspi_click_plus_global_hotkeys",
            ],
        },
        "role_b": {
            "slug": "digital_logic_ta",
            "est_role_seconds": 570.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "singleton_cdp_browser",
                "viewport_resize_vs_fullscreen_capture",
                "twin_named_modals",
                "iterative_keyboard_shortcuts",
            ],
        },
    },
}

# 16 borrower packets:
# (loan_id, borrower, gross_mo_inc, piti, other_debt, principal, appraised, fico, escrow_mo, title_status, fema_zone)
LOAN_PACKETS: list[tuple[str, str, float, float, float, int, int, int, int, str, str]] = [
    ("LN-101", "A. Morales",  10000.0, 2600.0,  900.0, 360000, 480000, 762, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-102", "B. Kowalski",  9000.0, 2500.0, 1010.0, 320000, 400000, 715,  6, "SENIOR_TAX_LIEN", "ZONE_X"),
    ("LN-103", "C. Takahashi",12000.0, 3600.0, 1680.0, 450000, 600000, 755, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-104", "D. Osei",     10000.0, 3100.0, 1320.0, 380000, 440000, 760, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-105", "E. Lindholm", 11000.0, 2800.0, 1160.0, 396000, 520000, 734,  6, "UNENCUMBERED",    "ZONE_AE"),
    ("LN-106", "F. Narayanan",12500.0, 3200.0, 1300.0, 440000, 550000, 748, 14, "UNENCUMBERED",    "ZONE_AE"),
    ("LN-107", "G. Vance",     8500.0, 2700.0, 1295.0, 290000, 380000, 780, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-108", "H. Al-Mansoor",14000.0,3500.0, 1540.0, 510000, 680000, 790, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-109", "I. Petrov",    9500.0, 2400.0, 1020.0, 330000, 440000, 728,  8, "SENIOR_TAX_LIEN", "ZONE_AE"),
    ("LN-110", "J. Delgado",  10500.0, 3150.0, 1522.5, 360000, 460000, 712, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-111", "K. Sorensen", 13000.0, 3380.0, 1560.0, 470000, 600000, 742,  4, "UNENCUMBERED",    "ZONE_AE"),
    ("LN-112", "L. Chatterjee",15000.0,4500.0, 2175.0, 560000, 700000, 768, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-113", "M. Belanger",  9200.0, 2300.0, 1196.0, 310000, 400000, 705, 12, "UNENCUMBERED",    "ZONE_X"),
    ("LN-114", "N. Okonkwo",  11500.0, 2990.0, 1380.0, 415000, 530000, 751,  9, "UNENCUMBERED",    "ZONE_AE"),
    ("LN-115", "O. Halvorsen",10800.0, 2700.0, 1296.0, 390000, 500000, 739, 12, "SENIOR_TAX_LIEN", "ZONE_X"),
    ("LN-116", "P. Watanabe", 16000.0, 4000.0, 1920.0, 600000, 800000, 802, 18, "UNENCUMBERED",    "ZONE_AE"),
]

UNDERWRITING_SEAL = make_opaque_seal("rbs205_lh", "LOANHUB_16PKT_DTI_FEMA")
JUMBO_RESERVE_MONTHS = 6


def _eval_loan(row: tuple[str, str, float, float, float, int, int, int, int, str, str]) -> dict[str, Any]:
    lid, name, inc, piti, debt, prin, appr, fico, esc, title_st, fema_z = row
    dti = round(100.0 * (piti + debt) / inc, 2)
    ltv = round(100.0 * prin / appr, 2)
    if title_st == "SENIOR_TAX_LIEN":
        dec = "REJECT_TITLE_LIEN"
    elif dti > 45.0 or (dti > 43.0 and not (fico >= 740 and ltv <= 80.0)):
        dec = "REJECT_EXCESS_DTI"
    elif fema_z == "ZONE_AE" and esc < 12:
        dec = "CONDITIONAL_FLOOD_ESCROW"
    else:
        dec = "APPROVE_STANDARD"
    return {
        "loan_id": lid,
        "borrower": name,
        "dti_pct": dti,
        "ltv_pct": ltv,
        "decision": dec,
        "principal_usd": prin,
    }


LOAN_TRUTH = [_eval_loan(r) for r in LOAN_PACKETS]
LOAN_BY_ID = {d["loan_id"]: d for d in LOAN_TRUTH}
TRUE_APPROVED_CNT = sum(1 for d in LOAN_TRUTH if d["decision"] == "APPROVE_STANDARD")          # 7
TRUE_CONDITIONAL_CNT = sum(1 for d in LOAN_TRUTH if d["decision"] == "CONDITIONAL_FLOOD_ESCROW")  # 3
TRUE_REJECTED_CNT = sum(1 for d in LOAN_TRUTH if d["decision"].startswith("REJECT_"))          # 6
TRUE_APPROVED_PRINCIPAL = sum(d["principal_usd"] for d in LOAN_TRUTH if d["decision"] == "APPROVE_STANDARD")

# 12 digital logic circuits: (cir_id, student_handle, module_name, fault_code, score)
CIRCUITS_TRUTH: list[tuple[str, str, str, str, int]] = [
    ("CIR-01", "stu_lin",     "alu4_ripple",   "PASS_CLEAN",            100),
    ("CIR-02", "stu_mehta",   "cla_carry4",    "HAZARD_CARRY_GLITCH",    75),
    ("CIR-03", "stu_kline",   "barrel_mux8",   "MUX_POLARITY_INVERTED",  50),
    ("CIR-04", "stu_sato",    "sync_cntr4",    "PASS_CLEAN",            100),
    ("CIR-05", "stu_bello",   "sr_jk_latch",   "LATCH_RACE_LOCKUP",      25),
    ("CIR-06", "stu_novak",   "alu_sub_ovf",   "HAZARD_CARRY_GLITCH",    75),
    ("CIR-07", "stu_choi",    "fsm_seq_det",   "PASS_CLEAN",            100),
    ("CIR-08", "stu_duarte",  "prio_enc_mux",  "MUX_POLARITY_INVERTED",  50),
    ("CIR-09", "stu_farah",   "dual_edge_ff",  "LATCH_RACE_LOCKUP",      25),
    ("CIR-10", "stu_weber",   "gray_code_cnt", "PASS_CLEAN",            100),
    ("CIR-11", "stu_ibrahim", "fast_add_cin",  "HAZARD_CARRY_GLITCH",    75),
    ("CIR-12", "stu_zhao",    "alu_shift_sel", "MUX_POLARITY_INVERTED",  50),
]
CIR_BY_ID = {cid: (stu, mod, fcode, sc) for cid, stu, mod, fcode, sc in CIRCUITS_TRUTH}
TA_BENCH_SEAL = make_opaque_seal("rbs205_gs", "GATESIM_12CIR_WAVEFORM_TA")
GLITCH_MARGIN_NS = 1.8
TRUE_MEAN_SCORE = round(sum(x[4] for x in CIRCUITS_TRUTH) / len(CIRCUITS_TRUTH), 2)

GATESIM_QT_SOURCE = f"""import json, os, subprocess, sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QShortcut, QVBoxLayout, QWidget
)

CIRS = {repr([(c[0], c[1], c[2], c[3]) for c in CIRCUITS_TRUTH])}
GOLD_BITS = [0, 1, 1, 0, 1, 0, 0, 1]
SEAL_OK = {repr(TA_BENCH_SEAL)}

class ScopeCanvas(QWidget):
    def __init__(self, parent_win):
        super().__init__()
        self.pw = parent_win
        self.setMinimumSize(920, 440)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(12, 18, 30))
        cid, stu, mod, fcode = CIRS[self.pw.idx]
        # Grid for 8 clock cycles T0..T7
        x0, cw = 135, 92
        p.setPen(QPen(QColor(38, 52, 75), 1, Qt.DashLine))
        p.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))
        for t in range(9):
            gx = x0 + t * cw
            p.drawLine(gx, 36, gx, 405)
            if t < 8:
                p.setPen(QColor(148, 163, 184))
                p.drawText(gx + 28, 28, f"T{{t}}")
                p.setPen(QPen(QColor(38, 52, 75), 1, Qt.DashLine))

        labels = [("CLK", 82, QColor(56, 189, 248)), ("IN_BUS", 162, QColor(167, 139, 250)),
                  ("GOLD_REF", 248, QColor(52, 211, 153)), ("STUDENT_OUT", 344, QColor(248, 250, 252))]
        for name, yc, col in labels:
            p.setPen(col)
            p.drawText(14, yc + 5, name)

        # Draw CLK
        p.setPen(QPen(QColor(56, 189, 248), 2))
        for t in range(8):
            gx = x0 + t * cw
            p.drawLine(gx, 96, gx, 64); p.drawLine(gx, 64, gx + cw // 2, 64)
            p.drawLine(gx + cw // 2, 64, gx + cw // 2, 96); p.drawLine(gx + cw // 2, 96, gx + cw, 96)

        # Draw IN_BUS
        p.setPen(QPen(QColor(167, 139, 250), 2))
        in_bits = [1, 0, 1, 1, 0, 1, 0, 0]
        for t, b in enumerate(in_bits):
            gx = x0 + t * cw
            yy = 144 if b else 178
            p.drawLine(gx, yy, gx + cw, yy)
            if t > 0 and in_bits[t - 1] != b:
                p.drawLine(gx, 144, gx, 178)

        # Draw GOLD_REF
        p.setPen(QPen(QColor(52, 211, 153), 3))
        for t, b in enumerate(GOLD_BITS):
            gx = x0 + t * cw
            yy = 228 if b else 268
            p.drawLine(gx, yy, gx + cw, yy)
            if t > 0 and GOLD_BITS[t - 1] != b:
                p.drawLine(gx, 228, gx, 268)

        # Draw STUDENT_OUT purely visually on QPainter canvas (LAW_7: never exposed via AT-SPI text)
        if fcode == "PASS_CLEAN":
            p.setPen(QPen(QColor(16, 185, 129), 4))
            for t, b in enumerate(GOLD_BITS):
                gx = x0 + t * cw
                yy = 324 if b else 366
                p.drawLine(gx, yy, gx + cw, yy)
                if t > 0 and GOLD_BITS[t - 1] != b:
                    p.drawLine(gx, 324, gx, 366)
        elif fcode == "HAZARD_CARRY_GLITCH":
            p.setPen(QPen(QColor(245, 158, 11), 4))
            for t, b in enumerate(GOLD_BITS):
                gx = x0 + t * cw
                yy = 324 if b else 366
                if t in (2, 5):
                    mid = gx + cw // 2
                    opp = 366 if b else 324
                    p.drawLine(gx, yy, mid - 7, yy)
                    p.drawLine(mid - 7, yy, mid, opp)
                    p.drawLine(mid, opp, mid + 7, yy)
                    p.drawLine(mid + 7, yy, gx + cw, yy)
                    p.fillRect(mid - 6, 306, 12, 12, QColor(245, 158, 11))
                else:
                    p.drawLine(gx, yy, gx + cw, yy)
                if t > 0 and GOLD_BITS[t - 1] != b:
                    p.drawLine(gx, 324, gx, 366)
        elif fcode == "MUX_POLARITY_INVERTED":
            inv = [1 - b for b in GOLD_BITS]
            p.setPen(QPen(QColor(217, 70, 239), 4))
            for t, b in enumerate(inv):
                gx = x0 + t * cw
                yy = 324 if b else 366
                p.drawLine(gx, yy, gx + cw, yy)
                if t > 0 and inv[t - 1] != b:
                    p.drawLine(gx, 324, gx, 366)
        else:  # LATCH_RACE_LOCKUP
            p.setPen(QPen(QColor(239, 68, 68), 4))
            for t in range(8):
                gx = x0 + t * cw
                if t < 3:
                    b = GOLD_BITS[t]
                    yy = 324 if b else 366
                    p.drawLine(gx, yy, gx + cw, yy)
                    if t > 0 and GOLD_BITS[t - 1] != b:
                        p.drawLine(gx, 324, gx, 366)
                else:
                    p.drawLine(gx, 320, gx + cw, 320)
                    p.fillRect(gx + 6, 310, cw - 12, 8, QColor(220, 38, 38))

        p.setPen(QColor(148, 163, 184))
        p.drawText(135, 428, "Legend: Emerald match=PASS_CLEAN(100) | Amber mid-cycle spike=HAZARD_CARRY_GLITCH(75) | Magenta inverted=MUX_POLARITY_INVERTED(50) | Red flatline T3..T7=LATCH_RACE_LOCKUP(25)")
        p.end()

class GateSimWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GateSim Digital Logic")
        self.resize(1120, 640)
        self.idx = 0
        self.visited = {{0}}
        self.sweeps = 0
        cw = QWidget(); v = QVBoxLayout(cw)
        self.hdr = QLabel()
        self.hdr.setStyleSheet("font-weight:bold;padding:6px;background:#0f172a;color:#38bdf8;")
        v.addWidget(self.hdr)
        self.cv = ScopeCanvas(self)
        v.addWidget(self.cv)
        row = QHBoxLayout()
        b_prev = QPushButton("&Prev Circuit ([)"); b_prev.clicked.connect(lambda: self.step_cir(-1))
        b_next = QPushButton("&Next Circuit (])"); b_next.clicked.connect(lambda: self.step_cir(1))
        b_swp = QPushButton("Clock &Sweep (Space)"); b_swp.clicked.connect(self.clock_sweep)
        b_prf = QPushButton("&Preferences (Ctrl+P)"); b_prf.clicked.connect(self.open_prefs)
        b_seal = QPushButton("Copy TA &Bench Seal (Ctrl+B)"); b_seal.clicked.connect(self.copy_seal)
        for b in (b_prev, b_next, b_swp, b_prf, b_seal):
            row.addWidget(b)
        v.addLayout(row)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("["), self, activated=lambda: self.step_cir(-1))
        QShortcut(QKeySequence("]"), self, activated=lambda: self.step_cir(1))
        QShortcut(QKeySequence("Space"), self, activated=self.clock_sweep)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.copy_seal)
        for k_i, key_s in enumerate(["1","2","3","4","5","6","7","8","9","0","-","="]):
            QShortcut(QKeySequence(key_s), self, activated=lambda idx=k_i: self.jump_cir(idx))
        self.refresh()

    def jump_cir(self, i):
        self.idx = i % len(CIRS)
        self.visited.add(self.idx)
        self.refresh()

    def step_cir(self, d):
        self.jump_cir((self.idx + d) % len(CIRS))

    def clock_sweep(self):
        self.sweeps += 1
        self.visited.add(self.idx)
        self.refresh()

    def refresh(self):
        cid, stu, mod, _ = CIRS[self.idx]
        self.hdr.setText(f"Active Submission: {{cid}} ({{stu}} / {{mod}}) | Inspected {{len(self.visited)}}/12 | Sweeps={{self.sweeps}}")
        self.cv.update()

    def copy_seal(self):
        tok = SEAL_OK if len(self.visited) >= 12 else "INSPECT_ALL_12_CIRCUITS_FIRST"
        subprocess.run(["xclip", "-selection", "clipboard"], input=tok.encode(), check=False)
        self.hdr.setText(f"Copied TA seal token (visited={{len(self.visited)}}/12)")

    def open_prefs(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        dlg.setModal(True)
        dlg.resize(460, 220)
        dv = QVBoxLayout(dlg)
        tok = SEAL_OK if len(self.visited) >= 12 else "INSPECT_ALL_12_CIRCUITS_FIRST"
        dv.addWidget(QLabel("GateSim Oscilloscope Timing Preferences"))
        dv.addWidget(QLabel("glitch_setup_margin_ns = 1.8"))
        dv.addWidget(QLabel(f"ta_bench_seal = {{tok}}"))
        bc = QPushButton("Close"); bc.clicked.connect(dlg.accept); dv.addWidget(bc)
        dlg.exec_()

app = QApplication(sys.argv)
app.setApplicationName("gatesim-logic")
w = GateSimWin()
w.show()
sys.exit(app.exec_())
"""


def _build_loanhub_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"/><title>Meridian LoanHub</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;}
header{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;}
.bar{padding:10px 18px;background:#e2e8f0;display:flex;gap:10px;align-items:center;}
button{padding:7px 12px;border-radius:5px;border:1px solid #334155;background:#1d4ed8;color:#fff;cursor:pointer;font-weight:600;}
table{border-collapse:collapse;width:96%;margin:14px auto;background:#fff;}
th,td{border:1px solid #cbd5e1;padding:6px 10px;font-size:13px;text-align:left;}
#prefsModal{display:none;position:fixed;left:25%;top:18%;width:480px;background:#fff;border:3px solid #0f172a;padding:18px;z-index:50;box-shadow:0 16px 40px rgba(0,0,0,.35);}
</style></head><body>
<header><strong>Meridian LoanHub — Collateral, Title &amp; FEMA Desk</strong><span id="viewBadge">VIEW=INCOME_DTI</span></header>
<div class="bar">
  <button id="btnIncome" onclick="loadView('INCOME_DTI')">[1] INCOME_DTI</button>
  <button id="btnTitle" onclick="loadView('TITLE_LIEN')">[2] TITLE_LIEN</button>
  <button id="btnFlood" onclick="loadView('FLOOD_ESCROW')">[3] FLOOD_ESCROW</button>
  <button id="btnExport" onclick="exportCsv()">Export Active View CSV (~/Downloads/portal_packet_export.csv)</button>
  <button id="btnPrefs" onclick="openPrefs()">Preferences (Ctrl+P)</button>
  <button id="btnSeal" onclick="copySeal()">Copy Underwriting Seal</button>
</div>
<div id="statusMsg" style="padding:8px 18px;color:#065f46;font-weight:600;">Ready</div>
<table><thead><tr id="thRow"></tr></thead><tbody id="tbBody"></tbody></table>
<div id="prefsModal" role="dialog" aria-label="Preferences">
  <h3>Preferences — Underwriting Policy Parameters</h3>
  <p id="prefReserve">jumbo_reserve_months = 6</p>
  <p id="prefSeal">underwriting_seal = VISIT_TITLE_AND_FLOOD_VIEWS_FIRST</p>
  <button onclick="document.getElementById('prefsModal').style.display='none'">Close</button>
</div>
<script>
let curView = 'INCOME_DTI';
async function loadView(v){
  curView = v;
  document.getElementById('viewBadge').textContent = 'VIEW=' + v;
  const r = await fetch('/api/lh/view?view=' + encodeURIComponent(v));
  const d = await r.json();
  const th = document.getElementById('thRow');
  const tb = document.getElementById('tbBody');
  th.innerHTML = d.columns.map(c=>'<th>'+c+'</th>').join('');
  tb.innerHTML = d.rows.map(rw=>'<tr>'+rw.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('');
  document.getElementById('prefSeal').textContent = 'underwriting_seal = ' + d.seal;
}
async function exportCsv(){
  const r = await fetch('/api/lh/export_csv?view=' + encodeURIComponent(curView), {method:'POST'});
  const d = await r.json();
  document.getElementById('statusMsg').textContent = 'Exported ' + d.path + ' (' + d.view + ')';
}
async function copySeal(){
  const r = await fetch('/api/lh/copy_seal', {method:'POST'});
  const d = await r.json();
  document.getElementById('statusMsg').textContent = 'Clipboard updated: ' + d.seal;
}
function openPrefs(){ document.getElementById('prefsModal').style.display = 'block'; }
window.addEventListener('keydown', e=>{
  if(e.key==='1') loadView('INCOME_DTI');
  if(e.key==='2') loadView('TITLE_LIEN');
  if(e.key==='3') loadView('FLOOD_ESCROW');
  if(e.ctrlKey && e.key.toLowerCase()==='p'){ e.preventDefault(); openPrefs(); }
});
loadView('INCOME_DTI');
</script></body></html>"""


def _build_gradebook_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"/><title>CS240 CourseGradebook</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;}
header{background:#1e1b4b;padding:12px 18px;display:flex;justify-content:space-between;}
.wrap{padding:16px 20px;}
textarea{width:96%;height:240px;background:#1e293b;color:#f8fafc;border:1px solid #475569;font-family:monospace;padding:10px;}
button{padding:8px 14px;background:#059669;color:#fff;border:none;border-radius:5px;font-weight:600;cursor:pointer;margin-right:8px;}
</style></head><body>
<header><strong>CS240 Digital Logic — TA Waveform Gradebook</strong><span id="gbStat">UPLOADED=0/12</span></header>
<div class="wrap">
  <p>Submit JSON mapping or list of 12 graded circuits (<code>cir_id</code>, <code>fault_code</code>, <code>score</code>) inspected in <strong>GateSim Digital Logic</strong>:</p>
  <textarea id="gbInput" placeholder='[{"cir_id":"CIR-01","fault_code":"PASS_CLEAN","score":100}, ...]'></textarea><br/><br/>
  <button id="btnSubmitGrades" onclick="submitGrades()">Post Roster Grades</button>
  <button id="btnExportRoster" onclick="exportRoster()">Export Roster Template (~/Downloads/portal_packet_export.csv)</button>
  <p id="gbMsg">Awaiting TA grade submission.</p>
</div>
<script>
async function submitGrades(){
  let payload = [];
  try { payload = JSON.parse(document.getElementById('gbInput').value); } catch(e){ document.getElementById('gbMsg').textContent = 'Invalid JSON'; return; }
  const r = await fetch('/api/gb/submit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({grades: payload})});
  const d = await r.json();
  document.getElementById('gbStat').textContent = 'UPLOADED=' + d.count + '/12';
  document.getElementById('gbMsg').textContent = 'Saved ' + d.count + ' circuit grades (receipt=' + d.receipt + ')';
}
async function exportRoster(){
  const r = await fetch('/api/gb/export_csv', {method:'POST'});
  const d = await r.json();
  document.getElementById('gbMsg').textContent = 'Exported roster template to ' + d.path;
}
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Mortgage Collateral, Title & FEMA Underwriting Work Order — {b}mortgage_underwriter{b}",
        "",
        "## Scope & Deliverables",
        f"Underwrite all 16 residential mortgage packets (`LN-101` .. `LN-116`) by reconciling {b}/workspace/loanhub/borrower_packets.sqlite{b}, the scanned policy rider {b}/workspace/loanhub/FEMA_DTI_Rider.png{b}, and the live **Meridian LoanHub** session at {b}http://127.0.0.1:{PORTAL_PORT}/{b} in Chromium (`127.0.0.1:9222`).",
        "",
        "Deliverables:",
        f"1. **Underwriting Decisions JSON ({b}/workspace/loanhub/MORTGAGE_DECISIONS.json{b})** with exact keys:",
        f"   - {b}\"packets\"{b}: list of 16 objects sorted by `loan_id` (`LN-101..LN-116`), each containing `loan_id`, `dti_pct` (float, 2 decimals), `ltv_pct` (float, 2 decimals), and `decision` (`APPROVE_STANDARD`, `CONDITIONAL_FLOOD_ESCROW`, `REJECT_TITLE_LIEN`, or `REJECT_EXCESS_DTI`) per the priority rules in `FEMA_DTI_Rider.png` and LoanHub's `INCOME_DTI`, `TITLE_LIEN`, and `FLOOD_ESCROW` views",
        f"   - {b}\"approved_count\"{b} (int), {b}\"conditional_count\"{b} (int), {b}\"rejected_count\"{b} (int)",
        f"   - {b}\"total_approved_principal_usd\"{b} (int: sum of `loan_principal_usd` across `APPROVE_STANDARD` loans only)",
        f"   - {b}\"jumbo_reserve_months\"{b} (int: parameter from LoanHub's `Preferences` dialog)",
        f"   - {b}\"underwriting_seal\"{b} (string `ATTEST-...` copied after inspecting all 3 LoanHub views)",
        f"2. **Underwriting Summary CSV ({b}/workspace/loanhub/underwriting_summary.csv{b})**:",
        "   - Header `loan_id,dti_pct,ltv_pct,decision` followed by all 16 adjudicated rows in `LN-101..LN-116` order.",
        "",
    ])
    role_b = "\n".join([
        f"# Digital Logic Waveform Grading & Gradebook Submission Work Order — {b}digital_logic_ta{b}",
        "",
        "## Scope & Deliverables",
        f"Grade all 12 student sequential/ALU circuit submissions (`CIR-01` .. `CIR-12`) by inspecting their 8-cycle timing waveforms in **GateSim Digital Logic** on the desktop and posting the final roster to **CS240 CourseGradebook** at {b}http://127.0.0.1:{GRADEBOOK_PORT}/{b} in Chromium (`127.0.0.1:9222`).",
        "",
        "Deliverables:",
        f"1. **Waveform Grading Manifest ({b}/workspace/gatesim/GATESIM_GRADES.json{b})** with exact keys:",
        f"   - {b}\"circuits\"{b}: list of 12 objects ordered `CIR-01..CIR-12`, each with `cir_id`, `student`, `module`, `fault_code` (`PASS_CLEAN`, `HAZARD_CARRY_GLITCH`, `MUX_POLARITY_INVERTED`, or `LATCH_RACE_LOCKUP`), and `score` (`100`, `75`, `50`, or `25`)",
        f"   - {b}\"pass_clean_count\"{b} (int), {b}\"glitch_count\"{b} (int), {b}\"inverted_count\"{b} (int), {b}\"lockup_count\"{b} (int)",
        f"   - {b}\"mean_score\"{b} (float, rounded to 2 decimals)",
        f"   - {b}\"glitch_setup_margin_ns\"{b} (float from GateSim's `Preferences` dialog)",
        f"   - {b}\"ta_bench_seal\"{b} (string `ATTEST-...` unlocked in GateSim after inspecting all 12 circuits)",
        f"2. **Gradebook CSV & Live Portal Upload ({b}/workspace/gatesim/gradebook_upload.csv{b})**:",
        f"   - Write `cir_id,student,module,fault_code,score` for `CIR-01..CIR-12` to `gradebook_upload.csv` AND post all 12 circuit grades to {b}http://127.0.0.1:{GRADEBOOK_PORT}/{b}.",
        "",
    ])
    return {"mortgage_underwriter": role_a, "digital_logic_ta": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    lh_dir = ws / "loanhub"
    gs_dir = ws / "gatesim"
    lh_dir.mkdir(parents=True, exist_ok=True)
    gs_dir.mkdir(parents=True, exist_ok=True)

    db_p = lh_dir / "borrower_packets.sqlite"
    if db_p.exists():
        db_p.unlink()
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute(
            "CREATE TABLE loans (loan_id TEXT PRIMARY KEY, borrower_name TEXT, gross_monthly_income REAL, "
            "monthly_housing_piti REAL, monthly_other_debt REAL, loan_principal_usd INTEGER, "
            "appraised_value_usd INTEGER, credit_score INTEGER, flood_escrow_months INTEGER)"
        )
        for r in LOAN_PACKETS:
            conn.execute("INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?)", r[:9])
        conn.commit()

    render_scanned_document_png(
        lh_dir / "FEMA_DTI_Rider.png",
        "MERIDIAN CREDIT POLICY RIDER — DTI, TITLE LIEN & FEMA ESCROW MATRIX",
        [
            "1. Formulas: dti_pct = 100 * (monthly_housing_piti + monthly_other_debt) / gross_monthly_income",
            "             ltv_pct = 100 * loan_principal_usd / appraised_value_usd (round both to 2 decimals).",
            "2. Priority Rule A (Title): If LoanHub TITLE_LIEN view shows SENIOR_TAX_LIEN -> REJECT_TITLE_LIEN.",
            "3. Priority Rule B (DTI Cap): Standard back-end cap is dti_pct <= 43.00%.",
            "   Compensating exception permits 43.00% < dti_pct <= 45.00% ONLY when credit_score >= 740 AND ltv_pct <= 80.00%.",
            "   Any packet exceeding applicable DTI cap -> REJECT_EXCESS_DTI.",
            "4. Priority Rule C (Flood): Remaining packets in FEMA ZONE_AE (from LoanHub FLOOD_ESCROW view)",
            "   with flood_escrow_months < 12 -> CONDITIONAL_FLOOD_ESCROW.",
            "5. Priority Rule D: All other packets -> APPROVE_STANDARD.",
        ],
        stamp_text="UNDERWRITING POLICY RIDER 2026-Q4",
    )

    roster_stub = [{"cir_id": c[0], "student": c[1], "module": c[2]} for c in CIRCUITS_TRUTH]
    write_json(gs_dir / "student_roster.json", {"course": "CS240", "submissions": roster_stub})

    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_tok = secrets.token_hex(16)
    lh_cookie = secrets.token_hex(18)
    gb_cookie = secrets.token_hex(18)
    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    write_json(
        state_p,
        {
            "task_id": TASK_ID,
            "contention_events": 0,
            "lh_views_seen": [],
            "gb_grades": {},
        },
    )
    lh_html = _build_loanhub_html().encode("utf-8")
    gb_html = _build_gradebook_html().encode("utf-8")
    dl_csv = Path("/home/user/Downloads/portal_packet_export.csv")

    def _has_cookie(hdrs: Any, cname: str, expected: str) -> bool:
        c = SimpleCookie()
        try:
            c.load(hdrs.get("Cookie") or "")
            m = c.get(cname)
            return bool(m and m.value == expected)
        except Exception:
            return False

    def _view_payload(view: str) -> tuple[list[str], list[list[Any]]]:
        if view == "TITLE_LIEN":
            return ["loan_id", "borrower", "title_status"], [[r[0], r[1], r[9]] for r in LOAN_PACKETS]
        if view == "FLOOD_ESCROW":
            return ["loan_id", "borrower", "fema_zone", "escrow_months_on_file"], [[r[0], r[1], r[10], r[8]] for r in LOAN_PACKETS]
        return ["loan_id", "borrower", "gross_monthly_income", "piti_plus_debt", "credit_score"], [
            [r[0], r[1], r[2], round(r[3] + r[4], 2), r[7]] for r in LOAN_PACKETS
        ]

    class LhHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302)
                self.send_header("Set-Cookie", f"lh_sid={lh_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not _has_cookie(self.headers, "lh_sid", lh_cookie):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium LoanHub session"); return
            if parsed.path == "/api/lh/view":
                vw = (qs.get("view") or ["INCOME_DTI"])[0]
                if vw not in ("INCOME_DTI", "TITLE_LIEN", "FLOOD_ESCROW"):
                    vw = "INCOME_DTI"
                cols, rows = _view_payload(vw)
                with lock:
                    st = read_json_safe(state_p)
                    seen = set(st.get("lh_views_seen") or [])
                    seen.add(vw)
                    st["lh_views_seen"] = sorted(seen)
                    write_json(state_p, st)
                    ready = {"INCOME_DTI", "TITLE_LIEN", "FLOOD_ESCROW"}.issubset(seen)
                seal_val = UNDERWRITING_SEAL if ready else "VISIT_ALL_3_VIEWS_FIRST"
                raw = json.dumps({"view": vw, "columns": cols, "rows": rows, "seal": seal_val}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(lh_html))); self.end_headers(); self.wfile.write(lh_html)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not _has_cookie(self.headers, "lh_sid", lh_cookie):
                self.send_response(401); self.end_headers(); return
            qs = parse_qs(parsed.query)
            if parsed.path == "/api/lh/export_csv":
                vw = (qs.get("view") or ["INCOME_DTI"])[0]
                cols, rows = _view_payload(vw)
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(cols)
                w.writerows(rows)
                dl_csv.parent.mkdir(parents=True, exist_ok=True)
                dl_csv.write_text(buf.getvalue(), encoding="utf-8")
                os.chmod(dl_csv, 0o666)
                raw = json.dumps({"ok": True, "view": vw, "path": str(dl_csv)}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
                return
            if parsed.path == "/api/lh/copy_seal":
                with lock:
                    st = read_json_safe(state_p)
                    ready = {"INCOME_DTI", "TITLE_LIEN", "FLOOD_ESCROW"}.issubset(set(st.get("lh_views_seen") or []))
                seal_val = UNDERWRITING_SEAL if ready else "VISIT_ALL_3_VIEWS_FIRST"
                set_x11_clipboard(seal_val)
                raw = json.dumps({"ok": True, "seal": seal_val}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
                return
            self.send_response(404); self.end_headers()

    class GbHandler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302)
                self.send_header("Set-Cookie", f"gb_sid={gb_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not _has_cookie(self.headers, "gb_sid", gb_cookie):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium Gradebook session"); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(gb_html))); self.end_headers(); self.wfile.write(gb_html)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not _has_cookie(self.headers, "gb_sid", gb_cookie):
                self.send_response(401); self.end_headers(); return
            if parsed.path == "/api/gb/export_csv":
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(["cir_id", "student", "module", "fault_code", "score"])
                for c in CIRCUITS_TRUTH:
                    w.writerow([c[0], c[1], c[2], "PENDING", 0])
                dl_csv.parent.mkdir(parents=True, exist_ok=True)
                dl_csv.write_text(buf.getvalue(), encoding="utf-8")
                os.chmod(dl_csv, 0o666)
                raw = json.dumps({"ok": True, "path": str(dl_csv)}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
                return
            if parsed.path == "/api/gb/submit":
                ln = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln > 0 else {}
                items = body.get("grades") or []
                gmap: dict[str, dict[str, Any]] = {}
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, dict) and it.get("cir_id"):
                            gmap[str(it["cir_id"])] = {
                                "fault_code": str(it.get("fault_code") or ""),
                                "score": int(it.get("score") or 0),
                            }
                elif isinstance(items, dict):
                    for k, v in items.items():
                        if isinstance(v, dict):
                            gmap[str(k)] = {"fault_code": str(v.get("fault_code") or ""), "score": int(v.get("score") or 0)}
                with lock:
                    st = read_json_safe(state_p)
                    st["gb_grades"] = gmap
                    write_json(state_p, st)
                raw = json.dumps({"ok": True, "count": len(gmap), "receipt": f"GB-POSTED-{len(gmap)}"}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
                return
            self.send_response(404); self.end_headers()

    t_gb = threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", GRADEBOOK_PORT), GbHandler).serve_forever, daemon=True)
    t_gb.start()
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(
        json.dumps(
            {
                "urls": [
                    f"http://127.0.0.1:{port}/?sso_boot={boot_tok}",
                    f"http://127.0.0.1:{GRADEBOOK_PORT}/?sso_boot={boot_tok}",
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ThreadingHTTPServer(("127.0.0.1", port), LhHandler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    stage_private_studio_script(state_dir, "gatesim_ref.py", GATESIM_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["gatesim_ref.py"])
    boot_cfg = read_json_safe(state_dir / "boot_url")
    boot_singleton_cdp_chromium(list(boot_cfg.get("urls") or []), window_size=(1220, 860))


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    lh_dir = ws / "loanhub"
    gs_dir = ws / "gatesim"

    # --- Role A: Mortgage Underwriting (19 subchecks) ---
    m_json = read_json_safe(lh_dir / "MORTGAGE_DECISIONS.json")
    m_csv_p = lh_dir / "underwriting_summary.csv"
    pkts = m_json.get("packets") if isinstance(m_json.get("packets"), list) else []
    pkt_map = {str(p.get("loan_id")): p for p in pkts if isinstance(p, dict) and p.get("loan_id")}

    dec_hits = sum(1 for lid, tr in LOAN_BY_ID.items() if str((pkt_map.get(lid) or {}).get("decision")) == tr["decision"])
    dti_hits = sum(
        1
        for lid, tr in LOAN_BY_ID.items()
        if isinstance((pkt_map.get(lid) or {}).get("dti_pct"), (int, float))
        and abs(float(pkt_map[lid]["dti_pct"]) - tr["dti_pct"]) <= 0.08
    )
    ltv_hits = sum(
        1
        for lid, tr in LOAN_BY_ID.items()
        if isinstance((pkt_map.get(lid) or {}).get("ltv_pct"), (int, float))
        and abs(float(pkt_map[lid]["ltv_pct"]) - tr["ltv_pct"]) <= 0.08
    )
    lien_ok = all(str((pkt_map.get(lid) or {}).get("decision")) == "REJECT_TITLE_LIEN" for lid in ("LN-102", "LN-109", "LN-115"))
    flood_ok = all(str((pkt_map.get(lid) or {}).get("decision")) == "CONDITIONAL_FLOOD_ESCROW" for lid in ("LN-105", "LN-111", "LN-114"))
    comp_ok = (
        str((pkt_map.get("LN-103") or {}).get("decision")) == "APPROVE_STANDARD"
        and str((pkt_map.get("LN-112") or {}).get("decision")) == "APPROVE_STANDARD"
        and str((pkt_map.get("LN-104") or {}).get("decision")) == "REJECT_EXCESS_DTI"
        and str((pkt_map.get("LN-110") or {}).get("decision")) == "REJECT_EXCESS_DTI"
    )
    csv_rows = 0
    csv_match = 0
    if m_csv_p.is_file():
        for row in csv.DictReader(m_csv_p.read_text(encoding="utf-8", errors="replace").splitlines()):
            lid = (row.get("loan_id") or "").strip()
            if lid in LOAN_BY_ID:
                csv_rows += 1
                if (row.get("decision") or "").strip() == LOAN_BY_ID[lid]["decision"]:
                    csv_match += 1
    views_seen = set(service_state.get("lh_views_seen") or [])

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_exists", (lh_dir / "MORTGAGE_DECISIONS.json").is_file(), 0.04, "Missing MORTGAGE_DECISIONS.json"),
        ("a_csv_exists", m_csv_p.is_file(), 0.04, "Missing underwriting_summary.csv"),
        ("a_portal_views", {"INCOME_DTI", "TITLE_LIEN", "FLOOD_ESCROW"}.issubset(views_seen), 0.06, f"LoanHub views visited: {sorted(views_seen)}"),
        ("a_dec_half8", dec_hits >= 8, 0.06, f"Loan decisions {dec_hits}/16 < 8"),
        ("a_dec_12", dec_hits >= 12, 0.06, f"Loan decisions {dec_hits}/16 < 12"),
        ("a_dec_all16", dec_hits == 16, 0.08, f"Loan decisions {dec_hits}/16 != 16"),
        ("a_dti_14", dti_hits >= 14, 0.05, f"DTI values accurate {dti_hits}/16"),
        ("a_dti_16", dti_hits == 16, 0.05, f"DTI values accurate {dti_hits}/16 != 16"),
        ("a_ltv_16", ltv_hits == 16, 0.05, f"LTV values accurate {ltv_hits}/16 != 16"),
        ("a_title_lien_3", lien_ok, 0.06, "SENIOR_TAX_LIEN packets (LN-102/109/115) not REJECT_TITLE_LIEN"),
        ("a_flood_ae_3", flood_ok, 0.06, "ZONE_AE <12m escrow packets (LN-105/111/114) not CONDITIONAL_FLOOD_ESCROW"),
        ("a_compensating_fico_ltv", comp_ok, 0.07, "43-45% DTI compensating FICO>=740 & LTV<=80 rule misapplied"),
        ("a_approved_cnt", m_json.get("approved_count") == TRUE_APPROVED_CNT, 0.05, f"approved_count != {TRUE_APPROVED_CNT}"),
        ("a_conditional_cnt", m_json.get("conditional_count") == TRUE_CONDITIONAL_CNT, 0.04, f"conditional_count != {TRUE_CONDITIONAL_CNT}"),
        ("a_rejected_cnt", m_json.get("rejected_count") == TRUE_REJECTED_CNT, 0.04, f"rejected_count != {TRUE_REJECTED_CNT}"),
        ("a_approved_principal", m_json.get("total_approved_principal_usd") == TRUE_APPROVED_PRINCIPAL, 0.06, f"total_approved_principal_usd != {TRUE_APPROVED_PRINCIPAL}"),
        ("a_jumbo_months", m_json.get("jumbo_reserve_months") == JUMBO_RESERVE_MONTHS, 0.04, "jumbo_reserve_months != 6"),
        ("a_seal_exact", m_json.get("underwriting_seal") == UNDERWRITING_SEAL, 0.05, "underwriting_seal mismatch"),
        ("a_csv_16_match", csv_rows == 16 and csv_match == 16, 0.04, f"CSV rows={csv_rows}, matches={csv_match}/16"),
    ]

    # --- Role B: GateSim Waveform TA Bench (19 subchecks) ---
    g_json = read_json_safe(gs_dir / "GATESIM_GRADES.json")
    g_csv_p = gs_dir / "gradebook_upload.csv"
    c_list = g_json.get("circuits") if isinstance(g_json.get("circuits"), list) else []
    c_map = {str(c.get("cir_id")): c for c in c_list if isinstance(c, dict) and c.get("cir_id")}

    fault_hits = sum(1 for cid, tr in CIR_BY_ID.items() if str((c_map.get(cid) or {}).get("fault_code")) == tr[2])
    score_hits = sum(1 for cid, tr in CIR_BY_ID.items() if (c_map.get(cid) or {}).get("score") == tr[3])
    clean_ok = all(str((c_map.get(cid) or {}).get("fault_code")) == "PASS_CLEAN" for cid in ("CIR-01", "CIR-04", "CIR-07", "CIR-10"))
    glitch_ok = all(str((c_map.get(cid) or {}).get("fault_code")) == "HAZARD_CARRY_GLITCH" for cid in ("CIR-02", "CIR-06", "CIR-11"))
    inv_ok = all(str((c_map.get(cid) or {}).get("fault_code")) == "MUX_POLARITY_INVERTED" for cid in ("CIR-03", "CIR-08", "CIR-12"))
    lock_ok = all(str((c_map.get(cid) or {}).get("fault_code")) == "LATCH_RACE_LOCKUP" for cid in ("CIR-05", "CIR-09"))

    gb_posted = service_state.get("gb_grades") or {}
    gb_hits = sum(
        1
        for cid, tr in CIR_BY_ID.items()
        if str((gb_posted.get(cid) or {}).get("fault_code")) == tr[2]
        and int((gb_posted.get(cid) or {}).get("score") or -1) == tr[3]
    )
    g_csv_hits = 0
    if g_csv_p.is_file():
        for row in csv.DictReader(g_csv_p.read_text(encoding="utf-8", errors="replace").splitlines()):
            cid = (row.get("cir_id") or "").strip()
            if cid in CIR_BY_ID and (row.get("fault_code") or "").strip() == CIR_BY_ID[cid][2]:
                g_csv_hits += 1

    mean_val = g_json.get("mean_score")
    margin_val = g_json.get("glitch_setup_margin_ns")

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_exists", (gs_dir / "GATESIM_GRADES.json").is_file(), 0.04, "Missing GATESIM_GRADES.json"),
        ("b_csv_exists", g_csv_p.is_file(), 0.04, "Missing gradebook_upload.csv"),
        ("b_fault_half6", fault_hits >= 6, 0.06, f"Waveform fault_code {fault_hits}/12 < 6"),
        ("b_fault_9", fault_hits >= 9, 0.06, f"Waveform fault_code {fault_hits}/12 < 9"),
        ("b_fault_all12", fault_hits == 12, 0.08, f"Waveform fault_code {fault_hits}/12 != 12"),
        ("b_scores_all12", score_hits == 12, 0.06, f"Circuit numeric scores {score_hits}/12 != 12"),
        ("b_clean_4", clean_ok, 0.05, "PASS_CLEAN circuits (CIR-01/04/07/10) misclassified"),
        ("b_glitch_3", glitch_ok, 0.06, "HAZARD_CARRY_GLITCH circuits (CIR-02/06/11) misclassified"),
        ("b_inverted_3", inv_ok, 0.06, "MUX_POLARITY_INVERTED circuits (CIR-03/08/12) misclassified"),
        ("b_lockup_2", lock_ok, 0.05, "LATCH_RACE_LOCKUP circuits (CIR-05/09) misclassified"),
        ("b_counts_summary", g_json.get("pass_clean_count") == 4 and g_json.get("glitch_count") == 3 and g_json.get("inverted_count") == 3 and g_json.get("lockup_count") == 2, 0.06, "Fault summary counts != 4/3/3/2"),
        ("b_mean_score", isinstance(mean_val, (int, float)) and abs(float(mean_val) - TRUE_MEAN_SCORE) <= 0.08, 0.05, f"mean_score != {TRUE_MEAN_SCORE}"),
        ("b_margin_1p8", isinstance(margin_val, (int, float)) and abs(float(margin_val) - GLITCH_MARGIN_NS) <= 0.05, 0.05, "glitch_setup_margin_ns != 1.8"),
        ("b_seal_exact", g_json.get("ta_bench_seal") == TA_BENCH_SEAL, 0.06, "ta_bench_seal mismatch"),
        ("b_gb_posted_6", gb_hits >= 6, 0.05, f"CourseGradebook live upload {gb_hits}/12 < 6"),
        ("b_gb_posted_12", gb_hits == 12, 0.07, f"CourseGradebook live upload {gb_hits}/12 != 12"),
        ("b_csv_half6", g_csv_hits >= 6, 0.04, f"gradebook_upload.csv matches {g_csv_hits}/12 < 6"),
        ("b_csv_all12", g_csv_hits == 12, 0.06, f"gradebook_upload.csv matches {g_csv_hits}/12 != 12"),
        ("b_student_names", sum(1 for cid, tr in CIR_BY_ID.items() if str((c_map.get(cid) or {}).get("student")) == tr[0]) == 12, 0.00 + 0.00 or 0.04, "Student handles missing in circuits list"),
    ]
    # Normalize checks_b last two weights cleanly to 1.00 total:
    checks_b[-2] = ("b_csv_all12", g_csv_hits == 12, 0.04, f"gradebook_upload.csv matches {g_csv_hits}/12 != 12")
    checks_b[-1] = ("b_student_names", sum(1 for cid, tr in CIR_BY_ID.items() if str((c_map.get(cid) or {}).get("student")) == tr[0]) == 12, 0.02, "Student handles missing in circuits list")

    # --- Joint preservation checks (2 subchecks -> total 40 subchecks) ---
    db_intact = False
    db_p = lh_dir / "borrower_packets.sqlite"
    if db_p.is_file():
        try:
            with sqlite3.connect(str(db_p)) as conn:
                cnt = conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
                db_intact = int(cnt) == 16
        except Exception:
            db_intact = False
    no_seal_swap = (m_json.get("underwriting_seal") != TA_BENCH_SEAL) and (g_json.get("ta_bench_seal") != UNDERWRITING_SEAL)

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_loans_sqlite_intact", db_intact, 0.06, "borrower_packets.sqlite corrupted or missing rows"),
        ("j_no_cross_role_seal_swap", no_seal_swap, 0.06, "X11 clipboard seal swapped across LoanHub and GateSim"),
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
    assert role in ("mortgage_underwriter", "digital_logic_ta")
    ws = next(iter(workspace_map.values()))

    def _work() -> None:
        if role == "mortgage_underwriter":
            targets = cdp_list_targets(9222)
            t_lh = next(t for t in targets if str(port) in t.get("url", ""))
            ws_url = t_lh["webSocketDebuggerUrl"]
            for vw in ("INCOME_DTI", "TITLE_LIEN", "FLOOD_ESCROW"):
                cdp_eval_js(ws_url, f"loadView('{vw}').then(()=>true);")
            cdp_eval_js(ws_url, "copySeal().then(()=>true);")
            seal = get_x11_clipboard()
            lh_dir = ws / "loanhub"
            pkts = [
                {"loan_id": d["loan_id"], "dti_pct": d["dti_pct"], "ltv_pct": d["ltv_pct"], "decision": d["decision"]}
                for d in LOAN_TRUTH
            ]
            write_json(
                lh_dir / "MORTGAGE_DECISIONS.json",
                {
                    "packets": pkts,
                    "approved_count": TRUE_APPROVED_CNT,
                    "conditional_count": TRUE_CONDITIONAL_CNT,
                    "rejected_count": TRUE_REJECTED_CNT,
                    "total_approved_principal_usd": TRUE_APPROVED_PRINCIPAL,
                    "jumbo_reserve_months": JUMBO_RESERVE_MONTHS,
                    "underwriting_seal": seal,
                },
            )
            buf = io.StringIO()
            cw = csv.writer(buf)
            cw.writerow(["loan_id", "dti_pct", "ltv_pct", "decision"])
            for d in LOAN_TRUTH:
                cw.writerow([d["loan_id"], d["dti_pct"], d["ltv_pct"], d["decision"]])
            (lh_dir / "underwriting_summary.csv").write_text(buf.getvalue(), encoding="utf-8")
        else:
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'GateSim Digital Logic' | tail -n 1); "
                "wmctrl -i -r \"$wid\" -e 0,720,50,1120,640; "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.25; "
                "for k in 1 2 3 4 5 6 7 8 9 0 minus equal; do "
                "  xdotool key --clearmodifiers \"$k\"; sleep 0.06; "
                "done; "
                "xdotool key --clearmodifiers ctrl+b; sleep 0.25"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=20)
            seal = get_x11_clipboard()
            gs_dir = ws / "gatesim"
            c_out = [
                {"cir_id": c[0], "student": c[1], "module": c[2], "fault_code": c[3], "score": c[4]}
                for c in CIRCUITS_TRUTH
            ]
            write_json(
                gs_dir / "GATESIM_GRADES.json",
                {
                    "circuits": c_out,
                    "pass_clean_count": 4,
                    "glitch_count": 3,
                    "inverted_count": 3,
                    "lockup_count": 2,
                    "mean_score": TRUE_MEAN_SCORE,
                    "glitch_setup_margin_ns": GLITCH_MARGIN_NS,
                    "ta_bench_seal": seal,
                },
            )
            buf = io.StringIO()
            cw = csv.writer(buf)
            cw.writerow(["cir_id", "student", "module", "fault_code", "score"])
            for c in CIRCUITS_TRUTH:
                cw.writerow(list(c))
            (gs_dir / "gradebook_upload.csv").write_text(buf.getvalue(), encoding="utf-8")

            targets = cdp_list_targets(9222)
            t_gb = next(t for t in targets if str(GRADEBOOK_PORT) in t.get("url", ""))
            payload_js = json.dumps(c_out)
            cdp_eval_js(
                t_gb["webSocketDebuggerUrl"],
                f"fetch('/api/gb/submit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{grades:{payload_js}}})}}).then(r=>r.json());",
            )

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_1 + LAW_4 + Clipboard Race): GateSim hotkeys 1..3 misroute to LoanHub & swap clipboard seal."""
    solve_role("mortgage_underwriter", workspace_map, port, careful_conc=False)
    solve_role("digital_logic_ta", workspace_map, port, careful_conc=False)
    ws = next(iter(workspace_map.values()))
    bad_lh = read_json_safe(ws / "loanhub" / "MORTGAGE_DECISIONS.json")
    bad_lh["underwriting_seal"] = TA_BENCH_SEAL
    write_json(ws / "loanhub" / "MORTGAGE_DECISIONS.json", bad_lh)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 4
    write_json(sp, st)
