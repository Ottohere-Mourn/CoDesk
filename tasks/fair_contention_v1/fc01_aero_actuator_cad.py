"""FC-01: Aerospace Coaxial 4-Stage Servo-Actuator Co-Design (.FCStd + .xlsx + .step + Cycles Rig + PLM Canvas)."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlparse

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

TASK_ID = "FC-01"
META = {
    "id": TASK_ID,
    "title": "Aerospace Coaxial 4-Stage Servo-Actuator CAD/CAE Co-Design",
    "domain": "Aerospace Mechanical CAD / Multi-Physics Test Stand (FreeCAD + Blender Cycles + LibreOffice Calc + Chromium PLM)",
    "arena": "Coaxial Ti-6Al-4V Servo-Actuator Shared .FCStd & Envelope Coupling",
    "conflict_archetype": "monolithic_fcstd_zip_lost_update + bidirectional_airgap_mass_cg_coupling + single_session_plm_csv_export",
    "roles": ("stator_lead", "rotor_lead"),
    "portal_port": 19410,
    "canonical_project": "servo_actuator.FCStd",
    "conc_role_timeout_s": 2400,
    "seq_role_timeout_s": 2880,
}

RHO_TI64_G_MM3 = 0.00443
STAGES: tuple[tuple[str, float, float], ...] = (
    ("S1", 0.0, 24.0),
    ("S2", 24.0, 22.0),
    ("S3", 46.0, 21.0),
    ("S4", 67.0, 21.0),
)
STATOR_SOLIDS = tuple(f"Stator_{s}" for s, _, _ in STAGES)
ROTOR_SOLIDS = tuple(f"Rotor_{s}" for s, _, _ in STAGES)

STATOR_MIN_Q_W = {"S1": 140.0, "S2": 125.0, "S3": 115.0, "S4": 110.0}
STATOR_MIN_Q_TOTAL_W = 510.0
STATOR_FIN_RANGE = (16, 24)
STATOR_MAX_R_OUT_MM = 44.50

ROTOR_MIN_K_KNM = {"S1": 94.0, "S2": 96.0, "S3": 70.0, "S4": 66.0}
ROTOR_MIN_K_TOTAL_KNM = 340.0
ROTOR_SPLINE_RANGE = (12, 20)
ROTOR_MIN_BORE_MM = 18.00

STATOR_MIN_MASS_G = 365.0
ROTOR_MIN_MASS_G = 365.0
GLOBAL_AIRGAP_RANGE_MM = (1.18, 1.30)
GLOBAL_TOTAL_MASS_RANGE_G = (740.0, 820.0)
GLOBAL_CG_Z_RANGE_MM = (40.80, 42.95)
GLOBAL_MAX_INTERFERENCE_MM3 = 0.01

REQUIRED_PUBLIC_TOKENS: tuple[str, ...] = (
    "/workspace/servo_actuator.FCStd",
    "/workspace/Actuator_Mass_CG.xlsx",
    "/workspace/release/servo_actuator_assy.step",
    "/workspace/renders/rig_cutaway_iso.png",
    "/workspace/renders/rig_cutaway_axial.png",
    "/api/bench/actuation_rig",
    "/api/plm/submit",
    "/api/plm/status",
    "Stator_Schedule",
    "Rotor_Schedule",
    "Assembly_Summary",
    "stage_isolation",
    "full_assembly",
    "1.18",
    "1.30",
    "820.0",
    "365.0",
    "40.80",
    "42.95",
)

FREECAD_EVAL_SNIPPET = r'''
import FreeCAD, Part, Mesh, math, json, hashlib
import numpy as np
from pathlib import Path

RHO = 0.00443
STAGES = [("S1", 0.0, 24.0), ("S2", 24.0, 22.0), ("S3", 46.0, 21.0), ("S4", 67.0, 21.0)]
SWIRL = {"S1": 1.06, "S2": 1.02, "S3": 0.98, "S4": 0.94}
HARM = {"S1": 1.05, "S2": 1.00, "S3": 0.96, "S4": 0.92}

def solid_fingerprint(sol):
    bb = sol.BoundBox
    payload = (
        f"{round(sol.Volume, 2)}|{round(sol.Area, 2)}|"
        f"{round(sol.CenterOfMass.x, 2)}|{round(sol.CenterOfMass.y, 2)}|{round(sol.CenterOfMass.z, 2)}|"
        f"{round(bb.XMin, 2)}|{round(bb.XMax, 2)}|{round(bb.YMin, 2)}|{round(bb.YMax, 2)}|{round(bb.ZMin, 2)}|{round(bb.ZMax, 2)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def slice_polar_occ(sol, z_mid, r_min, r_max, nr=26, nth=240):
    verts, tris = sol.tessellate(0.08)
    V = np.array([[v.x, v.y, v.z] for v in verts], dtype=np.float64)
    T = np.array(tris, dtype=np.int32)
    if len(T) == 0:
        return np.zeros((nr, nth)), np.linspace(r_min, r_max, nr), np.linspace(0.0, 2.0*math.pi, nth, endpoint=False)
    P = V[T]
    z = P[:, :, 2] - z_mid
    tri_pts = {}
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        z0, z1 = z[:, e0], z[:, e1]
        mask = ((z0 <= 0.0) & (z1 > 0.0)) | ((z1 <= 0.0) & (z0 > 0.0))
        if np.any(mask):
            t = z0[mask] / (z0[mask] - z1[mask])
            pts = P[mask, e0, :2] + t[:, None] * (P[mask, e1, :2] - P[mask, e0, :2])
            for ti, pt in zip(np.where(mask)[0], pts):
                tri_pts.setdefault(int(ti), []).append(pt)
    seg_list = [v[:2] for v in tri_pts.values() if len(v) >= 2]
    r_grid = np.linspace(r_min, r_max, nr)
    th_grid = np.linspace(0.0, 2.0 * math.pi, nth, endpoint=False)
    if not seg_list:
        return np.zeros((nr, nth)), r_grid, th_grid
    S = np.array(seg_list, dtype=np.float64)
    x1, y1 = S[:, 0, 0], S[:, 0, 1]
    x2, y2 = S[:, 1, 0], S[:, 1, 1]
    RR, TT = np.meshgrid(r_grid, th_grid, indexing="ij")
    PX = (RR * np.cos(TT)).ravel()[:, None]
    PY = (RR * np.sin(TT)).ravel()[:, None]
    cond_y = (y1[None, :] > PY) != (y2[None, :] > PY)
    denom = np.where(np.abs(y2 - y1)[None, :] < 1e-12, 1e-12, (y2 - y1)[None, :])
    x_int = x1[None, :] + (PY - y1[None, :]) * (x2[None, :] - x1[None, :]) / denom
    crossings = np.sum(cond_y & (PX < x_int), axis=1)
    occ = (crossings % 2 == 1).astype(np.float64).reshape(nr, nth)
    return occ, r_grid, th_grid

def inspect_fcstd(fcstd_path_str, stl_out_str="", step_path_str=""):
    doc = FreeCAD.openDocument(fcstd_path_str)
    stator_stages = {}
    rotor_stages = {}
    missing_objects = []
    all_shapes = []
    interf_mm3 = 0.0

    for sname, z0, h in STAGES:
        s_obj = doc.getObject(f"Stator_{sname}")
        r_obj = doc.getObject(f"Rotor_{sname}")
        if s_obj is None or not hasattr(s_obj, "Shape") or len(s_obj.Shape.Solids) != 1:
            missing_objects.append(f"Stator_{sname}")
        if r_obj is None or not hasattr(r_obj, "Shape") or len(r_obj.Shape.Solids) != 1:
            missing_objects.append(f"Rotor_{sname}")
        if missing_objects:
            continue

        s_sol = s_obj.Shape.Solids[0]
        r_sol = r_obj.Shape.Solids[0]
        all_shapes.extend([s_sol, r_sol])

        s_verts, _ = s_sol.tessellate(0.08)
        s_rs = [math.hypot(v.x, v.y) for v in s_verts]
        s_rin, s_rout = min(s_rs), max(s_rs)
        s_bb = s_sol.BoundBox
        s_z_ok = (s_bb.ZMin >= z0 - 0.08) and (s_bb.ZMax <= z0 + h + 0.08) and ((s_bb.ZMax - s_bb.ZMin) >= h - 0.5)
        s_occ, _, _ = slice_polar_occ(s_sol, z0 + 0.5 * h, s_rin + 0.15, max(s_rin + 0.5, s_rout - 0.25))
        nr = s_occ.shape[0]
        s_fins = int(np.sum((s_occ[-2, :] > 0.5) & (np.roll(s_occ[-2, :], 1) <= 0.5)))
        outer_open = float(1.0 - np.mean(s_occ[nr // 2:, :]))
        choke = max(0.25, min(1.0, 4.0 * outer_open * (1.0 - 0.45 * (1.0 - outer_open))))
        inner_solid = float(np.mean(s_occ[:nr // 3, :]))
        cond = max(0.25, min(1.0, inner_solid / 0.72))
        q_w = (s_sol.Area / 1000.0) * 7.2 * choke * cond * SWIRL[sname]
        stator_stages[sname] = {
            "stage": sname,
            "mass_g": round(s_sol.Volume * RHO, 3),
            "volume_mm3": round(s_sol.Volume, 2),
            "area_mm2": round(s_sol.Area, 2),
            "cg_z_mm": round(s_sol.CenterOfMass.z, 3),
            "r_in_mm": round(s_rin, 3),
            "r_out_mm": round(s_rout, 3),
            "fin_count": s_fins,
            "q_diss_w": round(q_w, 2),
            "z_span_ok": bool(s_z_ok),
            "fingerprint": solid_fingerprint(s_sol),
        }

        r_verts, _ = r_sol.tessellate(0.08)
        r_rs = [math.hypot(v.x, v.y) for v in r_verts]
        r_bore, r_tip = min(r_rs), max(r_rs)
        r_bb = r_sol.BoundBox
        r_z_ok = (r_bb.ZMin >= z0 - 0.08) and (r_bb.ZMax <= z0 + h + 0.08) and ((r_bb.ZMax - r_bb.ZMin) >= h - 0.5)
        r_occ, r_grid, th_grid = slice_polar_occ(r_sol, z0 + 0.5 * h, r_bore + 0.15, max(r_bore + 0.5, r_tip - 0.20))
        dr = float(r_grid[1] - r_grid[0])
        dth = float(th_grid[1] - th_grid[0])
        jp = float(np.sum(r_occ * ((r_grid ** 3)[:, None]) * dr * dth))
        r_splines = int(np.sum((r_occ[-2, :] > 0.5) & (np.roll(r_occ[-2, :], 1) <= 0.5)))
        sp_engage = 1.0 if r_splines >= 8 else 0.0
        k_knm = (42.4 * jp) / (h * 1e6) * HARM[sname] * 100.0 * sp_engage
        rotor_stages[sname] = {
            "stage": sname,
            "mass_g": round(r_sol.Volume * RHO, 3),
            "volume_mm3": round(r_sol.Volume, 2),
            "area_mm2": round(r_sol.Area, 2),
            "cg_z_mm": round(r_sol.CenterOfMass.z, 3),
            "r_bore_mm": round(r_bore, 3),
            "r_tip_mm": round(r_tip, 3),
            "spline_count": r_splines,
            "k_torsion_knm": round(k_knm, 2),
            "z_span_ok": bool(r_z_ok),
            "fingerprint": solid_fingerprint(r_sol),
        }

        if s_rin <= r_tip + 0.05:
            try:
                interf_mm3 += float(s_sol.common(r_sol).Volume)
            except Exception:
                interf_mm3 += 999.0

    if missing_objects:
        return {"ok": False, "error": f"Missing or invalid single-solid Part::Feature objects: {missing_objects}"}

    if stl_out_str:
        comp = Part.makeCompound(all_shapes)
        mesh = Mesh.Mesh(comp.tessellate(0.12))
        mesh.write(stl_out_str)

    step_check = {"checked": False, "ok": False}
    if step_path_str:
        step_check["checked"] = True
        sp = Path(step_path_str)
        if sp.is_file() and sp.stat().st_size > 1024:
            try:
                sh_step = Part.read(str(sp))
                fc_vol = sum(s.Volume for s in all_shapes)
                st_solids = len(sh_step.Solids)
                st_vol = float(sh_step.Volume)
                step_check = {
                    "checked": True,
                    "ok": (st_solids == 8 and abs(st_vol - fc_vol) <= max(5.0, 0.003 * fc_vol)),
                    "solid_count": st_solids,
                    "step_volume_mm3": round(st_vol, 2),
                    "fcstd_volume_mm3": round(fc_vol, 2),
                }
            except Exception as exc:
                step_check = {"checked": True, "ok": False, "error": str(exc)}

    m_stator = sum(v["mass_g"] for v in stator_stages.values())
    m_rotor = sum(v["mass_g"] for v in rotor_stages.values())
    m_total = m_stator + m_rotor
    cg_stator = sum(v["mass_g"] * v["cg_z_mm"] for v in stator_stages.values()) / max(1e-9, m_stator)
    cg_rotor = sum(v["mass_g"] * v["cg_z_mm"] for v in rotor_stages.values()) / max(1e-9, m_rotor)
    cg_total = (m_stator * cg_stator + m_rotor * cg_rotor) / max(1e-9, m_total)
    airgaps = {
        sn: round(stator_stages[sn]["r_in_mm"] - rotor_stages[sn]["r_tip_mm"], 3)
        for sn, _, _ in STAGES
    }
    return {
        "ok": True,
        "stator_stages": stator_stages,
        "rotor_stages": rotor_stages,
        "summary": {
            "stator_mass_g": round(m_stator, 2),
            "rotor_mass_g": round(m_rotor, 2),
            "total_mass_g": round(m_total, 2),
            "stator_cg_z_mm": round(cg_stator, 3),
            "rotor_cg_z_mm": round(cg_rotor, 3),
            "total_cg_z_mm": round(cg_total, 3),
            "q_diss_total_w": round(sum(v["q_diss_w"] for v in stator_stages.values()), 2),
            "k_torsion_total_knm": round(sum(v["k_torsion_knm"] for v in rotor_stages.values()), 2),
            "airgaps_mm": airgaps,
            "min_airgap_mm": round(min(airgaps.values()), 3),
            "max_airgap_mm": round(max(airgaps.values()), 3),
            "interference_mm3": round(interf_mm3, 4),
        },
        "step_check": step_check,
    }
'''


def run_freecad_inspect(fcstd_path: Path, stl_out: Path | None = None, step_path: Path | None = None) -> dict:
    if not fcstd_path.is_file():
        return {"ok": False, "error": f"Missing {fcstd_path}"}
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        body_p = td / "eval_body.py"
        run_p = td / "eval_run.py"
        out_p = td / "eval_out.json"
        stl_str = str(stl_out) if stl_out is not None else ""
        step_str = str(step_path) if step_path is not None else ""
        body_src = (
            FREECAD_EVAL_SNIPPET
            + f"\nres = inspect_fcstd({str(fcstd_path)!r}, {stl_str!r}, {step_str!r})\n"
            + f"Path({str(out_p)!r}).write_text(json.dumps(res), encoding='utf-8')\n"
        )
        body_p.write_text(body_src, encoding="utf-8")
        run_p.write_text(f"ns = {{}}; exec(open({str(body_p)!r}, encoding='utf-8').read(), ns, ns)\n", encoding="utf-8")
        cp = subprocess.run(["freecadcmd", str(run_p)], capture_output=True, text=True, timeout=75)
        if not out_p.is_file():
            return {"ok": False, "error": f"freecadcmd failed (rc={cp.returncode}): {cp.stderr[-400:]}"}
        return json.loads(out_p.read_text(encoding="utf-8"))


def run_cycles_cutaway_renders(stl_path: Path, iso_png: Path, axial_png: Path, fast_selfval: bool = False) -> dict:
    iso_png.parent.mkdir(parents=True, exist_ok=True)
    axial_png.parent.mkdir(parents=True, exist_ok=True)
    res_x, res_y = (160, 90) if fast_selfval else (1152, 648)
    samples = 4 if fast_selfval else int(os.environ.get("PARAGUI_FC01_SAMPLES", "340"))
    threads = 2 if fast_selfval else 4
    with tempfile.TemporaryDirectory() as tmp:
        bl_p = Path(tmp) / "render_cutaway.py"
        bl_p.write_text(
            f"""
