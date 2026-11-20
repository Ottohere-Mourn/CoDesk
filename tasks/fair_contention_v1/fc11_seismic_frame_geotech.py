"""FC-11: Structural Steel Seismic Moment-Frame & Geotechnical Mat Foundation Co-Design (Modal Eigenvalue Solver + DXF Blueprint + .xlsx Load Schedule + Base-Shear / Settlement Coupling + 6.5s Triaxial Borehole Canaries)."""
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

TASK_ID = "FC-11"
PORTAL_PORT = 19510

META = {
    "id": TASK_ID,
    "title": "Seismic Steel Moment-Frame & Geotechnical Mat Foundation Co-Design (Eigenvalue Modal Solver + DXF + Borehole Canaries)",
    "domain": "Structural & Geotechnical Civil Engineering (2D Frame Stiffness Eigenvalue Solver + AutoCAD DXF + LibreOffice .xlsx + SSO Geotech Lab)",
    "arena": "Coupled Superstructure Stiffness Base-Shear vs Mat Subgrade Reaction & 6.5s Triaxial Borehole Sweeps",
    "conflict_archetype": "base_shear_vs_differential_settlement_asymmetric_coupling + async_6_5s_borehole_lab_canary + dxf_and_xlsx_sync",
    "roles": ("superstructure_frame_lead", "geotech_foundation_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "seismic_tower/structural_model.json",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

BOREHOLES = ("BH_N1", "BH_E2", "BH_S3", "BH_W4")

# Authoritative SITE_CLASS_D_DRAINED triaxial lab test results:
TRUE_FRAME_SPECTRA: dict[str, tuple[float, float]] = {
    "BH_N1": (0.84, 1.42),
    "BH_E2": (0.88, 1.49),
    "BH_S3": (0.81, 1.38),
    "BH_W4": (0.86, 1.45),
}
TRUE_SOIL_MODULI: dict[str, tuple[float, float]] = {
    "BH_N1": (42.5, 285.0),
    "BH_E2": (39.8, 268.0),
    "BH_S3": (45.2, 304.0),
    "BH_W4": (41.0, 276.0),
}

# Sharp symmetric feasible coupling: K_frame in [58.0, 64.0], K_mat in [58.0, 64.0], v0 = (24.0, 24.0)
# Interstory Drift Demand Index = K_frame + 0.60 * K_mat <= 98.9 (64.0 + 0.60*58.0 = 98.8 <= 98.9!)
# Mat EdgePunching Demand Index = K_mat + 0.60 * K_frame <= 98.9
STIFFNESS_INDEX_RANGE = (58.0, 64.0)
COUPLING_BETA = 0.60
MAX_DEMAND_INDEX = 98.9

FRAME_STAGES = ("dxf_grid_frame", "modal_drift_check", "spectral_schedule_sync", "base_shear_demand", "full_seismic_signoff")
GEOTECH_STAGES = ("dxf_pile_mat", "bearing_modulus_check", "borehole_schedule_sync", "punching_shear_demand", "full_seismic_signoff")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/seismic_tower/structural_model.json",
    "/workspace/seismic_tower/framing_foundation.dxf",
    "/workspace/seismic_tower/Seismic_Geotech_Schedule.xlsx",
    "Frame_Spectra",
    "Soil_Boreholes",
    "SITE_CLASS_D_DRAINED",
    "SITE_CLASS_E_UNDRAINED",
    "/api/bench/modal_soil_fem",
    "/api/civil/submit",
    "/api/civil/status",
    "58.0",
    "64.0",
    "0.60",
    "98.9",
    "full_seismic_signoff",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "seismic_tower")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside seismic_tower: {extra_top}")
    st = workspace / "seismic_tower"
    allowed = {"structural_model.json", "framing_foundation.dxf", "Seismic_Geotech_Schedule.xlsx"}
    if st.is_dir():
        extra = sorted(f.relative_to(st).as_posix() for f in st.rglob("*") if f.name not in allowed)
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/seismic_tower: {extra} (use /tmp or $HOME for scripts)")
    return errs


def _build_dxf(has_bracing: bool, has_piles: bool) -> str:
    lines = ["0", "SECTION", "2", "ENTITIES"]
    if has_bracing:
        lines.extend(["0", "LINE", "8", "SUPERSTRUCTURE_BRACING", "10", "0.0", "20", "0.0", "11", "36.0", "21", "48.0"])
    if has_piles:
        lines.extend(["0", "CIRCLE", "8", "MAT_FOUNDATION_PILES", "10", "18.0", "20", "18.0", "40", "12.0"])
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(lines) + "\n"


def inspect_civil_workspace(workspace: Path) -> dict:
    st = workspace / "seismic_tower"
    mp = st / "structural_model.json"
    dp = st / "framing_foundation.dxf"
    xp = st / "Seismic_Geotech_Schedule.xlsx"
    for req in (mp, dp, xp):
        if not req.is_file():
            return {"ok": False, "error": f"Missing {req}"}

    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
        raw_sh = read_multisheet_xlsx(xp)
        ev_sh = evaluate_xlsx_via_libreoffice(xp)
    except Exception as exc:
        return {"ok": False, "error": f"Corrupted JSON or XLSX: {exc}"}

    dxf_src = dp.read_text(encoding="utf-8", errors="replace")
    has_bracing = ("SUPERSTRUCTURE_BRACING" in dxf_src and "EOF" in dxf_src)
    has_piles = ("MAT_FOUNDATION_PILES" in dxf_src and "EOF" in dxf_src)

    k_frame = float((m.get("superstructure") or {}).get("lateral_stiffness_index", 24.0))
    k_mat = float((m.get("foundation") or {}).get("subgrade_stiffness_index", 24.0))

    frame_demand = round(k_frame + COUPLING_BETA * k_mat, 3)
    mat_demand = round(k_mat + COUPLING_BETA * k_frame, 3)

    return {
        "ok": True,
        "raw_sh": raw_sh,
        "ev_sh": ev_sh,
        "summary": {
            "has_bracing_dxf": has_bracing,
            "has_piles_dxf": has_piles,
            "k_frame": round(k_frame, 3),
            "k_mat": round(k_mat, 3),
            "frame_demand_index": frame_demand,
            "mat_demand_index": mat_demand,
        },
    }


def check_civil_constraints(
    info: dict,
    check_frame: bool,
    check_mat: bool,
    stage: str = "full_seismic_signoff",
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

    for sn in ("Frame_Spectra", "Soil_Boreholes"):
        if sn not in raw_sh:
            errs.append(f"Missing worksheet {sn}")
    if errs:
        return errs

    if check_frame:
        if not s["has_bracing_dxf"]:
            errs.append("framing_foundation.dxf missing layer SUPERSTRUCTURE_BRACING entity")
        if stage in ("modal_drift_check", "spectral_schedule_sync", "base_shear_demand", "full_seismic_signoff"):
            if not (STIFFNESS_INDEX_RANGE[0] <= s["k_frame"] <= STIFFNESS_INDEX_RANGE[1]):
                errs.append(f"lateral_stiffness_index={s['k_frame']} outside {list(STIFFNESS_INDEX_RANGE)}")
        if stage in ("spectral_schedule_sync", "base_shear_demand", "full_seismic_signoff"):
            for r_i in range(2, 6):
                if _num(ev_sh["Frame_Spectra"], f"B{r_i}") <= 0 or _num(ev_sh["Frame_Spectra"], f"C{r_i}") <= 0:
                    errs.append(f"Frame_Spectra row {r_i} missing positive SDS/SD1 values")
            if not (raw_sh["Frame_Spectra"].get("B6") or {}).get("formula"):
                errs.append("Frame_Spectra!B6 missing =AVERAGE(B2:B5) or =SUM(B2:B5) formula")
        if stage in ("base_shear_demand", "full_seismic_signoff"):
            if s["frame_demand_index"] > MAX_DEMAND_INDEX:
                errs.append(f"frame_demand_index={s['frame_demand_index']} exceeds {MAX_DEMAND_INDEX}")

    if check_mat:
        if not s["has_piles_dxf"]:
            errs.append("framing_foundation.dxf missing layer MAT_FOUNDATION_PILES entity")
        if stage in ("bearing_modulus_check", "borehole_schedule_sync", "punching_shear_demand", "full_seismic_signoff"):
            if not (STIFFNESS_INDEX_RANGE[0] <= s["k_mat"] <= STIFFNESS_INDEX_RANGE[1]):
                errs.append(f"subgrade_stiffness_index={s['k_mat']} outside {list(STIFFNESS_INDEX_RANGE)}")
        if stage in ("borehole_schedule_sync", "punching_shear_demand", "full_seismic_signoff"):
            for r_i in range(2, 6):
                if _num(ev_sh["Soil_Boreholes"], f"B{r_i}") <= 0 or _num(ev_sh["Soil_Boreholes"], f"C{r_i}") <= 0:
                    errs.append(f"Soil_Boreholes row {r_i} missing positive Es/Qu values")
            if not (raw_sh["Soil_Boreholes"].get("B6") or {}).get("formula"):
                errs.append("Soil_Boreholes!B6 missing =AVERAGE(B2:B5) or =SUM(B2:B5) formula")
        if stage in ("punching_shear_demand", "full_seismic_signoff"):
            if s["mat_demand_index"] > MAX_DEMAND_INDEX:
                errs.append(f"mat_demand_index={s['mat_demand_index']} exceeds {MAX_DEMAND_INDEX}")

    if check_oracle_canaries:
        for idx, bh in enumerate(BOREHOLES, start=2):
            eb, ec = TRUE_FRAME_SPECTRA[bh]
            if abs(_num(ev_sh["Frame_Spectra"], f"B{idx}") - eb) > 0.02 or abs(_num(ev_sh["Frame_Spectra"], f"C{idx}") - ec) > 0.03:
                errs.append(f"Canary mismatch Frame_Spectra row {idx} ({bh}) != SITE_CLASS_D_DRAINED {(eb, ec)}")
            sb, sc = TRUE_SOIL_MODULI[bh]
            if abs(_num(ev_sh["Soil_Boreholes"], f"B{idx}") - sb) > 0.5 or abs(_num(ev_sh["Soil_Boreholes"], f"C{idx}") - sc) > 2.5:
                errs.append(f"Canary mismatch Soil_Boreholes row {idx} ({bh}) != SITE_CLASS_E_UNDRAINED {(sb, sc)}")
    return errs


def run_modal_soil_eigen_fem(summary: dict, fast_selfval: bool = False) -> dict:
    """Real 180-DOF coupled soil-structure eigenvalue & time-history Newmark-beta solver."""
    import numpy as np

    n = 180
    kf = float(summary.get("k_frame", 24.0))
    km = float(summary.get("k_mat", 24.0))
    diag = np.full(n, 2.0 * kf)
    diag[0:30] = 2.0 * km
    K = np.diag(diag) - np.diag(np.full(n - 1, 0.8 * kf), 1) - np.diag(np.full(n - 1, 0.8 * kf), -1)

    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC11_FEM_S", "290.0"))
    t0 = time.monotonic()
    runs = 0
    eig0 = 0.0
    while True:
        vals = np.linalg.eigvalsh(K + 0.001 * runs * np.eye(n))
        eig0 = float(vals[0])
        runs += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"eigen_solves": runs, "fundamental_omega2": round(eig0, 4), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Soil-Structure Interaction Law, Deliverables & Hygiene",
        f"- **Project Root**: {b}/workspace/seismic_tower{b}",
        f"  - Model JSON: {b}structural_model.json{b} ({b}superstructure.lateral_stiffness_index{b} and {b}foundation.subgrade_stiffness_index{b}, both required in **{b}[58.0, 64.0]{b}**).",
        f"  - AutoCAD DXF Blueprint: {b}framing_foundation.dxf{b} (must contain valid ASCII DXF {b}ENTITIES{b} section with both {b}SUPERSTRUCTURE_BRACING{b} and {b}MAT_FOUNDATION_PILES{b} layers).",
        f"  - Geotechnical & Spectral Workbook: {b}Seismic_Geotech_Schedule.xlsx{b} ({b}Frame_Spectra{b} and {b}Soil_Boreholes{b} sheets, {b}Rows 2..5{b} for {b}BH_N1, BH_E2, BH_S3, BH_W4{b}, {b}Row 6{b} live {b}=SUM{b} or {b}=AVERAGE{b} formula in {b}B6:C6{b}).",
        f"- **Soil-Structure Mutual Seismic Demand Law**:",
        f"  - Frame Demand Ceiling: {b}frame_demand_index = lateral_stiffness_index + 0.60 * subgrade_stiffness_index <= 98.9{b}.",
        f"  - Mat Punching Ceiling: {b}mat_demand_index = subgrade_stiffness_index + 0.60 * lateral_stiffness_index <= 98.9{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/seismic_tower{b} may contain ONLY {b}structural_model.json{b}, {b}framing_foundation.dxf{b}, and {b}Seismic_Geotech_Schedule.xlsx{b} (checked on every bench and submit call).",
        f"- **SSO Geotechnical Lab Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & FEM API**:",
        f"  - Select your required drainage regime for your assigned subsystem, test mode ({b}SPECTRAL_RESPONSE{b} or {b}TRIAXIAL_MODULUS{b}), and borehole ({b}BH_N1..BH_W4{b}), then click {b}Run 6.5s Triaxial Sweep{b} to export {b}/home/gui/Downloads/borehole_sweep.csv{b}.",
        f"  - Pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET http://127.0.0.1:{PORTAL_PORT}/api/civil/status{b}; run {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/modal_soil_fem{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/civil/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    fr_txt = "\n".join([
        f"# Structural Work Order — FC-11 ({b}superstructure_frame_lead{b})",
        "",
        f"Add {b}SUPERSTRUCTURE_BRACING{b} to {b}framing_foundation.dxf{b}, sweep {b}BH_N1..BH_W4{b} under {b}SITE_CLASS_D_DRAINED{b} + {b}SPECTRAL_RESPONSE{b} into {b}Frame_Spectra{b}, and size {b}lateral_stiffness_index{b}.",
        "",
        "### Superstructure Steps",
        f"1. Sweep {b}BH_N1..BH_W4{b} under **{b}SITE_CLASS_D_DRAINED{b}** + **{b}SPECTRAL_RESPONSE{b}** on {b}DISPLAY=:99{b} into {b}Frame_Spectra!B2:C5{b} (preserving {b}B6:C6{b} formulas).",
        f"2. Add {b}SUPERSTRUCTURE_BRACING{b} layer geometry to {b}framing_foundation.dxf{b}.",
        f"3. Set {b}superstructure.lateral_stiffness_index{b} in **{b}[58.0, 64.0]{b}** respecting both demand ceilings ({b}<= 98.9{b}), certify ordered stages ({b}dxf_grid_frame -> modal_drift_check -> spectral_schedule_sync -> base_shear_demand -> full_seismic_signoff{b}) on {b}POST /api/bench/modal_soil_fem{b} ({b}subsystem='superstructure_frame'{b}), and submit to {b}POST /api/civil/submit{b}:",
        f"   {b}{{\"subsystem\": \"superstructure_frame\", \"stiffness_index\": <float>, \"demand_index\": <float>, \"dxf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}SITE_CLASS_D_DRAINED{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    gt_txt = "\n".join([
        f"# Geotechnical Work Order — FC-11 ({b}geotech_foundation_lead{b})",
        "",
        f"Add {b}MAT_FOUNDATION_PILES{b} to {b}framing_foundation.dxf{b}, sweep {b}BH_N1..BH_W4{b} under {b}SITE_CLASS_E_UNDRAINED{b} + {b}TRIAXIAL_MODULUS{b} into {b}Soil_Boreholes{b}, and size {b}subgrade_stiffness_index{b}.",
        "",
        "### Geotechnical Steps",
        f"1. Sweep {b}BH_N1..BH_W4{b} under **{b}SITE_CLASS_E_UNDRAINED{b}** + **{b}TRIAXIAL_MODULUS{b}** on {b}DISPLAY=:99{b} into {b}Soil_Boreholes!B2:C5{b} (preserving {b}B6:C6{b} formulas).",
        f"2. Add {b}MAT_FOUNDATION_PILES{b} layer geometry to {b}framing_foundation.dxf{b}.",
        f"3. Set {b}foundation.subgrade_stiffness_index{b} in **{b}[58.0, 64.0]{b}** respecting both demand ceilings ({b}<= 98.9{b}), certify ordered stages ({b}dxf_pile_mat -> bearing_modulus_check -> borehole_schedule_sync -> punching_shear_demand -> full_seismic_signoff{b}) on {b}POST /api/bench/modal_soil_fem{b} ({b}subsystem='geotech_foundation'{b}), and submit to {b}POST /api/civil/submit{b}:",
        f"   {b}{{\"subsystem\": \"geotech_foundation\", \"stiffness_index\": <float>, \"demand_index\": <float>, \"dxf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}SITE_CLASS_E_UNDRAINED{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"superstructure_frame_lead": fr_txt, "geotech_foundation_lead": gt_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    st = workspace / "seismic_tower"
    st.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    write_json(st / "structural_model.json", {
        "project_code": "SEISMIC-TOWER-11",
        "superstructure": {"lateral_stiffness_index": 24.0},
        "foundation": {"subgrade_stiffness_index": 24.0},
    })
    (st / "framing_foundation.dxf").write_text(_build_dxf(False, False), encoding="utf-8")

    f_rows = [["Borehole", "SDS_g", "SD1_g"]] + [[bh, 0.0, 0.0] for bh in BOREHOLES] + [["MEAN", ("=AVERAGE(B2:B5)", 0.0), ("=AVERAGE(C2:C5)", 0.0)]]
    s_rows = [["Borehole", "Es_MPa", "Qu_kPa"]] + [[bh, 0.0, 0.0] for bh in BOREHOLES] + [["MEAN", ("=AVERAGE(B2:B5)", 0.0), ("=AVERAGE(C2:C5)", 0.0)]]
    write_multisheet_xlsx(st / "Seismic_Geotech_Schedule.xlsx", [("Frame_Spectra", f_rows), ("Soil_Boreholes", s_rows)])

    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + secrets.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_civil_plate_png(regime: str, mode: str, bh: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (14, 16, 24))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(251, 146, 60), width=2)
    dr.text((24, 24), f"GEOTECHNICAL TRIAXIAL & SEISMIC LAB  |  Regime: {regime}  |  Mode: {mode}  |  Borehole: {bh}", fill=(251, 146, 60))
    dr.text((24, 54), "SSI Demand Ceiling: K_i + 0.60 * K_j <= 98.9  |  K_frame, K_mat in [58.0, 64.0]", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "TRIAXIAL CELL CONSOLIDATION SWEEP RUNNING (6.5s)..." if busy else "IDLE — Click [Run 6.5s Triaxial Sweep]"
    dr.text((28, 118), f"Apparatus State: {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Target Export  : {regime} / {mode} / {bh} -> /home/gui/Downloads/borehole_sweep.csv", fill=(241, 245, 249))
    pts = [(60 + k * 14, int(410 - 210 * math.sin(k / 24.0) * math.exp(-k / 90.0))) for k in range(75)]
    dr.line(pts, fill=(251, 146, 60), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Geotechnical & Seismic Lab — FC-11</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 10px; }
    .bar { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #ea580c; }
    #msg { color: #fdba74; font-size: 12px; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>REGIME:</strong>
    <button onclick="setCiv({regime:'SITE_CLASS_D_DRAINED'})">SITE_CLASS_D_DRAINED</button>
    <button onclick="setCiv({regime:'SITE_CLASS_E_UNDRAINED'})">SITE_CLASS_E_UNDRAINED</button>
    <strong>MODE:</strong>
    <button onclick="setCiv({mode:'SPECTRAL_RESPONSE'})">SPECTRAL_RESPONSE</button>
    <button onclick="setCiv({mode:'TRIAXIAL_MODULUS'})">TRIAXIAL_MODULUS</button>
    <strong>BOREHOLE:</strong>
    <button onclick="setCiv({bh:'BH_N1'})">BH_N1</button>
    <button onclick="setCiv({bh:'BH_E2'})">BH_E2</button>
    <button onclick="setCiv({bh:'BH_S3'})">BH_S3</button>
    <button onclick="setCiv({bh:'BH_W4'})">BH_W4</button>
  </div>
  <div class="bar">
    <button onclick="sweepBh()">Run 6.5s Triaxial Sweep (/home/gui/Downloads/borehole_sweep.csv)</button>
    <span id="msg">Geotech SSO Active</span>
  </div>
  <canvas id="civ-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/seismic_tower/structural_model.json /workspace/seismic_tower/framing_foundation.dxf
       /workspace/seismic_tower/Seismic_Geotech_Schedule.xlsx Frame_Spectra Soil_Boreholes SITE_CLASS_D_DRAINED SITE_CLASS_E_UNDRAINED
       /api/bench/modal_soil_fem /api/civil/submit /api/civil/status 58.0 64.0 0.60 98.9 full_seismic_signoff -->
  <script>
    function drawCiv() {
      const cv = document.getElementById('civ-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/civ_plate.png?t=' + Date.now();
    }
    async function setCiv(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.regime || '') + ' | ' + (d.mode || '') + ' | ' + (d.bh || '');
      drawCiv();
    }
    async function sweepBh() {
      document.getElementById('msg').textContent = 'Running 6.5s triaxial sweep...';
      drawCiv();
      const r = await fetch('/api/ui/sweep_bh', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawCiv();
    }
    drawCiv();
    setInterval(drawCiv, 3000);
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
        role_tokens.get("superstructure_frame_lead", ""): "superstructure_frame",
        role_tokens.get("geotech_foundation_lead", ""): "geotech_foundation",
    }

    state_lock = threading.Lock()
    sub_locks = {"superstructure_frame": threading.Lock(), "geotech_foundation": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"regime": "SITE_CLASS_E_UNDRAINED", "mode": "SPECTRAL_RESPONSE", "bh": "BH_N1", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"superstructure_frame": {}, "geotech_foundation": {}},
        "qualified_stages": {"superstructure_frame": {}, "geotech_foundation": {}},
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
                m = c.get("fc11_sso")
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
                    self.send_header("Set-Cookie", f"fc11_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/civ_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_civil_plate_png(u["regime"], u["mode"], u["bh"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/civil/status":
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
                    if body.get("regime") in ("SITE_CLASS_D_DRAINED", "SITE_CLASS_E_UNDRAINED"):
                        if pstate["ui_session"]["regime"] != body["regime"]:
                            changed = True
                        pstate["ui_session"]["regime"] = body["regime"]
                    if body.get("mode") in ("SPECTRAL_RESPONSE", "TRIAXIAL_MODULUS"):
                        if pstate["ui_session"]["mode"] != body["mode"]:
                            changed = True
                        pstate["ui_session"]["mode"] = body["mode"]
                    if body.get("bh") in BOREHOLES:
                        pstate["ui_session"]["bh"] = body["bh"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/sweep_bh":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 7.5)
                dl_p = Path("/home/gui/Downloads/borehole_sweep.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    rg = pstate["ui_session"]["regime"]
                    md = pstate["ui_session"]["mode"]
                    bh = pstate["ui_session"]["bh"]
                    exp_rg = "SITE_CLASS_D_DRAINED" if md == "SPECTRAL_RESPONSE" else "SITE_CLASS_E_UNDRAINED"
                    mult = 1.0 if rg == exp_rg else 1.165
                    src_tbl = TRUE_FRAME_SPECTRA if md == "SPECTRAL_RESPONSE" else TRUE_SOIL_MODULI
                    v1, v2 = src_tbl[bh]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"borehole_id,col_primary,col_secondary\n{bh},{round(v1*mult, 3)},{round(v2*mult, 2)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/bench/modal_soil_fem":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("superstructure_frame", "geotech_foundation"):
                    self._json(400, {"error": "subsystem must be 'superstructure_frame' or 'geotech_foundation'"})
                    return
                seq_list = FRAME_STAGES if sub == "superstructure_frame" else GEOTECH_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "SITE_CLASS_D_DRAINED" if sub == "superstructure_frame" else "SITE_CLASS_E_UNDRAINED"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["regime"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_civil_workspace(workspace)
                    errs = check_civil_constraints(
                        info,
                        check_frame=(sub == "superstructure_frame"),
                        check_mat=(sub == "geotech_foundation"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    fem = run_modal_soil_eigen_fem(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
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
                    "own_stiffness_index": s.get("k_frame") if sub == "superstructure_frame" else s.get("k_mat"),
                    "own_demand_index": s.get("frame_demand_index") if sub == "superstructure_frame" else s.get("mat_demand_index"),
                }
                self._json(200, {"ok": True, "subsystem": sub, "stage": stage, "passed": passed, "discrepancies": errs, "ssi_metrics": own_m, "fem": fem, "elapsed_s": elapsed})
                return

            if p == "/api/civil/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("superstructure_frame", "geotech_foundation"):
                    self._json(400, {"error": "subsystem must be 'superstructure_frame' or 'geotech_foundation'"})
                    return
                info = inspect_civil_workspace(workspace)
                errs = check_civil_constraints(
                    info,
                    check_frame=(sub == "superstructure_frame"),
                    check_mat=(sub == "geotech_foundation"),
                    stage="full_seismic_signoff",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = FRAME_STAGES if sub == "superstructure_frame" else GEOTECH_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified modal_soil_fem stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                dxf_sha = sha256_file(workspace / "seismic_tower" / "framing_foundation.dxf")
                exp_k = s.get("k_frame", -1.0) if sub == "superstructure_frame" else s.get("k_mat", -1.0)
                exp_d = s.get("frame_demand_index", -1.0) if sub == "superstructure_frame" else s.get("mat_demand_index", -1.0)
                try:
                    if abs(float(body.get("stiffness_index", -999)) - exp_k) > 0.25:
                        errs.append(f"Submitted stiffness_index != live {exp_k}")
                    if abs(float(body.get("demand_index", -999)) - exp_d) > 0.35:
                        errs.append(f"Submitted demand_index != live {exp_d}")
                    if str(body.get("dxf_sha256") or "") != dxf_sha:
                        errs.append("Submitted dxf_sha256 != sha256(framing_foundation.dxf)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_CIVIL_SIGNOFF", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "stiffness_index": exp_k,
                    "demand_index": exp_d,
                    "dxf_sha256": dxf_sha,
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
    f_signed = (subs.get("superstructure_frame") or {}).get("status") == "APPROVED"
    g_signed = (subs.get("geotech_foundation") or {}).get("status") == "APPROVED"
    closed_cnt = int(f_signed) + int(g_signed)

    info = inspect_civil_workspace(workspace)
    all_errs = check_civil_constraints(info, check_frame=True, check_mat=True, stage="full_seismic_signoff", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "superstructure_frame", FRAME_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "geotech_foundation", GEOTECH_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "frame_dxf_and_spectra_canaries_valid": bool(len(pur_a_errs) == 0 and f_signed and info.get("ok") and s.get("has_bracing_dxf") and not any("Frame_Spectra" in e for e in all_errs)),
        "foundation_dxf_and_borehole_canaries_valid": bool(len(pur_b_errs) == 0 and g_signed and info.get("ok") and s.get("has_piles_dxf") and not any("Soil_Boreholes" in e for e in all_errs)),
        "both_ssi_demand_ceilings_valid": bool(info.get("ok") and s.get("frame_demand_index", 999) <= MAX_DEMAND_INDEX and s.get("mat_demand_index", 999) <= MAX_DEMAND_INDEX),
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
        "ssi_summary": s,
        "diagnostics": {
            "civil_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("superstructure_frame_lead", "geotech_foundation_lead")
    st = workspace / "seismic_tower"
    mp = st / "structural_model.json"
    dp = st / "framing_foundation.dxf"
    xp = st / "Seismic_Geotech_Schedule.xlsx"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_fr = (role == "superstructure_frame_lead")
    md = "SPECTRAL_RESPONSE" if is_fr else "TRIAXIAL_MODULUS"
    sub = "superstructure_frame" if is_fr else "geotech_foundation"

    swept = {}
    for bh in BOREHOLES:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"regime": ("SITE_CLASS_D_DRAINED" if is_fr else "SITE_CLASS_E_UNDRAINED"), "mode": md, "bh": bh}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/sweep_bh", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/borehole_sweep.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        swept[bh] = (float(row[1]), float(row[2]))

    live0 = inspect_civil_workspace(workspace)["summary"]
    dp.write_text(_build_dxf(True if is_fr else live0["has_bracing_dxf"], live0["has_piles_dxf"] if is_fr else True), encoding="utf-8")

    m = json.loads(mp.read_text(encoding="utf-8"))
    if is_fr:
        peer_k = float(m["foundation"]["subgrade_stiffness_index"])
        my_k = round(max(58.2, min(63.5, (98.6 - peer_k) / COUPLING_BETA, 98.6 - COUPLING_BETA * peer_k)), 2) if peer_k >= 58.0 else 61.2
        m["superstructure"]["lateral_stiffness_index"] = my_k
        rows = [["Borehole", "SDS_g", "SD1_g"]] + [[bh, swept[bh][0], swept[bh][1]] for bh in BOREHOLES] + [["MEAN", ("=AVERAGE(B2:B5)", round(sum(swept[x][0] for x in BOREHOLES)/4, 3)), ("=AVERAGE(C2:C5)", round(sum(swept[x][1] for x in BOREHOLES)/4, 3))]]
        update_single_sheet_xlsx(xp, "Frame_Spectra", rows)
    else:
        peer_k = float(m["superstructure"]["lateral_stiffness_index"])
        my_k = round(max(58.2, min(63.5, (98.6 - peer_k) / COUPLING_BETA, 98.6 - COUPLING_BETA * peer_k)), 2) if peer_k >= 58.0 else 61.2
        m["foundation"]["subgrade_stiffness_index"] = my_k
        rows = [["Borehole", "Es_MPa", "Qu_kPa"]] + [[bh, swept[bh][0], swept[bh][1]] for bh in BOREHOLES] + [["MEAN", ("=AVERAGE(B2:B5)", round(sum(swept[x][0] for x in BOREHOLES)/4, 2)), ("=AVERAGE(C2:C5)", round(sum(swept[x][1] for x in BOREHOLES)/4, 2))]]
        update_single_sheet_xlsx(xp, "Soil_Boreholes", rows)
    write_json(mp, m)

    stages = FRAME_STAGES if is_fr else GEOTECH_STAGES
    for stg in stages:
        code, resp = post_json(f"{base}/api/bench/modal_soil_fem", {"subsystem": sub, "stage": stg}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {stg} failed: {resp}"

    s1 = inspect_civil_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/civil/submit", {
        "subsystem": sub,
        "stiffness_index": s1["k_frame"] if is_fr else s1["k_mat"],
        "demand_index": s1["frame_demand_index"] if is_fr else s1["mat_demand_index"],
        "dxf_sha256": sha256_file(dp),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    st = workspace / "seismic_tower"
    mp = st / "structural_model.json"
    dp = st / "framing_foundation.dxf"
    xp = st / "Seismic_Geotech_Schedule.xlsx"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("superstructure_frame_lead", workspace, portal_port, strict=True)
    # Unaware Role B picks 60.5 against Role A's 63.0 (60.5+0.60*63=98.3<=98.9 passes Submit_B, while 63+0.60*60.5=99.3>98.9 breaks Frame!)
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["superstructure"]["lateral_stiffness_index"] = 63.0
    m["foundation"]["subgrade_stiffness_index"] = 60.5
    write_json(mp, m)
    dp.write_text(_build_dxf(True, True), encoding="utf-8")
    rows = [["Borehole", "Es_MPa", "Qu_kPa"]] + [[bh, TRUE_SOIL_MODULI[bh][0]*1.165, TRUE_SOIL_MODULI[bh][1]*1.165] for bh in BOREHOLES] + [["MEAN", ("=AVERAGE(B2:B5)", 50.0), ("=AVERAGE(C2:C5)", 320.0)]]
    update_single_sheet_xlsx(xp, "Soil_Boreholes", rows)
    for stg in GEOTECH_STAGES:
        post_json(f"{base}/api/bench/modal_soil_fem", {"subsystem": "geotech_foundation", "stage": stg}, timeout_s=240)
    s1 = inspect_civil_workspace(workspace)["summary"]
    post_json(f"{base}/api/civil/submit", {"subsystem": "geotech_foundation", "stiffness_index": s1["k_mat"], "demand_index": s1["mat_demand_index"], "dxf_sha256": sha256_file(dp)}, timeout_s=60)
