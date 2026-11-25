"""AW-06: IEC 62366 ICU Infusion Console Release 3.2 — Qt5 Designer Ergonomics & QSS vs. Qt5 Linguist L10n & Git."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    launch_desktop_app_as_user,
    read_json_safe,
    resource_lock,
    write_json,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-06",
    "slug": "qt_designer_linguist_l10n",
    "title": "IEC 62366 ICU Infusion Console Release 3.2: Qt5 Designer Ergonomics & QSS vs. Qt5 Linguist Clinical L10n & Git",
    "domain": "Embedded Medical Qt UI & Clinical Localization (Qt5 Designer + Qt5 Linguist + lrelease + PyQt5 + Git + Chromium)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19606,
    "roles": ("qt_ui_ergonomics_eng", "clinical_l10n_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

REGULATORY_SIGNOFF_ID = "IEC62366-ICU32-2026"
EXPECTED_TABSTOPS = ["rateSpinBox", "vtbiSpinBox", "bolusBtn", "startInfusionBtn", "emergencyStopBtn"]

# (context, canonical_en_source, de_DE, ja_JP, fr_FR)
CLINICAL_STRINGS: list[tuple[str, str, str, str, str]] = [
    ("InfusionConsole", "Infusion Rate (mL/h)", "Infusionsrate (mL/h)", "投与速度 (mL/h)", "Débit de perfusion (mL/h)"),
    ("InfusionConsole", "Volume to Be Infused (mL)", "Zu infundierendes Volumen (mL)", "予定投与量 (mL)", "Volume à perfuser (mL)"),
    ("InfusionConsole", "Deliver Bolus", "Bolusgabe jetzt starten", "ボーラス投与開始", "Administrer le bolus"),
    ("InfusionConsole", "Start Primary Infusion", "Primärinfusion freigeben", "主投与を開始", "Démarrer perfusion primaire"),
    ("InfusionConsole", "Emergency Occlusion Stop", "Okklusions-Nothalt aktiv", "閉塞緊急停止", "Arrêt d'urgence d'occlusion"),
    (
        "InfusionConsole",
        "HIGH ALARM: Downstream Line Occlusion (%1 kPa)",
        "HOCHALARM: Distale Leitungsokklusion (%1 kPa)",
        "高優先度警報: 下流ライン閉塞 (%1 kPa)",
        "ALARME HAUTE : Occlusion aval (%1 kPa)",
    ),
    (
        "InfusionConsole",
        "Bolus Dose: %1 mL over %2 min",
        "Bolusdosis: %1 mL über %2 Min.",
        "ボーラス量: %2 分間で %1 mL",
        "Dose bolus : %1 mL sur %2 min",
    ),
    ("InfusionConsole", "Clear Total", "Kumuliertes Volumen nullen", "積算量をリセット", "Effacer le volume cumulé"),
    ("ServiceMenu", "Clear Total", "Wartungszähler löschen", "保守カウンタ消去", "Réinitialiser compteur SAV"),
]

TICKET_A = (
    "# Work Order — Embedded Qt UI & IEC 62366 Ergonomics Engineer (`qt_ui_ergonomics_eng`)\n\n"
    "Remediate the **Adult ICU** infusion pump console UI layout, dose hard-limits, source label standardization, high-priority alarm QSS, and offscreen render check on Git branch `release/3.2` in `/workspace/medpanel`:\n\n"
    "1. Review `/workspace/medpanel/specs/IEC62366_Infusion_UI_Spec.pdf` and inspect the **IEC 62366 Clinical UI Portal** open in Chromium (`http://127.0.0.1:19606` — make sure to select the **Adult ICU** department profile and also check the 3-locale glossary for maximum localized button length).\n"
    "2. Remediate `/workspace/medpanel/ui/infusion_console.ui` (standardizing informal draft button labels to exact canonical English strings per spec, setting Adult ICU spinbox bounds/precision/steps, sizing primary button `minimumSize` for nitrile-glove height AND multi-locale text expansion across `de_DE`/`ja_JP`/`fr_FR`, and configuring explicit clinical `<tabstops>`).\n"
    "3. Remediate `/workspace/medpanel/src/alarm_theme.qss` for IEC 60601-1-8 high-priority alarm luminance, render `/workspace/medpanel/build/infusion_ui_offscreen.png` via `PyQt5` (`QT_QPA_PLATFORM=offscreen`), write `/workspace/medpanel/ui_ergonomics_verification.json` (`regulatory_signoff_id`, `min_button_width_px`, `min_button_height_px`, `alarm_contrast_ratio`, `tabstops`), set `ui_ergonomics` in `/workspace/medpanel/release_manifest.json` to the `regulatory_signoff_id` string, and commit cleanly onto `release/3.2`.\n"
)

TICKET_B = (
    "# Work Order — Clinical Localization & Regulatory Terminology Engineer (`clinical_l10n_eng`)\n\n"
    "Complete the German (`de_DE`), Japanese (`ja_JP`), and French (`fr_FR`) Adult ICU clinical translations, compile `.qm` binaries, update Qt resources, and commit cleanly on Git branch `release/3.2` in `/workspace/medpanel`:\n\n"
    "1. Review `/workspace/medpanel/specs/IEC62366_Infusion_UI_Spec.pdf` and inspect the **IEC 62366 Clinical UI Portal** in Chromium (`http://127.0.0.1:19606`, `3-Locale Approved ICU Glossary` tab).\n"
    "2. Update `/workspace/medpanel/i18n/infusion_de.ts`, `infusion_ja.ts`, and `infusion_fr.ts`: standardize any informal `<source>` strings (`Bolus Now!`, `STOP!!`) to canonical English per spec, fix all unfinished/false-friend/context-swapped/placeholder-broken (`%1`, `%2`) translations across all 9 messages, and remove all `type=\"unfinished\"` attributes.\n"
    "3. Compile `/workspace/medpanel/build/i18n/infusion_de.qm`, `infusion_ja.qm`, and `infusion_fr.qm` via `lrelease`, register all three `.qm` files in `/workspace/medpanel/resources/medpanel.qrc`, write `/workspace/medpanel/i18n/localization_manifest.json` (`regulatory_signoff_id`, `de_qm_sha256`, `ja_qm_sha256`, `fr_qm_sha256`, `translated_message_count`, `max_localized_button_chars`), set `clinical_l10n` in `/workspace/medpanel/release_manifest.json` to the `regulatory_signoff_id` string, and commit cleanly onto `release/3.2`.\n"
)

INITIAL_UI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>InfusionConsole</class>
 <widget class="QWidget" name="InfusionConsole">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>760</width><height>480</height></rect>
  </property>
  <property name="windowTitle"><string>MedPanel ICU Infusion Console</string></property>
  <layout class="QVBoxLayout" name="mainLayout">
   <item>
    <widget class="QLabel" name="alarmBanner">
     <property name="minimumSize"><size><width>680</width><height>44</height></size></property>
     <property name="text"><string>HIGH ALARM: Downstream Line Occlusion (%1 kPa)</string></property>
    </widget>
   </item>
   <item>
    <layout class="QFormLayout" name="doseForm">
     <item row="0" column="0">
      <widget class="QLabel" name="rateLabel"><property name="text"><string>Infusion Rate (mL/h)</string></property></widget>
     </item>
     <item row="0" column="1">
      <widget class="QDoubleSpinBox" name="rateSpinBox">
       <property name="decimals"><number>0</number></property>
       <property name="minimum"><double>0.000000000000000</double></property>
       <property name="maximum"><double>2500.000000000000000</double></property>
       <property name="singleStep"><double>5.000000000000000</double></property>
      </widget>
     </item>
     <item row="1" column="0">
      <widget class="QLabel" name="vtbiLabel"><property name="text"><string>Volume to Be Infused (mL)</string></property></widget>
     </item>
     <item row="1" column="1">
      <widget class="QDoubleSpinBox" name="vtbiSpinBox">
       <property name="decimals"><number>0</number></property>
       <property name="minimum"><double>0.000000000000000</double></property>
       <property name="maximum"><double>9999.000000000000000</double></property>
       <property name="singleStep"><double>10.000000000000000</double></property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <layout class="QHBoxLayout" name="btnRow">
     <item>
      <widget class="QPushButton" name="bolusBtn">
       <property name="minimumSize"><size><width>92</width><height>28</height></size></property>
       <property name="text"><string>Bolus Now!</string></property>
      </widget>
     </item>
     <item>
      <widget class="QPushButton" name="startInfusionBtn">
       <property name="minimumSize"><size><width>92</width><height>28</height></size></property>
       <property name="text"><string>Start Primary Infusion</string></property>
      </widget>
     </item>
     <item>
      <widget class="QPushButton" name="emergencyStopBtn">
       <property name="minimumSize"><size><width>92</width><height>28</height></size></property>
       <property name="text"><string>STOP!!</string></property>
      </widget>
     </item>
    </layout>
   </item>
  </layout>
 </widget>
 <tabstops>
  <tabstop>emergencyStopBtn</tabstop>
  <tabstop>rateSpinBox</tabstop>
 </tabstops>
 <resources/>
 <connections/>
</ui>
"""


