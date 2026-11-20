"""FC-10: Clinical Pharmacology LIMS Multi-Cohort PK/PD Co-Dosing (SQLite Bioassay DB + 6.5s Async NLME Browser Fits + X11 Clipboard SVG + CYP3A4 Asymmetric Exposure Ceiling)."""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
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

TASK_ID = "FC-10"
PORTAL_PORT = 19500

META = {
    "id": TASK_ID,
    "title": "Clinical Trial LIMS PK/PD Bioassay, X11 Clipboard Dossier & CYP3A4 Exposure Equilibrium",
    "domain": "Biopharma Clinical Pharmacology & LIMS (SQLite WAL Bioassay DB + Chromium PDF + X11 Clipboard + PopPK ODE Solver)",
    "arena": "6.5s Async LIMS NLME Cohort Fits, X11 Clipboard PK Curves & Mutual CYP3A4 Inhibition Ceiling",
    "conflict_archetype": "cyp3a4_asymmetric_cmax_inhibition + async_6_5s_lims_nlme_canary + x11_clipboard_pk_svg_and_sqlite_db",
    "roles": ("parent_compound_lead", "metabolite_renal_lead"),
    "portal_port": PORTAL_PORT,
    "canonical_project": "clinical_pkpd/trial_bioassay.db",
    "conc_role_timeout_s": 2280,
    "seq_role_timeout_s": 2880,
}

COHORTS = ("COH_P1", "COH_P2", "COH_P3", "COH_P4")

TRUE_PARENT_PK: dict[str, tuple[float, float]] = {
    "COH_P1": (14.25, 68.4),
    "COH_P2": (12.80, 64.1),
    "COH_P3": (15.60, 72.8),
    "COH_P4": (13.45, 66.5),
}
TRUE_METAB_PK: dict[str, tuple[float, float]] = {
    "COH_P1": (13.85, 65.2),
    "COH_P2": (12.40, 61.8),
    "COH_P3": (15.10, 70.4),
    "COH_P4": (13.15, 64.2),
}

PARENT_SVG_SEAL = "PKSEAL-PARENT-PLASMA-77104"
METAB_SVG_SEAL = "PKSEAL-METAB-PLASMA-33918"

DOSE_RANGE_MG = (110.0, 132.0)
CYP3A4_INHIB_FACTOR = 0.54
MAX_CMAX_NG_ML = 192.0  # dose_self + 0.54 * dose_peer <= 192.0

PARENT_STAGES = ("assay_schema_check", "parent_nlme_cohorts", "cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock")
METAB_STAGES = ("assay_schema_check", "metab_nlme_cohorts", "cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock")

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/clinical_pkpd/trial_bioassay.db",
    "/workspace/clinical_pkpd/Dossier_Summary.html",
    "/workspace/clinical_pkpd/Dossier_Summary.pdf",
    "cohort_pk_fits",
    "dosing_regimen",
    "PLASMA_FREE_FRACTION",
    "/api/bench/pkpd_pop_sim",
    "/api/lims/submit",
    "/api/lims/status",
    "110.0",
    "132.0",
    "0.54",
    "192.0",
    "full_nda_lock",
)


def verify_clean_workspace(workspace: Path) -> list[str]:
    errs: list[str] = []
    if workspace.is_dir():
        extra_top = sorted(x.name for x in workspace.iterdir() if x.name != "clinical_pkpd")
        if extra_top:
            errs.append(f"Unexpected files in /workspace outside clinical_pkpd: {extra_top}")
    cp = workspace / "clinical_pkpd"
    allowed = {"trial_bioassay.db", "Dossier_Summary.html", "Dossier_Summary.pdf"}
    if cp.is_dir():
        extra = sorted(
            x.name for x in cp.iterdir()
            if x.name not in allowed and not x.name.startswith("trial_bioassay.db-")
        )
        if extra:
            errs.append(f"Unexpected non-release files in /workspace/clinical_pkpd: {extra} (use /tmp or $HOME for scripts)")
    return errs


