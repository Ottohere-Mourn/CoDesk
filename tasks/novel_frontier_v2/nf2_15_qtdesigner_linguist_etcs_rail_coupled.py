"""NF2-15: Live Qt5 Designer (`.ui`) + Qt5 Linguist (`.ts` -> `.qm`) — ETCS Rail Cab DMI Layout & Localization Pixel Coupling."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    file_atomic_lock,
    inspect_live_x11_window_titles_readonly,
    launch_chromium_natural,
    launch_qt_designer_natural,
    launch_qt_linguist_natural,
    make_canary_code,
    read_json_safe,
    write_json,
    write_multipage_sop_pdf,
)

TASK_ID = "NF2-15"
PORTAL_PORT = 19615

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `Qt5 Designer` (`.ui`) & `Qt5 Linguist` (`.ts`/`.qm`) Coupling: ERA ETCS Cab DMI Ergonomics vs. German/French Safety Strings",
    "domain": "Railway Signaling EN 50126 HMI (`Qt5 Designer` + `Qt5 Linguist` + `lrelease`) & Braking Curve Physics (`SQLite`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("rail_hmi_ergonomics_eng", "rail_safety_l10n_lead"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

ERA_DMI_CODE = make_canary_code("ERA-026-DMI", "night-cab-1024px")
ERA_L10N_CODE = make_canary_code("ERA-026-L10N", "de-fr-abbr-qm")
# Cab LCD horizontal budget = 1024 px:
# SpeedGaugePane (>= 520 px, Role A pref 560 px) + AlertBanner (>= 450 px base; >= max_de_chars*11+20 = 493 px once DE translated, Role B pref 500 px).
# Solo A: 560 + 450 = 1010 <= 1024; Solo B: 520 + 500 = 1020 <= 1024; Uncoord A+B: 560 + 500 = 1060 > 1024!
LCD_WIDTH_CAP_PX = 1024
SPEED_PANE_FLOOR_PX = 520
BANNER_FLOOR_PX = 450

SOURCE_STRINGS = [
    ("STR_EB_INTERVENTION", "EMERGENCY BRAKE INTERVENTION", "ZWANGSBREMSUNG AKTIV", "FREINAGE D'URGENCE ACTIF"),
    ("STR_OVERSPEED_WARN", "OVERSPEED WARNING", "GESCHWINDIGKEITSWARNUNG", "ALERTE SURVITESSE"),
    ("STR_SIGNAL_PASS_STOP", "UNAUTHORIZED PASSING OF EOA", "ZWANGSBREMSUNG: UNZULÄSSIGE EOA-VORBEIFAHRT", "FRANCHISSEMENT EOA INTERDIT"),
    ("STR_TRACTION_CUTOFF", "TRACTION CUT-OFF ENGAGED", "TRAKTIONSABSCHALTUNG EIN", "COUPURE TRACTION ACTIVE"),
    ("STR_BALISE_CRC_ERR", "EUROBALISE TELEGRAM FAULT", "EUROBALISE-TELEGRAMMFEHLER", "DÉFAUT TÉLÉGRAMME BALISE"),
    ("STR_ISOLATION_MODE", "ETCS SYSTEM ISOLATED", "ETCS-STÖRSCHALTER EIN", "ETCS ISOLÉ MANUELLEMENT"),
    ("STR_ROLLBACK_SUPERVISION", "ROLLBACK PROTECTION ACTIVE", "RÜCKROLLÜBERWACHUNG AKTIV", "ANTI-RECUL ACTIF"),
    ("STR_RADIO_HOLDOVER", "GSM-R SAFE RADIO TIMEOUT", "GSM-R-FUNKÜBERWACHUNG ABGELAUFEN", "DÉLAI RADIO GSM-R EXPIRÉ"),
]

INIT_ETCS_UI = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>ETCSCabDMI</class>
 <widget class="QWidget" name="ETCSCabDMI">
  <property name="geometry"><rect><x>0</x><y>0</y><width>1024</width><height>768</height></rect></property>
  <property name="windowTitle"><string>ERA ETCS Subset-026 Cab DMI</string></property>
  <property name="styleSheet"><string>background-color: #FFFFFF; color: #000000;</string></property>
  <layout class="QVBoxLayout" name="rootVBox">
   <item>
    <layout class="QHBoxLayout" name="cabTopHBox">
     <item>
      <widget class="QFrame" name="SpeedGaugePane">
       <property name="minimumSize"><size><width>0</width><height>360</height></size></property>
       <layout class="QFormLayout" name="speedForm">
        <item row="0" column="0"><widget class="QLabel" name="lblMaxSpeed"><property name="text"><string>Permitted Speed (km/h)</string></property></widget></item>
        <item row="0" column="1"><widget class="QSpinBox" name="maxSpeedSpin"><property name="minimum"><number>0</number></property><property name="maximum"><number>999</number></property><property name="singleStep"><number>1</number></property></widget></item>
        <item row="1" column="0"><widget class="QLabel" name="lblRelSpeed"><property name="text"><string>Release Speed (km/h)</string></property></widget></item>
        <item row="1" column="1"><widget class="QSpinBox" name="releaseSpeedSpin"><property name="minimum"><number>0</number></property><property name="maximum"><number>200</number></property><property name="singleStep"><number>1</number></property></widget></item>
       </layout>
      </widget>
     </item>
     <item>
      <widget class="QLabel" name="AlertBanner">
       <property name="minimumSize"><size><width>450</width><height>96</height></size></property>
       <property name="text"><string>EMERGENCY BRAKE INTERVENTION</string></property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <widget class="QPushButton" name="BtnAcknowledgeEB">
     <property name="minimumSize"><size><width>220</width><height>28</height></size></property>
     <property name="text"><string>ACKNOWLEDGE INTERVENTION</string></property>
    </widget>
   </item>
  </layout>
 </widget>
 <resources/>
 <connections/>
</ui>
"""


