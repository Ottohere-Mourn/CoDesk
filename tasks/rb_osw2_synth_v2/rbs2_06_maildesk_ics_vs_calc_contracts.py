"""RBS2-06: MailDesk Blackout Heatmap & RFC-5545 Defense Calendar vs. LibreOffice Calc SLA Contracts.

Grounded in OSWorld-V2 (OSW2-P14 Thunderbird/Calendar `.ics` + LibreOffice Contract Macro/Calc)
& RecreationBench (LAW_6 + LAW_7 + LAW_2 + LAW_1):
  - LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI: Live PyQt5 `MailDesk Client` renders a 3x5 Room
    Occupancy & Maintenance Blackout Heatmap purely via QPainter (revealing 3 red blackout
    cells `(HALL_A, 11:00)`, `(HALL_B, 15:00)`, `(SEM_C, 09:00)` absent from SQLite & AT-SPI).
  - LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN: Single open `LibreOffice Calc` holds
    `/workspace/contracts/Contract_Schedule.xlsx` with unsaved desk control tag `CONTRACT-DESK-906`
    in `Vendor_SLAs!C1` alongside shared `/workspace/maildesk/maildesk.sqlite`.
  - LAW_2 + LAW_1: Twin `"Preferences"` modals (`Ctrl+P`), single-slot X11 `CLIPBOARD` seals,
    and folder/view hotkeys (`1`, `2`, `Ctrl+B`) collide on shared `:99`.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
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

TASK_ID = "RBS2-06"
PORTAL_PORT = 19406
CALC_DESK_TAG = "CONTRACT-DESK-906"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "MailDesk Visual Blackout Heatmap & RFC-5545 .ics Scheduling vs. LibreOffice Calc SLA Contracts",
    "domain": "Academic Committee Calendar Scheduling (.ics/SQLite) & Vendor SLA ContractSpreadsheet Automation",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN",
        "LAW_7_VISUAL_CANVAS_OPAQUE_TO_ATSPI",
        "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP",
        "LAW_1_KEYSTROKE_MISROUTING",
    ),
    "roles": ("defense_scheduler", "contract_automation_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/contracts/Contract_Schedule.xlsx", CALC_DESK_TAG, "calc"),
    ),
    "conc_role_timeout_s": 1680,
    "iso_role_timeout_s": 1680,
    "max_cua_calls": 65,
    "factory_blueprint": {
        "horizon_band": "high_granularity_visual_recreation",
        "total_subchecks": 40,
        "cli_bypass_resistance": 0.95,
        "role_a": {
            "slug": "defense_scheduler",
            "est_role_seconds": 560.0,
            "traits": [
                "atspi_opaque_visual_canvas",
                "multi_step_interactive_state_machine",
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "twin_named_modals",
            ],
        },
        "role_b": {
            "slug": "contract_automation_eng",
            "est_role_seconds": 550.0,
            "traits": [
                "single_instance_mdi_or_soffice",
                "shared_db_or_dirty_gui_buffer",
                "twin_named_modals",
                "atspi_click_plus_global_hotkeys",
            ],
        },
    },
}

ROOMS_SPEC = {
    "HALL_A": {"capacity": 45, "rate_usd": 450},
    "HALL_B": {"capacity": 28, "rate_usd": 280},
    "SEM_C": {"capacity": 16, "rate_usd": 150},
}
TIME_SLOTS = ["09:00", "11:00", "13:00", "15:00", "17:00"]
SLOT_DT_MAP = {
    "09:00": ("20261204T090000", "20261204T104500"),
    "11:00": ("20261204T110000", "20261204T124500"),
    "13:00": ("20261204T130000", "20261204T144500"),
    "15:00": ("20261204T150000", "20261204T164500"),
    "17:00": ("20261204T170000", "20261204T184500"),
}
BLACKOUT_CELLS = {("HALL_A", "11:00"), ("HALL_B", "15:00"), ("SEM_C", "09:00")}

# 12 defense threads: (def_id, candidate, chair_prof, attendees, avail_csv, true_room, true_slot)
DEFENSE_TRUTH: list[tuple[str, str, str, int, str, str, str]] = [
    ("DEF-01", "Lin_Thesis",     "Prof_Kaur",  38, "09:00,11:00", "HALL_A", "09:00"),
    ("DEF-02", "Patel_Thesis",   "Prof_Silva", 34, "11:00,13:00", "HALL_A", "13:00"),
    ("DEF-03", "Gomez_Thesis",   "Prof_Chen",  41, "13:00,15:00", "HALL_A", "15:00"),
    ("DEF-04", "Muller_Thesis",  "Prof_Vance", 36, "15:00,17:00", "HALL_A", "17:00"),
    ("DEF-05", "Okafor_Thesis",  "Prof_Silva", 24, "09:00,15:00", "HALL_B", "09:00"),
    ("DEF-06", "Sato_Thesis",    "Prof_Kaur",  22, "11:00,15:00", "HALL_B", "11:00"),
    ("DEF-07", "Novak_Thesis",   "Prof_Vance", 25, "11:00,13:00", "HALL_B", "13:00"),
    ("DEF-08", "Haddad_Thesis",  "Prof_Chen",  21, "13:00,17:00", "HALL_B", "17:00"),
    ("DEF-09", "Kim_Thesis",     "Prof_Chen",  14, "09:00,11:00", "SEM_C",  "11:00"),
    ("DEF-10", "Rossi_Thesis",   "Prof_Kaur",  12, "09:00,13:00", "SEM_C",  "13:00"),
    ("DEF-11", "Park_Thesis",    "Prof_Silva", 15, "13:00,15:00", "SEM_C",  "15:00"),
    ("DEF-12", "Alvarez_Thesis", "Prof_Kaur",  13, "15:00,17:00", "SEM_C",  "17:00"),
]
DEF_BY_ID = {d[0]: d for d in DEFENSE_TRUTH}
TRUE_ROOM_COST_USD = 3520.0  # 4*450 + 4*280 + 4*150
CALENDAR_ORGANIZER_SEAL = make_opaque_seal("rbs206_cal", "MAILDESK_12DEF_ICS_HEATMAP")

# 10 vendor SLA addenda: (vnd_id, vendor_name, category, base_fee, rush_pct, portal_status, net_sla_usd)
VENDORS_TRUTH: list[tuple[str, str, str, float, float, str, float]] = [
    ("VND-01", "Apex_AV_Rigging",   "AV",       2000.0, 10.0, "ACTIVE_APPROVED",    2200.0),
    ("VND-02", "Beacon_LiveStream", "STREAM",   1800.0,  5.0, "ACTIVE_APPROVED",    1890.0),
    ("VND-03", "Crest_Catering",    "CATERING", 2400.0,  0.0, "ACTIVE_APPROVED",    2400.0),
    ("VND-04", "Delta_TempPower",   "POWER",    3100.0, 15.0, "SUSPENDED_DEBARRED", 3565.0),
    ("VND-05", "Echo_MicArray",     "AV",       1500.0, 10.0, "ACTIVE_APPROVED",    1650.0),
    ("VND-06", "Folio_PrintBind",   "PRINT",    1200.0,  5.0, "ACTIVE_APPROVED",    1260.0),
    ("VND-07", "Granite_Security",  "FACILITY", 1900.0,  0.0, "ACTIVE_APPROVED",    1900.0),
    ("VND-08", "Harbor_Captioning", "ACCESS",   1600.0, 10.0, "ACTIVE_APPROVED",    1760.0),
    ("VND-09", "Ionic_StageLight",  "LIGHTING", 2800.0, 20.0, "SUSPENDED_DEBARRED", 3360.0),
    ("VND-10", "Juno_GownRental",   "REGALIA",  2420.0,  0.0, "ACTIVE_APPROVED",    2420.0),
]
ACTIVE_VENDORS = [v for v in VENDORS_TRUTH if v[5] == "ACTIVE_APPROVED"]
SUSPENDED_IDS = {v[0] for v in VENDORS_TRUTH if v[5] != "ACTIVE_APPROVED"}
TRUE_ACTIVE_SLA_SUM = 15480.0
DEAN_GRANT_USD = 25000.0
PROCUREMENT_SLA_SEAL = make_opaque_seal("rbs206_sla", "PROCUREMENT_8ACTIVE_CALC")

MAILDESK_QT_SOURCE = f"""import sqlite3, subprocess, sys
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QPushButton, QShortcut, QVBoxLayout, QWidget
)

