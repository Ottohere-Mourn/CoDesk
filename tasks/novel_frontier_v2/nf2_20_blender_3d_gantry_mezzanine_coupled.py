"""NF2-20: Live Blender 3.4 3D Robotic Palletizing Cell + Open Calc — Gantry Impact Load vs. Mezzanine Slab Live-Load Cap."""
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
    inspect_live_blender_readonly,
    inspect_live_uno_documents_readonly,
    launch_blender_gui_natural,
    launch_libreoffice_uno_natural,
    make_canary_code,
    read_json_safe,
    read_multisheet_xlsx,
    reload_blender_gui_file,
    reload_uno_pipe_documents,
    render_scanned_exhibit_png,
    update_single_sheet_xlsx,
    write_json,
    write_multipage_sop_pdf,
    write_multisheet_xlsx,
)

TASK_ID = "NF2-20"
PORTAL_PORT = 19620

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live `Blender 3.4` 3D Robotic Gantry Cell & Open Calc: Light-Curtain Clearance vs. EN 1991 Mezzanine Slab Load Cap",
    "domain": "Industrial Robotics Workcell CAD (`Blender 3.4` GUI) & Structural Mezzanine Engineering (`LibreOffice Calc`)",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("gantry_trajectory_eng", "mezzanine_buffer_eng"),
    "portal_port": PORTAL_PORT,
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

ISO13855_CODE = make_canary_code("ISO13855-ROB", "curtain-clr-025m")
EN1991_CODE = make_canary_code("EN1991-MEZZ", "cat-e2-psi-rack")
SLAB_CAP_KG = 4750.0  # Gantry floor 2150 + Buffer floor 2380 = 4530 <= 4750; pref 2420 + 2600 = 5020 > 4750!
GANTRY_FLOOR_KG = 2150.0
BUFFER_FLOOR_KG = 2380.0

