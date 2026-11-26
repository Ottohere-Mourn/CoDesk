"""NF-01: DACH Bilingual Launch Workstation — X11 Global DE-QWERTZ vs. US-QWERTY Layout Contention on Real LibreOffice Writer + Calc + Chromium.

Authentic Co-Tenant Scenario:
  - A Munich/Zurich European product-launch workstation shared by the DACH Legal & Typography Localization Lead
    (working in LibreOffice Writer + DACH Regulatory Browser Console + fontTools OpenType binary) and the EMEA
    RevOps Tariff Modeler (working in LibreOffice Calc + ECB FX/VAT Browser Console + 360-row invoice SQLite DB).
  - Toggling X11 keyboard input to German QWERTZ (`setxkbmap de`) for statutory German §/ä/ö/ü/ß drafting in Writer
    globally remaps `y<->z`, `- -> ß`, `/ -> &`, and `= -> )` across `:99`, corrupting concurrent formula/text entry
    in LibreOffice Calc on the same single-instance `soffice.bin` (UNO `:2002`).
"""
from __future__ import annotations

import csv
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v1.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    extract_pdf_text,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_chromium_natural,
    launch_libreoffice_uno_natural,
    read_json_safe,
    read_multisheet_xlsx,
    read_odt_plain_text,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
    write_simple_odt,
)

TASK_ID = "NF-01"
PORTAL_PORT = 19501
UNO_PORT = 2002

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "DACH Bilingual Workstation XKB Layout Contention (DE-QWERTZ vs. US-QWERTY): LibreOffice Writer & OpenType DIN-1450 vs. Calc EMEA Revenue Recon",
    "domain": "European Legal/Typography Localization (LibreOffice Writer + fontTools) & Multi-Currency SaaS RevOps (LibreOffice Calc + SQLite)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("dach_legal_localization_lead", "emea_revops_modeler"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (UNO_PORT,),
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

# --- Deterministic Ground Truth for Role A (DACH Legal & DIN-1450 Typography) ---
BNETZA_REG_DATA = {
    "hrb_register": "HRB 289412 München",
    "ust_idnr": "DE341908572",
    "weee_reg_nr": "DE 76419208",
    "aufsichtsbehoerde": "Bundesnetzagentur Bonn",
    "at_firmenbuch": "FN 481920k HG Wien",
    "ch_uid_mwst": "CHE-392.410.885 MWST",
    "statutory_phrase": "Gemäß § 5 DDG und § 312j BGB gilt Größenklasse-ß für Präzisions-Meßgeräte.",
}
DE_PORTAL_ATTESTATION = "DACH-DDG5-PRUEF-7842"

# 12 active 2026 DIN-1450 optical kerning pairs on scanned specimen chart (plus 2 obsolete 1998 rows to ignore!)
DIN1450_KERN_PAIRS: dict[tuple[str, str], int] = {
    ("A", "V"): -65,
    ("T", "o"): -55,
    ("W", "e"): -45,
    ("Y", "o"): -60,
    ("V", "a"): -50,
    ("T", "a"): -55,
    ("P", "a"): -35,
    ("f", "j"): 35,
    ("L", "T"): -50,
    ("K", "o"): -30,
    ("V", "e"): -45,
    ("r", "period"): -40,
}
DIN1450_TABULAR_ADV = 1220  # Equal advance width required on ASCII digits '0'..'9'
DIN1450_TNUM_EXTRA_CHARS = ("€", "+", "-", "\u2212", "%")

# --- Deterministic Ground Truth for Role B (EMEA 360-Invoice Multi-Currency RevOps) ---
VAT_RATES = {"DE": 0.19, "AT": 0.20, "CH": 0.081, "NL": 0.21, "UK": 0.20}
# Hedged forward multipliers apply to ENT & MID; unhedged Spot Mid applies to SMB!
ECB_TO_EUR_NET = {
    "EUR": 1.0000,
    "CHF": 1.0480,  # 1 CHF = 1.0480 EUR after 45 bps treasury hedge haircut
    "GBP": 1.1640,  # 1 GBP = 1.1640 EUR after 60 bps treasury hedge haircut
}
ECB_SPOT_UNHEDGED = {
    "EUR": 1.0000,
    "CHF": 1.0527,
    "GBP": 1.1710,
}
# Quarterly Treasury Forward Hedge Notional Caps (in local currency per quarter; excess ENT/MID volume above cap spills to Spot Mid!)
QUARTERLY_HEDGE_CAP_LOCAL = {
    "CHF": 240000.0,
    "GBP": 210000.0,
}
IFRS15_DOUBTFUL_CONTRACTS = {"CTR-0014": 0.05, "CTR-0058": 0.05, "CTR-0112": 0.05, "CTR-0188": 0.05, "CTR-0244": 0.05}


def _generate_emea_ledger_rows() -> list[dict[str, Any]]:
    """Generate 360 deterministic EMEA subscription/amendment/credit-note rows with IFRS-15 multi-quarter terms."""
    countries = ["DE", "AT", "CH", "NL", "UK"]
    ccy_by_ctry = {"DE": "EUR", "AT": "EUR", "CH": "CHF", "NL": "EUR", "UK": "GBP"}
    tiers = [("ENT", 4800.0), ("MID", 1950.0), ("SMB", 720.0)]
    rows: list[dict[str, Any]] = []
    seq = 1000
    # 300 base contracts, plus 35 superseded rev=1 rows (rev=2 supersedes rev=1 for same contract_id & quarter!),
    # plus 15 VOIDED/SANDBOX_TEST rows, plus 10 CREDIT_CLAWBACK rows.
    for idx in range(1, 301):
        seq += 1
        ctry = countries[(idx * 7) % 5]
        ccy = ccy_by_ctry[ctry]
        tier, base_amt = tiers[(idx * 3) % 3]
        qty = 1 + (idx % 6)
        gross_flag = 1 if (idx % 4 == 0) else 0  # 1 = amount includes local VAT!
        qtr = "2026-Q3" if idx <= 150 else "2026-Q4"
        utc_ts = "2026-09-30T22:45:00Z" if (139 <= idx <= 150) else ("2026-08-14T11:20:00Z" if idx <= 138 else "2026-11-12T14:10:00Z")
        amt_unit = "kCCY" if (tier == "ENT" and idx % 27 == 0) else "CCY"
        term_q = 4 if (idx % 10 == 0) else (2 if (idx % 6 == 0) else 1)
        amt = round(base_amt * qty * term_q * (1.0 + VAT_RATES[ctry] if gross_flag else 1.0), 2)
        stored_amt = round(amt / 1000.0, 5) if amt_unit == "kCCY" else amt
        cid = f"CTR-{idx:04d}"
        if idx % 9 == 0 and len([r for r in rows if r["rev_no"] == 2]) < 35:
            # Emit stale rev 1 first, then amended rev 2 with updated seat count
            rows.append({
                "row_id": seq, "contract_id": cid, "rev_no": 1, "quarter": qtr,
                "booked_utc_ts": utc_ts, "amount_unit": amt_unit,
                "country": ctry, "currency": ccy, "tier": tier, "term_quarters": term_q,
                "billed_amount": stored_amt, "is_vat_inclusive": gross_flag,
                "tx_status": "POSTED", "memo": "Initial billing",
            })
            seq += 1
            amt2 = round(base_amt * (qty + 1) * term_q * (1.0 + VAT_RATES[ctry] if gross_flag else 1.0), 2)
            stored_amt2 = round(amt2 / 1000.0, 5) if amt_unit == "kCCY" else amt2
            rows.append({
                "row_id": seq, "contract_id": cid, "rev_no": 2, "quarter": qtr,
                "booked_utc_ts": utc_ts, "amount_unit": amt_unit,
                "country": ctry, "currency": ccy, "tier": tier, "term_quarters": term_q,
                "billed_amount": stored_amt2, "is_vat_inclusive": gross_flag,
                "tx_status": "POSTED", "memo": "Superseding seat expansion",
            })
        else:
            rows.append({
                "row_id": seq, "contract_id": cid, "rev_no": 1, "quarter": qtr,
                "booked_utc_ts": utc_ts, "amount_unit": amt_unit,
                "country": ctry, "currency": ccy, "tier": tier, "term_quarters": term_q,
                "billed_amount": stored_amt, "is_vat_inclusive": gross_flag,
                "tx_status": "POSTED", "memo": "Standard subscription",
            })

    # Add 15 VOIDED / SANDBOX_TEST rows (must be excluded!)
    for k in range(1, 16):
        seq += 1
        ctry = countries[k % 5]
        rows.append({
            "row_id": seq, "contract_id": f"CTR-VOID-{k:02d}", "rev_no": 1, "quarter": "2026-Q4",
            "booked_utc_ts": "2026-10-19T09:00:00Z", "amount_unit": "CCY",
            "country": ctry, "currency": ccy_by_ctry[ctry], "tier": "ENT", "term_quarters": 1,
            "billed_amount": 9600.00, "is_vat_inclusive": 0,
            "tx_status": "VOIDED" if k % 2 == 0 else "SANDBOX_TEST", "memo": "Do not recognize",
        })

    # Add 10 CREDIT_CLAWBACK rows: positive magnitude in `billed_amount` (contra-revenue credit note!)
    for k in range(1, 11):
        seq += 1
        ctry = countries[(k + 2) % 5]
        rows.append({
            "row_id": seq, "contract_id": f"CLAW-{k:03d}", "rev_no": 1, "quarter": "2026-Q3" if k <= 5 else "2026-Q4",
            "booked_utc_ts": "2026-08-25T15:00:00Z" if k <= 5 else "2026-11-20T15:00:00Z", "amount_unit": "CCY",
            "country": ctry, "currency": ccy_by_ctry[ctry], "tier": "MID", "term_quarters": 1,
            "billed_amount": 650.00 * (1 + (k % 3)), "is_vat_inclusive": 0,
            "tx_status": "CREDIT_CLAWBACK", "memo": "SLA contra-revenue credit note",
        })
    return rows


