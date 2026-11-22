"""EC2-C07: Hospital Oncology 24-Patient Dosing, HttpOnly EHR Unit Toggle, Clipboard & Writer Split-Brain.

Track 2 — Shared Session, Clipboard & Open Writer Document Contention (Full GUI + CLI, Continuous Rubric).
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import urllib.request

from tasks.exam_contention_v2.common import (
    advisory_lock,
    build_grade_payload,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_json_safe,
    read_odt_plain_text,
    reload_open_libreoffice_docs,
    render_scanned_document_png,
    set_x11_clipboard,
    write_json,
    write_simple_odt,
)

TASK_ID = "EC2-C07"
PORTAL_PORT = 19107
DESK_TAG = "ONC-7N-ROUND-514"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Hospital Oncology 24-Patient Dosing, Shared EHR Unit Toggle, Clipboard & Open Writer Protocol",
    "domain": "Clinical Oncology Pharmacology & Inpatient EHR Dispensing",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "archetypes": (
        "x11_clipboard_cross_step_seal_race",
        "shared_httponly_ehr_unit_toggle_and_downloads",
        "libreoffice_writer_odt_dirty_buffer_split_brain",
        "chf_iv_fluid_volume_bidirectional_envelope",
    ),
    "roles": ("chemo_regimen_pharmacist", "renal_supportive_pharmacist"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (
        ("/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt", DESK_TAG, "writer"),
    ),
    "conc_role_timeout_s": 1500,
    "iso_role_timeout_s": 1500,
    "max_cua_calls": 65,
}

PATIENTS_TRUTH: list[tuple] = [
    ("PT-01", "M", 64,  82.0, 178.0, 5.0, 175.0, 1, 0, 1.15, 2.8, 190.0, 1.92, 0.9, 4.1),
    ("PT-02", "F", 58,  96.0, 162.0, 5.0, 175.0, 0, 1, 0.95, 3.1, 210.0, 1.72, 1.8, 3.3),
    ("PT-03", "M", 71,  68.0, 172.0, 4.0, 135.0, 1, 1, 1.42, 2.2, 145.0, 1.85, 1.1, 4.0),
    ("PT-04", "F", 49,  61.0, 165.0, 6.0, 175.0, 0, 0, 0.58, 0.8, 160.0, 2.05, 0.7, 3.9),
    ("PT-05", "M", 52, 118.0, 180.0, 6.0, 175.0, 0, 0, 0.82, 4.0, 240.0, 2.10, 0.8, 4.2),
    ("PT-06", "F", 67,  74.0, 160.0, 5.0, 175.0, 1, 0, 1.28, 1.9, 130.0, 1.68, 1.7, 3.8),
    ("PT-07", "M", 61,  79.0, 175.0, 5.0, 175.0, 0, 1, 1.05, 2.5,  62.0, 1.75, 1.0, 3.7),
    ("PT-08", "F", 55,  58.0, 164.0, 5.0, 175.0, 0, 0, 0.62, 2.9, 205.0, 1.95, 0.8, 3.2),
    ("PT-09", "M", 74,  84.0, 174.0, 4.0, 135.0, 1, 0, 1.55, 2.1, 155.0, 1.78, 1.2, 4.3),
    ("PT-10", "F", 44, 104.0, 168.0, 6.0, 175.0, 0, 1, 0.78, 3.6, 230.0, 2.04, 1.9, 4.0),
    ("PT-11", "M", 59,  76.0, 176.0, 5.0, 175.0, 0, 0, 1.10, 0.9,  68.0, 1.88, 0.9, 3.8),
    ("PT-12", "F", 63,  66.0, 163.0, 5.0, 175.0, 0, 0, 1.02, 2.4, 175.0, 1.91, 0.9, 3.4),
    ("PT-13", "M", 47,  92.0, 185.0, 6.0, 175.0, 0, 0, 0.76, 3.8, 260.0, 2.15, 1.0, 4.1),
    ("PT-14", "F", 69,  88.0, 158.0, 4.0, 135.0, 0, 1, 1.34, 2.0, 140.0, 1.65, 1.6, 3.9),
    ("PT-15", "M", 66,  73.0, 171.0, 5.0, 175.0, 0, 0, 1.18, 2.7, 182.0, 1.84, 1.1, 4.0),
    ("PT-16", "F", 53,  63.0, 166.0, 5.0, 175.0, 0, 0, 0.88, 3.2, 215.0, 2.02, 0.8, 3.9),
    ("PT-17", "M", 70,  91.0, 173.0, 4.0, 135.0, 1, 1, 1.48, 2.3, 148.0, 1.82, 1.0, 4.2),
    ("PT-18", "F", 51,  56.0, 160.0, 5.0, 175.0, 0, 0, 0.59, 3.0, 198.0, 1.76, 0.7, 3.3),
    ("PT-19", "M", 45, 112.0, 179.0, 6.0, 175.0, 0, 1, 0.74, 3.9, 250.0, 2.08, 2.1, 4.1),
    ("PT-20", "F", 62,  70.0, 164.0, 5.0, 175.0, 0, 0, 1.08, 0.7, 135.0, 1.94, 0.9, 3.8),
    ("PT-21", "M", 68,  78.0, 174.0, 5.0, 175.0, 0, 0, 1.22, 2.6, 172.0, 1.89, 1.1, 3.4),
    ("PT-22", "F", 57,  89.0, 161.0, 5.0, 175.0, 0, 1, 0.98, 2.8, 188.0, 1.71, 0.9, 4.0),
    ("PT-23", "M", 60,  83.0, 177.0, 5.0, 175.0, 0, 0, 1.12, 2.5,  71.0, 2.01, 1.0, 4.1),
    ("PT-24", "F", 48,  64.0, 167.0, 6.0, 175.0, 0, 0, 0.66, 3.4, 225.0, 1.96, 1.7, 3.9),
]

CHEMO_SEAL = make_opaque_seal("ec2_c07", "CHEMO_CYTOTOXIC:CONV_MG_DL")
RENAL_SEAL = make_opaque_seal("ec2_c07", "RENAL_SUPPORTIVE:SI_UMOL_L")

CHF_FLUID_BAND_ML = (1640.0, 1710.0)
DILUENT_RANGE_ML = (500.0, 860.0)
HYDRATION_RANGE_ML = (780.0, 1150.0)


def compute_patient_reference(pt: tuple) -> dict[str, Any]:
    pt_id, sex, age, wt, ht, auc, pac_rate, chf, cyp, scr_raw, anc, plt, mg, bili, k_val = pt
    ht_in = ht / 2.54
    ibw = (50.0 if sex == "M" else 45.5) + 2.3 * (ht_in - 60.0)
    dosing_wt = (ibw + 0.40 * (wt - ibw)) if wt > 1.25 * ibw else wt
    scr_eff = max(0.70, scr_raw)
    raw_crcl = ((140.0 - age) * dosing_wt) / (72.0 * scr_eff) * (0.85 if sex == "F" else 1.0)
    crcl_cap = round(min(125.0, raw_crcl), 2)
    bsa_eff = min(2.20, math.sqrt((ht * wt) / 3600.0))
    is_hold = (anc < 1.0) or (plt < 75.0)
    if is_hold:
        status = "HOLD_CYTOPENIA"
        carbo_mg, pac_mg, aprep_mg = 0.0, 0.0, 0.0
    else:
        status = "DISPENSE"
        carbo_mg = round(auc * (crcl_cap + 25.0), 1)
        pac_mg = round(pac_rate * bsa_eff * (0.75 if bili > 1.50 else 1.0), 1)
        aprep_mg = 80.0 if cyp == 1 else 125.0
    if mg < 1.80:
        mgso4_g = 2.0
    elif mg < 2.00:
        mgso4_g = 0.0 if is_hold else 1.0
    else:
        mgso4_g = 0.0
    min_hyd = 1080.0 if (not is_hold and chf == 0 and k_val < 3.50) else HYDRATION_RANGE_ML[0]
    return {
        "pt_id": pt_id,
        "status": status,
        "crcl_capped_ml_min": crcl_cap,
        "carboplatin_mg": carbo_mg,
        "paclitaxel_mg": pac_mg,
        "mgso4_g": mgso4_g,
        "aprepitant_mg": aprep_mg,
        "chf_flag": chf,
        "min_hyd_ml": min_hyd,
    }


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    chemo_md = "\n".join([
        f"# Oncology Clinical Pharmacy Work Order — {b}chemo_regimen_pharmacist{b}",
        "",
        "## Scope & Deliverables",
        f"Verify and enter Cycle-4 cytotoxic chemotherapy orders for all 24 inpatient oncology cases in {b}/workspace/oncology_ward{b}.",
        f"The ward protocol {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b} is currently open in LibreOffice Writer on the workstation (with an active shift session header) alongside the Oncology EHR Portal at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile all 24 patients in {b}/workspace/oncology_ward/pharmacy_dispense.db{b} ({b}patients{b} table) against {b}/workspace/oncology_ward/SOP_Clinical_Dosing.md{b}, all clinical chart addenda in {b}/workspace/oncology_ward/charts/{b}, and the full 24-patient Cycle-4 laboratory panel exported from {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        f"2. Populate all 24 rows of {b}chemo_orders(pt_id, regimen_status, crcl_capped_ml_min, carboplatin_mg, paclitaxel_mg, chemo_diluent_ml){b} in {b}pharmacy_dispense.db{b} (sizing only {b}chemo_orders.chemo_diluent_ml{b} for cardiac fluid compliance).",
        f"3. In the EHR Portal under {b}ROLE_VIEW = CHEMO_CYTOTOXIC{b} and {b}UNIT_BASIS = CONV_MG_DL{b}, copy the Pharmacist Verification Seal to the system clipboard and record it in the {b}[CHEMO_ATTESTATION_SEAL]{b} paragraph of {b}Cycle4_Infusion_Protocol.odt{b}, preserving all existing protocol headers and paragraphs.",
        f"4. Save {b}Cycle4_Infusion_Protocol.odt{b} cleanly and export {b}/workspace/oncology_ward/Chemo_Dispense_Signoff.pdf{b}.",
        "",
    ])

    renal_md = "\n".join([
        f"# Oncology Supportive & Renal Pharmacy Work Order — {b}renal_supportive_pharmacist{b}",
        "",
        "## Scope & Deliverables",
        f"Verify and enter Cycle-4 nephroprotective hydration, electrolyte repletion, and antiemetic orders for all 24 inpatient oncology cases in {b}/workspace/oncology_ward{b}.",
        f"The ward protocol {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b} is currently open in LibreOffice Writer on the workstation (with an active shift session header) alongside the Oncology EHR Portal at {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile all 24 patients in {b}/workspace/oncology_ward/pharmacy_dispense.db{b} ({b}patients{b} table) against {b}/workspace/oncology_ward/SOP_Clinical_Dosing.md{b}, all clinical chart addenda in {b}/workspace/oncology_ward/charts/{b}, and the full 24-patient Cycle-4 laboratory panel exported from {b}http://127.0.0.1:{PORTAL_PORT}/{b}.",
        f"2. Populate all 24 rows of {b}supportive_orders(pt_id, regimen_status, mgso4_g, aprepitant_mg, hydration_saline_ml){b} in {b}pharmacy_dispense.db{b} (sizing only {b}supportive_orders.hydration_saline_ml{b} for electrolyte and cardiac fluid compliance).",
        f"3. In the EHR Portal under {b}ROLE_VIEW = RENAL_SUPPORTIVE{b} and {b}UNIT_BASIS = SI_UMOL_L{b}, copy the Pharmacist Verification Seal to the system clipboard and record it in the {b}[RENAL_SUPPORT_ATTESTATION_SEAL]{b} paragraph of {b}Cycle4_Infusion_Protocol.odt{b}, preserving all existing protocol headers and paragraphs.",
        f"4. Save {b}Cycle4_Infusion_Protocol.odt{b} cleanly and export {b}/workspace/oncology_ward/Supportive_Care_Signoff.pdf{b}.",
        "",
    ])
    return {"chemo_regimen_pharmacist": chemo_md, "renal_supportive_pharmacist": renal_md}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    b = chr(96)
    ws = next(iter(workspace_map.values()))
    ow = ws / "oncology_ward"
    ch = ow / "charts"
    ch.mkdir(parents=True, exist_ok=True)
    db_p = ow / "pharmacy_dispense.db"
    if db_p.exists():
        db_p.unlink()
    conn = sqlite3.connect(str(db_p))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE patients (pt_id TEXT PRIMARY KEY, sex TEXT, age_yr INTEGER, actual_wt_kg REAL, height_cm REAL, target_auc REAL, paclitaxel_mg_m2 REAL, cardiac_chf_flag INTEGER, cyp3a4_inhibitor_flag INTEGER)")
    conn.execute("CREATE TABLE chemo_orders (pt_id TEXT PRIMARY KEY, regimen_status TEXT, crcl_capped_ml_min REAL, carboplatin_mg REAL, paclitaxel_mg REAL, chemo_diluent_ml REAL)")
    conn.execute("CREATE TABLE supportive_orders (pt_id TEXT PRIMARY KEY, regimen_status TEXT, mgso4_g REAL, aprepitant_mg REAL, hydration_saline_ml REAL)")
    for pt in PATIENTS_TRUTH:
        pid = pt[0]
        conn.execute("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?)", pt[:9])
        conn.execute("INSERT INTO chemo_orders VALUES (?,?,?,?,?,?)", (pid, "UNVERIFIED", 0.0, 0.0, 0.0, 830.0))
        conn.execute("INSERT INTO supportive_orders VALUES (?,?,?,?,?)", (pid, "UNVERIFIED", 0.0, 0.0, 1110.0))
    conn.commit()
    conn.close()

    (ow / "SOP_Clinical_Dosing.md").write_text(
        "\n".join([
            "# 7-North Inpatient Oncology — Cycle-4 Carboplatin/Paclitaxel & Supportive Care SOP",
            "",
            f"1. **EHR Laboratory Panel & Unit Conventions ({b}http://127.0.0.1:{PORTAL_PORT}/{b})**:",
            f"   - Screen previews {b}PT-01..PT-06{b}; click **Export Full 24-Patient Lab CSV** ({b}/home/user/Downloads/ehr_renal_cbc_panel.csv{b}) for all 24 patients.",
            f"   - Under {b}CONV_MG_DL{b}: {b}serum_creatinine{b}, {b}serum_mg{b}, and {b}total_bilirubin{b} are in {b}mg/dL{b}.",
            f"   - Under {b}SI_UMOL_L{b}: {b}serum_creatinine{b} is in {b}umol/L{b} ({b}1 mg/dL = 88.4 umol/L{b}), {b}serum_mg{b} is in {b}mmol/L{b} ({b}1 mmol/L = 2.43 mg/dL{b}), and {b}total_bilirubin{b} is in {b}umol/L{b} ({b}1 mg/dL = 17.1 umol/L{b}).",
            "",
            "2. **Hematologic Cytopenia Hold Rule**:",
            f"   - If {b}anc_k_ul < 1.0{b} OR {b}platelets_k_ul < 75{b}: {b}regimen_status = 'HOLD_CYTOPENIA'{b} (else {b}'DISPENSE'{b}).",
            f"   - Held patients MUST receive {b}0.0{b} for {b}carboplatin_mg{b}, {b}paclitaxel_mg{b}, {b}chemo_diluent_ml{b}, {b}aprepitant_mg{b}, and {b}hydration_saline_ml{b} (still record {b}crcl_capped_ml_min{b}, and still give {b}2.0 g{b} IV {b}mgso4_g{b} if severe hypomagnesemia applies).",
            "",
            "3. **Cytotoxic Dosing (`chemo_orders`)**:",
            f"   - Devine {b}IBW_kg{b} ({b}50.0{b} M / {b}45.5{b} F + {b}2.3{b} per inch over 60 in); if {b}actual_wt_kg > 1.25 * IBW_kg{b}, use {b}AdjBW_kg = IBW_kg + 0.40*(actual_wt_kg - IBW_kg){b}.",
            f"   - Apply {b}SCr{b} floor and {b}CrCl{b} cap from {b}charts/dosing_nomogram_addendum.png{b} ({b}0.85{b} female factor), rounded to 2 decimals; Calvert {b}target_auc * (crcl_capped_ml_min + 25.0){b} rounded to 0.1 mg; Mosteller BSA capped per chart addendum times hepatic factor in {b}charts/hepatic_bilirubin_protocol.png{b}, rounded to 0.1 mg.",
            f"   - Permitted {b}chemo_diluent_ml{b} for {b}DISPENSE{b}: {b}[500.0, 860.0] mL{b}.",
            "",
            "4. **Supportive Care (`supportive_orders`)**:",
            f"   - Permitted {b}hydration_saline_ml{b} for {b}DISPENSE{b}: {b}[780.0, 1150.0] mL{b}, subject to {b}charts/cardio_renal_supportive_sop.png{b}.",
            "",
        ]),
        encoding="utf-8",
    )
    render_scanned_document_png(
        ch / "dosing_nomogram_addendum.png",
        "PHARMACY CHART ADDENDUM C4-1: OBESITY, BSA & CRCL CAPS",
        [
            "1. Serum Creatinine Floor: Round any SCr < 0.70 mg/dL up to 0.70 mg/dL.",
            "2. Calvert CrCl Cap: Cap calculated CrCl at 125.0 mL/min.",
            "3. Mosteller BSA Cap: Cap BSA at 2.20 m^2 using actual_wt_kg.",
        ],
    )
    render_scanned_document_png(
        ch / "hepatic_bilirubin_protocol.png",
        "PHARMACY CHART ADDENDUM C4-2: HEPATIC TAXANE DOSE ADJUSTMENT",
        [
            "Paclitaxel Hepatic Clearance Adjustment (DISPENSE patients):",
            "  - Total Bilirubin <= 1.50 mg/dL : 100% of BSA-capped paclitaxel dose",
            "  - Total Bilirubin >  1.50 mg/dL : 75% of BSA-capped paclitaxel dose",
        ],
    )
    render_scanned_document_png(
        ch / "cardio_renal_supportive_sop.png",
        "PHARMACY CHART ADDENDUM C4-3: ELECTROLYTES, CYP3A4 & CHF FLUIDS",
        [
            "1. IV Magnesium Sulfate (mgso4_g, evaluate in mg/dL):",
            "   - Serum Mg < 1.80 mg/dL : 2.0 g IV (administer even if HOLD_CYTOPENIA)",
            "   - 1.80 <= Serum Mg < 2.00 mg/dL : 1.0 g IV if DISPENSE, else 0.0 g",
            "   - Serum Mg >= 2.00 mg/dL : 0.0 g IV",
            "2. Aprepitant (DISPENSE patients only):",
            "   80.0 mg if cyp3a4_inhibitor_flag == 1, else 125.0 mg.",
            "3. Non-CHF Hypokalemia (cardiac_chf_flag==0 & DISPENSE): if K < 3.50, hydration >= 1080.0 mL.",
            "4. Cardio-Oncology CHF (cardiac_chf_flag==1 & DISPENSE): diluent + hydration in [1640.0, 1710.0] mL.",
        ],
    )
    write_simple_odt(
        ow / "Cycle4_Infusion_Protocol.odt",
        "Cycle-4 Inpatient Oncology Infusion Master Protocol",
        [
            ("WARD_HEADER", "Unit: 7-North Inpatient Oncology | Cycle 4 Master Verification"),
            ("CHEMO_ATTESTATION_SEAL", "PENDING_CHEMO_PHARMACIST_SEAL"),
            ("RENAL_SUPPORT_ATTESTATION_SEAL", "PENDING_RENAL_PHARMACIST_SEAL"),
        ],
    )
    tickets_root.mkdir(parents=True, exist_ok=True)
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_ehr_html(role_view: str, unit_basis: str) -> str:
    is_si = (unit_basis == "SI_UMOL_L")
    rows = []
    for pt in PATIENTS_TRUTH[:6]:
        pid, sx, ag, _w, _h, _au, _pc, chf, cyp, scr, anc, plt, mg, bili, kv = pt
        rows.append(
            f"<tr><td>{pid}</td><td>{sx}/{ag}</td><td>{round(scr*88.4,1) if is_si else scr}</td>"
            f"<td>{anc:.1f}</td><td>{plt:.0f}</td><td>{round(mg/2.43,3) if is_si else mg}</td>"
            f"<td>{round(bili*17.1,1) if is_si else bili}</td><td>{kv:.1f}</td><td>{chf}</td><td>{cyp}</td></tr>"
        )
    return f"""<!doctype html><html><head><meta charset="utf-8"/><title>Oncology EHR</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f8fafc;}}header{{background:#1e1b4b;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;}}
.bar{{background:#e0e7ff;padding:10px 18px;display:flex;gap:8px;flex-wrap:wrap;}}button{{padding:6px 10px;font-weight:600;cursor:pointer;}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-top:10px;}}th,td{{border:1px solid #cbd5e1;padding:6px 8px;font-size:12px;}}</style></head>
<body>
<header><strong>7-North Oncology EHR</strong><span style="font-family:monospace;">ROLE_VIEW={role_view} | UNIT_BASIS={unit_basis}</span></header>
<div class="bar">
  <button onclick="setE({{role_view:'CHEMO_CYTOTOXIC'}})">CHEMO_CYTOTOXIC</button>
  <button onclick="setE({{role_view:'RENAL_SUPPORTIVE'}})">RENAL_SUPPORTIVE</button>
  <button onclick="setE({{unit_basis:'CONV_MG_DL'}})">CONV_MG_DL</button>
  <button onclick="setE({{unit_basis:'SI_UMOL_L'}})">SI_UMOL_L</button>
  <button onclick="expL()">Export Full 24-Patient Lab CSV (/home/user/Downloads/ehr_renal_cbc_panel.csv)</button>
  <button onclick="cpS()">Copy Pharmacist Verification Seal to Clipboard</button>
  <span id="msg" style="font-family:monospace;font-size:12px;">Ready</span>
</div>
<main style="padding:14px 18px;">
  <table><thead><tr><th>Pt</th><th>Sex/Age</th><th>SCr</th><th>ANC</th><th>Plt</th><th>Mg</th><th>Bili</th><th>K+</th><th>CHF</th><th>CYP3A4</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
</main>
<script>
async function setE(p){{await fetch('/api/ehr/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(p)}});location.reload();}}
async function expL(){{const r=await fetch('/api/ehr/export_csv',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Exported ['+d.unit_basis+']';}}
async function cpS(){{const r=await fetch('/api/ehr/copy_seal',{{method:'POST'}});const d=await r.json();document.getElementById('msg').textContent='Copied ['+d.role_view+'/'+d.unit_basis+']';}}
</script></body></html>"""


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    boot_secret = secrets.token_hex(16)
    sso_cookie = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    lock = threading.Lock()
    state_p = state_dir / "service_state.json"
    pstate: dict[str, Any] = {
        "task_id": TASK_ID,
        "role_view": "CHEMO_CYTOTOXIC",
        "unit_basis": "SI_UMOL_L",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
        "contention_events": 0,
    }
    write_json(state_p, pstate)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_a: Any) -> None: return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec2_c07_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True})
                return
            qs = parse_qs(parsed.query)
            if (qs.get("sso_boot") or [""])[0] == boot_secret:
                self.send_response(302)
                self.send_header("Set-Cookie", f"ec2_c07_sso={sso_cookie}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"})
                return
            with lock:
                raw = _render_ehr_html(pstate["role_view"], pstate["unit_basis"]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if not self._authed():
                self._send_json(401, {"error": "Unauthorized"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            if self.path == "/api/ehr/state":
                with lock:
                    changed = False
                    if body.get("role_view") in ("CHEMO_CYTOTOXIC", "RENAL_SUPPORTIVE") and pstate["role_view"] != body["role_view"]:
                        pstate["role_view"] = body["role_view"]; changed = True
                    if body.get("unit_basis") in ("CONV_MG_DL", "SI_UMOL_L") and pstate["unit_basis"] != body["unit_basis"]:
                        pstate["unit_basis"] = body["unit_basis"]; changed = True
                    if changed:
                        pstate["session_switches"] += 1
                        write_json(state_p, pstate)
                    self._send_json(200, {"ok": True, "role_view": pstate["role_view"], "unit_basis": pstate["unit_basis"]})
                return
            if self.path == "/api/ehr/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 3.5)
                dl_p = Path("/home/user/Downloads/ehr_renal_cbc_panel.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    ub = pstate["unit_basis"]
                    is_si = (ub == "SI_UMOL_L")
                    lines = ["pt_id,serum_creatinine,anc_k_ul,platelets_k_ul,serum_mg,total_bilirubin,serum_k_mmol_l"]
                    for pt in PATIENTS_TRUTH:
                        pid, _sx, _ag, _wt, _ht, _au, _pc, _chf, _cyp, scr, anc, plt, mg, bili, kv = pt
                        lines.append(
                            f"{pid},{round(scr*88.4,1) if is_si else round(scr,2)},{anc:.1f},{plt:.0f},"
                            f"{round(mg/2.43,3) if is_si else round(mg,2)},{round(bili*17.1,1) if is_si else round(bili,2)},{kv:.1f}"
                        )
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    os.chmod(dl_p, 0o644)
                    pstate["download_exports"] += 1
                    write_json(state_p, pstate)
                self._send_json(200, {"ok": True, "unit_basis": ub})
                return
            if self.path == "/api/ehr/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.2 if is_adm else 1.2)
                with lock:
                    rv, ub = pstate["role_view"], pstate["unit_basis"]
                    seal = make_opaque_seal("ec2_c07", f"{rv}:{ub}")
                    pstate["clipboard_copies"] += 1
                    write_json(state_p, pstate)
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "role_view": rv, "unit_basis": ub})
                return
            self._send_json(404, {"error": "Not found"})

    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(json.dumps({"mode": "studio_sso", "url": f"http://127.0.0.1:{port}/?sso_boot={boot_secret}"}) + "\n", encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path) -> None:
    from tasks.exam_contention_v2.c06_impress_calc_actuarial import boot_desktop_apps as _boot_sso
    _boot_sso(workspace_map, state_dir)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ws = next(iter(workspace_map.values()))
    ow = ws / "oncology_ward"
    db_p = ow / "pharmacy_dispense.db"
    odt_p = ow / "Cycle4_Infusion_Protocol.odt"
    pdf_a = ow / "Chemo_Dispense_Signoff.pdf"
    pdf_b = ow / "Supportive_Care_Signoff.pdf"

    chemo_map, supp_map = {}, {}
    if db_p.is_file():
        with sqlite3.connect(str(db_p)) as conn:
            for r in conn.execute("SELECT pt_id, regimen_status, crcl_capped_ml_min, carboplatin_mg, paclitaxel_mg, chemo_diluent_ml FROM chemo_orders"):
                chemo_map[r[0]] = r[1:]
            for r in conn.execute("SELECT pt_id, regimen_status, mgso4_g, aprepitant_mg, hydration_saline_ml FROM supportive_orders"):
                supp_map[r[0]] = r[1:]

    st_a_ok, crcl_ok, carbo_ok, pac_ok, dil_ok = 0, 0, 0, 0, 0
    st_b_ok, mg_ok, aprep_ok, hyd_ok = 0, 0, 0, 0
    chf_ok, chf_tot = 0, 0

    for pt in PATIENTS_TRUTH:
        ref = compute_patient_reference(pt)
        pid = ref["pt_id"]
        is_hold = (ref["status"] == "HOLD_CYTOPENIA")
        co = chemo_map.get(pid)
        if co:
            if co[0] == ref["status"]: st_a_ok += 1
            if is_hold or abs(float(co[1]) - ref["crcl_capped_ml_min"]) <= 0.6: crcl_ok += 1
            if abs(float(co[2]) - ref["carboplatin_mg"]) <= 2.5: carbo_ok += 1
            if abs(float(co[3]) - ref["paclitaxel_mg"]) <= 2.5: pac_ok += 1
            if (is_hold and abs(float(co[4])) <= 0.5) or ((not is_hold) and DILUENT_RANGE_ML[0] <= float(co[4]) <= DILUENT_RANGE_ML[1]):
                dil_ok += 1
        so = supp_map.get(pid)
        if so:
            if so[0] == ref["status"]: st_b_ok += 1
            if abs(float(so[1]) - ref["mgso4_g"]) <= 0.05: mg_ok += 1
            if abs(float(so[2]) - ref["aprepitant_mg"]) <= 0.5: aprep_ok += 1
            if (is_hold and abs(float(so[3])) <= 0.5) or ((not is_hold) and ref["min_hyd_ml"] <= float(so[3]) <= HYDRATION_RANGE_ML[1]):
                hyd_ok += 1
        if not is_hold and ref["chf_flag"] == 1:
            chf_tot += 1
            if co and so and CHF_FLUID_BAND_ML[0] <= (float(co[4]) + float(so[3])) <= CHF_FLUID_BAND_ML[1]:
                chf_ok += 1

    odt_txt = read_odt_plain_text(odt_p)
    pa_txt = extract_pdf_text(pdf_a)
    pb_txt = extract_pdf_text(pdf_b)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("chemo_hold_status", st_a_ok == 24, 0.15, f"chemo_orders regimen_status {st_a_ok}/24"),
        ("crcl_capped", crcl_ok == 24, 0.20, f"crcl_capped_ml_min {crcl_ok}/24"),
        ("carboplatin_doses", carbo_ok == 24, 0.20, f"carboplatin_mg {carbo_ok}/24"),
        ("paclitaxel_hepatic", pac_ok == 24, 0.15, f"paclitaxel_mg {pac_ok}/24"),
        ("diluent_bounds", dil_ok == 24, 0.10, f"chemo_diluent_ml {dil_ok}/24"),
        ("chemo_seal_odt_pdf", CHEMO_SEAL in odt_txt and CHEMO_SEAL in pa_txt and DESK_TAG in pa_txt, 0.20, "Missing CHEMO_ATTESTATION_SEAL or DESK_TAG in .odt / Chemo PDF"),
    ]
    checks_b: list[tuple[str, bool, float, str]] = [
        ("supp_hold_status", st_b_ok == 24, 0.15, f"supportive_orders regimen_status {st_b_ok}/24"),
        ("mgso4_repletion", mg_ok == 24, 0.25, f"mgso4_g {mg_ok}/24"),
        ("aprepitant_cyp3a4", aprep_ok == 24, 0.20, f"aprepitant_mg {aprep_ok}/24"),
        ("hydration_hypokalemia", hyd_ok == 24, 0.20, f"hydration_saline_ml {hyd_ok}/24"),
        ("renal_seal_odt_pdf", RENAL_SEAL in odt_txt and RENAL_SEAL in pb_txt and DESK_TAG in pb_txt, 0.20, "Missing RENAL_SUPPORT_ATTESTATION_SEAL or DESK_TAG in .odt / Supportive PDF"),
    ]
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("writer_desk_tag", DESK_TAG in odt_txt, 0.08, f"Cycle4_Infusion_Protocol.odt lost {DESK_TAG}"),
        ("chf_fluid_envelope", chf_ok == chf_tot, 0.12, f"CHF 24h IV fluid {chf_ok}/{chf_tot} in {list(CHF_FLUID_BAND_ML)}"),
        ("no_split_brain", service_state.get("open_gui_split_brain") is not True, 0.05, "Open Writer held stale unsaved buffer"),
    ]
    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.90,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    assert role in ("chemo_regimen_pharmacist", "renal_supportive_pharmacist")
    ws = next(iter(workspace_map.values()))
    ow = ws / "oncology_ward"
    db_p = ow / "pharmacy_dispense.db"
    odt_p = ow / "Cycle4_Infusion_Protocol.odt"
    adm_p = Path("/opt/ec2_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(odt_p)
        is_c = (role == "chemo_regimen_pharmacist")
        rv = "CHEMO_CYTOTOXIC" if is_c else "RENAL_SUPPORTIVE"
        ub = "CONV_MG_DL" if is_c else "SI_UMOL_L"
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/ehr/state", data=json.dumps({"role_view": rv, "unit_basis": ub}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST"), timeout=10).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/ehr/export_csv", data=b"{}", headers=adm_hdr, method="POST"), timeout=15).read()
        urllib.request.urlopen(urllib.request.Request(f"{base}/api/ehr/copy_seal", data=b"{}", headers=adm_hdr, method="POST"), timeout=10).read()
        seal_txt = get_x11_clipboard()

        with sqlite3.connect(str(db_p), timeout=15.0) as conn:
            for pt in PATIENTS_TRUTH:
                ref = compute_patient_reference(pt)
                pid = ref["pt_id"]
                is_hold = (ref["status"] == "HOLD_CYTOPENIA")
                if is_c:
                    cur_hyd = float(conn.execute("SELECT hydration_saline_ml FROM supportive_orders WHERE pt_id=?", (pid,)).fetchone()[0])
                    dil = 0.0 if is_hold else (round(max(DILUENT_RANGE_ML[0], min(DILUENT_RANGE_ML[1], 1675.0 - cur_hyd)), 1) if ref["chf_flag"] == 1 else 600.0)
                    conn.execute("UPDATE chemo_orders SET regimen_status=?, crcl_capped_ml_min=?, carboplatin_mg=?, paclitaxel_mg=?, chemo_diluent_ml=? WHERE pt_id=?", (ref["status"], ref["crcl_capped_ml_min"], ref["carboplatin_mg"], ref["paclitaxel_mg"], dil, pid))
                else:
                    cur_dil = float(conn.execute("SELECT chemo_diluent_ml FROM chemo_orders WHERE pt_id=?", (pid,)).fetchone()[0])
                    hyd = 0.0 if is_hold else (round(max(HYDRATION_RANGE_ML[0], min(HYDRATION_RANGE_ML[1], 1675.0 - cur_dil)), 1) if ref["chf_flag"] == 1 else max(1000.0, min(1120.0, ref["min_hyd_ml"])))
                    conn.execute("UPDATE supportive_orders SET regimen_status=?, mgso4_g=?, aprepitant_mg=?, hydration_saline_ml=? WHERE pt_id=?", (ref["status"], ref["mgso4_g"], ref["aprepitant_mg"], hyd, pid))
            conn.commit()

        cur_txt = read_odt_plain_text(odt_p)
        paras = [("DESK_SESSION_TAG", DESK_TAG)] if DESK_TAG in cur_txt else []
        paras.extend([
            ("WARD_HEADER", "Unit: 7-North Inpatient Oncology | Cycle 4 Master Verification"),
            ("CHEMO_ATTESTATION_SEAL", seal_txt if is_c else (CHEMO_SEAL if CHEMO_SEAL in cur_txt else "PENDING_CHEMO_PHARMACIST_SEAL")),
            ("RENAL_SUPPORT_ATTESTATION_SEAL", seal_txt if (not is_c) else (RENAL_SEAL if RENAL_SEAL in cur_txt else "PENDING_RENAL_PHARMACIST_SEAL")),
        ])
        write_simple_odt(odt_p, "Cycle-4 Inpatient Oncology Infusion Master Protocol", paras)
        reload_open_libreoffice_docs([odt_p])
        convert_doc_to_pdf_isolated(odt_p, ow / ("Chemo_Dispense_Signoff.pdf" if is_c else "Supportive_Care_Signoff.pdf"))

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    ws = next(iter(workspace_map.values()))
    db_p = ws / "oncology_ward" / "pharmacy_dispense.db"
    solve_role("chemo_regimen_pharmacist", workspace_map, port, careful_conc=False)
    solve_role("renal_supportive_pharmacist", workspace_map, port, careful_conc=False)
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("UPDATE chemo_orders SET chemo_diluent_ml=565.0 WHERE pt_id IN ('PT-01','PT-03','PT-06','PT-09','PT-17')")
        conn.execute("UPDATE supportive_orders SET hydration_saline_ml=845.0 WHERE pt_id IN ('PT-01','PT-03','PT-06','PT-09','PT-17')")
        conn.commit()
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 2
    write_json(sp, st)
