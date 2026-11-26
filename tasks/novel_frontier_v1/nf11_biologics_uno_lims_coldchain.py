"""NF-11: Biologics Cold-Chain Excursion & Air-Cargo Qualification — Live LibreOffice (Calc + Writer + UNO :2002) & LIMS Portal.

Authentic Co-Tenant Scenario:
  - Biologics Stability QA Specialist and Packaging Thermal Engineer share a GMP Quality Release Workstation
    with `ColdChain_Qualification.xlsx` and `Deviation_CAPA_2026_114.odt` open in a single `soffice.bin`
    process (UNO `:2002`) plus an authenticated LIMS Excursion Console in Chromium (`:19511`, no `:9222`).
  - Features 432 multi-probe 15-minute telemetry rows with NIST calibration offsets, CRC dropouts, and
    door-open audit exclusions, plus a tight true IATA PI-954 ULD gross shipper weight cap (`<= 42.60 kg`).
"""
from __future__ import annotations

import csv
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import secrets
import sqlite3
import subprocess
from typing import Any
from urllib.parse import parse_qs, urlparse

from tasks.novel_frontier_v1.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
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

TASK_ID = "NF-11"
PORTAL_PORT = 19511
UNO_PORT = 2002

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Biologics Cold-Chain Excursion LIMS & Live LibreOffice UNO Split-Brain: 432-Sample Multi-Probe Arrhenius MKT vs. 4-Leg IATA Dry-Ice Qualification",
    "domain": "Biopharmaceutical Cold-Chain Quality Assurance & Cryogenic Packaging Engineering (LibreOffice Calc/Writer + LIMS)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("biologics_stability_qa", "packaging_thermal_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (UNO_PORT,),
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

# NIST Calibration offsets (true_C = raw_C + offset_C) printed ONLY on scanned exhibit `probe_calibration_cert.png`
PROBE_OFFSETS_C = {
    "PRB-CORE-1": +0.35,
    "PRB-TOP-2":  -0.25,
    "PRB-DOOR-3": +0.45,
    "PRB-AMB-4":   0.00,  # External ambient reference probe — MUST NOT be included in product MKT!
}
EA_KJ_MOL = 83.144
GAS_R_KJ = 0.008314462
LIMS_QA_CODE = "LIMS-MKT-994A-5512"
LIMS_PKG_CODE = "LIMS-PI954-ULD-8834"

TRANSIT_LEGS = [
    # (leg_id, hours, ambient_c, mode, exposure, alt_factor)
    ("LEG-1-BSL-TRUCK",   6.0, 18.5, "GROUND", "ENCLOSED_REEFER_BAY", 1.00),
    ("LEG-2-FRA-RAMP",    8.0, 29.5, "GROUND", "UNSHADED_APRON",      1.00),  # +4.5 °C solar skin surcharge!
    ("LEG-3-ANC-FLIGHT", 22.0, 14.0, "FLIGHT", "CARGO_HOLD_DECK",     1.18),
    ("LEG-4-KIX-CUSTOMS",16.0, 24.0, "GROUND", "BONDED_WAREHOUSE",    1.00),
]
SHIPPER_TARE_KG = 6.20
PRECOOL_FLASH_LOSS_KG = 1.35
APRON_SOLAR_DELTA_C = 4.5
VIP_AGING_FACTOR = 1.06  # Shipper #VIP-ULD-09 has 47 thermal cycles (>40 cycle threshold -> +6% k_insul aging!)


def _generate_telemetry_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    t_cursor = 0
    for step in range(108):
        dt_min = 30 if (80 <= step <= 95) else 15  # Eco-flight 30-min polling window!
        ev_flag = "NORMAL"
        if step in (16, 17):
            ev_flag = "DOOR_OPEN_AUDIT"
        is_fahr = (64 <= step <= 75)  # 3-hour backup thermistor failover outputs °F!
        for prb in ("PRB-CORE-1", "PRB-TOP-2", "PRB-DOOR-3", "PRB-AMB-4"):
            if prb == "PRB-AMB-4":
                raw_c = 22.0 + (7.5 if 44 <= step <= 59 else 0.0)
            elif step in (16, 17):
                raw_c = 9.4 if prb == "PRB-DOOR-3" else 5.2
            elif 44 <= step <= 59:
                peak_boost = {"PRB-CORE-1": 6.4, "PRB-TOP-2": 8.6, "PRB-DOOR-3": 10.8}[prb]
                raw_c = 4.2 + peak_boost
            else:
                base = {"PRB-CORE-1": 3.8, "PRB-TOP-2": 4.6, "PRB-DOOR-3": 4.9}[prb]
                raw_c = base + 0.2 * math.sin(step * 0.3)

            qual = "OK"
            scale = "FAHRENHEIT" if is_fahr else "CELSIUS"
            cal_applied = 1 if step >= 96 else 0  # Post-swap steps 96..107 already include NIST probe offset!
            eff_raw_c = (raw_c + PROBE_OFFSETS_C[prb]) if cal_applied == 1 else raw_c
            disp_val = (eff_raw_c * 9.0 / 5.0 + 32.0) if is_fahr else eff_raw_c
            raw_str = f"{disp_val:.2f}"
            # Backup EU logger channel formats decimal comma on steps 32..37!
            if 32 <= step <= 37:
                raw_str = raw_str.replace(".", ",")
            # DS18B20 power-on-reset +85.00°C sentinel glitch (CRC valid so quality_flag stays 'OK'!)
            if (step == 22 and prb == "PRB-CORE-1") or (step == 61 and prb == "PRB-DOOR-3"):
                raw_str = "85.00"
            if (step == 29 and prb == "PRB-TOP-2") or (step == 73 and prb == "PRB-CORE-1"):
                qual = "CRC_FAULT"
                raw_str = "ERR_CRC"

            if step in (46, 52, 84) and prb == "PRB-DOOR-3":
                rows.append({
                    "sample_idx": len(rows) + 1,
                    "elapsed_min": t_cursor,
                    "interval_min": dt_min,
                    "seq_no": 1,
                    "probe_id": prb,
                    "temp_scale": scale,
                    "cal_applied": cal_applied,
                    "raw_temp": f"{disp_val + 3.40:.2f}",
                    "quality_flag": "OK",
                    "event_flag": ev_flag,
                })

            rows.append({
                "sample_idx": len(rows) + 1,
                "elapsed_min": t_cursor,
                "interval_min": dt_min,
                "seq_no": 2 if (step in (46, 52, 84) and prb == "PRB-DOOR-3") else 1,
                "probe_id": prb,
                "temp_scale": scale,
                "cal_applied": cal_applied,
                "raw_temp": raw_str,
                "quality_flag": qual,
                "event_flag": ev_flag,
            })
        t_cursor += dt_min
    return rows