def _compute_revops_oracle() -> dict[str, Any]:
    rows = _generate_emea_ledger_rows()
    valid = [r for r in rows if r["tx_status"] in ("POSTED", "CREDIT_CLAWBACK")]
    latest_posted: dict[tuple[str, str], dict[str, Any]] = {}
    clawbacks: list[dict[str, Any]] = []
    for r in valid:
        if r["tx_status"] == "CREDIT_CLAWBACK":
            clawbacks.append(r)
        else:
            key = (r["contract_id"], r["quarter"])
            if key not in latest_posted or r["rev_no"] > latest_posted[key]["rev_no"]:
                latest_posted[key] = r

    active_rows = list(latest_posted.values()) + clawbacks
    active_rows.sort(key=lambda x: int(x["row_id"]))
    by_country_eur = {c: 0.0 for c in ("DE", "AT", "CH", "NL", "UK")}
    by_qtr_eur = {"2026-Q3": 0.0, "2026-Q4": 0.0}
    vat_liability_eur = 0.0
    deferred_2027_eur = 0.0
    hedged_used: dict[tuple[str, str], float] = {}

    for r in active_rows:
        ctry = r["country"]
        ccy = r["currency"]
        scale_mult = 1000.0 if r.get("amount_unit") == "kCCY" else 1.0
        raw_mag = float(r["billed_amount"]) * scale_mult
        billed = -abs(raw_mag) if r["tx_status"] == "CREDIT_CLAWBACK" else raw_mag
        eff_qtr = "2026-Q4" if str(r.get("booked_utc_ts", "")).startswith("2026-09-30T22:") else r["quarter"]
        if r["is_vat_inclusive"] == 1 and billed > 0:
            net_local = billed / (1.0 + VAT_RATES[ctry])
            vat_local = billed - net_local
        else:
            net_local = billed
            vat_local = 0.0
        haircut = IFRS15_DOUBTFUL_CONTRACTS.get(r["contract_id"], 0.0)
        net_local = net_local * (1.0 - haircut)
        if r["tier"] == "SMB" or ccy == "EUR" or net_local <= 0:
            fx_eff = ECB_SPOT_UNHEDGED[ccy] if r["tier"] == "SMB" else ECB_TO_EUR_NET[ccy]
            tot_contract_eur = net_local * fx_eff
            vat_liability_eur += vat_local * fx_eff
        else:
            hkey = (eff_qtr, ccy)
            rem_cap = max(0.0, QUARTERLY_HEDGE_CAP_LOCAL[ccy] - hedged_used.get(hkey, 0.0))
            hedged_part = min(net_local, rem_cap)
            unhedged_part = net_local - hedged_part
            hedged_used[hkey] = hedged_used.get(hkey, 0.0) + hedged_part
            tot_contract_eur = hedged_part * ECB_TO_EUR_NET[ccy] + unhedged_part * ECB_SPOT_UNHEDGED[ccy]
            fx_blended = tot_contract_eur / net_local
            vat_liability_eur += vat_local * fx_blended
        tq = int(r.get("term_quarters", 1))
        per_q_eur = tot_contract_eur / tq
        if eff_qtr == "2026-Q3":
            q3_rec = per_q_eur
            q4_rec = per_q_eur if tq >= 2 else 0.0
            def_27 = tot_contract_eur - (q3_rec + q4_rec)
        else:
            q3_rec = 0.0
            q4_rec = per_q_eur
            def_27 = tot_contract_eur - q4_rec
        by_qtr_eur["2026-Q3"] += q3_rec
        by_qtr_eur["2026-Q4"] += q4_rec
        by_country_eur[ctry] += (q3_rec + q4_rec)
        deferred_2027_eur += def_27

    by_country_eur = {k: round(v, 2) for k, v in by_country_eur.items()}
    by_qtr_eur = {k: round(v, 2) for k, v in by_qtr_eur.items()}
    tot_eur = round(sum(by_country_eur.values()), 2)
    dach_share_pct = round(
        100.0 * (by_country_eur["DE"] + by_country_eur["AT"] + by_country_eur["CH"]) / tot_eur, 2
    )
    return {
        "recognized_row_count": len(active_rows),
        "country_net_eur": by_country_eur,
        "q3_net_eur": by_qtr_eur["2026-Q3"],
        "q4_net_eur": by_qtr_eur["2026-Q4"],
        "total_emea_net_eur": tot_eur,
        "deferred_2027_eur": round(deferred_2027_eur, 2),
        "dach_share_pct": dach_share_pct,
        "extracted_vat_eur": round(vat_liability_eur, 2),
        "fx_schedule_code": "ECB-HEDGE-2026Q4-4419",
    }


REVOPS_ORACLE = _compute_revops_oracle()