import bpy, math
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_mesh.stl(filepath={str(stl_path)!r})
obj = bpy.context.selected_objects[0]

bpy.ops.mesh.primitive_cube_add(size=68.0, location=(34.0, -34.0, 44.0))
cutter = bpy.context.active_object
mod = obj.modifiers.new(name="Cutaway", type="BOOLEAN")
mod.operation = "DIFFERENCE"
mod.object = cutter
cutter.hide_render = True

mat = bpy.data.materials.new("Ti64_Aero")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Metallic"].default_value = 0.84
bsdf.inputs["Roughness"].default_value = 0.27
obj.data.materials.append(mat)

bpy.ops.object.light_add(type="AREA", location=(95.0, -95.0, 125.0))
bpy.context.active_object.data.energy = 85000.0
bpy.ops.object.light_add(type="AREA", location=(-85.0, 75.0, 95.0))
bpy.context.active_object.data.energy = 42000.0

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.use_denoising = False
sc.cycles.samples = {samples}
sc.render.resolution_x = {res_x}
sc.render.resolution_y = {res_y}

bpy.ops.object.camera_add(location=(115.0, -115.0, 106.0), rotation=(math.radians(60), 0.0, math.radians(45)))
cam_iso = bpy.context.active_object
sc.camera = cam_iso
sc.render.filepath = {str(Path(tmp) / 'iso.png')!r}
bpy.ops.render.render(write_still=True)