def _compute_coldchain_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _generate_telemetry_rows()
    dedup: dict[tuple[int, str], dict[str, Any]] = {}
    for r in rows:
        key = (int(r["elapsed_min"]), str(r["probe_id"]))
        if key not in dedup or int(r["seq_no"]) >= int(dedup[key]["seq_no"]):
            dedup[key] = r

    dh_r = EA_KJ_MOL / GAS_R_KJ
    by_probe: dict[str, list[tuple[float, float]]] = {"PRB-CORE-1": [], "PRB-TOP-2": [], "PRB-DOOR-3": []}
    exc_min_door3 = 0.0
    for r in dedup.values():
        prb = r["probe_id"]
        if prb not in by_probe:
            continue
        if r["quality_flag"] != "OK":
            continue
        v_raw = float(str(r["raw_temp"]).replace(",", "."))
        if abs(v_raw - 85.0) < 1e-6 and r["temp_scale"] == "CELSIUS":
            continue  # Exclude DS18B20 +85.00°C power-on reset sentinel!
        c_uncal = ((v_raw - 32.0) * 5.0 / 9.0) if r["temp_scale"] == "FAHRENHEIT" else v_raw
        cal_c = c_uncal if int(r.get("cal_applied", 0)) == 1 else (c_uncal + PROBE_OFFSETS_C[prb])
        dt = float(r["interval_min"])
        by_probe[prb].append((dt, cal_c))
        if prb == "PRB-DOOR-3" and cal_c > 8.0:
            exc_min_door3 += dt

    mkt_by_probe: dict[str, float] = {}
    for prb, vals in by_probe.items():
        tot_dt = sum(dt for dt, _c in vals)
        mean_exp = sum(dt * math.exp(-dh_r / (c + 273.15)) for dt, c in vals) / tot_dt
        mkt_k = dh_r / (-math.log(mean_exp))
        mkt_by_probe[prb] = round(mkt_k - 273.15, 3)

    worst_prb = max(mkt_by_probe, key=lambda k: mkt_by_probe[k])
    worst_mkt = mkt_by_probe[worst_prb]
    exc_hours = round(exc_min_door3 / 60.0, 2)

    k_insul = 0.0038 * VIP_AGING_FACTOR
    leg_losses = {}
    tot_sub = 0.0
    for lid, hrs, tamb, _mode, exp_kind, afac in TRANSIT_LEGS:
        eff_t = tamb + (APRON_SOLAR_DELTA_C if exp_kind == "UNSHADED_APRON" else 0.0)
        rate = k_insul * (eff_t - (-78.5)) * afac
        loss = hrs * rate
        leg_losses[lid] = round(loss, 3)
        tot_sub += loss
    tot_sub_r = round(tot_sub, 3)
    min_ice = round((tot_sub + PRECOOL_FLASH_LOSS_KG) * 1.15, 2)

    qa_or = {
        "valid_product_sample_count": sum(len(v) for v in by_probe.values()),
        "probe_mkt_celsius": mkt_by_probe,
        "worst_probe_id": worst_prb,
        "worst_probe_mkt_c": worst_mkt,
        "worst_probe_hours_above_8c": exc_hours,
        "batch_disposition": "CONDITIONAL_RELEASE_TRIM_DOOR_TRAY" if worst_mkt <= 8.0 else "QUARANTINE",
        "lims_qa_code": LIMS_QA_CODE,
    }
    pkg_or = {
        "leg_sublimation_kg": leg_losses,
        "total_4leg_sublimation_kg": tot_sub_r,
        "minimum_qualified_dry_ice_kg": min_ice,
        "lims_pkg_code": LIMS_PKG_CODE,
    }
    return qa_or, pkg_or


QA_ORACLE, PKG_ORACLE = _compute_coldchain_oracles()
IATA_GROSS_CAP_KG = round(SHIPPER_TARE_KG + 13.60 + PKG_ORACLE["minimum_qualified_dry_ice_kg"] + 1.00, 2)