DB_PATH = Path("/workspace/maildesk/maildesk.sqlite")
ROOMS = ["HALL_A", "HALL_B", "SEM_C"]
CAPS = {{"HALL_A": 45, "HALL_B": 28, "SEM_C": 16}}
SLOTS = ["09:00", "11:00", "13:00", "15:00", "17:00"]
BLACKOUTS = {repr(sorted(BLACKOUT_CELLS))}
CAL_SEAL = {repr(CALENDAR_ORGANIZER_SEAL)}

class HeatmapCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(820, 250)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(15, 23, 42))
        p.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))
        p.setPen(QColor(226, 232, 240))
        p.drawText(16, 24, "2026-12-04 Facility Room Matrix (Red X = MAINTENANCE BLACKOUT — unavailable for scheduling)")
        x0, y0, cw, ch = 175, 42, 122, 54
        for ci, sl in enumerate(SLOTS):
            p.setPen(QColor(56, 189, 248))
            p.drawText(x0 + ci * cw + 26, y0 + 16, sl)
        for ri, rm in enumerate(ROOMS):
            yy = y0 + 24 + ri * ch
            p.setPen(QColor(248, 250, 252))
            p.drawText(16, yy + 30, f"{{rm}} (cap {{CAPS[rm]}})")
            for ci, sl in enumerate(SLOTS):
                xx = x0 + ci * cw
                if (rm, sl) in BLACKOUTS:
                    p.fillRect(xx + 4, yy + 4, cw - 8, ch - 8, QColor(185, 28, 28))
                    p.setPen(QPen(QColor(254, 226, 226), 3))
                    p.drawLine(xx + 12, yy + 10, xx + cw - 12, yy + ch - 10)
                    p.drawLine(xx + cw - 12, yy + 10, xx + 12, yy + ch - 10)
                else:
                    p.fillRect(xx + 4, yy + 4, cw - 8, ch - 8, QColor(16, 105, 78))
                    p.setPen(QPen(QColor(52, 211, 153), 1))
                    p.drawRect(xx + 4, yy + 4, cw - 8, ch - 8)
        p.end()