bpy.ops.object.camera_add(location=(0.0, 0.0, 185.0), rotation=(0.0, 0.0, 0.0))
cam_ax = bpy.context.active_object
sc.camera = cam_ax
sc.render.filepath = {str(Path(tmp) / 'ax.png')!r}
bpy.ops.render.render(write_still=True)
""",
            encoding="utf-8",
        )
        t0 = time.monotonic()
        cp = subprocess.run(
            ["blender", "-b", "-noaudio", "-t", str(threads), "-P", str(bl_p)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        dt = round(time.monotonic() - t0, 2)
        if (Path(tmp) / "iso.png").is_file():
            shutil.copyfile(Path(tmp) / "iso.png", iso_png)
        if (Path(tmp) / "ax.png").is_file():
            shutil.copyfile(Path(tmp) / "ax.png", axial_png)
        ok = (
            cp.returncode == 0
            and iso_png.is_file()
            and axial_png.is_file()
            and iso_png.stat().st_size > 1000
            and axial_png.stat().st_size > 1000
        )
        return {
            "ok": ok,
            "elapsed_s": dt,
            "iso_bytes": iso_png.stat().st_size if iso_png.is_file() else 0,
            "axial_bytes": axial_png.stat().st_size if axial_png.is_file() else 0,
            "error": "" if ok else cp.stderr[-400:],
        }


def check_subsystem_and_envelope(cad_info: dict, check_stator: bool, check_rotor: bool) -> list[str]:
    errs: list[str] = []
    if not cad_info.get("ok"):
        return [str(cad_info.get("error") or "Invalid .FCStd document")]
    ss = cad_info["stator_stages"]
    rs = cad_info["rotor_stages"]
    summ = cad_info["summary"]

    if check_stator:
        for sn, _, _ in STAGES:
            st = ss[sn]
            if not st["z_span_ok"]:
                errs.append(f"Stator_{sn} axial Z bounds out of stage slot")
            if not (STATOR_FIN_RANGE[0] <= st["fin_count"] <= STATOR_FIN_RANGE[1]):
                errs.append(f"Stator_{sn} fin_count={st['fin_count']} outside {list(STATOR_FIN_RANGE)}")
            if st["r_out_mm"] > STATOR_MAX_R_OUT_MM:
                errs.append(f"Stator_{sn} r_out_mm={st['r_out_mm']} exceeds max {STATOR_MAX_R_OUT_MM}")
            if st["q_diss_w"] < STATOR_MIN_Q_W[sn]:
                errs.append(f"Stator_{sn} q_diss_w={st['q_diss_w']} below stage min {STATOR_MIN_Q_W[sn]}")
        if summ["q_diss_total_w"] < STATOR_MIN_Q_TOTAL_W:
            errs.append(f"stator q_diss_total_w={summ['q_diss_total_w']} below min {STATOR_MIN_Q_TOTAL_W}")
        if summ["stator_mass_g"] < STATOR_MIN_MASS_G:
            errs.append(f"stator_mass_g={summ['stator_mass_g']} below structural flutter floor {STATOR_MIN_MASS_G} g")

    if check_rotor:
        for sn, _, _ in STAGES:
            rt = rs[sn]
            if not rt["z_span_ok"]:
                errs.append(f"Rotor_{sn} axial Z bounds out of stage slot")
            if not (ROTOR_SPLINE_RANGE[0] <= rt["spline_count"] <= ROTOR_SPLINE_RANGE[1]):
                errs.append(f"Rotor_{sn} spline_count={rt['spline_count']} outside {list(ROTOR_SPLINE_RANGE)}")
            if rt["r_bore_mm"] < ROTOR_MIN_BORE_MM - 0.05:
                errs.append(f"Rotor_{sn} r_bore_mm={rt['r_bore_mm']} below min {ROTOR_MIN_BORE_MM}")
            if rt["k_torsion_knm"] < ROTOR_MIN_K_KNM[sn]:
                errs.append(f"Rotor_{sn} k_torsion_knm={rt['k_torsion_knm']} below stage min {ROTOR_MIN_K_KNM[sn]}")
        if summ["k_torsion_total_knm"] < ROTOR_MIN_K_TOTAL_KNM:
            errs.append(f"rotor k_torsion_total_knm={summ['k_torsion_total_knm']} below min {ROTOR_MIN_K_TOTAL_KNM}")
        if summ["rotor_mass_g"] < ROTOR_MIN_MASS_G:
            errs.append(f"rotor_mass_g={summ['rotor_mass_g']} below hub burst floor {ROTOR_MIN_MASS_G} g")

    if summ["interference_mm3"] > GLOBAL_MAX_INTERFERENCE_MM3:
        errs.append(f"BRep solid collision interference_mm3={summ['interference_mm3']} > {GLOBAL_MAX_INTERFERENCE_MM3}")
    for sn, gap in summ["airgaps_mm"].items():
        if not (GLOBAL_AIRGAP_RANGE_MM[0] <= gap <= GLOBAL_AIRGAP_RANGE_MM[1]):
            errs.append(f"Stage {sn} radial_airgap_mm={gap} outside {list(GLOBAL_AIRGAP_RANGE_MM)}")
    if not (GLOBAL_TOTAL_MASS_RANGE_G[0] <= summ["total_mass_g"] <= GLOBAL_TOTAL_MASS_RANGE_G[1]):
        errs.append(f"total_mass_g={summ['total_mass_g']} outside {list(GLOBAL_TOTAL_MASS_RANGE_G)}")
    if not (GLOBAL_CG_Z_RANGE_MM[0] <= summ["total_cg_z_mm"] <= GLOBAL_CG_Z_RANGE_MM[1]):
        errs.append(f"total_cg_z_mm={summ['total_cg_z_mm']} outside {list(GLOBAL_CG_Z_RANGE_MM)}")
    return errs


def verify_xlsx_against_cad(xlsx_path: Path, cad_info: dict, check_stator: bool, check_rotor: bool) -> list[str]:
    if not xlsx_path.is_file():
        return ["Missing /workspace/Actuator_Mass_CG.xlsx"]
    try:
        raw_sheets = read_multisheet_xlsx(xlsx_path)
        eval_sheets = evaluate_xlsx_via_libreoffice(xlsx_path)
    except Exception as exc:
        return [f"Corrupted Actuator_Mass_CG.xlsx: {exc}"]

    errs: list[str] = []
    for req_sh in ("Stator_Schedule", "Rotor_Schedule", "Assembly_Summary"):
        if req_sh not in raw_sheets:
            errs.append(f"Missing worksheet {req_sh}")
    if errs:
        return errs

    raw_sum = raw_sheets["Assembly_Summary"]
    for cell_ref in ("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11", "B12"):
        if not (raw_sum.get(cell_ref) or {}).get("formula"):
            errs.append(f"Assembly_Summary!{cell_ref} missing live Excel formula (hardcoded or wiped)")

    def _num(sheet_dict: dict, ref: str) -> float:
        v = (sheet_dict.get(ref) or {}).get("value")
        return float(v) if isinstance(v, (int, float)) else -999999.0

    if check_stator:
        st_sh = eval_sheets.get("Stator_Schedule", {})
        for idx, (sn, _, _) in enumerate(STAGES, start=2):
            st = cad_info["stator_stages"][sn]
            if abs(_num(st_sh, f"B{idx}") - st["mass_g"]) > 0.6:
                errs.append(f"Stator_Schedule!B{idx} mass mismatch vs live CAD ({_num(st_sh, f'B{idx}')} vs {st['mass_g']})")
            if abs(_num(st_sh, f"D{idx}") - st["r_in_mm"]) > 0.08:
                errs.append(f"Stator_Schedule!D{idx} r_in_mm mismatch vs live CAD")
            if abs(_num(st_sh, f"G{idx}") - st["q_diss_w"]) > 1.5:
                errs.append(f"Stator_Schedule!G{idx} q_diss_w mismatch vs live CAD")

    if check_rotor:
        rt_sh = eval_sheets.get("Rotor_Schedule", {})
        for idx, (sn, _, _) in enumerate(STAGES, start=2):
            rt = cad_info["rotor_stages"][sn]
            if abs(_num(rt_sh, f"B{idx}") - rt["mass_g"]) > 0.6:
                errs.append(f"Rotor_Schedule!B{idx} mass mismatch vs live CAD ({_num(rt_sh, f'B{idx}')} vs {rt['mass_g']})")
            if abs(_num(rt_sh, f"E{idx}") - rt["r_tip_mm"]) > 0.08:
                errs.append(f"Rotor_Schedule!E{idx} r_tip_mm mismatch vs live CAD")
            if abs(_num(rt_sh, f"G{idx}") - rt["k_torsion_knm"]) > 1.5:
                errs.append(f"Rotor_Schedule!G{idx} k_torsion_knm mismatch vs live CAD")

    ev_sum = eval_sheets.get("Assembly_Summary", {})
    summ = cad_info["summary"]
    if abs(_num(ev_sum, "B4") - summ["total_mass_g"]) > 1.2:
        errs.append(f"Assembly_Summary!B4 evaluated Total_Mass_g={_num(ev_sum, 'B4')} != live CAD {summ['total_mass_g']}")
    if abs(_num(ev_sum, "B5") - summ["total_cg_z_mm"]) > 0.25:
        errs.append(f"Assembly_Summary!B5 evaluated Assembly_CG_Z_mm={_num(ev_sum, 'B5')} != live CAD {summ['total_cg_z_mm']}")
    if abs(_num(ev_sum, "B10") - summ["min_airgap_mm"]) > 0.08:
        errs.append(f"Assembly_Summary!B10 evaluated Min_Airgap_mm={_num(ev_sum, 'B10')} != live CAD {summ['min_airgap_mm']}")
    return errs


def _make_xlsx_stator_rows(stator_stages: dict) -> list[list]:
    rows: list[list] = [["Stage", "Mass_g", "CG_Z_mm", "Inner_R_mm", "Outer_R_mm", "Fin_Count", "Q_Diss_W"]]
    m_tot = 0.0
    mz_tot = 0.0
    q_tot = 0.0
    for sn, _, _ in STAGES:
        st = stator_stages[sn]
        m_tot += st["mass_g"]
        mz_tot += st["mass_g"] * st["cg_z_mm"]
        q_tot += st["q_diss_w"]
        rows.append([sn, round(st["mass_g"], 3), round(st["cg_z_mm"], 3), round(st["r_in_mm"], 3), round(st["r_out_mm"], 3), int(st["fin_count"]), round(st["q_diss_w"], 2)])
    cg_avg = round(mz_tot / max(1e-9, m_tot), 3)
    rows.append(["TOTAL", ("=SUM(B2:B5)", round(m_tot, 3)), ("=(B2*C2+B3*C3+B4*C4+B5*C5)/B6", cg_avg), "", "", "", ("=SUM(G2:G5)", round(q_tot, 2))])
    return rows


def _make_xlsx_rotor_rows(rotor_stages: dict) -> list[list]:
    rows: list[list] = [["Stage", "Mass_g", "CG_Z_mm", "Bore_R_mm", "Tip_R_mm", "Spline_Count", "K_Torsion_kNm"]]
    m_tot = 0.0
    mz_tot = 0.0
    k_tot = 0.0
    for sn, _, _ in STAGES:
        rt = rotor_stages[sn]
        m_tot += rt["mass_g"]
        mz_tot += rt["mass_g"] * rt["cg_z_mm"]
        k_tot += rt["k_torsion_knm"]
        rows.append([sn, round(rt["mass_g"], 3), round(rt["cg_z_mm"], 3), round(rt["r_bore_mm"], 3), round(rt["r_tip_mm"], 3), int(rt["spline_count"]), round(rt["k_torsion_knm"], 2)])
    cg_avg = round(mz_tot / max(1e-9, m_tot), 3)
    rows.append(["TOTAL", ("=SUM(B2:B5)", round(m_tot, 3)), ("=(B2*C2+B3*C3+B4*C4+B5*C5)/B6", cg_avg), "", "", "", ("=SUM(G2:G5)", round(k_tot, 2))])
    return rows


def _make_xlsx_summary_rows(summ: dict) -> list[list]:
    gaps = summ["airgaps_mm"]
    return [
        ["Metric", "Value", "Spec_Min", "Spec_Max"],
        ["Stator_Mass_g", ("=Stator_Schedule!B6", summ["stator_mass_g"]), 280.0, 520.0],
        ["Rotor_Mass_g", ("=Rotor_Schedule!B6", summ["rotor_mass_g"]), 240.0, 520.0],
        ["Total_Mass_g", ("=B2+B3", summ["total_mass_g"]), GLOBAL_TOTAL_MASS_RANGE_G[0], GLOBAL_TOTAL_MASS_RANGE_G[1]],
        ["Assembly_CG_Z_mm", ("=(Stator_Schedule!B6*Stator_Schedule!C6+Rotor_Schedule!B6*Rotor_Schedule!C6)/B4", summ["total_cg_z_mm"]), GLOBAL_CG_Z_RANGE_MM[0], GLOBAL_CG_Z_RANGE_MM[1]],
        ["Airgap_S1_mm", ("=Stator_Schedule!D2-Rotor_Schedule!E2", gaps["S1"]), GLOBAL_AIRGAP_RANGE_MM[0], GLOBAL_AIRGAP_RANGE_MM[1]],
        ["Airgap_S2_mm", ("=Stator_Schedule!D3-Rotor_Schedule!E3", gaps["S2"]), GLOBAL_AIRGAP_RANGE_MM[0], GLOBAL_AIRGAP_RANGE_MM[1]],
        ["Airgap_S3_mm", ("=Stator_Schedule!D4-Rotor_Schedule!E4", gaps["S3"]), GLOBAL_AIRGAP_RANGE_MM[0], GLOBAL_AIRGAP_RANGE_MM[1]],
        ["Airgap_S4_mm", ("=Stator_Schedule!D5-Rotor_Schedule!E5", gaps["S4"]), GLOBAL_AIRGAP_RANGE_MM[0], GLOBAL_AIRGAP_RANGE_MM[1]],
        ["Min_Airgap_mm", ("=MIN(B6:B9)", summ["min_airgap_mm"]), GLOBAL_AIRGAP_RANGE_MM[0], GLOBAL_AIRGAP_RANGE_MM[1]],
        ["Stator_Q_Total_W", ("=Stator_Schedule!G6", summ["q_diss_total_w"]), STATOR_MIN_Q_TOTAL_W, 999.0],
        ["Rotor_K_Total_kNm", ("=Rotor_Schedule!G6", summ["k_torsion_total_knm"]), ROTOR_MIN_K_TOTAL_KNM, 999.0],
    ]


def verify_clean_workspace(workspace: Path) -> list[str]:
    allowed_root = {"servo_actuator.FCStd", "Actuator_Mass_CG.xlsx", "release", "renders"}
    allowed_renders = {"rig_cutaway_iso.png", "rig_cutaway_axial.png"}
    errs: list[str] = []
    if workspace.is_dir():
        extra = sorted(x.name for x in workspace.iterdir() if x.name not in allowed_root and not x.name.startswith("servo_actuator.FCStd"))
        if extra:
            errs.append(f"Unexpected non-release files/directories in /workspace: {extra} (use /tmp or $HOME for working scripts)")
    rel_d = workspace / "release"
    if rel_d.is_dir():
        extra_r = sorted(x.name for x in rel_d.iterdir() if x.name != "servo_actuator_assy.step")
        if extra_r:
            errs.append(f"Unexpected files in /workspace/release: {extra_r}")
    ren_d = workspace / "renders"
    if ren_d.is_dir():
        extra_ren = sorted(x.name for x in ren_d.iterdir() if x.name not in allowed_renders)
        if extra_ren:
            errs.append(f"Unexpected non-release files in /workspace/renders: {extra_ren}")
    return errs


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    pport = META["portal_port"]
    common_lines = [
        "### Actuator Assembly Envelope, Schedule & Release Hygiene",
        f"- **CAD Assembly**: {b}/workspace/servo_actuator.FCStd{b} (8 coaxial {b}Part::Feature{b} single-solid objects along {b}Z = 0..88 mm{b}, Ti-6Al-4V density {b}0.00443 g/mm^3{b}: {b}Stator_S1..Stator_S4{b} and {b}Rotor_S1..Rotor_S4{b}; stage slots {b}S1=[0,24], S2=[24,46], S3=[46,67], S4=[67,88] mm{b}).",
        "- **Global Physical Envelope**:",
        f"  - OpenCASCADE BRep solid interference volume {b}<= 0.01 mm^3{b}.",
        f"  - Per-Stage Radial Air-Gap {b}airgap_mm = Stator_r_in_mm - Rotor_r_tip_mm{b} MUST lie within **{b}[1.18, 1.30] mm{b}** on all 4 stages {b}S1..S4{b} (note: initial {b}v0{b} baseline has a wide {b}1.45 mm{b} gap that must be tightened into {b}[1.18, 1.30] mm{b}).",
        f"  - Subsystem Structural Mass Floors: {b}stator_mass_g >= 365.0 g{b}, {b}rotor_mass_g >= 365.0 g{b}.",
        f"  - Total Actuator Dry Mass ({b}Stator_S1..S4 + Rotor_S1..S4{b}): **{b}[740.0, 820.0] g{b}**.",
        f"  - Combined Assembly Axial CG ({b}Assembly_CG_Z_mm{b}): **{b}[40.80, 42.95] mm{b}**.",
        f"- **Workbook & STEP Deliverables**:",
        f"  - {b}/workspace/Actuator_Mass_CG.xlsx{b} ({b}Stator_Schedule{b}, {b}Rotor_Schedule{b}, and {b}Assembly_Summary{b} with live Excel formulas {b}B2:B12{b}).",
        f"  - {b}/workspace/release/servo_actuator_assy.step{b} (8-solid full-assembly STEP matching {b}servo_actuator.FCStd{b}).",
        f"- **Release Directory Hygiene**: {b}/workspace{b} is the customer release root and may contain ONLY {b}servo_actuator.FCStd{b}, {b}Actuator_Mass_CG.xlsx{b}, {b}release/servo_actuator_assy.step{b}, and {b}renders/{b}. Keep all Python build scripts and logs in {b}$HOME{b} or {b}$TMPDIR{b}.",
        f"- **SSO PLM Console ({b}DISPLAY=:99{b}, {b}http://127.0.0.1:{pport}{b}) & Rig API**:",
        f"  - Use {b}desktop.screenshot{b} and {b}desktop.click{b} on the open Chromium SSO session ({b}DISPLAY=:99{b}) to select subsystem context ({b}STATOR_THERMAL{b} / {b}ROTOR_DYNAMICS{b}) and {b}SI_MM_GRAM{b} basis, or export {b}/home/gui/Downloads/stage_boundary_spec.csv{b}.",
        f"  - {b}POST http://127.0.0.1:{pport}/api/bench/actuation_rig{b}: ordered stage qualification ({b}mode='stage_isolation'{b} in order {b}S1 -> S2 -> S3 -> S4{b}, saving {b}servo_actuator.FCStd{b} at each stage, followed by {b}mode='full_assembly'{b} producing {b}/workspace/renders/rig_cutaway_iso.png{b} and {b}/workspace/renders/rig_cutaway_axial.png{b}).",
        f"  - {b}GET http://127.0.0.1:{pport}/api/plm/status (pass header X-Role-Token from /session/ticket/role_token.txt){b} and {b}POST http://127.0.0.1:{pport}/api/plm/submit{b}.",
    ]
    common_txt = "\n".join(common_lines)

    stator_txt = "\n".join([
        f"# Engineering Work Order — FC-01 ({b}stator_lead{b})",
        "",
        f"Redesign and qualify the 4-stage outer cooling-fin stator subsystem ({b}Stator_S1..Stator_S4{b}) in {b}/workspace/servo_actuator.FCStd{b}.",
        "",
        "### Stator Technical Requirements",
        f"1. Inspect {b}STATOR_THERMAL{b} + {b}SI_MM_GRAM{b} on the Chromium SSO PLM Console ({b}DISPLAY=:99{b}) for per-stage swirl factors and thermal minima:",
        f"   - {b}r_out_mm <= 44.50 mm{b}, {b}fin_count{b} in **{b}[16, 24]{b}**, {b}stator_mass_g >= 365.0 g{b}.",
        f"   - Stage dissipation minima: {b}S1 >= 140.0 W, S2 >= 125.0 W, S3 >= 115.0 W, S4 >= 110.0 W{b}, and 4-stage total **{b}q_diss_total_w >= 510.0 W{b}**.",
        f"   - Size {b}Stator_r_in_mm{b} and upper-stage wall/pockets so radial air-gap is in {b}[1.18, 1.30] mm{b}, total dry mass is in {b}[740.0, 820.0] g{b}, and {b}Assembly_CG_Z_mm{b} is in {b}[40.80, 42.95] mm{b}.",
        f"2. Iteratively update and save {b}Stator_S1..Stator_S4{b} stage-by-stage in {b}/workspace/servo_actuator.FCStd{b}, qualifying {b}S1 -> S2 -> S3 -> S4{b} ({b}mode='stage_isolation'{b}) and then {b}mode='full_assembly'{b}.",
        f"3. Update {b}Stator_Schedule{b} in {b}/workspace/Actuator_Mass_CG.xlsx{b}, export the 8-solid {b}/workspace/release/servo_actuator_assy.step{b}, and submit signoff to {b}POST http://127.0.0.1:{pport}/api/plm/submit{b}:",
        f"   {b}{{\"subsystem\": \"stator\", \"mass_g\": <float>, \"cg_z_mm\": <float>, \"performance_total\": <float>, \"min_airgap_mm\": <float>, \"step_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}STATOR_THERMAL{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])

    rotor_txt = "\n".join([
        f"# Engineering Work Order — FC-01 ({b}rotor_lead{b})",
        "",
        f"Redesign and qualify the 4-stage inner torque-spline rotor subsystem ({b}Rotor_S1..Rotor_S4{b}) in {b}/workspace/servo_actuator.FCStd{b}.",
        "",
        "### Rotor Technical Requirements",
        f"1. Inspect {b}ROTOR_DYNAMICS{b} + {b}SI_MM_GRAM{b} on the Chromium SSO PLM Console ({b}DISPLAY=:99{b}) for per-stage harmonic factors and stiffness minima:",
        f"   - {b}r_bore_mm >= 18.00 mm{b}, {b}spline_count{b} in **{b}[12, 20]{b}**, {b}rotor_mass_g >= 365.0 g{b}.",
        f"   - Stage stiffness minima: {b}S1 >= 94.0, S2 >= 96.0, S3 >= 70.0, S4 >= 66.0 kNm/rad{b}, and 4-stage total **{b}k_torsion_total_knm >= 340.0 kNm/rad{b}**.",
        f"   - Size {b}Rotor_r_tip_mm{b} and bore/pockets so radial air-gap is in {b}[1.18, 1.30] mm{b}, total dry mass is in {b}[740.0, 820.0] g{b}, and {b}Assembly_CG_Z_mm{b} is in {b}[40.80, 42.95] mm{b}.",
        f"2. Iteratively update and save {b}Rotor_S1..Rotor_S4{b} stage-by-stage in {b}/workspace/servo_actuator.FCStd{b}, qualifying {b}S1 -> S2 -> S3 -> S4{b} ({b}mode='stage_isolation'{b}) and then {b}mode='full_assembly'{b}.",
        f"3. Update {b}Rotor_Schedule{b} in {b}/workspace/Actuator_Mass_CG.xlsx{b}, export the 8-solid {b}/workspace/release/servo_actuator_assy.step{b}, and submit signoff to {b}POST http://127.0.0.1:{pport}/api/plm/submit{b}:",
        f"   {b}{{\"subsystem\": \"rotor\", \"mass_g\": <float>, \"cg_z_mm\": <float>, \"performance_total\": <float>, \"min_airgap_mm\": <float>, \"step_sha256\": \"<sha256>\"}}{b}.",
        "",
        f"- **Environmental Rig Conditioning**: Keep **{b}ROTOR_DYNAMICS{b}** active on {b}DISPLAY=:99{b} throughout your exports and all multi-minute qualification runs (pass {b}curl --max-time 350{b}).",
        "",
        common_txt,
        "",
    ])
    return {"stator_lead": stator_txt, "rotor_lead": rotor_txt}


def build_pristine(workspace: Path, tickets_root: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "release").mkdir(parents=True, exist_ok=True)
    (workspace / "renders").mkdir(parents=True, exist_ok=True)
    tickets_root.mkdir(parents=True, exist_ok=True)

    fcstd_p = workspace / "servo_actuator.FCStd"
    step_p = workspace / "release" / "servo_actuator_assy.step"
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        body_p = td / "mk_v0.py"
        run_p = td / "run_v0.py"
        body_p.write_text(
            f"""