def _write_initial_ts(path: Path, lang: str) -> None:
    # Deliberately unfinished + dangerous clinical false-friend draft strings
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", f'<TS version="2.1" language="{lang}">']
    for ctx_name in ("InfusionConsole", "ServiceMenu"):
        lines.append(f"  <context>\n    <name>{ctx_name}</name>")
        for c, src, _de, _ja, _fr in CLINICAL_STRINGS:
            if c != ctx_name:
                continue
            raw_src = "Bolus Now!" if src == "Deliver Bolus" else ("STOP!!" if src == "Emergency Occlusion Stop" else src)
            if "Deliver Bolus" in src:
                bad = "Infusion abbrechen" if lang == "de_DE" else ("投与を中止" if lang == "ja_JP" else "Arrêter la perfusion")
                lines.append(f'    <message><source>{raw_src}</source><translation type="unfinished">{bad}</translation></message>')
            elif "%1" in src:
                bad = "WARNUNG: Okklusion" if lang == "de_DE" else ("警報: 閉塞" if lang == "ja_JP" else "ALARME : Occlusion")
                lines.append(f'    <message><source>{raw_src}</source><translation type="unfinished">{bad}</translation></message>')
            else:
                lines.append(f'    <message><source>{raw_src}</source><translation type="unfinished"></translation></message>')
        lines.append("  </context>")
    lines.append("</TS>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def build(workspace_root: Path, tickets_root: Path) -> None:
    mp = workspace_root / "shared" / "medpanel"
    for sub in ("ui", "src", "i18n", "resources", "build/i18n", "specs"):
        (mp / sub).mkdir(parents=True, exist_ok=True)

    (mp / ".gitignore").write_text("__pycache__/\n*.pyc\n*.bak\n", encoding="utf-8")
    (mp / "build" / "i18n" / ".gitkeep").write_text("", encoding="utf-8")
    (mp / "ui" / "infusion_console.ui").write_text(INITIAL_UI_XML, encoding="utf-8")
    (mp / "src" / "alarm_theme.qss").write_text(
        "/* Legacy low-contrast staging stylesheet */\n"
        "#alarmBanner {\n  background-color: #fef08a;\n  color: #eab308;\n  font-weight: bold;\n  padding: 8px;\n}\n",
        encoding="utf-8",
    )
    _write_initial_ts(mp / "i18n" / "infusion_de.ts", "de_DE")
    _write_initial_ts(mp / "i18n" / "infusion_ja.ts", "ja_JP")
    _write_initial_ts(mp / "i18n" / "infusion_fr.ts", "fr_FR")
    (mp / "resources" / "medpanel.qrc").write_text(
        '<!DOCTYPE RCC><RCC version="1.0">\n  <qresource prefix="/i18n">\n  </qresource>\n</RCC>\n',
        encoding="utf-8",
    )
    write_json(
        mp / "release_manifest.json",
        {"branch": "release/3.2", "ui_ergonomics": "PENDING", "clinical_l10n": "PENDING"},
    )

    write_pdf_manual(
        mp / "specs" / "IEC62366_Infusion_UI_Spec.pdf",
        "IEC 62366 & IEC 60601-1-8 ICU Infusion Console Release 3.2 Specification",
        [
            (
                "1. Dose SpinBox Hard Safety Limits & Focus Tab Order",
                [
                    "Select the Adult ICU profile (not the default NICU Neonatal view!) in the Clinical UI Portal to retrieve hard dose SpinBox bounds, step increments, decimal precision, and rotary-encoder <tabstops> sequence.",
                ],
            ),
            (
                "2. Canonical English Label Standardization & Multi-Locale Button Sizing",
                [
                    "Draft informal button labels ('Bolus Now!' on bolusBtn and 'STOP!!' on emergencyStopBtn) violate IEC 62366 usability rules and must be replaced with canonical English 'Deliver Bolus' and 'Emergency Occlusion Stop' in BOTH ui/infusion_console.ui AND all .ts translation <source> elements!",
                    "All three primary QPushButtons (bolusBtn, startInfusionBtn, emergencyStopBtn) must set minimumSize height >= 48 px and width >= max(160, 9 * max_localized_button_chars + 32), where max_localized_button_chars is the character length of the longest approved translation of those three buttons across ALL THREE supported locales (de_DE, ja_JP, fr_FR)!",
                ],
            ),
            (
                "3. IEC 60601-1-8 High-Priority Alarm QSS & Offscreen Render Proof",
                [
                    "Apply the Adult ICU high-priority alarm background and foreground hex colors from the Clinical UI Portal to #alarmBanner in src/alarm_theme.qss.",
                    "Instantiate ui/infusion_console.ui with src/alarm_theme.qss under QT_QPA_PLATFORM=offscreen and grab widget snapshot build/infusion_ui_offscreen.png.",
                ],
            ),
            (
                "4. Clinical Localization, Placeholder Integrity & Git Release Hygiene",
                [
                    "Translate all 9 messages across InfusionConsole (8 strings) and ServiceMenu (1 disambiguated 'Clear Total') in infusion_de.ts, infusion_ja.ts, and infusion_fr.ts using exact approved terms from the Clinical UI Portal, preserving '%1' and '%2' positional placeholders and removing all unfinished flags.",
                    "Compile build/i18n/infusion_{de,ja,fr}.qm via lrelease, register all three in resources/medpanel.qrc, update your section of release_manifest.json without clobbering sibling keys, and leave branch release/3.2 with a clean git working tree.",
                ],
            ),
        ],
    )

    git_init = (
        f"cd '{mp}' && git init -b release/3.2 && "
        "git config user.name 'MedPanel Release Bot' && git config user.email 'release@medpanel.local' && "
        "git add -A && git commit -m 'Initial staging snapshot for release/3.2'"
    )
    subprocess.run(["bash", "-lc", git_init], check=True, capture_output=True, timeout=25)

    (tickets_root / "qt_ui_ergonomics_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "clinical_l10n_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "qt_ui_ergonomics_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "clinical_l10n_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "nicu_distractor", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw06_sess" in ck) and (ck["aw06_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw06_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 IEC 62366 Clinical Portal Session Required (Inspect open Chromium)</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["nicu_distractor"])[0]
                with lock:
                    if t in ("nicu_distractor", "icu_adult", "glossary") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return

            with lock:
                cur = state["active_tab"]
            if cur == "nicu_distractor":
                body = """
                <h2>NICU Neonatal Micro-Infusion Profile (release/3.1-neo — DO NOT APPLY TO ADULT ICU 3.2)</h2>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>rateSpinBox:</b> <code>0.05 .. 150.0 mL/h</code>, <code>singleStep = 0.05</code>, <code>decimals = 2</code></li>
                  <li><b>vtbiSpinBox:</b> <code>0.1 .. 500.0 mL</code>, <code>singleStep = 0.1</code>, <code>decimals = 1</code></li>
                </ul>"""
            elif cur == "icu_adult":
                body = f"""
                <h2>Adult ICU Console Profile (release/3.2 — TARGET SPECIFICATION)</h2>
                <p><b>Regulatory Signoff ID:</b> <code>{REGULATORY_SIGNOFF_ID}</code></p>
                <ul style="line-height:1.9;font-size:16px;margin-top:12px;">
                  <li><b>rateSpinBox:</b> <code>0.1 .. 1200.0 mL/h</code>, <code>singleStep = 0.5</code>, <code>decimals = 1</code></li>
                  <li><b>vtbiSpinBox:</b> <code>1.0 .. 5000.0 mL</code>, <code>singleStep = 1.0</code>, <code>decimals = 1</code></li>
                  <li><b>Glove Button Minimum Size Formula:</b> <code>height &gt;= 48 px</code>, <code>width &gt;= max(160, 9 * max_localized_button_chars + 32)</code> across <code>de_DE / ja_JP / fr_FR</code></li>
                  <li><b>High-Priority Alarm QSS (#alarmBanner):</b> <code>background-color: #dc2626; color: #ffffff;</code> (contrast <code>4.83:1</code>)</li>
                  <li><b>Tab Order:</b> <code>rateSpinBox -&gt; vtbiSpinBox -&gt; bolusBtn -&gt; startInfusionBtn -&gt; emergencyStopBtn</code></li>
                </ul>"""
            else:
                rows = "".join(
                    f"<tr><td><code>{ctx}</code></td><td>{src}</td><td><b>{de}</b></td><td><b>{ja}</b></td><td><b>{fr}</b></td></tr>"
                    for ctx, src, de, ja, fr in CLINICAL_STRINGS
                )
                body = f"""
                <h2>Approved Adult ICU 3-Locale Terminology Glossary (de_DE, ja_JP, fr_FR)</h2>
                <p><b>Regulatory Signoff ID:</b> <code>{REGULATORY_SIGNOFF_ID}</code></p>
                <table border="1" cellpadding="7" style="border-collapse:collapse;margin-top:12px;">
                  <tr><th>Qt Context</th><th>Canonical English Source</th><th>Approved de_DE</th><th>Approved ja_JP</th><th>Approved fr_FR</th></tr>
                  {rows}
                </table>"""

            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>IEC 62366 Clinical Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;color:#0f172a;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>IEC 62366 &amp; ISO 15223 Clinical UI Portal ({cur.upper()})</h1>
            <div class="nav">
              <a href="/tab?id=nicu_distractor">NICU Neonatal (3.1)</a>
              <a href="/tab?id=icu_adult">Adult ICU Ergonomics (3.2)</a>
              <a href="/tab?id=glossary">3-Locale Approved ICU Glossary</a>
            </div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1240, 820))
    mp = workspace_root / "shared" / "medpanel"
    if "qt_ui_ergonomics_eng" in roles:
        launch_desktop_app_as_user(
            f"nohup designer '{mp / 'ui' / 'infusion_console.ui'}' >/tmp/aw06_designer.log 2>&1 </dev/null &",
            wait_s=2.4,
        )
    if "clinical_l10n_eng" in roles:
        launch_desktop_app_as_user(
            f"nohup linguist '{mp / 'i18n' / 'infusion_de.ts'}' '{mp / 'i18n' / 'infusion_ja.ts'}' '{mp / 'i18n' / 'infusion_fr.ts'}' >/tmp/aw06_linguist.log 2>&1 </dev/null &",
            wait_s=2.4,
        )


