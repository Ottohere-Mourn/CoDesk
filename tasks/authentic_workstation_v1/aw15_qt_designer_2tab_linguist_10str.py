"""AW-15: Pure-GUI Qt5 Designer Dialysis Console + Qt5 Linguist 8-String Localization (No CLI Studio Mount)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
from pathlib import Path
import secrets
import shutil
import sqlite3
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
    "id": "AW-15",
    "slug": "qt_designer_2tab_linguist_10str",
    "title": "Pure-GUI Qt5 Designer Dialysis Console & Qt5 Linguist 8-String ICU Localization",
    "domain": "Medical Device Qt5 GUI Authoring & Localization (Qt5 Designer + Qt5 Linguist + Chromium + SQLite)",
    "track": "track2_shared_ws",
    "workspace_mode": "shared",
    "portal_port": 19615,
    "roles": ("dialysis_ui_eng", "dialysis_l10n_eng"),
    "iso_role_timeout_s": 1200,
    "conc_role_timeout_s": 1500,
    "max_cua_calls": 140,
}

DIALYSIS_CERT = "IEC60601-HD-2026"
DIAL_STRINGS = [
    ("DialysisPanel", "Blood Flow Rate (mL/min)", "Blutflussrate (mL/min)"),
    ("DialysisPanel", "Ultrafiltration Goal (mL)", "Ultrafiltrationsziel (mL)"),
    ("DialysisPanel", "Heparin Bolus (IU)", "Heparin-Bolus (IE)"),
    ("DialysisPanel", "Start Hemodialysis", "Hämodialyse starten"),
    ("DialysisPanel", "Clamp Venous Line", "Venöse Linie abklemmen"),
    ("DialysisPanel", "Bypass Dialysate", "Dialysat-Bypass aktivieren"),
    ("DialysisPanel", "ALARM: Transmembrane Pressure (%1 mmHg)", "ALARM: Transmembrandruck (%1 mmHg)"),
    ("DialysisPanel", "Air Detector Armed", "Luftdetektor scharfgeschaltet"),
]

TICKET_A = (
    "# Work Order — Hemodialysis Qt5 UI & Safety Engineer (`dialysis_ui_eng`)\n\n"
    "Configure the live **Qt5 Designer** form (`dialysis_panel.ui` open on the desktop) and compute the Daugirdas `Kt/V` clearance audit in `/workspace/dialysis_safety`:\n\n"
    "1. Read `/workspace/dialysis_safety/specs/IEC60601_Dialysis_Spec.pdf`, query `/workspace/dialysis_safety/patient_runs.sqlite`, and inspect the **IEC 60601-2-16 Dialysis Portal** in Chromium (`http://127.0.0.1:19615`, `Acute ICU Hemodialysis` tab — ignore the Home Peritoneal distractor tab!).\n"
    "2. In the open **Qt5 Designer** window (`dialysis_panel.ui`), configure:\n"
    "   - `bloodFlowSpin`: `minimum = 50`, `maximum = 500`, `singleStep = 10`\n"
    "   - `ufGoalSpin`: `minimum = 100`, `maximum = 4000`, `singleStep = 50`\n"
    "   - `heparinSpin`: `minimum = 0`, `maximum = 5000`, `singleStep = 250`\n"
    "   - `startHdBtn` and `clampVenousBtn`: `minimumSize` width `>= 250`, height `>= 48`\n"
    "   and save (`Ctrl+S`) in Qt5 Designer.\n"
    "3. Compute mean single-pool Daugirdas `sp_ktv` (3 decimals) across the 3 ICU treatment runs in `patient_runs.sqlite`, write `/workspace/dialysis_safety/ui_ktv_audit.json` (`cert_id`, `mean_sp_ktv`, `adequate_run_ids`), and set `\"ui_cert\": \"IEC60601-HD-2026\"` in `/workspace/dialysis_safety/release_gate.json`.\n"
)

TICKET_B = (
    "# Work Order — Hemodialysis Clinical Localization & TMP Engineer (`dialysis_l10n_eng`)\n\n"
    "Complete all 8 German (`de_DE`) translations in the live **Qt5 Linguist** window (`dialysis_de.ts` open on the desktop) and compute the transmembrane pressure (`TMP`) safety audit in `/workspace/dialysis_safety`:\n\n"
    "1. Read `/workspace/dialysis_safety/specs/IEC60601_Dialysis_Spec.pdf`, query `/workspace/dialysis_safety/patient_runs.sqlite`, and inspect the **IEC 60601-2-16 Dialysis Portal** in Chromium (`http://127.0.0.1:19615`, `Approved de_DE Dialysis Glossary` tab).\n"
    "2. In the open **Qt5 Linguist** window (`dialysis_de.ts`), enter the exact approved German string for all 8 `DialysisPanel` entries, mark each translation Done (`Ctrl+Return`), and save (`Ctrl+S`).\n"
    "3. Compute transmembrane pressure `tmp_mmhg = (p_art + p_ven)/2 - p_dial - oncotic_offset_mmhg` (1 decimal) for each run in `patient_runs.sqlite`, write `/workspace/dialysis_safety/tmp_l10n_audit.json` (`cert_id`, `max_tmp_mmhg`, `alarm_triggered_runs`), and set `\"l10n_cert\": \"IEC60601-HD-2026\"` in `/workspace/dialysis_safety/release_gate.json`.\n"
)

INIT_DIAL_UI = """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>DialysisPanel</class>
 <widget class="QWidget" name="DialysisPanel">
  <property name="geometry"><rect><x>0</x><y>0</y><width>760</width><height>460</height></rect></property>
  <property name="windowTitle"><string>Acute Hemodialysis Console</string></property>
  <layout class="QVBoxLayout" name="vl">
   <item>
    <layout class="QFormLayout" name="fl">
     <item row="0" column="0"><widget class="QLabel" name="la"><property name="text"><string>Blood Flow Rate (mL/min)</string></property></widget></item>
     <item row="0" column="1"><widget class="QSpinBox" name="bloodFlowSpin"><property name="minimum"><number>10</number></property><property name="maximum"><number>900</number></property><property name="singleStep"><number>1</number></property></widget></item>
     <item row="1" column="0"><widget class="QLabel" name="lb"><property name="text"><string>Ultrafiltration Goal (mL)</string></property></widget></item>
     <item row="1" column="1"><widget class="QSpinBox" name="ufGoalSpin"><property name="minimum"><number>0</number></property><property name="maximum"><number>9000</number></property><property name="singleStep"><number>10</number></property></widget></item>
     <item row="2" column="0"><widget class="QLabel" name="lc"><property name="text"><string>Heparin Bolus (IU)</string></property></widget></item>
     <item row="2" column="1"><widget class="QSpinBox" name="heparinSpin"><property name="minimum"><number>0</number></property><property name="maximum"><number>9999</number></property><property name="singleStep"><number>100</number></property></widget></item>
    </layout>
   </item>
   <item>
    <layout class="QHBoxLayout" name="bl">
     <item><widget class="QPushButton" name="startHdBtn"><property name="minimumSize"><size><width>90</width><height>28</height></size></property><property name="text"><string>Start Hemodialysis</string></property></widget></item>
     <item><widget class="QPushButton" name="clampVenousBtn"><property name="minimumSize"><size><width>90</width><height>28</height></size></property><property name="text"><string>Clamp Venous Line</string></property></widget></item>
    </layout>
   </item>
  </layout>
 </widget>
 <resources/><connections/>