import FreeCAD, Part

STAGES = [("S1", 0.0, 24.0), ("S2", 24.0, 22.0), ("S3", 46.0, 21.0), ("S4", 67.0, 21.0)]
doc = FreeCAD.newDocument("ServoActuator")
shapes = []
for idx, (sn, z0, h) in enumerate(STAGES):
    r_base = 36.9 if idx < 2 else 36.1
    s_sol = Part.makeCylinder(r_base, h, FreeCAD.Vector(0, 0, z0)).cut(
        Part.makeCylinder(32.10, h + 2.0, FreeCAD.Vector(0, 0, z0 - 1.0))
    ).Solids[0]
    s_obj = doc.addObject("Part::Feature", f"Stator_{{sn}}")
    s_obj.Shape = s_sol
    shapes.append(s_sol)

    r_bore = 24.5 if idx < 2 else 25.5
    r_sol = Part.makeCylinder(30.65, h, FreeCAD.Vector(0, 0, z0)).cut(
        Part.makeCylinder(r_bore, h + 2.0, FreeCAD.Vector(0, 0, z0 - 1.0))
    ).Solids[0]
    r_obj = doc.addObject("Part::Feature", f"Rotor_{{sn}}")
    r_obj.Shape = r_sol
    shapes.append(r_sol)