REMEDIATED_UI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>InfusionConsole</class>
 <widget class="QWidget" name="InfusionConsole">
  <property name="geometry">
   <rect><x>0</x><y>0</y><width>860</width><height>480</height></rect>
  </property>
  <property name="windowTitle"><string>MedPanel ICU Infusion Console</string></property>
  <layout class="QVBoxLayout" name="mainLayout">
   <item>
    <widget class="QLabel" name="alarmBanner">
     <property name="minimumSize"><size><width>780</width><height>48</height></size></property>
     <property name="text"><string>HIGH ALARM: Downstream Line Occlusion (%1 kPa)</string></property>
    </widget>
   </item>
   <item>
    <layout class="QFormLayout" name="doseForm">
     <item row="0" column="0">
      <widget class="QLabel" name="rateLabel"><property name="text"><string>Infusion Rate (mL/h)</string></property></widget>
     </item>
     <item row="0" column="1">
      <widget class="QDoubleSpinBox" name="rateSpinBox">
       <property name="decimals"><number>1</number></property>
       <property name="minimum"><double>0.100000000000000</double></property>
       <property name="maximum"><double>1200.000000000000000</double></property>
       <property name="singleStep"><double>0.500000000000000</double></property>
      </widget>
     </item>
     <item row="1" column="0">
      <widget class="QLabel" name="vtbiLabel"><property name="text"><string>Volume to Be Infused (mL)</string></property></widget>
     </item>
     <item row="1" column="1">
      <widget class="QDoubleSpinBox" name="vtbiSpinBox">
       <property name="decimals"><number>1</number></property>
       <property name="minimum"><double>1.000000000000000</double></property>
       <property name="maximum"><double>5000.000000000000000</double></property>
       <property name="singleStep"><double>1.000000000000000</double></property>
      </widget>
     </item>
    </layout>
   </item>
   <item>
    <layout class="QHBoxLayout" name="btnRow">
     <item>
      <widget class="QPushButton" name="bolusBtn">
       <property name="minimumSize"><size><width>280</width><height>52</height></size></property>
       <property name="text"><string>Deliver Bolus</string></property>
      </widget>
     </item>
     <item>
      <widget class="QPushButton" name="startInfusionBtn">
       <property name="minimumSize"><size><width>280</width><height>52</height></size></property>
       <property name="text"><string>Start Primary Infusion</string></property>
      </widget>
     </item>
     <item>
      <widget class="QPushButton" name="emergencyStopBtn">
       <property name="minimumSize"><size><width>280</width><height>52</height></size></property>
       <property name="text"><string>Emergency Occlusion Stop</string></property>
      </widget>
     </item>
    </layout>
   </item>
  </layout>
 </widget>
 <tabstops>
  <tabstop>rateSpinBox</tabstop>
  <tabstop>vtbiSpinBox</tabstop>
  <tabstop>bolusBtn</tabstop>
  <tabstop>startInfusionBtn</tabstop>
  <tabstop>emergencyStopBtn</tabstop>
 </tabstops>
 <resources/>
 <connections/>