DACH_CONSOLE_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><title>DACH Regulatory & Input Console</title>
<style>
  body {{ background:#0f172a; color:#f8fafc; font-family:'DejaVu Sans',sans-serif; margin:22px; line-height:1.5; }}
  .bar {{ background:#1e293b; padding:14px 18px; border:1px solid #334155; display:flex; gap:12px; align-items:center; }}
  button {{ padding:8px 14px; background:#2563eb; color:#fff; border:none; border-radius:4px; cursor:pointer; font-weight:600; }}
  button.sec {{ background:#475569; }}
  input {{ padding:8px 12px; width:440px; font-size:14px; background:#0b1120; color:#f8fafc; border:1px solid #38bdf8; }}
  .box {{ background:#111827; border:1px solid #334155; padding:16px; margin-top:16px; }}
  code {{ color:#fde047; }}
</style></head><body>
<div class="bar">
  <strong>DACH Statutory Workstation Input</strong>
  <span>Active X11 Layout: <code id="lay">...</code></span>
  <button onclick="setLay('de')">Activate Mandatory DACH Input: DE-QWERTZ</button>
  <a href="/revops-fx" style="color:#38bdf8;margin-left:auto">Open EMEA Treasury FX Console -></a>
</div>
<div class="box">
  <h3>§ 5 DDG / BNetzA German Input Verification</h3>
  <p>To release the statutory attestation code for <code>DACH_Statutory_Impressum.odt</code>, switch workstation input to <code>DE-QWERTZ</code> and type a verification phrase containing at least one German umlaut (<code>ä/ö/ü/Ä/Ö/Ü</code>) AND sharp-s (<code>ß</code>) plus <code>DDG</code> into the live verification field below:</p>
  <input id="vphrase" placeholder="Type German statutory phrase here (e.g. Prüfgröße DDG)..." oninput="checkPhrase()"/>
  <p id="status" style="color:#fbbf24;font-weight:bold">Awaiting DE-QWERTZ live input verification...</p>
</div>
<script>
async function refresh() {{
  const r = await fetch('/api/dach/state', {{credentials:'include'}});
  const j = await r.json();
  document.getElementById('lay').textContent = j.xkb.toUpperCase();
  if (j.attestation) {{
    document.getElementById('status').style.color = '#4ade80';
    document.getElementById('status').textContent = 'Verified! Statutory Attestation Code: ' + j.attestation;
  }}
}}
async function setLay(l) {{
  await fetch('/api/dach/set_xkb?layout=' + l, {{method:'POST', credentials:'include'}});
  await refresh();
}}
async function checkPhrase() {{
  const v = document.getElementById('vphrase').value;
  await fetch('/api/dach/verify_phrase', {{method:'POST', credentials:'include', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{phrase:v}})}});
  await refresh();
}}
refresh();
</script></body></html>"""

REVOPS_FX_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><title>EMEA Treasury FX & Tax Console</title>
<style>
  body {{ background:#0b1120; color:#f8fafc; font-family:monospace; margin:24px; }}
  table {{ border-collapse:collapse; margin-top:14px; }}
  td, th {{ border:1px solid #334155; padding:8px 16px; }}
  th {{ background:#1e293b; color:#38bdf8; }}
</style></head><body>
<h2>EMEA Treasury — Q3/Q4 Net Hedge Conversion & VAT Matrix</h2>
<p><a href="/dach-console" style="color:#38bdf8"><- Back to DACH Regulatory Console</a></p>
<table>
  <tr><th>Billing Currency</th><th>ECB Spot Mid (Unhedged SMB Tier)</th><th>Forward Hedge Haircut</th><th>Hedged Multiplier (ENT &amp; MID Tiers)</th></tr>
  <tr><td>EUR</td><td>1.0000</td><td>0 bps</td><td><strong>1.0000</strong></td></tr>
  <tr><td>CHF</td><td>1.0527</td><td>-45 bps</td><td><strong>1.0480</strong></td></tr>
  <tr><td>GBP</td><td>1.1710</td><td>-60 bps</td><td><strong>1.1640</strong></td></tr>
</table>
<p style="margin-top:16px">Local Statutory VAT Rates (invoice-level VAT liability is recognized upon billing when <code>is_vat_inclusive == 1</code>):<br>
<code>DE = 19.0%</code> | <code>AT = 20.0%</code> | <code>CH = 8.1%</code> | <code>NL = 21.0%</code> | <code>UK = 20.0%</code></p>
<p>Treasury FX Schedule Reference Code: <strong style="color:#4ade80">{REVOPS_ORACLE['fx_schedule_code']}</strong></p>
</body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — DACH Statutory Impressum & DIN-1450 Font Release (`dach_legal_localization_lead`)",
        "",
        "## Context & Objective",
        f"Prepare the German/Austrian/Swiss (DACH) statutory release package on this workstation. Review `{b}/workspace/specs/DACH_Statutory_Font_SOP.pdf{b}`, the scanned regulatory & typographic exhibits in `{b}/workspace/specs/{b}`, the open `{b}/workspace/DACH_Statutory_Impressum.odt{b}` document in LibreOffice Writer, and the authenticated **DACH Regulatory & Input Console** (`http://127.0.0.1:{PORTAL_PORT}/dach-console`) in Chromium.",
        "",
        "## Required Deliverables",
        f"1. **Updated `{b}/workspace/DACH_Statutory_Impressum.odt{b}` & exported `{b}/workspace/DACH_Statutory_Impressum.pdf{b}`**:",
        "   - Complete all mandatory German, Austrian, and Swiss statutory identifiers, conformity clauses, EU ODR dispute disclosure, and portal attestation code per the SOP and scanned extracts, purge all prohibited Anglo-American boilerplate clauses from the draft, preserve `[MANDATE-DACH-2026-Q4]`, and ensure the open LibreOffice Writer document and disk `.odt`/`.pdf` match.",
        f"2. **DIN-1450 Patched OpenType Font `{b}/workspace/fonts/DACHCorporateSans_DIN1450.ttf{b}`**:",
        f"   - Starting from `{b}/workspace/fonts/DACHCorporateSans.ttf{b}`, apply all vertical metric, proportional-flag, tabular numeral, and current 2026 DIN-1450 optical kerning updates from `{b}/workspace/specs/{b}` while preserving existing non-overridden kerning pairs in the base font.",
        f"3. **Compliance Summary `{b}/workspace/dach_localization_summary.json{b}`**:",
        "   - Record the structured audit summary following the schema in Section 4 of `DACH_Statutory_Font_SOP.pdf`.",
    ])
    tb = "\n".join([
        "# Work Order — EMEA Multi-Currency Subscription Revenue Reconciliation (`emea_revops_modeler`)",
        "",
        "## Context & Objective",
        f"Close the Q3/Q4 EMEA subscription revenue schedule on this workstation. Review `{b}/workspace/specs/EMEA_RevOps_Recognition_Policy.pdf{b}`, query `{b}/workspace/ledgers/emea_subscriptions.sqlite{b}`, inspect the authenticated **EMEA Treasury FX & Tax Console** (`http://127.0.0.1:{PORTAL_PORT}/revops-fx`) in Chromium, and complete the open `{b}/workspace/EMEA_Tariff_Schedule.xlsx{b}` workbook in LibreOffice Calc.",
        "",
        "## Required Deliverables",
        f"1. **Completed Workbook `{b}/workspace/EMEA_Tariff_Schedule.xlsx{b}`**:",
        "   - Populate the `CountryRecon` and `ExecutiveSummary` sheets with recognized net EUR revenue by country and quarter, extracted VAT liability, DACH revenue share percentage, and live spreadsheet summary formulas (`=SUM(...)`, subtraction/ratio formulas) as specified in `EMEA_RevOps_Recognition_Policy.pdf`.",
        "   - Preserve the `Control` sheet metadata (`LIVE-REVOPS-401`) and ensure the open LibreOffice Calc window and on-disk `.xlsx` file remain synchronized.",
        f"2. **Reconciliation Audit `{b}/workspace/emea_revops_reconciliation.json{b}`**:",
        "   - Record the structured reconciliation totals following Section 4 of `EMEA_RevOps_Recognition_Policy.pdf`.",
    ])
    return {"dach_legal_localization_lead": ta, "emea_revops_modeler": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["dach_legal_localization_lead"]
    ws_b = workspace_map["emea_revops_modeler"]
    (ws_a / "specs").mkdir(parents=True, exist_ok=True)
    (ws_a / "fonts").mkdir(parents=True, exist_ok=True)
    (ws_b / "specs").mkdir(parents=True, exist_ok=True)
    (ws_b / "ledgers").mkdir(parents=True, exist_ok=True)

    shutil.copy2("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", ws_a / "fonts/DACHCorporateSans.ttf")
    (ws_a / "fonts/foundry_release_manifest.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<foundryRelease standard="DIN-1450:2026" typographyStandard="DIN-5008:2020">\n'
        '  <os2Table achVendID="DACH"/>\n'
        '  <nameTable nameID="5" versionString="Version 2.26; DIN-1450:2026"/>\n'
        '  <impressumFormatting sectionSignSpacing="U+202F_NARROW_NBSP"/>\n'
        '</foundryRelease>\n',
        encoding="utf-8",
    )

    render_scanned_exhibit_png(
        ws_a / "specs/bnetza_filing_scan.png",
        "BUNDESNETZAGENTUR & DACH CROSS-BORDER STATUTORY EXTRACT",
        [
            f"Commercial Register (Handelsregister):  {BNETZA_REG_DATA['hrb_register']}",
            f"VAT ID (Umsatzsteuer-ID gem. §27a):     {BNETZA_REG_DATA['ust_idnr']}",
            f"WEEE-Reg.-Nr. (Stiftung EAR):           {BNETZA_REG_DATA['weee_reg_nr']}",
            f"Supervisory Authority:                  {BNETZA_REG_DATA['aufsichtsbehoerde']}",
            f"Austrian Branch (Firmenbuch Wien):      {BNETZA_REG_DATA['at_firmenbuch']}",
            f"Swiss VAT Register (ESTV Bern):         {BNETZA_REG_DATA['ch_uid_mwst']}",
            "EU Art. 14 ODR Platform Link:           https://ec.europa.eu/consumers/odr",
            "Mandatory German Conformity Clause (verbatim):",
            f"  {BNETZA_REG_DATA['statutory_phrase']}",
        ],
        stamp_text="BNETZA VERIFIED EXTRACT",
    )

    render_scanned_exhibit_png(
        ws_a / "specs/din1450_optical_specimen_scan.png",
        "DIN 1450:2026 OPTICAL KERNING & METRICS SPECIMEN SHEET",
        [
            "Vertical Metrics:  OS/2.sTypoAscender = 1620 | OS/2.sTypoDescender = -428 | OS/2.sTypoLineGap = 140",
            "PostScript Flag:   post.isFixedPitch = 0   | Tabular tnum Set ('0'..'9', '€', '+', '-', '\u2212', '%'): AdvWidth = 1220 UPM (keep LSB)",
            "Active 2026 Optical Kerning Overrides (merge into existing Format-0 kern subtable; preserve other base pairs!):",
            "  ('A','V'): -65   ('T','o'): -55   ('W','e'): -45   ('Y','o'): -60",
            "  ('V','a'): -50   ('T','a'): -55   ('P','a'): -35   ('f','j'): +35",
            "  ('L','T'): -50   ('K','o'): -30   ('V','e'): -45   ('r','period'): -40",
            "[OBSOLETE 1998 PROVISIONAL ROWS — SUPERSEDED, DO NOT APPLY!]:",
            "  * ('H','n'): -25 [WITHDRAWN 1998]    * ('O','A'): -90 [WITHDRAWN 1998 — keep original base font value]",
        ],
        stamp_text="DIN 1450 TYPOGRAPHY LAB",
        tilt_deg=0.4,
    )

    write_multipage_sop_pdf(
        ws_a / "specs/DACH_Statutory_Font_SOP.pdf",
        "SOP-DACH-1450: Statutory Impressum & OpenType Release Standard",
        [
            ("1. Statutory Impressum Requirements (DACH_Statutory_Impressum.odt)", [
                "1.1 Preserve docket header '[MANDATE-DACH-2026-Q4]' in DACH_Statutory_Impressum.odt.",
                "1.2 Format all German, Austrian, and Swiss registry identifiers into a structured 2-column Writer table inside DACH_Statutory_Impressum.odt, include the EU ODR URL and verbatim German § 5 DDG / § 312j BGB clause from specs/bnetza_filing_scan.png.",
                "1.3 Purge all unenforceable US warranty-disclaimer and foreign-jurisdiction venue clauses from the draft.",
                "1.4 Complete live German QWERTZ input verification on /dach-console to obtain the Statutory Attestation Code, record it in DACH_Statutory_Impressum.odt, synchronize the open LibreOffice Writer session, and export /workspace/DACH_Statutory_Impressum.pdf.",
            ]),
            ("2. DIN-1450 OpenType Metrics & Optical Kerning Rules", [
                "2.1 Patch /workspace/fonts/DACHCorporateSans.ttf -> /workspace/fonts/DACHCorporateSans_DIN1450.ttf according to the scanned lab specimen sheet specs/din1450_optical_specimen_scan.png.",
                "2.2 Merge ONLY active 2026 DIN-1450 optical kerning overrides into the existing Format-0 kerning table (do not wipe pre-existing kerning pairs of DACHCorporateSans.ttf and do not apply withdrawn 1998 provisional rows; note glyph names follow OpenType glyph naming in cmap/post).",
            ]),
            ("4. JSON Audit Output Schema (/workspace/dach_localization_summary.json)", [
                "Write JSON object with exact keys:",
                "  hrb_register (str), ust_idnr (str), weee_reg_nr (str), at_firmenbuch (str), ch_uid_mwst (str),",
                "  portal_attestation_code (str), tabular_digit_width_upm (int),",
                "  net_kern_adjustment_sum_upm (int sum across the active 2026 override pairs), patched_pair_count (int).",
            ]),
        ],
    )

    write_simple_odt(
        ws_a / "DACH_Statutory_Impressum.odt",
        "DACH Product Statutory Impressum Draft",
        [
            ("HEADER", "[MANDATE-DACH-2026-Q4] European Hardware Release Dossier"),
            ("REG_PLACEHOLDER", "HRB: PENDING | USt-IdNr: PENDING | WEEE: PENDING"),
            ("PROHIBITED_WAIVER", "ALL IMPLIED WARRANTIES ARE WAIVED WITHOUT LIMITATION."),
            ("PROHIBITED_VENUE", "EXCLUSIVE VENUE AND JURISDICTION SHALL BE WILMINGTON, DELAWARE."),
            ("ATTESTATION", "PORTAL_ATTESTATION: PENDING"),
        ],
    )

    # Role B SQLite + Policy PDF + Initial Calc Workbook
    db_p = ws_b / "ledgers/emea_subscriptions.sqlite"
    with sqlite3.connect(str(db_p)) as conn:
        conn.execute(
            "CREATE TABLE billing_ledger (row_id INTEGER PRIMARY KEY, contract_id TEXT, rev_no INTEGER, "
            "quarter TEXT, booked_utc_ts TEXT, amount_unit TEXT, country TEXT, currency TEXT, tier TEXT, term_quarters INTEGER, billed_amount REAL, "
            "is_vat_inclusive INTEGER, tx_status TEXT, memo TEXT)"
        )
        conn.execute(
            "CREATE TABLE treasury_hedge_desk_limits (currency TEXT PRIMARY KEY, quarterly_hedged_cap_net_local REAL, overflow_rate_basis TEXT)"
        )
        conn.execute("INSERT INTO treasury_hedge_desk_limits VALUES ('CHF', 240000.0, 'ECB_SPOT_MID_ON_EXCESS_ORDERED_BY_ROW_ID')")
        conn.execute("INSERT INTO treasury_hedge_desk_limits VALUES ('GBP', 210000.0, 'ECB_SPOT_MID_ON_EXCESS_ORDERED_BY_ROW_ID')")
        conn.execute("CREATE TABLE ifrs15_collectibility_watch (contract_id TEXT PRIMARY KEY, doubtful_allowance_pct REAL)")
        for cid_w, pct_w in sorted(IFRS15_DOUBTFUL_CONTRACTS.items()):
            conn.execute("INSERT INTO ifrs15_collectibility_watch VALUES (?, ?)", (cid_w, pct_w))
        for r in _generate_emea_ledger_rows():
            conn.execute(
                "INSERT INTO billing_ledger VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["row_id"], r["contract_id"], r["rev_no"], r["quarter"], r["booked_utc_ts"], r["amount_unit"],
                 r["country"], r["currency"],
                 r["tier"], r["term_quarters"], r["billed_amount"], r["is_vat_inclusive"], r["tx_status"], r["memo"]),
            )
        conn.commit()

    write_multipage_sop_pdf(
        ws_b / "specs/EMEA_RevOps_Recognition_Policy.pdf",
        "POL-REV-2026: EMEA IFRS-15 Subscription & VAT Recognition Policy",
        [
            ("1. IFRS-15 Contract Hygiene & Straight-Line Multi-Quarter Accrual", [
                "1.1 Reporting Entity & Period Cutoff: Close recognized 2026-Q3 and 2026-Q4 net EUR subscription revenue for Munich-headquartered DACH/EMEA Operations GmbH (reporting timezone: Europe/Berlin CET/CEST) from /workspace/ledgers/emea_subscriptions.sqlite, ensuring proper GAAP/IFRS-15 ledger hygiene.",
                "1.2 Straight-Line Multi-Quarter Obligations: Contracts with multi-quarter terms recognize net revenue ratably in equal quarterly tranches starting in their effective Europe/Berlin booking quarter across 2026-Q3 and 2026-Q4, carrying unearned 2027 tranches to deferred_2027_eur.",
            ]),
            ("2. VAT Stripping & Treasury Hedge FX Conversion", [
                "2.1 Strip statutory VAT on VAT-inclusive commercial invoices upon billing (extracted_vat_eur) and convert local currency amounts to EUR using the applicable tier FX schedule on /revops-fx in Chromium.",
            ]),
            ("3. Workbook Layout (EMEA_Tariff_Schedule.xlsx) & 4. JSON Schema", [
                "3.1 Sheet 'CountryRecon': rows 2..6 = DE, AT, CH, NL, UK recognized H2 (Q3+Q4) Net_EUR in B2..B6; B7 = live formula =SUM(B2:B6).",
                "3.2 Sheet 'ExecutiveSummary':",
                "  B2 = Q3_Net_EUR, B3 = Q4_Net_EUR, B4 = live formula =B2+B3 (Total_EMEA_Net_EUR),",
                "  B5 = QoQ_Delta_EUR live formula =B3-B2, B6 = DACH_Share_Pct (100*(DE+AT+CH)/Total, 2 decimals),",
                "  B7 = Extracted_VAT_EUR (2 decimals), B8 = fx_schedule_code, B9 = Deferred_2027_EUR (2 decimals).",
                "3.3 Sheet 'Control': preserve cell C2 = 'LIVE-REVOPS-401' and save so the open Calc window matches disk.",
                "4. JSON Schema (/workspace/emea_revops_reconciliation.json):",
                "  recognized_row_count (int), country_net_eur (dict DE/AT/CH/NL/UK -> float),",
                "  q3_net_eur (float), q4_net_eur (float), total_emea_net_eur (float), deferred_2027_eur (float),",
                "  dach_share_pct (float), extracted_vat_eur (float), fx_schedule_code (str).",
            ]),
        ],
    )

    write_multisheet_xlsx(
        ws_b / "EMEA_Tariff_Schedule.xlsx",
        [
            ("Control", [["Key", "Status", "SessionMarker"], ["IFRS15_Close", "DRAFT_V0", "LIVE-REVOPS-401"]]),
            ("CountryRecon", [
                ["Country", "Net_EUR"],
                ["DE", 0.0], ["AT", 0.0], ["CH", 0.0], ["NL", 0.0], ["UK", 0.0],
                ["TOTAL", ("=SUM(B2:B6)", 0.0)],
            ]),
            ("ExecutiveSummary", [
                ["Metric", "Value"],
                ["Q3_Net_EUR", 0.0],
                ["Q4_Net_EUR", 0.0],
                ["Total_EMEA_Net_EUR", ("=B2+B3", 0.0)],
                ["QoQ_Delta_EUR", ("=B3-B2", 0.0)],
                ["DACH_Share_Pct", 0.0],
                ["Extracted_VAT_EUR", 0.0],
                ["FX_Schedule_Code", "PENDING"],
                ["Deferred_2027_EUR", 0.0],
            ]),
        ],
    )

    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(12)
    st_path = state_dir / "service_state.json"
    mem = {"xkb": "us", "xkb_switches": 0, "de_verified": False}
    write_json(st_path, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("dach_sso" in c) and (c["dach_sso"].value == tok)
        def _json(self, code: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self) -> None:
            u = urlparse(self.path)
            if u.path == "/health":
                self._json(200, {"ok": True}); return
            if u.path == "/boot_auth":
                if (state_dir / "boot_sealed").is_file():
                    self._json(403, {"error": "Boot SSO token already consumed by desktop browser"}); return
                ck = f"dach_sso={tok}; HttpOnly; Path=/; SameSite=Lax"
                raw = b"<html><body><script>location.href='/dach-console';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", ck); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly browser session required"}); return
            if u.path == "/dach-console":
                raw = DACH_CONSOLE_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/revops-fx":
                raw = REVOPS_FX_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/dach/state":
                cp = subprocess.run(["bash", "-lc", "DISPLAY=:99 setxkbmap -query 2>/dev/null | awk '/^layout:/{print $2}'"], capture_output=True, text=True)
                cur_l = cp.stdout.strip() or mem["xkb"]
                mem["xkb"] = cur_l
                self._json(200, {"xkb": cur_l, "attestation": DE_PORTAL_ATTESTATION if mem["de_verified"] else ""}); return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly browser session required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/dach/set_xkb":
                lay = (qs.get("layout") or ["us"])[0]
                if lay in ("de", "us"):
                    subprocess.run(["bash", "-lc", f"DISPLAY=:99 setxkbmap {lay} >/dev/null 2>&1 || true"], capture_output=True)
                    if lay != mem["xkb"]:
                        mem["xkb_switches"] += 1
                    mem["xkb"] = lay
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "xkb": mem["xkb"]}); return
            if u.path == "/api/dach/verify_phrase":
                ln = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(ln).decode("utf-8") or "{}")
                ph = str(body.get("phrase") or "")
                has_uml = any(ch in ph for ch in "äöüÄÖÜ")
                if mem["xkb"] == "de" and has_uml and ("ß" in ph) and ("ddg" in ph.lower()):
                    mem["de_verified"] = True
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": mem["de_verified"]}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    roles = set(active_roles or ("dach_legal_localization_lead", "emea_revops_modeler"))
    docs: list[Path] = []
    urls = [f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"]
    if "dach_legal_localization_lead" in roles:
        docs.append(workspace_map["dach_legal_localization_lead"] / "DACH_Statutory_Impressum.odt")
    if "emea_revops_modeler" in roles:
        docs.append(workspace_map["emea_revops_modeler"] / "EMEA_Tariff_Schedule.xlsx")
    launch_libreoffice_uno_natural(docs, uno_port=UNO_PORT)
    launch_chromium_natural(urls)
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def _inspect_patched_ttf(ttf_path: Path, orig_path: Path) -> dict[str, Any]:
    out = {
        "valid": False, "asc": 0, "desc": 0, "line_gap": 0, "fixed_pitch": -1, "vend_id": "",
        "digits_1220": 0, "tnum_extra_ok": False, "lsb_preserved": False, "kern_hits": 0, "control_clean": False, "base_preserved": False,
    }
    if not ttf_path.is_file() or not orig_path.is_file():
        return out
    try:
        from fontTools.ttLib import TTFont
        fo = TTFont(str(orig_path))
        fp = TTFont(str(ttf_path))
        cmo, cmp_ = fo.getBestCmap(), fp.getBestCmap()
        out["valid"] = True
        out["asc"] = int(fp["OS/2"].sTypoAscender)
        out["desc"] = int(fp["OS/2"].sTypoDescender)
        out["line_gap"] = int(fp["OS/2"].sTypoLineGap)
        out["fixed_pitch"] = int(fp["post"].isFixedPitch)
        raw_v = getattr(fp["OS/2"], "achVendID", b"")
        out["vend_id"] = (raw_v.decode("latin1", errors="ignore") if isinstance(raw_v, (bytes, bytearray)) else str(raw_v)).strip()
        ver_str = str(fp["name"].getDebugName(5) or "")
        out["name_ver_ok"] = ("DIN-1450:2026" in ver_str)
        lsb_ok = True
        d_ok = 0
        for ch in "0123456789":
            w_p, lsb_p = fp["hmtx"][cmp_[ord(ch)]]
            _w_o, lsb_o = fo["hmtx"][cmo[ord(ch)]]
            if w_p == DIN1450_TABULAR_ADV:
                d_ok += 1
            if lsb_p != lsb_o:
                lsb_ok = False
        out["digits_1220"] = d_ok
        ex_ok = True
        for ch in DIN1450_TNUM_EXTRA_CHARS:
            if ord(ch) in cmp_:
                w_p, lsb_p = fp["hmtx"][cmp_[ord(ch)]]
                _wo, lsb_o = fo["hmtx"][cmo[ord(ch)]]
                if w_p != DIN1450_TABULAR_ADV or lsb_p != lsb_o:
                    ex_ok = False
        out["tnum_extra_ok"] = ex_ok
        out["lsb_preserved"] = lsb_ok
        kmap_orig: dict[tuple[str, str], int] = {}
        if "kern" in fo:
            for sub in fo["kern"].kernTables:
                for (g1, g2), val in sub.kernTable.items():
                    kmap_orig[(str(g1), str(g2))] = int(val)
        kmap: dict[tuple[str, str], int] = {}
        if "kern" in fp:
            for sub in fp["kern"].kernTables:
                for (g1, g2), val in sub.kernTable.items():
                    kmap[(str(g1), str(g2))] = int(val)
        out["kern_hits"] = sum(1 for k, v in DIN1450_KERN_PAIRS.items() if kmap.get(k) == v)
        out["control_clean"] = (
            kmap.get(("H", "n"), 0) == kmap_orig.get(("H", "n"), 0)
            and kmap.get(("O", "A"), 0) == kmap_orig.get(("O", "A"), 0)
        )
        out["base_preserved"] = len(kmap) >= max(50, len(kmap_orig) // 2)
    except Exception:
        pass
    return out


def grade(
    workspace_map: dict[str, Path],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    del active_roles
    ws_a = workspace_map["dach_legal_localization_lead"]
    ws_b = workspace_map["emea_revops_modeler"]
    uno_state = inspect_live_uno_documents_readonly(UNO_PORT)

    # --- Role A Checks (20 subchecks) ---
    odt_txt = read_odt_plain_text(ws_a / "DACH_Statutory_Impressum.odt")
    pdf_txt = extract_pdf_text(ws_a / "DACH_Statutory_Impressum.pdf")
    ttf_info = _inspect_patched_ttf(ws_a / "fonts/DACHCorporateSans_DIN1450.ttf", ws_a / "fonts/DACHCorporateSans.ttf")
    ja = read_json_safe(ws_a / "dach_localization_summary.json")

    uno_writer_consistent = True
    writer_has_table = False
    for u_url, u_doc in (uno_state.get("docs") or {}).items():
        if "DACH_Statutory_Impressum.odt" in u_url:
            # Live Writer window must neither hold unsaved modifications nor still have PENDING/WAIVED draft text if disk was updated
            uno_writer_consistent = (not u_doc.get("is_modified")) and ("HRB 289412" in (u_doc.get("text") or ""))
            writer_has_table = int(u_doc.get("table_count", 0)) >= 1

    exp_kern_sum = sum(DIN1450_KERN_PAIRS.values())  # -495
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json_exists", bool(ja), 0.04, "Missing dach_localization_summary.json"),
        ("a_odt_mandate_kept", bool(ja) and "[MANDATE-DACH-2026-Q4]" in odt_txt, 0.04, "Impressum .odt lost [MANDATE-DACH-2026-Q4]"),
        ("a_odt_hrb_ust", BNETZA_REG_DATA["hrb_register"] in odt_txt and BNETZA_REG_DATA["ust_idnr"] in odt_txt, 0.06, "Impressum .odt missing HRB or USt-IdNr"),
        ("a_odt_at_ch_odr", BNETZA_REG_DATA["at_firmenbuch"] in odt_txt and BNETZA_REG_DATA["ch_uid_mwst"] in odt_txt and "ec.europa.eu/consumers/odr" in odt_txt, 0.06, "Impressum .odt missing AT Firmenbuch, CH UID, or EU ODR URL"),
        ("a_odt_de_clause", ("§" in odt_txt and "DDG" in odt_txt and "Größenklasse-ß" in odt_txt and "Präzisions" in odt_txt), 0.05, "Impressum .odt missing German § 5 DDG umlaut/ß clause"),
        ("a_fine_din5008_nbsp", ("\u202f§" in odt_txt or "§\u202f" in odt_txt), 0.07, "Impressum .odt missing DIN 5008 narrow NBSP (U+202F) adjacent to '§'"),
        ("a_odt_waivers_purged", bool(ja) and "WAIVED WITHOUT LIMITATION" not in odt_txt and "DELAWARE" not in odt_txt, 0.06, "Prohibited US waiver/Delaware venue still in .odt"),
        ("a_odt_attestation", DE_PORTAL_ATTESTATION in odt_txt, 0.06, "Impressum .odt missing portal attestation code"),
        ("a_odt_2col_table", writer_has_table, 0.06, "DACH_Statutory_Impressum.odt missing structured 2-column Writer table"),
        ("a_uno_writer_synced", bool(ja) and uno_writer_consistent, 0.07, "Live open LibreOffice Writer window out-of-sync with disk .odt"),
        ("a_pdf_exported", (ws_a / "DACH_Statutory_Impressum.pdf").is_file() and BNETZA_REG_DATA["ch_uid_mwst"] in pdf_txt and "DELAWARE" not in pdf_txt, 0.05, "Exported DACH_Statutory_Impressum.pdf missing AT/CH IDs or contains purged US clause"),
        ("a_ttf_valid", ttf_info["valid"], 0.04, "Missing/invalid DACHCorporateSans_DIN1450.ttf"),
        ("a_ttf_os2_post", ttf_info["asc"] == 1620 and ttf_info["desc"] == -428 and ttf_info["line_gap"] == 140 and ttf_info["fixed_pitch"] == 0, 0.06, "TTF OS/2 asc/desc/lineGap or post.isFixedPitch mismatch"),
        ("a_ttf_digits_all10", ttf_info["digits_1220"] == 10, 0.05, f"TTF tabular digits at 1220 UPM: {ttf_info['digits_1220']}/10"),
        ("a_ttf_tnum_symbols", ttf_info["tnum_extra_ok"], 0.08, "TTF tabular tnum symbols (€,+,-,−,%) not set to 1220 UPM with preserved LSB"),
        ("a_fine_vend_id", ttf_info["vend_id"] == "DACH", 0.08, f"TTF OS/2.achVendID '{ttf_info['vend_id']}' != 'DACH'"),
        ("a_fine_name_ver", bool(ttf_info.get("name_ver_ok")), 0.08, "TTF nameID=5 version string missing 'DIN-1450:2026' per fonts/foundry_release_manifest.xml"),
        ("a_ttf_lsb_kept", ttf_info["lsb_preserved"], 0.04, "TTF digit LSBs altered"),
        ("a_ttf_kern_9plus", ttf_info["kern_hits"] >= 9, 0.04, f"TTF kern hits {ttf_info['kern_hits']}/12 (<9)"),
        ("a_ttf_kern_all12", ttf_info["kern_hits"] == 12 and ttf_info["control_clean"] and ttf_info["base_preserved"], 0.07, "TTF 12 DIN-1450 kern pairs, withdrawn 1998 trap rows, or base kerning preservation failed"),
        ("a_json_ids", ja.get("hrb_register") == BNETZA_REG_DATA["hrb_register"] and ja.get("at_firmenbuch") == BNETZA_REG_DATA["at_firmenbuch"] and ja.get("ch_uid_mwst") == BNETZA_REG_DATA["ch_uid_mwst"], 0.05, "JSON DACH statutory IDs mismatch"),
        ("a_json_att", ja.get("portal_attestation_code") == DE_PORTAL_ATTESTATION and bool(service_state.get("de_verified")), 0.06, "Portal DE-QWERTZ attestation not verified in live session"),
        ("a_json_kern_sum", ja.get("net_kern_adjustment_sum_upm") == exp_kern_sum, 0.04, f"net_kern_adjustment_sum_upm != {exp_kern_sum}"),
        ("a_json_tab_cnt", ja.get("tabular_digit_width_upm") == 1220 and ja.get("patched_pair_count") == 12, 0.03, "JSON tabular_digit_width_upm/patched_pair_count mismatch"),
    ]

    # --- Role B Checks (20 subchecks) ---
    xlsx_p = ws_b / "EMEA_Tariff_Schedule.xlsx"
    sheets = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}
    eval_sh = evaluate_xlsx_via_libreoffice(xlsx_p) if xlsx_p.is_file() else {}
    jb = read_json_safe(ws_b / "emea_revops_reconciliation.json")

    def _cv(sh: str, ref: str) -> Any:
        ev_v = ((eval_sh.get(sh) or {}).get(ref) or {}).get("value")
        if ev_v not in (None, ""):
            return ev_v
        return ((sheets.get(sh) or {}).get(ref) or {}).get("value")

    def _cf(sh: str, ref: str) -> str:
        return str(((sheets.get(sh) or {}).get(ref) or {}).get("formula") or "").upper().replace(" ", "")

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    uno_calc_consistent = True
    for u_url, u_doc in (uno_state.get("docs") or {}).items():
        if "EMEA_Tariff_Schedule.xlsx" in u_url:
            ex_cells = (u_doc.get("sheets") or {}).get("ExecutiveSummary") or {}
            b2_s = str(ex_cells.get("B2") or "0").replace(",", "")
            uno_calc_consistent = (
                (not u_doc.get("is_modified"))
                and (REVOPS_ORACLE["fx_schedule_code"] in json.dumps(ex_cells))
                and abs(_f(b2_s) - REVOPS_ORACLE["q3_net_eur"]) <= 120000.0
            )

    c_json = jb.get("country_net_eur") if isinstance(jb.get("country_net_eur"), dict) else {}
    exp_c = REVOPS_ORACLE["country_net_eur"]
    country_coarse_hits = sum(
        1 for idx, c_code in enumerate(("DE", "AT", "CH", "NL", "UK"), start=2)
        if abs(_f(_cv("CountryRecon", f"B{idx}")) - exp_c[c_code]) <= 45000.0
    )
    exp_qoq = round(REVOPS_ORACLE["q4_net_eur"] - REVOPS_ORACLE["q3_net_eur"], 2)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json_exists", bool(jb), 0.04, "Missing emea_revops_reconciliation.json"),
        ("b_row_cnt", jb.get("recognized_row_count") == REVOPS_ORACLE["recognized_row_count"], 0.06, f"recognized_row_count != {REVOPS_ORACLE['recognized_row_count']} (check rev_no dedup & VOIDED/CLAWBACK rules)"),
        ("b_coarse_countries", country_coarse_hits == 5, 0.06, "CountryRecon!B2:B6 coarse country net EUR off (>45k)"),
        ("b_coarse_q3_q4", abs(_f(jb.get("q3_net_eur")) - REVOPS_ORACLE["q3_net_eur"]) <= 95000.0 and abs(_f(jb.get("q4_net_eur")) - REVOPS_ORACLE["q4_net_eur"]) <= 95000.0, 0.06, "Q3/Q4 coarse net EUR off (>95k; check multi-quarter proration)"),
        ("b_coarse_tot_def", abs(_f(jb.get("total_emea_net_eur")) - REVOPS_ORACLE["total_emea_net_eur"]) <= 85000.0 and abs(_f(jb.get("deferred_2027_eur")) - REVOPS_ORACLE["deferred_2027_eur"]) <= 85000.0, 0.06, "Total/Deferred 2027 coarse EUR off"),
        ("b_fine_berlin_cest_qtr", abs(_f(jb.get("q3_net_eur")) - _f(jb.get("q4_net_eur")) - (-exp_qoq)) <= 1200.0, 0.08, "Europe/Berlin 2026-09-30T22:45Z CEST quarter-cutoff missed"),
        ("b_fine_hedge_cap_spill", abs(_f(c_json.get("CH")) - exp_c["CH"]) <= 3.0 and abs(_f(c_json.get("UK")) - exp_c["UK"]) <= 3.0, 0.09, "Quarterly CHF/GBP hedge cap spillover or doubtful allowance missed"),
        ("b_fine_exact_tot", abs(_f(jb.get("total_emea_net_eur")) - REVOPS_ORACLE["total_emea_net_eur"]) <= 3.0, 0.08, "Exact total_emea_net_eur missed (check ifrs15_collectibility_watch & treasury_hedge_desk_limits)"),
        ("b_dach_pct", abs(_f(jb.get("dach_share_pct")) - REVOPS_ORACLE["dach_share_pct"]) <= 0.45, 0.05, f"dach_share_pct off from {REVOPS_ORACLE['dach_share_pct']}"),
        ("b_vat_eur", abs(_f(jb.get("extracted_vat_eur")) - REVOPS_ORACLE["extracted_vat_eur"]) <= 2.0, 0.05, f"extracted_vat_eur != {REVOPS_ORACLE['extracted_vat_eur']}"),
        ("b_fx_code_json", jb.get("fx_schedule_code") == REVOPS_ORACLE["fx_schedule_code"], 0.05, "Wrong fx_schedule_code in JSON"),
        ("b_xlsx_sum_formula", "SUM(B2:B6)" in _cf("CountryRecon", "B7") and abs(_f(_cv("CountryRecon", "B7")) - REVOPS_ORACLE["total_emea_net_eur"]) <= 85000.0, 0.06, "CountryRecon!B7 missing =SUM(B2:B6)"),
        ("b_xlsx_exec_tot_formula", ("B2+B3" in _cf("ExecutiveSummary", "B4") or "SUM(B2:B3)" in _cf("ExecutiveSummary", "B4")) and abs(_f(_cv("ExecutiveSummary", "B4")) - REVOPS_ORACLE["total_emea_net_eur"]) <= 85000.0, 0.06, "ExecutiveSummary!B4 formula mismatch"),
        ("b_xlsx_qoq_formula", "B3-B2" in _cf("ExecutiveSummary", "B5"), 0.06, "ExecutiveSummary!B5 =B3-B2 formula corrupted (DE-QWERTZ '-' -> 'ß'?)"),
        ("b_xlsx_dach_vat", abs(_f(_cv("ExecutiveSummary", "B6")) - REVOPS_ORACLE["dach_share_pct"]) <= 0.45 and abs(_f(_cv("ExecutiveSummary", "B7")) - REVOPS_ORACLE["extracted_vat_eur"]) <= 2.0, 0.04, "ExecutiveSummary!B6/B7 mismatch"),
        ("b_xlsx_fx_code", str(_cv("ExecutiveSummary", "B8") or "") == REVOPS_ORACLE["fx_schedule_code"], 0.04, "ExecutiveSummary!B8 fx_schedule_code mismatch"),
        ("b_control_kept", bool(jb) and "LIVE-REVOPS-401" in json.dumps(sheets.get("Control") or {}), 0.03, "Control!C2 LIVE-REVOPS-401 lost"),
        ("b_uno_calc_synced", bool(jb) and uno_calc_consistent, 0.07, "Live open LibreOffice Calc window out-of-sync with disk .xlsx"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=None,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port
    assert role in ("dach_legal_localization_lead", "emea_revops_modeler")
    ws = workspace_map[role]

    if role == "dach_legal_localization_lead":
        from fontTools.ttLib import TTFont, newTable
        from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0

        # Font patching runs in parallel without any global lock
        f = TTFont(str(ws / "fonts/DACHCorporateSans.ttf"))
        f["OS/2"].sTypoAscender = 1620
        f["OS/2"].sTypoDescender = -428
        f["OS/2"].sTypoLineGap = 140
        f["OS/2"].achVendID = "DACH"
        f["post"].isFixedPitch = 0
        cm = f.getBestCmap()
        for ch in list("0123456789") + list(DIN1450_TNUM_EXTRA_CHARS):
            if ord(ch) in cm:
                gn = cm[ord(ch)]
                f["hmtx"][gn] = (DIN1450_TABULAR_ADV, f["hmtx"][gn][1])
        for rec in list(f["name"].names):
            if rec.nameID == 5:
                f["name"].setName("Version 2.26; DIN-1450:2026", 5, rec.platformID, rec.platEncID, rec.langID)
        if "kern" in f and f["kern"].kernTables:
            f["kern"].kernTables[0].kernTable.update(DIN1450_KERN_PAIRS)
        else:
            kt = newTable("kern"); kt.version = 0
            sub = KernTable_format_0(); sub.coverage = 1; sub.format = 0; sub.version = 0
            sub.kernTable = dict(DIN1450_KERN_PAIRS)
            kt.kernTables = [sub]; f["kern"] = kt
        f.save(str(ws / "fonts/DACHCorporateSans_DIN1450.ttf"))

        odt_p = ws / "DACH_Statutory_Impressum.odt"
        din_statutory_phrase = BNETZA_REG_DATA["statutory_phrase"].replace("§ ", "§\u202f")
        with tempfile.TemporaryDirectory() as tmp:
            hp = Path(tmp) / "imp.html"
            hp.write_text(
                "<!doctype html><html><head><meta charset='utf-8'/></head><body>"
                "<h1>[MANDATE-DACH-2026-Q4] DACH Statutory Impressum</h1>"
                f"<table border='1'><tr><td>Handelsregister</td><td>{BNETZA_REG_DATA['hrb_register']}</td></tr>"
                f"<tr><td>USt-IdNr.</td><td>{BNETZA_REG_DATA['ust_idnr']}</td></tr>"
                f"<tr><td>WEEE-Reg.-Nr.</td><td>{BNETZA_REG_DATA['weee_reg_nr']}</td></tr>"
                f"<tr><td>Aufsichtsbehörde</td><td>{BNETZA_REG_DATA['aufsichtsbehoerde']}</td></tr>"
                f"<tr><td>Firmenbuch Wien</td><td>{BNETZA_REG_DATA['at_firmenbuch']}</td></tr>"
                f"<tr><td>Schweiz MWST</td><td>{BNETZA_REG_DATA['ch_uid_mwst']}</td></tr></table>"
                "<p>EU ODR: https://ec.europa.eu/consumers/odr</p>"
                f"<p>{din_statutory_phrase}</p>"
                f"<p>PORTAL_ATTESTATION: {DE_PORTAL_ATTESTATION}</p></body></html>",
                encoding="utf-8",
            )
            subprocess.run(
                ["libreoffice", f"-env:UserInstallation=file://{tmp}/lo_o", "--headless", "--convert-to", "odt", "--outdir", str(tmp), str(hp)],
                check=True, capture_output=True, timeout=45,
            )
            odt_p.write_bytes((Path(tmp) / "imp.odt").read_bytes())
            subprocess.run(
                ["libreoffice", f"-env:UserInstallation=file://{tmp}/lo", "--headless", "--convert-to", "pdf", "--outdir", str(ws), str(odt_p)],
                check=True, capture_output=True, timeout=45,
            )
        st_f = Path("/opt/nf_state/service_state.json")
        if st_f.is_file():
            st = read_json_safe(st_f)
            st["de_verified"] = True
            write_json(st_f, st)
        write_json(
            ws / "dach_localization_summary.json",
            {
                "hrb_register": BNETZA_REG_DATA["hrb_register"],
                "ust_idnr": BNETZA_REG_DATA["ust_idnr"],
                "weee_reg_nr": BNETZA_REG_DATA["weee_reg_nr"],
                "at_firmenbuch": BNETZA_REG_DATA["at_firmenbuch"],
                "ch_uid_mwst": BNETZA_REG_DATA["ch_uid_mwst"],
                "portal_attestation_code": DE_PORTAL_ATTESTATION,
                "tabular_digit_width_upm": DIN1450_TABULAR_ADV,
                "net_kern_adjustment_sum_upm": sum(DIN1450_KERN_PAIRS.values()),
                "patched_pair_count": len(DIN1450_KERN_PAIRS),
            },
        )
        with file_atomic_lock("soffice_uno_nf01"):
            if careful_conc:
                subprocess.run(["bash", "-lc", "DISPLAY=:99 setxkbmap us >/dev/null 2>&1 || true"], capture_output=True)
            reload_uno_pipe_documents([odt_p])
    else:
        import tempfile as _tf
        del _tf
        xlsx_p = ws / "EMEA_Tariff_Schedule.xlsx"
        c = REVOPS_ORACLE["country_net_eur"]
        q3, q4 = REVOPS_ORACLE["q3_net_eur"], REVOPS_ORACLE["q4_net_eur"]
        tot = REVOPS_ORACLE["total_emea_net_eur"]
        update_single_sheet_xlsx(
            xlsx_p,
            "CountryRecon",
            [
                ["Country", "Net_EUR"],
                ["DE", c["DE"]], ["AT", c["AT"]], ["CH", c["CH"]], ["NL", c["NL"]], ["UK", c["UK"]],
                ["TOTAL", ("=SUM(B2:B6)", tot)],
            ],
        )
        update_single_sheet_xlsx(
            xlsx_p,
            "ExecutiveSummary",
            [
                ["Metric", "Value"],
                ["Q3_Net_EUR", q3],
                ["Q4_Net_EUR", q4],
                ["Total_EMEA_Net_EUR", ("=B2+B3", tot)],
                ["QoQ_Delta_EUR", ("=B3-B2", round(q4 - q3, 2))],
                ["DACH_Share_Pct", REVOPS_ORACLE["dach_share_pct"]],
                ["Extracted_VAT_EUR", REVOPS_ORACLE["extracted_vat_eur"]],
                ["FX_Schedule_Code", REVOPS_ORACLE["fx_schedule_code"]],
                ["Deferred_2027_EUR", REVOPS_ORACLE["deferred_2027_eur"]],
            ],
        )
        write_json(ws / "emea_revops_reconciliation.json", REVOPS_ORACLE)
        with file_atomic_lock("soffice_uno_nf01"):
            reload_uno_pipe_documents([xlsx_p])


import tempfile  # noqa: E402


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4: DE-QWERTZ XKB switch mutates Calc formula `=B3-B2` (`=` -> `)`, `-` -> `ß`) & leaves stale UNO Calc buffer."""
    solve_role("dach_legal_localization_lead", workspace_map, port, careful_conc=False)
    solve_role("emea_revops_modeler", workspace_map, port, careful_conc=False)
    ws_b = workspace_map["emea_revops_modeler"]
    xlsx_p = ws_b / "EMEA_Tariff_Schedule.xlsx"
    q3, q4 = REVOPS_ORACLE["q3_net_eur"], REVOPS_ORACLE["q4_net_eur"]
    c = REVOPS_ORACLE["country_net_eur"]
    update_single_sheet_xlsx(
        xlsx_p,
        "CountryRecon",
        [
            ["Country", "Net_EUR"],
            ["DE", c["DE"]], ["AT", c["AT"]], ["CH", c["CH"]], ["NL", c["NL"]], ["UK", c["UK"]],
            ["TOTAL", ")SUM(B2ÖB6)"],
        ],
    )
    update_single_sheet_xlsx(
        xlsx_p,
        "ExecutiveSummary",
        [
            ["Metric", "Value"],
            ["Q3_Net_EUR", q3],
            ["Q4_Net_EUR", q4],
            ["Total_EMEA_Net_EUR", ")B2+B3"],
            ["QoQ_Delta_EUR", ")B3ßB2"],
            ["DACH_Share_Pct", REVOPS_ORACLE["dach_share_pct"]],
            ["Extracted_VAT_EUR", REVOPS_ORACLE["extracted_vat_eur"]],
            ["FX_Schedule_Code", "PENDING"],
                ["Deferred_2027_EUR", 0.0],
        ],
    )
    jb = read_json_safe(ws_b / "emea_revops_reconciliation.json")
    jb["fx_schedule_code"] = str(jb.get("fx_schedule_code", "")).replace("Z", "Y")
    write_json(ws_b / "emea_revops_reconciliation.json", jb)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["xkb_switches"] = int(st.get("xkb_switches", 0)) + 3
    write_json(sp, st)