def _render_etcs_ui(qss: str, speed_w: int, banner_w: int, btn_w: int, btn_h: int, max_sp: tuple[int, int, int], rel_sp: tuple[int, int, int]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>ETCSCabDMI</class>
 <widget class="QWidget" name="ETCSCabDMI">
  <property name="geometry"><rect><x>0</x><y>0</y><width>1024</width><height>768</height></rect></property>
  <property name="windowTitle"><string>ERA ETCS Subset-026 Cab DMI</string></property>
  <property name="styleSheet"><string>{qss}</string></property>
  <layout class="QVBoxLayout" name="rootVBox">
   <item>
    <layout class="QHBoxLayout" name="cabTopHBox">
     <item>
      <widget class="QFrame" name="SpeedGaugePane">
       <property name="minimumSize"><size><width>{speed_w}</width><height>360</height></size></property>
       <layout class="QFormLayout" name="speedForm">
        <item row="0" column="0"><widget class="QLabel" name="lblMaxSpeed"><property name="text"><string>Permitted Speed (km/h)</string></property></widget></item>
        <item row="0" column="1"><widget class="QSpinBox" name="maxSpeedSpin"><property name="minimum"><number>{max_sp[0]}</number></property><property name="maximum"><number>{max_sp[1]}</number></property><property name="singleStep"><number>{max_sp[2]}</number></property></widget></item>
        <item row="1" column="0"><widget class="QLabel" name="lblRelSpeed"><property name="text"><string>Release Speed (km/h)</string></property></widget></item>
        <item row="1" column="1"><widget class="QSpinBox" name="releaseSpeedSpin"><property name="minimum"><number>{rel_sp[0]}</number></property><property name="maximum"><number>{rel_sp[1]}</number></property><property name="singleStep"><number>{rel_sp[2]}</number></property></widget></item>
       </layout>
      </widget>
     </item>
     <item>
      <widget class="QLabel" name="AlertBanner">
       <property name="minimumSize"><size><width>{banner_w}</width><height>96</height></size></property>
       <property name="text"><string>EMERGENCY BRAKE INTERVENTION</string></property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <widget class="QPushButton" name="BtnAcknowledgeEB">
     <property name="minimumSize"><size><width>{btn_w}</width><height>{btn_h}</height></size></property>
     <property name="text"><string>ACKNOWLEDGE INTERVENTION</string></property>
    </widget>
   </item>
  </layout>
 </widget>
 <resources/>
 <connections/>
</ui>
"""


def _compute_etcs_oracles() -> tuple[int, float, int, int]:
    # Role A: Two-stage emergency braking distance on EMU_8CAR runs with sensor_status='OK'
    # consist_braking_params for EMU_8CAR: a_high_ms2=1.05 (>120 km/h), a_low_ms2=1.22 (<=120 km/h),
    # rotating_inertia_factor=1.08, traction_cutoff_s=1.2, eb_build_s=2.4 -> t_eq = 1.2 + 0.5*2.4 = 2.4 s
    # adhesion_derating: 'WET' -> 0.85, 'CONTAMINATED_LEAF' -> 0.68
    # Uphill grade_permille > 0 assists braking (+9.81 * grade_permille / 1000.0); downhill < 0 reduces braking.
    v_split = 120.0 / 3.6
    t_eq = 1.2 + 0.5 * 2.4
    d_list: list[float] = []
    for i in range(1, 221):
        consist = "FREIGHT_LOCO" if (i % 9 == 0) else "EMU_8CAR"
        status = "DOPPLER_RADAR_DROPOUT" if (i % 23 == 0) else "OK"
        if consist != "EMU_8CAR" or status != "OK":
            continue
        v0_kmh = 100.0 + (i % 7) * 20.0
        gr = -6.0 + (i % 6) * 2.0
        adh = 0.68 if (i % 5 == 0) else 0.85
        v0 = v0_kmh / 3.6
        g_term = 9.81 * (gr / 1000.0)
        a_lo = (1.22 * adh + g_term) / 1.08
        a_hi = (1.05 * adh + g_term) / 1.08
        if v0_kmh > 120.0:
            d_stop = v0 * t_eq + (v0 * v0 - v_split * v_split) / (2.0 * a_hi) + (v_split * v_split) / (2.0 * a_lo)
        else:
            d_stop = v0 * t_eq + (v0 * v0) / (2.0 * a_lo)
        d_list.append(d_stop)

    # Role B: Subset-036 air-gap bits across deduplicated (balise_group_id, pig_index) latest telegram_seq
    # where test_bench_mode='TRACKSIDE_LIVE', crc_ok=1, nid_packet=41:
    # scrambled_payload_bits = ceil(payload_user_bits / 10) * 11, plus 13 header_control_bits + 85 check_crc_bits = +98 overhead
    dedup: dict[tuple[int, int], tuple[int, int, int, str]] = {}
    for seq in range(1, 211):
        bg = 400 + (seq % 35)
        pig = seq % 2
        nid = 41 if (seq % 3 == 0) else 27
        ubits = 134 + (seq % 9) * 13
        crc = 0 if (seq % 19 == 0) else 1
        mode = "BENCH_SIM" if (seq % 17 == 0) else "TRACKSIDE_LIVE"
        dedup[(bg, pig)] = (nid, ubits, crc, mode)
    total_bits = 0
    for nid, ubits, crc, mode in dedup.values():
        if mode == "TRACKSIDE_LIVE" and crc == 1 and nid == 41:
            total_bits += math.ceil(ubits / 10.0) * 11 + 13 + 85
    max_de_len = max(len(de) for _id, _s, de, _fr in SOURCE_STRINGS)
    return len(d_list), round(sum(d_list) / len(d_list), 2), max_de_len, total_bits


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — ERA ETCS Cab DMI `.ui` Layout & Emergency Braking Curve Audit (`rail_hmi_ergonomics_eng`)",
        "",
        "## Objective",
        f"Update `{b}/workspace/shared_docs/etcs_cab_dmi.ui{b}` (open in **Qt5 Designer**) per the **ERA ETCS Subset-026 Portal** in Chromium (`http://127.0.0.1:{PORTAL_PORT}`) and `{b}/workspace/docs/SOP_ETCS_DMI.pdf{b}`, analyze `{b}/workspace/physics/eb_braking_runs.sqlite{b}`, and write `{b}/workspace/dmi_ergonomics_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — ETCS Bilingual Safety `.ts`/`.qm` Localization & Fit Verification (`rail_safety_l10n_lead`)",
        "",
        "## Objective",
        f"Complete all 8 unfinished German safety translations in `{b}/workspace/shared_docs/etcs_safety_de.ts{b}` (open in **Qt5 Linguist**), compile `{b}/workspace/shared_docs/etcs_safety_de.qm{b}` via `lrelease`, verify horizontal banner pixel fit in `{b}/workspace/shared_docs/etcs_cab_dmi.ui{b}` per the **ERA ETCS Subset-026 Portal** (`http://127.0.0.1:{PORTAL_PORT}`) and `{b}/workspace/docs/SOP_ETCS_L10N.pdf{b}`, reconcile `{b}/workspace/glossary/balise_telegram_codes.sqlite{b}`, and write `{b}/workspace/etcs_l10n_audit.json{b}`.",
    ])
    return {"rail_hmi_ergonomics_eng": ta, "rail_safety_l10n_lead": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["rail_hmi_ergonomics_eng"]
    ws_b = workspace_map["rail_safety_l10n_lead"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "physics", ws_a / "docs", ws_b / "glossary", ws_b / "docs", hub):
        d.mkdir(parents=True, exist_ok=True)

    (hub / "etcs_cab_dmi.ui").write_text(INIT_ETCS_UI, encoding="utf-8")

    msgs = "".join(
        f'    <message id="{sid}"><source>{src}</source><translation type="unfinished"></translation></message>\n'
        for sid, src, _de, _fr in SOURCE_STRINGS
    )
    (hub / "etcs_safety_de.ts").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TS version="2.1" language="de_DE">\n'
        '  <context><name>ETCSCabDMI</name>\n' + msgs + '  </context>\n</TS>\n',
        encoding="utf-8",
    )

    with sqlite3.connect(str(ws_a / "physics/eb_braking_runs.sqlite")) as conn:
        conn.execute(
            "CREATE TABLE braking_tests (run_id INTEGER PRIMARY KEY, consist_class TEXT, v0_kmh REAL, grade_permille REAL, rail_cond TEXT, sensor_status TEXT)"
        )
        for i in range(1, 221):
            consist = "FREIGHT_LOCO" if (i % 9 == 0) else "EMU_8CAR"
            status = "DOPPLER_RADAR_DROPOUT" if (i % 23 == 0) else "OK"
            rcond = "CONTAMINATED_LEAF" if (i % 5 == 0) else "WET"
            conn.execute("INSERT INTO braking_tests VALUES (?,?,?,?,?,?)", (i, consist, 100.0 + (i % 7) * 20.0, -6.0 + (i % 6) * 2.0, rcond, status))
        conn.execute(
            "CREATE TABLE consist_braking_params (consist_class TEXT PRIMARY KEY, a_high_speed_ms2 REAL, a_low_speed_ms2 REAL, split_speed_kmh REAL, rotating_inertia_factor REAL, traction_cutoff_s REAL, eb_build_s REAL)"
        )
        conn.execute("INSERT INTO consist_braking_params VALUES ('EMU_8CAR', 1.05, 1.22, 120.0, 1.08, 1.2, 2.4)")
        conn.execute("INSERT INTO consist_braking_params VALUES ('FREIGHT_LOCO', 0.62, 0.74, 80.0, 1.14, 2.5, 4.8)")
        conn.execute("CREATE TABLE adhesion_derating (rail_cond TEXT PRIMARY KEY, adhesion_factor REAL)")
        conn.execute("INSERT INTO adhesion_derating VALUES ('WET', 0.85), ('CONTAMINATED_LEAF', 0.68)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_ETCS_DMI.pdf", "SOP-RAIL-1515A: EN 50126 Cab DMI .ui & Braking Distance", [
        ("1. Qt5 Designer .ui & Braking Curve Audit", [
            f"1.1 In /workspace/shared_docs/etcs_cab_dmi.ui (open in Qt5 Designer), enforce night-cab styleSheet containing '#0B101B', configure maxSpeedSpin, releaseSpeedSpin, and BtnAcknowledgeEB bounds per the 'DMI Widget Bounds' Portal tab, and set SpeedGaugePane minimum width (>={SPEED_PANE_FLOOR_PX} px, preferred 560 px) while preserving AlertBanner minimum width (>={BANNER_FLOOR_PX} px) so SpeedGaugePane + AlertBanner <= {LCD_WIDTH_CAP_PX} px. Save cleanly in Qt5 Designer.",
            "1.2 Filter eb_braking_runs.sqlite to passenger 'EMU_8CAR' runs with sensor_status = 'OK' and compute mean two-stage emergency stopping distance (m, 2 dec) per the 'Two-Stage Braking Physics' Portal tab.",
        ]),
        ("2. JSON Schema (/workspace/dmi_ergonomics_audit.json)", [
            "Keys: valid_run_count (int), mean_wet_stopping_distance_m (float, 2 dec), speed_pane_width_px (int), alert_banner_width_px (int), era_dmi_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "glossary/balise_telegram_codes.sqlite")) as conn:
        conn.execute("CREATE TABLE approved_de_glossary (msg_id TEXT PRIMARY KEY, source_en TEXT, verbose_rejected_de TEXT, concise_approved_de TEXT)")
        for sid, src, de_conc, _fr in SOURCE_STRINGS:
            conn.execute("INSERT INTO approved_de_glossary VALUES (?,?,?,?)", (sid, src, de_conc + " — SOFORTIGE QUITTIERUNG ERFORDERLICH BITTE PRÜFEN", de_conc))
        conn.execute(
            "CREATE TABLE packet_logs (telegram_seq INTEGER PRIMARY KEY, balise_group_id INTEGER, pig_index INTEGER, nid_packet INTEGER, payload_user_bits INTEGER, crc_ok INTEGER, test_bench_mode TEXT)"
        )
        for seq in range(1, 211):
            conn.execute(
                "INSERT INTO packet_logs VALUES (?,?,?,?,?,?,?)",
                (seq, 400 + (seq % 35), seq % 2, 41 if seq % 3 == 0 else 27, 134 + (seq % 9) * 13, 0 if seq % 19 == 0 else 1, "BENCH_SIM" if seq % 17 == 0 else "TRACKSIDE_LIVE"),
            )
        conn.execute("CREATE TABLE subset036_airgap_overhead (scrambler_in_bits INTEGER, scrambler_out_bits INTEGER, header_control_bits INTEGER, check_crc_bits INTEGER)")
        conn.execute("INSERT INTO subset036_airgap_overhead VALUES (10, 11, 13, 85)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_ETCS_L10N.pdf", "SOP-RAIL-1515B: Qt5 Linguist .ts/.qm Compilation & Pixel Fit", [
        ("1. Qt5 Linguist Translation & Pixel Budget", [
            "1.1 Populate all 8 German safety strings in /workspace/shared_docs/etcs_safety_de.ts (open in Qt5 Linguist) using concise_approved_de from approved_de_glossary, mark all 8 translated (no type='unfinished'), save cleanly, and compile /workspace/shared_docs/etcs_safety_de.qm via lrelease.",
            f"1.2 Verify and update AlertBanner minimum width in /workspace/shared_docs/etcs_cab_dmi.ui so AlertBanner >= (max_de_char_length * 11 + 20) px (preferred 500 px) while keeping SpeedGaugePane (>={SPEED_PANE_FLOOR_PX} px) + AlertBanner <= {LCD_WIDTH_CAP_PX} px.",
            "1.3 Deduplicate packet_logs by (balise_group_id, pig_index) keeping only the latest telegram_seq, filter to TRACKSIDE_LIVE rows with crc_ok = 1 and nid_packet = 41, and compute total Subset-036 scrambled air-gap bits per the 'Subset-036 Air-Gap Framing' Portal tab.",
        ]),
        ("2. JSON Schema (/workspace/etcs_l10n_audit.json)", [
            "Keys: translated_string_count (int), max_de_char_length (int), valid_nid41_total_airgap_bits (int), era_l10n_code (str).",
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
    state = {"task_id": TASK_ID, "active_tab": "overview", "tab_switches": 0}
    write_json(state_dir / "service_state.json", state)

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/health":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self.send_response(403); self.end_headers(); return
                raw = b"<html><body><script>location.href='/era-dmi';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"era_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            c = SimpleCookie(self.headers.get("Cookie") or "")
            if "era_sso" not in c or c["era_sso"].value != tok:
                self.send_response(403); self.end_headers(); return
            if u.path == "/tab":
                tid = (qs.get("id") or ["overview"])[0]
                if tid in ("overview", "dmi_bounds", "braking_physics", "balise_subset036") and tid != state["active_tab"]:
                    state["active_tab"] = tid
                    state["tab_switches"] = int(state["tab_switches"]) + 1
                    write_json(state_dir / "service_state.json", state)
                self.send_response(302); self.send_header("Location", "/era-dmi"); self.end_headers(); return
            cur = state["active_tab"]
            if cur == "overview":
                body = (
                    f"<h3>Active ERA Subset-026 / 036 Control Certificates</h3>"
                    f"<p>Cab LCD Horizontal Pixel Cap: <code>SpeedGaugePane + AlertBanner &lt;= {LCD_WIDTH_CAP_PX} px</code> | Banner Glyph Fit: <code>max_de_char_length * 11 + 20 &lt;= AlertBanner_width_px</code></p>"
                    f"<p>DMI Ergonomics Code: <strong style='color:#4ade80'>{ERA_DMI_CODE}</strong> | Localization Code: <strong style='color:#38bdf8'>{ERA_L10N_CODE}</strong></p>"
                )
            elif cur == "dmi_bounds":
                body = (
                    "<h3>Qt5 Designer Cab DMI Widget Safety Bounds (etcs_cab_dmi.ui)</h3>"
                    "<ul>"
                    "<li>Root <code>ETCSCabDMI</code> night styleSheet must include background <code>#0B101B</code>.</li>"
                    "<li><code>maxSpeedSpin</code>: minimum = <code>40</code>, maximum = <code>400</code>, singleStep = <code>5</code>.</li>"
                    "<li><code>releaseSpeedSpin</code>: minimum = <code>10</code>, maximum = <code>60</code>, singleStep = <code>5</code>.</li>"
                    "<li><code>BtnAcknowledgeEB</code>: minimumSize width &gt;= <code>280 px</code> and height &gt;= <code>56 px</code>.</li>"
                    f"<li><code>SpeedGaugePane</code> minimum width &gt;= <code>{SPEED_PANE_FLOOR_PX} px</code> (preferred <code>560 px</code>); <code>AlertBanner</code> minimum width &gt;= <code>{BANNER_FLOOR_PX} px</code>; sum &lt;= <code>{LCD_WIDTH_CAP_PX} px</code>.</li>"
                    "</ul>"
                )
            elif cur == "braking_physics":
                body = (
                    "<h3>ERA Subset-026 Two-Stage Emergency Braking Model</h3>"
                    "<p>Evaluate <code>consist_class = 'EMU_8CAR'</code> rows with <code>sensor_status = 'OK'</code> in <code>eb_braking_runs.sqlite</code>:</p>"
                    "<ul>"
                    "<li>Equivalent reaction time: <code>t_eq = traction_cutoff_s + 0.5 * eb_build_s</code> (coasting at <code>v0 = v0_kmh / 3.6</code>).</li>"
                    "<li>Effective deceleration in each speed band (uphill <code>grade_permille &gt; 0</code> assists braking; downhill <code>&lt; 0</code> reduces deceleration):<br/>"
                    "<code>a_eff = (a_band_ms2 * adhesion_factor + 9.81 * (grade_permille / 1000.0)) / rotating_inertia_factor</code></li>"
                    "<li>If <code>v0_kmh &gt; split_speed_kmh</code> (<code>120 km/h</code>, <code>v_split = 120 / 3.6</code>):<br/>"
                    "<code>d_stop = v0 * t_eq + (v0^2 - v_split^2) / (2 * a_eff_high) + v_split^2 / (2 * a_eff_low)</code>; otherwise <code>d_stop = v0 * t_eq + v0^2 / (2 * a_eff_low)</code>.</li>"
                    "</ul>"
                )
            else:
                body = (
                    "<h3>ERA Subset-036 Eurobalise Up-Link Air-Gap Bit Framing</h3>"
                    "<p>1. Deduplicate <code>packet_logs</code> by <code>(balise_group_id, pig_index)</code> retaining the highest <code>telegram_seq</code>.<br/>"
                    "2. Filter retained rows to <code>test_bench_mode = 'TRACKSIDE_LIVE'</code>, <code>crc_ok = 1</code>, and <code>nid_packet = 41</code>.<br/>"
                    "3. Each telegram's air-gap length = <code>ceil(payload_user_bits / 10) * 11 + header_control_bits + check_crc_bits</code> using <code>subset036_airgap_overhead</code>.</p>"
                )
            nav = (
                "<div style='margin-bottom:14px'>"
                "<a style='color:#93c5fd;margin-right:16px' href='/tab?id=overview'>[Overview &amp; Certs]</a>"
                "<a style='color:#93c5fd;margin-right:16px' href='/tab?id=dmi_bounds'>[DMI Widget Bounds]</a>"
                "<a style='color:#93c5fd;margin-right:16px' href='/tab?id=braking_physics'>[Two-Stage Braking Physics]</a>"
                "<a style='color:#93c5fd' href='/tab?id=balise_subset036'>[Subset-036 Air-Gap Framing]</a>"
                "</div>"
            )
            page = f"<!doctype html><html><body style='background:#0b101b;color:#f8fafc;font-family:monospace;margin:20px'><h2>ERA ETCS Subset-026 / 036 Engineering Portal ({cur})</h2>{nav}{body}</body></html>".encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(page)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    if "rail_hmi_ergonomics_eng" in roles:
        launch_qt_designer_natural(hub / "etcs_cab_dmi.ui")
    if "rail_safety_l10n_lead" in roles:
        launch_qt_linguist_natural(hub / "etcs_safety_de.ts")
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _parse_ui(ui_p: Path) -> dict[str, Any]:
    if not ui_p.is_file():
        return {}
    # Primary: authentic PyQt5.uic.loadUi() offscreen widget inspection (handles Qt5 Designer minimumSize, minimumWidth, QSS, SpinBoxes)
    probe = (
        "import json, os, sys\n"
        "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "from PyQt5 import QtWidgets, uic\n"
        "app = QtWidgets.QApplication(sys.argv)\n"
        f"w = uic.loadUi({json.dumps(str(ui_p))})\n"
        "sp = w.findChild(QtWidgets.QWidget, 'SpeedGaugePane')\n"
        "bn = w.findChild(QtWidgets.QWidget, 'AlertBanner')\n"
        "bt = w.findChild(QtWidgets.QWidget, 'BtnAcknowledgeEB')\n"
        "ms = w.findChild(QtWidgets.QSpinBox, 'maxSpeedSpin')\n"
        "rs = w.findChild(QtWidgets.QSpinBox, 'releaseSpeedSpin')\n"
        "out = {\n"
        "  'qss': w.styleSheet() or '',\n"
        "  'speed_w': int(max(sp.minimumWidth(), sp.minimumSize().width())) if sp else 0,\n"
        "  'banner_w': int(max(bn.minimumWidth(), bn.minimumSize().width())) if bn else 0,\n"
        "  'btn_w': int(max(bt.minimumWidth(), bt.minimumSize().width())) if bt else 0,\n"
        "  'btn_h': int(max(bt.minimumHeight(), bt.minimumSize().height())) if bt else 0,\n"
        "  'max_spin': [ms.minimum(), ms.maximum(), ms.singleStep()] if ms else [0, 0, 0],\n"
        "  'rel_spin': [rs.minimum(), rs.maximum(), rs.singleStep()] if rs else [0, 0, 0],\n"
        "}\n"
        "print('UIC_JSON:' + json.dumps(out))\n"
    )
    try:
        cp = subprocess.run(["python3", "-c", probe], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, capture_output=True, text=True, timeout=20)
        for ln in cp.stdout.splitlines():
            if ln.startswith("UIC_JSON:"):
                return json.loads(ln.split("UIC_JSON:", 1)[1])
    except Exception:
        pass
    # Fallback XML parser supporting BOTH Qt5 Designer <property name="minimumSize"><size> and <property name="minimumWidth">
    try:
        root = ET.fromstring(ui_p.read_text(encoding="utf-8"))
        out: dict[str, Any] = {"qss": "", "speed_w": 0, "banner_w": 0, "btn_w": 0, "btn_h": 0, "max_spin": [0, 0, 0], "rel_spin": [0, 0, 0]}
        for w in root.iter("widget"):
            nm = w.attrib.get("name", "")
            svals = {}
            for pr in w.findall("property"):
                pnm = pr.attrib.get("name", "")
                if nm == "ETCSCabDMI" and pnm == "styleSheet":
                    out["qss"] = "".join(pr.itertext())
                elif nm == "SpeedGaugePane" and pnm == "minimumWidth":
                    out["speed_w"] = max(out["speed_w"], int("".join(pr.itertext()).strip() or "0"))
                elif nm == "SpeedGaugePane" and pnm == "minimumSize":
                    we = pr.find("./size/width")
                    if we is not None and (we.text or "").strip():
                        out["speed_w"] = max(out["speed_w"], int(we.text.strip()))
                elif nm == "AlertBanner" and pnm == "minimumWidth":
                    out["banner_w"] = max(out["banner_w"], int("".join(pr.itertext()).strip() or "0"))
                elif nm == "AlertBanner" and pnm == "minimumSize":
                    we = pr.find("./size/width")
                    if we is not None and (we.text or "").strip():
                        out["banner_w"] = max(out["banner_w"], int(we.text.strip()))
                elif nm == "BtnAcknowledgeEB" and pnm == "minimumHeight":
                    out["btn_h"] = max(out["btn_h"], int("".join(pr.itertext()).strip() or "0"))
                elif nm == "BtnAcknowledgeEB" and pnm == "minimumWidth":
                    out["btn_w"] = max(out["btn_w"], int("".join(pr.itertext()).strip() or "0"))
                elif nm == "BtnAcknowledgeEB" and pnm == "minimumSize":
                    we = pr.find("./size/width"); he = pr.find("./size/height")
                    if we is not None and (we.text or "").strip():
                        out["btn_w"] = max(out["btn_w"], int(we.text.strip()))
                    if he is not None and (he.text or "").strip():
                        out["btn_h"] = max(out["btn_h"], int(he.text.strip()))
                elif nm in ("maxSpeedSpin", "releaseSpeedSpin") and pnm in ("minimum", "maximum", "singleStep"):
                    svals[pnm] = int("".join(pr.itertext()).strip() or "0")
            if nm == "maxSpeedSpin" and svals:
                out["max_spin"] = [svals.get("minimum", 0), svals.get("maximum", 0), svals.get("singleStep", 0)]
            elif nm == "releaseSpeedSpin" and svals:
                out["rel_spin"] = [svals.get("minimum", 0), svals.get("maximum", 0), svals.get("singleStep", 0)]
        return out
    except Exception:
        return {}


def _parse_ts(ts_p: Path) -> dict[str, str]:
    if not ts_p.is_file():
        return {}
    try:
        root = ET.fromstring(ts_p.read_text(encoding="utf-8"))
        out = {}
        for m in root.iter("message"):
            tr = m.find("translation")
            if tr is not None and tr.attrib.get("type") != "unfinished" and (tr.text or "").strip():
                src = m.findtext("source", "")
                out[src] = (tr.text or "").strip()
        return out
    except Exception:
        return {}


def _verify_qm_translations(qm_p: Path) -> dict[str, str]:
    if not qm_p.is_file() or qm_p.stat().st_size < 40:
        return {}
    srcs = [s for _id, s, _de, _fr in SOURCE_STRINGS]
    probe = (
        "import json, os, sys\n"
        "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "from PyQt5 import QtCore\n"
        "app = QtCore.QCoreApplication(sys.argv)\n"
        "tr = QtCore.QTranslator()\n"
        f"ok = tr.load({json.dumps(str(qm_p))})\n"
        f"res = {{s: tr.translate('ETCSCabDMI', s) for s in {json.dumps(srcs)}}} if ok else {{}}\n"
        "print('QM_JSON:' + json.dumps(res, ensure_ascii=False))\n"
    )
    try:
        cp = subprocess.run(["python3", "-c", probe], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, capture_output=True, text=True, timeout=15)
        for ln in cp.stdout.splitlines():
            if ln.startswith("QM_JSON:"):
                return json.loads(ln.split("QM_JSON:", 1)[1])
    except Exception:
        pass
    return {}


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("rail_hmi_ergonomics_eng" in act), ("rail_safety_l10n_lead" in act)
    ws_a = workspace_map["rail_hmi_ergonomics_eng"]
    ws_b = workspace_map["rail_safety_l10n_lead"]
    hub = workspace_map["__shared_hub__"]
    ui = _parse_ui(hub / "etcs_cab_dmi.ui")
    ts_map = _parse_ts(hub / "etcs_safety_de.ts")
    qm_map = _verify_qm_translations(hub / "etcs_safety_de.qm")
    ja = read_json_safe(ws_a / "dmi_ergonomics_audit.json")
    jb = read_json_safe(ws_b / "etcs_l10n_audit.json")
    titles = inspect_live_x11_window_titles_readonly()

    exp_cnt, exp_d, exp_max_len, exp_bits = _compute_etcs_oracles()

    sw = int(ui.get("speed_w", 0))
    bw = int(ui.get("banner_w", 0))
    ja_sw = ja.get("speed_pane_width_px")
    ja_sw_ok = (
        isinstance(ja_sw, (int, float))
        and SPEED_PANE_FLOOR_PX <= float(ja_sw) <= (LCD_WIDTH_CAP_PX - BANNER_FLOOR_PX)
        and (int(ja_sw) == sw if not has_b else True)
    )
    max_tr_len = max((len(v) for v in ts_map.values()), default=999)
    spins_ok = (ui.get("max_spin") == [40, 400, 5]) and (ui.get("rel_spin") == [10, 60, 5])
    btn_ok = int(ui.get("btn_h", 0)) >= 56 and int(ui.get("btn_w", 0)) >= 280

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing dmi_ergonomics_audit.json"),
        ("a_qss_btn", "#0b101b" in str(ui.get("qss", "")).lower() and btn_ok, 0.14, "etcs_cab_dmi.ui missing #0B101B night QSS or BtnAcknowledgeEB >= 280x56 px"),
        ("a_spins", spins_ok, 0.12, "maxSpeedSpin [40,400,5] or releaseSpeedSpin [10,60,5] bounds mismatch in etcs_cab_dmi.ui"),
        ("a_widths", sw >= SPEED_PANE_FLOOR_PX and bw >= BANNER_FLOOR_PX and ja_sw_ok, 0.16, f"SpeedGaugePane ({sw}) / AlertBanner ({bw}) widths below floor or JSON speed_pane_width_px ({ja_sw}) invalid"),
        ("a_code_cnt", ja.get("era_dmi_code") == ERA_DMI_CODE and ja.get("valid_run_count") == exp_cnt, 0.18, f"era_dmi_code or valid_run_count != {exp_cnt} mismatch"),
        ("a_fine_two_stage_stop", abs(float(ja.get("mean_wet_stopping_distance_m") or -999) - exp_d) <= 0.35, 0.32, f"mean_wet_stopping_distance_m != {exp_d} (check two-stage 120 km/h split, leaf adhesion 0.68 & rotating inertia 1.08)"),
    ]

    conc_hits = sum(1 for _id, src, de, _fr in SOURCE_STRINGS if ts_map.get(src) == de)
    qm_hits = sum(1 for _id, src, de, _fr in SOURCE_STRINGS if qm_map.get(src) == de)
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing etcs_l10n_audit.json"),
        ("b_ts_all8", conc_hits == 8 and jb.get("translated_string_count") == 8, 0.20, f"etcs_safety_de.ts concise approved translations: {conc_hits}/8"),
        ("b_qm_built", qm_hits == 8, 0.18, f"etcs_safety_de.qm QTranslator verified strings: {qm_hits}/8"),
        ("b_code_len", jb.get("era_l10n_code") == ERA_L10N_CODE and jb.get("max_de_char_length") == exp_max_len, 0.20, f"era_l10n_code or max_de_char_length != {exp_max_len} mismatch"),
        ("b_fine_airgap_bits", jb.get("valid_nid41_total_airgap_bits") == exp_bits, 0.34, f"valid_nid41_total_airgap_bits != {exp_bits} (check (balise_group_id,pig_index) dedup & ceil(bits/10)*11 + 98)"),
    ]

    eff_sw = sw if (has_a and sw > 0) else (SPEED_PANE_FLOOR_PX if not has_a else 9999)
    eff_bw = bw if bw > 0 else (BANNER_FLOOR_PX if not has_a else 9999)
    fit_ok = (not has_b) or ((max_tr_len * 11 + 20) <= eff_bw)
    ui_clean = not any("*" in t and ("Qt Designer" in t or "Qt Linguist" in t) for t in titles)
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_lcd_1024_cap", (eff_sw >= SPEED_PANE_FLOOR_PX) and (eff_bw >= BANNER_FLOOR_PX) and (eff_sw + eff_bw <= LCD_WIDTH_CAP_PX) and fit_ok, 0.14, f"Coupled LCD width {eff_sw}+{eff_bw} > 1024 px or German string ({max_tr_len}*11+20 px) overflows AlertBanner ({eff_bw} px)!"),
        ("j_qt_clean", act_done and ui_clean, 0.08, "Qt Designer or Qt Linguist holds unsaved [*] edits"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    ui_p = hub / "etcs_cab_dmi.ui"
    ts_p = hub / "etcs_safety_de.ts"
    exp_cnt, exp_d, exp_max_len, exp_bits = _compute_etcs_oracles()
    req_bw = exp_max_len * 11 + 20

    if role == "rail_hmi_ergonomics_eng":
        with file_atomic_lock("nf215_ui"):
            cur = _parse_ui(ui_p)
            bw = int(cur.get("banner_w") or 0)
            bw = max(bw, req_bw)
            sw = max(SPEED_PANE_FLOOR_PX, min(526, LCD_WIDTH_CAP_PX - bw))
            ui_p.write_text(
                _render_etcs_ui("background-color: #0B101B; color: #F8FAFC;", sw, bw, 300, 60, (40, 400, 5), (10, 60, 5)),
                encoding="utf-8",
            )
        write_json(ws / "dmi_ergonomics_audit.json", {
            "valid_run_count": exp_cnt, "mean_wet_stopping_distance_m": exp_d,
            "speed_pane_width_px": sw, "alert_banner_width_px": bw, "era_dmi_code": ERA_DMI_CODE,
        })
    else:
        with file_atomic_lock("nf215_ui"):
            cur = _parse_ui(ui_p)
            sw_cur = int(cur.get("speed_w") or 0)
            qss_cur = str(cur.get("qss") or "background-color: #FFFFFF; color: #000000;")
            btn_w = max(220, int(cur.get("btn_w") or 220))
            btn_h = max(28, int(cur.get("btn_h") or 28))
            ms_t = tuple(cur.get("max_spin") or [0, 999, 1])
            rs_t = tuple(cur.get("rel_spin") or [0, 200, 1])
            bw_set = max(req_bw, min(496, LCD_WIDTH_CAP_PX - sw_cur) if sw_cur >= SPEED_PANE_FLOOR_PX else 496)
            if sw_cur + bw_set > LCD_WIDTH_CAP_PX and sw_cur >= SPEED_PANE_FLOOR_PX:
                sw_cur = LCD_WIDTH_CAP_PX - bw_set
            ui_p.write_text(
                _render_etcs_ui(qss_cur, sw_cur, bw_set, btn_w, btn_h, (ms_t[0], ms_t[1], ms_t[2]), (rs_t[0], rs_t[1], rs_t[2])),
                encoding="utf-8",
            )
            msgs = "".join(f'    <message id="{sid}"><source>{src}</source><translation>{de}</translation></message>\n' for sid, src, de, _fr in SOURCE_STRINGS)
            ts_p.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<TS version="2.1" language="de_DE">\n  <context><name>ETCSCabDMI</name>\n' + msgs + '  </context>\n</TS>\n', encoding="utf-8")
            subprocess.run(["lrelease", str(ts_p), "-qm", str(hub / "etcs_safety_de.qm")], check=True, capture_output=True, timeout=20)
        write_json(ws / "etcs_l10n_audit.json", {
            "translated_string_count": 8, "max_de_char_length": exp_max_len,
            "valid_nid41_total_airgap_bits": exp_bits, "era_l10n_code": ERA_L10N_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("rail_hmi_ergonomics_eng", workspace_map, port)
    solve_role("rail_safety_l10n_lead", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    # Uncoordinated preferred widths 560 + 500 = 1060 > 1024 px!
    (hub / "etcs_cab_dmi.ui").write_text(
        _render_etcs_ui("background-color: #0B101B; color: #F8FAFC;", 560, 500, 300, 60, (40, 400, 5), (10, 60, 5)),
        encoding="utf-8",
    )