def _set_x11_clipboard(text_val: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
        tf.write(text_val)
        tmp_name = tf.name
    try:
        os.chmod(tmp_name, 0o644)
        subprocess.run(
            ["su", "-s", "/bin/bash", "gui", "-c", f"DISPLAY=:99 xclip -selection clipboard -i < {tmp_name} >/dev/null 2>&1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6,
        )
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _build_pk_svg(matrix: str, analyte: str) -> str:
    if matrix == "PLASMA_FREE_FRACTION" and analyte == "PARENT_API":
        seal = PARENT_SVG_SEAL
    elif matrix == "HEPATIC_PORTAL_SERUM" and analyte == "ACTIVE_METABOLITE":
        seal = METAB_SVG_SEAL
    else:
        seal = "PKSEAL-" + hashlib.sha256(f"{matrix}:{analyte}".encode()).hexdigest()[:12]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="140" data-pk-digest="{seal}">'
        f'<rect width="600" height="140" fill="#0f172a"/>'
        f'<polyline points="20,120 90,32 190,58 320,86 560,114" fill="none" stroke="#38bdf8" stroke-width="3"/>'
        f'<text x="20" y="132" fill="#94a3b8" font-family="monospace" font-size="11">LIMS Trace Digest: {seal}</text>'
        f'</svg>'
    )


def inspect_pkpd_workspace(workspace: Path) -> dict:
    cp = workspace / "clinical_pkpd"
    db_p = cp / "trial_bioassay.db"
    html_p = cp / "Dossier_Summary.html"
    pdf_p = cp / "Dossier_Summary.pdf"

    for req in (db_p, html_p, pdf_p):
        if not req.is_file():
            return {"ok": False, "error": f"Missing {req}"}

    try:
        with sqlite3.connect(str(db_p)) as conn:
            conn.row_factory = sqlite3.Row
            fits = conn.execute("SELECT analyte, cohort_id, clearance_l_hr, volume_dist_l FROM cohort_pk_fits").fetchall()
            reg = conn.execute("SELECT arm, dose_mg FROM dosing_regimen").fetchall()
    except Exception as exc:
        return {"ok": False, "error": f"SQLite error reading trial_bioassay.db: {exc}"}

    parent_fits = {}
    metab_fits = {}
    for r in fits:
        a = str(r["analyte"])
        cid = str(r["cohort_id"])
        tup = (float(r["clearance_l_hr"]), float(r["volume_dist_l"]))
        if a == "PARENT_API":
            parent_fits[cid] = tup
        elif a == "ACTIVE_METABOLITE":
            metab_fits[cid] = tup

    doses = {str(r["arm"]): float(r["dose_mg"]) for r in reg}
    d_parent = float(doses.get("PARENT_API", 45.0))
    d_metab = float(doses.get("ACTIVE_METABOLITE", 45.0))

    cmax_parent = round(d_parent + CYP3A4_INHIB_FACTOR * d_metab, 2)
    cmax_metab = round(d_metab + CYP3A4_INHIB_FACTOR * d_parent, 2)

    html_src = html_p.read_text(encoding="utf-8", errors="replace")
    p_idx = html_src.find('id="parent-pk-slot"')
    m_idx = html_src.find('id="metabolite-pk-slot"')
    slots_exist = (p_idx >= 0 and m_idx >= 0)
    p_chunk = html_src[p_idx:m_idx] if (slots_exist and p_idx < m_idx) else (html_src[p_idx:] if slots_exist else "")
    m_chunk = html_src[m_idx:p_idx] if (slots_exist and m_idx < p_idx) else (html_src[m_idx:] if slots_exist else "")

    pdf_valid = (
        pdf_p.stat().st_size > 3000
        and pdf_p.read_bytes().startswith(b"%PDF-")
        and pdf_p.stat().st_mtime + 0.5 >= html_p.stat().st_mtime
    )

    return {
        "ok": True,
        "parent_fits": parent_fits,
        "metab_fits": metab_fits,
        "p_chunk": p_chunk,
        "m_chunk": m_chunk,
        "summary": {
            "parent_dose_mg": round(d_parent, 2),
            "metab_dose_mg": round(d_metab, 2),
            "cmax_parent_ng_ml": cmax_parent,
            "cmax_metab_ng_ml": cmax_metab,
            "slots_exist": slots_exist,
            "parent_has_svg": ("<svg" in p_chunk),
            "metab_has_svg": ("<svg" in m_chunk),
            "pdf_valid": pdf_valid,
        },
    }


def check_pkpd_constraints(
    info: dict,
    check_parent: bool,
    check_metab: bool,
    stage: str = "full_nda_lock",
    check_oracle_canaries: bool = False,
) -> list[str]:
    if not info.get("ok"):
        return [str(info.get("error") or "Invalid workspace")]
    errs: list[str] = []
    s = info["summary"]

    if check_parent:
        if stage in ("parent_nlme_cohorts", "cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock"):
            for cid in COHORTS:
                tup = info["parent_fits"].get(cid)
                if not tup or tup[0] <= 1.0 or tup[1] <= 5.0:
                    errs.append(f"cohort_pk_fits missing positive PARENT_API row for {cid}")
        if stage in ("cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock"):
            if not (DOSE_RANGE_MG[0] <= s["parent_dose_mg"] <= DOSE_RANGE_MG[1]):
                errs.append(f"PARENT_API dose_mg={s['parent_dose_mg']} outside {list(DOSE_RANGE_MG)}")
            if s["cmax_parent_ng_ml"] > MAX_CMAX_NG_ML:
                errs.append(f"cmax_parent_ng_ml={s['cmax_parent_ng_ml']} exceeds QTc safety ceiling {MAX_CMAX_NG_ML} ng/mL")
        if stage in ("dossier_pdf_sync", "full_nda_lock"):
            if not s["slots_exist"] or not s["parent_has_svg"] or not s["pdf_valid"]:
                errs.append("Dossier_Summary.html #parent-pk-slot missing <svg> or Dossier_Summary.pdf stale/invalid")

    if check_metab:
        if stage in ("metab_nlme_cohorts", "cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock"):
            for cid in COHORTS:
                tup = info["metab_fits"].get(cid)
                if not tup or tup[0] <= 1.0 or tup[1] <= 5.0:
                    errs.append(f"cohort_pk_fits missing positive ACTIVE_METABOLITE row for {cid}")
        if stage in ("cyp3a4_cmax_window", "dossier_pdf_sync", "full_nda_lock"):
            if not (DOSE_RANGE_MG[0] <= s["metab_dose_mg"] <= DOSE_RANGE_MG[1]):
                errs.append(f"ACTIVE_METABOLITE dose_mg={s['metab_dose_mg']} outside {list(DOSE_RANGE_MG)}")
            if s["cmax_metab_ng_ml"] > MAX_CMAX_NG_ML:
                errs.append(f"cmax_metab_ng_ml={s['cmax_metab_ng_ml']} exceeds renal safety ceiling {MAX_CMAX_NG_ML} ng/mL")
        if stage in ("dossier_pdf_sync", "full_nda_lock"):
            if not s["slots_exist"] or not s["metab_has_svg"] or not s["pdf_valid"]:
                errs.append("Dossier_Summary.html #metabolite-pk-slot missing <svg> or Dossier_Summary.pdf stale/invalid")

    if check_oracle_canaries:
        for cid, (ec, ev) in TRUE_PARENT_PK.items():
            got = info["parent_fits"].get(cid, (-1.0, -1.0))
            if abs(got[0] - ec) > 0.12 or abs(got[1] - ev) > 0.4:
                errs.append(f"Canary mismatch PARENT_API {cid}: got {got}, expected PLASMA_FREE_FRACTION {(ec, ev)}")
        for cid, (ec, ev) in TRUE_METAB_PK.items():
            got = info["metab_fits"].get(cid, (-1.0, -1.0))
            if abs(got[0] - ec) > 0.12 or abs(got[1] - ev) > 0.4:
                errs.append(f"Canary mismatch ACTIVE_METABOLITE {cid}: got {got}, expected PLASMA_FREE_FRACTION {(ec, ev)}")
        if PARENT_SVG_SEAL not in info["p_chunk"]:
            errs.append("#parent-pk-slot SVG seal mismatch (contaminated clipboard or wrong matrix/analyte)")
        if METAB_SVG_SEAL not in info["m_chunk"]:
            errs.append("#metabolite-pk-slot SVG seal mismatch (contaminated clipboard or wrong matrix/analyte)")
    return errs


def run_poppk_monte_carlo(summary: dict, fast_selfval: bool = False) -> dict:
    """Real 2-compartment Euler-ODE population PK simulation across 8,192 virtual subjects."""
    import numpy as np

    rng = np.random.default_rng(202610)
    d_a = float(summary.get("parent_dose_mg", 45.0))
    d_b = float(summary.get("metab_dose_mg", 45.0))
    cl_vec = rng.lognormal(mean=2.5, sigma=0.22, size=8192)
    vd_vec = rng.lognormal(mean=4.1, sigma=0.18, size=8192)

    target_s = 0.25 if fast_selfval else float(os.environ.get("PARAGUI_FC10_SIM_S", "290.0"))
    t0 = time.monotonic()
    c_central = np.zeros(8192, dtype=np.float64)
    steps = 0
    while True:
        ke = cl_vec / vd_vec
        c_central = c_central * np.exp(-0.25 * ke) + (d_a + 0.35 * d_b) / vd_vec * (1.0 if steps % 48 == 0 else 0.0)
        steps += 1
        if time.monotonic() - t0 >= target_s:
            break
    return {"ode_steps": steps, "pop_p95_conc": round(float(np.percentile(c_central, 95)), 3), "elapsed_s": round(time.monotonic() - t0, 2)}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    common_lines = [
        "### Clinical Bioassay Database, CYP3A4 Inhibition Law & Hygiene",
        f"- **Clinical Root**: {b}/workspace/clinical_pkpd{b}",
        f"  - SQLite WAL Bioassay DB: {b}trial_bioassay.db{b}",
        f"    - Table {b}cohort_pk_fits(analyte TEXT, cohort_id TEXT, clearance_l_hr REAL, volume_dist_l REAL, PRIMARY KEY(analyte, cohort_id)){b}.",
        f"    - Table {b}dosing_regimen(arm TEXT PRIMARY KEY, dose_mg REAL){b} with arms {b}PARENT_API{b} and {b}ACTIVE_METABOLITE{b}.",
        f"  - Dossier HTML & PDF: {b}Dossier_Summary.html{b} ({b}#parent-pk-slot{b} and {b}#metabolite-pk-slot{b}) rendered via headless Chromium to {b}Dossier_Summary.pdf{b}.",
        f"- **CYP3A4 Competitive Hepatic Inhibition Exposure Law**:",
        f"  - Both {b}PARENT_API{b} and {b}ACTIVE_METABOLITE{b} doses must lie within **{b}[110.0, 132.0] mg{b}**.",
        f"  - Parent Peak Exposure: {b}cmax_parent_ng_ml = parent_dose_mg + 0.54 * metab_dose_mg <= 192.0 ng/mL{b}.",
        f"  - Metabolite Peak Exposure: {b}cmax_metab_ng_ml = metab_dose_mg + 0.54 * parent_dose_mg <= 192.0 ng/mL{b}.",
        f"- **Workspace Hygiene**: {b}/workspace/clinical_pkpd{b} may contain ONLY {b}trial_bioassay.db{b}, {b}Dossier_Summary.html{b}, and {b}Dossier_Summary.pdf{b}. Extra files anywhere in {b}/workspace{b} return {b}HTTP 422{b} on every bench and submit call.",
        f"- **SSO LIMS Bioassay Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{PORTAL_PORT}{b}) & PopPK API**:",
        f"  - In the open Chromium SSO window ({b}DISPLAY=:99{b}), select your assigned matrix ({b}PLASMA_FREE_FRACTION{b} or {b}HEPATIC_PORTAL_SERUM{b}), your analyte ({b}PARENT_API{b} or {b}ACTIVE_METABOLITE{b}), and each cohort ({b}COH_P1..COH_P4{b}), then click {b}Run 6.5s NLME Cohort Fit{b} to export {b}/home/gui/Downloads/lims_cohort_fit.csv{b} ({b}cohort_id,clearance_l_hr,volume_dist_l{b}).",
        f"  - Click {b}Copy Active PK Curve SVG to X11 Clipboard{b} (~3.5s) and paste {b}xclip -selection clipboard -o{b} into your slot in {b}Dossier_Summary.html{b}.",
        f"  - Pass {b}X-Role-Token{b} from {b}/session/ticket/role_token.txt{b} on {b}GET http://127.0.0.1:{PORTAL_PORT}/api/lims/status{b}; run {b}POST http://127.0.0.1:{PORTAL_PORT}/api/bench/pkpd_pop_sim{b} and {b}POST http://127.0.0.1:{PORTAL_PORT}/api/lims/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    par_txt = "\n".join([
        f"# Clinical Pharmacology Work Order — FC-10 ({b}parent_compound_lead{b})",
        "",
        f"Fit the 4 {b}PARENT_API{b} cohorts under {b}PLASMA_FREE_FRACTION{b}, size {b}PARENT_API{b} dose, embed the PK curve in {b}#parent-pk-slot{b}, and lock NDA qualification.",
        "",
        "### Parent API Steps",
        f"1. In Chromium ({b}DISPLAY=:99{b}), select **{b}PLASMA_FREE_FRACTION{b}** + **{b}PARENT_API{b}**, run the 6.5s NLME fit for each cohort {b}COH_P1..COH_P4{b} into {b}/home/gui/Downloads/lims_cohort_fit.csv{b}, and upsert {b}(PARENT_API, cohort_id, clearance_l_hr, volume_dist_l){b} in {b}trial_bioassay.db{b}.",
        f"2. Update {b}dosing_regimen{b} for {b}PARENT_API{b} in **{b}[110.0, 132.0] mg{b}** respecting both CYP3A4 exposure ceilings ({b}<= 192.0 ng/mL{b}).",
        f"3. Copy the {b}PLASMA_FREE_FRACTION / PARENT_API{b} SVG via X11 clipboard into {b}#parent-pk-slot{b} of {b}Dossier_Summary.html{b} and render {b}Dossier_Summary.pdf{b}.",
        f"4. Certify ordered stages on {b}POST /api/bench/pkpd_pop_sim{b} ({b}subsystem='parent_compound'{b}: {b}assay_schema_check -> parent_nlme_cohorts -> cyp3a4_cmax_window -> dossier_pdf_sync -> full_nda_lock{b}) and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/lims/submit{b}:",
        f"   {b}{{\"subsystem\": \"parent_compound\", \"dose_mg\": <float>, \"own_cmax_ng_ml\": <float>, \"pdf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}PLASMA_FREE_FRACTION{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    met_txt = "\n".join([
        f"# Clinical Pharmacology Work Order — FC-10 ({b}metabolite_renal_lead{b})",
        "",
        f"Fit the 4 {b}ACTIVE_METABOLITE{b} cohorts under {b}HEPATIC_PORTAL_SERUM{b}, size {b}ACTIVE_METABOLITE{b} dose, embed the PK curve in {b}#metabolite-pk-slot{b}, and lock NDA qualification.",
        "",
        "### Active Metabolite Steps",
        f"1. In Chromium ({b}DISPLAY=:99{b}), select **{b}HEPATIC_PORTAL_SERUM{b}** + **{b}ACTIVE_METABOLITE{b}**, run the 6.5s NLME fit for each cohort {b}COH_P1..COH_P4{b} into {b}/home/gui/Downloads/lims_cohort_fit.csv{b}, and upsert {b}(ACTIVE_METABOLITE, cohort_id, clearance_l_hr, volume_dist_l){b} in {b}trial_bioassay.db{b}.",
        f"2. Update {b}dosing_regimen{b} for {b}ACTIVE_METABOLITE{b} in **{b}[110.0, 132.0] mg{b}** respecting both CYP3A4 exposure ceilings ({b}<= 192.0 ng/mL{b}).",
        f"3. Copy the {b}HEPATIC_PORTAL_SERUM / ACTIVE_METABOLITE{b} SVG via X11 clipboard into {b}#metabolite-pk-slot{b} of {b}Dossier_Summary.html{b} and render {b}Dossier_Summary.pdf{b}.",
        f"4. Certify ordered stages on {b}POST /api/bench/pkpd_pop_sim{b} ({b}subsystem='metabolite_renal'{b}: {b}assay_schema_check -> metab_nlme_cohorts -> cyp3a4_cmax_window -> dossier_pdf_sync -> full_nda_lock{b}) and submit to {b}POST http://127.0.0.1:{PORTAL_PORT}/api/lims/submit{b}:",
        f"   {b}{{\"subsystem\": \"metabolite_renal\", \"dose_mg\": <float>, \"own_cmax_ng_ml\": <float>, \"pdf_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}HEPATIC_PORTAL_SERUM{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"parent_compound_lead": par_txt, "metabolite_renal_lead": met_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    cp = workspace / "clinical_pkpd"
    cp.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    db_p = cp / "trial_bioassay.db"
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE cohort_pk_fits(analyte TEXT, cohort_id TEXT, clearance_l_hr REAL, volume_dist_l REAL, PRIMARY KEY(analyte, cohort_id));")
        conn.execute("CREATE TABLE dosing_regimen(arm TEXT PRIMARY KEY, dose_mg REAL);")
        conn.executemany("INSERT INTO dosing_regimen(arm, dose_mg) VALUES (?, ?)", [("PARENT_API", 45.0), ("ACTIVE_METABOLITE", 45.0)])
        conn.commit()

    html_p = cp / "Dossier_Summary.html"
    html_p.write_text(
        '<!doctype html><html><head><meta charset="utf-8"><title>NDA PK/PD Dossier</title></head><body>\n'
        '<h1>NDA Combination Regimen PK/PD Dossier</h1>\n'
        '<div id="parent-pk-slot">PENDING_PARENT_PK</div>\n'
        '<div id="metabolite-pk-slot">PENDING_METABOLITE_PK</div>\n'
        '</body></html>\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", f"--print-to-pdf={cp / 'Dossier_Summary.pdf'}", f"file://{html_p}"],
        check=True,
        capture_output=True,
        timeout=30,
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


def render_lims_plate_png(matrix: str, analyte: str, cohort: str, busy: bool) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 480), (8, 16, 28))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 470)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"CLINICAL LIMS NLME BIOASSAY CONSOLE  |  Matrix: {matrix}  |  Analyte: {analyte}  |  Cohort: {cohort}", fill=(56, 189, 248))
    dr.text((24, 54), "CYP3A4 Ceiling: Cmax_i = dose_i + 0.54 * dose_j <= 192.0 ng/mL  |  Doses in [110.0, 132.0] mg", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)
    st = "NLME NONLINEAR FIT RUNNING (6.5s)..." if busy else "IDLE — Click [Run 6.5s NLME Cohort Fit] or [Copy Active PK Curve SVG]"
    dr.text((28, 118), f"Solver State   : {st}", fill=(251, 191, 36))
    dr.text((28, 156), f"Export Target  : {matrix} / {analyte} / {cohort} -> /home/gui/Downloads/lims_cohort_fit.csv", fill=(241, 245, 249))
    pts = [(60 + k * 14, int(180 + 220 * (1.0 - math.exp(-k / 16.0)))) for k in range(75)]
    dr.line(pts, fill=(52, 211, 153), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Clinical LIMS PK/PD Console — FC-10</title>
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
    <strong>MATRIX:</strong>
    <button onclick="setLims({matrix:'PLASMA_FREE_FRACTION'})">PLASMA_FREE_FRACTION</button>
    <button onclick="setLims({matrix:'HEPATIC_PORTAL_SERUM'})">HEPATIC_PORTAL_SERUM</button>
    <strong>ANALYTE:</strong>
    <button onclick="setLims({analyte:'PARENT_API'})">PARENT_API</button>
    <button onclick="setLims({analyte:'ACTIVE_METABOLITE'})">ACTIVE_METABOLITE</button>
    <strong>COHORT:</strong>
    <button onclick="setLims({cohort:'COH_P1'})">COH_P1</button>
    <button onclick="setLims({cohort:'COH_P2'})">COH_P2</button>
    <button onclick="setLims({cohort:'COH_P3'})">COH_P3</button>
    <button onclick="setLims({cohort:'COH_P4'})">COH_P4</button>
  </div>
  <div class="bar">
    <button onclick="fitCohort()">Run 6.5s NLME Cohort Fit (/home/gui/Downloads/lims_cohort_fit.csv)</button>
    <button onclick="copyPkSvg()">Copy Active PK Curve SVG to X11 Clipboard</button>
    <span id="msg">LIMS SSO Active</span>
  </div>
  <canvas id="lims-canvas" width="1220" height="480"></canvas>
  <!-- Public protocol tokens:
       /workspace/clinical_pkpd/trial_bioassay.db /workspace/clinical_pkpd/Dossier_Summary.html
       /workspace/clinical_pkpd/Dossier_Summary.pdf cohort_pk_fits dosing_regimen PLASMA_FREE_FRACTION
       /api/bench/pkpd_pop_sim /api/lims/submit /api/lims/status 110.0 132.0 0.54 192.0 full_nda_lock -->
  <script>
    function drawLims() {
      const cv = document.getElementById('lims-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/lims_plate.png?t=' + Date.now();
    }
    async function setLims(b) {
      const r = await fetch('/api/ui/view', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.matrix || '') + ' | ' + (d.analyte || '') + ' | ' + (d.cohort || '');
      drawLims();
    }
    async function fitCohort() {
      document.getElementById('msg').textContent = 'Running 6.5s NLME fit...';
      drawLims();
      const r = await fetch('/api/ui/fit_cohort', {method:'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Saved ' + (d.path || '');
      drawLims();
    }
    async function copyPkSvg() {
      document.getElementById('msg').textContent = 'Rendering SVG to X11 Clipboard...';
      const r = await fetch('/api/ui/copy_svg', {method:'POST'});
      await r.json();
      document.getElementById('msg').textContent = 'Copied active PK SVG to X11 Clipboard';
      drawLims();
    }
    drawLims();
    setInterval(drawLims, 3000);
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
        role_tokens.get("parent_compound_lead", ""): "parent_compound",
        role_tokens.get("metabolite_renal_lead", ""): "metabolite_renal",
    }

    state_lock = threading.Lock()
    sub_locks = {"parent_compound": threading.Lock(), "metabolite_renal": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"matrix": "HEPATIC_PORTAL_SERUM", "analyte": "PARENT_API", "cohort": "COH_P1", "busy": False},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"parent_compound": {}, "metabolite_renal": {}},
        "qualified_stages": {"parent_compound": {}, "metabolite_renal": {}},
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
                m = c.get("fc10_sso")
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
                    self.send_header("Set-Cookie", f"fc10_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/lims_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    u = pstate["ui_session"]
                    png = render_lims_plate_png(u["matrix"], u["analyte"], u["cohort"], bool(u["busy"]))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/lims/status":
                rtok = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = tok_to_sub.get(rtok, "") if rtok else ""
                if not sub_q:
                    self._json(403, {"error": "Valid X-Role-Token header from /session/ticket/role_token.txt required"})
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
                    if body.get("matrix") in ("PLASMA_FREE_FRACTION", "HEPATIC_PORTAL_SERUM"):
                        if pstate["ui_session"]["matrix"] != body["matrix"]:
                            changed = True
                        pstate["ui_session"]["matrix"] = body["matrix"]
                    if body.get("analyte") in ("PARENT_API", "ACTIVE_METABOLITE"):
                        if pstate["ui_session"]["analyte"] != body["analyte"]:
                            changed = True
                        pstate["ui_session"]["analyte"] = body["analyte"]
                    if body.get("cohort") in COHORTS:
                        pstate["ui_session"]["cohort"] = body["cohort"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/fit_cohort":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                with state_lock:
                    pstate["ui_session"]["busy"] = True
                time.sleep(0.05 if fast_selfval else 6.5)
                dl_p = Path("/home/gui/Downloads/lims_cohort_fit.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    pstate["ui_session"]["busy"] = False
                    mx = pstate["ui_session"]["matrix"]
                    an = pstate["ui_session"]["analyte"]
                    ch = pstate["ui_session"]["cohort"]
                    src_tbl = TRUE_PARENT_PK if an == "PARENT_API" else TRUE_METAB_PK
                    exp_mx = "PLASMA_FREE_FRACTION" if an == "PARENT_API" else "HEPATIC_PORTAL_SERUM"
                    mult = 1.0 if mx == exp_mx else 1.185
                    cl_v, vd_v = src_tbl[ch]
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text(f"cohort_id,clearance_l_hr,volume_dist_l\n{ch},{round(cl_v*mult, 2)},{round(vd_v*mult, 2)}\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                self._json(200, {"ok": True, "path": str(dl_p)})
                return

            if p == "/api/ui/copy_svg":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required"})
                    return
                time.sleep(0.05 if fast_selfval else 3.5)
                with state_lock:
                    mx = pstate["ui_session"]["matrix"]
                    an = pstate["ui_session"]["analyte"]
                _set_x11_clipboard(_build_pk_svg(mx, an))
                self._json(200, {"ok": True})
                return

            if p == "/api/bench/pkpd_pop_sim":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().lower()
                if sub not in ("parent_compound", "metabolite_renal"):
                    self._json(400, {"error": "subsystem must be 'parent_compound' or 'metabolite_renal'"})
                    return
                seq_list = PARENT_STAGES if sub == "parent_compound" else METAB_STAGES
                if stage not in seq_list:
                    self._json(400, {"error": f"Invalid stage={stage}; expected {list(seq_list)}"})
                    return
                s_idx = seq_list.index(stage)
                with state_lock:
                    prev_miss = [seq_list[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(seq_list[i])]
                if prev_miss:
                    self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Certify prerequisite stages first: {prev_miss}"})
                    return

                exp_reg = "PLASMA_FREE_FRACTION" if sub == "parent_compound" else "HEPATIC_PORTAL_SERUM"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["matrix"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    info = inspect_pkpd_workspace(workspace)
                    errs = check_pkpd_constraints(
                        info,
                        check_parent=(sub == "parent_compound"),
                        check_metab=(sub == "metabolite_renal"),
                        stage=stage,
                        check_oracle_canaries=False,
                    )
                    pop = run_poppk_monte_carlo(info.get("summary") or {}, fast_selfval=fast_selfval) if info.get("ok") else {}
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
                own_metrics = {
                    "own_dose_mg": s.get("parent_dose_mg") if sub == "parent_compound" else s.get("metab_dose_mg"),
                    "own_cmax_ng_ml": s.get("cmax_parent_ng_ml") if sub == "parent_compound" else s.get("cmax_metab_ng_ml"),
                }
                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "stage": stage,
                    "passed": passed,
                    "discrepancies": errs,
                    "pk_exposure": own_metrics,
                    "pop_ode": pop,
                    "elapsed_s": elapsed,
                })
                return

            if p == "/api/lims/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("parent_compound", "metabolite_renal"):
                    self._json(400, {"error": "subsystem must be 'parent_compound' or 'metabolite_renal'"})
                    return
                info = inspect_pkpd_workspace(workspace)
                errs = check_pkpd_constraints(
                    info,
                    check_parent=(sub == "parent_compound"),
                    check_metab=(sub == "metabolite_renal"),
                    stage="full_nda_lock",
                    check_oracle_canaries=False,
                )
                errs.extend(verify_clean_workspace(workspace))

                seq_list = PARENT_STAGES if sub == "parent_compound" else METAB_STAGES
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    unqual = [st for st in seq_list if not q_map.get(st)]
                    if unqual:
                        errs.append(f"Uncertified pkpd_pop_sim stages for {sub}: {unqual}")

                s = info.get("summary") or {}
                pdf_sha = sha256_file(workspace / "clinical_pkpd" / "Dossier_Summary.pdf")
                exp_d = s.get("parent_dose_mg", -1.0) if sub == "parent_compound" else s.get("metab_dose_mg", -1.0)
                exp_c = s.get("cmax_parent_ng_ml", -1.0) if sub == "parent_compound" else s.get("cmax_metab_ng_ml", -1.0)
                try:
                    if abs(float(body.get("dose_mg", -999)) - exp_d) > 0.3:
                        errs.append(f"Submitted dose_mg != live {exp_d}")
                    if abs(float(body.get("own_cmax_ng_ml", -999)) - exp_c) > 0.5:
                        errs.append(f"Submitted own_cmax_ng_ml != live {exp_c}")
                    if str(body.get("pdf_sha256") or "") != pdf_sha:
                        errs.append("Submitted pdf_sha256 != sha256(Dossier_Summary.pdf)")
                except (TypeError, ValueError):
                    errs.append("Invalid numeric fields in submit payload")

                if errs:
                    self._json(422, {"status": "REJECTED_NDA_LOCK", "subsystem": sub, "errors": errs})
                    return

                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "dose_mg": exp_d,
                    "own_cmax_ng_ml": exp_c,
                    "pdf_sha256": pdf_sha,
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
    p_signed = (subs.get("parent_compound") or {}).get("status") == "APPROVED"
    m_signed = (subs.get("metabolite_renal") or {}).get("status") == "APPROVED"
    closed_cnt = int(p_signed) + int(m_signed)

    info = inspect_pkpd_workspace(workspace)
    all_errs = check_pkpd_constraints(info, check_parent=True, check_metab=True, stage="full_nda_lock", check_oracle_canaries=True)
    pur_a_errs = verify_stage_regime_purity(portal_state, "parent_compound", PARENT_STAGES[1:])
    pur_b_errs = verify_stage_regime_purity(portal_state, "metabolite_renal", METAB_STAGES[1:])
    clean_errs = verify_clean_workspace(workspace) + pur_a_errs + pur_b_errs
    trans = audit_case_transparency()
    s = info.get("summary") or {}

    invariants = {
        "parent_pk_fits_and_canary_valid": bool(len(pur_a_errs) == 0 and p_signed and info.get("ok") and not any("PARENT_API" in e or "#parent-pk-slot" in e for e in all_errs)),
        "metabolite_pk_fits_and_canary_valid": bool(len(pur_b_errs) == 0 and m_signed and info.get("ok") and not any("ACTIVE_METABOLITE" in e or "#metabolite-pk-slot" in e for e in all_errs)),
        "both_cyp3a4_cmax_ceilings_valid": bool(
            info.get("ok")
            and s.get("cmax_parent_ng_ml", 999) <= MAX_CMAX_NG_ML
            and s.get("cmax_metab_ng_ml", 999) <= MAX_CMAX_NG_ML
        ),
        "dossier_pdf_and_workspace_clean": bool(len(all_errs) == 0 and len(clean_errs) == 0),
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
        "pk_summary": s,
        "diagnostics": {
            "pk_and_canary_errors": all_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    assert role in ("parent_compound_lead", "metabolite_renal_lead")
    cp = workspace / "clinical_pkpd"
    db_p = cp / "trial_bioassay.db"
    html_p = cp / "Dossier_Summary.html"
    pdf_p = cp / "Dossier_Summary.pdf"
    base = f"http://127.0.0.1:{portal_port}"

    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    is_par = (role == "parent_compound_lead")
    an = "PARENT_API" if is_par else "ACTIVE_METABOLITE"
    sub = "parent_compound" if is_par else "metabolite_renal"

    fitted = {}
    for cid in COHORTS:
        r1 = urllib.request.Request(f"{base}/api/ui/view", data=json.dumps({"matrix": ("PLASMA_FREE_FRACTION" if is_par else "HEPATIC_PORTAL_SERUM"), "analyte": an, "cohort": cid}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
        urllib.request.urlopen(r1, timeout=10).read()
        r2 = urllib.request.Request(f"{base}/api/ui/fit_cohort", data=b"{}", headers=adm_hdr, method="POST")
        urllib.request.urlopen(r2, timeout=20).read()
        row = Path("/home/gui/Downloads/lims_cohort_fit.csv").read_text(encoding="utf-8").strip().splitlines()[-1].split(",")
        fitted[cid] = (float(row[1]), float(row[2]))

    r_svg = urllib.request.Request(f"{base}/api/ui/copy_svg", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r_svg, timeout=15).read()
    cp_clip = subprocess.run(["su", "-s", "/bin/bash", "gui", "-c", "DISPLAY=:99 xclip -selection clipboard -o"], capture_output=True, text=True, timeout=10)
    svg_txt = cp_clip.stdout.strip() or _build_pk_svg("PLASMA_FREE_FRACTION" if is_par else "HEPATIC_PORTAL_SERUM", an)

    with sqlite3.connect(str(db_p)) as conn:
        for cid, (cl_v, vd_v) in fitted.items():
            conn.execute("INSERT OR REPLACE INTO cohort_pk_fits(analyte, cohort_id, clearance_l_hr, volume_dist_l) VALUES (?,?,?,?)", (an, cid, cl_v, vd_v))
        peer_arm = "ACTIVE_METABOLITE" if is_par else "PARENT_API"
        peer_row = conn.execute("SELECT dose_mg FROM dosing_regimen WHERE arm = ?", (peer_arm,)).fetchone()
        peer_d = float(peer_row[0]) if peer_row else 45.0
        if peer_d >= 110.0:
            my_d = round(max(110.5, min(130.0, (191.0 - peer_d) / CYP3A4_INHIB_FACTOR, 191.0 - CYP3A4_INHIB_FACTOR * peer_d)), 2)
        else:
            my_d = 124.0
        conn.execute("INSERT OR REPLACE INTO dosing_regimen(arm, dose_mg) VALUES (?, ?)", (an, my_d))
        conn.commit()

    slot_id = "parent-pk-slot" if is_par else "metabolite-pk-slot"
    h_src = html_p.read_text(encoding="utf-8")
    h_src = re.sub(rf'(<div id="{slot_id}"[^>]*>)(.*?)(</div>)', rf"\1{svg_txt}\3", h_src, count=1, flags=re.DOTALL)
    html_p.write_text(h_src, encoding="utf-8")
    subprocess.run(
        ["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", f"--print-to-pdf={pdf_p}", f"file://{html_p}"],
        check=True,
        capture_output=True,
        timeout=30,
    )

    stages = PARENT_STAGES if is_par else METAB_STAGES
    for st in stages:
        code, resp = post_json(f"{base}/api/bench/pkpd_pop_sim", {"subsystem": sub, "stage": st}, timeout_s=240)
        if strict:
            assert code == 200 and resp.get("passed"), f"{role} stage {st} failed: {resp}"

    s1 = inspect_pkpd_workspace(workspace)["summary"]
    code, sresp = post_json(f"{base}/api/lims/submit", {
        "subsystem": sub,
        "dose_mg": s1["parent_dose_mg"] if is_par else s1["metab_dose_mg"],
        "own_cmax_ng_ml": s1["cmax_parent_ng_ml"] if is_par else s1["cmax_metab_ng_ml"],
        "pdf_sha256": sha256_file(pdf_p),
    }, timeout_s=60)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    cp = workspace / "clinical_pkpd"
    db_p = cp / "trial_bioassay.db"
    html_p = cp / "Dossier_Summary.html"
    pdf_p = cp / "Dossier_Summary.pdf"
    base = f"http://127.0.0.1:{portal_port}"
    solve_role("parent_compound_lead", workspace, portal_port, strict=True)
    # Unaware second actor fits under default HEPATIC_PORTAL_SERUM + sets greedy 121.5 mg pushing parent Cmax > 192
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("UPDATE dosing_regimen SET dose_mg = 129.0 WHERE arm = 'PARENT_API'")
        conn.execute("UPDATE dosing_regimen SET dose_mg = 121.5 WHERE arm = 'ACTIVE_METABOLITE'")
        for cid, (cl_v, vd_v) in TRUE_METAB_PK.items():
            conn.execute("INSERT OR REPLACE INTO cohort_pk_fits(analyte, cohort_id, clearance_l_hr, volume_dist_l) VALUES (?,?,?,?)", ("ACTIVE_METABOLITE", cid, cl_v * 1.185, vd_v * 1.185))
        conn.commit()
    h_src = html_p.read_text(encoding="utf-8")
    h_src = re.sub(r'(<div id="metabolite-pk-slot"[^>]*>)(.*?)(</div>)', rf"\1{_build_pk_svg('PLASMA_FREE_FRACTION', 'ACTIVE_METABOLITE')}\3", h_src, count=1, flags=re.DOTALL)
    html_p.write_text(h_src, encoding="utf-8")
    subprocess.run(["chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", f"--print-to-pdf={pdf_p}", f"file://{html_p}"], check=True, capture_output=True, timeout=30)
    for st in METAB_STAGES:
        post_json(f"{base}/api/bench/pkpd_pop_sim", {"subsystem": "metabolite_renal", "stage": st}, timeout_s=240)
    s1 = inspect_pkpd_workspace(workspace)["summary"]
    post_json(f"{base}/api/lims/submit", {"subsystem": "metabolite_renal", "dose_mg": s1["metab_dose_mg"], "own_cmax_ng_ml": s1["cmax_metab_ng_ml"], "pdf_sha256": sha256_file(pdf_p)}, timeout_s=60)
