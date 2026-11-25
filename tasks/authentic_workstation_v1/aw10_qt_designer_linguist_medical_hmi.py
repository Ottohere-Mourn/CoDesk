"""AW-10: Live Qt5 Designer & Qt5 Linguist ICU Ventilator HMI Release 4.0."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.authentic_workstation_v1.common import (
    boot_studio_browser,
    build_aw_grade_payload,
    launch_studio_app,
    read_json_safe,
    resource_lock,
    write_json,
    write_pdf_manual,
)

TASK_META: dict[str, Any] = {
    "id": "AW-10",
    "slug": "qt_designer_linguist_medical_hmi",
    "title": "Live Qt5 Designer & Qt5 Linguist ICU Ventilator HMI Release 4.0",
    "domain": "Embedded Medical Qt5 GUI & Clinical Localization (Qt5 Designer + Qt5 Linguist + lrelease + PyQt5 + Git)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19610,
    "roles": ("hmi_designer_ergonomics_eng", "clinical_linguist_release_eng"),
    "iso_role_timeout_s": 7200,
    "conc_role_timeout_s": 7200,
    "mount_studio_ro": True,
}

VENT_SIGNOFF_ID = "ISO80601-VENT40-2026"
VENT_STRINGS = [
    ("VentilatorConsole", "Tidal Volume (mL)", "Atemzugvolumen (mL)"),
    ("VentilatorConsole", "PEEP Pressure (cmH2O)", "PEEP-Druck (cmH2O)"),
    ("VentilatorConsole", "Start Mechanical Ventilation", "Maschinelle Beatmung starten"),
    ("VentilatorConsole", "Silence Apnea Alarm (120s)", "Apnoe-Alarm stummschalten (120s)"),
    ("VentilatorConsole", "CRITICAL: High Airway Pressure (%1 cmH2O)", "KRITISCH: Hoher Atemwegsdruck (%1 cmH2O)"),
]

TICKET_A = (
    "# Work Order — Ventilator HMI Ergonomics Engineer (`hmi_designer_ergonomics_eng`)\n\n"
    "Remediate the live **Qt5 Designer** ventilator form (`/srv/studio_project/ventilator_console.ui`) and commit the QSS/offscreen verification artifacts in Git repository `/workspace/vent_repo` (branch `release/4.0`):\n\n"
    "1. Review `/workspace/vent_repo/specs/ISO80601_Ventilator_HMI_Spec.pdf` and inspect the **ISO 80601 Ventilator Portal** open in Chromium (`http://127.0.0.1:19610`, `Adult ICU Ventilator Bounds` tab — do not use the Pediatric distractor tab!).\n"
    "2. In the open **Qt5 Designer** window on the desktop (`/srv/studio_project/ventilator_console.ui`), update `tidalSpinBox` (`minimum = 200`, `maximum = 800`, `singleStep = 10`) and `peepSpinBox` (`minimum = 5`, `maximum = 20`, `singleStep = 1`), set `minimumSize` on `startVentBtn` and `silenceAlarmBtn` to `width >= 260` and `height >= 50`, and save (`Ctrl+S`) in Qt5 Designer.\n"
    "3. Copy the saved `/srv/studio_project/ventilator_console.ui` to `/workspace/vent_repo/ui/ventilator_console.ui`, style `#apneaBanner` in `/workspace/vent_repo/src/vent_alarm.qss` (`#dc2626` background, `#ffffff` foreground), render `/workspace/vent_repo/build/ventilator_offscreen.png` via `PyQt5` (`QT_QPA_PLATFORM=offscreen`), write `/workspace/vent_repo/ergonomics_audit.json` (`signoff_id`, `tidal_range`, `peep_range`, `min_btn_size`), set `\"ergonomics_signoff\": \"ISO80601-VENT40-2026\"` in `/workspace/vent_repo/release_signoff.json`, and commit cleanly onto `release/4.0`.\n"
)

TICKET_B = (
    "# Work Order — Clinical Localization & Release Engineer (`clinical_linguist_release_eng`)\n\n"
    "Complete the German (`de_DE`) ICU ventilator localization in the live **Qt5 Linguist** window (`/srv/studio_project/ventilator_de.ts`) and compile/commit the binary release artifacts in `/workspace/vent_repo` (branch `release/4.0`):\n\n"
    "1. Review `/workspace/vent_repo/specs/ISO80601_Ventilator_HMI_Spec.pdf` and inspect the **ISO 80601 Ventilator Portal** in Chromium (`http://127.0.0.1:19610`, `Approved de_DE ICU Glossary` tab).\n"
    "2. In the open **Qt5 Linguist** window on the desktop (`/srv/studio_project/ventilator_de.ts`), enter the exact approved German translation for each of the 5 `VentilatorConsole` strings, mark each translation Done (`Ctrl+Return`), and save (`Ctrl+S`).\n"
    "3. Copy the saved `/srv/studio_project/ventilator_de.ts` to `/workspace/vent_repo/i18n/ventilator_de.ts`, compile `/workspace/vent_repo/build/ventilator_de.qm` via `lrelease`, register `../build/ventilator_de.qm` in `/workspace/vent_repo/resources/vent.qrc`, write `/workspace/vent_repo/l10n_audit.json` (`signoff_id`, `de_qm_sha256`, `message_count`), set `\"l10n_signoff\": \"ISO80601-VENT40-2026\"` in `/workspace/vent_repo/release_signoff.json`, and commit cleanly onto `release/4.0`.\n"
)

INIT_VENT_UI = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>VentilatorConsole</class>
 <widget class="QWidget" name="VentilatorConsole">
  <property name="geometry"><rect><x>0</x><y>0</y><width>720</width><height>420</height></rect></property>
  <property name="windowTitle"><string>ICU Ventilator Console</string></property>
  <layout class="QVBoxLayout" name="vlay">
   <item><widget class="QLabel" name="apneaBanner"><property name="text"><string>CRITICAL: High Airway Pressure (%1 cmH2O)</string></property></widget></item>
   <item>
    <layout class="QFormLayout" name="flay">
     <item row="0" column="0"><widget class="QLabel" name="l1"><property name="text"><string>Tidal Volume (mL)</string></property></widget></item>
     <item row="0" column="1"><widget class="QSpinBox" name="tidalSpinBox"><property name="minimum"><number>50</number></property><property name="maximum"><number>2000</number></property><property name="singleStep"><number>50</number></property></widget></item>
     <item row="1" column="0"><widget class="QLabel" name="l2"><property name="text"><string>PEEP Pressure (cmH2O)</string></property></widget></item>
     <item row="1" column="1"><widget class="QSpinBox" name="peepSpinBox"><property name="minimum"><number>0</number></property><property name="maximum"><number>45</number></property><property name="singleStep"><number>5</number></property></widget></item>
    </layout>
   </item>
   <item>
    <layout class="QHBoxLayout" name="blay">
     <item><widget class="QPushButton" name="startVentBtn"><property name="minimumSize"><size><width>100</width><height>28</height></size></property><property name="text"><string>Start Mechanical Ventilation</string></property></widget></item>
     <item><widget class="QPushButton" name="silenceAlarmBtn"><property name="minimumSize"><size><width>100</width><height>28</height></size></property><property name="text"><string>Silence Apnea Alarm (120s)</string></property></widget></item>
    </layout>
   </item>
  </layout>
 </widget>
 <resources/><connections/>
</ui>
"""