class MailDeskWin(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MailDesk Client")
        self.setGeometry(20, 25, 900, 610)
        self.folder = "DEFENSE"
        cw = QWidget(); v = QVBoxLayout(cw)
        self.hdr = QLabel()
        self.hdr.setStyleSheet("font-weight:bold;padding:6px;background:#1e1b4b;color:#f8fafc;")
        v.addWidget(self.hdr)
        self.lst = QListWidget()
        v.addWidget(self.lst)
        self.hm = HeatmapCanvas()
        v.addWidget(self.hm)
        row = QHBoxLayout()
        b1 = QPushButton("[&1] Defense Threads (12)"); b1.clicked.connect(lambda: self.set_folder("DEFENSE"))
        b2 = QPushButton("[&2] Vendor SLA Addenda (10)"); b2.clicked.connect(lambda: self.set_folder("VENDOR"))
        bp = QPushButton("&Preferences (Ctrl+P)"); bp.clicked.connect(self.open_prefs)
        bs = QPushButton("Copy &Organizer Seal (Ctrl+B)"); bs.clicked.connect(self.copy_seal)
        for b in (b1, b2, bp, bs):
            row.addWidget(b)
        v.addLayout(row)
        self.setCentralWidget(cw)
        QShortcut(QKeySequence("1"), self, activated=lambda: self.set_folder("DEFENSE"))
        QShortcut(QKeySequence("2"), self, activated=lambda: self.set_folder("VENDOR"))
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.open_prefs)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.copy_seal)
        self.refresh()

    def set_folder(self, f):
        self.folder = f
        self.refresh()

    def refresh(self):
        self.lst.clear()
        if DB_PATH.is_file():
            with sqlite3.connect(str(DB_PATH)) as conn:
                if self.folder == "DEFENSE":
                    for r in conn.execute("SELECT def_id, candidate_name, chair_prof, expected_attendees, candidate_avail_slots_csv, status FROM defense_threads ORDER BY def_id"):
                        self.lst.addItem(f"{{r[0]}} | {{r[1]}} | Chair={{r[2]}} | Attend={{r[3]}} | Avail=[{{r[4]}}] | {{r[5]}}")
                else:
                    for r in conn.execute("SELECT vnd_id, vendor_name, category, base_fee_usd, rush_surcharge_pct, curation_status FROM vendor_addenda ORDER BY vnd_id"):
                        self.lst.addItem(f"{{r[0]}} | {{r[1]}} ({{r[2]}}) | Base=${{r[3]}} +{{r[4]}}% | {{r[5]}}")
        self.hdr.setText(f"MailDesk Unified Inbox — Folder={{self.folder}} | Rates: HALL_A=$450/slot, HALL_B=$280/slot, SEM_C=$150/slot")

    def copy_seal(self):
        subprocess.run(["xclip", "-selection", "clipboard"], input=CAL_SEAL.encode(), check=False)
        self.hdr.setText("Copied calendar_organizer_seal to X11 clipboard")

    def open_prefs(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Preferences")
        dlg.setModal(True)
        dlg.resize(470, 220)
        dv = QVBoxLayout(dlg)
        dv.addWidget(QLabel("MailDesk Committee & Room Tariff Preferences"))
        dv.addWidget(QLabel("Room Tariffs: HALL_A=$450/slot (cap 45), HALL_B=$280/slot (cap 28), SEM_C=$150/slot (cap 16)"))
        dv.addWidget(QLabel("Rule: Chair professor cannot chair two defenses in the same time slot."))
        dv.addWidget(QLabel(f"calendar_organizer_seal = {{CAL_SEAL}}"))
        bc = QPushButton("Close"); bc.clicked.connect(dlg.accept); dv.addWidget(bc)
        dlg.exec_()

app = QApplication(sys.argv)
app.setApplicationName("maildesk-client")
w = MailDeskWin()
w.show()
sys.exit(app.exec_())
"""


def _make_vendor_sheet(active_only: bool, desk_tag: str = "") -> list[list[Any]]:
    rows: list[list[Any]] = [["Vnd_ID", "Vendor_Name", "Base_Fee_USD", "Rush_Pct", "Net_SLA_USD", "Notes"]]
    if desk_tag:
        rows[0][2] = desk_tag  # C1 holds live desk control tag CONTRACT-DESK-906!
    src = ACTIVE_VENDORS if active_only else VENDORS_TRUTH[:8]
    for idx, v in enumerate(src, start=2):
        if active_only:
            net_cell: Any = (f"=ROUND(B_FIX,2)", v[6])  # replaced cleanly below
            # Wait: columns: A=Vnd_ID, B=Vendor_Name, C=DeskTag header / Base_Fee_USD, D=Rush_Pct, E=Net_SLA_USD
            net_cell = (f"=ROUND(C{idx}*(1+D{idx}/100),2)", v[6])
            rows.append([v[0], v[1], v[3], v[4], net_cell, "ACTIVE_APPROVED"])
        else:
            rows.append([v[0], v[1], v[3], v[4], 0.0, "UNVERIFIED_DRAFT"])
    return rows


def _make_budget_sheet(
    hall_a: int,
    hall_b: int,
    sem_c: int,
    cal_seal: str,
    active_sla_sum: float,
    contingency_usd: float,
    sla_seal: str,
) -> list[list[Any]]:
    room_cost = round(hall_a * 450.0 + hall_b * 280.0 + sem_c * 150.0, 2)
    tot_commit = round(room_cost + active_sla_sum + contingency_usd, 2)
    util = round(tot_commit / DEAN_GRANT_USD, 4)
    return [
        ["Envelope_Item", "Value", "Specification"],
        ["Hall_A_Booked_Slots", hall_a, "PROVISIONAL_PRE_BLACKOUT_AUDIT" if cal_seal == "PENDING" else "VERIFIED_SCHEDULE"],
        ["Hall_B_Booked_Slots", hall_b, "PROVISIONAL_PRE_BLACKOUT_AUDIT" if cal_seal == "PENDING" else "VERIFIED_SCHEDULE"],
        ["Sem_C_Booked_Slots", sem_c, "PROVISIONAL_PRE_BLACKOUT_AUDIT" if cal_seal == "PENDING" else "VERIFIED_SCHEDULE"],
        ["Total_Defense_Room_Cost_USD", ("=B2*450+B3*280+B4*150", room_cost), "ROOM_TARIFF_FORMULA"],
        ["Calendar_Organizer_Seal", cal_seal, ""],
        ["Total_Active_SLA_USD", ("=SUM(Vendor_SLAs!E2:E9)", active_sla_sum), "8_ACTIVE_VENDORS_SUM"],
        ["AV_Contingency_Reserve_USD", round(contingency_usd, 2), "RANGE_2100_TO_3000"],
        ["Total_Facility_Commitment_USD", ("=B5+B7+B8", tot_commit), "COUPLED_COMMITMENT"],
        ["Approved_Dean_Grant_USD", DEAN_GRANT_USD, "FIXED_GRANT_CAP"],
        ["Grant_Utilization_Ratio", ("=B9/B10", util), "TARGET_0.840_TO_0.885"],
        ["Procurement_SLA_Seal", sla_seal, ""],
    ]


def _build_procurement_html() -> str:
    rows_html = "".join(
        f"<tr><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td><td>${v[3]:.0f}</td><td>{v[4]:.0f}%</td><td><strong>{v[5]}</strong></td></tr>"
        for v in VENDORS_TRUTH
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Procurement Clause Portal</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;}}
header{{background:#0f172a;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{padding:10px 18px;background:#e2e8f0;display:flex;gap:10px;}}
button{{padding:7px 12px;background:#1d4ed8;color:#fff;border:none;border-radius:5px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:95%;margin:12px auto;background:#fff;}}
th,td{{border:1px solid #cbd5e1;padding:6px 10px;font-size:13px;}}
#prefsDlg{{display:none;position:fixed;left:22%;top:18%;width:460px;background:#fff;border:3px solid #0f172a;padding:16px;z-index:40;}}
</style></head><body>
<header><strong>University Procurement Compliance &amp; SLA Registry</strong><span>FY2026-DEC</span></header>
<div class="bar">
  <button onclick="openPrefs()">Preferences (Ctrl+P)</button>
  <button id="btnCopySlaSeal" onclick="copySeal()">Copy Procurement SLA Seal</button>
  <span id="pStat" style="font-weight:600;color:#065f46;align-self:center;">8 Active / 2 Suspended</span>
</div>
<table><thead><tr><th>Vnd_ID</th><th>Vendor</th><th>Category</th><th>Base_Fee</th><th>Rush_Pct</th><th>Compliance_Status</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<div id="prefsDlg" role="dialog" aria-label="Preferences">
  <h3>Preferences — SLA Reserve &amp; Utilization Rules</h3>
  <p>Exclude any vendor marked <code>SUSPENDED_DEBARRED</code>; compute <code>Net_SLA_USD = Base_Fee * (1 + Rush_Pct/100)</code>.</p>
  <p>Size <code>AV_Contingency_Reserve_USD</code> in <code>[2100, 3000]</code> so <code>Grant_Utilization_Ratio</code> lands in <code>[0.840, 0.885]</code>.</p>
  <p>procurement_sla_seal = {PROCUREMENT_SLA_SEAL}</p>
  <button onclick="document.getElementById('prefsDlg').style.display='none'">Close</button>
</div>
<script>
function openPrefs(){{ document.getElementById('prefsDlg').style.display='block'; }}
async function copySeal(){{
  const r = await fetch('/api/proc/copy_seal', {{method:'POST'}});
  const d = await r.json();
  document.getElementById('pStat').textContent = 'Clipboard: ' + d.seal;
}}
window.addEventListener('keydown', e=>{{ if(e.ctrlKey && e.key.toLowerCase()==='p'){{ e.preventDefault(); openPrefs(); }} }});
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    role_a = "\n".join([
        f"# Thesis Defense Calendar (.ics) & Room Tariff Scheduling Work Order — {b}defense_scheduler{b}",
        "",
        "## Scope & Deliverables",
        f"Schedule all 12 thesis defenses (`DEF-01` .. `DEF-12`) on `2026-12-04` using **MailDesk Client** on the desktop and `/workspace/maildesk/maildesk.sqlite`, and update the room-cost section of `/workspace/contracts/Contract_Schedule.xlsx` (currently open in LibreOffice Calc with an active desk tag in `Vendor_SLAs!C1`).",
        "",
        "Deliverables:",
        f"1. **Conflict-Free Schedule in SQLite ({b}/workspace/maildesk/maildesk.sqlite{b})**:",
        "   - Assign each `DEF-01..DEF-12` in `defense_threads` (`assigned_room`, `assigned_slot`, `status='SCHEDULED'`) across rooms `HALL_A` (cap 45, `$450/slot`), `HALL_B` (cap 28, `$280/slot`), and `SEM_C` (cap 16, `$150/slot`) and slots `09:00, 11:00, 13:00, 15:00, 17:00` so that: (a) room capacity `>= expected_attendees`, (b) `assigned_slot` is in `candidate_avail_slots_csv`, (c) none of the 3 red maintenance blackout cells shown on MailDesk's Room Matrix canvas is booked, (d) no `(room, slot)` is double-booked, and (e) no `chair_prof` chairs two defenses in the same time slot.",
        f"2. **RFC-5545 Calendar Export ({b}/workspace/schedule/defense_calendar.ics{b})**:",
        "   - Valid `VCALENDAR` containing 12 `VEVENT` blocks (`UID:DEF-01` .. `UID:DEF-12`, `SUMMARY` including `candidate_name`, `LOCATION` set to `HALL_A`/`HALL_B`/`SEM_C`, and `DTSTART`/`DTEND` on `20261204T090000..20261204T184500`).",
        f"3. **Spreadsheet Room Envelope ({b}/workspace/contracts/Contract_Schedule.xlsx{b})**:",
        "   - Update `Budget_Envelope!B2:B4` with booked slot counts for `HALL_A`, `HALL_B`, and `SEM_C`, preserve formula `=B2*450+B3*280+B4*150` in `B5`, and record `calendar_organizer_seal` (from MailDesk `Preferences` / `Ctrl+B`) in `Budget_Envelope!B6`, preserving all other rows/sheets and `Vendor_SLAs!C1` (`CONTRACT-DESK-906`) with the open Calc window kept in sync.",
        "",
    ])
    role_b = "\n".join([
        f"# Vendor SLA Addendum Curation & Facility Grant Envelope Work Order — {b}contract_automation_eng{b}",
        "",
        "## Scope & Deliverables",
        f"Reconcile the 10 vendor SLA addenda (`VND-01` .. `VND-10`) across `/workspace/maildesk/maildesk.sqlite` and the live **Procurement Clause Portal** at {b}http://127.0.0.1:{PORTAL_PORT}/{b} in Chromium (`127.0.0.1:9222`), and finalize `/workspace/contracts/Contract_Schedule.xlsx` (currently open in LibreOffice Calc with an active desk tag in `Vendor_SLAs!C1`).",
        "",
        "Deliverables:",
        f"1. **SQLite Vendor Curation ({b}/workspace/maildesk/maildesk.sqlite{b})**:",
        "   - Update `vendor_addenda.curation_status` to `INCLUDED_ACTIVE` for `ACTIVE_APPROVED` vendors and `EXCLUDED_SUSPENDED` for `SUSPENDED_DEBARRED` vendors.",
        f"2. **Spreadsheet SLA Table & Grant Sizing ({b}/workspace/contracts/Contract_Schedule.xlsx{b})**:",
        "   - Populate `Vendor_SLAs` rows `2..9` with the 8 active vendors (`Vnd_ID` in `A`, `Vendor_Name` in `B`, `Base_Fee_USD` in `C`, `Rush_Pct` in `D`, and formula `=ROUND(C2*(1+D2/100),2)` .. in `E`), preserving the live desk tag in `Vendor_SLAs!C1`.",
        "   - In `Budget_Envelope`, keep `B7` as `=SUM(Vendor_SLAs!E2:E9)`, size `AV_Contingency_Reserve_USD` (`B8` in `[2100, 3000]`) so `Grant_Utilization_Ratio` (`B11`, formula `=B9/B10` with `B9` `=B5+B7+B8`) lands in `[0.840, 0.885]`, and set `Budget_Envelope!B12` to `procurement_sla_seal` (preserving `Budget_Envelope!B2:B6` and keeping the open Calc window in sync).",
        f"3. **PDF & Contract Manifest ({b}/workspace/contracts/SLA_Summary.pdf{b} & {b}/workspace/contracts/CONTRACT_MANIFEST.json{b})**:",
        "   - Export `SLA_Summary.pdf` from `Contract_Schedule.xlsx` and write `CONTRACT_MANIFEST.json` with keys `active_vendor_ids` (sorted list of 8 IDs), `suspended_vendor_ids` (sorted list of 2 IDs), `total_active_sla_usd` (float), `av_contingency_reserve_usd` (float), and `procurement_sla_seal`.",
        "",
    ])
    return {"defense_scheduler": role_a, "contract_automation_eng": role_b}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws = next(iter(workspace_map.values()))
    md_dir = ws / "maildesk"
    sc_dir = ws / "schedule"
    ct_dir = ws / "contracts"
    for d in (md_dir, sc_dir, ct_dir):
        d.mkdir(parents=True, exist_ok=True)

    db_p = md_dir / "maildesk.sqlite"
    if db_p.exists():
        db_p.unlink()
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute(
            "CREATE TABLE defense_threads (def_id TEXT PRIMARY KEY, candidate_name TEXT, chair_prof TEXT, "
            "expected_attendees INTEGER, candidate_avail_slots_csv TEXT, assigned_room TEXT, assigned_slot TEXT, status TEXT)"
        )
        for d in DEFENSE_TRUTH:
            conn.execute("INSERT INTO defense_threads VALUES (?,?,?,?,?,?,?,?)", (d[0], d[1], d[2], d[3], d[4], "", "", "UNSCHEDULED"))
        conn.execute(
            "CREATE TABLE vendor_addenda (vnd_id TEXT PRIMARY KEY, vendor_name TEXT, category TEXT, "
            "base_fee_usd REAL, rush_surcharge_pct REAL, curation_status TEXT)"
        )
        for v in VENDORS_TRUTH:
            conn.execute("INSERT INTO vendor_addenda VALUES (?,?,?,?,?,?)", (v[0], v[1], v[2], v[3], v[4], "PENDING_REVIEW"))
        conn.commit()

    write_multisheet_xlsx(
        ct_dir / "Contract_Schedule.xlsx",
        [
            ("Vendor_SLAs", _make_vendor_sheet(active_only=False, desk_tag="")),
            ("Budget_Envelope", _make_budget_sheet(5, 5, 2, "PENDING", 0.0, 0.0, "PENDING")),
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
    boot_tok = secrets.token_hex(16)
    proc_cookie = secrets.token_hex(18)
    state_p = state_dir / "service_state.json"
    write_json(state_p, {"task_id": TASK_ID, "contention_events": 0, "proc_seal_copied": False})
    html_bytes = _build_procurement_html().encode("utf-8")
    lock = threading.Lock()

    def _has_cookie(hdrs: Any) -> bool:
        c = SimpleCookie()
        try:
            c.load(hdrs.get("Cookie") or "")
            m = c.get("proc_sid")
            return bool(m and m.value == proc_cookie)
        except Exception:
            return False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_tok:
                self.send_response(302)
                self.send_header("Set-Cookie", f"proc_sid={proc_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not _has_cookie(self.headers):
                self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized: use live Chromium Procurement session"); return
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(html_bytes))); self.end_headers(); self.wfile.write(html_bytes)

        def do_POST(self) -> None:
            if not _has_cookie(self.headers):
                self.send_response(401); self.end_headers(); return
            if urlparse(self.path).path == "/api/proc/copy_seal":
                with lock:
                    st = read_json_safe(state_p)
                    st["proc_seal_copied"] = True
                    write_json(state_p, st)
                set_x11_clipboard(PROCUREMENT_SLA_SEAL)
                raw = json.dumps({"ok": True, "seal": PROCUREMENT_SLA_SEAL}).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(raw)
                return
            self.send_response(404); self.end_headers()

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"urls": [f"http://127.0.0.1:{port}/?sso_boot={boot_tok}"]}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    del workspace_map
    stage_private_studio_script(state_dir, "maildesk_ref.py", MAILDESK_QT_SOURCE)
    boot_isolated_studio_scripts(state_dir, ["maildesk_ref.py"])
    boot_cfg = read_json_safe(state_dir / "boot_url")
    boot_singleton_cdp_chromium(list(boot_cfg.get("urls") or []), window_pos=(25, 500), window_size=(900, 520))


def _parse_ics_events(ics_text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, flags=re.S | re.I):
        ev: dict[str, str] = {}
        for ln in blk.splitlines():
            ln = ln.strip()
            if ":" in ln:
                k, v = ln.split(":", 1)
                ev[k.split(";")[0].upper()] = v.strip()
        events.append(ev)
    return events


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    db_p = ws / "maildesk" / "maildesk.sqlite"
    ics_p = ws / "schedule" / "defense_calendar.ics"
    xp = ws / "contracts" / "Contract_Schedule.xlsx"
    pdf_p = ws / "contracts" / "SLA_Summary.pdf"
    man_p = ws / "contracts" / "CONTRACT_MANIFEST.json"

    def_rows: dict[str, tuple[str, str, str]] = {}
    vnd_rows: dict[str, str] = {}
    if db_p.is_file():
        try:
            with sqlite3.connect(str(db_p)) as conn:
                for did, rm, sl, st in conn.execute("SELECT def_id, assigned_room, assigned_slot, status FROM defense_threads"):
                    def_rows[str(did)] = (str(rm or "").strip(), str(sl or "").strip(), str(st or "").strip())
                for vid, cst in conn.execute("SELECT vnd_id, curation_status FROM vendor_addenda"):
                    vnd_rows[str(vid)] = str(cst or "").strip()
        except Exception:
            pass

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

    # --- Role A: Defense Schedule + RFC-5545 .ics + Room Envelope (18 subchecks) ---
    exact_def = sum(
        1
        for d in DEFENSE_TRUTH
        if def_rows.get(d[0], ("", "", ""))[:2] == (d[5], d[6]) and def_rows.get(d[0], ("", "", ""))[2] == "SCHEDULED"
    )
    assigned_pairs = [(rm, sl) for rm, sl, st in def_rows.values() if rm and sl and st == "SCHEDULED"]
    no_blackout = len(assigned_pairs) >= 10 and not any(p in BLACKOUT_CELLS for p in assigned_pairs)
    no_room_dup = len(assigned_pairs) == 12 and len(set(assigned_pairs)) == 12
    cap_ok = len(assigned_pairs) == 12 and all(
        ROOMS_SPEC.get(def_rows.get(d[0], ("", "", ""))[0], {}).get("capacity", 0) >= d[3]
        for d in DEFENSE_TRUTH
    )
    chair_pairs = [
        (d[2], def_rows.get(d[0], ("", "", ""))[1])
        for d in DEFENSE_TRUTH
        if def_rows.get(d[0], ("", "", ""))[1]
    ]
    no_chair_dup = len(chair_pairs) == 12 and len(set(chair_pairs)) == 12

    ics_txt = ics_p.read_text(encoding="utf-8", errors="replace") if ics_p.is_file() else ""
    evs = _parse_ics_events(ics_txt)
    ics_vcal = "BEGIN:VCALENDAR" in ics_txt.upper() and "END:VCALENDAR" in ics_txt.upper()
    ics_exact = 0
    for ev in evs:
        uid = ev.get("UID", "")
        for d in DEFENSE_TRUTH:
            if d[0] in uid:
                exp_dt0, _ = SLOT_DT_MAP[d[6]]
                if ev.get("LOCATION") == d[5] and exp_dt0 in ev.get("DTSTART", ""):
                    ics_exact += 1
                break

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_db_sched_half6", exact_def >= 6, 0.06, f"SQLite defense assignments {exact_def}/12 < 6"),
        ("a_db_sched_9", exact_def >= 9, 0.06, f"SQLite defense assignments {exact_def}/12 < 9"),
        ("a_db_sched_all12", exact_def == 12, 0.08, f"SQLite defense assignments {exact_def}/12 != 12"),
        ("a_no_blackout_booked", no_blackout, 0.07, "Booked one of the 3 red QPainter facility blackout cells"),
        ("a_no_room_double_book", no_room_dup, 0.06, "Room/slot double-booked or <12 scheduled"),
        ("a_capacity_respected", cap_ok, 0.05, "Room capacity violated"),
        ("a_no_chair_conflict", no_chair_dup, 0.06, "Chair professor double-booked in same slot"),
        ("a_ics_exists", ics_p.is_file(), 0.04, "Missing /workspace/schedule/defense_calendar.ics"),
        ("a_ics_vcalendar", ics_vcal, 0.04, "Invalid RFC-5545 VCALENDAR wrapper"),
        ("a_ics_12_vevents", len(evs) == 12, 0.06, f"VEVENT count {len(evs)} != 12"),
        ("a_ics_loc_dt_half6", ics_exact >= 6, 0.06, f"VEVENT LOCATION+DTSTART matches {ics_exact}/12 < 6"),
        ("a_ics_loc_dt_all12", ics_exact == 12, 0.08, f"VEVENT LOCATION+DTSTART matches {ics_exact}/12 != 12"),
        ("a_xlsx_hall_a_4", abs(_v("Budget_Envelope", "B2") - 4.0) <= 0.01, 0.04, "Budget_Envelope!B2 != 4"),
        ("a_xlsx_hall_b_4", abs(_v("Budget_Envelope", "B3") - 4.0) <= 0.01, 0.04, "Budget_Envelope!B3 != 4"),
        ("a_xlsx_sem_c_4", abs(_v("Budget_Envelope", "B4") - 4.0) <= 0.01, 0.04, "Budget_Envelope!B4 != 4"),
        ("a_xlsx_room_formula", _f("Budget_Envelope", "B5"), 0.05, "Budget_Envelope!B5 missing formula"),
        ("a_xlsx_room_3520", abs(_v("Budget_Envelope", "B5") - TRUE_ROOM_COST_USD) <= 0.5, 0.05, f"Budget_Envelope!B5 != {TRUE_ROOM_COST_USD}"),
        ("a_xlsx_cal_seal", _s("Budget_Envelope", "B6") == CALENDAR_ORGANIZER_SEAL, 0.06, "Budget_Envelope!B6 missing calendar_organizer_seal"),
    ]

    # --- Role B: Vendor SLA Curation + Calc Sizing + PDF/Manifest (18 subchecks) ---
    inc_ok = sum(1 for v in ACTIVE_VENDORS if vnd_rows.get(v[0]) == "INCLUDED_ACTIVE")
    exc_ok = sum(1 for vid in SUSPENDED_IDS if vnd_rows.get(vid) == "EXCLUDED_SUSPENDED")
    sheet_ids = [_s("Vendor_SLAs", f"A{r}") for r in range(2, 10)]
    sheet_active_hits = sum(1 for v in ACTIVE_VENDORS if v[0] in sheet_ids)
    sheet_no_susp = not any(_s("Vendor_SLAs", f"A{r}") in SUSPENDED_IDS for r in range(2, 14))
    e_formulas = sum(1 for r in range(2, 10) if _f("Vendor_SLAs", f"E{r}"))

    b7_val = _v("Budget_Envelope", "B7")
    b8_val = _v("Budget_Envelope", "B8")
    b11_val = _v("Budget_Envelope", "B11")
    man = read_json_safe(man_p)
    pdf_txt = extract_pdf_text(pdf_p)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_db_active8", inc_ok == 8, 0.06, f"SQLite INCLUDED_ACTIVE {inc_ok}/8"),
        ("b_db_suspended2", exc_ok == 2, 0.05, f"SQLite EXCLUDED_SUSPENDED {exc_ok}/2"),
        ("b_sheet_rows6", sheet_active_hits >= 6, 0.05, f"Vendor_SLAs active rows {sheet_active_hits}/8 < 6"),
        ("b_sheet_rows8", sheet_active_hits == 8, 0.07, f"Vendor_SLAs active rows {sheet_active_hits}/8 != 8"),
        ("b_sheet_no_suspended", sheet_no_susp and sheet_active_hits >= 1, 0.06, "Vendor_SLAs includes suspended vendor"),
        ("b_sheet_net_formulas", e_formulas >= 8, 0.05, f"Vendor_SLAs!E2:E9 formulas {e_formulas}/8"),
        ("b_b7_sum_formula", _f("Budget_Envelope", "B7"), 0.05, "Budget_Envelope!B7 missing SUM formula"),
        ("b_b7_15480", abs(b7_val - TRUE_ACTIVE_SLA_SUM) <= 1.0, 0.08, f"Total_Active_SLA_USD={b7_val} != {TRUE_ACTIVE_SLA_SUM}"),
        ("b_b8_range", 2100.0 <= b8_val <= 3000.0, 0.06, f"AV_Contingency_Reserve_USD={b8_val} outside [2100, 3000]"),
        ("b_b9_formula", _f("Budget_Envelope", "B9"), 0.05, "Budget_Envelope!B9 missing =B5+B7+B8 formula"),
        ("b_b11_formula", _f("Budget_Envelope", "B11"), 0.05, "Budget_Envelope!B11 missing =B9/B10 formula"),
        ("b_b11_util_band", 0.840 <= b11_val <= 0.885, 0.08, f"Grant_Utilization_Ratio={b11_val} outside [0.840, 0.885]"),
        ("b_b12_sla_seal", _s("Budget_Envelope", "B12") == PROCUREMENT_SLA_SEAL, 0.06, "Budget_Envelope!B12 missing procurement_sla_seal"),
        ("b_manifest_exists", man_p.is_file(), 0.04, "Missing CONTRACT_MANIFEST.json"),
        ("b_manifest_vendors", sorted(man.get("active_vendor_ids") or []) == sorted(v[0] for v in ACTIVE_VENDORS) and sorted(man.get("suspended_vendor_ids") or []) == sorted(SUSPENDED_IDS), 0.05, "CONTRACT_MANIFEST vendor ID lists mismatch"),
        ("b_manifest_seal", man.get("procurement_sla_seal") == PROCUREMENT_SLA_SEAL, 0.04, "CONTRACT_MANIFEST seal mismatch"),
        ("b_pdf_exists", pdf_p.is_file(), 0.05, "Missing SLA_Summary.pdf"),
        (
            "b_pdf_content",
            ("15480" in pdf_txt or "15,480" in pdf_txt)
            and (PROCUREMENT_SLA_SEAL in pdf_txt or PROCUREMENT_SLA_SEAL[:10] in pdf_txt),
            0.05,
            "SLA_Summary.pdf missing 15480 or SLA seal",
        ),
    ]

    # --- Joint preservation checks (4 subchecks -> total 40 subchecks, weight 0.18 <= 0.20 cap) ---
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_calc_desk_tag", _s("Vendor_SLAs", "C1") == CALC_DESK_TAG, 0.05, f"Vendor_SLAs!C1 lost {CALC_DESK_TAG}"),
        ("j_both_sheets_intact", "Vendor_SLAs" in ev_sh and "Budget_Envelope" in ev_sh, 0.04, "Contract_Schedule.xlsx lost sheet"),
        ("j_sqlite_tables_intact", len(def_rows) == 12 and len(vnd_rows) == 10, 0.04, "maildesk.sqlite lost rows"),
        ("j_no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.05, "Open LibreOffice Calc held stale unsaved buffer"),
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
    assert role in ("defense_scheduler", "contract_automation_eng")
    ws = next(iter(workspace_map.values()))
    db_p = ws / "maildesk" / "maildesk.sqlite"
    ics_p = ws / "schedule" / "defense_calendar.ics"
    xp = ws / "contracts" / "Contract_Schedule.xlsx"

    def _work() -> None:
        flush_open_libreoffice_to_disk(xp)
        ev = evaluate_xlsx_via_libreoffice(xp)
        desk_c1 = str((ev.get("Vendor_SLAs") or {}).get("C1", {}).get("value") or CALC_DESK_TAG)
        cur_ha = int(float((ev.get("Budget_Envelope") or {}).get("B2", {}).get("value") or 5))
        cur_hb = int(float((ev.get("Budget_Envelope") or {}).get("B3", {}).get("value") or 5))
        cur_sc = int(float((ev.get("Budget_Envelope") or {}).get("B4", {}).get("value") or 2))
        cur_cseal = str((ev.get("Budget_Envelope") or {}).get("B6", {}).get("value") or "PENDING")
        cur_sla_sum = float((ev.get("Budget_Envelope") or {}).get("B7", {}).get("value") or 0.0)
        cur_cont = float((ev.get("Budget_Envelope") or {}).get("B8", {}).get("value") or 0.0)
        cur_pseal = str((ev.get("Budget_Envelope") or {}).get("B12", {}).get("value") or "PENDING")

        if role == "defense_scheduler":
            gui_sh = (
                "export DISPLAY=:99; "
                "wid=$(xdotool search --onlyvisible --name 'MailDesk Client' | tail -n 1); "
                "wmctrl -i -a \"$wid\" 2>/dev/null || true; xdotool windowactivate \"$wid\"; sleep 0.2; "
                "xdotool key --clearmodifiers ctrl+b; sleep 0.25"
            )
            subprocess.run(["su", "-s", "/bin/bash", "user", "-c", gui_sh], check=True, capture_output=True, timeout=15)
            c_seal = get_x11_clipboard()
            with sqlite3.connect(str(db_p), timeout=15.0) as conn:
                for d in DEFENSE_TRUTH:
                    conn.execute(
                        "UPDATE defense_threads SET assigned_room=?, assigned_slot=?, status='SCHEDULED' WHERE def_id=?",
                        (d[5], d[6], d[0]),
                    )
                conn.commit()
            ics_lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MailDesk//ThesisDefense2026//EN"]
            for d in DEFENSE_TRUTH:
                dt0, dt1 = SLOT_DT_MAP[d[6]]
                ics_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{d[0]}@maildesk.local",
                    f"SUMMARY:{d[0]} {d[1]} (Chair: {d[2]})",
                    f"LOCATION:{d[5]}",
                    f"DTSTART:{dt0}",
                    f"DTEND:{dt1}",
                    "END:VEVENT",
                ])
            ics_lines.append("END:VCALENDAR")
            ics_p.write_text("\n".join(ics_lines) + "\n", encoding="utf-8")
            update_single_sheet_xlsx(
                xp,
                "Budget_Envelope",
                _make_budget_sheet(4, 4, 4, c_seal, cur_sla_sum, cur_cont, cur_pseal),
            )
        else:
            targets = cdp_list_targets(9222)
            t_p = next(t for t in targets if str(port) in t.get("url", ""))
            cdp_eval_js(t_p["webSocketDebuggerUrl"], "copySeal().then(()=>true);")
            p_seal = get_x11_clipboard()
            with sqlite3.connect(str(db_p), timeout=15.0) as conn:
                for v in VENDORS_TRUTH:
                    st_v = "INCLUDED_ACTIVE" if v[5] == "ACTIVE_APPROVED" else "EXCLUDED_SUSPENDED"
                    conn.execute("UPDATE vendor_addenda SET curation_status=? WHERE vnd_id=?", (st_v, v[0]))
                conn.commit()
            update_single_sheet_xlsx(xp, "Vendor_SLAs", _make_vendor_sheet(active_only=True, desk_tag=desk_c1))
            update_single_sheet_xlsx(
                xp,
                "Budget_Envelope",
                _make_budget_sheet(cur_ha, cur_hb, cur_sc, cur_cseal, TRUE_ACTIVE_SLA_SUM, 2500.0, p_seal),
            )
            convert_doc_to_pdf_isolated(xp, ws / "contracts" / "SLA_Summary.pdf")
            write_json(
                ws / "contracts" / "CONTRACT_MANIFEST.json",
                {
                    "active_vendor_ids": sorted(v[0] for v in ACTIVE_VENDORS),
                    "suspended_vendor_ids": sorted(SUSPENDED_IDS),
                    "total_active_sla_usd": TRUE_ACTIVE_SLA_SUM,
                    "av_contingency_reserve_usd": 2500.0,
                    "procurement_sla_seal": p_seal,
                },
            )
        reload_open_libreoffice_docs([xp])

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4 (LAW_6 Calc Split-Brain + Clipboard Overwrite): Stale Budget_Envelope overwrite clobbers B6 & C1."""
    ws = next(iter(workspace_map.values()))
    xp = ws / "contracts" / "Contract_Schedule.xlsx"
    solve_role("defense_scheduler", workspace_map, port, careful_conc=False)
    solve_role("contract_automation_eng", workspace_map, port, careful_conc=False)
    update_single_sheet_xlsx(xp, "Vendor_SLAs", _make_vendor_sheet(active_only=True, desk_tag=""))
    update_single_sheet_xlsx(
        xp,
        "Budget_Envelope",
        _make_budget_sheet(5, 5, 2, "PENDING", TRUE_ACTIVE_SLA_SUM, 2500.0, PROCUREMENT_SLA_SEAL),
    )
    reload_open_libreoffice_docs([xp])
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 4
    write_json(sp, st)