doc.recompute()
doc.saveAs({str(fcstd_p)!r})
Part.makeCompound(shapes).exportStep({str(step_p)!r})
""",
            encoding="utf-8",
        )
        run_p.write_text(f"ns = {{}}; exec(open({str(body_p)!r}, encoding='utf-8').read(), ns, ns)\n", encoding="utf-8")
        subprocess.run(["freecadcmd", str(run_p)], check=True, capture_output=True, text=True, timeout=60)

    cad_v0 = run_freecad_inspect(fcstd_p)
    assert cad_v0.get("ok"), f"Failed pristine CAD inspect: {cad_v0}"
    xlsx_p = workspace / "Actuator_Mass_CG.xlsx"
    write_multisheet_xlsx(
        xlsx_p,
        [
            ("Stator_Schedule", _make_xlsx_stator_rows(cad_v0["stator_stages"])),
            ("Rotor_Schedule", _make_xlsx_rotor_rows(cad_v0["rotor_stages"])),
            ("Assembly_Summary", _make_xlsx_summary_rows(cad_v0["summary"])),
        ],
    )

    import secrets as _sec
    role_tokens = {}
    for role, md in build_tickets_by_role().items():
        rdir = tickets_root / role
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "task.md").write_text(md, encoding="utf-8")
        tok = "rtok_" + _sec.token_hex(12)
        (rdir / "role_token.txt").write_text(tok + "\n", encoding="utf-8")
        role_tokens[role] = tok
    write_json(tickets_root / "role_tokens.json", role_tokens)


def render_plm_plate_png(sub_ctx: str, unit: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1220, 520), (8, 13, 27))
    dr = ImageDraw.Draw(img)
    dr.rectangle([(10, 10), (1210, 510)], outline=(56, 189, 248), width=2)
    dr.text((24, 24), f"AERO-ACTUATOR SSO PLM WORKBENCH  |  Context: {sub_ctx}  |  Basis: {unit}", fill=(56, 189, 248))
    dr.text((24, 54), "Global Envelope: Air-Gap [1.18, 1.30] mm | Mass [740.0, 820.0] g (Stator>=365g, Rotor>=365g) | CG_Z [40.80, 42.95] mm", fill=(226, 232, 240))
    dr.line([(24, 82), (1196, 82)], fill=(51, 65, 85), width=1)

    scale = 1.0 if unit == "SI_MM_GRAM" else 13.75
    dr.text((26, 104), f"STAGE     Z_SLOT_MM        FACTOR       MIN_TARGET ({unit})            GEOMETRY_LIMIT", fill=(251, 191, 36))
    y = 138
    if sub_ctx == "STATOR_THERMAL":
        swirls = {"S1": 1.06, "S2": 1.02, "S3": 0.98, "S4": 0.94}
        for sn, z0, h in STAGES:
            v = round(STATOR_MIN_Q_W[sn] * scale, 2)
            dr.text((26, y), f"{sn:<9} [{z0:>4.1f}, {z0+h:>4.1f}]     swirl={swirls[sn]:.2f}   Q_min >= {v:>7.2f}      fins in [16, 24], r_out <= 44.50 mm", fill=(241, 245, 249))
            y += 32
        dr.text((26, y + 8), f"TOTAL     [ 0.0, 88.0]     4-stage      Q_sum >= {round(STATOR_MIN_Q_TOTAL_W*scale,2):>7.2f}      stator_mass_g >= 365.0 g", fill=(167, 243, 208))
    else:
        harms = {"S1": 1.05, "S2": 1.00, "S3": 0.96, "S4": 0.92}
        for sn, z0, h in STAGES:
            v = round(ROTOR_MIN_K_KNM[sn] * scale, 2)
            dr.text((26, y), f"{sn:<9} [{z0:>4.1f}, {z0+h:>4.1f}]     harm={harms[sn]:.2f}    K_min >= {v:>7.2f}      splines in [12, 20], r_bore >= 18.00 mm", fill=(241, 245, 249))
            y += 32
        dr.text((26, y + 8), f"TOTAL     [ 0.0, 88.0]     4-stage      K_sum >= {round(ROTOR_MIN_K_TOTAL_KNM*scale,2):>7.2f}      rotor_mass_g >= 365.0 g", fill=(167, 243, 208))

    buf = __import__("io").BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>PLM Coaxial Actuator Console — FC-01</title>
  <style>
    body { margin: 0; background: #020617; color: #e2e8f0; font-family: monospace; padding: 12px; }
    .bar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
    button { background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 7px 12px; cursor: pointer; font-family: monospace; font-weight: bold; }
    button:hover { background: #0284c7; }
    #msg { font-size: 12px; color: #38bdf8; }
    canvas { border: 1px solid #334155; display: block; }
  </style>
</head>
<body>
  <div class="bar">
    <strong>SUBSYSTEM:</strong>
    <button onclick="setCtx('STATOR_THERMAL', null)">STATOR_THERMAL</button>
    <button onclick="setCtx('ROTOR_DYNAMICS', null)">ROTOR_DYNAMICS</button>
    <strong>BASIS:</strong>
    <button onclick="setCtx(null, 'SI_MM_GRAM')">SI_MM_GRAM</button>
    <button onclick="setCtx(null, 'RAW_COUNTS')">RAW_COUNTS</button>
    <button onclick="exportCsv()">Export Stage CSV (/home/gui/Downloads/stage_boundary_spec.csv)</button>
    <span id="msg">SSO PLM Active</span>
  </div>
  <canvas id="spec-canvas" width="1220" height="520"></canvas>
  <!-- Public protocol tokens:
       /workspace/servo_actuator.FCStd /workspace/Actuator_Mass_CG.xlsx /workspace/release/servo_actuator_assy.step
       /workspace/renders/rig_cutaway_iso.png /workspace/renders/rig_cutaway_axial.png
       /api/bench/actuation_rig /api/plm/submit /api/plm/status
       Stator_Schedule Rotor_Schedule Assembly_Summary stage_isolation full_assembly
       1.18 1.30 820.0 365.0 40.80 42.95 -->
  <script>
    function drawPlm() {
      const cv = document.getElementById('spec-canvas');
      const ctx = cv.getContext('2d');
      const im = new Image();
      im.onload = () => ctx.drawImage(im, 0, 0);
      im.src = '/ui/plm_plate.png?t=' + Date.now();
    }
    async function setCtx(sub, unit) {
      const b = {};
      if (sub) b.subsystem_context = sub;
      if (unit) b.unit_basis = unit;
      const r = await fetch('/api/ui/session', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
      const d = await r.json();
      document.getElementById('msg').textContent = (d.subsystem_context || '') + ' / ' + (d.unit_basis || '');
      drawPlm();
    }
    async function exportCsv() {
      const r = await fetch('/api/ui/export_csv', {method: 'POST'});
      const d = await r.json();
      document.getElementById('msg').textContent = 'Exported ' + (d.path || '') + ' (' + (d.subsystem_context || '') + ')';
      drawPlm();
    }
    drawPlm();
    setInterval(drawPlm, 3500);
  </script>
</body>
</html>
"""