INIT_VENT_TS = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="de_DE">
  <context>
    <name>VentilatorConsole</name>
    <message><source>Tidal Volume (mL)</source><translation type="unfinished"></translation></message>
    <message><source>PEEP Pressure (cmH2O)</source><translation type="unfinished"></translation></message>
    <message><source>Start Mechanical Ventilation</source><translation type="unfinished">Beatmung stoppen</translation></message>
    <message><source>Silence Apnea Alarm (120s)</source><translation type="unfinished"></translation></message>
    <message><source>CRITICAL: High Airway Pressure (%1 cmH2O)</source><translation type="unfinished">WARNUNG: Druck hoch</translation></message>
  </context>
</TS>
"""


def build(workspace_root: Path, tickets_root: Path) -> None:
    vr = workspace_root / "shared" / "vent_repo"
    for sub in ("ui", "src", "i18n", "resources", "build", "specs"):
        (vr / sub).mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "shared" / ".studio_seed"
    seed.mkdir(parents=True, exist_ok=True)

    (seed / "ventilator_console.ui").write_text(INIT_VENT_UI, encoding="utf-8")
    (seed / "ventilator_de.ts").write_text(INIT_VENT_TS, encoding="utf-8")
    (vr / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    (vr / "build" / ".gitkeep").write_text("", encoding="utf-8")
    (vr / "ui" / "ventilator_console.ui").write_text(INIT_VENT_UI, encoding="utf-8")
    (vr / "i18n" / "ventilator_de.ts").write_text(INIT_VENT_TS, encoding="utf-8")
    (vr / "src" / "vent_alarm.qss").write_text("#apneaBanner { background-color: #fde047; color: #854d0e; }\n", encoding="utf-8")
    (vr / "resources" / "vent.qrc").write_text('<!DOCTYPE RCC><RCC version="1.0"><qresource prefix="/i18n"></qresource></RCC>\n', encoding="utf-8")
    write_json(vr / "release_signoff.json", {"branch": "release/4.0", "ergonomics_signoff": "PENDING", "l10n_signoff": "PENDING"})

    write_pdf_manual(
        vr / "specs" / "ISO80601_Ventilator_HMI_Spec.pdf",
        "ISO 80601-2-12 Adult ICU Ventilator HMI & Localization Spec",
        [
            (
                "1. Live Qt5 Designer & Qt5 Linguist Authoring",
                [
                    "Master files /srv/studio_project/ventilator_console.ui and /srv/studio_project/ventilator_de.ts are open in Qt5 Designer and Qt5 Linguist on the desktop. Save your GUI edits in /srv/studio_project/ first, then sync into /workspace/vent_repo/ and commit on branch release/4.0.",
                ],
            ),
            (
                "2. Safety Bounds, Glove Buttons & German Glossary",
                [
                    "Select the Adult ICU Ventilator profile (not Pediatric!) in the Chromium portal for SpinBox bounds and minimum button dimensions, and use the Approved de_DE ICU Glossary for all 5 German translations (preserving '%1').",
                ],
            ),
        ],
    )
    subprocess.run(
        ["bash", "-lc", f"cd '{vr}' && git init -b release/4.0 && git config user.name 'Vent Bot' && git config user.email 'vent@local' && git add -A && git commit -m 'Init release/4.0'"],
        check=True, capture_output=True, timeout=25,
    )
    (tickets_root / "hmi_designer_ergonomics_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "clinical_linguist_release_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "hmi_designer_ergonomics_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "clinical_linguist_release_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "pediatric", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw10_sess" in ck) and (ck["aw10_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw10_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 ISO 80601 Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["pediatric"])[0]
                with lock:
                    if t in ("pediatric", "adult_icu", "glossary") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "pediatric":
                body = "<h2>Pediatric Mode (DO NOT APPLY TO ADULT ICU 4.0)</h2><p>tidalSpinBox: 30..250 mL | peepSpinBox: 3..12 cmH2O</p>"
            elif cur == "adult_icu":
                body = f"""<h2>Adult ICU Ventilator Bounds (release/4.0)</h2>
                <p><b>Signoff ID:</b> <code>{VENT_SIGNOFF_ID}</code></p>
                <p><b>tidalSpinBox:</b> <code>200 .. 800 mL, step 10</code> | <b>peepSpinBox:</b> <code>5 .. 20 cmH2O, step 1</code></p>
                <p><b>Glove Action Buttons:</b> <code>minimumSize &gt;= 260 x 50 px</code> | <b>#apneaBanner:</b> <code>#dc2626 / #ffffff</code></p>"""
            else:
                rows = "".join(f"<tr><td>{s}</td><td><b>{d}</b></td></tr>" for _c, s, d in VENT_STRINGS)
                body = f"""<h2>Approved de_DE ICU Glossary ({VENT_SIGNOFF_ID})</h2>
                <table border="1" cellpadding="7" style="border-collapse:collapse;"><tr><th>English Source</th><th>Approved de_DE</th></tr>{rows}</table>"""
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>ISO 80601 Ventilator Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:24px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 16px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:18px;padding:22px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>ISO 80601 Ventilator Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=pediatric">Pediatric (3.x)</a><a href="/tab?id=adult_icu">Adult ICU Ventilator Bounds</a><a href="/tab?id=glossary">Approved de_DE ICU Glossary</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1180, 780))
    seed = workspace_root / "shared" / ".studio_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "ventilator_console.ui", sp / "ventilator_console.ui")
    shutil.copy2(seed / "ventilator_de.ts", sp / "ventilator_de.ts")
    if "hmi_designer_ergonomics_eng" in roles:
        launch_studio_app("nohup designer '/srv/studio_project/ventilator_console.ui' >/tmp/aw10_des.log 2>&1 </dev/null &", wait_s=2.4)
    if "clinical_linguist_release_eng" in roles:
        launch_studio_app("nohup linguist '/srv/studio_project/ventilator_de.ts' >/tmp/aw10_lin.log 2>&1 </dev/null &", wait_s=2.4)