BLENDER_INIT_CELL_PY = r"""
import bpy, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.5))
lc = bpy.context.active_object; lc.name = "LightCurtain_Plane"; lc.scale = (0.1, 3.0, 2.0)
bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.8, location=(0.05, 0.0, 0.9))
ee = bpy.context.active_object; ee.name = "Gantry_EndEffector"
ee["gantry_dynamic_kg"] = 0.0; ee["status"] = "PENDING"
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3.6, 0.0, 0.6))
rk = bpy.context.active_object; rk.name = "AGV_Accumulator_Rack"
rk["buffer_live_kg"] = 0.0; rk["status"] = "PENDING"
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Gantry Light-Curtain Clearance & Dynamic Impact Load (`gantry_trajectory_eng`)",
        "",
        "## Objective",
        f"Move `Gantry_EndEffector` to `x >= 0.65 m` (clear of `LightCurtain_Plane` at `x=0`) in `{b}/workspace/shared_docs/pallet_mezzanine_cell.blend{b}` (open in **Blender 3.4** GUI) and commit `gantry_dynamic_kg` in `.blend` and `{b}/workspace/shared_docs/Mezzanine_Structural_Load.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_Gantry_13855.pdf{b}` and `{b}/workspace/exhibits/mezzanine_placard.png{b}`, analyze `{b}/workspace/servo/decel_profiles.sqlite{b}`, and write `{b}/workspace/gantry_clearance_audit.json{b}`.",
    ])
    tb = "\n".join([
        "# Work Order — AGV Accumulator Rack Placement & EN 1991 Mezzanine Load (`mezzanine_buffer_eng`)",
        "",
        "## Objective",
        f"Move `AGV_Accumulator_Rack` inside the safe slab zone `x in [1.80, 2.80] m` (v0 `x=3.6` overhangs slab edge!) in `{b}/workspace/shared_docs/pallet_mezzanine_cell.blend{b}` (open in **Blender 3.4** GUI) and commit `buffer_live_kg` in `.blend` and `{b}/workspace/shared_docs/Mezzanine_Structural_Load.xlsx{b}` (open in Calc) per `{b}/workspace/docs/SOP_Mezzanine_1991.pdf{b}` and `{b}/workspace/exhibits/mezzanine_placard.png{b}`, analyze `{b}/workspace/pallets/sku_layers.sqlite{b}`, and write `{b}/workspace/mezzanine_load_audit.json{b}`.",
    ])
    return {"gantry_trajectory_eng": ta, "mezzanine_buffer_eng": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["gantry_trajectory_eng"]
    ws_b = workspace_map["mezzanine_buffer_eng"]
    hub = workspace_map["__shared_hub__"]
    for d in (ws_a / "servo", ws_a / "docs", ws_a / "exhibits", ws_b / "pallets", ws_b / "docs", ws_b / "exhibits", hub):
        d.mkdir(parents=True, exist_ok=True)

    subprocess.run(["blender", "-b", "--python-expr", BLENDER_INIT_CELL_PY, "--", str(hub / "pallet_mezzanine_cell.blend")], check=True, capture_output=True, timeout=45)
    write_multisheet_xlsx(hub / "Mezzanine_Structural_Load.xlsx", [
        ("DeckLoads", [
            ["Equipment", "Design_Load_kg", "BAY-MEZZ-4750"],
            ["Gantry_Dynamic_Load_kg", 0.0, "PENDING"],
            ["AGV_Buffer_Rack_kg", 0.0, "PENDING"],
            ["Total_Deck_Load_kg", ("=SUM(B2:B3)", 0.0), f"CAP_{SLAB_CAP_KG:.1f}"],
        ]),
    ])
    render_scanned_exhibit_png(
        ws_a / "exhibits/mezzanine_placard.png",
        "MEZZANINE STRUCTURAL DECK & ISO 13855 SAFETY PLACARD",
        [
            f"Maximum Coupled Mezzanine Deck Live Load: gantry_dynamic_kg + buffer_live_kg <= {SLAB_CAP_KG:.1f} kg",
            f"Gantry Dynamic Reaction Floor:            >= {GANTRY_FLOOR_KG:.1f} kg (preferred high-speed cycle = 2420.0 kg)",
            f"AGV Accumulator Buffer Floor:             >= {BUFFER_FLOOR_KG:.1f} kg (preferred 4-pallet buffer = 2600.0 kg)",
            f"ISO 13855 Safety Code: {ISO13855_CODE}  |  EN 1991 Deck Code: {EN1991_CODE}",
        ],
        stamp_text="PLANT STRUCTURAL PE",
    )
    (ws_b / "exhibits/mezzanine_placard.png").write_bytes((ws_a / "exhibits/mezzanine_placard.png").read_bytes())

    # Role A: ISO 13855 minimum light-curtain safety distance S = K * (t1 + t2) + C, where K = 2000 mm/s if S <= 500 else re-evaluate at K = 1600 mm/s (if >500, S = max(500, 1600*(t1+t2) + C)) + C = 8*(d - 14) mm!
    with sqlite3.connect(str(ws_a / "servo/decel_profiles.sqlite")) as conn:
        conn.execute("CREATE TABLE stop_tests (axis_cycle INTEGER PRIMARY KEY, t1_curtain_s REAL, t2_brake_s REAL, beam_res_d_mm REAL)")
        for i in range(1, 151):
            conn.execute("INSERT INTO stop_tests VALUES (?,?,?,?)", (i, 0.018, 0.240 + (i % 6) * 0.012, 30.0))
        conn.execute("CREATE TABLE iso13855_formula (rule TEXT)")
        conn.execute("INSERT INTO iso13855_formula VALUES ('C = 8*(d - 14); S_2000 = 2000*(t1+t2) + C; if S_2000 > 500 then S_mm = max(500.0, 1600*(t1+t2) + C) else S_2000')")
        conn.commit()

    write_multipage_sop_pdf(ws_a / "docs/SOP_Gantry_13855.pdf", "SOP-IND-2020A: ISO 13855 Curtain Distance & Blender Gantry Pose", [
        ("1. Blender Gantry Repositioning & ISO 13855", [
            f"1.1 Set Gantry_EndEffector.location.x >= 0.65 in pallet_mezzanine_cell.blend, commit Gantry_EndEffector['gantry_dynamic_kg'] (>={GANTRY_FLOOR_KG} kg, status='COMMITTED') within the {SLAB_CAP_KG} kg slab cap, sync open Blender GUI, and update Mezzanine_Structural_Load.xlsx B2 & C2='COMMITTED'.",
            "1.2 Compute worst-case (maximum) required ISO 13855 safety distance S_mm across all 150 cycles in decel_profiles.sqlite.",
        ]),
        ("2. JSON Schema (/workspace/gantry_clearance_audit.json)", [
            "Keys: worst_case_iso13855_s_mm (float, 2 dec), end_effector_x_m (float, 3 dec), gantry_dynamic_committed_kg (float, 1 dec), iso13855_code (str).",
        ]),
    ])

    # Role B: EN 1991-1-1 pallet mass including CHEP hardwood tare (+25.5 kg/pallet in SQLite!) & forklift dynamic amplification phi = 1.40 on active transfer pallet!
    with sqlite3.connect(str(ws_b / "pallets/sku_layers.sqlite")) as conn:
        conn.execute("CREATE TABLE queued_pallets (pallet_slot INTEGER PRIMARY KEY, layers INTEGER, cases_per_layer INTEGER, case_mass_kg REAL, is_active_transfer INTEGER)")
        for k in range(1, 5):
            conn.execute("INSERT INTO queued_pallets VALUES (?,?,?,?,?)", (k, 5, 10, 10.8, 1 if k == 1 else 0))
        conn.execute("CREATE TABLE en1991_pallet_factors (chep_pallet_tare_kg REAL, active_transfer_dynamic_phi REAL)")
        conn.execute("INSERT INTO en1991_pallet_factors VALUES (25.5, 1.40)")
        conn.commit()

    write_multipage_sop_pdf(ws_b / "docs/SOP_Mezzanine_1991.pdf", "SOP-IND-2020B: EN 1991-1-1 Rack Placement & Factored Pallet Mass", [
        ("1. Blender Rack Placement & EN 1991 Load", [
            f"1.1 Move AGV_Accumulator_Rack.location.x into [1.80, 2.80] in pallet_mezzanine_cell.blend, commit AGV_Accumulator_Rack['buffer_live_kg'] (>={BUFFER_FLOOR_KG} kg, status='COMMITTED') within the {SLAB_CAP_KG} kg slab cap, sync open Blender GUI, and update Mezzanine_Structural_Load.xlsx B3 & C3='COMMITTED'.",
            "1.2 Compute exact EN 1991 factored 4-pallet mass kg from sku_layers.sqlite (including CHEP pallet tare on all 4 slots and dynamic_phi on is_active_transfer=1).",
        ]),
        ("2. JSON Schema (/workspace/mezzanine_load_audit.json)", [
            "Keys: factored_4pallet_mass_kg (float, 2 dec), rack_x_m (float, 3 dec), buffer_live_committed_kg (float, 1 dec), en1991_code (str).",
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
    launch_blender_gui_natural(hub / "pallet_mezzanine_cell.blend")
    launch_libreoffice_uno_natural([hub / "Mezzanine_Structural_Load.xlsx"])


def _inspect_cell_blend(bp: Path) -> dict[str, Any]:
    if not bp.is_file():
        return {}
    code = (
        "import bpy, json\n"
        "ee = bpy.data.objects.get('Gantry_EndEffector'); rk = bpy.data.objects.get('AGV_Accumulator_Rack'); lc = bpy.data.objects.get('LightCurtain_Plane')\n"
        "out = {'all3': bool(ee and rk and lc), 'ee_x': round(float(ee.location.x), 3) if ee else -9.0, 'g_kg': float(ee.get('gantry_dynamic_kg', -1.0)) if ee else -1.0, 'g_st': str(ee.get('status', '')) if ee else '', 'rk_x': round(float(rk.location.x), 3) if rk else -9.0, 'b_kg': float(rk.get('buffer_live_kg', -1.0)) if rk else -1.0, 'b_st': str(rk.get('status', '')) if rk else ''}\n"
        "print('CELL_JSON:' + json.dumps(out))\n"
    )
    cp = subprocess.run(["blender", "-b", str(bp), "--python-expr", code], capture_output=True, text=True, timeout=40)
    for ln in cp.stdout.splitlines():
        if ln.startswith("CELL_JSON:"):
            return json.loads(ln.split("CELL_JSON:", 1)[1])
    return {}


def grade(workspace_map: dict[str, Path], service_state: dict[str, Any], wall_seconds: float, active_roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    act = set(active_roles or META["roles"])
    has_a, has_b = ("gantry_trajectory_eng" in act), ("mezzanine_buffer_eng" in act)
    ws_a = workspace_map["gantry_trajectory_eng"]
    ws_b = workspace_map["mezzanine_buffer_eng"]
    hub = workspace_map["__shared_hub__"]
    bl = _inspect_cell_blend(hub / "pallet_mezzanine_cell.blend")
    bl_live = inspect_live_blender_readonly()
    uno_st = inspect_live_uno_documents_readonly()
    xp = hub / "Mezzanine_Structural_Load.xlsx"
    shs = read_multisheet_xlsx(xp) if xp.is_file() else {}
    evs = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
    ja = read_json_safe(ws_a / "gantry_clearance_audit.json")
    jb = read_json_safe(ws_b / "mezzanine_load_audit.json")

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    def _cv(ref: str) -> Any:
        v = ((evs.get("DeckLoads") or {}).get(ref) or {}).get("value")
        return v if v not in (None, "") else ((shs.get("DeckLoads") or {}).get(ref) or {}).get("value")

    # ISO 13855 worst-case: max t2 = 0.240 + 5*0.012 = 0.300 -> t1+t2 = 0.318; C = 8*(30-14) = 128 mm; S_2000 = 2000*0.318 + 128 = 764 > 500 -> S_mm = max(500, 1600*0.318 + 128) = 636.80 mm!
    exp_s_mm = round(max(500.0, 1600.0 * (0.018 + 0.300) + 128.0), 2)
    # EN 1991 4-pallet mass: unit_gross = 5*10*10.8 + 25.5 = 565.5 kg; slot 1 * 1.40 + 3 * 565.5 = 791.7 + 1696.5 = 2488.20 kg!
    exp_pal_kg = round(565.5 * 1.40 + 3.0 * 565.5, 2)

    gk = _f(bl.get("g_kg"), -1.0)
    bk = _f(bl.get("b_kg"), -1.0)

    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.08, "Missing gantry_clearance_audit.json"),
        ("a_pose", bool(bl.get("all3")) and _f(bl.get("ee_x")) >= 0.65, 0.20, "Gantry_EndEffector.x < 0.65 m in .blend"),
        ("a_commit", gk >= GANTRY_FLOOR_KG and bl.get("g_st") == "COMMITTED" and abs(_f(_cv("B2")) - gk) <= 0.5, 0.22, "gantry_dynamic_kg mismatch across .blend / Calc"),
        ("a_code", ja.get("iso13855_code") == ISO13855_CODE, 0.16, "iso13855_code mismatch"),
        ("a_fine_s1600_stepdown", abs(_f(ja.get("worst_case_iso13855_s_mm")) - exp_s_mm) <= 0.2, 0.34, f"worst_case_iso13855_s_mm != {exp_s_mm} (check S>500 -> K=1600 mm/s stepdown)"),
    ]

    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.08, "Missing mezzanine_load_audit.json"),
        ("b_pose", bool(bl.get("all3")) and (1.80 <= _f(bl.get("rk_x")) <= 2.80), 0.20, "AGV_Accumulator_Rack.x outside [1.80, 2.80] m"),
        ("b_commit", bk >= BUFFER_FLOOR_KG and bl.get("b_st") == "COMMITTED" and abs(_f(_cv("B3")) - bk) <= 0.5, 0.22, "buffer_live_kg mismatch across .blend / Calc"),
        ("b_code", jb.get("en1991_code") == EN1991_CODE, 0.16, "en1991_code mismatch"),
        ("b_fine_chep_phi_mass", abs(_f(jb.get("factored_4pallet_mass_kg")) - exp_pal_kg) <= 0.5, 0.34, f"factored_4pallet_mass_kg != {exp_pal_kg} (check +25.5kg CHEP tare & 1.40x active slot)"),
    ]

    eff_g = gk if (has_a and gk > 0) else (GANTRY_FLOOR_KG if not has_a else 99999.0)
    eff_b = bk if (has_b and bk > 0) else (BUFFER_FLOOR_KG if not has_b else 99999.0)
    fl_ok = ((not has_a) or gk >= GANTRY_FLOOR_KG) and ((not has_b) or bk >= BUFFER_FLOOR_KG)
    bl_ok = bool(bl_live.get("running")) and (not bl_live.get("is_dirty"))
    calc_ok = all(not d.get("is_modified") for d in (uno_st.get("docs") or {}).values())
    act_done = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))

    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_slab_4750_cap", fl_ok and (eff_g + eff_b <= SLAB_CAP_KG), 0.12, f"Coupled slab load {eff_g + eff_b:.1f} kg exceeds {SLAB_CAP_KG:.1f} kg!"),
        ("j_blender_uno_sync", act_done and bl_ok and calc_ok, 0.10, "Live Blender 3.4 or Calc out-of-sync with disk"),
    ]
    return build_grade_payload(task_id=TASK_ID, checks_a=checks_a, checks_b=checks_b, checks_joint=checks_joint, tickets_by_role=build_tickets_by_role(), service_state=service_state, wall_seconds=wall_seconds)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bp = hub / "pallet_mezzanine_cell.blend"
    xp = hub / "Mezzanine_Structural_Load.xlsx"

    with file_atomic_lock("nf220_shared"):
        cur = _inspect_cell_blend(bp)
        shs = read_multisheet_xlsx(xp)
        b2 = float(((shs.get("DeckLoads") or {}).get("B2") or {}).get("value") or 0.0)
        c2 = str(((shs.get("DeckLoads") or {}).get("C2") or {}).get("value") or "PENDING")
        b3 = float(((shs.get("DeckLoads") or {}).get("B3") or {}).get("value") or 0.0)
        c3 = str(((shs.get("DeckLoads") or {}).get("C3") or {}).get("value") or "PENDING")
        if role == "gantry_trajectory_eng":
            bk = cur.get("b_kg", 0.0) if cur.get("b_st") == "COMMITTED" else 0.0
            val = round(max(GANTRY_FLOOR_KG, min(2240.0, SLAB_CAP_KG - bk - 20.0)) if bk > 0 else 2240.0, 1)
            py = f"import bpy,sys; ee=bpy.data.objects['Gantry_EndEffector']; ee.location.x=0.85; ee['gantry_dynamic_kg']={val}; ee['status']='COMMITTED'; bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])"
            b2, c2 = val, "COMMITTED"
        else:
            gk = cur.get("g_kg", 0.0) if cur.get("g_st") == "COMMITTED" else 0.0
            val = round(max(BUFFER_FLOOR_KG, min(2460.0, SLAB_CAP_KG - gk - 20.0)) if gk > 0 else 2460.0, 1)
            py = f"import bpy,sys; rk=bpy.data.objects['AGV_Accumulator_Rack']; rk.location.x=2.25; rk['buffer_live_kg']={val}; rk['status']='COMMITTED'; bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])"
            b3, c3 = val, "COMMITTED"
        subprocess.run(["blender", "-b", str(bp), "--python-expr", py, "--", str(bp)], check=True, capture_output=True, timeout=45)
        reload_blender_gui_file(bp)
        update_single_sheet_xlsx(xp, "DeckLoads", [
            ["Equipment", "Design_Load_kg", "BAY-MEZZ-4750"],
            ["Gantry_Dynamic_Load_kg", b2, c2],
            ["AGV_Buffer_Rack_kg", b3, c3],
            ["Total_Deck_Load_kg", ("=SUM(B2:B3)", round(b2 + b3, 1)), f"CAP_{SLAB_CAP_KG:.1f}"],
        ])
        reload_uno_pipe_documents([xp])

    if role == "gantry_trajectory_eng":
        write_json(ws / "gantry_clearance_audit.json", {
            "worst_case_iso13855_s_mm": 636.80, "end_effector_x_m": 0.85,
            "gantry_dynamic_committed_kg": val, "iso13855_code": ISO13855_CODE,
        })
    else:
        write_json(ws / "mezzanine_load_audit.json", {
            "factored_4pallet_mass_kg": 2488.20, "rack_x_m": 2.25,
            "buffer_live_committed_kg": val, "en1991_code": EN1991_CODE,
        })


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    del state_dir
    solve_role("gantry_trajectory_eng", workspace_map, port)
    solve_role("mezzanine_buffer_eng", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map["__shared_hub__"]
    bp = hub / "pallet_mezzanine_cell.blend"
    subprocess.run(["blender", "-b", str(bp), "--python-expr", "import bpy,sys; bpy.data.objects['Gantry_EndEffector']['gantry_dynamic_kg']=2420.0; bpy.data.objects['AGV_Accumulator_Rack']['buffer_live_kg']=2600.0; bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])", "--", str(bp)], check=True, capture_output=True, timeout=40)
