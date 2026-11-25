"""NF2-12: Live FreeCAD 0.20 GUI (`.FCStd`) + Live Calc — 6U CubeSat B-Rep Solid Sizing & Coupled Wet-Mass/CG Envelope."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from tasks.novel_frontier_v2.common import (
    build_grade_payload,
    evaluate_xlsx_via_libreoffice,
    file_atomic_lock,
    inspect_live_freecad_readonly,
    inspect_live_uno_documents_readonly,
    inspect_live_x11_window_titles_readonly,
    launch_freecad_gui_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_freecad_gui_file,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-12"
PORTAL_PORT = 19612

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `FreeCAD 0.20` (`.FCStd`) Solid Assembly & Open Calc: 6U CubeSat Structural Bus vs. Star-Tracker Mass/CG Envelope",
    "domain": "Aerospace 6U CubeSat Mechanical CAD (`FreeCAD 0.20` B-Rep) & Mass-Properties Engineering (`LibreOffice Calc`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("spacecraft_bus_cad_eng", "payload_optics_thermal_eng"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

CDS_BUS_CODE = make_canary_code("NASA-6U-BUS", "al7075-isogrid")
CDS_PAY_CODE = make_canary_code("NASA-6U-PAY", "baffle-sic-optics")
# Dispenser wet mass cap = 11.75 kg.
# PDR pre-qualification baseline in XLSX: Bus = 4.40 (PDR_ESTIMATE), Payload = 5.95 (PDR_ESTIMATE).
# Solo A commits preferred 4.64 kg (1.10 + 4.64 + 5.95 = 11.69 <= 11.75);
# Role B CDR radiation-shielded battery raises PAY_FLOOR_KG to 6.12 kg (preferred 6.20 kg; solo B: 1.10 + 4.40 + 6.20 = 11.70 <= 11.75);
# Concurrent shared: 1.10 + 4.64 + 6.12 = 11.86 > 11.75 kg (Role B cannot fit if Role A holds 4.64 kg!).
DISPENSER_MASS_CAP_KG = 11.75
HARNESS_TARE_KG = 1.10
HARNESS_Z_MM = 170.0
BUS_FLOOR_KG = 4.40
PDR_PAY_EST_KG = 5.95
PAY_FLOOR_KG = 6.12
Z_CG_MIN_MM = 156.0
Z_CG_MAX_MM = 176.0

FC_INIT_SCRIPT = """
import sys
sys.path.append('/usr/lib/freecad-python3/lib')
import FreeCAD, Part
doc = FreeCAD.newDocument('CubeSat6U')
bus = doc.addObject('Part::Feature', 'Bus_Chassis_Shell')
outer = Part.makeBox(226.3, 100.0, 340.5)
inner = Part.makeBox(214.3, 88.0, 328.5, FreeCAD.Vector(6.0, 6.0, 6.0))
bus.Shape = outer.cut(inner)
bus.addProperty('App::PropertyFloat', 'CommittedMassKg', 'AIT', 'Bus mass kg').CommittedMassKg = 0.0
bus.addProperty('App::PropertyString', 'Status', 'AIT', 'Status').Status = 'PENDING'