LIMS_HTML = f"""<!doctype html><html><head><meta charset="utf-8"><title>Biologics LIMS & Cargo Telemetry</title>
<style>
  body {{ background:#0f172a; color:#f8fafc; font-family:monospace; margin:22px; }}
  .bar {{ background:#1e293b; padding:12px 16px; border:1px solid #334155; display:flex; gap:10px; align-items:center; }}
  button {{ padding:8px 14px; background:#2563eb; color:#fff; border:none; cursor:pointer; }}
  .card {{ background:#111827; border:1px solid #334155; padding:16px; margin-top:16px; }}
  table {{ border-collapse:collapse; margin-top:10px; }}
  td, th {{ border:1px solid #334155; padding:6px 12px; }}
</style></head><body>
<div class="bar">
  <strong>GMP Biologics LIMS v4.2</strong> | Active Session View: <span id="vw" style="color:#4ade80">...</span>
  <button onclick="setView('STABILITY_MKT_CELSIUS')">View: Stability MKT (mAb-Lot-994A)</button>
  <button onclick="setView('IATA_TRANSIT_LEGS')">View: 4-Leg Transit Routing (PI-954)</button>
</div>
<div class="card" id="panel">Loading LIMS context...</div>
<script>
async function loadPanel() {{
  const r = await fetch('/api/lims/context', {{credentials:'include'}});
  const j = await r.json();
  document.getElementById('vw').textContent = j.view;
  document.getElementById('panel').innerHTML = j.html;
}}
async function setView(v) {{
  await fetch('/api/lims/set_view?view=' + v, {{method:'POST', credentials:'include'}});
  await loadPanel();
}}
loadPanel();
</script></body></html>"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Biologics Multi-Probe Arrhenius MKT & Batch Release (`biologics_stability_qa`)",
        "",
        "## Context & Objective",
        f"Evaluate temperature excursion lot `mAb-Lot-994A` on this GMP workstation. Consult `{b}/workspace/SOP_QA_USP1079.pdf{b}`, `{b}/workspace/exhibits/probe_calibration_cert.png{b}`, `{b}/workspace/exhibits/iata_uld_waybill.png{b}`, `{b}/workspace/telemetry_15min_4probes.csv{b}`, and the authenticated **Biologics LIMS** portal (`http://127.0.0.1:{PORTAL_PORT}/lims`) in Chromium.",
        "",
        "## Deliverables",
        f"1. **Shared Workbook `{b}/workspace/shared_docs/ColdChain_Qualification.xlsx{b}`**:",
        "   - Complete the `StabilityMKT` sheet and update your committed releasable `vial_payload_kg` and status in `ULD_Summary` so both the clinical minimum order and the coupled IATA ULD gross shipper ceiling are respected without overwriting `PackagingThermal` or `Control` metadata. Ensure the open LibreOffice Calc window and disk workbook are synchronized.",
        f"2. **Shared CAPA Document `{b}/workspace/shared_docs/Deviation_CAPA_2026_114.odt{b}`**:",
        "   - Append your QA disposition summary and LIMS QA release code while preserving existing CAPA sections and keeping the open LibreOffice Writer document synchronized with disk.",
        f"3. **Audit JSON `{b}/workspace/stability_mkt_decision.json{b}`**: Follow Section 3 of `SOP_QA_USP1079.pdf`.",
    ])
    tb = "\n".join([
        "# Work Order — 4-Leg Cryogenic Sublimation & IATA PI-954 Shipper Qualification (`packaging_thermal_eng`)",
        "",
        "## Context & Objective",
        f"Qualify the dry-ice bunker charge for air-cargo route `BSL-FRA-ANC-KIX` on this GMP workstation. Consult `{b}/workspace/SOP_PKG_PI954.pdf{b}`, `{b}/workspace/exhibits/iata_uld_waybill.png{b}`, and the authenticated **Biologics LIMS** portal (`http://127.0.0.1:{PORTAL_PORT}/lims`) in Chromium.",
        "",
        "## Deliverables",
        f"1. **Shared Workbook `{b}/workspace/shared_docs/ColdChain_Qualification.xlsx{b}`**:",
        "   - Complete the `PackagingThermal` sheet and update your committed `dry_ice_charge_kg` and status in `ULD_Summary` so both the 15%-buffered thermal endurance floor and the coupled IATA ULD gross shipper ceiling are satisfied without clobbering `StabilityMKT`. Ensure the open LibreOffice Calc window and disk workbook are synchronized.",
        f"2. **Shared CAPA Document `{b}/workspace/shared_docs/Deviation_CAPA_2026_114.odt{b}`**:",
        "   - Append your thermal qualification signoff and LIMS PI-954 code while preserving existing CAPA content and keeping the open LibreOffice Writer document synchronized with disk.",
        f"3. **Audit JSON `{b}/workspace/packaging_pi954_qualification.json{b}`**: Follow Section 3 of `SOP_PKG_PI954.pdf`.",
    ])
    return {"biologics_stability_qa": ta, "packaging_thermal_eng": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["biologics_stability_qa"]
    ws_b = workspace_map["packaging_thermal_eng"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    (ws_a / "exhibits").mkdir(parents=True, exist_ok=True)
    (ws_b / "exhibits").mkdir(parents=True, exist_ok=True)
    hub.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    t_rows = _generate_telemetry_rows()
    cw = csv.DictWriter(buf, fieldnames=list(t_rows[0].keys()))
    cw.writeheader()
    cw.writerows(t_rows)
    (ws_a / "telemetry_15min_4probes.csv").write_text(buf.getvalue(), encoding="utf-8")

    render_scanned_exhibit_png(
        ws_a / "exhibits/probe_calibration_cert.png",
        "NIST TRACEABLE THERMISTOR CALIBRATION CERTIFICATE #CAL-2026-881",
        [
            "Apply signed offset:  T_calibrated_C = T_raw_C + Offset_C",
            "  • PRB-CORE-1 (Center Vial Tray):     Offset_C = +0.35 °C",
            "  • PRB-TOP-2  (Upper Vial Tray):      Offset_C = -0.25 °C",
            "  • PRB-DOOR-3 (Door Perimeter Tray):  Offset_C = +0.45 °C",
            "  • PRB-AMB-4  (Exterior ULD Skin):    Offset_C =  0.00 °C  [EXTERNAL REFERENCE ONLY — EXCLUDE FROM PRODUCT MKT]",
        ],
        stamp_text="QA METROLOGY CALIBRATED",
    )

    render_scanned_exhibit_png(
        ws_a / "exhibits/iata_uld_waybill.png",
        "IATA DANGEROUS GOODS PI-954 AIR WAYBILL — BSL -> FRA -> ANC -> KIX",
        [
            "Shipper Unit Serial: #VIP-ULD-09 (Thermal Cycle Count: 47 cycles) | Empty Tare: 6.20 kg",
            f"Maximum Structural & CO2-Vent Gross Mass Cap: {IATA_GROSS_CAP_KG:.2f} kg  (6.20 + vial_payload_kg + dry_ice_charge_kg <= {IATA_GROSS_CAP_KG:.2f} kg)",
            "Nominal New-Panel Conductance k_0: 0.0038 kg/(h*K) | Dry-Ice Sublimation Temp T_sub: -78.5 °C | Reserve: +15.0%",
            "Cruise Depressurization Sublimation Factor:    1.18x on FLIGHT legs, 1.00x on GROUND legs",
            "Unshaded Daytime Apron Solar Skin Surcharge:  +4.50 °C effective ambient delta on UNSHADED_APRON legs",
        ],
        stamp_text="IATA PI-954 CARGO CONTROL",
    )
    (ws_b / "exhibits/iata_uld_waybill.png").write_bytes((ws_a / "exhibits/iata_uld_waybill.png").read_bytes())
    with sqlite3.connect(str(ws_b / "uld_fleet_maintenance.sqlite")) as uconn:
        uconn.execute(
            "CREATE TABLE vip_uld_calibration (uld_serial TEXT PRIMARY KEY, thermal_cycles INTEGER, "
            "vacuum_aging_surcharge_pct REAL, warm_shell_precool_flash_kg REAL, status TEXT)"
        )
        for s_num, cyc, ag_pct, fl_kg, st_u in [
            ("#VIP-ULD-04", 18, 0.0, 1.10, "ACTIVE"),
            ("#VIP-ULD-06", 29, 0.0, 1.15, "ACTIVE"),
            ("#VIP-ULD-07", 52, 6.0, 1.35, "QUARANTINE_GASKET"),
            ("#VIP-ULD-09", 47, 6.0, 1.35, "ACTIVE"),
            ("#VIP-ULD-11", 12, 0.0, 1.05, "ACTIVE"),
        ]:
            uconn.execute("INSERT INTO vip_uld_calibration VALUES (?,?,?,?,?)", (s_num, cyc, ag_pct, fl_kg, st_u))
        uconn.commit()

    write_multipage_sop_pdf(
        ws_a / "SOP_QA_USP1079.pdf",
        "SOP-QA-1079: Biologics Excursion MKT & Batch Release Standard",
        [
            ("1. USP <1079> Arrhenius Mean Kinetic Temperature", [
            "1.1 Clean /workspace/telemetry_15min_4probes.csv across internal product probes using standard metrology data hygiene and exhibits/probe_calibration_cert.png (exclude external PRB-AMB-4, non-OK CRC_FAULT rows, and DS18B20 +85.00°C power-on-reset sentinels; retain real DOOR_OPEN_AUDIT thermal exposure on product trays).",
                "1.2 Compute time-weighted USP <1079> Arrhenius MKT per product probe using kinetic constants from /lims. Report worst_probe_id, worst_probe_mkt_c (3 dec), worst_probe_hours_above_8c (hours >8.0°C, 2 dec), and batch_disposition ('CONDITIONAL_RELEASE_TRIM_DOOR_TRAY' if worst_probe_mkt_c <= 8.0°C else 'QUARANTINE').",
            ]),
            ("2. Clinical Vial Release Sizing & Workbook Layout", [
                f"2.1 Clinical minimum order is 13.60 kg (preferred un-quarantined lot release = 14.30 kg, max 16.40 kg), subject to the shipper's {IATA_GROSS_CAP_KG:.2f} kg gross ceiling in /workspace/shared_docs/ColdChain_Qualification.xlsx ULD_Summary!B2:C5 (B3=vial_payload_kg, C3='COMMITTED', B5='=SUM(B2:B4)', C1='SESSION-QA-994A').",
                "2.2 Sheet 'StabilityMKT': B2=PRB-CORE-1 MKT, B3=PRB-TOP-2 MKT, B4=PRB-DOOR-3 MKT, B5=worst_probe_mkt_c, B6=worst_probe_hours_above_8c, B7=batch_disposition, B8=lims_qa_code.",
            ]),
            ("3. JSON Schema (/workspace/stability_mkt_decision.json)", [
                "  valid_product_sample_count (int), probe_mkt_celsius (dict), worst_probe_id (str),",
                "  worst_probe_mkt_c (float), worst_probe_hours_above_8c (float), vial_payload_kg (float),",
                "  batch_disposition (str), lims_qa_code (str).",
            ]),
        ],
    )

    write_multipage_sop_pdf(
        ws_b / "SOP_PKG_PI954.pdf",
        "SOP-PKG-954: Cryogenic Sublimation & IATA ULD Qualification",
        [
            ("1. 4-Leg Sublimation & Reserve Qualification", [
                "1.1 Compute per-leg dry-ice sublimation (3 dec) across the 4 route legs in /lims (IATA_TRANSIT_LEGS view) using the physical parameters on exhibits/iata_uld_waybill.png, then determine minimum_qualified_dry_ice_kg (2 dec).",
                f"1.2 Size committed dry_ice_charge_kg >= minimum_qualified_dry_ice_kg (preferred +0.65 kg operational buffer) in /workspace/shared_docs/ColdChain_Qualification.xlsx ULD_Summary (B4=dry_ice_charge_kg, C4='COMMITTED', gross mass <= {IATA_GROSS_CAP_KG:.2f} kg). Sheet 'PackagingThermal': B2..B5 = LEG-1..LEG-4 sublimation, B6 = '=SUM(B2:B5)', B7 = minimum_qualified_dry_ice_kg, B8 = lims_pkg_code.",
            ]),
            ("3. JSON Schema (/workspace/packaging_pi954_qualification.json)", [
                "  leg_sublimation_kg (dict mapping 'LEG-1-BSL-TRUCK', 'LEG-2-FRA-RAMP', 'LEG-3-ANC-FLIGHT', 'LEG-4-KIX-CUSTOMS' -> float),",
                "  total_4leg_sublimation_kg (float), minimum_qualified_dry_ice_kg (float), dry_ice_charge_kg (float), lims_pkg_code (str).",
            ]),
        ],
    )

    write_multisheet_xlsx(
        hub / "ColdChain_Qualification.xlsx",
        [
            ("ULD_Summary", [
                ["Component", "Mass_kg", "SESSION-QA-994A"],
                ["Container_Tare_kg", 6.20, "FIXED"],
                ["Vial_Payload_kg", 0.0, "PENDING"],
                ["Dry_Ice_Charge_kg", 0.0, "PENDING"],
                ["Gross_Shipper_Mass_kg", ("=SUM(B2:B4)", 6.20), f"CAP_{IATA_GROSS_CAP_KG:.2f}"],
            ]),
            ("StabilityMKT", [
                ["Metric", "Value"],
                ["MKT_PRB_CORE_1", 0.0],
                ["MKT_PRB_TOP_2", 0.0],
                ["MKT_PRB_DOOR_3", 0.0],
                ["Worst_Probe_MKT_C", 0.0],
                ["Worst_Hours_Above_8C", 0.0],
                ["Batch_Disposition", "PENDING"],
                ["LIMS_QA_Code", "PENDING"],
            ]),
            ("PackagingThermal", [
                ["Metric", "Value"],
                ["LEG-1-BSL-TRUCK", 0.0],
                ["LEG-2-FRA-RAMP", 0.0],
                ["LEG-3-ANC-FLIGHT", 0.0],
                ["LEG-4-KIX-CUSTOMS", 0.0],
                ["Total_Sublimation_kg", ("=SUM(B2:B5)", 0.0)],
                ["Min_Qualified_DryIce_kg", 0.0],
                ["LIMS_PKG_Code", "PENDING"],
            ]),
        ],
    )

    write_simple_odt(
        hub / "Deviation_CAPA_2026_114.odt",
        "GMP Deviation CAPA-2026-114 — Biologics Lot mAb-994A",
        [
            ("CAPA_HDR", "[CAPA-LOCK-114] Customs Ramp Excursion & Air-Cargo Re-Qualification"),
            ("SCOPE", "Requires both Stability QA MKT disposition and PI-954 Packaging Thermal signoff."),
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
    mem = {"view": "STABILITY_MKT_CELSIUS", "view_flips": 0}
    write_json(st_path, {"task_id": TASK_ID, **mem})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return ("lims_sso" in c) and (c["lims_sso"].value == tok)
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
                ck = f"lims_sso={tok}; HttpOnly; Path=/; SameSite=Lax"
                raw = b"<html><body><script>location.href='/lims';</script></body></html>"
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Set-Cookie", ck); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if not self._authed():
                self._json(403, {"error": "HttpOnly LIMS SSO required"}); return
            if u.path == "/lims":
                raw = LIMS_HTML.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            if u.path == "/api/lims/context":
                if mem["view"] == "STABILITY_MKT_CELSIUS":
                    h = (
                        f"<h3>Batch mAb-Lot-994A Kinetic Parameters</h3>"
                        f"<p>Activation Energy <code>E_a = {EA_KJ_MOL} kJ/mol</code> | Gas Constant <code>R = {GAS_R_KJ} kJ/(mol·K)</code></p>"
                        f"<p>USP &lt;1079&gt; Controlled Cold-Chain MKT Ceiling: <code>8.000 °C</code></p>"
                        f"<p>LIMS QA Release Code: <strong style='color:#4ade80'>{LIMS_QA_CODE}</strong></p>"
                    )
                else:
                    rows_html = "".join(
                        f"<tr><td>{lid}</td><td>{hrs}</td><td>{tamb} °C</td><td>{md}</td><td>{exp_k}</td></tr>"
                        for lid, hrs, tamb, md, exp_k, _af in TRANSIT_LEGS
                    )
                    h = (
                        f"<h3>Route BSL-FRA-ANC-KIX 4-Leg Ambient Profile</h3>"
                        f"<table><tr><th>Leg ID</th><th>Duration (h)</th><th>Mean Ambient</th><th>Regime</th><th>Ramp Exposure</th></tr>{rows_html}</table>"
                        f"<p>LIMS PI-954 Packaging Code: <strong style='color:#4ade80'>{LIMS_PKG_CODE}</strong></p>"
                    )
                self._json(200, {"view": mem["view"], "html": h}); return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not self._authed():
                self._json(403, {"error": "HttpOnly LIMS SSO required"}); return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if u.path == "/api/lims/set_view":
                nv = (qs.get("view") or ["STABILITY_MKT_CELSIUS"])[0]
                if nv in ("STABILITY_MKT_CELSIUS", "IATA_TRANSIT_LEGS") and nv != mem["view"]:
                    mem["view"] = nv; mem["view_flips"] += 1
                    write_json(st_path, {"task_id": TASK_ID, **mem})
                self._json(200, {"ok": True, "view": mem["view"]}); return
            self._json(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/boot_auth\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    launch_libreoffice_uno_natural([hub / "ColdChain_Qualification.xlsx", hub / "Deviation_CAPA_2026_114.odt"], uno_port=UNO_PORT)
    launch_chromium_natural([f"http://127.0.0.1:{PORTAL_PORT}/boot_auth"])
    (state_dir / "boot_sealed").write_text("1\n", encoding="utf-8")


def grade(
    workspace_map: dict[str, Path],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    act_set = set(active_roles or META["roles"])
    has_a = "biologics_stability_qa" in act_set
    has_b = "packaging_thermal_eng" in act_set
    ws_a = workspace_map["biologics_stability_qa"]
    ws_b = workspace_map["packaging_thermal_eng"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    xlsx_p = hub / "ColdChain_Qualification.xlsx"
    odt_p = hub / "Deviation_CAPA_2026_114.odt"
    sheets = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}
    eval_sh = evaluate_xlsx_via_libreoffice(xlsx_p) if xlsx_p.is_file() else {}
    odt_txt = read_odt_plain_text(odt_p)
    uno_state = inspect_live_uno_documents_readonly(UNO_PORT)

    ja = read_json_safe(ws_a / "stability_mkt_decision.json")
    jb = read_json_safe(ws_b / "packaging_pi954_qualification.json")

    def _cv(sh: str, ref: str) -> Any:
        ev_v = ((eval_sh.get(sh) or {}).get(ref) or {}).get("value")
        return ev_v if ev_v not in (None, "") else ((sheets.get(sh) or {}).get(ref) or {}).get("value")

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    pay_kg = _f(_cv("ULD_Summary", "B3"))
    ice_kg = _f(_cv("ULD_Summary", "B4"))
    gross_kg = 6.20 + pay_kg + ice_kg
    min_ice_req = PKG_ORACLE["minimum_qualified_dry_ice_kg"]

    uno_calc_ok = True
    uno_writer_ok = True
    for u_url, u_doc in (uno_state.get("docs") or {}).items():
        if "ColdChain_Qualification.xlsx" in u_url:
            sm = (u_doc.get("sheets") or {}).get("ULD_Summary") or {}
            st_sh = (u_doc.get("sheets") or {}).get("StabilityMKT") or {}
            pk_sh = (u_doc.get("sheets") or {}).get("PackagingThermal") or {}
            c3_ok = (not has_a) or (str(sm.get("C3") or "").upper() == "COMMITTED" and abs(_f(str(sm.get("B3") or "0").replace(",", "")) - pay_kg) <= 0.08 and LIMS_QA_CODE in json.dumps(st_sh))
            c4_ok = (not has_b) or (str(sm.get("C4") or "").upper() == "COMMITTED" and abs(_f(str(sm.get("B4") or "0").replace(",", "")) - ice_kg) <= 0.08 and LIMS_PKG_CODE in json.dumps(pk_sh))
            uno_calc_ok = (not u_doc.get("is_modified")) and c3_ok and c4_ok
        elif "Deviation_CAPA_2026_114.odt" in u_url:
            utxt = u_doc.get("text") or ""
            qa_u = (not has_a) or (LIMS_QA_CODE in utxt)
            pk_u = (not has_b) or (LIMS_PKG_CODE in utxt)
            uno_writer_ok = (not u_doc.get("is_modified")) and qa_u and pk_u

    pm = ja.get("probe_mkt_celsius") if isinstance(ja.get("probe_mkt_celsius"), dict) else {}
    exp_pm = QA_ORACLE["probe_mkt_celsius"]

    # 17 subchecks Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.05, "Missing stability_mkt_decision.json"),
        ("a_sample_cnt_exact", ja.get("valid_product_sample_count") in (QA_ORACLE["valid_product_sample_count"], 314), 0.10, f"valid_product_sample_count != {QA_ORACLE['valid_product_sample_count']} (check DS18B20 +85.00C sentinel)"),
        ("a_no_amb4", bool(ja) and "PRB-AMB-4" not in pm, 0.04, "External PRB-AMB-4 included in product MKT"),
        ("a_core_top_coarse", abs(_f(pm.get("PRB-CORE-1")) - exp_pm["PRB-CORE-1"]) <= 0.90 and abs(_f(pm.get("PRB-TOP-2")) - exp_pm["PRB-TOP-2"]) <= 0.90, 0.06, "PRB-CORE-1/TOP-2 coarse MKT mismatch"),
        ("a_door3_mkt_exact", abs(_f(pm.get("PRB-DOOR-3")) - exp_pm["PRB-DOOR-3"]) <= 0.03 or abs(_f(pm.get("PRB-DOOR-3")) - 7.602) <= 0.03, 0.10, f"PRB-DOOR-3 exact MKT != {exp_pm['PRB-DOOR-3']} (check +85C sentinel & cal_applied)"),
        ("a_worst_id", ja.get("worst_probe_id") == "PRB-DOOR-3", 0.05, "worst_probe_id != PRB-DOOR-3"),
        ("a_worst_mkt_xlsx", abs(_f(_cv("StabilityMKT", "B5")) - QA_ORACLE["worst_probe_mkt_c"]) <= 1.20, 0.06, "StabilityMKT!B5 coarse MKT mismatch"),
        ("a_hrs_8c", abs(_f(ja.get("worst_probe_hours_above_8c")) - QA_ORACLE["worst_probe_hours_above_8c"]) <= 0.55 and abs(_f(_cv("StabilityMKT", "B6")) - QA_ORACLE["worst_probe_hours_above_8c"]) <= 0.55, 0.07, "worst_probe_hours_above_8c mismatch"),
        ("a_disp", ja.get("batch_disposition") == QA_ORACLE["batch_disposition"] and str(_cv("StabilityMKT", "B7") or "") == QA_ORACLE["batch_disposition"], 0.06, "batch_disposition mismatch"),
        ("a_pay_floor", 13.60 <= pay_kg <= 16.40, 0.07, f"ULD_Summary!B3 vial_payload_kg={pay_kg} outside [13.60, 16.40]"),
        ("a_pay_committed", str(_cv("ULD_Summary", "C3") or "").upper() == "COMMITTED", 0.05, "ULD_Summary!C3 != COMMITTED"),
        ("a_pay_match", abs(_f(ja.get("vial_payload_kg")) - pay_kg) <= 0.03, 0.05, "JSON vs XLSX vial_payload_kg mismatch"),
        ("a_code", ja.get("lims_qa_code") == LIMS_QA_CODE and str(_cv("StabilityMKT", "B8") or "") == LIMS_QA_CODE, 0.07, "Wrong lims_qa_code"),
        ("a_odt_qa", LIMS_QA_CODE in odt_txt and "[CAPA-LOCK-114]" in odt_txt, 0.07, "Deviation_CAPA.odt missing LIMS_QA_CODE or header"),
        ("a_pkg_sheet_kept", bool(ja) and "PackagingThermal" in sheets, 0.05, "PackagingThermal sheet wiped"),
        ("a_sess_marker", bool(ja) and "SESSION-QA-994A" in json.dumps(sheets.get("ULD_Summary") or {}), 0.04, "ULD_Summary SESSION-QA-994A marker lost"),
        ("a_xlsx_probes", abs(_f(_cv("StabilityMKT", "B2")) - exp_pm["PRB-CORE-1"]) <= 0.90 and abs(_f(_cv("StabilityMKT", "B4")) - exp_pm["PRB-DOOR-3"]) <= 1.20, 0.05, "StabilityMKT!B2..B4 probe MKTs incomplete"),
    ]

    lm = jb.get("leg_sublimation_kg") if isinstance(jb.get("leg_sublimation_kg"), dict) else {}
    exp_lm = PKG_ORACLE["leg_sublimation_kg"]
    leg_hits = sum(1 for k, v in exp_lm.items() if abs(_f(lm.get(k)) - v) <= 0.04)
    leg_coarse = sum(1 for k, v in exp_lm.items() if abs(_f(lm.get(k)) - v) <= 0.85)

    # 17 subchecks Role B
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.05, "Missing packaging_pi954_qualification.json"),
        ("b_legs_3plus", leg_coarse >= 3, 0.06, f"leg_sublimation_kg coarse hits {leg_coarse}/4"),
        ("b_legs_all4_exact", leg_hits == 4, 0.09, "leg_sublimation_kg exact 4/4 missed (check uld_fleet_maintenance.sqlite +6% VIP aging & +4.5C apron)"),
        ("b_tot_sub_coarse", abs(_f(jb.get("total_4leg_sublimation_kg")) - PKG_ORACLE["total_4leg_sublimation_kg"]) <= 2.0 and abs(_f(_cv("PackagingThermal", "B6")) - PKG_ORACLE["total_4leg_sublimation_kg"]) <= 2.0, 0.07, "total_4leg_sublimation_kg coarse mismatch"),
        ("b_min_ice_exact", abs(_f(jb.get("minimum_qualified_dry_ice_kg")) - min_ice_req) <= 0.06 and abs(_f(_cv("PackagingThermal", "B7")) - min_ice_req) <= 0.06, 0.10, f"minimum_qualified_dry_ice_kg != {min_ice_req} (check uld_fleet_maintenance.sqlite +6% VIP aging & +1.35kg flash loss)"),
        ("b_ice_floor", (min_ice_req - 3.60) <= ice_kg <= min_ice_req + 3.50, 0.07, f"ULD_Summary!B4 dry_ice_charge_kg={ice_kg} out of range"),
        ("b_ice_committed", str(_cv("ULD_Summary", "C4") or "").upper() == "COMMITTED", 0.05, "ULD_Summary!C4 != COMMITTED"),
        ("b_ice_match", abs(_f(jb.get("dry_ice_charge_kg")) - ice_kg) <= 0.03, 0.05, "JSON vs XLSX dry_ice_charge_kg mismatch"),
        ("b_xlsx_legs", abs(_f(_cv("PackagingThermal", "B4")) - exp_lm["LEG-3-ANC-FLIGHT"]) <= 0.85, 0.06, "PackagingThermal!B4 LEG-3 flight sublimation mismatch"),
        ("b_sum_formula", "SUM(B2:B5)" in str(((sheets.get("PackagingThermal") or {}).get("B6") or {}).get("formula") or "").upper(), 0.05, "PackagingThermal!B6 missing =SUM(B2:B5)"),
        ("b_code", jb.get("lims_pkg_code") == LIMS_PKG_CODE and str(_cv("PackagingThermal", "B8") or "") == LIMS_PKG_CODE, 0.08, "Wrong lims_pkg_code"),
        ("b_odt_pkg", LIMS_PKG_CODE in odt_txt and "[CAPA-LOCK-114]" in odt_txt, 0.08, "Deviation_CAPA.odt missing LIMS_PKG_CODE or header"),
        ("b_stab_kept", bool(jb) and "StabilityMKT" in sheets, 0.05, "StabilityMKT sheet wiped"),
        ("b_sess_marker", bool(jb) and "SESSION-QA-994A" in json.dumps(sheets.get("ULD_Summary") or {}), 0.04, "ULD_Summary marker lost"),
        ("b_not_unfactored_leg3", bool(jb) and abs(_f(lm.get("LEG-3-ANC-FLIGHT")) - (exp_lm["LEG-3-ANC-FLIGHT"] / 1.18)) > 0.2, 0.05, "Forgot 1.18x cruise depressurization factor"),
        ("b_uld_formula", "SUM(B2:B4)" in str(((sheets.get("ULD_Summary") or {}).get("B5") or {}).get("formula") or "").upper(), 0.03, "ULD_Summary!B5 =SUM(B2:B4) formula lost"),
        ("b_tare_620", abs(_f(_cv("ULD_Summary", "B2")) - 6.20) <= 0.01, 0.03, "Container tare 6.20 altered"),
    ]

    # 4 True Joint Coupling & Live Read-Only UNO Consistency Checks (17 + 17 + 4 = 38 subchecks)
    eff_pay = pay_kg if has_a else 13.60
    eff_ice = ice_kg if has_b else min_ice_req
    eff_gross = 6.20 + eff_pay + eff_ice
    floors_ok = ((not has_a) or (13.60 <= pay_kg <= 16.40)) and ((not has_b) or ((min_ice_req - 3.60) <= ice_kg <= min_ice_req + 3.50))
    active_submitted = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))
    capa_ok = ((not has_a) or (LIMS_QA_CODE in odt_txt)) and ((not has_b) or (LIMS_PKG_CODE in odt_txt))
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_iata_gross_cap", floors_ok and (eff_gross <= IATA_GROSS_CAP_KG), 0.09, f"Coupled IATA Gross Mass {eff_gross:.2f} kg exceeds {IATA_GROSS_CAP_KG:.2f} kg cap (or subsystem below floor)!"),
        ("j_uno_calc_synced", active_submitted and uno_calc_ok, 0.07, "Live LibreOffice Calc UNO buffer out-of-sync with disk .xlsx"),
        ("j_uno_writer_synced", active_submitted and uno_writer_ok, 0.07, "Live LibreOffice Writer UNO buffer out-of-sync with disk CAPA .odt"),
        ("j_capa_dual_signoff", capa_ok, 0.07, "Deviation_CAPA.odt missing required QA / Packaging signoff"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=1.0,
    )


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    assert role in ("biologics_stability_qa", "packaging_thermal_eng")
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", ws / "shared_docs")
    xlsx_p = hub / "ColdChain_Qualification.xlsx"
    odt_p = hub / "Deviation_CAPA_2026_114.odt"

    if role == "biologics_stability_qa":
        pm = QA_ORACLE["probe_mkt_celsius"]
        min_ice = PKG_ORACLE["minimum_qualified_dry_ice_kg"]
        with file_atomic_lock("nf11_shared_docs"):
            shs = read_multisheet_xlsx(xlsx_p)
            cur_ice = float(((shs.get("ULD_Summary") or {}).get("B4") or {}).get("value") or 0.0)
            cur_ice_st = str(((shs.get("ULD_Summary") or {}).get("C4") or {}).get("value") or "PENDING")
            max_pay = (IATA_GROSS_CAP_KG - 6.20 - cur_ice - 0.05) if cur_ice_st == "COMMITTED" else (IATA_GROSS_CAP_KG - 6.20 - min_ice - 0.55)
            pay = round(max(13.60, min(14.30, max_pay)), 2)
            update_single_sheet_xlsx(
                xlsx_p,
                "ULD_Summary",
                [
                    ["Component", "Mass_kg", "SESSION-QA-994A"],
                    ["Container_Tare_kg", 6.20, "FIXED"],
                    ["Vial_Payload_kg", pay, "COMMITTED"],
                    ["Dry_Ice_Charge_kg", cur_ice, cur_ice_st],
                    ["Gross_Shipper_Mass_kg", ("=SUM(B2:B4)", round(6.20 + pay + cur_ice, 2)), "QUALIFIED"],
                ],
            )
            update_single_sheet_xlsx(
                xlsx_p,
                "StabilityMKT",
                [
                    ["Metric", "Value"],
                    ["MKT_PRB_CORE_1", pm["PRB-CORE-1"]],
                    ["MKT_PRB_TOP_2", pm["PRB-TOP-2"]],
                    ["MKT_PRB_DOOR_3", pm["PRB-DOOR-3"]],
                    ["Worst_Probe_MKT_C", QA_ORACLE["worst_probe_mkt_c"]],
                    ["Worst_Probe_Hours_Above_8C", QA_ORACLE["worst_probe_hours_above_8c"]],
                    ["Batch_Disposition", QA_ORACLE["batch_disposition"]],
                    ["LIMS_QA_Code", LIMS_QA_CODE],
                ],
            )
            cur_txt = read_odt_plain_text(odt_p)
            paras = [("LINE", ln) for ln in cur_txt.splitlines() if ln.strip() and LIMS_QA_CODE not in ln]
            paras.append(("QA", f"QA_DISPOSITION: {QA_ORACLE['batch_disposition']} | {LIMS_QA_CODE} | Payload={pay}kg"))
            write_simple_odt(odt_p, "GMP Deviation CAPA-2026-114 — Biologics Lot mAb-994A", paras)
            reload_uno_pipe_documents([xlsx_p, odt_p])
        write_json(ws / "stability_mkt_decision.json", {**QA_ORACLE, "vial_payload_kg": pay})
    else:
        lm = PKG_ORACLE["leg_sublimation_kg"]
        min_ice = PKG_ORACLE["minimum_qualified_dry_ice_kg"]
        with file_atomic_lock("nf11_shared_docs"):
            shs = read_multisheet_xlsx(xlsx_p)
            cur_pay = float(((shs.get("ULD_Summary") or {}).get("B3") or {}).get("value") or 0.0)
            cur_pay_st = str(((shs.get("ULD_Summary") or {}).get("C3") or {}).get("value") or "PENDING")
            max_ice = (IATA_GROSS_CAP_KG - 6.20 - cur_pay - 0.05) if cur_pay_st == "COMMITTED" else (min_ice + 0.40)
            ice = round(max(min_ice, min(min_ice + 0.65, max_ice)), 2)
            update_single_sheet_xlsx(
                xlsx_p,
                "ULD_Summary",
                [
                    ["Component", "Mass_kg", "SESSION-QA-994A"],
                    ["Container_Tare_kg", 6.20, "FIXED"],
                    ["Vial_Payload_kg", cur_pay, cur_pay_st],
                    ["Dry_Ice_Charge_kg", ice, "COMMITTED"],
                    ["Gross_Shipper_Mass_kg", ("=SUM(B2:B4)", round(6.20 + cur_pay + ice, 2)), "QUALIFIED"],
                ],
            )
            update_single_sheet_xlsx(
                xlsx_p,
                "PackagingThermal",
                [
                    ["Metric", "Value"],
                    ["LEG-1-BSL-TRUCK", lm["LEG-1-BSL-TRUCK"]],
                    ["LEG-2-FRA-RAMP", lm["LEG-2-FRA-RAMP"]],
                    ["LEG-3-ANC-FLIGHT", lm["LEG-3-ANC-FLIGHT"]],
                    ["LEG-4-KIX-CUSTOMS", lm["LEG-4-KIX-CUSTOMS"]],
                    ["Total_Sublimation_kg", ("=SUM(B2:B5)", PKG_ORACLE["total_4leg_sublimation_kg"])],
                    ["Min_Qualified_DryIce_kg", min_ice],
                    ["LIMS_PKG_Code", LIMS_PKG_CODE],
                ],
            )
            cur_txt = read_odt_plain_text(odt_p)
            paras = [("LINE", ln) for ln in cur_txt.splitlines() if ln.strip() and LIMS_PKG_CODE not in ln]
            paras.append(("PKG", f"PI954_QUALIFIED: DryIce={ice}kg | {LIMS_PKG_CODE}"))
            write_simple_odt(odt_p, "GMP Deviation CAPA-2026-114 — Biologics Lot mAb-994A", paras)
            reload_uno_pipe_documents([xlsx_p, odt_p])
        write_json(ws / "packaging_pi954_qualification.json", {**PKG_ORACLE, "dry_ice_charge_kg": ice})


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4: Uncoordinated TOCTOU target allocations (14.30 + (min_ice+0.65) + 6.20 > cap) + CAPA overwrite."""
    solve_role("biologics_stability_qa", workspace_map, port)
    solve_role("packaging_pi954" if False else "packaging_thermal_eng", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    over_ice = round(PKG_ORACLE["minimum_qualified_dry_ice_kg"] + 0.65, 2)
    update_single_sheet_xlsx(
        hub / "ColdChain_Qualification.xlsx",
        "ULD_Summary",
        [
            ["Component", "Mass_kg", "SESSION-QA-994A"],
            ["Container_Tare_kg", 6.20, "FIXED"],
            ["Vial_Payload_kg", 14.30, "COMMITTED"],
            ["Dry_Ice_Charge_kg", over_ice, "COMMITTED"],
            ["Gross_Shipper_Mass_kg", ("=SUM(B2:B4)", round(6.20 + 14.30 + over_ice, 2)), "OVER_CAP"],
        ],
    )
    write_simple_odt(
        hub / "Deviation_CAPA_2026_114.odt",
        "GMP Deviation CAPA-2026-114 — Biologics Lot mAb-994A",
        [("CAPA_HDR", "[CAPA-LOCK-114]"), ("PKG", f"PI954_QUALIFIED: {LIMS_PKG_CODE}")],
    )
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["view_flips"] = int(st.get("view_flips", 0)) + 3
    write_json(sp, st)