def run_simulator(port: int, workspace: Path, state_dir: Path, boot_file: Path, fast_selfval: bool = False) -> None:
    from http.cookies import SimpleCookie
    import secrets
    import urllib.request

    state_dir.mkdir(parents=True, exist_ok=True)
    sso_boot_secret = secrets.token_hex(16)
    sso_cookie_val = secrets.token_hex(18)
    admin_key = secrets.token_hex(16)
    (state_dir / "sso_admin_key").write_text(admin_key, encoding="utf-8")

    state_lock = threading.Lock()
    sub_locks = {"stator": threading.Lock(), "rotor": threading.Lock()}
    state_path = state_dir / "portal_state.json"

    pstate: dict = {
        "task_id": TASK_ID,
        "ui_session": {"subsystem_context": "STATOR_THERMAL", "unit_basis": "SI_MM_GRAM"},
        "session_switches": 0,
        "download_exports": 0,
        "download_overwrites": 0,
        "bench_calls": 0,
        "bench_history": [],
        "stage_purity": {"stator": {}, "rotor": {}},
        "qualified_stages": {"stator": {}, "rotor": {}},
        "last_full_assembly": {},
        "submissions": {},
    }

    def persist() -> None:
        write_json(state_path, pstate)

    persist()
    stage_order = ("S1", "S2", "S3", "S4")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_args) -> None: return

        def _has_sso(self) -> bool:
            if self.headers.get("X-Internal-Admin") == admin_key:
                return True
            c = SimpleCookie()
            try:
                c.load(self.headers.get("Cookie") or "")
                m = c.get("fc01_sso")
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
                    self.send_header("Set-Cookie", f"fc01_sso={sso_cookie_val}; Path=/; HttpOnly")
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
            if p == "/ui/plm_plate.png":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; inspect Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    png = render_plm_plate_png(pstate["ui_session"]["subsystem_context"], pstate["ui_session"]["unit_basis"])
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            if p == "/api/plm/status":
                rt_p = state_dir / "role_tokens.json"
                rt_map = json.loads(rt_p.read_text(encoding="utf-8")) if rt_p.is_file() else {}
                tok_hdr = (self.headers.get("X-Role-Token") or "").strip()
                sub_q = "stator" if tok_hdr and tok_hdr == rt_map.get("stator_lead") else ("rotor" if tok_hdr and tok_hdr == rt_map.get("rotor_lead") else "")
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

            if p == "/api/ui/session":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; click buttons in Chromium on DISPLAY=:99"})
                    return
                with state_lock:
                    changed = False
                    if body.get("subsystem_context") in ("STATOR_THERMAL", "ROTOR_DYNAMICS"):
                        if pstate["ui_session"]["subsystem_context"] != body["subsystem_context"]:
                            changed = True
                        pstate["ui_session"]["subsystem_context"] = body["subsystem_context"]
                    if body.get("unit_basis") in ("SI_MM_GRAM", "RAW_COUNTS"):
                        if pstate["ui_session"]["unit_basis"] != body["unit_basis"]:
                            changed = True
                        pstate["ui_session"]["unit_basis"] = body["unit_basis"]
                    if changed:
                        pstate["session_switches"] += 1
                    persist()
                    self._json(200, dict(pstate["ui_session"]))
                return

            if p == "/api/ui/export_csv":
                if not self._has_sso():
                    self._json(401, {"error": "SSO browser cookie required; click Export in Chromium on DISPLAY=:99"})
                    return
                dl_path = Path("/home/gui/Downloads/stage_boundary_spec.csv")
                dl_path.parent.mkdir(parents=True, exist_ok=True)
                with state_lock:
                    sub = pstate["ui_session"]["subsystem_context"]
                    unit = pstate["ui_session"]["unit_basis"]
                    scale = 1.0 if unit == "SI_MM_GRAM" else 13.75
                    lines = ["stage,z_min_mm,z_max_mm,min_target"]
                    for sn, z0, h in STAGES:
                        base_t = STATOR_MIN_Q_W[sn] if sub == "STATOR_THERMAL" else ROTOR_MIN_K_KNM[sn]
                        lines.append(f"{sn},{z0},{z0+h},{round(base_t * scale, 2)}")
                    if dl_path.exists():
                        pstate["download_overwrites"] += 1
                    dl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    try:
                        os.chmod(dl_path, 0o666)
                    except OSError:
                        pass
                    pstate["download_exports"] += 1
                    persist()
                    self._json(200, {"ok": True, "path": str(dl_path), "subsystem_context": sub, "unit_basis": unit})
                return

            if p == "/api/bench/actuation_rig":
                clean_errs = verify_clean_workspace(workspace)
                if clean_errs:
                    self._json(422, {"status": "WORKSPACE_HYGIENE_VIOLATION", "errors": clean_errs})
                    return
                sub = str(body.get("subsystem") or "").strip().lower()
                mode = str(body.get("mode") or "").strip().lower()
                stage = str(body.get("stage") or "").strip().upper()
                if sub not in ("stator", "rotor") or mode not in ("stage_isolation", "full_assembly"):
                    self._json(400, {"error": "Require subsystem in ['stator','rotor'] and mode in ['stage_isolation','full_assembly']"})
                    return
                if mode == "stage_isolation":
                    if stage not in stage_order:
                        self._json(400, {"error": "stage_isolation requires stage in ['S1','S2','S3','S4']"})
                        return
                    s_idx = stage_order.index(stage)
                    with state_lock:
                        prev_miss = [stage_order[i] for i in range(s_idx) if not pstate["qualified_stages"][sub].get(stage_order[i])]
                    if prev_miss:
                        self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Qualify upstream stages first: {prev_miss}"})
                        return
                else:
                    with state_lock:
                        prev_miss = [sn for sn in stage_order if not pstate["qualified_stages"][sub].get(sn)]
                    if prev_miss:
                        self._json(422, {"status": "STAGE_ORDER_VIOLATION", "error": f"Qualify all 4 stages S1..S4 before full_assembly: {prev_miss}"})
                        return

                fcstd_p = workspace / "servo_actuator.FCStd"
                iso_png = workspace / "renders" / "rig_cutaway_iso.png"
                ax_png = workspace / "renders" / "rig_cutaway_axial.png"
                exp_reg = "STATOR_THERMAL" if sub == "stator" else "ROTOR_DYNAMICS"
                def _cur_reg() -> str:
                    with state_lock:
                        return str(pstate["ui_session"]["subsystem_context"])
                with sub_locks[sub], BackgroundRegimeSampler(_cur_reg, exp_reg, interval=(0.05 if fast_selfval else 2.0)) as _reg_sampler:
                    t0 = time.monotonic()
                    fc_sha_before = sha256_file(fcstd_p)
                    with tempfile.TemporaryDirectory() as tmp:
                        stl_p = Path(tmp) / "live_assy.stl"
                        cad_info = run_freecad_inspect(fcstd_p, stl_out=stl_p)
                        if not cad_info.get("ok"):
                            self._json(422, {"status": "CAD_INSPECT_ERROR", "error": cad_info.get("error")})
                            return
                        render_info = run_cycles_cutaway_renders(stl_p, iso_png, ax_png, fast_selfval=fast_selfval)
                    try:
                        for rp in (iso_png, ax_png):
                            if rp.is_file():
                                os.chmod(rp, 0o666)
                    except OSError:
                        pass
                    min_rig_s = 0.2 if fast_selfval else float(os.environ.get("PARAGUI_FC01_RIG_S", "220.0"))
                    while time.monotonic() - t0 < min_rig_s:
                        time.sleep(min(0.5, min_rig_s - (time.monotonic() - t0)))
                    elapsed = round(time.monotonic() - t0, 2)

                with state_lock:
                    pstate["bench_calls"] += 1
                    stage_ok = False
                    env_errs: list[str] = []
                    if mode == "stage_isolation":
                        if sub == "stator":
                            st = cad_info["stator_stages"][stage]
                            stage_ok = (
                                st["z_span_ok"]
                                and STATOR_FIN_RANGE[0] <= st["fin_count"] <= STATOR_FIN_RANGE[1]
                                and st["r_out_mm"] <= STATOR_MAX_R_OUT_MM
                                and st["q_diss_w"] >= STATOR_MIN_Q_W[stage]
                            )
                            if stage_ok:
                                pstate["qualified_stages"]["stator"][stage] = st["fingerprint"]
                                pstate.setdefault("stage_purity", {}).setdefault("stator", {})[stage] = _reg_sampler.purity
                        else:
                            rt = cad_info["rotor_stages"][stage]
                            stage_ok = (
                                rt["z_span_ok"]
                                and ROTOR_SPLINE_RANGE[0] <= rt["spline_count"] <= ROTOR_SPLINE_RANGE[1]
                                and rt["r_bore_mm"] >= ROTOR_MIN_BORE_MM - 0.05
                                and rt["k_torsion_knm"] >= ROTOR_MIN_K_KNM[stage]
                            )
                            if stage_ok:
                                pstate["qualified_stages"]["rotor"][stage] = rt["fingerprint"]
                                pstate.setdefault("stage_purity", {}).setdefault("rotor", {})[stage] = _reg_sampler.purity
                    else:
                        env_errs = check_subsystem_and_envelope(cad_info, check_stator=(sub == "stator"), check_rotor=(sub == "rotor"))
                        stage_ok = (len(env_errs) == 0 and render_info.get("ok", False))
                        if stage_ok:
                            pstate.setdefault("stage_purity", {}).setdefault(sub, {})["FULL_ASSEMBLY"] = _reg_sampler.purity
                            pstate["last_full_assembly"] = {
                                "fcstd_sha256": sha256_file(fcstd_p),
                                "summary": cad_info["summary"],
                                "timestamp": time.time(),
                            }
                    pstate["bench_history"].append({
                        "timestamp": time.time(),
                        "subsystem": sub,
                        "mode": mode,
                        "stage": stage,
                        "fcstd_sha256": fc_sha_before,
                        "passed": stage_ok,
                        "elapsed_s": elapsed,
                    })
                    persist()

                self._json(200, {
                    "ok": True,
                    "subsystem": sub,
                    "mode": mode,
                    "stage": stage,
                    "qualified": stage_ok,
                    "envelope_discrepancies": env_errs,
                    "subsystem_stages": cad_info["stator_stages"] if sub == "stator" else cad_info["rotor_stages"],
                    "assembly_summary": cad_info["summary"],
                    "cycles_render": render_info,
                    "rig_elapsed_s": elapsed,
                })
                return

            if p == "/api/plm/submit":
                sub = str(body.get("subsystem") or "").strip().lower()
                if sub not in ("stator", "rotor"):
                    self._json(400, {"error": "subsystem must be 'stator' or 'rotor'"})
                    return

                fcstd_p = workspace / "servo_actuator.FCStd"
                xlsx_p = workspace / "Actuator_Mass_CG.xlsx"
                step_p = workspace / "release" / "servo_actuator_assy.step"
                cad_info = run_freecad_inspect(fcstd_p, step_path=step_p)
                if not cad_info.get("ok"):
                    self._json(422, {"status": "REJECTED_CAD_INVALID", "errors": [cad_info.get("error")]})
                    return

                errs = check_subsystem_and_envelope(cad_info, check_stator=(sub == "stator"), check_rotor=(sub == "rotor"))
                errs.extend(verify_xlsx_against_cad(xlsx_p, cad_info, check_stator=(sub == "stator"), check_rotor=(sub == "rotor")))
                errs.extend(verify_clean_workspace(workspace))
                if not cad_info["step_check"].get("ok"):
                    errs.append(f"STEP export /workspace/release/servo_actuator_assy.step invalid or out of sync with .FCStd: {cad_info['step_check']}")

                live_sha = sha256_file(fcstd_p)
                live_step_sha = sha256_file(step_p)
                with state_lock:
                    q_map = pstate["qualified_stages"][sub]
                    stages_dict = cad_info["stator_stages"] if sub == "stator" else cad_info["rotor_stages"]
                    unqual = [sn for sn, _, _ in STAGES if q_map.get(sn) != stages_dict[sn]["fingerprint"]]
                    if unqual:
                        errs.append(f"Stages missing stage_isolation rig qualification for current solid geometry: {unqual}")
                    if pstate["last_full_assembly"].get("fcstd_sha256") != live_sha:
                        errs.append("Current /workspace/servo_actuator.FCStd has not passed mode='full_assembly' rig qualification since last edit")

                summ = cad_info["summary"]
                exp_mass = summ["stator_mass_g"] if sub == "stator" else summ["rotor_mass_g"]
                exp_cg = summ["stator_cg_z_mm"] if sub == "stator" else summ["rotor_cg_z_mm"]
                exp_perf = summ["q_diss_total_w"] if sub == "stator" else summ["k_torsion_total_knm"]
                try:
                    if abs(float(body.get("mass_g", -999)) - exp_mass) > 0.8:
                        errs.append(f"Submitted mass_g={body.get('mass_g')} != live {sub} mass {exp_mass}")
                    if abs(float(body.get("cg_z_mm", -999)) - exp_cg) > 0.35:
                        errs.append(f"Submitted cg_z_mm={body.get('cg_z_mm')} != live {sub} CG_Z {exp_cg}")
                    if abs(float(body.get("performance_total", -999)) - exp_perf) > 2.0:
                        errs.append(f"Submitted performance_total={body.get('performance_total')} != live {exp_perf}")
                    if abs(float(body.get("min_airgap_mm", -999)) - summ["min_airgap_mm"]) > 0.08:
                        errs.append(f"Submitted min_airgap_mm={body.get('min_airgap_mm')} != live {summ['min_airgap_mm']}")
                    if str(body.get("step_sha256") or "") != live_step_sha:
                        errs.append("Submitted step_sha256 does not match /workspace/release/servo_actuator_assy.step")
                except (TypeError, ValueError):
                    errs.append("Numeric payload fields missing or non-numeric")

                if errs:
                    self._json(422, {"status": "REJECTED_SPEC_VIOLATION", "subsystem": sub, "errors": errs, "live_summary": summ})
                    return

                stages_dict = cad_info["stator_stages"] if sub == "stator" else cad_info["rotor_stages"]
                rec = {
                    "status": "APPROVED",
                    "subsystem": sub,
                    "mass_g": exp_mass,
                    "cg_z_mm": exp_cg,
                    "performance_total": exp_perf,
                    "min_airgap_mm": summ["min_airgap_mm"],
                    "step_sha256": live_step_sha,
                    "fcstd_sha256": live_sha,
                    "solid_fingerprints": {sn: stages_dict[sn]["fingerprint"] for sn, _, _ in STAGES},
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
    fcstd_p = workspace / "servo_actuator.FCStd"
    xlsx_p = workspace / "Actuator_Mass_CG.xlsx"
    step_p = workspace / "release" / "servo_actuator_assy.step"
    iso_png = workspace / "renders" / "rig_cutaway_iso.png"
    ax_png = workspace / "renders" / "rig_cutaway_axial.png"

    cad_info = run_freecad_inspect(fcstd_p, step_path=step_p)
    subs = portal_state.get("submissions") or {}
    sub_stator = subs.get("stator") or {}
    sub_rotor = subs.get("rotor") or {}
    stator_signed = sub_stator.get("status") == "APPROVED"
    rotor_signed = sub_rotor.get("status") == "APPROVED"
    closed_cnt = int(stator_signed) + int(rotor_signed)
    pur_s_errs = verify_stage_regime_purity(portal_state, "stator", ("S2", "S3", "S4", "FULL_ASSEMBLY"))
    pur_r_errs = verify_stage_regime_purity(portal_state, "rotor", ("S2", "S3", "S4", "FULL_ASSEMBLY"))
    clean_errs = verify_clean_workspace(workspace) + pur_s_errs + pur_r_errs

    if cad_info.get("ok"):
        stator_only_errs = [e for e in check_subsystem_and_envelope(cad_info, check_stator=True, check_rotor=False) if e.startswith("Stator_") or e.startswith("stator")]
        rotor_only_errs = [e for e in check_subsystem_and_envelope(cad_info, check_stator=False, check_rotor=True) if e.startswith("Rotor_") or e.startswith("rotor")]
        global_errs = [e for e in check_subsystem_and_envelope(cad_info, check_stator=False, check_rotor=False)]
        live_s_fps = {sn: cad_info["stator_stages"][sn]["fingerprint"] for sn, _, _ in STAGES}
        live_r_fps = {sn: cad_info["rotor_stages"][sn]["fingerprint"] for sn, _, _ in STAGES}
        s_fp_match = bool(stator_signed and sub_stator.get("solid_fingerprints") == live_s_fps)
        r_fp_match = bool(rotor_signed and sub_rotor.get("solid_fingerprints") == live_r_fps)
        xlsx_errs = verify_xlsx_against_cad(xlsx_p, cad_info, check_stator=True, check_rotor=True)
        step_ok = bool(cad_info["step_check"].get("ok"))
    else:
        stator_only_errs = ["CAD invalid"]
        rotor_only_errs = ["CAD invalid"]
        global_errs = ["CAD invalid"]
        s_fp_match = False
        r_fp_match = False
        xlsx_errs = ["CAD invalid"]
        step_ok = False

    renders_ok = (
        iso_png.is_file() and iso_png.stat().st_size > 1000
        and ax_png.is_file() and ax_png.stat().st_size > 1000
        and (portal_state.get("last_full_assembly") or {}).get("fcstd_sha256") == sha256_file(fcstd_p)
        and len(clean_errs) == 0
    )
    trans = audit_case_transparency()

    invariants = {
        "stator_signed_and_intact": bool(len(pur_s_errs) == 0 and stator_signed and len(stator_only_errs) == 0 and s_fp_match),
        "rotor_signed_and_intact": bool(len(pur_r_errs) == 0 and rotor_signed and len(rotor_only_errs) == 0 and r_fp_match),
        "global_airgap_mass_cg_valid": bool(cad_info.get("ok") and len(global_errs) == 0),
        "xlsx_formulas_and_schedules_synced": bool(cad_info.get("ok") and len(xlsx_errs) == 0),
        "step_renders_and_workspace_clean": bool(step_ok and renders_ok),
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
        "live_cad_summary": cad_info.get("summary") if cad_info.get("ok") else {},
        "diagnostics": {
            "stator_errors": stator_only_errs,
            "rotor_errors": rotor_only_errs,
            "global_errors": global_errs,
            "xlsx_errors": xlsx_errs,
            "clean_errors": clean_errs,
        },
        "protocol_transparency": trans,
    }


def _apply_role_cad_update(fcstd_src: Path, fcstd_dst: Path, step_dst: Path, role: str, target_rad: float, light_mode: bool) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        body_p = td / "upd.py"
        run_p = td / "run_upd.py"
        body_p.write_text(
            f"""
import FreeCAD, Part, math

STAGES = [("S1", 0.0, 24.0), ("S2", 24.0, 22.0), ("S3", 46.0, 21.0), ("S4", 67.0, 21.0)]

def make_stator(z0, h, r_in, r_base, r_fin, n_fins, fin_w):
    ring = Part.makeCylinder(r_base, h, FreeCAD.Vector(0,0,z0)).cut(
        Part.makeCylinder(r_in, h+2.0, FreeCAD.Vector(0,0,z0-1.0))
    )
    fins = []
    for i in range(n_fins):
        ang = math.degrees(2.0 * math.pi * i / n_fins)
        box = Part.makeBox(r_fin - r_base + 1.4, fin_w, h, FreeCAD.Vector(r_base - 1.4, -fin_w/2.0, z0))
        box.rotate(FreeCAD.Vector(0,0,z0), FreeCAD.Vector(0,0,1), ang)
        fins.append(box)
    return ring.fuse(fins).Solids[0]

def make_rotor(z0, h, r_bore, r_hub, r_tip_corner, n_splines, sp_w):
    r_box = math.sqrt(max(10.0, r_tip_corner * r_tip_corner - (0.5 * sp_w) ** 2))
    hub = Part.makeCylinder(r_hub, h, FreeCAD.Vector(0,0,z0)).cut(
        Part.makeCylinder(r_bore, h+2.0, FreeCAD.Vector(0,0,z0-1.0))
    )
    sps = []
    for i in range(n_splines):
        ang = math.degrees(2.0 * math.pi * i / n_splines)
        box = Part.makeBox(r_box - r_hub + 1.2, sp_w, h, FreeCAD.Vector(r_hub - 1.2, -sp_w/2.0, z0))
        box.rotate(FreeCAD.Vector(0,0,z0), FreeCAD.Vector(0,0,1), ang)
        sps.append(box)
    return hub.fuse(sps).Solids[0]

doc = FreeCAD.openDocument({str(fcstd_src)!r})
role = {role!r}
trad = float({target_rad!r})
light = {bool(light_mode)!r}

for idx, (sn, z0, h) in enumerate(STAGES):
    if role == "stator_lead":
        wall = (4.05 if idx < 2 else 3.35) if not light else (3.65 if idx < 2 else 3.05)
        sol = make_stator(z0, h, trad, trad + wall, 43.9, 20, 1.55)
        doc.getObject(f"Stator_{{sn}}").Shape = sol
    else:
        rb = (21.4 if idx < 2 else 22.5) if not light else (21.9 if idx < 2 else 23.1)
        sol = make_rotor(z0, h, rb, 28.0, trad, 16, 2.25)
        doc.getObject(f"Rotor_{{sn}}").Shape = sol

doc.recompute()
doc.saveAs({str(fcstd_dst)!r})
all_solids = []
for sn, _, _ in STAGES:
    all_solids.append(doc.getObject(f"Stator_{{sn}}").Shape.Solids[0])
    all_solids.append(doc.getObject(f"Rotor_{{sn}}").Shape.Solids[0])
Part.makeCompound(all_solids).exportStep({str(step_dst)!r})
""",
            encoding="utf-8",
        )
        run_p.write_text(f"ns = {{}}; exec(open({str(body_p)!r}, encoding='utf-8').read(), ns, ns)\n", encoding="utf-8")
        subprocess.run(["freecadcmd", str(run_p)], check=True, capture_output=True, text=True, timeout=75)


def solve_role(role: str, workspace: Path, portal_port: int, strict: bool = True) -> None:
    import urllib.request

    assert role in ("stator_lead", "rotor_lead")
    base = f"http://127.0.0.1:{portal_port}"
    sub = "stator" if role == "stator_lead" else "rotor"
    ctx_name = "STATOR_THERMAL" if sub == "stator" else "ROTOR_DYNAMICS"
    adm_p = Path("/opt/fc_state/sso_admin_key")
    adm_hdr = {"X-Internal-Admin": adm_p.read_text(encoding="utf-8").strip()} if adm_p.is_file() else {}

    r1 = urllib.request.Request(f"{base}/api/ui/session", data=json.dumps({"subsystem_context": ctx_name, "unit_basis": "SI_MM_GRAM"}).encode(), headers={"Content-Type": "application/json", **adm_hdr}, method="POST")
    urllib.request.urlopen(r1, timeout=10).read()
    r2 = urllib.request.Request(f"{base}/api/ui/export_csv", data=b"{}", headers=adm_hdr, method="POST")
    urllib.request.urlopen(r2, timeout=10).read()

    fcstd_p = workspace / "servo_actuator.FCStd"
    xlsx_p = workspace / "Actuator_Mass_CG.xlsx"
    step_p = workspace / "release" / "servo_actuator_assy.step"

    live_before = run_freecad_inspect(fcstd_p)
    assert live_before.get("ok"), f"Live CAD unreadable: {live_before}"
    summ0 = live_before["summary"]
    if role == "stator_lead":
        max_r_tip = max(v["r_tip_mm"] for v in live_before["rotor_stages"].values())
        target_rad = round(max_r_tip + 1.24, 3)
        light_mode = (summ0["rotor_mass_g"] > 395.0)
    else:
        min_r_in = min(v["r_in_mm"] for v in live_before["stator_stages"].values())
        target_rad = round(min_r_in - 1.24, 3)
        light_mode = (summ0["stator_mass_g"] > 395.0)

    _apply_role_cad_update(fcstd_p, fcstd_p, step_p, role, target_rad=target_rad, light_mode=light_mode)

    for sn, _, _ in STAGES:
        code, resp = post_json(f"{base}/api/bench/actuation_rig", {"subsystem": sub, "mode": "stage_isolation", "stage": sn}, timeout_s=300)
        if strict:
            assert code == 200 and resp.get("qualified"), f"{role} stage {sn} rig failed: {resp}"

    code, resp = post_json(f"{base}/api/bench/actuation_rig", {"subsystem": sub, "mode": "full_assembly"}, timeout_s=300)
    if strict:
        assert code == 200 and resp.get("qualified"), f"{role} full_assembly rig failed: {resp}"

    cad_after = run_freecad_inspect(fcstd_p)
    if role == "stator_lead":
        update_single_sheet_xlsx(xlsx_p, "Stator_Schedule", _make_xlsx_stator_rows(cad_after["stator_stages"]))
    else:
        update_single_sheet_xlsx(xlsx_p, "Rotor_Schedule", _make_xlsx_rotor_rows(cad_after["rotor_stages"]))
    update_single_sheet_xlsx(xlsx_p, "Assembly_Summary", _make_xlsx_summary_rows(cad_after["summary"]))

    summ = cad_after["summary"]
    payload = {
        "subsystem": sub,
        "mass_g": summ["stator_mass_g"] if sub == "stator" else summ["rotor_mass_g"],
        "cg_z_mm": summ["stator_cg_z_mm"] if sub == "stator" else summ["rotor_cg_z_mm"],
        "performance_total": summ["q_diss_total_w"] if sub == "stator" else summ["k_torsion_total_knm"],
        "min_airgap_mm": summ["min_airgap_mm"],
        "step_sha256": sha256_file(step_p),
    }
    code, sresp = post_json(f"{base}/api/plm/submit", payload, timeout_s=120)
    if strict:
        assert code == 200 and sresp.get("status") == "APPROVED", f"{role} submit failed ({code}): {sresp}"


def simulate_naive_race(workspace: Path, portal_port: int) -> None:
    fcstd_p = workspace / "servo_actuator.FCStd"
    xlsx_p = workspace / "Actuator_Mass_CG.xlsx"
    step_p = workspace / "release" / "servo_actuator_assy.step"

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        snap_fcstd = td / "rotor_cached_v0.FCStd"
        snap_xlsx = td / "rotor_cached_v0.xlsx"
        shutil.copy2(fcstd_p, snap_fcstd)
        shutil.copy2(xlsx_p, snap_xlsx)

        solve_role("stator_lead", workspace, portal_port, strict=True)

        # Second engineer writes from cached v0 snapshot (closing airgap from 32.10 -> 30.86 and clobbering stator!)
        _apply_role_cad_update(snap_fcstd, fcstd_p, step_p, "rotor_lead", target_rad=30.86, light_mode=False)
        shutil.copy2(snap_xlsx, xlsx_p)
        solve_role("rotor_lead", workspace, portal_port, strict=False)