pay = doc.addObject('Part::Feature', 'StarTracker_Baffle')
cyl_out = Part.makeCylinder(42.0, 140.0, FreeCAD.Vector(113.15, 50.0, 150.0))
cyl_in = Part.makeCylinder(36.0, 140.0, FreeCAD.Vector(113.15, 50.0, 150.0))
pay.Shape = cyl_out.cut(cyl_in)
pay.addProperty('App::PropertyFloat', 'CommittedMassKg', 'AIT', 'Payload mass kg').CommittedMassKg = 0.0
pay.addProperty('App::PropertyString', 'Status', 'AIT', 'Status').Status = 'PENDING'
doc.recompute()
doc.saveAs(sys.argv[-1])
"""


def _inspect_fcstd(fc_path: Path) -> dict[str, Any]:
    if not fc_path.is_file():
        return {}
    code = (
        "import json, sys\n"
        "sys.path.append('/usr/lib/freecad-python3/lib')\n"
        "import FreeCAD\n"
        f"doc = FreeCAD.openDocument({json.dumps(str(fc_path))})\n"
        "bus = doc.getObject('Bus_Chassis_Shell'); pay = doc.getObject('StarTracker_Baffle')\n"
        "out = {\n"
        "  'has_both': bool(bus and pay),\n"
        "  'bus_vol_mm3': round(float(bus.Shape.Volume), 1) if bus else 0.0,\n"
        "  'pay_vol_mm3': round(float(pay.Shape.Volume), 1) if pay else 0.0,\n"
        "  'bus_z_mm': round(float(bus.Shape.CenterOfGravity.z), 2) if bus else 0.0,\n"
        "  'pay_z_mm': round(float(pay.Shape.CenterOfGravity.z), 2) if pay else 0.0,\n"
        "  'bus_mass': round(float(getattr(bus, 'CommittedMassKg', -1.0)), 3) if bus else -1.0,\n"
        "  'bus_status': str(getattr(bus, 'Status', '')) if bus else '',\n"
        "  'pay_mass': round(float(getattr(pay, 'CommittedMassKg', -1.0)), 3) if pay else -1.0,\n"
        "  'pay_status': str(getattr(pay, 'Status', '')) if pay else '',\n"
        "}\n"
        "print('FC_JSON:' + json.dumps(out))\n"
    )
    cp = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=30)
    for ln in cp.stdout.splitlines():
        if ln.startswith("FC_JSON:"):
            return json.loads(ln.split("FC_JSON:", 1)[1])
    return {}


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — 6U CubeSat Al-7075 Pocketed Chassis & Modal Stiffness (`spacecraft_bus_cad_eng`)",
        "",
        "## Objective",
        f"Pocket/lightweight `Bus_Chassis_Shell` in `{b}/workspace/shared_docs/cubesat_6u_assembly.FCStd{b}` (open in **FreeCAD 0.20**) and commit your bus mass allocation in `{b}/workspace/shared_docs/CubeSat_Mass_Properties.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_Bus_CAD.pdf{b}` and `{b}/workspace/exhibits/cds_6u_envelope.png{b}`, analyze `{b}/workspace/fem/chassis_fasteners.sqlite{b}`, and write `{b}/workspace/bus_cad_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — Star-Tracker Baffle Geometry & Radiator Balance (`payload_optics_thermal_eng`)",
        "",
        "## Objective",
        f"Trim `StarTracker_Baffle` in `{b}/workspace/shared_docs/cubesat_6u_assembly.FCStd{b}` (open in **FreeCAD 0.20**) and commit your payload+power mass allocation in `{b}/workspace/shared_docs/CubeSat_Mass_Properties.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_Payload_CAD.pdf{b}` and `{b}/workspace/exhibits/cds_6u_envelope.png{b}`, analyze `{b}/workspace/thermal/orbit_flux_nodes.sqlite{b}`, and write `{b}/workspace/payload_thermal_audit.json{b}`.",
    ])
    return {"spacecraft_bus_cad_eng": ta, "payload_optics_thermal_eng": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["spacecraft_bus_cad_eng"]
    ws_b = workspace_map["payload_optics_thermal_eng"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "fem", ws_a / "docs", ws_a / "exhibits", ws_b / "thermal", ws_b / "docs", ws_b / "exhibits", hub):
        d.mkdir(parents=True, exist_ok=True)

    fc_p = hub / "cubesat_6u_assembly.FCStd"
    subprocess.run(["python3", "-c", FC_INIT_SCRIPT, str(fc_p)], check=True, capture_output=True, timeout=35)
    write_multisheet_xlsx(hub / "CubeSat_Mass_Properties.xlsx", [
        ("MassBudget", [
            ["Subsystem", "Mass_kg", "CDS-6U-REV4"],
            ["Harness_Tare_kg", HARNESS_TARE_KG, "FIXED"],
            ["Bus_Structure_kg", BUS_FLOOR_KG, "PDR_ESTIMATE"],
            ["Payload_Power_kg", PDR_PAY_EST_KG, "PDR_ESTIMATE"],
            ["Total_Wet_Mass_kg", ("=SUM(B2:B4)", round(HARNESS_TARE_KG + BUS_FLOOR_KG + PDR_PAY_EST_KG, 2)), f"CAP_{DISPENSER_MASS_CAP_KG:.2f}"],
        ]),
    ])
    render_scanned_exhibit_png(
        ws_a / "exhibits/cds_6u_envelope.png",
        "NASA / CALPOLY 6U CUBESAT DISPENSER — STRUCTURAL BUS ICD",
        [
            f"Maximum 6U Dispenser Wet Mass Cap: {DISPENSER_MASS_CAP_KG:.2f} kg (1.10 + bus_mass_kg + payload_mass_kg <= {DISPENSER_MASS_CAP_KG:.2f} kg)",
            f"Harness Tare: {HARNESS_TARE_KG:.2f} kg @ Z = {HARNESS_Z_MM:.1f} mm  |  Coupled Spacecraft Axial CG: [{Z_CG_MIN_MM:.1f}, {Z_CG_MAX_MM:.1f}] mm",
            f"Structural Bus Minimum Qualified Mass: {BUS_FLOOR_KG:.2f} kg  |  Preferred Stiffened CDR Bus Target: 4.64 kg",
            f"Bus CAD Control Code: {CDS_BUS_CODE}",
        ],
        stamp_text="AIT CLEANROOM CONTROL",
    )
    render_scanned_exhibit_png(
        ws_b / "exhibits/cds_6u_envelope.png",
        "NASA / CALPOLY 6U CUBESAT DISPENSER — PAYLOAD & POWER ICD",
        [
            f"Maximum 6U Dispenser Wet Mass Cap: {DISPENSER_MASS_CAP_KG:.2f} kg (1.10 + bus_mass_kg + payload_mass_kg <= {DISPENSER_MASS_CAP_KG:.2f} kg)",
            f"Harness Tare: {HARNESS_TARE_KG:.2f} kg @ Z = {HARNESS_Z_MM:.1f} mm  |  Coupled Spacecraft Axial CG: [{Z_CG_MIN_MM:.1f}, {Z_CG_MAX_MM:.1f}] mm",
            f"CDR Radiation-Shielded Payload+Battery Minimum Floor: {PAY_FLOOR_KG:.2f} kg (supersedes 5.95 kg PDR) | Preferred: 6.20 kg",
            f"Payload CAD Control Code: {CDS_PAY_CODE}",
        ],
        stamp_text="AIT CLEANROOM CONTROL",
    )

    with sqlite3.connect(str(ws_a / "fem/chassis_fasteners.sqlite")) as conn:
        conn.execute("CREATE TABLE fastener_loads (joint_id INTEGER PRIMARY KEY, joint_zone TEXT, preload_p0_n REAL, ext_launch_axial_n REAL, shear_n REAL, status TEXT)")
        for i in range(1, 181):
            ax = 9999.0 if (i % 31 == 0) else (420.0 + (i % 15) * 18.0)  # 9999.0 = ADC preload gauge rail-saturation dropout!
            z = "SOLAR_WING_HINGE" if (i % 4 == 0) else "NADIR_DECK"
            ext_ax = 310.0 + (i % 9) * 22.0
            conn.execute("INSERT INTO fastener_loads VALUES (?,?,?,?,?,?)", (i, z, ax, ext_ax, 240.0 + (i % 11) * 14.0, "ACTIVE" if i % 29 != 0 else "DUMMY_TOOLING_PIN"))
        conn.execute("CREATE TABLE joint_stiffness_factors (joint_zone TEXT PRIMARY KEY, thermal_delta_ext_n REAL, bolt_load_share_phi REAL)")
        conn.execute("INSERT INTO joint_stiffness_factors VALUES ('NADIR_DECK', 80.0, 0.26), ('SOLAR_WING_HINGE', 145.0, 0.34)")
        conn.execute("CREATE TABLE random_vib_shear_allowance (joint_zone TEXT PRIMARY KEY, dynamic_3sigma_shear_n REAL)")
        conn.execute("INSERT INTO random_vib_shear_allowance VALUES ('NADIR_DECK', 32.0), ('SOLAR_WING_HINGE', 58.0)")
        conn.execute("CREATE TABLE helicoil_insert_allowance (material TEXT PRIMARY KEY, m3_allowable_equiv_n REAL, torque_scatter_cmax REAL, safety_factor REAL)")
        conn.execute("INSERT INTO helicoil_insert_allowance VALUES ('TI6AL4V_LOCKING', 2150.0, 1.12, 1.40)")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_Bus_CAD.pdf", "SOP-AIT-1212A: FreeCAD 6U Chassis Light-Weighting & Fastener Margin", [
        ("1. FreeCAD Bus_Chassis_Shell & Fastener Von-Mises Margin", [
            f"1.1 Pocket Bus_Chassis_Shell in cubesat_6u_assembly.FCStd by cutting a side access window so its B-Rep volume lies in [1,100,000, 1,550,000] mm^3 while keeping the coupled spacecraft axial CG within [{Z_CG_MIN_MM}, {Z_CG_MAX_MM}] mm (preserving StarTracker_Baffle). Set Bus_Chassis_Shell.CommittedMassKg (>={BUS_FLOOR_KG} kg, preferred 4.64 kg, within {DISPENSER_MASS_CAP_KG} kg wet-mass cap) and Status='COMMITTED', ensure the live open FreeCAD 0.20 window reflects the saved assembly cleanly, and update CubeSat_Mass_Properties.xlsx MassBudget!B3 & C3='COMMITTED'.",
            "1.2 Inspect all tables in chassis_fasteners.sqlite. Filter fastener_loads to rows with status = 'ACTIVE' AND preload_p0_n < 9000.0 (excluding DUMMY_TOOLING_PIN and 9999.0 N saturated ADC gauge sentinels) and report this count as valid_unsat_active_fastener_count. Evaluate NASA-STD-5020 preloaded bolted-joint Von-Mises combined axial-shear force F_eq = sqrt(F_ax^2 + 3*V_tot^2) incorporating all preload scatter, joint stiffness load-sharing, thermal, and launch vibration allowances in the database, and report min_fastener_margin_of_safety = allowable / (safety_factor * max(F_eq)) - 1.0.",
        ]),
        ("2. JSON Schema (/workspace/bus_cad_audit.json)", [
            "Keys: valid_unsat_active_fastener_count (int), min_fastener_margin_of_safety (float, 4 dec), bus_shell_volume_mm3 (float, 1 dec), bus_mass_committed_kg (float, 2 dec), cds_bus_code (str).",
        ]),
    ])

    with sqlite3.connect(str(ws_b / "thermal/orbit_flux_nodes.sqlite")) as conn:
        conn.execute("CREATE TABLE orbit_slices (step_id INTEGER PRIMARY KEY, solar_inc_w_m2 REAL, albedo_w_m2 REAL, earth_ir_w_m2 REAL, eclipse_flag INTEGER)")
        for i in range(1, 241):
            ec = 1 if (i % 3 == 0) else 0
            eir = -999.0 if (i % 29 == 0) else 238.0  # -999.0 = South Atlantic Anomaly pyrgeometer telemetry dropout!
            conn.execute("INSERT INTO orbit_slices VALUES (?,?,?,?,?)", (i, 0.0 if ec else 1361.0, 0.0 if ec else 185.0, eir, ec))
        conn.execute("CREATE TABLE osr_radiator_properties (radiator_area_m2 REAL, bol_alpha REAL, eol_uv_delta_alpha REAL, epsilon_ir REAL, beta_angle_deg REAL, earth_view_factor REAL, sigma_sb REAL)")
        conn.execute("INSERT INTO osr_radiator_properties VALUES (0.85, 0.11, 0.07, 0.84, 28.0, 0.32, 5.670374419e-8)")
        conn.execute("CREATE TABLE thermal_dissipation_modes (eclipse_flag INTEGER PRIMARY KEY, payload_elec_watts REAL, survival_heater_watts REAL)")
        conn.execute("INSERT INTO thermal_dissipation_modes VALUES (0, 38.0, 0.0), (1, 16.0, 19.5)")
        conn.execute("CREATE TABLE mli_strut_parasitic_leak (interface_id TEXT PRIMARY KEY, continuous_parasitic_watts REAL)")
        conn.execute("INSERT INTO mli_strut_parasitic_leak VALUES ('TI_BIPOD_STRUTS', 6.4)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_Payload_CAD.pdf", "SOP-AIT-1212B: Star-Tracker Baffle Trim & EOL Radiator Sizing", [
        ("1. FreeCAD Baffle Trim & EOL Equilibrium Temperature", [
            f"1.1 Trim StarTracker_Baffle length and seat its base along Z in cubesat_6u_assembly.FCStd so its B-Rep volume lies in [140,000, 185,000] mm^3 and its Shape.CenterOfGravity.z <= 172.0 mm so the coupled spacecraft axial CG stays within [{Z_CG_MIN_MM}, {Z_CG_MAX_MM}] mm (preserving Bus_Chassis_Shell). Set StarTracker_Baffle.CommittedMassKg (>={PAY_FLOOR_KG} kg CDR floor, preferred 6.20 kg, within {DISPENSER_MASS_CAP_KG} kg cap) and Status='COMMITTED', ensure the live open FreeCAD 0.20 window reflects the saved assembly cleanly, and update CubeSat_Mass_Properties.xlsx MassBudget!B4 & C4='COMMITTED'.",
            "1.2 Inspect all tables in orbit_flux_nodes.sqlite. Filter orbit_slices to valid telemetry rows where earth_ir_w_m2 > 0 (excluding -999.0 SAA pyrgeometer dropouts) and report valid_telemetry_sunlit_slice_count as the count of valid telemetry rows with eclipse_flag = 0. Across all valid telemetry rows (sunlit and eclipse), compute orbit-average Stefan-Boltzmann radiative equilibrium temperature eol_equilibrium_temp_k (Kelvin, 2 dec) incorporating all EOL optical radiator properties, orbital geometry view/projection factors, mode-dependent internal dissipations, and conductive interface heat leaks in the database.",
        ]),
        ("2. JSON Schema (/workspace/payload_thermal_audit.json)", [
            "Keys: valid_telemetry_sunlit_slice_count (int), eol_equilibrium_temp_k (float, 2 dec), baffle_volume_mm3 (float, 1 dec), payload_mass_committed_kg (float, 2 dec), cds_payload_code (str).",
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
    launch_freecad_gui_natural(hub / "cubesat_6u_assembly.FCStd")
    launch_libreoffice_uno_natural([hub / "CubeSat_Mass_Properties.xlsx"])


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    import math
    act = set(active_roles or META["roles"])
    has_a, has_b = ("spacecraft_bus_cad_eng" in act), ("payload_optics_thermal_eng" in act)
    ws_a = workspace_map["spacecraft_bus_cad_eng"]
    ws_b = workspace_map["payload_optics_thermal_eng"]
    hub = workspace_map["__shared_hub__"]
    fc = _inspect_fcstd(hub / "cubesat_6u_assembly.FCStd")
    fc_live = inspect_live_freecad_readonly()
    xp = hub / "CubeSat_Mass_Properties.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    uno_st = inspect_live_uno_documents_readonly()
    titles = inspect_live_x11_window_titles_readonly()
    ja = read_json_safe(ws_a / "bus_cad_audit.json")
    jb = read_json_safe(ws_b / "payload_thermal_audit.json")

    def _f(v: Any, d: float = -999999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("MassBudget") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("MassBudget") or {}).get(ref) or {}).get("value")

    # Exact oracles
    act_j = [
        (
            1.12 * (420.0 + (i % 15) * 18.0) + (0.34 if i % 4 == 0 else 0.26) * ((310.0 + (i % 9) * 22.0) + (145.0 if i % 4 == 0 else 80.0)),
            (240.0 + (i % 11) * 14.0) + (58.0 if i % 4 == 0 else 32.0),
        )
        for i in range(1, 181)
        if (i % 29 != 0) and (i % 31 != 0)
    ]
    max_eq = max(math.sqrt(ax * ax + 3.0 * sh * sh) for ax, sh in act_j)
    exp_ms = round((2150.0 / (1.40 * max_eq)) - 1.0, 4)

    valid_orb = [i for i in range(1, 241) if i % 29 != 0]
    sunlit_cnt = sum(1 for i in valid_orb if i % 3 != 0)
    cos_b = math.cos(math.radians(28.0))
    area_r = 0.85
    p_tot_w = [
        area_r * ((0.0 if i % 3 == 0 else (1361.0 * cos_b + 185.0 * 0.32)) * 0.18 + 238.0 * 0.32 * 0.84)
        + ((16.0 + 19.5) if i % 3 == 0 else 38.0) + 6.4
        for i in valid_orb
    ]
    exp_tk = round(((sum(p_tot_w) / len(p_tot_w)) / (area_r * 0.84 * 5.670374419e-8)) ** 0.25, 2)

    bm = _f(fc.get("bus_mass"), -1.0)
    pm = _f(fc.get("pay_mass"), -1.0)
    bv = _f(fc.get("bus_vol_mm3"), 0.0)
    pv = _f(fc.get("pay_vol_mm3"), 0.0)
    bz = _f(fc.get("bus_z_mm"), 999.0)
    pz = _f(fc.get("pay_z_mm"), 999.0)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing bus_cad_audit.json"),
        ("a_fc_pocket", bool(fc.get("has_both")) and (1_100_000.0 <= bv <= 1_550_000.0), 0.20, f"Bus_Chassis_Shell B-Rep volume {bv} outside [1.10e6, 1.55e6] mm^3"),
        ("a_fc_commit", bm >= BUS_FLOOR_KG and fc.get("bus_status") == "COMMITTED" and abs(_f(_cv("B3")) - bm) <= 0.02 and abs(_f(ja.get("bus_mass_committed_kg")) - bm) <= 0.02, 0.18, "Bus CommittedMassKg / XLSX MassBudget!B3 / JSON mismatch"),
        ("a_vol_json", abs(_f(ja.get("bus_shell_volume_mm3")) - bv) <= 50.0 and ja.get("cds_bus_code") == CDS_BUS_CODE, 0.14, "JSON bus volume or code mismatch"),
        ("a_cnt", ja.get("valid_unsat_active_fastener_count") == len(act_j), 0.10, f"valid_unsat_active_fastener_count != {len(act_j)}"),
        ("a_fine_helicoil_ms", abs(_f(ja.get("min_fastener_margin_of_safety")) - exp_ms) <= 0.003, 0.30, f"min_fastener_margin_of_safety != {exp_ms} (check 1.12 preload scatter, phi load-share & SF=1.40)"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing payload_thermal_audit.json"),
        ("b_fc_baffle", bool(fc.get("has_both")) and (140_000.0 <= pv <= 185_000.0) and (pz <= 172.0), 0.20, f"StarTracker_Baffle volume {pv} or CenterOfMass.z {pz} > 172.0 mm"),
        ("b_fc_commit", pm >= PAY_FLOOR_KG and fc.get("pay_status") == "COMMITTED" and abs(_f(_cv("B4")) - pm) <= 0.02 and abs(_f(jb.get("payload_mass_committed_kg")) - pm) <= 0.02, 0.18, "Payload CommittedMassKg / XLSX MassBudget!B4 / JSON mismatch"),
        ("b_vol_json", abs(_f(jb.get("baffle_volume_mm3")) - pv) <= 50.0 and jb.get("cds_payload_code") == CDS_PAY_CODE, 0.14, "JSON baffle volume or code mismatch"),
        ("b_cnt", jb.get("valid_telemetry_sunlit_slice_count") == sunlit_cnt, 0.10, f"valid_telemetry_sunlit_slice_count != {sunlit_cnt}"),
        ("b_fine_eol_tk", abs(_f(jb.get("eol_equilibrium_temp_k")) - exp_tk) <= 0.25, 0.30, f"eol_equilibrium_temp_k != {exp_tk} (check 0.85 m^2 area, eclipse heater & EOL alpha=0.18)"),
    ]

    eff_b = bm if (has_a and bm > 0) else (BUS_FLOOR_KG if not has_a else 99.0)
    eff_p = pm if (has_b and pm > 0) else (PDR_PAY_EST_KG if not has_b else 99.0)
    eff_bz = bz if has_a else 170.25
    eff_pz = pz if has_b else 161.0
    tot_m = HARNESS_TARE_KG + eff_b + eff_p
    z_cg_tot = (HARNESS_TARE_KG * HARNESS_Z_MM + eff_b * eff_bz + eff_p * eff_pz) / max(tot_m, 1e-6)
    fl_ok = ((not has_a) or bm >= BUS_FLOOR_KG) and ((not has_b) or pm >= PAY_FLOOR_KG)
    calc_ok = True
    for u_url, u_doc in (uno_st.get("docs") or {}).items():
        if "CubeSat_Mass_Properties.xlsx" in u_url:
            calc_ok = not u_doc.get("is_modified")
    live_objs = fc_live.get("objects") or {}
    live_bus_ok = (not has_a) or ((live_objs.get("Bus_Chassis_Shell") or {}).get("status") == "COMMITTED" and abs(_f((live_objs.get("Bus_Chassis_Shell") or {}).get("vol")) - bv) <= 50.0)
    live_pay_ok = (not has_b) or ((live_objs.get("StarTracker_Baffle") or {}).get("status") == "COMMITTED" and abs(_f((live_objs.get("StarTracker_Baffle") or {}).get("vol")) - pv) <= 50.0)
    fc_clean = bool(fc_live.get("running")) and (not fc_live.get("is_dirty")) and live_bus_ok and live_pay_ok and (not any("*" in t and "FreeCAD" in t for t in titles))
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_cds_mass_and_cg", fl_ok and (tot_m <= DISPENSER_MASS_CAP_KG) and (Z_CG_MIN_MM <= z_cg_tot <= Z_CG_MAX_MM), 0.12, f"Coupled wet mass {tot_m:.2f} kg > {DISPENSER_MASS_CAP_KG:.2f} kg or Z_cg {z_cg_tot:.1f} mm outside [{Z_CG_MIN_MM}, {Z_CG_MAX_MM}] mm!"),
        ("j_sum_formula", "SUM(B2:B4)" in str(((shs.get("MassBudget") or {}).get("B5") or {}).get("formula") or "").upper(), 0.06, "MassBudget!B5 =SUM(B2:B4) lost"),
        ("j_gui_synced", act_done and calc_ok and fc_clean, 0.08, "Live FreeCAD 0.20 3D document or open Calc window out-of-sync with disk"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    import math
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    fc_p = hub / "cubesat_6u_assembly.FCStd"
    xp = hub / "CubeSat_Mass_Properties.xlsx"

    if role == "spacecraft_bus_cad_eng":
        with file_atomic_lock("nf212_shared"):
            cur = _inspect_fcstd(fc_p)
            pm = cur.get("pay_mass", 0.0) if cur.get("pay_status") == "COMMITTED" else 0.0
            bm = round(max(BUS_FLOOR_KG, min(4.48, DISPENSER_MASS_CAP_KG - HARNESS_TARE_KG - pm - 0.03)) if pm > 0 else 4.48, 2)
            code = (
                "import json, sys; sys.path.append('/usr/lib/freecad-python3/lib')\n"
                "import FreeCAD, Part\n"
                f"doc = FreeCAD.openDocument({json.dumps(str(fc_p))})\n"
                "bus = doc.getObject('Bus_Chassis_Shell')\n"
                "outer = Part.makeBox(226.3, 100.0, 340.5); inner = Part.makeBox(214.3, 88.0, 328.5, FreeCAD.Vector(6,6,6))\n"
                "win = Part.makeBox(150.0, 120.0, 220.0, FreeCAD.Vector(38.0, -10.0, 60.0))\n"
                "bus.Shape = outer.cut(inner).cut(win)\n"
                f"bus.CommittedMassKg = {bm}; bus.Status = 'COMMITTED'\n"
                f"doc.recompute(); doc.saveAs({json.dumps(str(fc_p))})\n"
            )
            subprocess.run(["python3", "-c", code], check=True, capture_output=True, timeout=35)
            reload_freecad_gui_file(fc_p)
            shs = read_multisheet_xlsx(xp)
            b4 = float(((shs.get("MassBudget") or {}).get("B4") or {}).get("value") or 0.0)
            c4 = str(((shs.get("MassBudget") or {}).get("C4") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "MassBudget", [
                ["Subsystem", "Mass_kg", "CDS-6U-REV4"],
                ["Harness_Tare_kg", HARNESS_TARE_KG, "FIXED"],
                ["Bus_Structure_kg", bm, "COMMITTED"],
                ["Payload_Power_kg", b4, c4],
                ["Total_Wet_Mass_kg", ("=SUM(B2:B4)", round(HARNESS_TARE_KG + bm + b4, 2)), f"CAP_{DISPENSER_MASS_CAP_KG:.2f}"],
            ])
            reload_uno_pipe_documents([xp])
        info = _inspect_fcstd(fc_p)
        act_j = [
            (
                1.12 * (420.0 + (i % 15) * 18.0) + (0.34 if i % 4 == 0 else 0.26) * ((310.0 + (i % 9) * 22.0) + (145.0 if i % 4 == 0 else 80.0)),
                (240.0 + (i % 11) * 14.0) + (58.0 if i % 4 == 0 else 32.0),
            )
            for i in range(1, 181)
            if (i % 29 != 0) and (i % 31 != 0)
        ]
        max_eq = max(math.sqrt(ax * ax + 3.0 * sh * sh) for ax, sh in act_j)
        write_json(ws / "bus_cad_audit.json", {
            "valid_unsat_active_fastener_count": len(act_j),
            "min_fastener_margin_of_safety": round((2150.0 / (1.40 * max_eq)) - 1.0, 4),
            "bus_shell_volume_mm3": info["bus_vol_mm3"],
            "bus_mass_committed_kg": bm,
            "cds_bus_code": CDS_BUS_CODE,
        })
    else:
        with file_atomic_lock("nf212_shared"):
            cur = _inspect_fcstd(fc_p)
            bm = cur.get("bus_mass", 0.0) if cur.get("bus_status") == "COMMITTED" else 0.0
            pm = round(max(PAY_FLOOR_KG, min(6.12, DISPENSER_MASS_CAP_KG - HARNESS_TARE_KG - bm - 0.03)) if bm > 0 else 6.12, 2)
            code = (
                "import json, sys; sys.path.append('/usr/lib/freecad-python3/lib')\n"
                "import FreeCAD, Part\n"
                f"doc = FreeCAD.openDocument({json.dumps(str(fc_p))})\n"
                "pay = doc.getObject('StarTracker_Baffle')\n"
                "co = Part.makeCylinder(42.0, 112.0, FreeCAD.Vector(113.15, 50.0, 105.0))\n"
                "ci = Part.makeCylinder(36.0, 112.0, FreeCAD.Vector(113.15, 50.0, 105.0))\n"
                "pay.Shape = co.cut(ci)\n"
                f"pay.CommittedMassKg = {pm}; pay.Status = 'COMMITTED'\n"
                f"doc.recompute(); doc.saveAs({json.dumps(str(fc_p))})\n"
            )
            subprocess.run(["python3", "-c", code], check=True, capture_output=True, timeout=35)
            reload_freecad_gui_file(fc_p)
            shs = read_multisheet_xlsx(xp)
            b3 = float(((shs.get("MassBudget") or {}).get("B3") or {}).get("value") or 0.0)
            c3 = str(((shs.get("MassBudget") or {}).get("C3") or {}).get("value") or "PENDING")
            update_single_sheet_xlsx(xp, "MassBudget", [
                ["Subsystem", "Mass_kg", "CDS-6U-REV4"],
                ["Harness_Tare_kg", HARNESS_TARE_KG, "FIXED"],
                ["Bus_Structure_kg", b3, c3],
                ["Payload_Power_kg", pm, "COMMITTED"],
                ["Total_Wet_Mass_kg", ("=SUM(B2:B4)", round(HARNESS_TARE_KG + b3 + pm, 2)), f"CAP_{DISPENSER_MASS_CAP_KG:.2f}"],
            ])
            reload_uno_pipe_documents([xp])
        info = _inspect_fcstd(fc_p)
        valid_orb = [i for i in range(1, 241) if i % 29 != 0]
        cos_b = math.cos(math.radians(28.0))
        area_r = 0.85
        p_tot_w = [
            area_r * ((0.0 if i % 3 == 0 else (1361.0 * cos_b + 185.0 * 0.32)) * 0.18 + 238.0 * 0.32 * 0.84)
            + ((16.0 + 19.5) if i % 3 == 0 else 38.0) + 6.4
            for i in valid_orb
        ]
        exp_tk = round(((sum(p_tot_w) / len(p_tot_w)) / (area_r * 0.84 * 5.670374419e-8)) ** 0.25, 2)
        write_json(ws / "payload_thermal_audit.json", {
            "valid_telemetry_sunlit_slice_count": sum(1 for i in valid_orb if i % 3 != 0),
            "eol_equilibrium_temp_k": exp_tk,
            "baffle_volume_mm3": info["pay_vol_mm3"],
            "payload_mass_committed_kg": pm,
            "cds_payload_code": CDS_PAY_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("spacecraft_bus_cad_eng", workspace_map, port)
    solve_role("payload_optics_thermal_eng", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    fc_p = hub / "cubesat_6u_assembly.FCStd"
    # Uncoordinated nominal targets 4.85 + 6.50 + 1.10 = 12.45 > 12.00 kg!
    subprocess.run(["python3", "-c", f"import sys; sys.path.append('/usr/lib/freecad-python3/lib'); import FreeCAD; d=FreeCAD.openDocument({json.dumps(str(fc_p))}); d.getObject('Bus_Chassis_Shell').CommittedMassKg=4.85; d.getObject('StarTracker_Baffle').CommittedMassKg=6.50; d.saveAs({json.dumps(str(fc_p))})"], check=True, capture_output=True, timeout=30)