CLEAN_VENT_UI = (
    INIT_VENT_UI.replace("<number>50</number>", "<number>200</number>", 1)
    .replace("<number>2000</number>", "<number>800</number>", 1)
    .replace("<number>50</number>", "<number>10</number>", 1)
    .replace("<number>0</number>", "<number>5</number>", 1)
    .replace("<number>45</number>", "<number>20</number>", 1)
    .replace("<number>5</number></property></widget></item>\n    </layout>", "<number>1</number></property></widget></item>\n    </layout>")
    .replace("<width>100</width><height>28</height>", "<width>268</width><height>52</height>")
)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    vr = workspace_root / "shared" / "vent_repo"
    sp = Path("/srv/studio_project")
    if role == "hmi_designer_ergonomics_eng":
        (sp / "ventilator_console.ui").write_text(CLEAN_VENT_UI, encoding="utf-8")
        (vr / "ui" / "ventilator_console.ui").write_text(CLEAN_VENT_UI, encoding="utf-8")
        (vr / "src" / "vent_alarm.qss").write_text("#apneaBanner { background-color: #dc2626; color: #ffffff; }\n", encoding="utf-8")
        subprocess.run(
            [
                "python3", "-c",
                f"import os,sys; os.environ['QT_QPA_PLATFORM']='offscreen'; from PyQt5 import QtWidgets,uic; app=QtWidgets.QApplication(sys.argv); w=uic.loadUi({str(vr/'ui'/'ventilator_console.ui')!r}); w.setStyleSheet(open({str(vr/'src'/'vent_alarm.qss')!r}).read()); w.show(); app.processEvents(); w.grab().save({str(vr/'build'/'ventilator_offscreen.png')!r}, 'PNG')",
            ],
            check=True, capture_output=True, timeout=25,
        )
        write_json(vr / "ergonomics_audit.json", {"signoff_id": VENT_SIGNOFF_ID, "tidal_range": [200, 800, 10], "peep_range": [5, 20, 1], "min_btn_size": [268, 52]})
        if cooperative:
            with resource_lock("aw10_git"):
                rs = read_json_safe(vr / "release_signoff.json")
                rs["ergonomics_signoff"] = VENT_SIGNOFF_ID
                write_json(vr / "release_signoff.json", rs)
                subprocess.run(["bash", "-lc", f"cd '{vr}' && git add ui/ventilator_console.ui src/vent_alarm.qss build/ventilator_offscreen.png ergonomics_audit.json release_signoff.json && (git diff --cached --quiet || git commit -m 'Ergonomics 4.0')"], check=True, capture_output=True, timeout=20)
        else:
            write_json(vr / "release_signoff.json", {"branch": "release/4.0", "ergonomics_signoff": VENT_SIGNOFF_ID})
    elif role == "clinical_linguist_release_eng":
        if not cooperative:
            subprocess.run(["bash", "-lc", f"cd '{vr}' && git checkout -- . && git clean -fd"], check=True, capture_output=True, timeout=20)
        ts_lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", '<TS version="2.1" language="de_DE"><context><name>VentilatorConsole</name>']
        for _c, s, d in VENT_STRINGS:
            ts_lines.append(f"<message><source>{s}</source><translation>{d}</translation></message>")
        ts_lines.append("</context></TS>\n")
        ts_xml = "\n".join(ts_lines)
        (sp / "ventilator_de.ts").write_text(ts_xml, encoding="utf-8")
        (vr / "i18n" / "ventilator_de.ts").write_text(ts_xml, encoding="utf-8")
        qm_p = vr / "build" / "ventilator_de.qm"
        subprocess.run(["lrelease", str(vr / "i18n" / "ventilator_de.ts"), "-qm", str(qm_p)], check=True, capture_output=True, timeout=20)
        (vr / "resources" / "vent.qrc").write_text('<!DOCTYPE RCC><RCC version="1.0"><qresource prefix="/i18n"><file>../build/ventilator_de.qm</file></qresource></RCC>\n', encoding="utf-8")
        write_json(vr / "l10n_audit.json", {"signoff_id": VENT_SIGNOFF_ID, "de_qm_sha256": hashlib.sha256(qm_p.read_bytes()).hexdigest(), "message_count": 5})
        if cooperative:
            with resource_lock("aw10_git"):
                rs = read_json_safe(vr / "release_signoff.json")
                rs["l10n_signoff"] = VENT_SIGNOFF_ID
                write_json(vr / "release_signoff.json", rs)
                subprocess.run(["bash", "-lc", f"cd '{vr}' && git add i18n/ventilator_de.ts build/ventilator_de.qm resources/vent.qrc l10n_audit.json release_signoff.json && (git diff --cached --quiet || git commit -m 'L10n 4.0')"], check=True, capture_output=True, timeout=20)
        else:
            write_json(vr / "release_signoff.json", {"branch": "release/4.0", "l10n_signoff": VENT_SIGNOFF_ID})
    subprocess.run(["chmod", "-R", "a+rX", str(sp)], capture_output=True, timeout=10)


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("hmi_designer_ergonomics_eng", workspace_root, cooperative=False)
    solve_role("clinical_linguist_release_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "hmi_designer_ergonomics_eng", workspace_root, True)
        fb = pool.submit(solve_role, "clinical_linguist_release_eng", workspace_root, True)
        fa.result()
        fb.result()


def _probe_vent_qt(sp_ui: Path, repo_qm: Path) -> dict[str, Any]:
    code = f"""
import json, os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtCore, QtWidgets, uic
app = QtWidgets.QApplication(sys.argv)
out = {{}}
if os.path.isfile({str(sp_ui)!r}):
    w = uic.loadUi({str(sp_ui)!r})
    t = w.findChild(QtWidgets.QSpinBox, "tidalSpinBox")
    p = w.findChild(QtWidgets.QSpinBox, "peepSpinBox")
    b1 = w.findChild(QtWidgets.QPushButton, "startVentBtn")
    b2 = w.findChild(QtWidgets.QPushButton, "silenceAlarmBtn")
    if t: out["tidal"] = [t.minimum(), t.maximum(), t.singleStep()]
    if p: out["peep"] = [p.minimum(), p.maximum(), p.singleStep()]
    if b1 and b2: out["btns"] = [[b1.minimumWidth(), b1.minimumHeight()], [b2.minimumWidth(), b2.minimumHeight()]]
tr = QtCore.QTranslator()
if os.path.isfile({str(repo_qm)!r}) and tr.load({str(repo_qm)!r}):
    out["tr"] = {{s: tr.translate("VentilatorConsole", s) for _c, s, _d in {VENT_STRINGS!r}}}
print("AW10_JSON:" + json.dumps(out, ensure_ascii=False))
"""
    try:
        cp = subprocess.run(["python3", "-c", code], check=True, capture_output=True, text=True, timeout=25)
        for ln in cp.stdout.splitlines():
            if ln.startswith("AW10_JSON:"):
                return json.loads(ln.split("AW10_JSON:", 1)[1])
    except Exception:
        pass
    return {}


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    vr = workspace_root / "shared" / "vent_repo"
    sp = Path("/srv/studio_project")
    rt_studio = _probe_vent_qt(sp / "ventilator_console.ui", vr / "build" / "ventilator_de.qm")
    ja = read_json_safe(vr / "ergonomics_audit.json")
    jb = read_json_safe(vr / "l10n_audit.json")
    rs = read_json_safe(vr / "release_signoff.json")
    qss_txt = (vr / "src" / "vent_alarm.qss").read_text(encoding="utf-8", errors="replace").lower() if (vr / "src" / "vent_alarm.qss").is_file() else ""
    studio_ts = (sp / "ventilator_de.ts").read_text(encoding="utf-8", errors="replace") if (sp / "ventilator_de.ts").is_file() else ""
    git_st = subprocess.run(["bash", "-lc", f"cd '{vr}' && git status --porcelain"], capture_output=True, text=True, timeout=10)
    git_clean = git_st.returncode == 0 and git_st.stdout.strip() == ""

    btns = rt_studio.get("btns") or []
    btns_ok = len(btns) == 2 and all(w >= 260 and h >= 50 for w, h in btns)
    tr_map = rt_studio.get("tr") or {}
    tr_ok = all(tr_map.get(s) == d for _c, s, d in VENT_STRINGS)
    studio_ts_done = 'type="unfinished"' not in studio_ts and all(d in studio_ts for _c, _s, d in VENT_STRINGS)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_signoff", ja.get("signoff_id") == VENT_SIGNOFF_ID, 1.0, "signoff_id mismatch"),
        ("a_gui_tidal", rt_studio.get("tidal") == [200, 800, 10], 2.2, f"Live Designer tidalSpinBox mismatch ({rt_studio.get('tidal')})"),
        ("a_gui_peep", rt_studio.get("peep") == [5, 20, 1], 2.0, f"Live Designer peepSpinBox mismatch ({rt_studio.get('peep')})"),
        ("a_gui_btns", btns_ok, 2.2, f"Live Designer button minimumSize < 260x50 ({btns})"),
        ("a_qss_png", "#dc2626" in qss_txt and (vr / "build" / "ventilator_offscreen.png").is_file(), 1.6, "vent_alarm.qss or ventilator_offscreen.png missing"),
        ("a_rel_git", rs.get("ergonomics_signoff") == VENT_SIGNOFF_ID and git_clean, 1.6, "release_signoff.json ergonomics_signoff or clean git status failed"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_signoff", jb.get("signoff_id") == VENT_SIGNOFF_ID, 1.0, "signoff_id mismatch"),
        ("b_gui_linguist_ts", studio_ts_done, 2.6, "/srv/studio_project/ventilator_de.ts not completed/saved in Qt5 Linguist"),
        ("b_qm_translations", tr_ok, 2.4, "Compiled ventilator_de.qm missing approved German ICU strings"),
        ("b_qrc", "ventilator_de.qm" in ((vr / "resources" / "vent.qrc").read_text(encoding="utf-8", errors="replace") if (vr / "resources" / "vent.qrc").is_file() else ""), 1.4, "vent.qrc missing ventilator_de.qm"),
        ("b_rel_git", rs.get("l10n_signoff") == VENT_SIGNOFF_ID and git_clean, 1.6, "release_signoff.json l10n_signoff or clean git status failed"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_designer_linguist_and_git_integrated",
            btns_ok and studio_ts_done and tr_ok and git_clean and rs.get("ergonomics_signoff") == VENT_SIGNOFF_ID and rs.get("l10n_signoff") == VENT_SIGNOFF_ID,
            2.5,
            "Shared Qt5 Designer/Linguist focus contention or Git/release_signoff.json overwrite broke combined release/4.0",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"hmi_designer_ergonomics_eng": TICKET_A, "clinical_linguist_release_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
