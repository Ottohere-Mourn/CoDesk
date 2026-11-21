"""EC-02: Hospital Oncology Infusion Dosing, Shared HttpOnly EHR Session, X11 Clipboard & Open Writer Protocol.

Contention Archetypes:
  1. In-Memory GUI Dirty Buffer vs. Disk CLI Split-Brain (Cycle4_Infusion_Protocol.odt open in LibreOffice Writer with unsaved desk tag).
  2. Cross-Step System Clipboard Transaction (Pharmacist EHR Attestation Seals copied to X11 CLIPBOARD).
  4. Shared Authenticated Browser Session & ~/Downloads (SI vs Conventional unit toggle + paginated 24-patient CSV overwrite).
  5. Bidirectional Coupled Clinical Envelope (24h CHF IV Fluid Volume in [1640.0, 1710.0] mL).
"""
from __future__ import annotations

import hashlib
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

from tasks.exam_contention_v1.common import (
    advisory_lock,
    convert_doc_to_pdf_isolated,
    extract_pdf_text,
    find_unexpected_workspace_files,
    flush_open_libreoffice_to_disk,
    get_x11_clipboard,
    make_opaque_seal,
    read_odt_plain_text,
    reload_open_libreoffice_window,
    render_scanned_document_png,
    set_x11_clipboard,
    verify_prompt_driver_and_ban_clean,
    write_json,
    write_simple_odt,
)

TASK_ID = "EC-02"
PORTAL_PORT = 18802
DESK_TAG = "ONC-7N-ROUND-514"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Hospital Oncology Infusion Dosing, Shared EHR Unit Toggle, X11 Clipboard & Open Writer Split-Brain",
    "domain": "Clinical Oncology Pharmacology & Hospital EHR Dispensing",
    "archetypes": (
        "x11_clipboard_cross_step_seal_race",
        "shared_httponly_ehr_unit_toggle_and_downloads",
        "libreoffice_writer_odt_dirty_buffer_split_brain",
        "chf_iv_fluid_volume_bidirectional_envelope",
    ),
    "roles": ("chemo_regimen_pharmacist", "renal_supportive_pharmacist"),
    "portal_port": PORTAL_PORT,
    "open_gui_doc": "/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt",
    "open_gui_unsaved_tag": DESK_TAG,
    "conc_role_timeout_s": 1800,
    "seq_role_timeout_s": 1800,
}

# 24 inpatient oncology cases:
# (pt_id, sex, age, wt_kg, ht_cm, auc, pac_mg_m2, chf_flag, cyp3a4_flag, scr_mg_dl, anc_k, plt_k, mg_mg_dl, bili_mg_dl, k_mmol_l)
PATIENTS_TRUTH: list[tuple] = [
    ("PT-01", "M", 64,  82.0, 178.0, 5.0, 175.0, 1, 0, 1.15, 2.8, 190.0, 1.92, 0.9, 4.1),
    ("PT-02", "F", 58,  96.0, 162.0, 5.0, 175.0, 0, 1, 0.95, 3.1, 210.0, 1.72, 1.8, 3.3),  # Obese + CYP3A4 + low Mg + Bili>1.5 + K<3.5
    ("PT-03", "M", 71,  68.0, 172.0, 4.0, 135.0, 1, 1, 1.42, 2.2, 145.0, 1.85, 1.1, 4.0),  # CHF + CYP3A4
    ("PT-04", "F", 49,  61.0, 165.0, 6.0, 175.0, 0, 0, 0.58, 0.8, 160.0, 2.05, 0.7, 3.9),  # HOLD: ANC 0.8 < 1.0
    ("PT-05", "M", 52, 118.0, 180.0, 6.0, 175.0, 0, 0, 0.82, 4.0, 240.0, 2.10, 0.8, 4.2),  # Obese + CrCl>125 + BSA>2.20
    ("PT-06", "F", 67,  74.0, 160.0, 5.0, 175.0, 1, 0, 1.28, 1.9, 130.0, 1.68, 1.7, 3.8),  # CHF + Obese + Mg<1.8 + Bili>1.5
    ("PT-07", "M", 61,  79.0, 175.0, 5.0, 175.0, 0, 1, 1.05, 2.5,  62.0, 1.75, 1.0, 3.7),  # HOLD: Plt 62 < 75 + Mg<1.8
    ("PT-08", "F", 55,  58.0, 164.0, 5.0, 175.0, 0, 0, 0.62, 2.9, 205.0, 1.95, 0.8, 3.2),  # scr<0.70 floor + K<3.5
    ("PT-09", "M", 74,  84.0, 174.0, 4.0, 135.0, 1, 0, 1.55, 2.1, 155.0, 1.78, 1.2, 4.3),  # CHF + Mg<1.8
    ("PT-10", "F", 44, 104.0, 168.0, 6.0, 175.0, 0, 1, 0.78, 3.6, 230.0, 2.04, 1.9, 4.0),  # Obese + CrCl cap + CYP3A4 + Bili>1.5
    ("PT-11", "M", 59,  76.0, 176.0, 5.0, 175.0, 0, 0, 1.10, 0.9,  68.0, 1.88, 0.9, 3.8),  # HOLD: ANC 0.9 & Plt 68
    ("PT-12", "F", 63,  66.0, 163.0, 5.0, 175.0, 0, 0, 1.02, 2.4, 175.0, 1.91, 0.9, 3.4),  # K<3.5
    ("PT-13", "M", 47,  92.0, 185.0, 6.0, 175.0, 0, 0, 0.76, 3.8, 260.0, 2.15, 1.0, 4.1),  # CrCl>125 cap
    ("PT-14", "F", 69,  88.0, 158.0, 4.0, 135.0, 0, 1, 1.34, 2.0, 140.0, 1.65, 1.6, 3.9),  # Obese + CYP3A4 + Mg<1.8 + Bili>1.5
    ("PT-15", "M", 66,  73.0, 171.0, 5.0, 175.0, 0, 0, 1.18, 2.7, 182.0, 1.84, 1.1, 4.0),
    ("PT-16", "F", 53,  63.0, 166.0, 5.0, 175.0, 0, 0, 0.88, 3.2, 215.0, 2.02, 0.8, 3.9),
    ("PT-17", "M", 70,  91.0, 173.0, 4.0, 135.0, 1, 1, 1.48, 2.3, 148.0, 1.82, 1.0, 4.2),  # CHF + Obese + CYP3A4
    ("PT-18", "F", 51,  56.0, 160.0, 5.0, 175.0, 0, 0, 0.59, 3.0, 198.0, 1.76, 0.7, 3.3),  # scr<0.70 floor + Mg<1.8 + K<3.5
    ("PT-19", "M", 45, 112.0, 179.0, 6.0, 175.0, 0, 1, 0.74, 3.9, 250.0, 2.08, 2.1, 4.1),  # Obese + CrCl>125 + BSA>2.2 + Bili>1.5
    ("PT-20", "F", 62,  70.0, 164.0, 5.0, 175.0, 0, 0, 1.08, 0.7, 135.0, 1.94, 0.9, 3.8),  # HOLD: ANC 0.7
    ("PT-21", "M", 68,  78.0, 174.0, 5.0, 175.0, 0, 0, 1.22, 2.6, 172.0, 1.89, 1.1, 3.4),  # K<3.5
    ("PT-22", "F", 57,  89.0, 161.0, 5.0, 175.0, 0, 1, 0.98, 2.8, 188.0, 1.71, 0.9, 4.0),  # Obese + CYP3A4 + Mg<1.8
    ("PT-23", "M", 60,  83.0, 177.0, 5.0, 175.0, 0, 0, 1.12, 2.5,  71.0, 2.01, 1.0, 4.1),  # HOLD: Plt 71 < 75
    ("PT-24", "F", 48,  64.0, 167.0, 6.0, 175.0, 0, 0, 0.66, 3.4, 225.0, 1.96, 1.7, 3.9),  # scr<0.70 floor + Bili>1.5
]

