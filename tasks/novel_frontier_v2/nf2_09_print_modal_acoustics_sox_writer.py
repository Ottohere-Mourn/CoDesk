"""NF2-09: Modal Print-Layout Freeze & LibreOffice Writer vs. SoX/WAV Impulse-Response Acoustics (`RT60` / `C80` / `L_den`)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sqlite3
import struct
import subprocess
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlparse
import wave

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    extract_pdf_text,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_odt_plain_text,
    reload_uno_pipe_documents,
    write_json,
    write_multipage_sop_pdf,
    write_simple_odt,
)

TASK_ID = "NF2-09"
PORTAL_PORT = 19609

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Chromium Print-Layout Modal Lock & Live Writer: Room Impulse-Response WAV (`RT60`/`C80`) vs. EU `L_den` Noise Ordinance",
    "domain": "Architectural Room Acoustics (`WAV`/`SoX` Schroeder Integration) & Environmental Noise Compliance (`LibreOffice Writer`)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("impulse_rt60_acoustician", "noise_ordinance_officer"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

SABINE_LAB_CODE = make_canary_code("ISO3382", "schroeder-hall-rt60")
ORD_SEAL_CODE = make_canary_code("DIR2002-49", "lden-municipal-seal")


def _write_impulse_wav(wav_path: Path, sr: int = 16000, rt60_target_s: float = 1.68) -> dict[str, float]:
    import numpy as np
    # Deterministic exponential decay h(t) = exp(-6.907755 * t / rt60_target_s) * cos(...) for 2.5s
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(sr * 2.5)
    t = np.arange(n, dtype=np.float64) / sr
    decay = np.exp(-6.90775527898 * t / rt60_target_s)
    carrier = 0.65 * np.sin(2.0 * np.pi * 1000.0 * t) + 0.35 * np.cos(2.0 * np.pi * 500.0 * t + 0.3)
    sig = decay * carrier
    sig = sig / np.max(np.abs(sig)) * 0.88
    pcm = np.clip(np.round(sig * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    # Compute exact discrete Schroeder curve & C80_dB = 10*log10( sum_{0..80ms} p^2 / sum_{80ms..end} p^2 )
    x = pcm.astype(np.float64) / 32768.0
    e = x * x
    n80 = int(round(0.080 * sr))
    c80_db = 10.0 * math.log10(float(np.sum(e[:n80])) / float(np.sum(e[n80:])))
    edc = np.cumsum(e[::-1])[::-1]
    edc_db = 10.0 * np.log10(np.maximum(edc / edc[0], 1e-12))
    mask = (edc_db <= -5.0) & (edc_db >= -25.0)
    slope, _ic = np.polyfit(t[mask], edc_db[mask], 1)
    t20_rt60 = -60.0 / float(slope)
    # ISO 3382-1 air-absorption correction at 42% RH (4*m*V term in SQLite hall_geometry: subtract 0.045 s excess dry-air correction -> net 50% RH standard RT60!)
    return {"raw_t20_rt60_s": round(t20_rt60, 4), "std_50rh_rt60_s": round(t20_rt60 - 0.0450, 4), "clarity_c80_db": round(c80_db, 3)}


def _generate_noise_hours() -> list[dict[str, Any]]:
    # 15 days x 24 hours = 360 hourly Leq dBA measurements!
    # EU Directive 2002/49/EC L_den: Day (07..18, 12h): +0 dB; Evening (19..22, 4h): +5 dB; Night (23, 00..06, 8h): +10 dB;
    # PLUS ISO 1996-2 prominent tonal penalty (+3.0 dB on hours with tonal_prominence_flag == 1, documented in SQLite)!
    rows = []
    for d in range(1, 16):
        for hr in range(24):
            base = 58.2 if (7 <= hr <= 18) else (53.6 if (19 <= hr <= 22) else 47.4)
            leq = round(base + 1.4 * math.sin((d * 24 + hr) * 0.19), 2)
            tonal = 1 if (hr in (2, 3) and d % 3 == 0) else 0
            valid = "VALID" if not (d == 7 and hr in (11, 12)) else "RAIN_WIND_REJECT"
            rows.append({"obs_id": len(rows) + 1, "day_no": d, "hour_24": hr, "leq_dba": leq, "tonal_prominence_flag": tonal, "qc_flag": valid})
    return rows


def _compute_lden_oracle() -> dict[str, Any]:
    rows = [r for r in _generate_noise_hours() if r["qc_flag"] == "VALID"]
    day_e, eve_e, ngt_e = [], [], []
    for r in rows:
        adj = float(r["leq_dba"]) + (3.0 if int(r["tonal_prominence_flag"]) == 1 else 0.0)
        hr = int(r["hour_24"])
        if 7 <= hr <= 18:
            day_e.append(10.0 ** (adj / 10.0))
        elif 19 <= hr <= 22:
            eve_e.append(10.0 ** ((adj + 5.0) / 10.0))
        else:
            ngt_e.append(10.0 ** ((adj + 10.0) / 10.0))
    mean_d = sum(day_e) / len(day_e)
    mean_e = sum(eve_e) / len(eve_e)
    mean_n = sum(ngt_e) / len(ngt_e)
    lden = 10.0 * math.log10((12.0 * mean_d + 4.0 * mean_e + 8.0 * mean_n) / 24.0)
    lnight = 10.0 * math.log10(mean_n) - 10.0  # Unpenalized L_night (since ngt_e had +10dB -> -10dB recovers L_night with tonal)
    return {
        "valid_hour_count": len(rows),
        "lden_dba": round(lden, 3),
        "lnight_tonal_adj_dba": round(lnight, 3),
        "exceeds_60dba_residential_limit": lden > 60.0,
        "ordinance_seal_code": ORD_SEAL_CODE,
    }


LDEN_ORACLE = _compute_lden_oracle()

PORTAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Acoustic Spectrum & Print-Seal Console</title>
<style>
  body{margin:18px;background:#0f172a;color:#f8fafc;font-family:monospace}
  button{padding:8px 14px;background:#2563eb;color:#fff;border:none;cursor:pointer;margin-right:8px}
  #print-modal{display:none;position:fixed;inset:0;background:rgba(2,6,23,0.94);z-index:999;padding:48px}
</style></head><body>
<h2>Concert-Hall ISO 3382 & Municipal Dir. 2002/49/EC Portal</h2>
<button onclick="loadIso()">Load ISO 3382 Schroeder Spec</button>
<button style="background:#d97706" onclick="openPrintLock()">Open Print-Layout Seal Preview (Locks Screen)</button>
<pre id="out">Select an action above...</pre>
<div id="print-modal">
  <h3>Print-Layout Ordinance Preview (Modal Active — Blocks Underlying Analyzer!)</h3>
  <p>EU Dir. 2002/49/EC Residential Limit: <code>60.0 dBA L_den</code> (12h Day 07-18 +0dB, 4h Evening 19-22 +5dB, 8h Night 23-06 +10dB).</p>
  <p>Ordinance Seal Code: <strong style="color:#4ade80">__ORD__</strong></p>
  <button style="background:#059669" onclick="closePrintLock()">Confirm Print Seal & Dismiss Modal</button>
</div>
<script>
async function loadIso() {
  const r = await fetch('/api/iso3382', {credentials:'include'});
  document.getElementById('out').textContent = JSON.stringify(await r.json(), null, 2);
}
async function openPrintLock() {
  await fetch('/api/modal?open=1', {method:'POST', credentials:'include'});
  document.getElementById('print-modal').style.display = 'block';
}
async function closePrintLock() {
  await fetch('/api/modal?open=0', {method:'POST', credentials:'include'});
  document.getElementById('print-modal').style.display = 'none';
}
</script></body></html>""".replace("__ORD__", ORD_SEAL_CODE)


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Concert-Hall Impulse Response `RT60` & `C80` Audit (`impulse_rt60_acoustician`)",
        "",
        "## Objective",
        f"Analyze `{b}/workspace/audio/hall_impulse_1khz.wav{b}` and `{b}/workspace/audio/hall_hygrometry.sqlite{b}` using ISO 3382-1 criteria on `http://127.0.0.1:{PORTAL_PORT}/acoustics` and `{b}/workspace/docs/SOP_ISO3382.pdf{b}`, and write `{b}/workspace/room_acoustics_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Municipal `L_den` Noise Ordinance Certificate (`noise_ordinance_officer`)",
        "",
        "## Objective",
        f"Evaluate `{b}/workspace/monitoring/community_noise_leq.sqlite{b}` per `http://127.0.0.1:{PORTAL_PORT}/acoustics` and `{b}/workspace/docs/SOP_Lden_Ordinance.pdf{b}`, finalize the open `{b}/workspace/Acoustic_Compliance_Certificate.odt{b}` in LibreOffice Writer (and export `{b}/workspace/Acoustic_Compliance_Certificate.pdf{b}`), and write `{b}/workspace/noise_ordinance_audit.json{b}`.",
    ])
    return {"impulse_rt60_acoustician": ta, "noise_ordinance_officer": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["impulse_rt60_acoustician"]
    ws_b = workspace_map["noise_ordinance_officer"]
    for d in (ws_a / "audio", ws_a / "docs", ws_b / "monitoring", ws_b / "docs"):
        d.mkdir(parents=True, exist_ok=True)

    wav_meta = _write_impulse_wav(ws_a / "audio/hall_impulse_1khz.wav")
    (ws_a.parent / ".nf209_wav_oracle.json").write_text(json.dumps(wav_meta), encoding="utf-8")
    with sqlite3.connect(str(ws_a / "audio/hall_hygrometry.sqlite")) as conn:
        conn.execute("CREATE TABLE humidity_air_absorption (measured_rh_pct REAL, target_ref_rh_pct REAL, rt60_humidity_delta_s REAL)")
        conn.execute("INSERT INTO humidity_air_absorption VALUES (42.0, 50.0, -0.0450)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_ISO3382.pdf", "SOP-ACO-909A: Schroeder Backward Integration (T20) & Clarity C80", [
        ("1. WAV Impulse Analysis", [
            "1.1 Compute discrete Schroeder backward-integrated energy decay curve on /workspace/audio/hall_impulse_1khz.wav, fit linear regression over [-5.0 dB, -25.0 dB] to extrapolate T20 -> raw_t20_rt60_s, apply the 50% RH air-absorption normalization in hall_hygrometry.sqlite -> std_50rh_rt60_s, and compute 80 ms early-to-late clarity index clarity_c80_db.",
        ]),
        ("2. JSON Schema (/workspace/room_acoustics_audit.json)", [
            "Keys: raw_t20_rt60_s (float, 4 dec), std_50rh_rt60_s (float, 4 dec), clarity_c80_db (float, 3 dec), sabine_lab_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "monitoring/community_noise_leq.sqlite")) as conn:
        conn.execute("CREATE TABLE hourly_leq (obs_id INTEGER PRIMARY KEY, day_no INTEGER, hour_24 INTEGER, leq_dba REAL, tonal_prominence_flag INTEGER, qc_flag TEXT)")
        for r in _generate_noise_hours():
            conn.execute("INSERT INTO hourly_leq VALUES (?,?,?,?,?,?)", (r["obs_id"], r["day_no"], r["hour_24"], r["leq_dba"], r["tonal_prominence_flag"], r["qc_flag"]))
        conn.execute("CREATE TABLE iso1996_tonal_adjustment (tonal_prominence_flag INTEGER PRIMARY KEY, penalty_dba REAL)")
        conn.execute("INSERT INTO iso1996_tonal_adjustment VALUES (0, 0.0), (1, 3.0)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_Lden_Ordinance.pdf", "SOP-ENV-909B: EU Directive 2002/49/EC L_den & Writer Certificate", [
        ("1. Energetic L_den Averaging & Writer Certificate", [
            "1.1 Retain VALID hourly rows in /workspace/monitoring/community_noise_leq.sqlite, apply ISO 1996-2 tonal adjustments from SQLite prior to energetic (10^(L/10)) Day/Evening(+5)/Night(+10) time-weighted L_den aggregation.",
            "1.2 Record ordinance_seal_code, lden_dba, and '[CERT-ACO-2026]' in Acoustic_Compliance_Certificate.odt (keep open Writer synced) and export Acoustic_Compliance_Certificate.pdf (dismiss any open Print-Layout modal on /acoustics when finished).",
        ]),
        ("2. JSON Schema (/workspace/noise_ordinance_audit.json)", [
            "Keys: valid_hour_count (int), lden_dba (float, 3 dec), lnight_tonal_adj_dba (float, 3 dec), exceeds_60dba_residential_limit (bool), ordinance_seal_code (str).",
        ]),
    ])
    write_simple_odt(ws_b / "Acoustic_Compliance_Certificate.odt", "Municipal Noise Certificate", [("HDR", "[CERT-ACO-2026] DRAFT"), ("SEAL", "SEAL: PENDING")])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_p = state_dir / "service_state.json"
    mem = {"modal_open": False, "modal_opens": 0, "seal_viewed": False}
    write_json(st_p, {"task_id": TASK_ID, **mem})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("aco_sso" in c) and (c["aco_sso"].value == tok)
        def _json(self, code: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self._json(200, {"ok": True}); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self._json(403, {"error": "SSO sealed"}); return
                raw = b"<html><body><script>location.href='/acoustics';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", f"aco_sso={tok}; HttpOnly; Path=/"); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "SSO required"}); return
            if u.path == "/api/iso3382":
                if mem["modal_open"]:
                    self._json(200, {"error": "Blocked by active Print-Layout Modal!"}); return
                self._json(200, {"t20_fit_range_db": [-5.0, -25.0], "c80_early_ms": 80.0, "sabine_lab_code": SABINE_LAB_CODE}); return
            raw = PORTAL_HTML.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(raw)
        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/modal":
                op = (qs.get("open") == ["1"])
                mem["modal_open"] = op
                if op:
                    mem["modal_opens"] += 1; mem["seal_viewed"] = True
                write_json(st_p, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "modal_open": op}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or META["roles"])
    if "noise_ordinance_officer" in roles:
        launch_libreoffice_uno_natural([workspace_map["noise_ordinance_officer"] / "Acoustic_Compliance_Certificate.odt"])
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["impulse_rt60_acoustician"]
    ws_b = workspace_map["noise_ordinance_officer"]
    wav_or = read_json_safe(ws_a.parent / ".nf209_wav_oracle.json") or _write_impulse_wav(Path("/tmp/nf209_tmp.wav"))
    ja = read_json_safe(ws_a / "room_acoustics_audit.json")
    jb = read_json_safe(ws_b / "noise_ordinance_audit.json")
    odt_txt = read_odt_plain_text(ws_b / "Acoustic_Compliance_Certificate.odt")
    pdf_txt = extract_pdf_text(ws_b / "Acoustic_Compliance_Certificate.pdf")
    uno_st = inspect_live_uno_documents_readonly()

    writer_sync = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Acoustic_Compliance_Certificate.odt" in u_url:
            writer_sync = (not u_doc.get("is_modified")) and (ORD_SEAL_CODE in (u_doc.get("text") or ""))

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.10, "Missing room_acoustics_audit.json"),
        ("a_raw_rt60", abs(_f(ja.get("raw_t20_rt60_s")) - wav_or["raw_t20_rt60_s"]) <= 0.025, 0.22, "raw_t20_rt60_s Schroeder T20 mismatch"),
        ("a_c80", abs(_f(ja.get("clarity_c80_db")) - wav_or["clarity_c80_db"]) <= 0.15, 0.22, "clarity_c80_db 80ms early/late ratio mismatch"),
        ("a_code", ja.get("sabine_lab_code") == SABINE_LAB_CODE, 0.22, "Missing sabine_lab_code (blocked by Print-Layout modal?)"),
        ("a_fine_50rh_rt60", abs(_f(ja.get("std_50rh_rt60_s")) - wav_or["std_50rh_rt60_s"]) <= 0.008 and abs(_f(ja.get("std_50rh_rt60_s")) - _f(ja.get("raw_t20_rt60_s"))) > 0.02, 0.24, "Missed hall_hygrometry.sqlite -0.0450s 50% RH air-absorption correction"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.07, "Missing noise_ordinance_audit.json"),
        ("b_cnt", jb.get("valid_hour_count") == LDEN_ORACLE["valid_hour_count"], 0.10, "valid_hour_count != 358"),
        ("b_lden_coarse", abs(_f(jb.get("lden_dba")) - LDEN_ORACLE["lden_dba"]) <= 1.2, 0.12, "lden_dba coarse off (arithmetic mean instead of 10*log10 energetic mean?)"),
        ("b_bool", jb.get("exceeds_60dba_residential_limit") is LDEN_ORACLE["exceeds_60dba_residential_limit"], 0.08, "exceeds_60dba_residential_limit wrong"),
        ("b_odt_pdf", ORD_SEAL_CODE in odt_txt and "[CERT-ACO-2026]" in odt_txt and ORD_SEAL_CODE in pdf_txt, 0.14, "ODT or PDF certificate incomplete"),
        ("b_writer_sync", bool(jb) and writer_sync, 0.10, "Open LibreOffice Writer out-of-sync with disk .odt"),
        ("b_modal_closed", bool(jb) and not bool(service_state.get("modal_open")), 0.09, "Print-Layout modal left open blocking portal!"),
        ("b_fine_tonal_lden", abs(_f(jb.get("lden_dba")) - LDEN_ORACLE["lden_dba"]) <= 0.02 and abs(_f(jb.get("lnight_tonal_adj_dba")) - LDEN_ORACLE["lnight_tonal_adj_dba"]) <= 0.02, 0.30, "Missed iso1996_tonal_adjustment +3.0 dB penalty on prominent tonal hours"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    st_f = Path("/opt/nf_state/service_state.json")
    if role == "impulse_rt60_acoustician":
        wav_or = read_json_safe(ws.parent / ".nf209_wav_oracle.json")
        write_json(ws / "room_acoustics_audit.json", {**wav_or, "sabine_lab_code": SABINE_LAB_CODE})
    else:
        odt_p = ws / "Acoustic_Compliance_Certificate.odt"
        write_simple_odt(odt_p, "Municipal Noise Certificate", [
            ("HDR", "[CERT-ACO-2026] CERTIFIED"),
            ("LDEN", f"L_den = {LDEN_ORACLE['lden_dba']} dBA | Seal = {ORD_SEAL_CODE}"),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["libreoffice", f"-env:UserInstallation=file://{tmp}/lo", "--headless", "--convert-to", "pdf", "--outdir", str(ws), str(odt_p)], check=True, capture_output=True, timeout=45)
        with file_atomic_lock("nf209_uno"):
            reload_uno_pipe_documents([odt_p])
        if st_f.is_file():
            with file_atomic_lock("nf209_st"):
                st = read_json_safe(st_f); st["modal_open"] = False; st["seal_viewed"] = True; write_json(st_f, st)
        write_json(ws / "noise_ordinance_audit.json", LDEN_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    solve_role("impulse_rt60_acoustician", workspace_map, port)
    solve_role("noise_ordinance_officer", workspace_map, port)
    # Print modal left open blocks Role A's /api/iso3382 lookup
    st_p = state_dir / "service_state.json"
    st = read_json_safe(st_p); st["modal_open"] = True; write_json(st_p, st)
    ja = read_json_safe(workspace_map["impulse_rt60_acoustician"] / "room_acoustics_audit.json")
    ja["sabine_lab_code"] = ""
    ja["raw_t20_rt60_s"] = 0.0
    write_json(workspace_map["impulse_rt60_acoustician"] / "room_acoustics_audit.json", ja)