</ui>
"""


def _init_dial_ts() -> str:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", '<TS version="2.1" language="de_DE"><context><name>DialysisPanel</name>']
    for _c, s, _d in DIAL_STRINGS:
        lines.append(f'<message><source>{s}</source><translation type="unfinished"></translation></message>')
    lines.append("</context></TS>\n")
    return "\n".join(lines)


PATIENT_RUNS = [
    ("HD-01", 68.0, 22.0, 4.0, 2.4, 72.0, 195.0, 165.0, -90.0),
    ("HD-02", 74.0, 19.0, 3.5, 1.8, 78.0, 220.0, 190.0, -145.0),
    ("HD-03", 62.0, 28.0, 4.0, 2.8, 66.0, 180.0, 150.0, -70.0),
]
ONCOTIC_OFFSET = 24.0
TMP_ALARM_LIMIT = 300.0


def compute_aw15_oracle() -> dict[str, Any]:
    # Daugirdas 2nd gen spKt/V = -ln(R - 0.008*t) + (4 - 3.5*R) * (UF_L / W_post_kg), R = post_bun / pre_bun
    ktvs = []
    adeq = []
    tmps = []
    alm = []
    for rid, pre_bun, post_bun, t_hr, uf_l, w_kg, p_art, p_ven, p_dial in PATIENT_RUNS:
        r = post_bun / pre_bun
        ktv = -math.log(r - 0.008 * t_hr) + (4.0 - 3.5 * r) * (uf_l / w_kg)
        ktvs.append(ktv)
        if ktv >= 1.20:
            adeq.append(rid)
        tmp = round(0.5 * (p_art + p_ven) - p_dial - ONCOTIC_OFFSET, 1)
        tmps.append(tmp)
        if tmp > TMP_ALARM_LIMIT:
            alm.append(rid)
    return {
        "cert_id": DIALYSIS_CERT,
        "mean_sp_ktv": round(sum(ktvs) / len(ktvs), 3),
        "adequate_run_ids": sorted(adeq),
        "max_tmp_mmhg": max(tmps),
        "alarm_triggered_runs": sorted(alm),
    }


def build(workspace_root: Path, tickets_root: Path) -> None:
    ds = workspace_root / "shared" / "dialysis_safety"
    (ds / "specs").mkdir(parents=True, exist_ok=True)
    seed = workspace_root / "_desk_seed"
    seed.mkdir(parents=True, exist_ok=True)
    (seed / "dialysis_panel.ui").write_text(INIT_DIAL_UI, encoding="utf-8")
    (seed / "dialysis_de.ts").write_text(_init_dial_ts(), encoding="utf-8")
    write_json(ds / "release_gate.json", {"ui_cert": "PENDING", "l10n_cert": "PENDING"})

    db_p = ds / "patient_runs.sqlite"
    db_p.unlink(missing_ok=True)
    con = sqlite3.connect(db_p)
    con.execute("CREATE TABLE hd_runs (run_id TEXT PRIMARY KEY, pre_bun_mg_dl REAL, post_bun_mg_dl REAL, session_hours REAL, uf_volume_liters REAL, post_weight_kg REAL, p_arterial_pos_mmhg REAL, p_venous_mmhg REAL, p_dialysate_mmhg REAL)")
    con.executemany("INSERT INTO hd_runs VALUES (?,?,?,?,?,?,?,?,?)", PATIENT_RUNS)
    con.commit()
    con.close()

    write_pdf_manual(
        ds / "specs" / "IEC60601_Dialysis_Spec.pdf",
        "IEC 60601-2-16 Hemodialysis Console & Safety Equations",
        [
            ("1. Daugirdas spKt/V Adequacy", ["R = post_bun / pre_bun; spKt/V = -ln(R - 0.008*session_hours) + (4 - 3.5*R)*(uf_volume_liters / post_weight_kg). Runs with spKt/V >= 1.20 are adequate."]),
            ("2. Effective Transmembrane Pressure (TMP)", ["TMP = (p_arterial_pos_mmhg + p_venous_mmhg)/2 - p_dialysate_mmhg - oncotic_offset_mmhg (retrieve oncotic_offset_mmhg and TMP alarm ceiling from the Dialysis Portal)."]),
        ],
    )
    (tickets_root / "dialysis_ui_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "dialysis_l10n_eng").mkdir(parents=True, exist_ok=True)
    (tickets_root / "dialysis_ui_eng" / "task.md").write_text(TICKET_A, encoding="utf-8")
    (tickets_root / "dialysis_l10n_eng" / "task.md").write_text(TICKET_B, encoding="utf-8")


def serve(port: int, workspace_root: Path, state_dir: Path, boot_file: Path) -> None:
    tok = secrets.token_hex(16)
    state_file = state_dir / "service_state.json"
    lock = threading.Lock()
    state: dict[str, Any] = {"active_tab": "home_pd", "switches": 0}
    write_json(state_file, state)
    write_json(boot_file, {"url": f"http://127.0.0.1:{port}/auth?token={tok}"})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _authed(self) -> bool:
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            return ("aw15_sess" in ck) and (ck["aw15_sess"].value == tok)

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
                    self._send(302, b"", hdrs=[("Set-Cookie", f"aw15_sess={tok}; HttpOnly; Path=/"), ("Location", "/")])
                    return
                self._send(403, b"Forbidden")
                return
            if not self._authed():
                self._send(401, b"<h3>401 Dialysis Portal Session Required</h3>")
                return
            if parsed.path == "/tab":
                t = (qs.get("id") or ["home_pd"])[0]
                with lock:
                    if t in ("home_pd", "icu_hd", "glossary") and t != state["active_tab"]:
                        state["active_tab"] = t
                        state["switches"] = int(state["switches"]) + 1
                        write_json(state_file, state)
                self._send(302, b"", hdrs=[("Location", "/")])
                return
            with lock:
                cur = state["active_tab"]
            if cur == "home_pd":
                body = "<h2>Home Peritoneal Dialysis (DO NOT USE FOR ACUTE ICU HD)</h2><p>Dwell: 1500..2500 mL</p>"
            elif cur == "icu_hd":
                body = f"<h2>Acute ICU Hemodialysis ({DIALYSIS_CERT})</h2><p><code>oncotic_offset_mmhg = 24.0</code> | <code>TMP_alarm_limit = 300.0 mmHg</code></p>"
            else:
                rows = "".join(f"<tr><td>{s}</td><td><b>{d}</b></td></tr>" for _c, s, d in DIAL_STRINGS)
                body = f"<h2>Approved de_DE Dialysis Glossary ({DIALYSIS_CERT})</h2><table border='1' cellpadding='6' style='border-collapse:collapse;'><tr><th>Source</th><th>de_DE</th></tr>{rows}</table>"
            html = f"""<!doctype html><html><head><meta charset="utf-8"/><title>IEC 60601-2-16 Portal</title>
            <style>body{{font-family:DejaVu Sans,sans-serif;padding:22px;background:#f8fafc;}}
            .nav a{{display:inline-block;padding:10px 15px;margin-right:10px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:700;}}
            .card{{margin-top:16px;padding:20px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;}}</style></head>
            <body><h1>IEC 60601-2-16 Dialysis Portal ({cur.upper()})</h1>
            <div class="nav"><a href="/tab?id=home_pd">Home Peritoneal</a><a href="/tab?id=icu_hd">Acute ICU Hemodialysis</a><a href="/tab?id=glossary">Approved de_DE Dialysis Glossary</a></div>
            <div class="card">{body}</div></body></html>"""
            self._send(200, html.encode("utf-8"))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_apps(workspace_root: Path, state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or TASK_META["roles"])
    boot_studio_browser(state_dir, window_size=(1160, 760))
    seed = workspace_root / "_desk_seed"
    sp = Path("/srv/studio_project")
    sp.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed / "dialysis_panel.ui", sp / "dialysis_panel.ui")
    shutil.copy2(seed / "dialysis_de.ts", sp / "dialysis_de.ts")
    if "dialysis_ui_eng" in roles:
        launch_studio_app("nohup designer '/srv/studio_project/dialysis_panel.ui' >/tmp/aw15_des.log 2>&1 </dev/null &", wait_s=2.4)
    if "dialysis_l10n_eng" in roles:
        launch_studio_app("nohup linguist '/srv/studio_project/dialysis_de.ts' >/tmp/aw15_lin.log 2>&1 </dev/null &", wait_s=2.4)


def solve_role(role: str, workspace_root: Path, cooperative: bool = True) -> None:
    ds = workspace_root / "shared" / "dialysis_safety"
    sp = Path("/srv/studio_project")
    ora = compute_aw15_oracle()
    if role == "dialysis_ui_eng":
        ui_clean = (
            INIT_DIAL_UI.replace("<number>10</number>", "<number>50</number>", 1)
            .replace("<number>900</number>", "<number>500</number>", 1)
            .replace("<number>1</number>", "<number>10</number>", 1)
            .replace("<number>0</number>", "<number>100</number>", 1)
            .replace("<number>9000</number>", "<number>4000</number>", 1)
            .replace("<number>10</number></property></widget></item>\n     <item row=\"2\"", "<number>50</number></property></widget></item>\n     <item row=\"2\"", 1)
            .replace("<number>9999</number>", "<number>5000</number>", 1)
            .replace("<number>100</number></property></widget></item>\n    </layout>", "<number>250</number></property></widget></item>\n    </layout>", 1)
            .replace("<width>90</width><height>28</height>", "<width>256</width><height>50</height>")
        )
        (sp / "dialysis_panel.ui").write_text(ui_clean, encoding="utf-8")
        write_json(ds / "ui_ktv_audit.json", {"cert_id": DIALYSIS_CERT, "mean_sp_ktv": ora["mean_sp_ktv"], "adequate_run_ids": ora["adequate_run_ids"]})
        if cooperative:
            with resource_lock("aw15_gate"):
                rg = read_json_safe(ds / "release_gate.json")
                rg["ui_cert"] = DIALYSIS_CERT
                write_json(ds / "release_gate.json", rg)
        else:
            write_json(ds / "release_gate.json", {"ui_cert": DIALYSIS_CERT})
    elif role == "dialysis_l10n_eng":
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", '<TS version="2.1" language="de_DE"><context><name>DialysisPanel</name>']
        for _c, s, d in DIAL_STRINGS:
            lines.append(f"<message><source>{s}</source><translation>{d}</translation></message>")
        lines.append("</context></TS>\n")
        (sp / "dialysis_de.ts").write_text("\n".join(lines), encoding="utf-8")
        write_json(ds / "tmp_l10n_audit.json", {"cert_id": DIALYSIS_CERT, "max_tmp_mmhg": ora["max_tmp_mmhg"], "alarm_triggered_runs": ora["alarm_triggered_runs"]})
        if cooperative:
            with resource_lock("aw15_gate"):
                rg = read_json_safe(ds / "release_gate.json")
                rg["l10n_cert"] = DIALYSIS_CERT
                write_json(ds / "release_gate.json", rg)
        else:
            write_json(ds / "release_gate.json", {"l10n_cert": DIALYSIS_CERT})


def sim_contention(workspace_root: Path, state_dir: Path) -> None:
    solve_role("dialysis_ui_eng", workspace_root, cooperative=False)
    solve_role("dialysis_l10n_eng", workspace_root, cooperative=False)


def careful_conc(workspace_root: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(solve_role, "dialysis_ui_eng", workspace_root, True)
        fb = pool.submit(solve_role, "dialysis_l10n_eng", workspace_root, True)
        fa.result()
        fb.result()


def grade(
    workspace_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
    active_mode: str = "shared",
) -> dict[str, Any]:
    import json as _json

    ds = workspace_root / "shared" / "dialysis_safety"
    sp = Path("/srv/studio_project")
    ora = compute_aw15_oracle()
    ja = read_json_safe(ds / "ui_ktv_audit.json")
    jb = read_json_safe(ds / "tmp_l10n_audit.json")
    rg = read_json_safe(ds / "release_gate.json")

    probe = f"""
import json, os, sys, tempfile, subprocess
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtCore, QtWidgets, uic
app = QtWidgets.QApplication(sys.argv)
out = {{}}
uip = {str(sp / 'dialysis_panel.ui')!r}
tsp = {str(sp / 'dialysis_de.ts')!r}
if os.path.isfile(uip):
    w = uic.loadUi(uip)
    for k in ("bloodFlowSpin", "ufGoalSpin", "heparinSpin"):
        sb = w.findChild(QtWidgets.QSpinBox, k)
        if sb: out[k] = [sb.minimum(), sb.maximum(), sb.singleStep()]
    b1 = w.findChild(QtWidgets.QPushButton, "startHdBtn")
    b2 = w.findChild(QtWidgets.QPushButton, "clampVenousBtn")
    if b1 and b2: out["btns"] = [[b1.minimumWidth(), b1.minimumHeight()], [b2.minimumWidth(), b2.minimumHeight()]]
if os.path.isfile(tsp):
    qmp = "/tmp/aw15_eval.qm"
    subprocess.run(["lrelease", tsp, "-qm", qmp], capture_output=True, timeout=15)
    tr = QtCore.QTranslator()
    if os.path.isfile(qmp) and tr.load(qmp):
        out["tr"] = {{s: tr.translate("DialysisPanel", s) for _c, s, _d in {DIAL_STRINGS!r}}}
print("AW15_OUT:" + json.dumps(out, ensure_ascii=False))
"""
    rt = {}
    cp = subprocess.run(["python3", "-c", probe], capture_output=True, text=True, timeout=25)
    for ln in cp.stdout.splitlines():
        if ln.startswith("AW15_OUT:"):
            rt = _json.loads(ln.split("AW15_OUT:", 1)[1])

    ts_raw = (sp / "dialysis_de.ts").read_text(encoding="utf-8", errors="replace") if (sp / "dialysis_de.ts").is_file() else ""
    btns = rt.get("btns") or []
    btns_ok = len(btns) == 2 and all(w >= 250 and h >= 48 for w, h in btns)
    tr_map = rt.get("tr") or {}
    tr_count = sum(1 for _c, s, d in DIAL_STRINGS if tr_map.get(s) == d)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_ktv", isinstance(ja.get("mean_sp_ktv"), (int, float)) and abs(float(ja["mean_sp_ktv"]) - ora["mean_sp_ktv"]) <= 0.02 and sorted(ja.get("adequate_run_ids") or []) == ora["adequate_run_ids"], 2.0, f"mean_sp_ktv mismatch ({ora['mean_sp_ktv']})"),
        ("a_gui_bf", rt.get("bloodFlowSpin") == [50, 500, 10], 1.8, f"Designer bloodFlowSpin mismatch ({rt.get('bloodFlowSpin')})"),
        ("a_gui_uf", rt.get("ufGoalSpin") == [100, 4000, 50], 1.8, f"Designer ufGoalSpin mismatch ({rt.get('ufGoalSpin')})"),
        ("a_gui_hep", rt.get("heparinSpin") == [0, 5000, 250], 1.8, f"Designer heparinSpin mismatch ({rt.get('heparinSpin')})"),
        ("a_gui_btns", btns_ok, 1.8, f"Designer button minimumSize < 250x48 ({btns})"),
        ("a_gate", rg.get("ui_cert") == DIALYSIS_CERT, 1.2, "release_gate.json missing ui_cert"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_tmp", isinstance(jb.get("max_tmp_mmhg"), (int, float)) and abs(float(jb["max_tmp_mmhg"]) - ora["max_tmp_mmhg"]) <= 0.5 and sorted(jb.get("alarm_triggered_runs") or []) == ora["alarm_triggered_runs"], 2.0, f"max_tmp_mmhg mismatch ({ora['max_tmp_mmhg']})"),
        ("b_tr_6plus", tr_count >= 6, 2.0, f"Fewer than 6/8 strings translated accurately in Linguist ({tr_count}/8)"),
        ("b_tr_all8", tr_count == 8, 2.2, f"Not all 8/8 strings translated accurately in Linguist ({tr_count}/8)"),
        ("b_no_unfin", 'type="unfinished"' not in ts_raw, 1.8, "dialysis_de.ts still has unfinished entries in Linguist"),
        ("b_gate", rg.get("l10n_cert") == DIALYSIS_CERT, 1.2, "release_gate.json missing l10n_cert"),
    ]

    checks_joint: list[tuple[str, bool, float, str]] = [
        (
            "j_both_designer_linguist_and_gate_clean",
            btns_ok and rt.get("heparinSpin") == [0, 5000, 250] and tr_count == 8 and rg.get("ui_cert") == DIALYSIS_CERT and rg.get("l10n_cert") == DIALYSIS_CERT,
            2.5,
            "Shared Designer/Linguist focus collision or release_gate.json overwrite broke combined ICU dialysis release",
        ),
    ]

    return build_aw_grade_payload(
        task_id=TASK_META["id"],
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role={"dialysis_ui_eng": TICKET_A, "dialysis_l10n_eng": TICKET_B},
        service_state=service_state,
        wall_seconds=wall_seconds,
        active_mode=active_mode,
    )