CHEMO_SEAL = make_opaque_seal("ec02", "CHEMO_CYTOTOXIC:CONV_MG_DL")
RENAL_SEAL = make_opaque_seal("ec02", "RENAL_SUPPORTIVE:SI_UMOL_L")
ALLOWED_ONC_FILES = {
    "pharmacy_dispense.db",
    "Cycle4_Infusion_Protocol.odt",
    "Chemo_Dispense_Signoff.pdf",
    "Supportive_Care_Signoff.pdf",
    "SOP_Clinical_Dosing.md",
    "charts/dosing_nomogram_addendum.png",
    "charts/hepatic_bilirubin_protocol.png",
    "charts/cardio_renal_supportive_sop.png",
}

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
        carbo_mg = 0.0
        pac_mg = 0.0
        aprep_mg = 0.0
    else:
        status = "DISPENSE"
        carbo_mg = round(auc * (crcl_cap + 25.0), 1)
        bili_mult = 0.75 if bili > 1.50 else 1.0
        pac_mg = round(pac_rate * bsa_eff * bili_mult, 1)
        aprep_mg = 80.0 if cyp == 1 else 125.0

    mg_g = 2.0 if mg < 1.80 else (1.0 if (not is_hold and mg < 2.00) else 0.0)
    min_hyd_ml = 1080.0 if (not is_hold and chf == 0 and k_val < 3.50) else HYDRATION_RANGE_ML[0]
    return {
        "pt_id": pt_id,
        "status": status,
        "crcl_capped_ml_min": crcl_cap,
        "carboplatin_mg": carbo_mg,
        "paclitaxel_mg": pac_mg,
        "aprepitant_mg": aprep_mg,
        "mgso4_g": mg_g,
        "chf_flag": chf,
        "min_hyd_ml": min_hyd_ml,
    }


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    chemo_md = "\n".join([
        f"# Oncology Clinical Pharmacy Work Order — {b}chemo_regimen_pharmacist{b}",
        "",
        "## Scope & Deliverables",
        f"Verify and enter Cycle-4 cytotoxic chemotherapy orders for all 24 inpatient oncology cases in {b}/workspace/oncology_ward{b}.",
        f"The ward master protocol {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b} is currently open in LibreOffice Writer on the workstation (with an active shift session header) alongside the Oncology EHR Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile all 24 patients in {b}/workspace/oncology_ward/pharmacy_dispense.db{b} ({b}patients{b} table) against {b}/workspace/oncology_ward/SOP_Clinical_Dosing.md{b}, all clinical chart addenda in {b}/workspace/oncology_ward/charts/{b}, and the full 24-patient Cycle-4 laboratory panel from the EHR Portal ({b}http://127.0.0.1:{PORTAL_PORT}{b}).",
        f"2. Populate all 24 rows of {b}chemo_orders(pt_id, regimen_status, crcl_capped_ml_min, carboplatin_mg, paclitaxel_mg, chemo_diluent_ml){b} in {b}pharmacy_dispense.db{b} in compliance with all renal, hematologic, hepatic, and cardio-oncology fluid rules.",
        f"3. In the EHR Portal under {b}ROLE_VIEW = CHEMO_CYTOTOXIC{b} and {b}UNIT_BASIS = CONV_MG_DL{b}, copy the Pharmacist Verification Seal to the system clipboard and record it in the {b}[CHEMO_ATTESTATION_SEAL]{b} paragraph of {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b}, preserving all existing protocol headers and paragraphs.",
        f"4. Save {b}Cycle4_Infusion_Protocol.odt{b} cleanly and export {b}/workspace/oncology_ward/Chemo_Dispense_Signoff.pdf{b}. Keep {b}/workspace/oncology_ward{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])

    renal_md = "\n".join([
        f"# Oncology Supportive & Renal Pharmacy Work Order — {b}renal_supportive_pharmacist{b}",
        "",
        "## Scope & Deliverables",
        f"Verify and enter Cycle-4 nephroprotective hydration, electrolyte repletion, and antiemetic orders for all 24 inpatient oncology cases in {b}/workspace/oncology_ward{b}.",
        f"The ward master protocol {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b} is currently open in LibreOffice Writer on the workstation (with an active shift session header) alongside the Oncology EHR Portal at {b}http://127.0.0.1:{PORTAL_PORT}{b}.",
        "",
        "Deliverables:",
        f"1. Reconcile all 24 patients in {b}/workspace/oncology_ward/pharmacy_dispense.db{b} ({b}patients{b} table) against {b}/workspace/oncology_ward/SOP_Clinical_Dosing.md{b}, all clinical chart addenda in {b}/workspace/oncology_ward/charts/{b}, and the full 24-patient Cycle-4 laboratory panel from the EHR Portal ({b}http://127.0.0.1:{PORTAL_PORT}{b}).",
        f"2. Populate all 24 rows of {b}supportive_orders(pt_id, regimen_status, mgso4_g, aprepitant_mg, hydration_saline_ml){b} in {b}pharmacy_dispense.db{b} in compliance with all hematologic, electrolyte, drug-interaction, and cardio-oncology fluid rules.",
        f"3. In the EHR Portal under {b}ROLE_VIEW = RENAL_SUPPORTIVE{b} and {b}UNIT_BASIS = SI_UMOL_L{b}, copy the Pharmacist Verification Seal to the system clipboard and record it in the {b}[RENAL_SUPPORT_ATTESTATION_SEAL]{b} paragraph of {b}/workspace/oncology_ward/Cycle4_Infusion_Protocol.odt{b}, preserving all existing protocol headers and paragraphs.",
        f"4. Save {b}Cycle4_Infusion_Protocol.odt{b} cleanly and export {b}/workspace/oncology_ward/Supportive_Care_Signoff.pdf{b}. Keep {b}/workspace/oncology_ward{b} clean of scratch scripts or extra files (use {b}/tmp{b} for intermediate work).",
        "",
    ])
    return {"chemo_regimen_pharmacist": chemo_md, "renal_supportive_pharmacist": renal_md}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    b = chr(96)
    ow = workspace / "oncology_ward"
    ch = ow / "charts"
    ch.mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    db_p = ow / "pharmacy_dispense.db"
    if db_p.exists():
        db_p.unlink()
    conn = sqlite3.connect(str(db_p))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE patients (
            pt_id TEXT PRIMARY KEY,
            sex TEXT NOT NULL,
            age_yr INTEGER NOT NULL,
            actual_wt_kg REAL NOT NULL,
            height_cm REAL NOT NULL,
            target_auc REAL NOT NULL,
            paclitaxel_mg_m2 REAL NOT NULL,
            cardiac_chf_flag INTEGER NOT NULL,
            cyp3a4_inhibitor_flag INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE chemo_orders (
            pt_id TEXT PRIMARY KEY,
            regimen_status TEXT NOT NULL,
            crcl_capped_ml_min REAL NOT NULL,
            carboplatin_mg REAL NOT NULL,
            paclitaxel_mg REAL NOT NULL,
            chemo_diluent_ml REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE supportive_orders (
            pt_id TEXT PRIMARY KEY,
            regimen_status TEXT NOT NULL,
            mgso4_g REAL NOT NULL,
            aprepitant_mg REAL NOT NULL,
            hydration_saline_ml REAL NOT NULL
        )
        """
    )
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
            f"1. **EHR Laboratory Panel & Unit Conventions ({b}http://127.0.0.1:{PORTAL_PORT}{b})**:",
            f"   - The EHR browser screen previews only {b}PT-01..PT-06{b}; click **Export Lab CSV** ({b}/home/gui/Downloads/ehr_renal_cbc_panel.csv{b}) to retrieve all 24 patients.",
            f"   - Under {b}CONV_MG_DL{b}: {b}serum_creatinine{b}, {b}serum_mg{b}, and {b}total_bilirubin{b} are reported in {b}mg/dL{b}.",
            f"   - Under {b}SI_UMOL_L{b}: {b}serum_creatinine{b} is in {b}umol/L{b} ({b}1 mg/dL = 88.4 umol/L{b}), {b}serum_mg{b} is in {b}mmol/L{b} ({b}1 mmol/L = 2.43 mg/dL{b}), and {b}total_bilirubin{b} is in {b}umol/L{b} ({b}1 mg/dL = 17.1 umol/L{b}).",
            "",
            "2. **Hematologic Cytopenia Hold Rule (Applies to Both Tables)**:",
            f"   - If {b}anc_k_ul < 1.0{b} OR {b}platelets_k_ul < 75{b}: set {b}regimen_status = 'HOLD_CYTOPENIA'{b} (otherwise {b}'DISPENSE'{b}).",
            f"   - Held patients MUST receive {b}0.0{b} for {b}carboplatin_mg{b}, {b}paclitaxel_mg{b}, {b}chemo_diluent_ml{b}, {b}aprepitant_mg{b}, and {b}hydration_saline_ml{b} (note: still compute and record {b}crcl_capped_ml_min{b}, and still administer acute {b}2.0 g{b} IV {b}mgso4_g{b} if severe hypomagnesemia applies per chart addendum).",
            "",
            "3. **Cytotoxic Dosing Equations (`chemo_orders`)**:",
            f"   - **Cockcroft-Gault CrCl**: Compute Devine Ideal Body Weight ({b}IBW_kg{b}, {b}50.0 kg{b} male / {b}45.5 kg{b} female + {b}2.3 kg{b} per inch over 60 inches). For obese patients ({b}actual_wt_kg > 1.25 * IBW_kg{b}), use 40% Adjusted Body Weight ({b}IBW_kg + 0.40 * (actual_wt_kg - IBW_kg){b}); otherwise use {b}actual_wt_kg{b}.",
            f"   - Apply the serum creatinine floor and glomerular CrCl cap specified in {b}charts/dosing_nomogram_addendum.png{b} (with standard {b}0.85{b} female Cockcroft-Gault factor), rounding {b}crcl_capped_ml_min{b} to 2 decimal places.",
            f"   - **Carboplatin (Calvert)**: {b}target_auc * (crcl_capped_ml_min + 25.0){b}, rounded to 0.1 mg.",
            f"   - **Paclitaxel**: Mosteller BSA using {b}actual_wt_kg{b} subject to the BSA cap in {b}charts/dosing_nomogram_addendum.png{b}, multiplied by any hepatic bilirubin modification factor in {b}charts/hepatic_bilirubin_protocol.png{b}, rounded to 0.1 mg.",
            f"   - Permitted {b}chemo_diluent_ml{b} for {b}DISPENSE{b} patients: {b}[500.0, 860.0] mL{b} (size only {b}chemo_orders.chemo_diluent_ml{b}).",
            "",
            "4. **Supportive Care & IV Fluid Envelope (`supportive_orders`)**:",
            f"   - Permitted {b}hydration_saline_ml{b} for {b}DISPENSE{b} patients: {b}[780.0, 1150.0] mL{b} (size only {b}supportive_orders.hydration_saline_ml{b}), subject to the hypokalemia dilution floor and CHF 24h combined fluid window in {b}charts/{b}.",
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
        stamp_text="ONCOLOGY P&T APPROVED",
        tilt_deg=-1.5,
    )
    render_scanned_document_png(
        ch / "hepatic_bilirubin_protocol.png",
        "PHARMACY CHART ADDENDUM C4-2: HEPATIC TAXANE DOSE ADJUSTMENT",
        [
            "Paclitaxel Hepatic Clearance Adjustment (DISPENSE patients):",
            "  - Total Bilirubin <= 1.50 mg/dL : 100% of BSA-capped paclitaxel dose",
            "  - Total Bilirubin >  1.50 mg/dL : 75% of BSA-capped paclitaxel dose",
            "    (25% hepatic dose reduction; note SI conversion 1 mg/dL = 17.1 umol/L)",
        ],
        stamp_text="HEPATOLOGY SIGN-OFF",
        tilt_deg=1.7,
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
            "3. Non-CHF Hypokalemia Dilution (cardiac_chf_flag==0 & DISPENSE):",
            "   If serum_k_mmol_l < 3.50, hydration_saline_ml MUST be >= 1080.0 mL.",
            "4. Cardio-Oncology CHF Restriction (cardiac_chf_flag==1 & DISPENSE):",
            "   Combined chemo_diluent_ml + hydration_saline_ml MUST lie",
            "   within [1640.0, 1710.0] mL.",
        ],
        stamp_text="CARDIO-ONCOLOGY SOP",
        tilt_deg=-1.6,
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

    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")


def _render_ehr_html(role_view: str, unit_basis: str, view_tab: str = "LABS") -> str:
    is_si = (unit_basis == "SI_UMOL_L")
    scr_hdr = "SCr (umol/L)" if is_si else "SCr (mg/dL)"
    mg_hdr = "Mg (mmol/L)" if is_si else "Mg (mg/dL)"
    bili_hdr = "Bili (umol/L)" if is_si else "Bili (mg/dL)"
    rows_html = []
    for pt in PATIENTS_TRUTH[:6]:
        pt_id, sex, age, _wt, _ht, _auc, _pac, chf, cyp, scr_mg, anc, plt, mg_mg, bili_mg, k_v = pt
        scr_disp = round(scr_mg * 88.4, 1) if is_si else round(scr_mg, 2)
        mg_disp = round(mg_mg / 2.43, 3) if is_si else round(mg_mg, 2)
        bili_disp = round(bili_mg * 17.1, 1) if is_si else round(bili_mg, 2)
        rows_html.append(
            f"<tr><td>{pt_id}</td><td>{sex}/{age}</td><td>{scr_disp}</td><td>{anc:.1f}</td><td>{plt:.0f}</td>"
            f"<td>{mg_disp}</td><td>{bili_disp}</td><td>{k_v:.1f}</td>"
            f"<td>{'CHF_RESTRICT' if chf else 'STD'}</td><td>{'CYP3A4_INH' if cyp else 'NONE'}</td></tr>"
        )
    if view_tab == "CHARTS":
        main_html = (
            "<h3>Authenticated Ward Pharmacy Scanned Chart Addenda (C4-1..C4-3)</h3>"
            "<p><img src='/charts/dosing_nomogram_addendum.png' style='max-width:860px;border:1px solid #94a3b8;margin-bottom:8px;'/></p>"
            "<p><img src='/charts/hepatic_bilirubin_protocol.png' style='max-width:860px;border:1px solid #94a3b8;margin-bottom:8px;'/></p>"
            "<p><img src='/charts/cardio_renal_supportive_sop.png' style='max-width:860px;border:1px solid #94a3b8;'/></p>"
        )
    else:
        main_html = (
            "<p style='font-size:13px;color:#334155;'><strong>Previewing 6 of 24 Cycle-4 Inpatient Cases</strong> — Export Lab CSV to retrieve complete 24-patient panel under active unit basis.</p>"
            f"<table><thead><tr><th>Pt</th><th>Sex/Age</th><th>{scr_hdr}</th><th>ANC</th><th>Plt</th><th>{mg_hdr}</th><th>{bili_hdr}</th><th>K+ (mmol/L)</th><th>Cardiac</th><th>CYP3A4</th></tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Oncology Inpatient EHR — Cycle-4 Lab & Verification Portal</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: #1e1b4b; color: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }}
    .badge {{ background: #4338ca; padding: 4px 10px; border-radius: 4px; font-family: monospace; font-size: 13px; }}
    .toolbar {{ background: #e0e7ff; padding: 10px 20px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid #c7d2fe; }}
    button {{ background: #ffffff; border: 1px solid #4f46e5; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-weight: 600; }}
    button.active {{ background: #1e1b4b; color: #ffffff; }}
    main {{ padding: 16px 20px; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; font-size: 12px; text-align: left; }}
    th {{ background: #eef2ff; }}
  </style>
</head>
<body>
  <header>
    <div><strong>7-North Oncology EHR — Cycle-4 Laboratory & Sign-Off</strong></div>
    <div class="badge" id="ehr-banner">ROLE_VIEW={role_view} | UNIT_BASIS={unit_basis}</div>
  </header>
  <div class="toolbar">
    <strong>Role View:</strong>
    <button class="{'active' if role_view == 'CHEMO_CYTOTOXIC' else ''}" onclick="setEhr({{role_view:'CHEMO_CYTOTOXIC'}})">CHEMO_CYTOTOXIC</button>
    <button class="{'active' if role_view == 'RENAL_SUPPORTIVE' else ''}" onclick="setEhr({{role_view:'RENAL_SUPPORTIVE'}})">RENAL_SUPPORTIVE</button>
    <strong>Unit Basis:</strong>
    <button class="{'active' if unit_basis == 'CONV_MG_DL' else ''}" onclick="setEhr({{unit_basis:'CONV_MG_DL'}})">CONV_MG_DL</button>
    <button class="{'active' if unit_basis == 'SI_UMOL_L' else ''}" onclick="setEhr({{unit_basis:'SI_UMOL_L'}})">SI_UMOL_L</button>
    <button class="{'active' if view_tab == 'LABS' else ''}" onclick="setEhr({{view_tab:'LABS'}})">Lab Panel (6/24)</button>
    <button class="{'active' if view_tab == 'CHARTS' else ''}" onclick="setEhr({{view_tab:'CHARTS'}})">Chart Addenda (3 Scans)</button>
    <button onclick="exportLab()">Export Full 24-Patient Lab CSV (/home/gui/Downloads/ehr_renal_cbc_panel.csv)</button>
    <button onclick="copySeal()">Copy Pharmacist Verification Seal to Clipboard</button>
    <span id="msg" style="font-family:monospace;font-size:12px;color:#3730a3;">Ready</span>
  </div>
  <main>
    {main_html}
  </main>
  <script>
    async function setEhr(p) {{
      const r = await fetch('/api/ehr/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(p)}});
      if (r.ok) window.location.reload();
    }}
    async function exportLab() {{
      document.getElementById('msg').textContent = 'Running 24-patient LIS batch extract...';
      const r = await fetch('/api/ehr/export_csv', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Exported 24 rows [' + d.unit_basis + ']') : 'Error';
    }}
    async function copySeal() {{
      const r = await fetch('/api/ehr/copy_seal', {{method:'POST'}});
      const d = await r.json();
      document.getElementById('msg').textContent = d.ok ? ('Copied seal for ' + d.role_view + '/' + d.unit_basis) : 'Error';
    }}
  </script>
</body>
</html>
"""


def run_portal_service(port: int, workspace: Path, state_dir: Path, boot_file: Path) -> None:
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
        "view_tab": "LABS",
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "clipboard_copies": 0,
    }

    def persist() -> None:
        write_json(state_p, pstate)

    persist()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a: Any) -> None:
            return

        def _authed(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("ec02_ehr_sso")
                return bool(m and m.value == sso_cookie)
            except Exception:
                return False

        def _send_json(self, code: int, obj: dict) -> None:
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "task_id": TASK_ID})
                return
            if parsed.path == "/":
                qs = parse_qs(parsed.query)
                if (qs.get("sso_boot") or [""])[0] == boot_secret:
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"ec02_ehr_sso={sso_cookie}; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated EHR browser session required"})
                    return
                with lock:
                    html = _render_ehr_html(pstate["role_view"], pstate["unit_basis"], pstate["view_tab"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path.startswith("/charts/"):
                if not self._authed():
                    self._send_json(401, {"error": "Authenticated EHR browser session required"})
                    return
                fn = Path(parsed.path).name
                fp = workspace / "oncology_ward" / "charts" / fn
                if fp.is_file() and fp.suffix == ".png":
                    raw_png = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw_png)))
                    self.end_headers()
                    self.wfile.write(raw_png)
                    return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._authed():
                self._send_json(401, {"error": "Authenticated EHR browser session required"})
                return
            n = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8")) if n > 0 else {}
            except Exception:
                body = {}

            if parsed.path == "/api/ehr/state":
                with lock:
                    changed = False
                    if body.get("role_view") in ("CHEMO_CYTOTOXIC", "RENAL_SUPPORTIVE"):
                        if pstate["role_view"] != body["role_view"]:
                            changed = True
                        pstate["role_view"] = body["role_view"]
                    if body.get("unit_basis") in ("CONV_MG_DL", "SI_UMOL_L"):
                        if pstate["unit_basis"] != body["unit_basis"]:
                            changed = True
                        pstate["unit_basis"] = body["unit_basis"]
                    if body.get("view_tab") in ("LABS", "CHARTS"):
                        if pstate["view_tab"] != body["view_tab"]:
                            changed = True
                        pstate["view_tab"] = body["view_tab"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "role_view": pstate["role_view"], "unit_basis": pstate["unit_basis"]})
                return

            if parsed.path == "/api/ehr/export_csv":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.4 if is_adm else 4.2)
                dl_p = Path("/home/gui/Downloads/ehr_renal_cbc_panel.csv")
                dl_p.parent.mkdir(parents=True, exist_ok=True)
                with lock:
                    ub = pstate["unit_basis"]
                    is_si = (ub == "SI_UMOL_L")
                    lines = ["pt_id,serum_creatinine,anc_k_ul,platelets_k_ul,serum_mg,total_bilirubin,serum_k_mmol_l"]
                    for pt in PATIENTS_TRUTH:
                        pt_id, _sx, _ag, _wt, _ht, _au, _pc, _chf, _cyp, scr_mg, anc, plt, mg_mg, bili_mg, k_v = pt
                        scr_v = round(scr_mg * 88.4, 1) if is_si else round(scr_mg, 2)
                        mg_v = round(mg_mg / 2.43, 3) if is_si else round(mg_mg, 2)
                        bili_v = round(bili_mg * 17.1, 1) if is_si else round(bili_mg, 2)
                        lines.append(f"{pt_id},{scr_v},{anc:.1f},{plt:.0f},{mg_v},{bili_v},{k_v:.1f}")
                    if dl_p.exists():
                        pstate["download_overwrites"] += 1
                    dl_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_p, 0o644)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._send_json(200, {"ok": True, "path": str(dl_p), "unit_basis": ub})
                return

            if parsed.path == "/api/ehr/copy_seal":
                is_adm = (self.headers.get("X-Internal-Admin") == admin_key)
                time.sleep(0.3 if is_adm else 1.5)
                with lock:
                    rv = pstate["role_view"]
                    ub = pstate["unit_basis"]
                    seal = make_opaque_seal("ec02", f"{rv}:{ub}")
                    pstate["clipboard_copies"] += 1
                    persist()
                set_x11_clipboard(seal)
                self._send_json(200, {"ok": True, "role_view": rv, "unit_basis": ub})
                return

            self._send_json(404, {"error": "Unknown endpoint"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(f"http://127.0.0.1:{port}/?sso_boot={boot_secret}\n", encoding="utf-8")
    srv.serve_forever()


def grade(workspace: Path, service_state: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    ow = workspace / "oncology_ward"
    db_p = ow / "pharmacy_dispense.db"
    odt_p = ow / "Cycle4_Infusion_Protocol.odt"
    pdf_a = ow / "Chemo_Dispense_Signoff.pdf"
    pdf_b = ow / "Supportive_Care_Signoff.pdf"

    errs_a: list[str] = []
    errs_b: list[str] = []
    errs_joint: list[str] = []

    chemo_map: dict[str, tuple] = {}
    supp_map: dict[str, tuple] = {}
    if not db_p.is_file():
        errs_a.append("Missing pharmacy_dispense.db")
        errs_b.append("Missing pharmacy_dispense.db")
    else:
        try:
            with sqlite3.connect(str(db_p)) as conn:
                for r in conn.execute("SELECT pt_id, regimen_status, crcl_capped_ml_min, carboplatin_mg, paclitaxel_mg, chemo_diluent_ml FROM chemo_orders"):
                    chemo_map[r[0]] = r[1:]
                for r in conn.execute("SELECT pt_id, regimen_status, mgso4_g, aprepitant_mg, hydration_saline_ml FROM supportive_orders"):
                    supp_map[r[0]] = r[1:]
        except Exception as exc:
            errs_joint.append(f"Corrupted pharmacy_dispense.db: {exc}")

    for pt in PATIENTS_TRUTH:
        ref = compute_patient_reference(pt)
        pid = ref["pt_id"]
        is_hold = (ref["status"] == "HOLD_CYTOPENIA")

        co = chemo_map.get(pid)
        if not co:
            errs_a.append(f"Missing chemo_orders row for {pid}")
        else:
            st_a, crcl_a, carbo_a, pac_a, dil_a = co
            if st_a != ref["status"]:
                errs_a.append(f"{pid} chemo status={st_a} != {ref['status']}")
            if not is_hold and abs(float(crcl_a) - ref["crcl_capped_ml_min"]) > 0.6:
                errs_a.append(f"{pid} crcl={crcl_a} != {ref['crcl_capped_ml_min']}")
            if abs(float(carbo_a) - ref["carboplatin_mg"]) > 2.5:
                errs_a.append(f"{pid} carboplatin={carbo_a} != {ref['carboplatin_mg']}")
            if abs(float(pac_a) - ref["paclitaxel_mg"]) > 2.5:
                errs_a.append(f"{pid} paclitaxel={pac_a} != {ref['paclitaxel_mg']}")
            if is_hold:
                if abs(float(dil_a)) > 0.5:
                    errs_a.append(f"{pid} held patient must have chemo_diluent_ml=0")
            elif not (DILUENT_RANGE_ML[0] <= float(dil_a) <= DILUENT_RANGE_ML[1]):
                errs_a.append(f"{pid} chemo_diluent_ml={dil_a} outside {list(DILUENT_RANGE_ML)}")

        so = supp_map.get(pid)
        if not so:
            errs_b.append(f"Missing supportive_orders row for {pid}")
        else:
            st_b, mg_b, aprep_b, hyd_b = so
            if st_b != ref["status"]:
                errs_b.append(f"{pid} supportive status={st_b} != {ref['status']}")
            if abs(float(mg_b) - ref["mgso4_g"]) > 0.05:
                errs_b.append(f"{pid} mgso4_g={mg_b} != {ref['mgso4_g']}")
            if abs(float(aprep_b) - ref["aprepitant_mg"]) > 0.5:
                errs_b.append(f"{pid} aprepitant_mg={aprep_b} != {ref['aprepitant_mg']}")
            if is_hold:
                if abs(float(hyd_b)) > 0.5:
                    errs_b.append(f"{pid} held patient must have hydration_saline_ml=0")
            elif not (ref["min_hyd_ml"] <= float(hyd_b) <= HYDRATION_RANGE_ML[1]):
                errs_b.append(f"{pid} hydration_saline_ml={hyd_b} outside [{ref['min_hyd_ml']}, {HYDRATION_RANGE_ML[1]}]")

        if co and so and not is_hold and ref["chf_flag"] == 1:
            tot_fl = float(co[4]) + float(so[3])
            if not (CHF_FLUID_BAND_ML[0] <= tot_fl <= CHF_FLUID_BAND_ML[1]):
                errs_joint.append(f"CHF patient {pid} 24h IV fluid={tot_fl} mL outside {list(CHF_FLUID_BAND_ML)}")

    odt_txt = read_odt_plain_text(odt_p)
    if DESK_TAG not in odt_txt:
        errs_joint.append(f"Cycle4_Infusion_Protocol.odt lost live Writer shift session tag {DESK_TAG}")
    if CHEMO_SEAL not in odt_txt:
        errs_a.append("Cycle4_Infusion_Protocol.odt missing valid CHEMO_ATTESTATION_SEAL from clipboard")
    if RENAL_SEAL not in odt_txt:
        errs_b.append("Cycle4_Infusion_Protocol.odt missing valid RENAL_SUPPORT_ATTESTATION_SEAL from clipboard")

    if not (pdf_a.is_file() and pdf_a.stat().st_size > 800):
        errs_a.append("Missing Chemo_Dispense_Signoff.pdf")
    else:
        pa_txt = extract_pdf_text(pdf_a)
        if DESK_TAG not in pa_txt or CHEMO_SEAL not in pa_txt:
            errs_a.append("Chemo_Dispense_Signoff.pdf missing DESK_TAG or CHEMO_ATTESTATION_SEAL")
    if not (pdf_b.is_file() and pdf_b.stat().st_size > 800):
        errs_b.append("Missing Supportive_Care_Signoff.pdf")
    else:
        pb_txt = extract_pdf_text(pdf_b)
        if DESK_TAG not in pb_txt or RENAL_SEAL not in pb_txt:
            errs_b.append("Supportive_Care_Signoff.pdf missing DESK_TAG or RENAL_SUPPORT_ATTESTATION_SEAL")

    if service_state.get("open_gui_split_brain") is True:
        errs_joint.append("Open LibreOffice Writer window held stale unsaved buffer inconsistent with disk .odt")
    extra_files = find_unexpected_workspace_files(ow, ALLOWED_ONC_FILES)
    if extra_files:
        errs_joint.append(f"Unexpected scratch/coordination files in /workspace/oncology_ward: {extra_files[:5]}")

    pass_a = len(errs_a) == 0 and len(errs_joint) == 0
    pass_b = len(errs_b) == 0 and len(errs_joint) == 0
    return {
        "task_id": TASK_ID,
        "pass_a": pass_a,
        "pass_b": pass_b,
        "joint_pass": pass_a and pass_b,
        "errors_a": errs_a[:8],
        "errors_b": errs_b[:8],
        "errors_joint": errs_joint[:8],
        "wall_seconds": round(wall_seconds, 2),
        "prompt_hygiene": verify_prompt_driver_and_ban_clean(build_tickets_by_role()),
        "telemetry": service_state,
    }


def solve_role(role: str, workspace: Path, port: int, careful_conc: bool = False) -> None:
    assert role in ("chemo_regimen_pharmacist", "renal_supportive_pharmacist")
    ow = workspace / "oncology_ward"
    db_p = ow / "pharmacy_dispense.db"
    odt_p = ow / "Cycle4_Infusion_Protocol.odt"
    adm_p = Path("/opt/ec_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}
    base = f"http://127.0.0.1:{port}"

    def _work() -> None:
        flush_open_libreoffice_to_disk(odt_p)
        is_c = (role == "chemo_regimen_pharmacist")
        rv = "CHEMO_CYTOTOXIC" if is_c else "RENAL_SUPPORTIVE"
        ub = "CONV_MG_DL" if is_c else "SI_UMOL_L"

        urllib.request.urlopen(
            urllib.request.Request(
                f"{base}/api/ehr/state",
                data=json.dumps({"role_view": rv, "unit_basis": ub}).encode("utf-8"),
                headers={"Content-Type": "application/json", **adm_hdr},
                method="POST",
            ),
            timeout=10,
        ).read()
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
                    if is_hold:
                        dil = 0.0
                    elif ref["chf_flag"] == 1:
                        tgt_f = 1675.0
                        dil = round(max(DILUENT_RANGE_ML[0], min(DILUENT_RANGE_ML[1], tgt_f - cur_hyd)), 1)
                    else:
                        dil = 600.0
                    conn.execute(
                        "UPDATE chemo_orders SET regimen_status=?, crcl_capped_ml_min=?, carboplatin_mg=?, paclitaxel_mg=?, chemo_diluent_ml=? WHERE pt_id=?",
                        (ref["status"], ref["crcl_capped_ml_min"], ref["carboplatin_mg"], ref["paclitaxel_mg"], dil, pid),
                    )
                else:
                    cur_dil = float(conn.execute("SELECT chemo_diluent_ml FROM chemo_orders WHERE pt_id=?", (pid,)).fetchone()[0])
                    if is_hold:
                        hyd = 0.0
                    elif ref["chf_flag"] == 1:
                        tgt_f = 1675.0
                        hyd = round(max(HYDRATION_RANGE_ML[0], min(HYDRATION_RANGE_ML[1], tgt_f - cur_dil)), 1)
                    else:
                        hyd = max(1000.0, min(1120.0, ref["min_hyd_ml"]))
                    conn.execute(
                        "UPDATE supportive_orders SET regimen_status=?, mgso4_g=?, aprepitant_mg=?, hydration_saline_ml=? WHERE pt_id=?",
                        (ref["status"], ref["mgso4_g"], ref["aprepitant_mg"], hyd, pid),
                    )
            conn.commit()

        cur_txt = read_odt_plain_text(odt_p)
        has_desk = DESK_TAG in cur_txt
        chemo_val = seal_txt if is_c else (CHEMO_SEAL if CHEMO_SEAL in cur_txt else "PENDING_CHEMO_PHARMACIST_SEAL")
        renal_val = seal_txt if (not is_c) else (RENAL_SEAL if RENAL_SEAL in cur_txt else "PENDING_RENAL_PHARMACIST_SEAL")
        paras = []
        if has_desk:
            paras.append(("DESK_SESSION_TAG", DESK_TAG))
        paras.extend([
            ("WARD_HEADER", "Unit: 7-North Inpatient Oncology | Cycle 4 Master Verification"),
            ("CHEMO_ATTESTATION_SEAL", chemo_val),
            ("RENAL_SUPPORT_ATTESTATION_SEAL", renal_val),
        ])
        write_simple_odt(odt_p, "Cycle-4 Inpatient Oncology Infusion Master Protocol", paras)
        reload_open_libreoffice_window(odt_p)
        convert_doc_to_pdf_isolated(odt_p, ow / ("Chemo_Dispense_Signoff.pdf" if is_c else "Supportive_Care_Signoff.pdf"))

    if careful_conc:
        with advisory_lock(TASK_ID):
            _work()
    else:
        _work()


def simulate_naive_race(workspace: Path, port: int) -> None:
    ow = workspace / "oncology_ward"
    db_p = ow / "pharmacy_dispense.db"
    solve_role("chemo_regimen_pharmacist", workspace, port, careful_conc=False)
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute("UPDATE supportive_orders SET hydration_saline_ml=1150.0 WHERE pt_id='PT-01'")
        conn.commit()
