"""NF2-13: Live QGIS 3.22 Shared SpatiaLite Geodatabase + Open Calc — Solar PV Hosting vs. EV Depot N-1 Substation MVA Cap."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_qgis_readonly,
    inspect_live_uno_documents_readonly,
    launch_libreoffice_uno_natural,
    launch_qgis_gui_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_qgis_gui_project,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-13"
PORTAL_PORT = 19613

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `QGIS 3.22` Shared `SpatiaLite` Geodatabase & Open Calc: Community Solar PV vs. EV Fleet Depot `N-1` Substation MVA Cap",
    "domain": "Electric Utility Distribution GIS (`QGIS 3.22` + `SpatiaLite`) & Feeder Interconnection Planning (`LibreOffice Calc`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("community_solar_gis_eng", "ev_depot_charging_planner"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

IEEE1547_PV_CODE = make_canary_code("IEEE1547", "pv-voltvar-qgis")
IEEE519_EV_CODE = make_canary_code("IEEE519", "dcfc-harmonic-mva")
# Substation N-1 cap = 37.80 MVA (Base = 6.40 MVA).
# Pre-study XLSX baseline: Solar = 14.80 (PRE_STUDY), EV = 16.20 (PRE_STUDY).
# Solo A commits preferred 15.12 MVA (6.40 + 15.12 + 16.20 = 37.72 <= 37.80);
# Role B IEEE 519 harmonic audit raises EV_FLOOR_MVA to 16.50 MVA (preferred 16.56; solo B: 6.40 + 14.80 + 16.56 = 37.76 <= 37.80);
# Concurrent shared: 6.40 + 15.12 + 16.50 = 38.02 > 37.80 MVA!
SUBSTATION_MVA_CAP = 37.80
BASE_FEEDER_MVA = 6.40
PV_FLOOR_MVA = 14.80
PRE_STUDY_EV_MVA = 16.20
EV_FLOOR_MVA = 16.50


def _build_gis_corridors_and_queue() -> tuple[dict[str, Any], dict[str, Any], set[str], set[str]]:
    # Three 13.8kV 3-phase trunk lines running West-East at lat 42.650, 42.670, 42.690 (lon -73.820..-73.720),
    # plus one 4.16kV single-phase lateral at lat 42.625 (cannot host 3-phase DER or DCFC!).
    # At lat 42.67 deg, 0.001 deg lat ~= 111.1 m; 0.006 deg lat ~= 667 m (well clear of 350 m / 250 m thresholds!).
    corridors = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"feeder_id": "FDR-N01", "voltage_class": "13.8kV_3PH"}, "geometry": {"type": "LineString", "coordinates": [[-73.820, 42.650], [-73.720, 42.650]]}},
            {"type": "Feature", "properties": {"feeder_id": "FDR-N02", "voltage_class": "13.8kV_3PH"}, "geometry": {"type": "LineString", "coordinates": [[-73.820, 42.670], [-73.720, 42.670]]}},
            {"type": "Feature", "properties": {"feeder_id": "FDR-N03", "voltage_class": "13.8kV_3PH"}, "geometry": {"type": "LineString", "coordinates": [[-73.820, 42.690], [-73.720, 42.690]]}},
            {"type": "Feature", "properties": {"feeder_id": "LAT-S04", "voltage_class": "4.16kV_1PH"}, "geometry": {"type": "LineString", "coordinates": [[-73.820, 42.625], [-73.720, 42.625]]}},
        ],
    }
    base_lats = {"FDR-N01": 42.650, "FDR-N02": 42.670, "FDR-N03": 42.690}
    q_feats: list[dict[str, Any]] = []
    elig_pv_q: set[str] = set()
    elig_ev_q: set[str] = set()

    # 18 SOLAR_PV queue entries on the shared interconnection_queue layer:
    # k=1..12: near 13.8kV_3PH (~135 m offset), wetland_buffer=0 -> APPROVED_PV (12 sites)
    # k=13..15: wetland_buffer=1 -> REJECTED
    # k=16..17: >680 m away from 13.8kV_3PH (>350 m limit) -> REJECTED
    # k=18: 80 m from 4.16kV_1PH lateral (~2780 m from 13.8kV_3PH) -> REJECTED
    for k in range(1, 19):
        qid = f"PV-{k:02d}"
        fdr = ("FDR-N01", "FDR-N02", "FDR-N03")[(k - 1) % 3]
        lon = round(-73.808 + k * 0.0042, 6)
        wet = 1 if (13 <= k <= 15) else 0
        if k <= 15:
            lat = round(base_lats[fdr] + 0.0012, 6)
        elif k <= 17:
            lat = round(base_lats[fdr] + 0.0062, 6)
        else:
            lat = 42.6257
        if k <= 12:
            elig_pv_q.add(qid)
        q_feats.append({
            "type": "Feature",
            "properties": {"queue_id": qid, "program_type": "SOLAR_PV", "feeder_id": fdr, "wetland_buffer": wet, "transformer_bay_ok": 0, "queue_status": "PENDING"},
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    # 14 EV_DCFC queue entries on the EXACT SAME shared interconnection_queue layer:
    # k=1..9: near 13.8kV_3PH (~110 m offset), transformer_bay_ok=1 -> APPROVED_EV (9 sites)
    # k=10..11: transformer_bay_ok=0 -> REJECTED
    # k=12..13: >560 m away from 13.8kV_3PH (>250 m limit) -> REJECTED
    # k=14: 70 m from 4.16kV_1PH lateral -> REJECTED
    for k in range(1, 15):
        qid = f"EV-{k:02d}"
        fdr = ("FDR-N01", "FDR-N02", "FDR-N03")[(k - 1) % 3]
        lon = round(-73.804 + k * 0.0052, 6)
        bay = 0 if (10 <= k <= 11) else 1
        if k <= 11:
            lat = round(base_lats[fdr] - 0.0010, 6)
        elif k <= 13:
            lat = round(base_lats[fdr] - 0.0052, 6)
        else:
            lat = 42.6244
        if k <= 9:
            elig_ev_q.add(qid)
        q_feats.append({
            "type": "Feature",
            "properties": {"queue_id": qid, "program_type": "EV_DCFC", "feeder_id": fdr, "wetland_buffer": 0, "transformer_bay_ok": bay, "queue_status": "PENDING"},
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })
    return corridors, {"type": "FeatureCollection", "features": q_feats}, elig_pv_q, elig_ev_q


def _compute_nf213_oracles() -> tuple[set[str], set[str], int, float, int, float]:
    _corr, _qfc, elig_pv_q, elig_ev_q = _build_gis_corridors_and_queue()
    net_caps = {"FDR-N01": 7.50 - 0.90, "FDR-N02": 7.20 - 1.35, "FDR-N03": 8.10 - 1.25}
    vr_derate = {"FDR-N01": 0.98, "FDR-N02": 0.95, "FDR-N03": 0.97}
    feeder_sums = {"FDR-N01": 0.0, "FDR-N02": 0.0, "FDR-N03": 0.0}
    elig_sub_cnt = 0
    for i in range(1, 217):
        k = ((i - 1) % 18) + 1
        qid = f"PV-{k:02d}"
        fdr = ("FDR-N01", "FDR-N02", "FDR-N03")[(k - 1) % 3]
        dc_kw = (265.0 if fdr == "FDR-N02" else 220.0) + (i % 9) * 18.0
        slope = 4.0 + (i % 12)
        zoning_ok = 1 if (i % 17 != 0) else 0
        if qid in elig_pv_q and slope <= 10.0 and zoning_ok == 1:
            elig_sub_cnt += 1
            feeder_sums[fdr] += ((dc_kw * 0.96 * vr_derate[fdr]) / 1000.0) / 1.25 / 0.95
    curtailed_pv_mva = round(sum(min(feeder_sums[f], net_caps[f]) for f in net_caps), 3)

    comm_cnt = 0
    tot_stalls = 0
    for i in range(1, 169):
        k = ((i - 1) % 14) + 1
        qid = f"EV-{k:02d}"
        stalls = 3 + (i % 3)
        status = "COMMISSIONED_2026" if (i % 19 != 0) else "DEFERRED_2028"
        if status == "COMMISSIONED_2026" and qid in elig_ev_q:
            comm_cnt += 1
            tot_stalls += stalls
    true_pf = 0.96 / math.sqrt(1.0 + 0.18 ** 2)
    seasons = [("SUMMER_PEAK", 0.84, 11.5), ("WINTER_PEAK", 0.80, 8.5)]
    ev_mva = round(
        max(
            ((((tot_stalls * (150.0 / 0.94 + aux_kw) * div_f) * 1.022 + comm_cnt * 4.2) / 1000.0)) / true_pf
            for _sn, div_f, aux_kw in seasons
        ),
        3,
    )
    return elig_pv_q, elig_ev_q, elig_sub_cnt, curtailed_pv_mva, comm_cnt, ev_mva


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Community Solar Parcel GIS Screening & Feeder MVA Allocation (`community_solar_gis_eng`)",
        "",
        "## Objective",
        f"Screen `SOLAR_PV` queue sites on the shared `interconnection_queue` layer in `{b}/workspace/shared_docs/substation_interconnection.qgs{b}` (open in **QGIS 3.22**, backed by `{b}/workspace/shared_docs/interconnection_queue.geojson` and `feeder_corridors.geojson`), evaluate curtailed hosting capacity in `{b}/workspace/pv_parcels.sqlite{b}`, commit your solar feeder MVA in `{b}/workspace/shared_docs/grid_interconnection.sqlite{b}` and `{b}/workspace/shared_docs/Substation_MVA_Schedule.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_Solar_GIS.pdf{b}` and `{b}/workspace/exhibits/substation_n1_limit.png{b}`, and write `{b}/workspace/solar_hosting_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Transit EV DCFC Depot Harmonic MVA Sizing & Feeder Allocation (`ev_depot_charging_planner`)",
        "",
        "## Objective",
        f"Screen `EV_DCFC` depot entries on the shared `interconnection_queue` layer in `{b}/workspace/shared_docs/substation_interconnection.qgs{b}` (open in **QGIS 3.22**, backed by `{b}/workspace/shared_docs/interconnection_queue.geojson` and `feeder_corridors.geojson`), size fleet DCFC apparent power across `{b}/workspace/ev_depots.sqlite{b}`, commit your EV depot MVA allocation in `{b}/workspace/shared_docs/grid_interconnection.sqlite{b}` and `{b}/workspace/shared_docs/Substation_MVA_Schedule.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_EV_Interconnect.pdf{b}` and `{b}/workspace/exhibits/substation_n1_limit.png{b}`, and write `{b}/workspace/ev_interconnect_audit.json{b}`.",
    ])
    return {"community_solar_gis_eng": ta, "ev_depot_charging_planner": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["community_solar_gis_eng"]
    ws_b = workspace_map["ev_depot_charging_planner"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "docs", ws_a / "exhibits", ws_b / "docs", ws_b / "exhibits", hub):
        d.mkdir(parents=True, exist_ok=True)

    # Shared SpatiaLite-enabled interconnection DB + QGIS project
    sh_db = hub / "grid_interconnection.sqlite"
    with sqlite3.connect(str(sh_db)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE feeder_queue (program TEXT PRIMARY KEY, committed_mva REAL, status TEXT)")
        conn.execute("INSERT INTO feeder_queue VALUES ('SOLAR_PV_HOSTING', 0.0, 'PENDING'), ('EV_DEPOT_DCFC', 0.0, 'PENDING')")
        conn.commit()

    corridors, queue_fc, _epv, _eev = _build_gis_corridors_and_queue()
    write_json(hub / "feeder_corridors.geojson", corridors)
    write_json(hub / "interconnection_queue.geojson", queue_fc)
    qgs_p = hub / "substation_interconnection.qgs"
    subprocess.run([
        "python3", "-c",
        "from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem; "
        "app = QgsApplication([], False); app.initQgis(); "
        "prj = QgsProject.instance(); prj.setCrs(QgsCoordinateReferenceSystem('EPSG:4326')); "
        f"lyr1 = QgsVectorLayer({json.dumps(str(hub / 'feeder_corridors.geojson'))}, 'feeder_corridors', 'ogr'); prj.addMapLayer(lyr1); "
        f"lyr2 = QgsVectorLayer({json.dumps(str(hub / 'interconnection_queue.geojson'))}, 'interconnection_queue', 'ogr'); prj.addMapLayer(lyr2); "
        f"prj.write({json.dumps(str(qgs_p))}); app.exitQgis()",
    ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)

    write_multisheet_xlsx(hub / "Substation_MVA_Schedule.xlsx", [
        ("FeederCap", [
            ["Allocation_Block", "Apparent_MVA", "SUB-NORTH-115KV"],
            ["Existing_Base_Load_MVA", BASE_FEEDER_MVA, "FIXED"],
            ["Solar_PV_Hosting_MVA", PV_FLOOR_MVA, "PRE_STUDY"],
            ["EV_Depot_DCFC_MVA", PRE_STUDY_EV_MVA, "PRE_STUDY"],
            ["Total_Substation_MVA", ("=SUM(B2:B4)", round(BASE_FEEDER_MVA + PV_FLOOR_MVA + PRE_STUDY_EV_MVA, 2)), f"CAP_{SUBSTATION_MVA_CAP:.2f}"],
        ]),
    ])
    render_scanned_exhibit_png(
        ws_a / "exhibits/substation_n1_limit.png",
        "115/13.8kV SUBSTATION N-1 TARIFF — COMMUNITY SOLAR QUEUE",
        [
            f"Hard N-1 Transformer Apparent Power Cap: {BASE_FEEDER_MVA:.2f} + solar_mva + ev_mva <= {SUBSTATION_MVA_CAP:.2f} MVA",
            f"Community Solar Queue Minimum Floor:     >= {PV_FLOOR_MVA:.2f} MVA  |  Preferred Solar Queue Target: 15.12 MVA",
            f"IEEE 1547 Solar GIS Control Code:        {IEEE1547_PV_CODE}",
        ],
        stamp_text="UTILITY T&D PLANNING",
    )
    render_scanned_exhibit_png(
        ws_b / "exhibits/substation_n1_limit.png",
        "115/13.8kV SUBSTATION N-1 TARIFF — TRANSIT EV DEPOT QUEUE",
        [
            f"Hard N-1 Transformer Apparent Power Cap: {BASE_FEEDER_MVA:.2f} + solar_mva + ev_mva <= {SUBSTATION_MVA_CAP:.2f} MVA",
            f"IEEE 519 Audited EV Depot Floor:         >= {EV_FLOOR_MVA:.2f} MVA (supersedes 16.20 PRE_STUDY) | Preferred: 16.56 MVA",
            f"IEEE 519 EV Harmonic Control Code:       {IEEE519_EV_CODE}",
        ],
        stamp_text="UTILITY T&D PLANNING",
    )

    with sqlite3.connect(str(ws_a / "pv_parcels.sqlite")) as conn:
        conn.execute("CREATE TABLE solar_sites (row_id INTEGER PRIMARY KEY, parcel_code TEXT, queue_id TEXT, feeder_id TEXT, filing_rev INTEGER, dc_kw REAL, slope_deg REAL, zoning_ok INTEGER)")
        rid = 1
        for i in range(1, 217):
            k = ((i - 1) % 18) + 1
            qid = f"PV-{k:02d}"
            fdr = ("FDR-N01", "FDR-N02", "FDR-N03")[(k - 1) % 3]
            dc_latest = (265.0 if fdr == "FDR-N02" else 220.0) + (i % 9) * 18.0
            if i % 14 == 0:
                conn.execute("INSERT INTO solar_sites VALUES (?,?,?,?,?,?,?,?)", (rid, f"PARCEL-{i:03d}", qid, fdr, 1, 310.0, 5.0, 1)); rid += 1
            conn.execute("INSERT INTO solar_sites VALUES (?,?,?,?,?,?,?,?)", (rid, f"PARCEL-{i:03d}", qid, fdr, 2 if i % 14 == 0 else 1, dc_latest, 4.0 + (i % 12), 1 if i % 17 != 0 else 0)); rid += 1
        conn.execute("CREATE TABLE inverter_ieee1547_rules (dc_to_ac_ratio REAL, temp_derate_factor REAL, max_slope_deg REAL, reactive_priority_pf REAL)")
        conn.execute("INSERT INTO inverter_ieee1547_rules VALUES (1.25, 0.96, 10.0, 0.95)")
        conn.execute("CREATE TABLE feeder_relay_caps (feeder_id TEXT PRIMARY KEY, max_reverse_mva REAL, existing_rooftop_dg_mva REAL)")
        conn.execute("INSERT INTO feeder_relay_caps VALUES ('FDR-N01', 7.50, 0.90), ('FDR-N02', 7.20, 1.35), ('FDR-N03', 8.10, 1.25)")
        conn.execute("CREATE TABLE feeder_voltage_rise_derate (feeder_id TEXT PRIMARY KEY, ltc_bandwidth_derate REAL)")
        conn.execute("INSERT INTO feeder_voltage_rise_derate VALUES ('FDR-N01', 0.98), ('FDR-N02', 0.95), ('FDR-N03', 0.97)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_Solar_GIS.pdf", "SOP-UTIL-1313A: QGIS UTM18N Screening & IEEE 1547 Inverter MVA", [
        ("1. Shared QGIS Layer Screening & Feeder-Curtailed PV MVA", [
            "1.1 Reproject feeder_corridors.geojson and interconnection_queue.geojson to EPSG:32618 (UTM Zone 18N). A SOLAR_PV feature in interconnection_queue is spatially eligible iff wetland_buffer = 0 AND its Euclidean distance in EPSG:32618 to the nearest voltage_class = '13.8kV_3PH' trunk line (exclude 4.16kV_1PH laterals!) is <= 350.0 m. Update queue_status of SOLAR_PV features in /workspace/shared_docs/interconnection_queue.geojson to 'APPROVED_PV' (or 'REJECTED_PV' if ineligible) without modifying non-SOLAR_PV features.",
            "1.2 Export a rendered map PNG (/workspace/solar_approved_map.png, >= 600x400 px) of approved solar queue sites over feeder_corridors, and ensure /workspace/shared_docs/substation_interconnection.qgs (open in live QGIS 3.22) is saved cleanly in EPSG:32618 with interconnection_queue subset filter \"queue_status LIKE 'APPROVED_%'\" so all approved substation projects remain visible.",
            f"1.3 Inspect all tables in /workspace/pv_parcels.sqlite. Deduplicate solar_sites by parcel_code retaining the highest filing_rev, filter to spatially approved SOLAR_PV queue_ids satisfying slope and zoning limits (report count as eligible_site_count), apply all inverter, feeder voltage-regulation, and net reverse-power headroom curtailment rules in the database to compute total_screened_pv_mva (3 dec), and commit solar_mva (>={PV_FLOOR_MVA} MVA, preferred 15.12 MVA, within {SUBSTATION_MVA_CAP} MVA cap) in grid_interconnection.sqlite and Substation_MVA_Schedule.xlsx (B3, C3='COMMITTED').",
        ]),
        ("2. JSON Schema (/workspace/solar_hosting_audit.json)", [
            "Keys: eligible_site_count (int), total_screened_pv_mva (float, 3 dec), solar_mva_committed (float, 2 dec), ieee1547_pv_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "ev_depots.sqlite")) as conn:
        conn.execute("CREATE TABLE dcfc_banks (bank_id INTEGER PRIMARY KEY, queue_id TEXT, stalls INTEGER, kw_per_stall REAL, phase_status TEXT)")
        for i in range(1, 169):
            k = ((i - 1) % 14) + 1
            conn.execute("INSERT INTO dcfc_banks VALUES (?,?,?,?,?)", (i, f"EV-{k:02d}", 3 + (i % 3), 150.0, "COMMISSIONED_2026" if i % 19 != 0 else "DEFERRED_2028"))
        conn.execute("CREATE TABLE ieee519_harmonic_pf (rectifier_efficiency REAL, displacement_pf REAL, current_thd_frac REAL, xfmr_core_noload_kw_per_bank REAL)")
        conn.execute("INSERT INTO ieee519_harmonic_pf VALUES (0.94, 0.96, 0.18, 4.2)")
        conn.execute("CREATE TABLE seasonal_aux_profiles (season TEXT PRIMARY KEY, coincident_diversity REAL, thermal_aux_kw_per_stall REAL)")
        conn.execute("INSERT INTO seasonal_aux_profiles VALUES ('SUMMER_PEAK', 0.84, 11.5), ('WINTER_PEAK', 0.80, 8.5)")
        conn.execute("CREATE TABLE underground_feeder_line_loss (conductor_spec TEXT PRIMARY KEY, diversified_i2r_loss_multiplier REAL)")
        conn.execute("INSERT INTO underground_feeder_line_loss VALUES ('500KCMIL_EPR_13K8', 1.022)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_EV_Interconnect.pdf", "SOP-UTIL-1313B: EV Fleet DCFC True-PF MVA & Feeder Commitment", [
        ("1. Shared QGIS Layer Screening & Harmonic True-PF MVA", [
            "1.1 Reproject feeder_corridors.geojson and interconnection_queue.geojson to EPSG:32618 (UTM Zone 18N). An EV_DCFC feature in interconnection_queue is spatially eligible iff transformer_bay_ok = 1 AND its Euclidean distance in EPSG:32618 to the nearest voltage_class = '13.8kV_3PH' trunk line (exclude 4.16kV_1PH laterals!) is <= 250.0 m. Update queue_status of EV_DCFC features in /workspace/shared_docs/interconnection_queue.geojson to 'APPROVED_EV' (or 'REJECTED_EV' if ineligible) without modifying non-EV_DCFC features.",
            "1.2 Export a rendered map PNG (/workspace/ev_approved_map.png, >= 600x400 px) of approved EV depot sites over feeder_corridors, and ensure /workspace/shared_docs/substation_interconnection.qgs (open in live QGIS 3.22) is saved cleanly in EPSG:32618 with interconnection_queue subset filter \"queue_status LIKE 'APPROVED_%'\" so all approved substation projects remain visible.",
            f"1.3 Inspect all tables in /workspace/ev_depots.sqlite. Filter dcfc_banks to phase_status = 'COMMISSIONED_2026' AND spatially approved EV_DCFC queue_ids (report count as commissioned_bank_count), evaluate worst-case seasonal peak apparent power demand coincident_fleet_mva_exact (MVA, 3 dec) incorporating all rectifier, seasonal thermal-auxiliary, underground feeder I^2R loss, padmount core no-load loss, and IEEE 519 harmonic true-PF tables in the database, and commit ev_mva (>={EV_FLOOR_MVA} MVA, preferred 16.56 MVA, within {SUBSTATION_MVA_CAP} MVA cap) in grid_interconnection.sqlite and Substation_MVA_Schedule.xlsx (B4, C4='COMMITTED').",
        ]),
        ("2. JSON Schema (/workspace/ev_interconnect_audit.json)", [
            "Keys: commissioned_bank_count (int), coincident_fleet_mva_exact (float, 3 dec), ev_mva_committed (float, 2 dec), ieee519_ev_code (str).",
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
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/health\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del state_dir, active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    launch_qgis_gui_natural(hub / "substation_interconnection.qgs")
    launch_libreoffice_uno_natural([hub / "Substation_MVA_Schedule.xlsx"])


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("community_solar_gis_eng" in act), ("ev_depot_charging_planner" in act)
    ws_a = workspace_map["community_solar_gis_eng"]
    ws_b = workspace_map["ev_depot_charging_planner"]
    hub = workspace_map["__shared_hub__"]
    ja = read_json_safe(ws_a / "solar_hosting_audit.json")
    jb = read_json_safe(ws_b / "ev_interconnect_audit.json")
    qg_live = inspect_live_qgis_readonly()
    uno_st = inspect_live_uno_documents_readonly()
    xp = hub / "Substation_MVA_Schedule.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}

    with sqlite3.connect(str(hub / "grid_interconnection.sqlite")) as conn:
        qmap = {r[0]: (float(r[1]), str(r[2])) for r in conn.execute("SELECT program, committed_mva, status FROM feeder_queue")}
    pv_mva, pv_st = qmap.get("SOLAR_PV_HOSTING", (-1.0, ""))
    ev_mva, ev_st = qmap.get("EV_DEPOT_DCFC", (-1.0, ""))

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("FeederCap") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("FeederCap") or {}).get(ref) or {}).get("value")

    elig_pv_q, elig_ev_q, exp_pv_cnt, exp_pv_mva, exp_ev_cnt, exp_ev_mva = _compute_nf213_oracles()
    q_disk = read_json_safe(hub / "interconnection_queue.geojson")
    feats_disk = q_disk.get("features") if isinstance(q_disk.get("features"), list) else []
    pv_appr_disk = {str((f.get("properties") or {}).get("queue_id")) for f in feats_disk if str((f.get("properties") or {}).get("program_type")) == "SOLAR_PV" and str((f.get("properties") or {}).get("queue_status", "")).startswith("APPROVED")}
    ev_appr_disk = {str((f.get("properties") or {}).get("queue_id")) for f in feats_disk if str((f.get("properties") or {}).get("program_type")) == "EV_DCFC" and str((f.get("properties") or {}).get("queue_status", "")).startswith("APPROVED")}

    lyr_q = (qg_live.get("layers") or {}).get("interconnection_queue") or {}
    exp_q_count = (len(elig_pv_q) if has_a else 0) + (len(elig_ev_q) if has_b else 0)
    qg_base_ok = bool(qg_live.get("running")) and (not qg_live.get("is_dirty")) and qg_live.get("crs") == "EPSG:32618" and bool(lyr_q.get("subset"))
    map_a_ok = (not has_a) or ((ws_a / "solar_approved_map.png").is_file() and (ws_a / "solar_approved_map.png").stat().st_size > 1500)
    map_b_ok = (not has_b) or ((ws_b / "ev_approved_map.png").is_file() and (ws_b / "ev_approved_map.png").stat().st_size > 1500)
    qg_ok = (not has_a) or (qg_base_ok and map_a_ok and pv_appr_disk == elig_pv_q and lyr_q.get("count") == exp_q_count)
    qg_ev_ok = (not has_b) or (qg_base_ok and map_b_ok and ev_appr_disk == elig_ev_q and lyr_q.get("count") == exp_q_count)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing solar_hosting_audit.json"),
        ("a_qgis_shared_queue", qg_ok, 0.20, f"Live QGIS 3.22 shared interconnection_queue count={lyr_q.get('count')} (expected {exp_q_count} in EPSG:32618) or PV approvals clobbered"),
        ("a_commit_sync", pv_mva >= PV_FLOOR_MVA and pv_st == "COMMITTED" and abs(_f(_cv("B3")) - pv_mva) <= 0.02 and abs(_f(ja.get("solar_mva_committed")) - pv_mva) <= 0.02, 0.20, "Solar MVA mismatch across SQLite/Calc/JSON"),
        ("a_code_cnt", ja.get("ieee1547_pv_code") == IEEE1547_PV_CODE and ja.get("eligible_site_count") == exp_pv_cnt, 0.18, f"ieee1547_pv_code or eligible_site_count != {exp_pv_cnt} mismatch"),
        ("a_fine_pv_curtailed", abs(_f(ja.get("total_screened_pv_mva")) - exp_pv_mva) <= 0.03, 0.34, f"total_screened_pv_mva != {exp_pv_mva} (check existing_rooftop_dg_mva net headroom, 0.96 temp derate & 0.95 PF)"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing ev_interconnect_audit.json"),
        ("b_qgis_shared_queue", qg_ev_ok, 0.18, f"Live QGIS 3.22 shared interconnection_queue count={lyr_q.get('count')} (expected {exp_q_count} in EPSG:32618) or EV approvals clobbered"),
        ("b_commit_sync", ev_mva >= EV_FLOOR_MVA and ev_st == "COMMITTED" and abs(_f(_cv("B4")) - ev_mva) <= 0.02 and abs(_f(jb.get("ev_mva_committed")) - ev_mva) <= 0.02, 0.18, "EV MVA mismatch across SQLite/Calc/JSON"),
        ("b_cnt_code", jb.get("commissioned_bank_count") == exp_ev_cnt and jb.get("ieee519_ev_code") == IEEE519_EV_CODE, 0.16, f"commissioned_bank_count != {exp_ev_cnt} or ieee519_ev_code mismatch"),
        ("b_mva_coarse", abs(_f(jb.get("coincident_fleet_mva_exact")) - exp_ev_mva) <= 2.5, 0.10, "coincident_fleet_mva_exact coarse off"),
        ("b_fine_aux_thd_mva", abs(_f(jb.get("coincident_fleet_mva_exact")) - exp_ev_mva) <= 0.05, 0.30, f"coincident_fleet_mva_exact != {exp_ev_mva} (check SUMMER_PEAK worst-case aux, non-diversified 4.2 kW/bank core loss & THD=0.18)"),
    ]

    eff_pv = pv_mva if (has_a and pv_mva > 0) else (PV_FLOOR_MVA if not has_a else 999.0)
    eff_ev = ev_mva if (has_b and ev_mva > 0) else (PRE_STUDY_EV_MVA if not has_b else 999.0)
    fl_ok = ((not has_a) or pv_mva >= PV_FLOOR_MVA) and ((not has_b) or ev_mva >= EV_FLOOR_MVA)
    calc_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "Substation_MVA_Schedule.xlsx" in u_url:
            calc_ok = not u_doc.get("is_modified")
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_n1_mva_cap", fl_ok and (BASE_FEEDER_MVA + eff_pv + eff_ev <= SUBSTATION_MVA_CAP), 0.12, f"Coupled substation load {BASE_FEEDER_MVA + eff_pv + eff_ev:.2f} MVA exceeds {SUBSTATION_MVA_CAP:.2f} MVA!"),
        ("j_sum_formula", "SUM(B2:B4)" in str(((shs.get("FeederCap") or {}).get("B5") or {}).get("formula") or "").upper(), 0.06, "FeederCap!B5 =SUM(B2:B4) lost"),
        ("j_uno_qgis_sync", act_done and calc_ok and qg_ok and qg_ev_ok, 0.08, "Live Calc or QGIS 3.22 out-of-sync with disk"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    sh_db = hub / "grid_interconnection.sqlite"
    xp = hub / "Substation_MVA_Schedule.xlsx"
    qgs_p = hub / "substation_interconnection.qgs"
    q_gj = hub / "interconnection_queue.geojson"
    elig_pv_q, elig_ev_q, exp_pv_cnt, exp_pv_mva, exp_ev_cnt, exp_ev_mva = _compute_nf213_oracles()

    if role == "community_solar_gis_eng":
        with file_atomic_lock("nf213_shared"):
            q_data = read_json_safe(q_gj)
            for feat in (q_data.get("features") or []):
                pr = feat.get("properties") or {}
                if pr.get("program_type") == "SOLAR_PV":
                    pr["queue_status"] = "APPROVED_PV" if pr.get("queue_id") in elig_pv_q else "REJECTED_PV"
            write_json(q_gj, q_data)
            subprocess.run([
                "python3", "-c",
                "from qgis.core import QgsApplication, QgsProject, QgsCoordinateReferenceSystem, QgsMapSettings, QgsMapRendererParallelJob\n"
                "from qgis.PyQt.QtCore import QSize\n"
                "app = QgsApplication([], False)\napp.initQgis()\n"
                f"prj = QgsProject.instance()\nprj.read({json.dumps(str(qgs_p))})\n"
                "prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32618'))\n"
                "for lyr in prj.mapLayers().values():\n"
                "    if lyr.name() == 'interconnection_queue': lyr.setSubsetString(\"\\\"queue_status\\\" = 'APPROVED_PV'\")\n"
                "ms = QgsMapSettings(); ms.setLayers(list(prj.mapLayers().values())); ms.setDestinationCrs(prj.crs()); ms.setOutputSize(QSize(800, 600))\n"
                "ext = list(prj.mapLayers().values())[0].extent(); ms.setExtent(ext)\n"
                "job = QgsMapRendererParallelJob(ms); job.start(); job.waitForFinished()\n"
                f"job.renderedImage().save({json.dumps(str(ws / 'solar_approved_map.png'))}, 'PNG')\n"
                "for lyr in prj.mapLayers().values():\n"
                "    if lyr.name() == 'interconnection_queue': lyr.setSubsetString(\"\\\"queue_status\\\" LIKE 'APPROVED_%'\")\n"
                f"prj.write({json.dumps(str(qgs_p))})\napp.exitQgis()\n",
            ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)
            reload_qgis_gui_project(qgs_p)
            with sqlite3.connect(str(sh_db)) as conn:
                ev_r = conn.execute("SELECT committed_mva, status FROM feeder_queue WHERE program='EV_DEPOT_DCFC'").fetchone()
                ev_cur = float(ev_r[0]) if ev_r and ev_r[1] == "COMMITTED" else 0.0
                pv_v = round(max(PV_FLOOR_MVA, min(14.84, SUBSTATION_MVA_CAP - BASE_FEEDER_MVA - ev_cur - 0.03)) if ev_cur > 0 else 14.84, 2)
                conn.execute("UPDATE feeder_queue SET committed_mva=?, status='COMMITTED' WHERE program='SOLAR_PV_HOSTING'", (pv_v,))
                conn.commit()
            shs = read_multisheet_xlsx(xp)
            b4 = float(((shs.get("FeederCap") or {}).get("B4") or {}).get("value") or 0.0)
            c4 = str(((shs.get("FeederCap") or {}).get("C4") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "FeederCap", [
                ["Allocation_Block", "Apparent_MVA", "SUB-NORTH-115KV"],
                ["Existing_Base_Load_MVA", BASE_FEEDER_MVA, "FIXED"],
                ["Solar_PV_Hosting_MVA", pv_v, "COMMITTED"],
                ["EV_Depot_DCFC_MVA", b4, c4],
                ["Total_Substation_MVA", ("=SUM(B2:B4)", round(BASE_FEEDER_MVA + pv_v + b4, 2)), f"CAP_{SUBSTATION_MVA_CAP:.2f}"],
            ])
            reload_uno_pipe_documents([xp])
        write_json(ws / "solar_hosting_audit.json", {
            "eligible_site_count": exp_pv_cnt,
            "total_screened_pv_mva": exp_pv_mva,
            "solar_mva_committed": pv_v,
            "ieee1547_pv_code": IEEE1547_PV_CODE,
        })
    else:
        with file_atomic_lock("nf213_shared"):
            q_data = read_json_safe(q_gj)
            for feat in (q_data.get("features") or []):
                pr = feat.get("properties") or {}
                if pr.get("program_type") == "EV_DCFC":
                    pr["queue_status"] = "APPROVED_EV" if pr.get("queue_id") in elig_ev_q else "REJECTED_EV"
            write_json(q_gj, q_data)
            subprocess.run([
                "python3", "-c",
                "from qgis.core import QgsApplication, QgsProject, QgsCoordinateReferenceSystem, QgsMapSettings, QgsMapRendererParallelJob\n"
                "from qgis.PyQt.QtCore import QSize\n"
                "app = QgsApplication([], False)\napp.initQgis()\n"
                f"prj = QgsProject.instance()\nprj.read({json.dumps(str(qgs_p))})\n"
                "prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32618'))\n"
                "for lyr in prj.mapLayers().values():\n"
                "    if lyr.name() == 'interconnection_queue': lyr.setSubsetString(\"\\\"queue_status\\\" = 'APPROVED_EV'\")\n"
                "ms = QgsMapSettings(); ms.setLayers(list(prj.mapLayers().values())); ms.setDestinationCrs(prj.crs()); ms.setOutputSize(QSize(800, 600))\n"
                "ext = list(prj.mapLayers().values())[0].extent(); ms.setExtent(ext)\n"
                "job = QgsMapRendererParallelJob(ms); job.start(); job.waitForFinished()\n"
                f"job.renderedImage().save({json.dumps(str(ws / 'ev_approved_map.png'))}, 'PNG')\n"
                "for lyr in prj.mapLayers().values():\n"
                "    if lyr.name() == 'interconnection_queue': lyr.setSubsetString(\"\\\"queue_status\\\" LIKE 'APPROVED_%'\")\n"
                f"prj.write({json.dumps(str(qgs_p))})\napp.exitQgis()\n",
            ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)
            reload_qgis_gui_project(qgs_p)
            with sqlite3.connect(str(sh_db)) as conn:
                pv_r = conn.execute("SELECT committed_mva, status FROM feeder_queue WHERE program='SOLAR_PV_HOSTING'").fetchone()
                pv_cur = float(pv_r[0]) if pv_r and pv_r[1] == "COMMITTED" else 0.0
                ev_v = round(max(EV_FLOOR_MVA, min(16.52, SUBSTATION_MVA_CAP - BASE_FEEDER_MVA - pv_cur - 0.03)) if pv_cur > 0 else 16.52, 2)
                conn.execute("UPDATE feeder_queue SET committed_mva=?, status='COMMITTED' WHERE program='EV_DEPOT_DCFC'", (ev_v,))
                conn.commit()
            shs = read_multisheet_xlsx(xp)
            b3 = float(((shs.get("FeederCap") or {}).get("B3") or {}).get("value") or 0.0)
            c3 = str(((shs.get("FeederCap") or {}).get("C3") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "FeederCap", [
                ["Allocation_Block", "Apparent_MVA", "SUB-NORTH-115KV"],
                ["Existing_Base_Load_MVA", BASE_FEEDER_MVA, "FIXED"],
                ["Solar_PV_Hosting_MVA", b3, c3],
                ["EV_Depot_DCFC_MVA", ev_v, "COMMITTED"],
                ["Total_Substation_MVA", ("=SUM(B2:B4)", round(BASE_FEEDER_MVA + b3 + ev_v, 2)), f"CAP_{SUBSTATION_MVA_CAP:.2f}"],
            ])
            reload_uno_pipe_documents([xp])
        write_json(ws / "ev_interconnect_audit.json", {
            "commissioned_bank_count": exp_ev_cnt,
            "coincident_fleet_mva_exact": exp_ev_mva,
            "ev_mva_committed": ev_v,
            "ieee519_ev_code": IEEE519_EV_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("community_solar_gis_eng", workspace_map, port)
    solve_role("ev_depot_charging_planner", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    qgs_p = hub / "substation_interconnection.qgs"
    # Uncoordinated single-program subsetString hides peer's approved EV depots & preferred MVA overflows 37.80 MVA!
    subprocess.run([
        "python3", "-c",
        "from qgis.core import QgsApplication, QgsProject\n"
        "app = QgsApplication([], False)\napp.initQgis()\n"
        f"prj = QgsProject.instance()\nprj.read({json.dumps(str(qgs_p))})\n"
        "for lyr in prj.mapLayers().values():\n"
        "    if lyr.name() == 'interconnection_queue': lyr.setSubsetString(\"\\\"program_type\\\" = 'SOLAR_PV'\")\n"
        f"prj.write({json.dumps(str(qgs_p))})\napp.exitQgis()\n",
    ], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, check=True, capture_output=True, timeout=35)
    reload_qgis_gui_project(qgs_p)
    with sqlite3.connect(str(hub / "grid_interconnection.sqlite")) as conn:
        conn.execute("UPDATE feeder_queue SET committed_mva=14.96 WHERE program='SOLAR_PV_HOSTING'")
        conn.execute("UPDATE feeder_queue SET committed_mva=16.51 WHERE program='EV_DEPOT_DCFC'")
        conn.commit()
