"""NF2-05: Native Qt5 Assistant (.qhc) Shared Documentation Filter Contention + LibreOffice Calc — Avionics ARINC-429 & Flight Gain."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    compile_qhc_collection,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_uno_documents_readonly,
    launch_libreoffice_uno_natural,
    launch_qt_assistant_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_uno_pipe_documents,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-05"
PORTAL_PORT = 19605

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Native `Qt5 Assistant` (`.qhc`) Multi-Manual Filter Contention & Live Calc: ARINC-429 Bus Decoding vs. Flight Gain Margins",
    "domain": "DO-254 Avionics ARINC-429 Bus Telemetry & Flight-Control Gain-Margin Verification (Qt5 Assistant + LibreOffice Calc)",
    "track": "track1_isolated_screen",
    "workspace_mode": "isolated",
    "roles": ("arinc429_bus_engineer", "flight_gain_analyst"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

ARINC_REVC_CODE = make_canary_code("DO254-REVC", "arinc429-bnr-32bit")
GAIN_REVC_CODE = make_canary_code("FCS-REVC", "bode-margin-cert")
ARINC_REVA_TRAP = "DO254-REVA-PROTOTYPE-001"
GAIN_REVA_TRAP = "FCS-REVA-PROTOTYPE-002"

# Rev-C Certified ARINC-429:
# Label 0205 (Baro-Corrected Altitude, ADR pitot-static): LSB = 2.0 ft (Rev-A Prototype had LSB = 4.0 ft!).
# Label 0210 (True Airspeed, ADR pitot-static): LSB = 0.0625 kt (1/16 kt).
# Label 0324 (Body Pitch, IRU inertial — unaffected by pitot icing!): LSB = 180.0 / 32768.0 deg, plus additive_boresight_corr_deg = -0.35 deg.
PITCH_MOUNT_OFFSET_DEG = -0.35


def _encode_arinc_word(label_oct: str, sdi: int, raw_signed_16: int, ssm: int, force_bad_parity: bool = False) -> int:
    # Bits 0..7: reversed label byte; bits 8..9: SDI; bits 10..25: 16-bit two's complement BNR; bits 26..28: sign/SSM; bit 31: odd parity
    lbl_val = int(label_oct, 8) & 0xFF
    dat16 = raw_signed_16 & 0xFFFF
    w = lbl_val | ((sdi & 0x3) << 8) | (dat16 << 10) | ((ssm & 0x7) << 26)
    ones = bin(w).count("1")
    parity_bit = 0 if (ones % 2 == 1) else 1  # Odd parity across all 32 bits!
    if force_bad_parity:
        parity_bit ^= 1
    return w | (parity_bit << 31)


def _generate_arinc_frames() -> list[dict[str, Any]]:
    rows = []
    for i in range(1, 541):
        mod3 = i % 3
        lbl = "0205" if mod3 == 1 else ("0324" if mod3 == 2 else "0210")
        bad_par = (i % 23 == 0)
        # SSM: 3 = Normal Operation (NO), 0 = Failure Warning (FW), 2 = Functional Test (FT)
        ssm = 0 if (i % 19 == 0) else (2 if (i % 31 == 0) else 3)
        # SDI == 3 (`0b11`) is cross-side loopback diagnostic echo — exclude from primary flight channel (`SDI in {1, 2}`)!
        sdi = 3 if (i % 17 == 0) else (2 if i % 2 == 0 else 1)
        pitot_fault = 1 if (i % 29 == 0) else 0
        if lbl == "0324":
            deg = 4.25 + 1.8 * math.sin(i * 0.21)
            raw16 = int(round(deg / (180.0 / 32768.0)))
        elif lbl == "0210":
            tas_kt = 445.0 + (i % 13) * 3.5
            raw16 = int(round(tas_kt / 0.0625))
        else:
            alt_ft = 31000.0 + (i % 15) * 140.0
            raw16 = int(round(alt_ft / 2.0))
        w32 = _encode_arinc_word(lbl, sdi, raw16, ssm, force_bad_parity=bad_par)
        rows.append({"frame_seq": i, "hex_word": f"0x{w32:08X}", "pitot_heater_fault": pitot_fault})
    return rows


def _generate_bode_channels() -> list[dict[str, Any]]:
    # 4 flight-control loops across 90 frequency sweep rows each (360 rows)
    # Category-I loops (PITCH_CAS, ROLL_SAS, YAW_DAMP): GM >= 6.0 dB, PM_eff >= 45.0 deg
    # Category-II autoland loop (AUTOLAND_GS): GM >= 8.0 dB, PM_eff >= 50.0 deg
    loops = [
        ("PITCH_CAS", 9.4, 68.5, 0.012, 0.006),
        ("ROLL_SAS",  8.1, 66.0, 0.014, 0.007),
        ("YAW_DAMP",  6.8, 58.0, 0.015, 0.008),
        ("AUTOLAND_GS", 7.6, 69.0, 0.012, 0.006),
    ]
    rows = []
    for l_idx, (lname, gm_db, pm_deg, _tz, _ts) in enumerate(loops):
        for k in range(1, 91):
            w_rad = round(0.5 + k * 0.45, 2)
            is_xover = (k == 38 + l_idx * 3)
            is_180 = (k == 64 + l_idx * 2)
            mag_db = 0.0 if is_xover else (-gm_db if is_180 else round(18.0 - 0.34 * k, 3))
            raw_phase_deg = (-180.0 + pm_deg) if is_xover else (-180.0 if is_180 else round(-45.0 - 2.1 * k, 3))
            rows.append({
                "row_id": len(rows) + 1, "loop_id": lname, "omega_rad_s": w_rad,
                "open_loop_mag_db": mag_db, "plant_phase_deg": raw_phase_deg,
                "sweep_flag": "VALID" if (k != 15) else "SATURATED_ACTUATOR",
            })
    return rows


def _compute_oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    frames = _generate_arinc_frames()
    parity_err = 0
    alts: list[float] = []
    tas_list: list[float] = []
    pitches: list[float] = []
    for r in frames:
        w = int(r["hex_word"], 16)
        if bin(w).count("1") % 2 == 0:
            parity_err += 1
            continue
        ssm = (w >> 26) & 0x7
        sdi = (w >> 8) & 0x3
        if ssm != 3 or sdi == 3:
            continue
        lbl = w & 0xFF
        raw_u = (w >> 10) & 0xFFFF
        raw_s = raw_u - 65536 if (raw_u & 0x8000) else raw_u
        if lbl == int("0205", 8):
            if r["pitot_heater_fault"] == 0:
                alts.append(raw_s * 2.0)
        elif lbl == int("0210", 8):
            if r["pitot_heater_fault"] == 0:
                tas_list.append(raw_s * 0.0625)
        elif lbl == int("0324", 8):
            # Inertial IRU channel is unaffected by ADR pitot_heater_fault!
            pitches.append(raw_s * (180.0 / 32768.0) + PITCH_MOUNT_OFFSET_DEG)
    or_a = {
        "parity_fault_count": parity_err,
        "valid_normal_op_count": len(alts) + len(tas_list) + len(pitches),
        "mean_baro_altitude_ft": round(sum(alts) / len(alts), 2),
        "mean_true_airspeed_kt": round(sum(tas_list) / len(tas_list), 2),
        "mean_calibrated_pitch_deg": round(sum(pitches) / len(pitches), 4),
        "arinc_manual_code": ARINC_REVC_CODE,
    }

    tau_zoh = {"PITCH_CAS": 0.012, "ROLL_SAS": 0.014, "YAW_DAMP": 0.015, "AUTOLAND_GS": 0.012}
    tau_srv = {"PITCH_CAS": 0.006, "ROLL_SAS": 0.007, "YAW_DAMP": 0.008, "AUTOLAND_GS": 0.006}
    req_gm = {"PITCH_CAS": 6.0, "ROLL_SAS": 6.0, "YAW_DAMP": 6.0, "AUTOLAND_GS": 8.0}
    req_pm = {"PITCH_CAS": 45.0, "ROLL_SAS": 45.0, "YAW_DAMP": 45.0, "AUTOLAND_GS": 50.0}
    brows = [r for r in _generate_bode_channels() if r["sweep_flag"] == "VALID"]
    pm_eff: dict[str, float] = {}
    gm_map: dict[str, float] = {}
    for r in brows:
        lid = r["loop_id"]
        if abs(r["open_loop_mag_db"]) < 1e-6:
            tot_lag_deg = r["omega_rad_s"] * (tau_zoh[lid] + tau_srv[lid]) * (180.0 / math.pi)
            pm_eff[lid] = round(180.0 + (r["plant_phase_deg"] - tot_lag_deg), 2)
        if abs(r["plant_phase_deg"] - (-180.0)) < 1e-6 and r["open_loop_mag_db"] < 0:
            gm_map[lid] = round(-r["open_loop_mag_db"], 2)
    non_comp = sorted(k for k in pm_eff if gm_map[k] < req_gm[k] or pm_eff[k] < req_pm[k])
    or_b = {
        "loop_gain_margin_db": gm_map,
        "loop_effective_phase_margin_deg": pm_eff,
        "min_effective_phase_margin_deg": min(pm_eff.values()),
        "noncompliant_loops": non_comp,
        "fcs_manual_code": GAIN_REVC_CODE,
    }
    return or_a, or_b


ARINC_ORACLE, GAIN_ORACLE = _compute_oracles()


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — ARINC-429 32-Bit Bus Frame Decoding & Parity Audit (`arinc429_bus_engineer`)",
        "",
        "## Objective",
        f"Switch the open **Qt Assistant** documentation browser (`avionics_manuals.qhc`) to the **BUS_ICD_ARINC429_REVC** subsystem filter in the Filter toolbar to consult all 3 certified ARINC-429 Rev-C ICD sections, decode `{b}/workspace/bus/arinc429_capture.sqlite{b}` per `{b}/workspace/docs/SOP_ARINC429.pdf{b}`, complete `{b}/workspace/ARINC429_Channel_Summary.xlsx{b}` (open in LibreOffice Calc), and write `{b}/workspace/arinc429_telemetry_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — MIL-F-9490D Flight-Control Gain & Phase Margin Close (`flight_gain_analyst`)",
        "",
        "## Objective",
        f"Switch the open **Qt Assistant** documentation browser (`avionics_manuals.qhc`) to the **FCS_BODE_MIL9490D_REVC** subsystem filter in the Filter toolbar to consult all 3 certified MIL-F-9490D Rev-C stability sections, analyze `{b}/workspace/fcs/bode_sweeps.sqlite{b}` per `{b}/workspace/docs/SOP_FCS_Margins.pdf{b}`, complete `{b}/workspace/Flight_Gain_Margins.xlsx{b}` (open in LibreOffice Calc), and write `{b}/workspace/fcs_margin_audit.json{b}`.",
    ])
    return {"arinc429_bus_engineer": ta, "flight_gain_analyst": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["arinc429_bus_engineer"]
    ws_b = workspace_map["flight_gain_analyst"]
    (ws_a / "bus").mkdir(parents=True, exist_ok=True)
    (ws_a / "docs").mkdir(parents=True, exist_ok=True)
    (ws_b / "fcs").mkdir(parents=True, exist_ok=True)
    (ws_b / "docs").mkdir(parents=True, exist_ok=True)

    qhc_dir = ws_a.parent / "qt_manuals"
    compile_qhc_collection(
        qhc_dir / "avionics_manuals.qhc",
        {
            "OVERVIEW_DIRECTORY": [
                (
                    "idx",
                    "00. Avionics Master Index — Select Rev-C Subsystem Filter in Toolbar",
                    "<h2>DO-254 / MIL-F-9490D Certified Documentation Collection</h2>"
                    "<p>Use the <b>Filter</b> dropdown toolbar at the top of Qt Assistant to select <b>BUS_ICD_ARINC429_REVC</b> or <b>FCS_BODE_MIL9490D_REVC</b>.</p>"
                    "<p><i>Warning:</i> Unfiltered view also lists retired <b>REV_A_PROTOTYPE_ARCHIVE</b> bench drafts — do NOT use Rev-A prototype scalings or codes for production release!</p>",
                ),
            ],
            "REV_A_PROTOTYPE_ARCHIVE": [
                (
                    "reva_bus",
                    "01. [RETIRED REV-A PROTOTYPE] ARINC-429 Preliminary ICD",
                    f"<h2>RETIRED REV-A PROTOTYPE BUS ICD</h2><p>Prototype Label 0205 LSB = <code>4.0 ft</code>; Label 0210 LSB = <code>0.125 kt</code>; SDI 1..3 accepted.</p><p>Retired Prototype Code: <code>{ARINC_REVA_TRAP}</code></p>",
                ),
                (
                    "reva_fcs",
                    "02. [RETIRED REV-A PROTOTYPE] Flight-Control Preliminary Margins",
                    f"<h2>RETIRED REV-A PROTOTYPE FCS CRITERIA</h2><p>Uniform GM &gt;= <code>4.5 dB</code>, PM &gt;= <code>38.0 deg</code> (ZOH lag only).</p><p>Retired Prototype Code: <code>{GAIN_REVA_TRAP}</code></p>",
                ),
            ],
            "BUS_ICD_ARINC429_REVC": [
                (
                    "arinc_word",
                    "1. ARINC-429 Rev-C 32-Bit Word Format & ADR/IRU Hygiene",
                    "<h2>Section 1 — 32-Bit Word Packing & Subsystem Fault Hygiene</h2>"
                    "<ul>"
                    "<li><b>Bits [7:0]</b>: Octal label (<code>0205</code> Baro-Corrected Altitude, <code>0210</code> True Airspeed, <code>0324</code> Body Pitch).</li>"
                    "<li><b>Bits [9:8]</b>: SDI — retain active flight channels <code>SDI in {1, 2}</code>; exclude <code>SDI == 3</code> cross-side loopback echo.</li>"
                    "<li><b>Bits [25:10]</b>: 16-bit signed two's-complement BNR payload (<code>raw_s = raw_u - 65536 if raw_u &gt;= 32768 else raw_u</code>).</li>"
                    "<li><b>Bits [28:26]</b>: SSM — retain <code>SSM == 3</code> (Normal Operation); reject <code>0</code> (Failure Warning) and <code>2</code> (Functional Test).</li>"
                    "<li><b>Bit [31]</b>: Odd Parity across all 32 bits (total set bits in the 32-bit word must be odd; otherwise count in <code>parity_fault_count</code> and discard).</li>"
                    "<li><b>ADR Pitot-Heater Fault Rule</b>: Join <code>airdata_pitot_flags</code> on <code>frame_seq</code>. Frames with <code>pitot_heater_fault == 1</code> invalidate Air-Data labels <code>0205</code> and <code>0210</code> (exclude them from <code>valid_normal_op_count</code> and means), whereas Inertial IRU Pitch label <code>0324</code> does not use pitot pressure and remains valid!</li>"
                    "</ul>",
                ),
                (
                    "arinc_scale",
                    "2. ARINC-429 Rev-C BNR Scaling & Additive Boresight Convention",
                    "<h2>Section 2 — Rev-C BNR Engineering Units & Calibration</h2>"
                    "<ul>"
                    "<li><b>Label 0205 (Baro Altitude)</b>: <code>altitude_ft = raw_s * 2.0</code>.</li>"
                    "<li><b>Label 0210 (True Airspeed)</b>: <code>tas_kt = raw_s * 0.0625</code>.</li>"
                    "<li><b>Label 0324 (Body Pitch)</b>: <code>pitch_raw_deg = raw_s * (180.0 / 32768.0)</code>; apply additive IRU mount calibration from <code>iru_mount_boresight_cal</code>: <code>pitch_calibrated_deg = pitch_raw_deg + additive_boresight_corr_deg</code>.</li>"
                    "</ul>",
                ),
                (
                    "arinc_cert",
                    "3. ARINC-429 Rev-C Production Release Signoff Code",
                    f"<h2>Section 3 — DO-254 Rev-C Release Certificate</h2><p>Certified Production ICD Code (<code>arinc_manual_code</code>): <strong>{ARINC_REVC_CODE}</strong></p>",
                ),
            ],
            "FCS_BODE_MIL9490D_REVC": [
                (
                    "fcs_xover",
                    "1. MIL-F-9490D Rev-C Open-Loop Crossover Extraction",
                    "<h2>Section 1 — Valid Sweep Filtering & Crossover Points</h2>"
                    "<p>Filter <code>frequency_sweeps</code> to <code>sweep_flag = 'VALID'</code> (exclude <code>SATURATED_ACTUATOR</code>). For each loop, Gain Margin <code>GM_dB = -open_loop_mag_db</code> at the <code>plant_phase_deg == -180.0</code> crossover, and Effective Phase Margin is evaluated at the <code>open_loop_mag_db == 0.0</code> gain crossover.</p>",
                ),
                (
                    "fcs_lag",
                    "2. MIL-F-9490D Rev-C Combined Digital ZOH & Servo Transport Lag",
                    "<h2>Section 2 — Total High-Frequency Phase Lag Model</h2>"
                    "<p>At each loop's <code>0.0 dB</code> gain crossover frequency <code>omega_rad_s</code>, combine digital ZOH computational delay (<code>fcc_digital_zoh_delay.tau_zoh_sec</code>) AND electro-hydraulic servo valve lag (<code>actuator_servo_lags.tau_servo_sec</code>):</p>"
                    "<p><code>total_lag_deg = omega_rad_s * (tau_zoh_sec + tau_servo_sec) * (180.0 / pi)</code><br/>"
                    "<code>PM_eff_deg = round(180.0 + (plant_phase_deg - total_lag_deg), 2)</code></p>",
                ),
                (
                    "fcs_cat",
                    "3. MIL-F-9490D Rev-C Category-I vs Category-II Loop Thresholds & Code",
                    "<h2>Section 3 — Stability Thresholds by Flight-Phase Category</h2>"
                    "<ul>"
                    "<li><b>Category-I Primary Inner Loops</b> (<code>PITCH_CAS</code>, <code>ROLL_SAS</code>, <code>YAW_DAMP</code>): require <code>GM &gt;= 6.00 dB</code> AND <code>PM_eff &gt;= 45.00 deg</code>.</li>"
                    "<li><b>Category-II Coupled Automatic Landing</b> (<code>AUTOLAND_GS</code>): requires <code>GM &gt;= 8.00 dB</code> AND <code>PM_eff &gt;= 50.00 deg</code>!</li>"
                    "</ul>"
                    "<p>Any loop failing either its GM or PM_eff threshold belongs to <code>noncompliant_loops</code>.</p>"
                    f"<p>Certified FCS Manual Code (<code>fcs_manual_code</code>): <strong>{GAIN_REVC_CODE}</strong></p>",
                ),
            ],
        },
    )

    with sqlite3.connect(str(ws_a / "bus/arinc429_capture.sqlite")) as conn:
        conn.execute("CREATE TABLE raw_bus_words (frame_seq INTEGER PRIMARY KEY, hex_word TEXT)")
        conn.execute("CREATE TABLE airdata_pitot_flags (frame_seq INTEGER PRIMARY KEY, pitot_heater_fault INTEGER)")
        for r in _generate_arinc_frames():
            conn.execute("INSERT INTO raw_bus_words VALUES (?,?)", (r["frame_seq"], r["hex_word"]))
            conn.execute("INSERT INTO airdata_pitot_flags VALUES (?,?)", (r["frame_seq"], r["pitot_heater_fault"]))
        conn.execute("CREATE TABLE iru_mount_boresight_cal (label_oct TEXT PRIMARY KEY, additive_boresight_corr_deg REAL)")
        conn.execute("INSERT INTO iru_mount_boresight_cal VALUES ('0324', -0.35)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_ARINC429.pdf", "SOP-AVN-505A: ARINC-429 Frame Integrity & Calibration", [
        ("1. Odd-Parity, SSM Filtering & BNR Decoding", [
            "1.1 In Qt Assistant, select filter BUS_ICD_ARINC429_REVC and consult all 3 Rev-C sections. Decode /workspace/bus/arinc429_capture.sqlite enforcing 32-bit odd parity, SDI/SSM channel rules, ADR pitot-heater fault filtering (airdata_pitot_flags), Rev-C BNR LSB scalings, and additive IRU boresight pitch calibration.",
            "1.2 Populate /workspace/ARINC429_Channel_Summary.xlsx Sheet 'BusSummary' (B2 = parity_fault_count, B3 = valid_normal_op_count, B4 = mean_baro_altitude_ft, B5 = mean_true_airspeed_kt, B6 = mean_calibrated_pitch_deg, B7 = arinc_manual_code; preserve Control!B2 = 'ARINC-BENCH-05' and save cleanly in LibreOffice Calc).",
        ]),
        ("2. JSON Schema (/workspace/arinc429_telemetry_audit.json)", [
            "Keys: parity_fault_count (int), valid_normal_op_count (int), mean_baro_altitude_ft (float, 2 dec), mean_true_airspeed_kt (float, 2 dec), mean_calibrated_pitch_deg (float, 4 dec), arinc_manual_code (str).",
        ]),
    ])
    write_multisheet_xlsx(ws_a / "ARINC429_Channel_Summary.xlsx", [
        ("Control", [["Item", "Marker"], ["BenchID", "ARINC-BENCH-05"]]),
        ("BusSummary", [
            ["Metric", "Value"],
            ["Parity_Fault_Count", 0],
            ["Valid_Normal_Op_Count", 0],
            ["Mean_Baro_Altitude_ft", 0.0],
            ["Mean_True_Airspeed_kt", 0.0],
            ["Mean_Calibrated_Pitch_deg", 0.0],
            ["Manual_Code", "PENDING"],
        ]),
    ])

    with sqlite3.connect(str(ws_b / "fcs/bode_sweeps.sqlite")) as conn:
        conn.execute("CREATE TABLE frequency_sweeps (row_id INTEGER PRIMARY KEY, loop_id TEXT, omega_rad_s REAL, open_loop_mag_db REAL, plant_phase_deg REAL, sweep_flag TEXT)")
        for r in _generate_bode_channels():
            conn.execute("INSERT INTO frequency_sweeps VALUES (?,?,?,?,?,?)", (r["row_id"], r["loop_id"], r["omega_rad_s"], r["open_loop_mag_db"], r["plant_phase_deg"], r["sweep_flag"]))
        conn.execute("CREATE TABLE fcc_digital_zoh_delay (loop_id TEXT PRIMARY KEY, tau_zoh_sec REAL)")
        for k, v in [("PITCH_CAS", 0.012), ("ROLL_SAS", 0.014), ("YAW_DAMP", 0.015), ("AUTOLAND_GS", 0.012)]:
            conn.execute("INSERT INTO fcc_digital_zoh_delay VALUES (?,?)", (k, v))
        conn.execute("CREATE TABLE actuator_servo_lags (loop_id TEXT PRIMARY KEY, tau_servo_sec REAL)")
        for k, v in [("PITCH_CAS", 0.006), ("ROLL_SAS", 0.007), ("YAW_DAMP", 0.008), ("AUTOLAND_GS", 0.006)]:
            conn.execute("INSERT INTO actuator_servo_lags VALUES (?,?)", (k, v))
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_FCS_Margins.pdf", "SOP-AVN-505B: Flight-Control Bode Margin Audit", [
        ("1. Gain & Effective Phase Margin Evaluation", [
            "1.1 In Qt Assistant, select filter FCS_BODE_MIL9490D_REVC and consult all 3 Rev-C sections. Using valid open-loop sweep rows in /workspace/fcs/bode_sweeps.sqlite (combining ZOH delay and actuator servo lag, and applying Category-I vs Category-II loop thresholds), populate Flight_Gain_Margins.xlsx and /workspace/fcs_margin_audit.json.",
            "1.2 Workbook Sheet 'LoopMargins': rows 2..5 = PITCH_CAS, ROLL_SAS, YAW_DAMP, AUTOLAND_GS with B2:B5 = GainMargin_dB and C2:C5 = EffPhaseMargin_deg; C6 = '=MIN(C2:C5)'; C7 = fcs_manual_code. Preserve Control!B2 = 'FCS-BENCH-05' and save in Calc.",
        ]),
        ("2. JSON Schema (/workspace/fcs_margin_audit.json)", [
            "Keys: loop_gain_margin_db (dict), loop_effective_phase_margin_deg (dict), min_effective_phase_margin_deg (float, 2 dec), noncompliant_loops (sorted list[str]), fcs_manual_code (str).",
        ]),
    ])
    write_multisheet_xlsx(ws_b / "Flight_Gain_Margins.xlsx", [
        ("Control", [["Item", "Marker"], ["BenchID", "FCS-BENCH-05"]]),
        ("LoopMargins", [
            ["Loop_ID", "GainMargin_dB", "EffPhaseMargin_deg"],
            ["PITCH_CAS", 0.0, 0.0], ["ROLL_SAS", 0.0, 0.0], ["YAW_DAMP", 0.0, 0.0], ["AUTOLAND_GS", 0.0, 0.0],
            ["Min_PhaseMargin", "", ("=MIN(C2:C5)", 0.0)],
            ["Manual_Code", "", "PENDING"],
        ]),
    ])
    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID})

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            if self.path.startswith("/health"):
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}'); return
            self.send_response(404); self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/health\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del state_dir
    roles = set(active_roles or META["roles"])
    qhc = workspace_map["arinc429_bus_engineer"].parent / "qt_manuals/avionics_manuals.qhc"
    launch_qt_assistant_natural(qhc)
    docs: list[Path] = []
    if "arinc429_bus_engineer" in roles:
        docs.append(workspace_map["arinc429_bus_engineer"] / "ARINC429_Channel_Summary.xlsx")
    if "flight_gain_analyst" in roles:
        docs.append(workspace_map["flight_gain_analyst"] / "Flight_Gain_Margins.xlsx")
    if docs:
        launch_libreoffice_uno_natural(docs)


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("arinc429_bus_engineer" in act), ("flight_gain_analyst" in act)
    ws_a = workspace_map["arinc429_bus_engineer"]
    ws_b = workspace_map["flight_gain_analyst"]
    ja = read_json_safe(ws_a / "arinc429_telemetry_audit.json")
    jb = read_json_safe(ws_b / "fcs_margin_audit.json")
    uno_st = inspect_live_uno_documents_readonly()

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    xp_a = ws_a / "ARINC429_Channel_Summary.xlsx"
    shs_a = read_multisheet_xlsx(xp_a) if xp_a.is_file() else {}
    calc_sync_a = True
    if has_a:
        for u_url, u_doc in (uno_st.get("docs") or {}).items():
            if "ARINC429_Channel_Summary.xlsx" in u_url:
                calc_sync_a = (not u_doc.get("is_modified")) and (ARINC_REVC_CODE in json.dumps(u_doc.get("sheets") or {}))

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing arinc429_telemetry_audit.json"),
        ("a_par_cnt", ja.get("parity_fault_count") == ARINC_ORACLE["parity_fault_count"], 0.12, f"parity_fault_count != {ARINC_ORACLE['parity_fault_count']} (check 32-bit odd parity)"),
        ("a_ssm_pitot_cnt", ja.get("valid_normal_op_count") == ARINC_ORACLE["valid_normal_op_count"], 0.16, f"valid_normal_op_count != {ARINC_ORACLE['valid_normal_op_count']} (exclude pitot_heater_fault=1 on ADR 0205/0210 only, keep IRU 0324)"),
        ("a_alt_tas", abs(_f(ja.get("mean_baro_altitude_ft")) - ARINC_ORACLE["mean_baro_altitude_ft"]) <= 0.8 and abs(_f(ja.get("mean_true_airspeed_kt")) - ARINC_ORACLE["mean_true_airspeed_kt"]) <= 0.15, 0.16, "mean_baro_altitude_ft or mean_true_airspeed_kt mismatch (Rev-A LSB trap or pitot filter)"),
        ("a_code", ja.get("arinc_manual_code") == ARINC_REVC_CODE and ja.get("arinc_manual_code") != ARINC_REVA_TRAP, 0.16, "Wrong arinc_manual_code (Qt Assistant filter flipped from BUS_ICD_ARINC429_REVC?)"),
        ("a_xlsx_sync", bool(ja) and calc_sync_a and "ARINC-BENCH-05" in json.dumps(shs_a.get("Control") or {}), 0.12, "ARINC429_Channel_Summary.xlsx out-of-sync in open Calc or Control!B2 lost"),
        ("a_fine_boresight_pitch", abs(_f(ja.get("mean_calibrated_pitch_deg")) - ARINC_ORACLE["mean_calibrated_pitch_deg"]) <= 0.002, 0.20, f"mean_calibrated_pitch_deg != {ARINC_ORACLE['mean_calibrated_pitch_deg']} (check additive_boresight_corr_deg -0.35 on IRU 0324)"),
    ]

    xp = ws_b / "Flight_Gain_Margins.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    calc_sync = True
    if has_b:
        for u_url, u_doc in (uno_st.get("docs") or {}).items():
            if "Flight_Gain_Margins.xlsx" in u_url:
                calc_sync = (not u_doc.get("is_modified")) and (GAIN_REVC_CODE in json.dumps(u_doc.get("sheets") or {}))

    pm = jb.get("loop_effective_phase_margin_deg") if isinstance(jb.get("loop_effective_phase_margin_deg"), dict) else {}
    exp_pm = GAIN_ORACLE["loop_effective_phase_margin_deg"]
    pm_exact = sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 0.08)

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.06, "Missing fcs_margin_audit.json"),
        ("b_gm", jb.get("loop_gain_margin_db") == GAIN_ORACLE["loop_gain_margin_db"], 0.12, "loop_gain_margin_db mismatch"),
        ("b_pm_coarse", sum(1 for k, v in exp_pm.items() if abs(_f(pm.get(k)) - v) <= 12.0) == 4, 0.10, "Phase margins coarse off"),
        ("b_code", jb.get("fcs_manual_code") == GAIN_REVC_CODE and jb.get("fcs_manual_code") != GAIN_REVA_TRAP, 0.14, "Wrong fcs_manual_code (Qt Assistant left on REV_A_PROTOTYPE?)"),
        ("b_xlsx_min_f", "MIN(C2:C5)" in str(((shs.get("LoopMargins") or {}).get("C6") or {}).get("formula") or "").upper(), 0.10, "LoopMargins!C6 =MIN(C2:C5) lost"),
        ("b_ctrl_kept", "FCS-BENCH-05" in json.dumps(shs.get("Control") or {}), 0.05, "Control!B2 lost"),
        ("b_uno_sync", bool(jb) and calc_sync, 0.09, "Open Calc window out-of-sync with disk .xlsx"),
        ("b_fine_zoh_servo_pm", pm_exact == 4 and abs(_f(((evs.get("LoopMargins") or {}).get("C6") or {}).get("value")) - GAIN_ORACLE["min_effective_phase_margin_deg"]) <= 0.15, 0.17, "Missed combined tau_zoh_sec + tau_servo_sec lag on phase margins"),
        ("b_fine_cat2_noncomp", sorted(jb.get("noncompliant_loops") or []) == GAIN_ORACLE["noncompliant_loops"], 0.17, f"noncompliant_loops != {GAIN_ORACLE['noncompliant_loops']} (check Category-II AUTOLAND_GS GM>=8 dB / PM>=50 deg)"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=None, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    if role == "arinc429_bus_engineer":
        xp_a = ws / "ARINC429_Channel_Summary.xlsx"
        write_multisheet_xlsx(xp_a, [
            ("Control", [["Item", "Marker"], ["BenchID", "ARINC-BENCH-05"]]),
            ("BusSummary", [
                ["Metric", "Value"],
                ["Parity_Fault_Count", ARINC_ORACLE["parity_fault_count"]],
                ["Valid_Normal_Op_Count", ARINC_ORACLE["valid_normal_op_count"]],
                ["Mean_Baro_Altitude_ft", ARINC_ORACLE["mean_baro_altitude_ft"]],
                ["Mean_True_Airspeed_kt", ARINC_ORACLE["mean_true_airspeed_kt"]],
                ["Mean_Calibrated_Pitch_deg", ARINC_ORACLE["mean_calibrated_pitch_deg"]],
                ["Manual_Code", ARINC_REVC_CODE],
            ]),
        ])
        with file_atomic_lock("nf205_uno"):
            reload_uno_pipe_documents([xp_a])
        write_json(ws / "arinc429_telemetry_audit.json", ARINC_ORACLE)
    else:
        xp = ws / "Flight_Gain_Margins.xlsx"
        gm = GAIN_ORACLE["loop_gain_margin_db"]
        pm = GAIN_ORACLE["loop_effective_phase_margin_deg"]
        write_multisheet_xlsx(xp, [
            ("Control", [["Item", "Marker"], ["BenchID", "FCS-BENCH-05"]]),
            ("LoopMargins", [
                ["Loop_ID", "GainMargin_dB", "EffPhaseMargin_deg"],
                ["PITCH_CAS", gm["PITCH_CAS"], pm["PITCH_CAS"]],
                ["ROLL_SAS", gm["ROLL_SAS"], pm["ROLL_SAS"]],
                ["YAW_DAMP", gm["YAW_DAMP"], pm["YAW_DAMP"]],
                ["AUTOLAND_GS", gm["AUTOLAND_GS"], pm["AUTOLAND_GS"]],
                ["Min_PhaseMargin", "", ("=MIN(C2:C5)", GAIN_ORACLE["min_effective_phase_margin_deg"])],
                ["Manual_Code", "", GAIN_REVC_CODE],
            ]),
        ])
        with file_atomic_lock("nf205_uno"):
            reload_uno_pipe_documents([xp])
        write_json(ws / "fcs_margin_audit.json", GAIN_ORACLE)


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("arinc429_bus_engineer", workspace_map, port)
    solve_role("flight_gain_analyst", workspace_map, port)
    # Qt Assistant filter flipped to REV_A_PROTOTYPE -> Role A gets 2x altitude & REV-A code
    ja = read_json_safe(workspace_map["arinc429_bus_engineer"] / "arinc429_telemetry_audit.json")
    ja["arinc_manual_code"] = ARINC_REVA_TRAP
    ja["mean_baro_altitude_ft"] = round(ja["mean_baro_altitude_ft"] * 2.0, 2)
    write_json(workspace_map["arinc429_bus_engineer"] / "arinc429_telemetry_audit.json", ja)
    update_single_sheet_xlsx(workspace_map["flight_gain_analyst"] / "Flight_Gain_Margins.xlsx", "LoopMargins", [
        ["Loop_ID", "GainMargin_dB", "EffPhaseMargin_deg"],
        ["PITCH_CAS", 0.0, 0.0],
    ])
