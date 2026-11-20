"""FC-15: Semiconductor 5nm Lithography OPC Mask & CMP Oxide Dishing Co-Optimization (2D Wafer Density .npz + Aerial-Image FFT Solver + .xlsx Signoff + Dummy-Fill vs Inductor CMP Erosion + 6.5s CD-SEM Metrology Canaries)."""
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
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
    write_multisheet_xlsx,
)

TASK_ID = "FC-15"
PORTAL_PORT = 19550

META = {
    "id": TASK_ID,
    "title": "Semiconductor 5nm OPC Mask Dummy-Fill, CMP Oxide Dishing & CD-SEM Metrology Co-Optimization",
    "domain": "Semiconductor Process & RET/OPC Engineering (NumPy 2D Wafer Density .npz + FFT Aerial-Image Solver + .xlsx + SSO CD-SEM Metrology)",
    "arena": "Shared 2D Reticle Density Map, SRAM Dummy-Fill vs Analog CMP Oxide Erosion & 6.5s CD-SEM Sweeps",
    "conflict_archetype": "sram_dummy_fill_vs_inductor_cmp_erosion_asymmetric_cap + async_6_5s_cd_sem_metrology_canary + npz_and_xlsx_tapeout_sync",
    "roles": ("opc_sram_ret_lead", "cmp_analog_planar_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "reticle_5nm/reticle_density.npz",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

DIES = ("DIE_NW", "DIE_NE", "DIE_SW", "DIE_SE")

TRUE_OPC_CDSEM: dict[str, tuple[float, float]] = {
    "DIE_NW": (18.2, 1.45),
    "DIE_NE": (18.6, 1.52),
    "DIE_SW": (17.9, 1.41),
    "DIE_SE": (18.4, 1.48),
}
TRUE_CMP_PROFILER: dict[str, tuple[float, float]] = {
    "DIE_NW": (18.9, 1.54),
    "DIE_NE": (19.4, 1.61),
    "DIE_SW": (18.1, 1.47),
    "DIE_SE": (19.0, 1.56),
}

DENSITY_PCT_RANGE = (58.0, 64.0)
SLURRY_COUPLING = 0.60
MAX_EROSION_NM = 98.9

OPC_STAGES = ("sram_tile_grid_gate", "aerial_contrast_gate", "cdsem_wafer_sync", "sram_erosion_budget", "full_tapeout_drc")
CMP_STAGES = ("inductor_tile_grid_gate", "planar_uniformity_gate", "profilometer_wafer_sync", "inductor_erosion_budget", "full_tapeout_drc")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/reticle_5nm/reticle_density.npz",
    "/workspace/reticle_5nm/Tapeout_Metrology.xlsx",
    "sram_density",
    "analog_density",
    "OPC_CDSEM",
    "CMP_Profilometry",
    "EUV_13_5NM_CALIBRATED",
    "/api/bench/litho_cmp_sim",
    "/api/fab/submit",
    "/api/fab/status",
    "58.0",
    "64.0",
    "0.60",
    "98.9",
    "full_tapeout_drc",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "reticle_5nm")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside reticle_5nm: {extra_top}")
    rt = workspace / "reticle_5nm"
    allowed = {"reticle_density.npz", "Tapeout_Metrology.xlsx"}
    if rt.is_dir():
        extra = sorted(f.relative_to(rt).as_posix() for f in rt.rglob("*") if f.name not in allowed)
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/reticle_5nm: {extra}")
    return errs


def inspect_fab_workspace(workspace: Path) -> dict:
    import numpy as np

    rt = workspace / "reticle_5nm"
    npz_p = rt / "reticle_density.npz"
    xp = rt / "Tapeout_Metrology.xlsx"
    if not npz_p.is_file() or not xp.is_file():
        return {"ok": False, "error": "Missing reticle_density.npz or Tapeout_Metrology.xlsx"}

    try:
        with np.load(npz_p) as data:
            sram_g = np.array(data["sram_density"], dtype=np.float64)
            ana_g = np.array(data["analog_density"], dtype=np.float64)
        if sram_g.shape != (64, 64) or ana_g.shape != (64, 64):
            return {"ok": False, "error": f"Expected (64,64) arrays sram_density and analog_density, got {sram_g.shape}, {ana_g.shape}"}
        raw_sh = read_multisheet_xlsx(xp)
        ev_sh = evaluate_xlsx_via_libreoffice(xp)
    except Exception as exc:
        return {"ok": False, "error": f"Corrupted NPZ or XLSX: {exc}"}

    d_sram = round(float(np.mean(sram_g)), 3)
    d_ana = round(float(np.mean(ana_g)), 3)
    ero_sram = round(d_sram + SLURRY_COUPLING * d_ana, 3)
    ero_ana = round(d_ana + SLURRY_COUPLING * d_sram, 3)

    return {
        "ok": True,
        "raw_sh": raw_sh,
        "ev_sh": ev_sh,
        "summary": {
            "sram_mean_density_pct": d_sram,
            "analog_mean_density_pct": d_ana,
            "sram_oxide_erosion_nm": ero_sram,
            "analog_oxide_erosion_nm": ero_ana,
        },
    }


def check_fab_constraints(
    info: dict,
    check_opc: bool,
    check_cmp: bool,
    stage: str = "full_tapeout_drc",
    check_oracle_canaries: bool = False,
) -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid workspace")]
    errs: list[str] = []
    s = info["summary"]
    raw_sh = info["raw_sh"]
    ev_sh = info["ev_sh"]

    def _num(sh: dict, ref: str) -> float:
        v = (sh.get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999.0

    for sn in ("OPC_CDSEM", "CMP_Profilometry"):
        if sn not in raw_sh:
            errs.append(f"Missing worksheet {sn}")
    if errs:
        return errs

    if check_opc:
        if not (DENSITY_PCT_RANGE[0] <= s["sram_mean_density_pct"] <= DENSITY_PCT_RANGE[1]):
            errs.append(f"sram_mean_density_pct={s['sram_mean_density_pct']} outside {list(DENSITY_PCT_RANGE)}")
        if stage in ("cdsem_wafer_sync", "sram_erosion_budget", "full_tapeout_drc"):
            for r_i in range(2, 6):
                if _num(ev_sh["OPC_CDSEM"], f"B{r_i}") <= 0 or _num(ev_sh["OPC_CDSEM"], f"C{r_i}") <= 0:
                    errs.append(f"OPC_CDSEM row {r_i} missing positive CD/LWR values")
            if not (raw_sh["OPC_CDSEM"].get("B6") or {}).get("formula"):
                errs.append("OPC_CDSEM!B6 missing =AVERAGE or =SUM formula")
        if stage in ("sram_erosion_budget", "full_tapeout_drc"):
            if s["sram_oxide_erosion_nm"] > MAX_EROSION_NM:
                errs.append(f"sram_oxide_erosion_nm={s['sram_oxide_erosion_nm']} > {MAX_EROSION_NM}")

    if check_cmp:
        if not (DENSITY_PCT_RANGE[0] <= s["analog_mean_density_pct"] <= DENSITY_PCT_RANGE[1]):
            errs.append(f"analog_mean_density_pct={s['analog_mean_density_pct']} outside {list(DENSITY_PCT_RANGE)}")
        if stage in ("profilometer_wafer_sync", "inductor_erosion_budget", "full_tapeout_drc"):
            for r_i in range(2, 6):
                if _num(ev_sh["CMP_Profilometry"], f"B{r_i}") <= 0 or _num(ev_sh["CMP_Profilometry"], f"C{r_i}") <= 0:
                    errs.append(f"CMP_Profilometry row {r_i} missing positive thickness/dishing values")
            if not (raw_sh["CMP_Profilometry"].get("B6") or {}).get("formula"):
                errs.append("CMP_Profilometry!B6 missing =AVERAGE or =SUM formula")
        if stage in ("inductor_erosion_budget", "full_tapeout_drc"):
            if s["analog_oxide_erosion_nm"] > MAX_EROSION_NM:
                errs.append(f"analog_oxide_erosion_nm={s['analog_oxide_erosion_nm']} > {MAX_EROSION_NM}")

    if check_oracle_canaries:
        for idx, die in enumerate(DIES, start=2):
            o1, o2 = TRUE_OPC_CDSEM[die]
            if abs(_num(ev_sh["OPC_CDSEM"], f"B{idx}") - o1) > 0.25 or abs(_num(ev_sh["OPC_CDSEM"], f"C{idx}") - o2) > 0.05:
                errs.append(f"Canary mismatch OPC_CDSEM {die} != EUV_13_5NM_CALIBRATED {(o1, o2)}")
            c1, c2 = TRUE_CMP_PROFILER[die]
            if abs(_num(ev_sh["CMP_Profilometry"], f"B{idx}") - c1) > 0.25 or abs(_num(ev_sh["CMP_Profilometry"], f"C{idx}") - c2) > 0.05:
                errs.append(f"Canary mismatch CMP_Profilometry {die} != EUV_13_5NM_CALIBRATED {(c1, c2)}")
    return errs


def run_hopkins_aerial_fft(summary: dict, fast_selfval: bool = False) -> dict:
    import numpy as np

    mask = np.ones((256, 256), dtype=np.float64) * (summary.get("sram_mean_density_pct", 20.0) / 100.0)
    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC15_SIM_S", "290.0"))
    t0 = time.monotonic()
    passes = 0
    ils = 0.0
    while True:
        spec = np.fft.fft2(mask)
        aerial = np.abs(np.fft.ifft2(spec * 0.92)) ** 2
        ils = float(np.mean(aerial))
        passes += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"hopkins_passes": passes, "mean_intensity": round(ils, 4), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### 5nm Reticle Density Map, CMP Erosion Law & Hygiene",
        f"- **Fab Root**: {b}/workspace/reticle_5nm{b}",
        f"  - 2D Reticle Density Archive: {b}reticle_density.npz{b} containing two {b}(64, 64){b} float arrays: {b}sram_density{b} and {b}analog_density{b} (mean density of each array required in **{b}[58.0, 64.0]%{b}**).",
        f"  - Metrology Workbook: {b}Tapeout_Metrology.xlsx{b} ({b}OPC_CDSEM{b} and {b}CMP_Profilometry{b} sheets, {b}Rows 2..5{b} for {b}DIE_NW, DIE_NE, DIE_SW, DIE_SE{b}, {b}Row 6{b} live {b}=AVERAGE{b} or {b}=SUM{b} formula in {b}B6:C6{b}).",
        f"- **Long-Range CMP Slurry Load & Oxide Erosion Law**:",
        f"  - SRAM Oxide Erosion: {b}sram_oxide_erosion_nm = sram_mean_density_pct + 0.60 * analog_mean_density_pct <= 98.9 nm{b}.",
        f"  - Analog Inductor Erosion: {b}analog_oxide_erosion_nm = analog_mean_density_pct + 0.60 * sram_mean_density_pct <= 98.9 nm{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/reticle_5nm{b} may contain ONLY {b}reticle_density.npz{b} and {b}Tapeout_Metrology.xlsx{b}.",
        f"- **SSO Fab Metrology Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & Litho/CMP API**:",
        f"  - Select your assigned calibration ({b}EUV_13_5NM_CALIBRATED{b} or {b}CMP_SLURRY_PH10_REF{b}), tool ({b}CD_SEM_SCAN{b} or {b}CMP_PROFILER{b}), and die ({b}DIE_NW..DIE_SE{b}), then click {b}Run 6.5s Wafer Metrology Scan{b} to export {b}/home/gui/Downloads/wafer_metrology.csv{b}.",
        f"  - Each {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/litho_cmp_sim{b} run takes ~110s (use {b}curl --max-time 300{b}); pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET /api/fab/status{b}.",
    ]
    common_txt = "\n".join(common_lines)

    opc_txt = "\n".join([
        f"# RET/OPC Work Order — FC-15 ({b}opc_sram_ret_lead{b})",
        "",
        f"Tune {b}sram_density{b} in {b}reticle_density.npz{b} and populate {b}OPC_CDSEM{b} in {b}Tapeout_Metrology.xlsx{b} under {b}EUV_13_5NM_CALIBRATED{b}.",
        "",
        "### OPC Steps",
        f"1. Scan {b}DIE_NW..DIE_SE{b} under **{b}EUV_13_5NM_CALIBRATED{b}** + **{b}CD_SEM_SCAN{b}** on {b}DISPLAY=:99{b} into {b}OPC_CDSEM!B2:C5{b} (keeping {b}B6:C6{b} formulas).",
        f"2. Update {b}sram_density{b} ({b}64x64{b}) in {b}reticle_density.npz{b} so {b}sram_mean_density_pct{b} is in **{b}[58.0, 64.0]%{b}** respecting both CMP erosion ceilings ({b}<= 98.9 nm{b}).",
        f"3. Certify ordered stages ({b}sram_tile_grid_gate -> aerial_contrast_gate -> cdsem_wafer_sync -> sram_erosion_budget -> full_tapeout_drc{b}) on {b}POST /api/bench/litho_cmp_sim{b} ({b}subsystem='opc_sram_ret'{b}) and submit to {b}POST /api/fab/submit{b}:",
        f"   {b}{{\"subsystem\": \"opc_sram_ret\", \"mean_density_pct\": <float>, \"erosion_nm\": <float>, \"npz_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}EUV_13_5NM_CALIBRATED{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    cmp_txt = "\n".join([
        f"# CMP Planarization Work Order — FC-15 ({b}cmp_analog_planar_lead{b})",
        "",
        f"Tune {b}analog_density{b} in {b}reticle_density.npz{b} and populate {b}CMP_Profilometry{b} in {b}Tapeout_Metrology.xlsx{b} under {b}CMP_SLURRY_PH10_REF{b}.",
        "",
        "### CMP Steps",
        f"1. Scan {b}DIE_NW..DIE_SE{b} under **{b}CMP_SLURRY_PH10_REF{b}** + **{b}CMP_PROFILER{b}** on {b}DISPLAY=:99{b} into {b}CMP_Profilometry!B2:C5{b} (keeping {b}B6:C6{b} formulas).",
        f"2. Update {b}analog_density{b} ({b}64x64{b}) in {b}reticle_density.npz{b} so {b}analog_mean_density_pct{b} is in **{b}[58.0, 64.0]%{b}** respecting both CMP erosion ceilings ({b}<= 98.9 nm{b}).",
        f"3. Certify ordered stages ({b}inductor_tile_grid_gate -> planar_uniformity_gate -> profilometer_wafer_sync -> inductor_erosion_budget -> full_tapeout_drc{b}) on {b}POST /api/bench/litho_cmp_sim{b} ({b}subsystem='cmp_analog_planar'{b}) and submit to {b}POST /api/fab/submit{b}:",
        f"   {b}{{\"subsystem\": \"cmp_analog_planar\", \"mean_density_pct\": <float>, \"erosion_nm\": <float>, \"npz_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}CMP_SLURRY_PH10_REF{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"opc_sram_ret_lead": opc_txt, "cmp_analog_planar_lead": cmp_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    import numpy as np

    rt = workspace / "reticle_5nm"
    rt.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    np.savez(
        rt / "reticle_density.npz",
        sram_density=np.full((64, 64), 22.0, dtype=np.float64),
        analog_density=np.full((64, 64), 22.0, dtype=np.float64),
    )
    o_rows = [["Die", "CD_nm", "LWR_nm"]] + [[d, 0.0, 0.0] for d in DIES] + [["MEAN", ("=AVERAGE(B2:B5)", 0.0), ("=AVERAGE(C2:C5)", 0.0)]]
    c_rows = [["Die", "Oxide_nm", "Dishing_nm"]] + [[d, 0.0, 0.0] for d in DIES] + [["MEAN", ("=AVERAGE(B2:B5)", 0.0), ("=AVERAGE(C2:C5)", 0.0)]]
    write_multisheet_xlsx(rt / "Tapeout_Metrology.xlsx", [("OPC_CDSEM", o_rows), ("CMP_Profilometry", c_rows)])

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_fab_plate_png(cal: str, tool: str, die: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (12, 12, 24))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(244, 114, 182), width=2)
    dr.text((24, 24), f"5NM EUV METROLOGY & CMP CONSOLE  |  Calib: {cal}  |  Tool: {tool}  |  Die: {die}", fill=(244, 114, 182))
    dr.text((24, 54), "CMP Oxide Erosion Law: D_i + 0.60 * D_j <= 98.9 nm  |  Density in [58.0, 64.0]%", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "WAFER STAGE VACUUM SCAN IN PROGRESS (6.5s)..." if busy else "IDLE — Click [Run 6.5s Wafer Metrology Scan]"
    dr.text((28, 118), f"Stage Status   : {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Export Target  : {cal} / {tool} / {die} -> /home/gui/Downloads/wafer_metrology.csv", fill=(241, 245, 249))
    dr.ellipse([(500, 210), (720, 430)], outline=(56, 189, 248), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>5nm Fab Metrology Console — FC-15</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #db2777; }
    #msg { color: #f472b6; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>CALIB:</strong>
    <button onclick="setF({cal:'EUV_13_5NM_CALIBRATED'})">EUV_13_5NM_CALIBRATED</button>
    <button onclick="setF({cal:'CMP_SLURRY_PH10_REF'})">CMP_SLURRY_PH10_REF</button>
    <strong>TOOL:</strong>
    <button onclick="setF({tool:'CD_SEM_SCAN'})">CD_SEM_SCAN</button>
    <button onclick="setF({tool:'CMP_PROFILER'})">CMP_PROFILER</button>
    <strong>DIE:</strong>
    <button onclick="setF({die:'DIE_NW'})">DIE_NW</button>
    <button onclick="setF({die:'DIE_NE'})">DIE_NE</button>
    <button onclick="setF({die:'DIE_SW'})">DIE_SW</button>
    <button onclick="setF({die:'DIE_SE'})">DIE_SE</button>
  </div>
  <div class="bar">
    <button onclick="scanDie()">Run 6.5s Wafer Metrology Scan (/home/gui/Downloads/wafer_metrology.csv)</button>
    <span id="msg">Fab Metrology SSO Active</span>
  </div>
  <canvas id="f-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/reticle_5nm/reticle_density.npz /workspace/reticle_5nm/Tapeout_Metrology.xlsx
       sram_density analog_density OPC_CDSEM CMP_Profilometry EUV_13_5NM_CALIBRATED
       /api/bench/litho_cmp_sim /api/fab/submit /api/fab/status 58.0 64.0 0.60 98.9 full_tapeout_drc -->
  <script>
    function drawF() {
      const cv = document.getElementById('f-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/fab_plate.png?t=' + Date.now();
    }
    async function setF(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.cal || '') + ' | ' + (d.tool || '') + ' | ' + (d.die || '');
      drawF();
    }
    async function scanDie() {
      document.getElementById('msg').textContent = 'Running 6.5s wafer scan...';
      drawF();
      const r = await fetch('/api/ui/scan_die', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawF();
    }
    drawF();
    setInterval(drawF, 3000);
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
        role_tokens.get("opc_sram_ret_lead", ""): "opc_sram_ret",
        role_tokens.get("cmp_analog_planar_lead", ""): "cmp_analog_planar",
    }

    state_lock = threading.Lock()
    sub_locks = {"opc_sram_ret": threading.Lock(), "cmp_analog_planar": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"cal": "CMP_SLURRY_PH10_REF", "tool": "CD_SEM_SCAN", "die": "DIE_NW", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"opc_sram_ret": {}, "cmp_analog_planar": {}},
        "qualified_stages": {"opc_sram_ret": {}, "cmp_analog_planar": {}},
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
                m = c.get("fc15_sso")
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
                    self.send_header("Set-Cookie", f"fc15_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/fab_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_fab_plate_png(u["cal"], u["tool"], u["die"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/fab/status":
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
                    if body.get("cal") in ("EUV_13_5NM_CALIBRATED", "CMP_SLURRY_PH10_REF"):
                        if pstate["ui_session"]["cal"] != body["cal"]:
                            changed = True
                        pstate["ui_session"]["cal"] = body["cal"]
                    if body.get("tool") in ("CD_SEM_SCAN", "CMP_PROFILER"):
                        if pstate["ui_session"]["tool"] != body["tool"]:
                            changed = True
                        pstate["ui_session"]["tool"] = body["tool"]
                    if body.get("die") in DIES:
                        pstate["ui_session"]["die"] = body["die"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/scan_die":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 6.5)
                dl_p = Path("/home/gui/Downloads/wafer_metrology.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    cl = pstate["ui_session"]["cal"]
                    tl = pstate["ui_session"]["tool"]
                    di = pstate["ui_session"]["die"]
                    src_tbl = TRUE_OPC_CDSEM if tl == "CD_SEM_SCAN" else TRUE_CMP_PROFILER
                    exp_cl = "EUV_13_5NM_CALIBRATED" if tl == "CD_SEM_SCAN" else "CMP_SLURRY_PH10_REF"
                    mult = 1.0 if cl == exp_cl else 1.155
                    v1, v2 = src_tbl[di]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"die_id,val_primary,val_secondary\n{di},{round(v1*mult, 2)},{round(v2*mult, 3)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/litho_cmp_sim":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("opc_sram_ret", "cmp_analog_planar"):
                    self._json(400, {"error": "subsystem must be 'opc_sram_ret' or 'cmp_analog_planar'"})
                    return
                seq_list = OPC_STAGES if sub == "opc_sram_ret" else CMP_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "EUV_13_5NM_CALIBRATED" if sub == "opc_sram_ret" else "CMP_SLURRY_PH10_REF"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["cal"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_fab_workspace(workspace)
                    errs = check_fab_constraints(
                        info,
                        check_opc=(sub == "opc_sram_ret"),
                        check_cmp=(sub == "cmp_analog_planar"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    fft = run_hopkins_aerial_fft(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
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
                    "own_mean_density_pct": s.get("sram_mean_density_pct") if sub == "opc_sram_ret" else s.get("analog_mean_density_pct"),
                    "own_oxide_erosion_nm": s.get("sram_oxide_erosion_nm") if sub == "opc_sram_ret" else s.get("analog_oxide_erosion_nm"),
                }
                self._json(200, {"ok": True, "subsystem": sub, "stage": stage, "passed": passed, "discrepancies": errs, "fab_metrics": own_m, "aerial_fft": fft, "elapsed_s": elapsed})
                return

            if p == "/api/fab/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("opc_sram_ret", "cmp_analog_planar"):
                    self._json(400, {"error": "subsystem must be 'opc_sram_ret' or 'cmp_analog_planar'"})
                    return
                info = inspect_fab_workspace(workspace)
                errs = check_fab_constraints(
                    info,
                    check_opc=(sub == "opc_sram_ret"),
                    check_cmp=(sub == "cmp_analog_planar"),
                    stage="full_tapeout_drc",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = OPC_STAGES if sub == "opc_sram_ret" else CMP_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified litho_cmp_sim stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                npz_sha = sha256_file(workspace / "reticle_5nm" / "reticle_density.npz")
                exp_d = s.get("sram_mean_density_pct", -1.0) if sub == "opc_sram_ret" else s.get("analog_mean_density_pct", -1.0)
                exp_e = s.get("sram_oxide_erosion_nm", -1.0) if sub == "opc_sram_ret" else s.get("analog_oxide_erosion_nm", -1.0)
                try:
                    if abs(float(body.get("mean_density_pct", -999)) - exp_d) > 0.25:
                        errs.append(f"Submitted mean_density_pct != live {exp_d}")
                    if abs(float(body.get("erosion_nm", -999)) - exp_e) > 0.35:
                        errs.append(f"Submitted erosion_nm != live {exp_e}")
                    if str(body.get("npz_sha256") or "") != npz_sha:
                        errs.append("Submitted npz_sha256 != sha256(reticle_density.npz)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_FAB_SIGNOFF", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "mean_density_pct": exp_d,
                    "erosion_nm": exp_e,
                    "npz_sha256": npz_sha,
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
    o_signed = (subs.get("opc_sram_ret") or {}).get("status") == "APPROVED"
    c_signed = (subs.get("cmp_analog_planar") or {}).get("status") == "APPROVED"
    closed_cnt = int(o_signed) + int(c_signed)

    info = inspect_fab_workspace(workspace)
    all_errs = check_fab_constraints(info, check_opc=True, check_cmp=True, stage="full_tapeout_drc", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "opc_sram_ret", OPC_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "cmp_analog_planar", CMP_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "opc_sram_grid_and_cdsem_canaries_valid": bool(len(pur_a_errs) == 0 and o_signed and info.get("ok") and not any("OPC_CDSEM" in e or "sram_" in e for e in all_errs)),
        "cmp_analog_grid_and_profiler_canaries_valid": bool(len(pur_b_errs) == 0 and c_signed and info.get("ok") and not any("CMP_Profilometry" in e or "analog_" in e for e in all_errs)),
        "both_cmp_erosion_caps_valid": bool(info.get("ok") and s.get("sram_oxide_erosion_nm", 999) <= MAX_EROSION_NM and s.get("analog_oxide_erosion_nm", 999) <= MAX_EROSION_NM),
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
        "fab_summary": s,
        "diagnostics": {
            "fab_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    import numpy as np

    assert role in ("opc_sram_ret_lead", "cmp_analog_planar_lead")
    rt = workspace / "reticle_5nm"
    npz_p = rt / "reticle_density.npz"
    xp = rt / "Tapeout_Metrology.xlsx"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_opc = (role == "opc_sram_ret_lead")
    tl = "CD_SEM_SCAN" if is_opc else "CMP_PROFILER"
    sub = "opc_sram_ret" if is_opc else "cmp_analog_planar"

    swept = {}
    for di in DIES:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"cal": ("EUV_13_5NM_CALIBRATED" if is_opc else "CMP_SLURRY_PH10_REF"), "tool": tl, "die": di}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/scan_die", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/wafer_metrology.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        swept[di] = (float(row[1]), float(row[2]))

    with np.load(npz_p) as data:
        sram_g = np.array(data["sram_density"], dtype=np.float64)
        ana_g = np.array(data["analog_density"], dtype=np.float64)

    if is_opc:
        peer_d = float(np.mean(ana_g))
        my_d = round(max(58.2, min(63.5, (98.6 - peer_d) / SLURRY_COUPLING, 98.6 - SLURRY_COUPLING * peer_d)), 2) if peer_d >= 58.0 else 61.2
        sram_g = np.full((64, 64), my_d, dtype=np.float64)
        rows = [["Die", "CD_nm", "LWR_nm"]] + [[d, swept[d][0], swept[d][1]] for d in DIES] + [["MEAN", ("=AVERAGE(B2:B5)", round(sum(swept[x][0] for x in DIES)/4, 2)), ("=AVERAGE(C2:C5)", round(sum(swept[x][1] for x in DIES)/4, 3))]]
        update_single_sheet_xlsx(xp, "OPC_CDSEM", rows)
    else:
        peer_d = float(np.mean(sram_g))
        my_d = round(max(58.2, min(63.5, (98.6 - peer_d) / SLURRY_COUPLING, 98.6 - SLURRY_COUPLING * peer_d)), 2) if peer_d >= 58.0 else 61.2
        ana_g = np.full((64, 64), my_d, dtype=np.float64)
        rows = [["Die", "Oxide_nm", "Dishing_nm"]] + [[d, swept[d][0], swept[d][1]] for d in DIES] + [["MEAN", ("=AVERAGE(B2:B5)", round(sum(swept[x][0] for x in DIES)/4, 2)), ("=AVERAGE(C2:C5)", round(sum(swept[x][1] for x in DIES)/4, 2))]]
        update_single_sheet_xlsx(xp, "CMP_Profilometry", rows)
    np.savez(npz_p, sram_density=sram_g, analog_density=ana_g)

    stages = OPC_STAGES if is_opc else CMP_STAGES
    for stg in stages:
        code, resp = post_json(f"{base}/api/bench/litho_cmp_sim", {"subsystem": sub, "stage": stg}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {stg} failed: {resp}"

    s1 = inspect_fab_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/fab/submit", {
        "subsystem": sub,
        "mean_density_pct": s1["sram_mean_density_pct"] if is_opc else s1["analog_mean_density_pct"],
        "erosion_nm": s1["sram_oxide_erosion_nm"] if is_opc else s1["analog_oxide_erosion_nm"],
        "npz_sha256": sha256_file(npz_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    import numpy as np

    rt = workspace / "reticle_5nm"
    npz_p = rt / "reticle_density.npz"
    xp = rt / "Tapeout_Metrology.xlsx"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("opc_sram_ret_lead", workspace, portal_port, strict=True)
    np.savez(npz_p, sram_density=np.full((64, 64), 63.0, dtype=np.float64), analog_density=np.full((64, 64), 60.5, dtype=np.float64))
    rows = [["Die", "Oxide_nm", "Dishing_nm"]] + [[d, TRUE_CMP_PROFILER[d][0]*1.155, TRUE_CMP_PROFILER[d][1]*1.155] for d in DIES] + [["MEAN", ("=AVERAGE(B2:B5)", 360.0), ("=AVERAGE(C2:C5)", 16.0)]]
    update_single_sheet_xlsx(xp, "CMP_Profilometry", rows)
    for stg in CMP_STAGES:
        post_json(f"{base}/api/bench/litho_cmp_sim", {"subsystem": "cmp_analog_planar", "stage": stg}, timeout_s=240)
    s1 = inspect_fab_workspace(workspace)["summary"]
    post_json(f"{base}/api/fab/submit", {"subsystem": "cmp_analog_planar", "mean_density_pct": s1["analog_mean_density_pct"], "erosion_nm": s1["analog_oxide_erosion_nm"], "npz_sha256": sha256_file(npz_p)}, timeout_s=60)
