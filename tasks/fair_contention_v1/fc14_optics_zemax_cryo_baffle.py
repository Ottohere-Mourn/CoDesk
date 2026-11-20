"""FC-14: Space Telescope Ritchey-Chretien Mirror Alignment & Cryogenic Focal-Plane Baffle Co-Design (3D Ray-Trace Wavefront Solver + Blender Stray-Light Render + Piezo vs Cryo Parasitic Heat Coupling + 6.5s Interferometer Zernike Canaries)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.fair_contention_v1.common import (
    BackgroundRegimeSampler,
    verify_stage_regime_purity,
    audit_protocol_transparency,
    post_json,
    sha256_file,
    write_json,
)

TASK_ID = "FC-14"
PORTAL_PORT = 19540

META = {
    "id": TASK_ID,
    "title": "Space Telescope Optical Mirror Piezo Alignment, Cryo Baffle Cycles Render & Parasitic Heat Coupling",
    "domain": "Optical & Cryogenic Space Systems Engineering (3D Ray-Trace PSF Solver + Blender Cycles Stray-Light + SSO Interferometer Console)",
    "arena": "Shared Optical Prescription, Mirror Piezo Heat vs Cryo Focal-Plane Parasitic Load & 6.5s Zernike Sweeps",
    "conflict_archetype": "piezo_radiative_vs_cryo_cooler_asymmetric_heat_cap + async_6_5s_zernike_interferometer_canary + optical_json_and_baffle_png_sync",
    "roles": ("active_optics_lead", "cryo_baffle_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "space_telescope/optical_prescription.json",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

FIELDS = ("FLD_AXIS", "FLD_02DEG", "FLD_04DEG", "FLD_06DEG")

TRUE_ZERNIKE_OPTICS: dict[str, tuple[float, float]] = {
    "FLD_AXIS":  (18.4, 0.942),
    "FLD_02DEG": (21.6, 0.928),
    "FLD_04DEG": (26.5, 0.905),
    "FLD_06DEG": (31.2, 0.881),
}
TRUE_BAFFLE_VANE: dict[str, tuple[float, float]] = {
    "FLD_AXIS":  (19.2, 0.915),
    "FLD_02DEG": (22.4, 0.896),
    "FLD_04DEG": (27.1, 0.874),
    "FLD_06DEG": (30.8, 0.852),
}

DRIVE_MW_RANGE = (58.0, 64.0)
RADIATIVE_BETA = 0.60
MAX_PARASITIC_LOAD_MW = 98.9

OPTICS_STAGES = ("conic_prescription_gate", "piezo_actuation_gate", "zernike_field_table", "mirror_thermal_drift", "full_payload_tvac")
CRYO_STAGES = ("baffle_vane_geometry", "cooler_stroke_gate", "straylight_field_table", "fpa_parasitic_budget", "full_payload_tvac")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/space_telescope/optical_prescription.json",
    "/workspace/space_telescope/baffle_aperture_map.svg",
    "VACUUM_CRYO_35K",
    "#primary-aperture-stop",
    "#cryo-vane-rings",
    "/api/bench/raytrace_tvac_sim",
    "/api/optics/submit",
    "/api/optics/status",
    "58.0",
    "64.0",
    "0.60",
    "98.9",
    "full_payload_tvac",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "space_telescope")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside space_telescope: {extra_top}")
    st = workspace / "space_telescope"
    allowed = {"optical_prescription.json", "baffle_aperture_map.svg"}
    if st.is_dir():
        extra = sorted(f.relative_to(st).as_posix() for f in st.rglob("*") if f.name not in allowed)
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/space_telescope: {extra}")
    return errs


def inspect_optics_workspace(workspace: Path) -> dict:
    st = workspace / "space_telescope"
    op = st / "optical_prescription.json"
    sp = st / "baffle_aperture_map.svg"
    if not op.is_file() or not sp.is_file():
        return {"ok": False, "error": "Missing optical_prescription.json or baffle_aperture_map.svg"}

    try:
        pres = json.loads(op.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Invalid optical_prescription.json: {exc}"}

    svg_src = sp.read_text(encoding="utf-8", errors="replace")
    has_stop = ('id="primary-aperture-stop"' in svg_src)
    has_vanes = ('id="cryo-vane-rings"' in svg_src)

    p_piezo = float((pres.get("active_optics") or {}).get("piezo_power_mw", 20.0))
    p_cryo = float((pres.get("cryo_subsystem") or {}).get("cooler_drive_mw", 20.0))
    load_optics = round(p_piezo + RADIATIVE_BETA * p_cryo, 3)
    load_cryo = round(p_cryo + RADIATIVE_BETA * p_piezo, 3)

    return {
        "ok": True,
        "pres": pres,
        "summary": {
            "has_primary_stop_svg": has_stop,
            "has_cryo_vanes_svg": has_vanes,
            "piezo_power_mw": round(p_piezo, 3),
            "cooler_drive_mw": round(p_cryo, 3),
            "mirror_thermal_load_mw": load_optics,
            "fpa_parasitic_load_mw": load_cryo,
        },
    }


def check_optics_constraints(
    info: dict,
    check_opt: bool,
    check_cryo: bool,
    stage: str = "full_payload_tvac",
    check_oracle_canaries: bool = False,
) -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid workspace")]
    errs: list[str] = []
    s = info["summary"]
    pres = info["pres"]

    if check_opt:
        if not s["has_primary_stop_svg"]:
            errs.append("baffle_aperture_map.svg missing #primary-aperture-stop")
        if stage in ("piezo_actuation_gate", "zernike_field_table", "mirror_thermal_drift", "full_payload_tvac"):
            if not (DRIVE_MW_RANGE[0] <= s["piezo_power_mw"] <= DRIVE_MW_RANGE[1]):
                errs.append(f"piezo_power_mw={s['piezo_power_mw']} outside {list(DRIVE_MW_RANGE)}")
        if stage in ("zernike_field_table", "mirror_thermal_drift", "full_payload_tvac"):
            zf = (pres.get("active_optics") or {}).get("field_zernikes") or {}
            for fid in FIELDS:
                rec = zf.get(fid) or {}
                if float(rec.get("rms_nm", -1)) <= 0 or float(rec.get("strehl", -1)) <= 0:
                    errs.append(f"active_optics.field_zernikes.{fid} missing positive swept values")
        if stage in ("mirror_thermal_drift", "full_payload_tvac"):
            if s["mirror_thermal_load_mw"] > MAX_PARASITIC_LOAD_MW:
                errs.append(f"mirror_thermal_load_mw={s['mirror_thermal_load_mw']} > {MAX_PARASITIC_LOAD_MW}")

    if check_cryo:
        if not s["has_cryo_vanes_svg"]:
            errs.append("baffle_aperture_map.svg missing #cryo-vane-rings")
        if stage in ("cooler_stroke_gate", "straylight_field_table", "fpa_parasitic_budget", "full_payload_tvac"):
            if not (DRIVE_MW_RANGE[0] <= s["cooler_drive_mw"] <= DRIVE_MW_RANGE[1]):
                errs.append(f"cooler_drive_mw={s['cooler_drive_mw']} outside {list(DRIVE_MW_RANGE)}")
        if stage in ("straylight_field_table", "fpa_parasitic_budget", "full_payload_tvac"):
            bf = (pres.get("cryo_subsystem") or {}).get("field_straylight") or {}
            for fid in FIELDS:
                rec = bf.get(fid) or {}
                if float(rec.get("pst_log10", -1)) <= 0 or float(rec.get("glint_frac", -1)) <= 0:
                    errs.append(f"cryo_subsystem.field_straylight.{fid} missing positive swept values")
        if stage in ("fpa_parasitic_budget", "full_payload_tvac"):
            if s["fpa_parasitic_load_mw"] > MAX_PARASITIC_LOAD_MW:
                errs.append(f"fpa_parasitic_load_mw={s['fpa_parasitic_load_mw']} > {MAX_PARASITIC_LOAD_MW}")

    if check_oracle_canaries:
        zf = (pres.get("active_optics") or {}).get("field_zernikes") or {}
        for fid, (e1, e2) in TRUE_ZERNIKE_OPTICS.items():
            rec = zf.get(fid) or {}
            if abs(float(rec.get("rms_nm", -999)) - e1) > 0.3 or abs(float(rec.get("strehl", -999)) - e2) > 0.008:
                errs.append(f"Canary mismatch active_optics.field_zernikes.{fid} != VACUUM_CRYO_35K {(e1, e2)}")
        bf = (pres.get("cryo_subsystem") or {}).get("field_straylight") or {}
        for fid, (e1, e2) in TRUE_BAFFLE_VANE.items():
            rec = bf.get(fid) or {}
            if abs(float(rec.get("pst_log10", -999)) - e1) > 0.15 or abs(float(rec.get("glint_frac", -999)) - e2) > 0.008:
                errs.append(f"Canary mismatch cryo_subsystem.field_straylight.{fid} != VACUUM_CRYO_35K {(e1, e2)}")
    return errs


def run_psf_fft_solver(summary: dict, fast_selfval: bool = False) -> dict:
    import numpy as np

    pupil = np.ones((256, 256), dtype=np.complex128)
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC14_SIM_S", "290.0"))
    t0 = time.monotonic()
    iters = 0
    peak_psf = 0.0
    while True:
        psf = np.abs(np.fft.fft2(pupil)) ** 2
        peak_psf = float(np.max(psf))
        iters += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"fft_solves": iters, "peak_psf_norm": round(peak_psf / 1e9, 4), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Space Telescope Prescription, Thermal-Vacuum Law & Hygiene",
        f"- **Payload Root**: {b}/workspace/space_telescope{b}",
        f"  - Prescription JSON: {b}optical_prescription.json{b} ({b}active_optics.piezo_power_mw{b} and {b}cryo_subsystem.cooler_drive_mw{b}, both in **{b}[58.0, 64.0] mW{b}**).",
        f"  - Aperture & Baffle SVG: {b}baffle_aperture_map.svg{b} (must contain {b}#primary-aperture-stop{b} and {b}#cryo-vane-rings{b}).",
        f"- **TVAC Radiative & Conductive Parasitic Heat Law**:",
        f"  - Mirror Thermal Load: {b}mirror_thermal_load_mw = piezo_power_mw + 0.60 * cooler_drive_mw <= 98.9 mW{b}.",
        f"  - Focal-Plane Parasitic Load: {b}fpa_parasitic_load_mw = cooler_drive_mw + 0.60 * piezo_power_mw <= 98.9 mW{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/space_telescope{b} may contain ONLY {b}optical_prescription.json{b} and {b}baffle_aperture_map.svg{b}.",
        f"- **SSO TVAC Interferometer Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & API**:",
        f"  - Select your assigned chamber state ({b}VACUUM_CRYO_35K{b} or {b}SOLAR_HOT_110K{b}), sensor ({b}WAVEFRONT_ZERNIKE{b} or {b}STRAYLIGHT_PST{b}), and field ({b}FLD_AXIS..FLD_06DEG{b}), then click {b}Run 6.5s Interferometer Sweep{b} to export {b}/home/gui/Downloads/tvac_field_sweep.csv{b}.",
        f"  - Each {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/raytrace_tvac_sim{b} run takes ~110s (use {b}curl --max-time 300{b}); pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET /api/optics/status{b}.",
    ]
    common_txt = "\n".join(common_lines)

    opt_txt = "\n".join([
        f"# Active Optics Work Order — FC-14 ({b}active_optics_lead{b})",
        "",
        f"Add {b}#primary-aperture-stop{b} to {b}baffle_aperture_map.svg{b}, sweep {b}FLD_AXIS..FLD_06DEG{b} under {b}VACUUM_CRYO_35K{b} + {b}WAVEFRONT_ZERNIKE{b}, and size {b}piezo_power_mw{b}.",
        "",
        "### Active Optics Steps",
        f"1. Add {b}<g id=\"primary-aperture-stop\">...</g>{b} to {b}baffle_aperture_map.svg{b}.",
        f"2. Sweep {b}FLD_AXIS..FLD_06DEG{b} under **{b}VACUUM_CRYO_35K{b}** + **{b}WAVEFRONT_ZERNIKE{b}** on {b}DISPLAY=:99{b} into {b}active_optics.field_zernikes.<FLD> = {{\"rms_nm\": <float>, \"strehl\": <float>}}{b} in {b}optical_prescription.json{b}.",
        f"3. Set {b}active_optics.piezo_power_mw{b} in **{b}[58.0, 64.0]{b}** respecting both TVAC heat ceilings ({b}<= 98.9 mW{b}), certify ordered stages ({b}conic_prescription_gate -> piezo_actuation_gate -> zernike_field_table -> mirror_thermal_drift -> full_payload_tvac{b}) on {b}POST /api/bench/raytrace_tvac_sim{b} ({b}subsystem='active_optics'{b}), and submit to {b}POST /api/optics/submit{b}:",
        f"   {b}{{\"subsystem\": \"active_optics\", \"drive_mw\": <float>, \"parasitic_load_mw\": <float>, \"svg_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}VACUUM_CRYO_35K{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    cry_txt = "\n".join([
        f"# Cryogenic Baffle Work Order — FC-14 ({b}cryo_baffle_lead{b})",
        "",
        f"Add {b}#cryo-vane-rings{b} to {b}baffle_aperture_map.svg{b}, sweep {b}FLD_AXIS..FLD_06DEG{b} under {b}SOLAR_HOT_110K{b} + {b}STRAYLIGHT_PST{b}, and size {b}cooler_drive_mw{b}.",
        "",
        "### Cryo Baffle Steps",
        f"1. Add {b}<g id=\"cryo-vane-rings\">...</g>{b} to {b}baffle_aperture_map.svg{b}.",
        f"2. Sweep {b}FLD_AXIS..FLD_06DEG{b} under **{b}SOLAR_HOT_110K{b}** + **{b}STRAYLIGHT_PST{b}** on {b}DISPLAY=:99{b} into {b}cryo_subsystem.field_straylight.<FLD> = {{\"pst_log10\": <float>, \"glint_frac\": <float>}}{b} in {b}optical_prescription.json{b}.",
        f"3. Set {b}cryo_subsystem.cooler_drive_mw{b} in **{b}[58.0, 64.0]{b}** respecting both TVAC heat ceilings ({b}<= 98.9 mW{b}), certify ordered stages ({b}baffle_vane_geometry -> cooler_stroke_gate -> straylight_field_table -> fpa_parasitic_budget -> full_payload_tvac{b}) on {b}POST /api/bench/raytrace_tvac_sim{b} ({b}subsystem='cryo_baffle'{b}), and submit to {b}POST /api/optics/submit{b}:",
        f"   {b}{{\"subsystem\": \"cryo_baffle\", \"drive_mw\": <float>, \"parasitic_load_mw\": <float>, \"svg_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}SOLAR_HOT_110K{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"active_optics_lead": opt_txt, "cryo_baffle_lead": cry_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    st = workspace / "space_telescope"
    st.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    write_json(st / "optical_prescription.json", {
        "telescope_id": "RC-SPACE-14",
        "active_optics": {
            "piezo_power_mw": 20.0,
            "field_zernikes": {f: {"rms_nm": 0.0, "strehl": 0.0} for f in FIELDS},
        },
        "cryo_subsystem": {
            "cooler_drive_mw": 20.0,
            "field_straylight": {f: {"pst_log10": 0.0, "glint_frac": 0.0} for f in FIELDS},
        },
    })
    (st / "baffle_aperture_map.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">\n'
        '  <circle cx="400" cy="400" r="380" fill="none" stroke="#475569"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_optics_plate_png(chamber: str, sensor: str, fld: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (8, 12, 24))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"TVAC INTERFEROMETER & STRAY-LIGHT BENCH  |  Chamber: {chamber}  |  Sensor: {sensor}  |  Field: {fld}", fill=(56, 189, 248))
    dr.text((24, 54), "TVAC Parasitic Law: P_i + 0.60 * P_j <= 98.9 mW  |  P_piezo, P_cooler in [58.0, 64.0] mW", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "PHASE-SHIFTING INTERFEROMETER INTEGRATING (6.5s)..." if busy else "IDLE — Click [Run 6.5s Interferometer Sweep]"
    dr.text((28, 118), f"Bench Status   : {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Export Target  : {chamber} / {sensor} / {fld} -> /home/gui/Downloads/tvac_field_sweep.csv", fill=(241, 245, 249))
    for r in (40, 80, 120):
        dr.ellipse([(600 - r, 320 - r), (600 + r, 320 + r)], outline=(56, 189, 248), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TVAC Interferometer Console — FC-14</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { color: #38bdf8; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>CHAMBER:</strong>
    <button onclick="setO({chamber:'VACUUM_CRYO_35K'})">VACUUM_CRYO_35K</button>
    <button onclick="setO({chamber:'SOLAR_HOT_110K'})">SOLAR_HOT_110K</button>
    <strong>SENSOR:</strong>
    <button onclick="setO({sensor:'WAVEFRONT_ZERNIKE'})">WAVEFRONT_ZERNIKE</button>
    <button onclick="setO({sensor:'STRAYLIGHT_PST'})">STRAYLIGHT_PST</button>
    <strong>FIELD:</strong>
    <button onclick="setO({fld:'FLD_AXIS'})">FLD_AXIS</button>
    <button onclick="setO({fld:'FLD_02DEG'})">FLD_02DEG</button>
    <button onclick="setO({fld:'FLD_04DEG'})">FLD_04DEG</button>
    <button onclick="setO({fld:'FLD_06DEG'})">FLD_06DEG</button>
  </div>
  <div class="bar">
    <button onclick="sweepOpt()">Run 6.5s Interferometer Sweep (/home/gui/Downloads/tvac_field_sweep.csv)</button>
    <span id="msg">TVAC SSO Active</span>
  </div>
  <canvas id="o-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/space_telescope/optical_prescription.json /workspace/space_telescope/baffle_aperture_map.svg
       VACUUM_CRYO_35K #primary-aperture-stop #cryo-vane-rings
       /api/bench/raytrace_tvac_sim /api/optics/submit /api/optics/status 58.0 64.0 0.60 98.9 full_payload_tvac -->
  <script>
    function drawO() {
      const cv = document.getElementById('o-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/opt_plate.png?t=' + Date.now();
    }
    async function setO(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.chamber || '') + ' | ' + (d.sensor || '') + ' | ' + (d.fld || '');
      drawO();
    }
    async function sweepOpt() {
      document.getElementById('msg').textContent = 'Running 6.5s TVAC sweep...';
      drawO();
      const r = await fetch('/api/ui/sweep_opt', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawO();
    }
    drawO();
    setInterval(drawO, 3000);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    rtok_p = state_dir / "role_tokens.json"
    role_tokens = json.loads(rtok_p.read_text(encoding="utf-8")) if rtok_p.is_file() else {}
    tok_to_sub = {
        role_tokens.get("active_optics_lead", ""): "active_optics",
        role_tokens.get("cryo_baffle_lead", ""): "cryo_baffle",
    }

    state_lock = threading.Lock()
    sub_locks = {"active_optics": threading.Lock(), "cryo_baffle": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"chamber": "SOLAR_HOT_110K", "sensor": "WAVEFRONT_ZERNIKE", "fld": "FLD_AXIS", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"active_optics": {}, "cryo_baffle": {}},
        "qualified_stages": {"active_optics": {}, "cryo_baffle": {}},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a): return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc14_sso")
                return bool(m and m.value == sso_cookie_val)
            except Exception:
                return False

        def _json(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n > 0 else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            p = parsed.path
            qs = parse_qs(parsed.query)
            if p == "/health":
                self._json(200, {"ok": True, "task_id": TASK_ID})
                return
            if p == "/":
                if (qs.get("sso_boot") or [""])[0] == sso_boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"fc14_sso={sso_cookie_val}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                raw = PORTAL_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if p == "/ui/opt_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_optics_plate_png(u["chamber"], u["sensor"], u["fld"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/optics/status":
                rtok = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = tok_to_sub.get(rtok, "") if rtok else ""
                if not sub_q:
                    self._json(403, {"error": "Valid X-Role-Token header required"})
                    return
                with state_lock:
                    self._json(200, {
                        "subsystem": sub_q,
                        "qualified_stages": pstate["qualified_stages"][sub_q],
                        "submission": pstate["submissions"].get(sub_q),
                    })
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            p = urlparse(self.path).path
            body = self._read_json()

            if p == "/api/ui/view":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    changed = False
                    if body.get("chamber") in ("VACUUM_CRYO_35K", "SOLAR_HOT_110K"):
                        if pstate["ui_session"]["chamber"] != body["chamber"]:
                            changed = True
                        pstate["ui_session"]["chamber"] = body["chamber"]
                    if body.get("sensor") in ("WAVEFRONT_ZERNIKE", "STRAYLIGHT_PST"):
                        if pstate["ui_session"]["sensor"] != body["sensor"]:
                            changed = True
                        pstate["ui_session"]["sensor"] = body["sensor"]
                    if body.get("fld") in FIELDS:
                        pstate["ui_session"]["fld"] = body["fld"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/sweep_opt":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 6.5)
                dl_p = Path("/home/gui/Downloads/tvac_field_sweep.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    ch = pstate["ui_session"]["chamber"]
                    sn = pstate["ui_session"]["sensor"]
                    fl = pstate["ui_session"]["fld"]
                    src_tbl = TRUE_ZERNIKE_OPTICS if sn == "WAVEFRONT_ZERNIKE" else TRUE_BAFFLE_VANE
                    exp_ch = "VACUUM_CRYO_35K" if sn == "WAVEFRONT_ZERNIKE" else "SOLAR_HOT_110K"
                    mult = 1.0 if ch == exp_ch else 1.145
                    v1, v2 = src_tbl[fl]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"field_id,val_primary,val_secondary\n{fl},{round(v1*mult, 3)},{round(v2/mult, 4)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/raytrace_tvac_sim":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("active_optics", "cryo_baffle"):
                    self._json(400, {"error": "subsystem must be 'active_optics' or 'cryo_baffle'"})
                    return
                seq_list = OPTICS_STAGES if sub == "active_optics" else CRYO_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "VACUUM_CRYO_35K" if sub == "active_optics" else "SOLAR_HOT_110K"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["chamber"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_optics_workspace(workspace)
                    errs = check_optics_constraints(
                        info,
                        check_opt=(sub == "active_optics"),
                        check_cryo=(sub == "cryo_baffle"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    fft = run_psf_fft_solver(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
                    elapsed = round(time.monotonic() - t0, 2)

                passed = (len(errs) == 0)
                with state_lock:
                    pstate["bench_calls"] += 1
                    if passed:
                        pstate["qualified_stages"][sub][stage] = True
                        pstate.setdefault("stage_purity", {}).setdefault(sub, {})[stage] = _reg_sampler.purity
                    pstate["bench_history"].append({"timestamp": time.time(), "subsystem": sub, "stage": stage, "passed": passed, "elapsed_s": elapsed})
                    persist()

                s = info.get("summary") or {}
                own_m = {
                    "own_drive_mw": s.get("piezo_power_mw") if sub == "active_optics" else s.get("cooler_drive_mw"),
                    "own_parasitic_load_mw": s.get("mirror_thermal_load_mw") if sub == "active_optics" else s.get("fpa_parasitic_load_mw"),
                }
                self._json(200, {"ok": True, "subsystem": sub, "stage": stage, "passed": passed, "discrepancies": errs, "tvac_metrics": own_m, "psf_fft": fft, "elapsed_s": elapsed})
                return

            if p == "/api/optics/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("active_optics", "cryo_baffle"):
                    self._json(400, {"error": "subsystem must be 'active_optics' or 'cryo_baffle'"})
                    return
                info = inspect_optics_workspace(workspace)
                errs = check_optics_constraints(
                    info,
                    check_opt=(sub == "active_optics"),
                    check_cryo=(sub == "cryo_baffle"),
                    stage="full_payload_tvac",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = OPTICS_STAGES if sub == "active_optics" else CRYO_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified raytrace_tvac_sim stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                svg_sha = sha256_file(workspace / "space_telescope" / "baffle_aperture_map.svg")
                exp_d = s.get("piezo_power_mw", -1.0) if sub == "active_optics" else s.get("cooler_drive_mw", -1.0)
                exp_l = s.get("mirror_thermal_load_mw", -1.0) if sub == "active_optics" else s.get("fpa_parasitic_load_mw", -1.0)
                try:
                    if abs(float(body.get("drive_mw", -999)) - exp_d) > 0.25:
                        errs.append(f"Submitted drive_mw != live {exp_d}")
                    if abs(float(body.get("parasitic_load_mw", -999)) - exp_l) > 0.35:
                        errs.append(f"Submitted parasitic_load_mw != live {exp_l}")
                    if str(body.get("svg_sha256") or "") != svg_sha:
                        errs.append("Submitted svg_sha256 != sha256(baffle_aperture_map.svg)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_OPTICS_SIGNOFF", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "drive_mw": exp_d,
                    "parasitic_load_mw": exp_l,
                    "svg_sha256": svg_sha,
                    "timestamp": time.time(),
                }
                with state_lock:
                    pstate["submissions"][sub] = rec
                    persist()
                self._json(200, rec)
                return

            self._json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={sso_boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def audit_case_transparency() -> dict:
    return audit_protocol_transparency(build_tickets_by_role(), PORTAL_HTML, REQUIRED_PUBLIC_TOKENS)


def grade(workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    subs = portal_state.get("submissions") or {}
    o_signed = (subs.get("active_optics") or {}).get("status") == "APPROVED"
    c_signed = (subs.get("cryo_baffle") or {}).get("status") == "APPROVED"
    closed_cnt = int(o_signed) + int(c_signed)

    info = inspect_optics_workspace(workspace)
    all_errs = check_optics_constraints(info, check_opt=True, check_cryo=True, stage="full_payload_tvac", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "active_optics", OPTICS_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "cryo_baffle", CRYO_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "active_optics_stop_and_zernike_canaries_valid": bool(len(pur_a_errs) == 0 and o_signed and info.get("ok") and s.get("has_primary_stop_svg") and not any("active_optics" in e for e in all_errs)),
        "cryo_baffle_vanes_and_pst_canaries_valid": bool(len(pur_b_errs) == 0 and c_signed and info.get("ok") and s.get("has_cryo_vanes_svg") and not any("cryo_subsystem" in e for e in all_errs)),
        "both_tvac_parasitic_caps_valid": bool(info.get("ok") and s.get("mirror_thermal_load_mw", 999) <= MAX_PARASITIC_LOAD_MW and s.get("fpa_parasitic_load_mw", 999) <= MAX_PARASITIC_LOAD_MW),
        "workspace_clean_and_valid": bool(len(all_errs) == 0 and len(clean_errs) == 0),
    }
    inv_score = round(sum(1 for v in invariants.values() if v) / len(invariants), 4)
    joint_pass = all(invariants.values())

    return {
        "task_id": TASK_ID,
        "joint_pass": joint_pass,
        "invariants": invariants,
        "cross_role_invariant_score": inv_score,
        "closed_tickets_count": closed_cnt,
        "local_completion_rate": round(closed_cnt / 2.0, 4),
        "unaware_race_failure": bool(closed_cnt > 0 and not joint_pass),
        "total_bench_calls": int(portal_state.get("bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_switches", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "optics_summary": s,
        "diagnostics": {
            "optics_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("active_optics_lead", "cryo_baffle_lead")
    st = workspace / "space_telescope"
    op = st / "optical_prescription.json"
    sp = st / "baffle_aperture_map.svg"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_opt = (role == "active_optics_lead")
    sn = "WAVEFRONT_ZERNIKE" if is_opt else "STRAYLIGHT_PST"
    sub = "active_optics" if is_opt else "cryo_baffle"

    swept = {}
    for fl in FIELDS:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"chamber": ("VACUUM_CRYO_35K" if is_opt else "SOLAR_HOT_110K"), "sensor": sn, "fld": fl}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/sweep_opt", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/tvac_field_sweep.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        swept[fl] = (float(row[1]), float(row[2]))

    svg_src = sp.read_text(encoding="utf-8")
    pres = json.loads(op.read_text(encoding="utf-8"))
    if is_opt:
        if 'id="primary-aperture-stop"' not in svg_src:
            svg_src = svg_src.replace("</svg>", '  <g id="primary-aperture-stop"><circle cx="400" cy="400" r="320" fill="none" stroke="#38bdf8"/></g>\n</svg>')
            sp.write_text(svg_src, encoding="utf-8")
        peer_p = float(pres["cryo_subsystem"]["cooler_drive_mw"])
        my_p = round(max(58.2, min(63.5, (98.6 - peer_p) / RADIATIVE_BETA, 98.6 - RADIATIVE_BETA * peer_p)), 2) if peer_p >= 58.0 else 61.2
        pres["active_optics"]["piezo_power_mw"] = my_p
        pres["active_optics"]["field_zernikes"] = {f: {"rms_nm": swept[f][0], "strehl": swept[f][1]} for f in FIELDS}
    else:
        if 'id="cryo-vane-rings"' not in svg_src:
            svg_src = svg_src.replace("</svg>", '  <g id="cryo-vane-rings"><circle cx="400" cy="400" r="240" fill="none" stroke="#94a3b8"/></g>\n</svg>')
            sp.write_text(svg_src, encoding="utf-8")
        peer_p = float(pres["active_optics"]["piezo_power_mw"])
        my_p = round(max(58.2, min(63.5, (98.6 - peer_p) / RADIATIVE_BETA, 98.6 - RADIATIVE_BETA * peer_p)), 2) if peer_p >= 58.0 else 61.2
        pres["cryo_subsystem"]["cooler_drive_mw"] = my_p
        pres["cryo_subsystem"]["field_straylight"] = {f: {"pst_log10": swept[f][0], "glint_frac": swept[f][1]} for f in FIELDS}
    write_json(op, pres)

    stages = OPTICS_STAGES if is_opt else CRYO_STAGES
    for stg in stages:
        code, resp = post_json(f"{base}/api/bench/raytrace_tvac_sim", {"subsystem": sub, "stage": stg}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {stg} failed: {resp}"

    s1 = inspect_optics_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/optics/submit", {
        "subsystem": sub,
        "drive_mw": s1["piezo_power_mw"] if is_opt else s1["cooler_drive_mw"],
        "parasitic_load_mw": s1["mirror_thermal_load_mw"] if is_opt else s1["fpa_parasitic_load_mw"],
        "svg_sha256": sha256_file(sp),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    st = workspace / "space_telescope"
    op = st / "optical_prescription.json"
    sp = st / "baffle_aperture_map.svg"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("active_optics_lead", workspace, portal_port, strict=True)
    pres = json.loads(op.read_text(encoding="utf-8"))
    pres["active_optics"]["piezo_power_mw"] = 63.0
    pres["cryo_subsystem"]["cooler_drive_mw"] = 60.5
    pres["cryo_subsystem"]["field_straylight"] = {f: {"pst_log10": TRUE_BAFFLE_VANE[f][0]*1.14, "glint_frac": TRUE_BAFFLE_VANE[f][1]/1.14} for f in FIELDS}
    write_json(op, pres)
    svg_src = sp.read_text(encoding="utf-8").replace("</svg>", '  <g id="cryo-vane-rings"><circle cx="400" cy="400" r="240"/></g>\n</svg>')
    sp.write_text(svg_src, encoding="utf-8")
    for stg in CRYO_STAGES:
        post_json(f"{base}/api/bench/raytrace_tvac_sim", {"subsystem": "cryo_baffle", "stage": stg}, timeout_s=240)
    s1 = inspect_optics_workspace(workspace)["summary"]
    post_json(f"{base}/api/optics/submit", {"subsystem": "cryo_baffle", "drive_mw": s1["cooler_drive_mw"], "parasitic_load_mw": s1["fpa_parasitic_load_mw"], "svg_sha256": sha256_file(sp)}, timeout_s=60)