</ui>
"""


def _write_clean_ts(path: Path, lang: str) -> None:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", f'<TS version="2.1" language="{lang}">']
    for ctx_name in ("InfusionConsole", "ServiceMenu"):
        lines.append(f"  <context>\n    <name>{ctx_name}</name>")
        for c, src, de, ja, fr in CLINICAL_STRINGS:
            if c != ctx_name:
                continue
            tgt = de if lang == "de_DE" else (ja if lang == "ja_JP" else fr)
            lines.append(f"    <message><source>{src}</source><translation>{tgt}</translation></message>")
        lines.append("  </context>")
    lines.append("</TS>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    mp = workspace_root / "shared" / "medpanel"
    if role == "qt_ui_ergonomics_eng":
        (mp / "ui" / "infusion_console.ui").write_text(REMEDIATED_UI_XML, encoding="utf-8")
        (mp / "src" / "alarm_theme.qss").write_text(
            "#alarmBanner {\n  background-color: #dc2626;\n  color: #ffffff;\n  font-weight: bold;\n  padding: 8px;\n}\n",
            encoding="utf-8",
        )
        offscreen_py = f"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtWidgets, uic
app = QtWidgets.QApplication(sys.argv)
w = uic.loadUi({str(mp / 'ui' / 'infusion_console.ui')!r})
w.setStyleSheet(open({str(mp / 'src' / 'alarm_theme.qss')!r}, encoding="utf-8").read())
w.resize(860, 480)
w.show()
app.processEvents()
pix = w.grab()
pix.save({str(mp / 'build' / 'infusion_ui_offscreen.png')!r}, "PNG")
"""
        subprocess.run(["python3", "-c", offscreen_py], check=True, capture_output=True, timeout=25)
        write_json(
            mp / "ui_ergonomics_verification.json",
            {
                "regulatory_signoff_id": REGULATORY_SIGNOFF_ID,
                "min_button_width_px": 280,
                "min_button_height_px": 52,
                "alarm_contrast_ratio": 4.83,
                "tabstops": EXPECTED_TABSTOPS,
            },
        )
        if cooperative:
            with resource_lock("aw06_git"):
                rm = read_json_safe(mp / "release_manifest.json")
                rm["branch"] = "release/3.2"
                rm["ui_ergonomics"] = REGULATORY_SIGNOFF_ID
                write_json(mp / "release_manifest.json", rm)
                subprocess.run(
                    [
                        "bash", "-lc",
                        f"cd '{mp}' && git add ui/infusion_console.ui src/alarm_theme.qss build/infusion_ui_offscreen.png ui_ergonomics_verification.json release_manifest.json "
                        "&& (git diff --cached --quiet || git commit -m 'IEC 62366 UI ergonomics & QSS remediation')",
                    ],
                    check=True, capture_output=True, timeout=25,
                )
        else:
            write_json(mp / "release_manifest.json", {"branch": "release/3.2", "ui_ergonomics": REGULATORY_SIGNOFF_ID})
    elif role == "clinical_l10n_eng":
        if not cooperative:
            # Simulate destructive git checkout -- . wiping uncommitted peer edits before l10n work
            subprocess.run(["bash", "-lc", f"cd '{mp}' && git checkout -- . && git clean -fd"], check=True, capture_output=True, timeout=20)
        (mp / "build" / "i18n").mkdir(parents=True, exist_ok=True)
        _write_clean_ts(mp / "i18n" / "infusion_de.ts", "de_DE")
        _write_clean_ts(mp / "i18n" / "infusion_ja.ts", "ja_JP")
        _write_clean_ts(mp / "i18n" / "infusion_fr.ts", "fr_FR")
        de_qm = mp / "build" / "i18n" / "infusion_de.qm"
        ja_qm = mp / "build" / "i18n" / "infusion_ja.qm"
        fr_qm = mp / "build" / "i18n" / "infusion_fr.qm"
        subprocess.run(["lrelease", str(mp / "i18n" / "infusion_de.ts"), "-qm", str(de_qm)], check=True, capture_output=True, timeout=20)
        subprocess.run(["lrelease", str(mp / "i18n" / "infusion_ja.ts"), "-qm", str(ja_qm)], check=True, capture_output=True, timeout=20)
        subprocess.run(["lrelease", str(mp / "i18n" / "infusion_fr.ts"), "-qm", str(fr_qm)], check=True, capture_output=True, timeout=20)
        (mp / "resources" / "medpanel.qrc").write_text(
            '<!DOCTYPE RCC><RCC version="1.0">\n  <qresource prefix="/i18n">\n'
            '    <file alias="infusion_de.qm">../build/i18n/infusion_de.qm</file>\n'
            '    <file alias="infusion_ja.qm">../build/i18n/infusion_ja.qm</file>\n'
            '    <file alias="infusion_fr.qm">../build/i18n/infusion_fr.qm</file>\n'
            "  </qresource>\n</RCC>\n",
            encoding="utf-8",
        )
        de_sha = hashlib.sha256(de_qm.read_bytes()).hexdigest()
        ja_sha = hashlib.sha256(ja_qm.read_bytes()).hexdigest()
        fr_sha = hashlib.sha256(fr_qm.read_bytes()).hexdigest()
        write_json(
            mp / "i18n" / "localization_manifest.json",
            {
                "regulatory_signoff_id": REGULATORY_SIGNOFF_ID,
                "de_qm_sha256": de_sha,
                "ja_qm_sha256": ja_sha,
                "fr_qm_sha256": fr_sha,
                "translated_message_count": 9,
                "max_localized_button_chars": 27,
            },
        )
        if cooperative:
            with resource_lock("aw06_git"):
                rm = read_json_safe(mp / "release_manifest.json")
                rm["branch"] = "release/3.2"
                rm["clinical_l10n"] = REGULATORY_SIGNOFF_ID
                write_json(mp / "release_manifest.json", rm)
                subprocess.run(
                    [
                        "bash", "-lc",
                        f"cd '{mp}' && git add i18n/infusion_de.ts i18n/infusion_ja.ts i18n/infusion_fr.ts i18n/localization_manifest.json "
                        "build/i18n/infusion_de.qm build/i18n/infusion_ja.qm build/i18n/infusion_fr.qm resources/medpanel.qrc release_manifest.json "
                        "&& (git diff --cached --quiet || git commit -m 'ICU de_DE, ja_JP, fr_FR clinical localization')",
                    ],
                    check=True, capture_output=True, timeout=25,
                )
        else:
            write_json(mp / "release_manifest.json", {"branch": "release/3.2", "clinical_l10n": REGULATORY_SIGNOFF_ID})


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("qt_ui_ergonomics_eng", workspace_root, cooperative=False)
    solve_role("clinical_l10n_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "qt_ui_ergonomics_eng", workspace_root, True)
        fb = pool.submit(solve_role, "clinical_l10n_eng", workspace_root, True)
        fa.result()
        fb.result()


def _inspect_qt_runtime(mp: Path) -> dict[str, Any]:
    probe = f"""
import json, os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtCore, QtWidgets, uic
app = QtWidgets.QApplication(sys.argv)
out = {{"ui_loaded": False, "de_loaded": False, "ja_loaded": False}}
ui_p = {str(mp / 'ui' / 'infusion_console.ui')!r}
if os.path.isfile(ui_p):
    w = uic.loadUi(ui_p)
    out["ui_loaded"] = True
    r_sb = w.findChild(QtWidgets.QDoubleSpinBox, "rateSpinBox")
    v_sb = w.findChild(QtWidgets.QDoubleSpinBox, "vtbiSpinBox")
    if r_sb:
        out["rate_bounds"] = [round(r_sb.minimum(), 2), round(r_sb.maximum(), 2), round(r_sb.singleStep(), 2), r_sb.decimals()]
    if v_sb:
        out["vtbi_bounds"] = [round(v_sb.minimum(), 2), round(v_sb.maximum(), 2), round(v_sb.singleStep(), 2), v_sb.decimals()]
    btns = {{}}
    src_labels = {{}}
    for bname in ("bolusBtn", "startInfusionBtn", "emergencyStopBtn"):
        b = w.findChild(QtWidgets.QPushButton, bname)
        if b:
            btns[bname] = [b.minimumWidth(), b.minimumHeight()]
            src_labels[bname] = b.text()
    out["btn_min_sizes"] = btns
    out["btn_texts"] = src_labels

for tag, qm_p in (("de", {str(mp / 'build' / 'i18n' / 'infusion_de.qm')!r}), ("ja", {str(mp / 'build' / 'i18n' / 'infusion_ja.qm')!r}), ("fr", {str(mp / 'build' / 'i18n' / 'infusion_fr.qm')!r})):
    tr = QtCore.QTranslator()
    if os.path.isfile(qm_p) and tr.load(qm_p):
        out[tag + "_loaded"] = True
        tmap = {{}}
        for ctx, src, _de, _ja, _fr in {CLINICAL_STRINGS!r}:
            tmap[f"{{ctx}}::{{src}}"] = tr.translate(ctx, src)
        out[tag + "_translations"] = tmap
print("AW06_QT_JSON:" + json.dumps(out, ensure_ascii=False))
"""
    try:
        cp = subprocess.run(["python3", "-c", probe], check=True, capture_output=True, text=True, timeout=30)
        for ln in cp.stdout.splitlines():
            if ln.startswith("AW06_QT_JSON:"):
                return json.loads(ln.split("AW06_QT_JSON:", 1)[1])
    except Exception:
        pass
    return {}


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    mp = workspace_root / "shared" / "medpanel"
    rt = _inspect_qt_runtime(mp)
    ja = read_json_safe(mp / "ui_ergonomics_verification.json")
    jb = read_json_safe(mp / "i18n" / "localization_manifest.json")
    rm = read_json_safe(mp / "release_manifest.json")
    qss_txt = (mp / "src" / "alarm_theme.qss").read_text(encoding="utf-8", errors="replace").lower() if (mp / "src" / "alarm_theme.qss").is_file() else ""
    qrc_txt = (mp / "resources" / "medpanel.qrc").read_text(encoding="utf-8", errors="replace") if (mp / "resources" / "medpanel.qrc").is_file() else ""
    de_ts_txt = (mp / "i18n" / "infusion_de.ts").read_text(encoding="utf-8", errors="replace") if (mp / "i18n" / "infusion_de.ts").is_file() else ""
    ja_ts_txt = (mp / "i18n" / "infusion_ja.ts").read_text(encoding="utf-8", errors="replace") if (mp / "i18n" / "infusion_ja.ts").is_file() else ""
    fr_ts_txt = (mp / "i18n" / "infusion_fr.ts").read_text(encoding="utf-8", errors="replace") if (mp / "i18n" / "infusion_fr.ts").is_file() else ""

    tabstops_got: list[str] = []
    if (mp / "ui" / "infusion_console.ui").is_file():
        try:
            u_root = ET.fromstring((mp / "ui" / "infusion_console.ui").read_text(encoding="utf-8"))
            ts_el = u_root.find("tabstops")
            if ts_el is not None:
                tabstops_got = [el.text.strip() for el in ts_el.findall("tabstop") if el.text]
        except Exception:
            pass

    git_st = subprocess.run(["bash", "-lc", f"cd '{mp}' && git status --porcelain"], capture_output=True, text=True, timeout=10)
    git_br = subprocess.run(["bash", "-lc", f"cd '{mp}' && git rev-parse --abbrev-ref HEAD"], capture_output=True, text=True, timeout=10)
    git_clean = (git_st.returncode == 0 and git_st.stdout.strip() == "" and git_br.stdout.strip() == "release/3.2")

    btn_sizes = rt.get("btn_min_sizes") or {}
    btns_erg_ok = (
        len(btn_sizes) == 3
        and all(int(wh[0]) >= 275 and int(wh[1]) >= 48 for wh in btn_sizes.values())
    )
    src_preserved = (
        (rt.get("btn_texts") or {}).get("bolusBtn") == "Deliver Bolus"
        and (rt.get("btn_texts") or {}).get("startInfusionBtn") == "Start Primary Infusion"
        and (rt.get("btn_texts") or {}).get("emergencyStopBtn") == "Emergency Occlusion Stop"
    )

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_reg_id", str(ja.get("regulatory_signoff_id", "")).strip() == REGULATORY_SIGNOFF_ID, 1.0, "regulatory_signoff_id missing/wrong"),
        ("a_rate_spin", rt.get("rate_bounds") == [0.1, 1200.0, 0.5, 1], 2.0, f"rateSpinBox bounds mismatch (got {rt.get('rate_bounds')}; verify Adult ICU vs NICU)"),
        ("a_vtbi_spin", rt.get("vtbi_bounds") == [1.0, 5000.0, 1.0, 1], 1.8, f"vtbiSpinBox bounds mismatch (got {rt.get('vtbi_bounds')})"),
        ("a_btn_glove_fr_width", btns_erg_ok, 2.2, f"Button minimumSize fails >=275x48 ICU glove + 27-char French width rule (got {btn_sizes})"),
        ("a_src_labels_standardized", src_preserved, 1.8, "Informal draft labels ('Bolus Now!', 'STOP!!') not standardized in infusion_console.ui"),
        ("a_tabstops", tabstops_got == EXPECTED_TABSTOPS, 1.8, f"tabstops mismatch (got {tabstops_got})"),
        ("a_qss_alarm", "#dc2626" in qss_txt and ("#ffffff" in qss_txt or "#fff" in qss_txt) and "#fef08a" not in qss_txt, 1.6, "alarm_theme.qss missing #dc2626/#ffffff high-priority styling"),
        ("a_offscreen_png", (mp / "build" / "infusion_ui_offscreen.png").is_file() and (mp / "build" / "infusion_ui_offscreen.png").stat().st_size > 4000, 1.5, "build/infusion_ui_offscreen.png missing"),
        ("a_rel_manifest", rm.get("ui_ergonomics") == REGULATORY_SIGNOFF_ID, 1.2, "release_manifest.json missing ui_ergonomics signoff"),
        ("a_git_clean", git_clean, 1.4, "Git working tree on release/3.2 has uncommitted/untracked files"),
    ]

    de_tr = rt.get("de_translations") or {}
    ja_tr = rt.get("ja_translations") or {}
    fr_tr = rt.get("fr_translations") or {}
    de_all_ok = bool(rt.get("de_loaded")) and all(de_tr.get(f"{c}::{s}") == d for c, s, d, _j, _f in CLINICAL_STRINGS)
    ja_all_ok = bool(rt.get("ja_loaded")) and all(ja_tr.get(f"{c}::{s}") == j for c, s, _d, j, _f in CLINICAL_STRINGS)
    fr_all_ok = bool(rt.get("fr_loaded")) and all(fr_tr.get(f"{c}::{s}") == f for c, s, _d, _j, f in CLINICAL_STRINGS)
    de_ctx_ok = de_tr.get("InfusionConsole::Clear Total") == "Kumuliertes Volumen nullen" and de_tr.get("ServiceMenu::Clear Total") == "Wartungszähler löschen"
    placeholders_ok = (
        "%1" in str(de_tr.get("InfusionConsole::HIGH ALARM: Downstream Line Occlusion (%1 kPa)", ""))
        and "%1" in str(fr_tr.get("InfusionConsole::Bolus Dose: %1 mL over %2 min", ""))
        and "%2" in str(ja_tr.get("InfusionConsole::Bolus Dose: %1 mL over %2 min", ""))
    )

    de_qm_p = mp / "build" / "i18n" / "infusion_de.qm"
    ja_qm_p = mp / "build" / "i18n" / "infusion_ja.qm"
    fr_qm_p = mp / "build" / "i18n" / "infusion_fr.qm"
    sha_ok = (
        de_qm_p.is_file()
        and ja_qm_p.is_file()
        and fr_qm_p.is_file()
        and str(jb.get("de_qm_sha256", "")).lower() == hashlib.sha256(de_qm_p.read_bytes()).hexdigest()
        and str(jb.get("ja_qm_sha256", "")).lower() == hashlib.sha256(ja_qm_p.read_bytes()).hexdigest()
        and str(jb.get("fr_qm_sha256", "")).lower() == hashlib.sha256(fr_qm_p.read_bytes()).hexdigest()
    )

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_reg_id", str(jb.get("regulatory_signoff_id", "")).strip() == REGULATORY_SIGNOFF_ID, 1.0, "regulatory_signoff_id missing/wrong"),
        ("b_no_unfinished", 'type="unfinished"' not in de_ts_txt and 'type="unfinished"' not in ja_ts_txt and 'type="unfinished"' not in fr_ts_txt, 1.5, ".ts files still contain unfinished markers"),
        ("b_de_qm_exact", de_all_ok, 2.2, "infusion_de.qm missing or fails approved German ICU terminology"),
        ("b_ja_qm_exact", ja_all_ok, 2.2, "infusion_ja.qm missing or fails approved Japanese ICU terminology"),
        ("b_fr_qm_exact", fr_all_ok, 2.2, "infusion_fr.qm missing or fails approved French ICU terminology"),
        ("b_ctx_disambig", de_ctx_ok, 1.6, "Context disambiguation failed between InfusionConsole::Clear Total and ServiceMenu::Clear Total"),
        ("b_placeholders", placeholders_ok, 1.5, "%1 / %2 positional placeholders missing in compiled translations"),
        ("b_qrc_updated", "infusion_de.qm" in qrc_txt and "infusion_ja.qm" in qrc_txt and "infusion_fr.qm" in qrc_txt, 1.2, "resources/medpanel.qrc does not reference all 3 compiled .qm files"),
        ("b_manifest_sha", sha_ok and jb.get("max_localized_button_chars") == 27, 1.6, "localization_manifest.json SHA-256 or max_localized_button_chars mismatch (expected 27)"),
        ("b_rel_manifest", rm.get("clinical_l10n") == REGULATORY_SIGNOFF_ID, 1.2, "release_manifest.json missing clinical_l10n signoff"),
        ("b_git_clean", git_clean, 1.4, "Git working tree on release/3.2 has uncommitted/untracked files"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_ui_and_qm_integrated_without_clipping",
            btns_erg_ok and src_preserved and de_all_ok and ja_all_ok and fr_all_ok,
            2.2,
            "Combined Qt UI + compiled .qm binaries broken due to .ui overwrite, unstandardized source strings, or button width < 275px",
        ),
        (
            "j_shared_git_release_branch_clean",
            git_clean and rm.get("ui_ergonomics") == REGULATORY_SIGNOFF_ID and rm.get("clinical_l10n") == REGULATORY_SIGNOFF_ID,
            1.8,
            "Shared Git branch release/3.2 left dirty or release_manifest.json lost one role's signoff due to concurrent overwrite",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"qt_ui_ergonomics_eng": TICKET_A, "clinical_l10n_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
