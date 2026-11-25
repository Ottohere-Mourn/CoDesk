"""NF-14: Laparoscopic Surgical Workcell — Live Blender 3.4 GUI Multi-Mesh Assembly, Camera Raycast Occlusion & Open Writer DHF.

Authentic Co-Tenant Scenario:
  - Surgical Robotics Kinematics Engineer and Endoscope Optical/Thermal Engineer share a Medical Device R&D
    Workstation running **real Blender 3.4.1 GUI** (`laparoscopic_workcell.blend`, 13-object multi-mesh assembly)
    and **real LibreOffice Writer** (`Design_History_File.odt`, UNO `:2002`) on `:99`.
  - Couples 3D BVH organ-clearance posing of articulated instrument arms with Cycles camera framing/raycast
    line-of-sight to 3 surgical fiducials and a tight IEC 60601-2-18 intra-abdominal thermal cap (`<= 12.00 W`).
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any

from tasks.novel_frontier_v1.common import (
    build_grade_payload,
    file_atomic_lock,
    inspect_live_blender_readonly,
    inspect_live_uno_documents_readonly,
    launch_blender_gui_natural,
    launch_libreoffice_uno_natural,
    read_json_safe,
    read_odt_plain_text,
    render_scanned_exhibit_png,
    write_json,
    write_multipage_sop_pdf,
    write_simple_odt,
)

TASK_ID = "NF-14"
PORTAL_PORT = 19514
UNO_PORT = 2002
THERMAL_CAP_W = 12.00  # Bipolar floor 6.80W + LED floor 4.60W = 11.40W -> tight 0.60W coupled window [11.40, 12.00]W!
KIN_DOC_CODE = "IEC-60601-KIN-7410"
OPT_DOC_CODE = "IEC-60601-OPT-3928"

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "Live Blender 3.4 Surgical Workcell GUI & Open Writer DHF: 13-Mesh Organ-Clearance Kinematics vs. Cycles Camera Occlusion & IEC Thermal Cap",
    "domain": "Surgical Robotics 3D CAD/Kinematics (Blender 3.4 GUI) & Medical Endoscope Optical/Thermal Engineering",
    "track": "track2_shared_state",
    "workspace_mode": "shared",
    "roles": ("robotics_kinematics_eng", "endoscope_optics_eng"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (UNO_PORT,),
    "conc_role_timeout_s": 7200,
    "iso_role_timeout_s": 7200,
    "max_cua_calls": None,
}

BLENDER_BUILD_SCENE_PY = r"""
import bpy, math, mathutils, sys

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.use_denoising = False
sc.cycles.samples = 8
sc.render.resolution_x = 960
sc.render.resolution_y = 540
sc.world = bpy.data.worlds.new("SurgWorld")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.03, 0.05, 1.0)

def make_emit_mat(name, rgba, strength=6.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs[0])
    return m

def make_diffuse_mat(name, rgba):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
    return m

# 1. Insufflation dome reference ring + 3 trocar RCM ports (world frame) + rotated Patient_Pneumoperitoneum_Rig!
bpy.ops.object.empty_add(type='ARROWS', location=(4.0, 3.0, -3.0), rotation=(math.radians(8.0), math.radians(-6.0), math.radians(10.0)))
rig = bpy.context.active_object
rig.name = "Patient_Pneumoperitoneum_Rig"

for nm, loc in [
    ("Port_Left_RCM",  (-44.0, -10.0, 76.0)),
    ("Port_Right_RCM", ( 44.0, -10.0, 76.0)),
    ("Port_Optic_RCM", (  0.0, -48.0, 68.0)),
]:
    bpy.ops.mesh.primitive_torus_add(major_radius=5.0, minor_radius=1.2, location=loc)
    bpy.context.active_object.name = nm
    if nm != "Port_Optic_RCM":
        bpy.context.active_object["cannula_max_distal_insertion_mm"] = 80.0

# 2. Target hepatic lesion & 3 colored emissive fiducials (parented to rotated Patient_Pneumoperitoneum_Rig!)
bpy.ops.mesh.primitive_uv_sphere_add(radius=5.0, location=(0.0, 20.0, 20.0))
les = bpy.context.active_object
les.name = "HepaticTarget_Lesion"
les.data.materials.append(make_diffuse_mat("MatLesion", (0.55, 0.18, 0.18, 1.0)))
les.parent = rig

for fnm, floc, fcol in [
    ("Fiducial_Medial",   (-12.0, 18.0, 20.0), (1.00, 0.02, 0.02, 1.0)),
    ("Fiducial_Lateral",  ( 12.0, 18.0, 20.0), (0.02, 1.00, 0.02, 1.0)),
    ("Fiducial_Superior", (  0.0, 22.0, 30.0), (0.02, 0.88, 1.00, 1.0)),
]:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=3.4, location=floc)
    fo = bpy.context.active_object
    fo.name = fnm
    # Diffuse surgical marker (requires aimed SPOT Endoscope_Light to illuminate in Cycles render!)
    fo.data.materials.append(make_diffuse_mat("Mat_" + fnm, fcol))
    fo.parent = rig

# 3. Critical anatomical keep-out structures (>= 8.0 mm mesh clearance required!)
bpy.ops.mesh.primitive_uv_sphere_add(radius=7.0, location=(14.0, -4.0, 38.0))
pv = bpy.context.active_object
pv.name = "PortalVein_KeepOut"
pv.data.materials.append(make_diffuse_mat("MatPV", (0.75, 0.10, 0.35, 1.0)))
pv.parent = rig

bpy.ops.mesh.primitive_uv_sphere_add(radius=6.0, location=(-15.0, -4.0, 36.0))
bd = bpy.context.active_object
bd.name = "BileDuct_KeepOut"
bd.data.materials.append(make_diffuse_mat("MatBD", (0.65, 0.55, 0.10, 1.0)))
bd.parent = rig

# 4. Initial v0 colliding & sightline-occluding surgical arms (PENDING thermal allocation = 0.0 W):
mat_arm = make_diffuse_mat("MatArm", (0.75, 0.78, 0.82, 1.0))
bpy.ops.mesh.primitive_cylinder_add(radius=2.8, depth=72.0, location=(-21.0, -6.0, 40.0), rotation=(math.radians(55.0), 0.0, math.radians(8.0)))
lg = bpy.context.active_object
lg.name = "LeftGrasper_Arm"
lg.scale = (1.0, 1.0, 1.25)  # Non-uniform axial scale -> actual world shaft length = 90.0 mm (half = 45.0 mm)!
lg.data.materials.append(mat_arm)
lg["status"] = "PENDING"

bpy.ops.mesh.primitive_cylinder_add(radius=2.8, depth=72.0, location=(22.0, -6.0, 42.0), rotation=(math.radians(55.0), 0.0, math.radians(-8.0)))
rb = bpy.context.active_object
rb.name = "RightBipolar_Arm"
rb.scale = (1.0, 1.0, 1.25)
rb.data.materials.append(mat_arm)
rb["bipolar_duty_w"] = 0.0
rb["bipolar_freq_khz"] = 0
rb["iec_spec_freq_khz"] = 470
rb["status"] = "PENDING"

# 5. Initial v0 mis-aimed & over-standoff Endoscope_Camera + Endoscope_Light
cam_data = bpy.data.cameras.new("Endoscope_CamData")
cam_data.lens = 30.0
cam_data.clip_start = 1.0
cam_data.clip_end = 500.0
cam_data["iec_require_dof_focus_on_lesion"] = True
cam_data["iec_required_fstop"] = 4.0
cam_obj = bpy.data.objects.new("Endoscope_Camera", cam_data)
sc.collection.objects.link(cam_obj)
cam_obj.location = (0.0, -112.0, 130.0)
cam_obj.rotation_euler = (math.radians(78.0), 0.0, 0.0)
cam_obj["status"] = "PENDING"
sc.camera = cam_obj

lt_data = bpy.data.lights.new("Endoscope_SpotData", type='SPOT')
lt_data.energy = 38000.0
lt_data.spot_size = math.radians(64.0)
lt_data.spot_blend = 0.25
lt_data["max_coaxial_aim_err_deg"] = 12.0
lt_obj = bpy.data.objects.new("Endoscope_Light", lt_data)
sc.collection.objects.link(lt_obj)
lt_obj.location = (0.0, -50.0, 62.0)
lt_obj.rotation_euler = (0.0, 0.0, 0.0)  # Mis-aimed straight down (-Z) in v0 -> leaves fiducials unlit until aimed!
lt_obj["led_illuminator_w"] = 0.0
lt_obj["status"] = "PENDING"

bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
"""


def build_tickets_by_role() -> dict[str, str]:
    b = chr(96)
    ta = "\n".join([
        "# Work Order — Articulated Instrument Organ-Clearance & Bipolar Duty Qualification (`robotics_kinematics_eng`)",
        "",
        "## Context & Objective",
        f"Resolve anatomical collisions and sightline interference for `LeftGrasper_Arm` and `RightBipolar_Arm` in `{b}/workspace/shared_docs/laparoscopic_workcell.blend{b}` (open in Blender 3.4 on the desktop) per `{b}/workspace/SOP_Kinematics_60601.pdf{b}` and `{b}/workspace/exhibits/cannula_thermal_derating.png{b}`.",
        "",
        "## Deliverables",
        f"1. **Updated `{b}/workspace/shared_docs/laparoscopic_workcell.blend{b}`**:",
        "   - Reposition/orient `LeftGrasper_Arm` and `RightBipolar_Arm` so all organ keep-out surface clearances, inter-arm shaft separation, target lesion working reach, and optical corridor non-occlusion rules in Section 1 of the SOP hold without clobbering `Endoscope_Camera` or `Endoscope_Light`.",
        "   - Configure `RightBipolar_Arm['bipolar_duty_w']` and `RightBipolar_Arm['status'] = 'COMMITTED'` within both the hemostasis floor and the coupled IEC 60601 intra-abdominal thermal ceiling.",
        "   - Ensure the open Blender 3.4 workcell window on the desktop is synchronized with the saved `.blend` on disk (reload/revert or save in the open Blender session with zero unsaved dirty state).",
        f"2. **Shared DHF `{b}/workspace/shared_docs/Design_History_File.odt{b}`**:",
        "   - Record your kinematics verification summary and document control code while preserving existing DHF headers/sections and keeping the open LibreOffice Writer window synchronized with disk.",
        f"3. **Audit JSON `{b}/workspace/kinematics_clearance_audit.json{b}`**: Follow Section 3 of `SOP_Kinematics_60601.pdf`.",
    ])
    tb = "\n".join([
        "# Work Order — Endoscope Working Standoff, Fiducial Framing Render & LED Thermal Qualification (`endoscope_optics_eng`)",
        "",
        "## Context & Objective",
        f"Calibrate `Endoscope_Camera` and `Endoscope_Light` in `{b}/workspace/shared_docs/laparoscopic_workcell.blend{b}` (open in Blender 3.4 on the desktop) and render the illuminated endoscopic view per `{b}/workspace/SOP_Optics_60601.pdf{b}` and `{b}/workspace/exhibits/cannula_thermal_derating.png{b}`.",
        "",
        "## Deliverables",
        f"1. **Updated `{b}/workspace/shared_docs/laparoscopic_workcell.blend{b}` & Cycles Render `{b}/workspace/renders/endoscope_view.png{b}`**:",
        "   - Position and aim `Endoscope_Camera` (and `Endoscope_Light`) so camera-to-lesion standoff, 3-fiducial central safe-frame projection, and unobstructed line-of-sight hold without overwriting `LeftGrasper_Arm` or `RightBipolar_Arm`, then render `960x540` `renders/endoscope_view.png`.",
        "   - Configure `Endoscope_Light['led_illuminator_w']` and `Endoscope_Light['status'] = 'COMMITTED'` within both the optical SNR floor and the coupled IEC 60601 intra-abdominal thermal ceiling.",
        "   - Ensure the open Blender 3.4 workcell window on the desktop is synchronized with the saved `.blend` on disk (reload/revert or save in the open Blender session with zero unsaved dirty state).",
        f"2. **Shared DHF `{b}/workspace/shared_docs/Design_History_File.odt{b}`**:",
        "   - Append your optical framing and thermal signoff plus document control code while preserving existing DHF content and keeping the open LibreOffice Writer window synchronized with disk.",
        f"3. **Audit JSON `{b}/workspace/optics_framing_audit.json{b}`**: Follow Section 3 of `SOP_Optics_60601.pdf`.",
    ])
    return {"robotics_kinematics_eng": ta, "endoscope_optics_eng": tb}


def build_pristine(workspace_map: dict[str, Path], tickets_root: Path) -> None:
    ws_a = workspace_map["robotics_kinematics_eng"]
    ws_b = workspace_map["endoscope_optics_eng"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    (ws_a / "exhibits").mkdir(parents=True, exist_ok=True)
    (ws_b / "exhibits").mkdir(parents=True, exist_ok=True)
    (ws_b / "renders").mkdir(parents=True, exist_ok=True)
    hub.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["blender", "-b", "--python-expr", BLENDER_BUILD_SCENE_PY, "--", str(hub / "laparoscopic_workcell.blend")],
        check=True,
        capture_output=True,
        timeout=60,
    )

    render_scanned_exhibit_png(
        ws_a / "exhibits/cannula_thermal_derating.png",
        "IEC 60601-2-18 PNEUMOPERITONEUM CANNULA THERMAL DERATING CHART",
        [
            "Bipolar Hemostasis Coagulator Floor:   6.80 W  (Nominal target = 7.25 W; single-unit max = 8.80 W)",
            "Endoscope Fiber-LED Illuminator Floor: 4.60 W  (Nominal target = 5.05 W; single-unit max = 6.40 W)",
            "MAXIMUM COUPLED INTRA-ABDOMINAL DISSIPATION CAP:     12.00 W  (bipolar_duty_w + led_illuminator_w <= 12.00 W)",
            "Kinematics DHF Control Code:  " + KIN_DOC_CODE,
            "Optics DHF Control Code:      " + OPT_DOC_CODE,
        ],
        stamp_text="IEC 60601 SAFETY LAB",
    )
    (ws_b / "exhibits/cannula_thermal_derating.png").write_bytes((ws_a / "exhibits/cannula_thermal_derating.png").read_bytes())

    write_multipage_sop_pdf(
        ws_a / "SOP_Kinematics_60601.pdf",
        "SOP-SURG-60601A: Articulated Instrument Clearance & Bipolar Qualification",
        [
            ("1. 3D Trocar Kinematics & Organ Clearance", [
                "1.1 Inspect /workspace/shared_docs/laparoscopic_workcell.blend (1 unit = 1.0 mm; preserve all 14 scene objects and object scales, and synchronize the open Blender 3.4 GUI session with disk).",
                "1.2 Pose LeftGrasper_Arm and RightBipolar_Arm so physical 3D mesh-to-mesh surface clearance to PortalVein_KeepOut (portal_vein_clearance_mm) and BileDuct_KeepOut (bile_duct_clearance_mm) is >= 8.0 mm, each shaft's centerline axis passes within <= 4.0 mm of its trocar RCM port, arm center separation >= 38.0 mm, each arm's closest mesh vertex to HepaticTarget_Lesion center <= 22.0 mm, and neither arm occludes the endoscopic sightlines to the 3 fiducials.",
                "1.3 Commit RightBipolar_Arm['bipolar_duty_w'] >= 6.80 W (nominal 7.25 W, status='COMMITTED') within the 12.00 W coupled intra-abdominal cap, and sign /workspace/shared_docs/Design_History_File.odt.",
            ]),
            ("3. JSON Schema (/workspace/kinematics_clearance_audit.json)", [
                "  portal_vein_clearance_mm (float, 2 dec), bile_duct_clearance_mm (float, 2 dec),",
                "  min_organ_surface_clearance_mm (float, 2 dec), inter_arm_center_dist_mm (float, 2 dec),",
                "  left_tip_to_lesion_mm (float, 2 dec), right_tip_to_lesion_mm (float, 2 dec),",
                "  bipolar_duty_w (float, 2 dec), kinematics_dhf_code (str).",
            ]),
        ],
    )

    write_multipage_sop_pdf(
        ws_b / "SOP_Optics_60601.pdf",
        "SOP-SURG-60601B: Endoscope Optical Framing, Illumination & Thermal Qualification",
        [
            ("1. Endoscope Standoff, Illumination & Cycles Render", [
                "1.1 Calibrate Endoscope_Camera and Endoscope_Light in /workspace/shared_docs/laparoscopic_workcell.blend (preserve all 14 objects and synchronize the open Blender 3.4 GUI session with disk).",
                "1.2 Set camera-to-lesion center standoff in [76.0, 86.0] mm with optical axis passing within <= 5.0 mm of Port_Optic_RCM and upright horizon, aim BOTH Endoscope_Camera and the SPOT Endoscope_Light so all 3 surgical fiducials are clearly illuminated inside normalized camera frame [0.15, 0.85] x [0.15, 0.85] without occlusion, and render 960x540 /workspace/renders/endoscope_view.png (keep use_denoising=False).",
                "1.3 Commit Endoscope_Light['led_illuminator_w'] >= 4.60 W (nominal 5.05 W, status='COMMITTED') within the 12.00 W coupled cap, and sign /workspace/shared_docs/Design_History_File.odt.",
            ]),
            ("3. JSON Schema (/workspace/optics_framing_audit.json)", [
                "  camera_to_lesion_standoff_mm (float, 2 dec), optic_port_axis_err_mm (float, 2 dec),",
                "  fiducials_ndc_xy (dict Fiducial_* -> [x, y] rounded 3 dec),",
                "  all_fiducials_unoccluded (bool), led_illuminator_w (float, 2 dec), optics_dhf_code (str).",
            ]),
        ],
    )

    write_simple_odt(
        hub / "Design_History_File.odt",
        "IEC 60601-2-18 Laparoscopic Workcell Design History File",
        [
            ("DHF_HDR", "[DHF-REV-E-60601] Pre-Clinical Clearance, Optical Framing & Thermal Dossier"),
            ("STATUS", "Pending Robotics Kinematics and Endoscope Optics engineering verification."),
        ],
    )

    for role, md in build_tickets_by_role().items():
        td = tickets_root / role
        td.mkdir(parents=True, exist_ok=True)
        (td / "task.md").write_text(md + "\n", encoding="utf-8")


def run_portal_service(port: int, workspace_map: dict[str, Path], state_dir: Path, boot_ready_file: Path) -> None:
    del workspace_map
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / "service_state.json", {"task_id": TASK_ID, "uno_port": UNO_PORT})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return
        def do_GET(self) -> None:
            if self.path.startswith("/health"):
                raw = b'{"ok":true}'
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_response(404); self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    boot_ready_file.write_text(f"http://127.0.0.1:{port}/health\n", encoding="utf-8")
    srv.serve_forever()


def boot_desktop_apps(workspace_map: dict[str, Path], state_dir: Path, active_roles: tuple[str, ...] | None = None) -> None:
    del state_dir, active_roles
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    launch_blender_gui_natural(hub / "laparoscopic_workcell.blend")
    launch_libreoffice_uno_natural([hub / "Design_History_File.odt"], uno_port=UNO_PORT)


BLENDER_INSPECT_PY = r"""
import bpy, json, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
sc = bpy.context.scene

req_names = [
    "Patient_Pneumoperitoneum_Rig",
    "Port_Left_RCM", "Port_Right_RCM", "Port_Optic_RCM", "HepaticTarget_Lesion",
    "Fiducial_Medial", "Fiducial_Lateral", "Fiducial_Superior",
    "PortalVein_KeepOut", "BileDuct_KeepOut", "LeftGrasper_Arm", "RightBipolar_Arm",
    "Endoscope_Camera", "Endoscope_Light",
]
has_all = all(n in bpy.data.objects for n in req_names)
out = {"has_all": has_all}

if has_all:
    les_loc = bpy.data.objects["HepaticTarget_Lesion"].matrix_world.translation
    lg = bpy.data.objects["LeftGrasper_Arm"]
    rb = bpy.data.objects["RightBipolar_Arm"]
    pv = bpy.data.objects["PortalVein_KeepOut"]
    bd = bpy.data.objects["BileDuct_KeepOut"]
    cam = bpy.data.objects["Endoscope_Camera"]
    lt = bpy.data.objects["Endoscope_Light"]

    def mesh_world_verts(o):
        mw = o.matrix_world
        return [mw @ v.co for v in o.data.vertices]

    def world_bvh(o):
        verts = mesh_world_verts(o)
        polys = [tuple(p.vertices) for p in o.data.polygons]
        return BVHTree.FromPolygons(verts, polys), verts

    def bvh_min_dist(o1, o2):
        t1, v1 = world_bvh(o1)
        t2, v2 = world_bvh(o2)
        if t1.overlap(t2):
            return 0.0
        best = 9999.0
        for v in v1:
            loc, _n, _i, d = t2.find_nearest(v)
            if d is not None and d < best:
                best = d
        for v in v2:
            loc, _n, _i, d = t1.find_nearest(v)
            if d is not None and d < best:
                best = d
        return round(best, 3)

    pv_clr = round(min(bvh_min_dist(lg, pv), bvh_min_dist(rb, pv)), 3)
    bd_clr = round(min(bvh_min_dist(lg, bd), bvh_min_dist(rb, bd)), 3)
    d_clear = min(pv_clr, bd_clr)
    inter_arm = round((lg.matrix_world.translation - rb.matrix_world.translation).length, 3)
    l_reach = round(min((v - les_loc).length for v in mesh_world_verts(lg)), 3)
    r_reach = round(min((v - les_loc).length for v in mesh_world_verts(rb)), 3)

    def axis_to_point_dist(arm_obj, port_obj):
        p0 = arm_obj.matrix_world.translation
        az = (arm_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        pt = port_obj.matrix_world.translation
        return round(((pt - p0).cross(az)).length, 3)

    l_rcm = axis_to_point_dist(lg, bpy.data.objects["Port_Left_RCM"])
    r_rcm = axis_to_point_dist(rb, bpy.data.objects["Port_Right_RCM"])
    opt_rcm = axis_to_point_dist(cam, bpy.data.objects["Port_Optic_RCM"])
    cam_up_z = round(float((cam.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized().z), 3)
    lt_is_spot = (getattr(lt.data, "type", "") == "SPOT")
    lt_dir = (lt.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    to_les = (les_loc - lt.matrix_world.translation).normalized()
    lt_aim_deg = round(math.degrees(math.acos(max(-1.0, min(1.0, float(lt_dir.dot(to_les)))))), 2)
    p_l_w = bpy.data.objects["Port_Left_RCM"].matrix_world.translation
    p_r_w = bpy.data.objects["Port_Right_RCM"].matrix_world.translation
    l_ins = round(max((v - p_l_w).length for v in mesh_world_verts(lg) if v.z < p_l_w.z), 2)
    r_ins = round(max((v - p_r_w).length for v in mesh_world_verts(rb) if v.z < p_r_w.z), 2)

    cam_pos = cam.matrix_world.translation
    standoff = round((cam_pos - les_loc).length, 3)

    ndc = {}
    unoccluded = True
    unoccluded_anat = True
    arm_names = {"LeftGrasper_Arm", "RightBipolar_Arm"}
    for fn in ("Fiducial_Medial", "Fiducial_Lateral", "Fiducial_Superior"):
        fo = bpy.data.objects[fn]
        fc = fo.matrix_world.translation
        uvw = world_to_camera_view(sc, cam, fc)
        ndc[fn] = [round(float(uvw.x), 3), round(float(uvw.y), 3), round(float(uvw.z), 3)]
        vec = fc - cam_pos
        dist_f = vec.length
        hit, _hloc, _hnorm, _hidx, hobj, _hmw = sc.ray_cast(dg, cam_pos + vec.normalized() * 1.5, vec.normalized(), distance=max(1.0, dist_f - 4.0))
        if hit and hobj is not None and hobj.name != fn:
            unoccluded = False
            if hobj.name not in arm_names:
                unoccluded_anat = False
        # Also check sightline ignoring un-moved v0 arms so solo optics role can verify anatomical line-of-sight
        lg_hide, rb_hide = lg.hide_viewport, rb.hide_viewport
        lg.hide_viewport = True; rb.hide_viewport = True
        dg2 = bpy.context.evaluated_depsgraph_get()
        hit2, _hl2, _hn2, _hi2, hobj2, _hm2 = sc.ray_cast(dg2, cam_pos + vec.normalized() * 1.5, vec.normalized(), distance=max(1.0, dist_f - 4.0))
        if hit2 and hobj2 is not None and hobj2.name != fn:
            unoccluded_anat = False
        lg.hide_viewport = lg_hide; rb.hide_viewport = rb_hide

    dof_ok = bool(cam.data.dof.use_dof) and abs(float(cam.data.dof.focus_distance) - standoff) <= 2.5
    fstop_ok = bool(cam.data.dof.use_dof) and abs(float(cam.data.dof.aperture_fstop) - 4.0) <= 0.15
    freq_ok = int(rb.get("bipolar_freq_khz", 0)) == 470
    out.update({
        "pv_clearance_mm": pv_clr,
        "bd_clearance_mm": bd_clr,
        "min_organ_clearance_mm": d_clear,
        "inter_arm_dist_mm": inter_arm,
        "left_reach_mm": l_reach,
        "right_reach_mm": r_reach,
        "left_rcm_err_mm": l_rcm,
        "right_rcm_err_mm": r_rcm,
        "opt_rcm_err_mm": opt_rcm,
        "cam_up_z": cam_up_z,
        "lt_is_spot": lt_is_spot,
        "lt_aim_deg": lt_aim_deg,
        "dof_ok": dof_ok,
        "fstop_ok": fstop_ok,
        "freq_ok": freq_ok,
        "max_ins_mm": max(l_ins, r_ins),
        "standoff_mm": standoff,
        "ndc": ndc,
        "unoccluded": unoccluded,
        "unoccluded_anat": unoccluded_anat,
        "bipolar_w": float(rb.get("bipolar_duty_w", -1.0)),
        "bipolar_status": str(rb.get("status", "")),
        "led_w": float(lt.get("led_illuminator_w", -1.0)),
        "led_status": str(lt.get("status", "")),
    })

print("NF14_BLEND_JSON:" + json.dumps(out))
"""


def _inspect_workcell_blend(blend_path: Path) -> dict[str, Any]:
    if not blend_path.is_file():
        return {}
    cp = subprocess.run(
        ["blender", "-b", str(blend_path), "--python-expr", BLENDER_INSPECT_PY],
        capture_output=True, text=True, timeout=50,
    )
    for ln in cp.stdout.splitlines():
        if ln.startswith("NF14_BLEND_JSON:"):
            return json.loads(ln.split("NF14_BLEND_JSON:", 1)[1])
    return {}


def _inspect_render_png(png_path: Path) -> dict[str, Any]:
    from PIL import Image
    out = {"valid_dim": False, "has_red": False, "has_green": False, "has_cyan": False}
    if not png_path.is_file():
        return out
    try:
        with Image.open(png_path) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            out["valid_dim"] = (w == 960 and h == 540)
            for y in range(int(0.10 * h), int(0.90 * h), 2):
                for x in range(int(0.10 * w), int(0.90 * w), 2):
                    r, g, b = rgb.getpixel((x, y))
                    if r > 110 and r > g + 50 and r > b + 50:
                        out["has_red"] = True
                    elif g > 110 and g > r + 50 and g > b + 45:
                        out["has_green"] = True
                    elif b > 110 and g > 90 and r < 70:
                        out["has_cyan"] = True
    except Exception:
        pass
    return out


def grade(
    workspace_map: dict[str, Path],
    service_state: dict[str, Any],
    wall_seconds: float,
    active_roles: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    act_set = set(active_roles or META["roles"])
    has_a = "robotics_kinematics_eng" in act_set
    has_b = "endoscope_optics_eng" in act_set
    ws_a = workspace_map["robotics_kinematics_eng"]
    ws_b = workspace_map["endoscope_optics_eng"]
    hub = workspace_map.get("__shared_hub__", ws_a / "shared_docs")
    bl = _inspect_workcell_blend(hub / "laparoscopic_workcell.blend")
    bl_live = inspect_live_blender_readonly()
    rnd = _inspect_render_png(ws_b / "renders/endoscope_view.png")
    odt_txt = read_odt_plain_text(hub / "Design_History_File.odt")
    uno_state = inspect_live_uno_documents_readonly(UNO_PORT)
    ja = read_json_safe(ws_a / "kinematics_clearance_audit.json")
    jb = read_json_safe(ws_b / "optics_framing_audit.json")

    def _f(v: Any, d: float = -9999.0) -> float:
        try:
            return float(v)
        except Exception:
            return d

    uno_dhf_ok = True
    for u_url, u_doc in (uno_state.get("docs") or {}).items():
        if "Design_History_File.odt" in u_url:
            ut = u_doc.get("text") or ""
            ka = (not has_a) or (KIN_DOC_CODE in ut)
            kb = (not has_b) or (OPT_DOC_CODE in ut)
            uno_dhf_ok = (not u_doc.get("is_modified")) and ka and kb

    bl_live_a_ok = bool(bl_live.get("running")) and (not bl_live.get("is_dirty")) and (bl_live.get("bipolar_status") == "COMMITTED")
    bl_live_b_ok = bool(bl_live.get("running")) and (not bl_live.get("is_dirty")) and (bl_live.get("led_status") == "COMMITTED")

    clr = _f(bl.get("min_organ_clearance_mm"), 0.0)
    pv_clr = _f(bl.get("pv_clearance_mm"), 0.0)
    bd_clr = _f(bl.get("bd_clearance_mm"), 0.0)
    iarm = _f(bl.get("inter_arm_dist_mm"), 0.0)
    l_rch = _f(bl.get("left_reach_mm"), 999.0)
    r_rch = _f(bl.get("right_reach_mm"), 999.0)
    l_rcm = _f(bl.get("left_rcm_err_mm"), 999.0)
    r_rcm = _f(bl.get("right_rcm_err_mm"), 999.0)
    opt_rcm = _f(bl.get("opt_rcm_err_mm"), 999.0)
    cam_up_z = _f(bl.get("cam_up_z"), -1.0)
    stdoff = _f(bl.get("standoff_mm"), -1.0)
    bip_w = _f(bl.get("bipolar_w"), -1.0)
    led_w = _f(bl.get("led_w"), -1.0)
    ndc = bl.get("ndc") if isinstance(bl.get("ndc"), dict) else {}
    framed_cnt = sum(
        1 for fn in ("Fiducial_Medial", "Fiducial_Lateral", "Fiducial_Superior")
        if len(ndc.get(fn, [])) == 3 and (0.15 <= ndc[fn][0] <= 0.85) and (0.15 <= ndc[fn][1] <= 0.85) and ndc[fn][2] > 0
    )

    # 17 subchecks Role A
    checks_a: list[tuple[str, bool, float, str]] = [
        ("a_json", bool(ja), 0.05, "Missing kinematics_clearance_audit.json"),
        ("a_objs_kept", bool(bl.get("has_all")), 0.06, "Scene objects deleted/renamed in laparoscopic_workcell.blend"),
        ("a_organ_clr_6plus", clr >= 6.0, 0.06, f"3D organ surface clearance {clr} mm < 6.0 mm"),
        ("a_organ_clr_8mm", clr >= 8.0, 0.10, f"3D organ surface clearance {clr} mm < 8.0 mm SOP requirement"),
        ("a_inter_arm", iarm >= 38.0, 0.08, f"Inter-arm center separation {iarm} mm < 38.0 mm"),
        ("a_left_reach", l_rch <= 22.0, 0.08, f"LeftGrasper closest distance to lesion {l_rch} mm > 22.0 mm"),
        ("a_right_reach", r_rch <= 22.0, 0.08, f"RightBipolar closest distance to lesion {r_rch} mm > 22.0 mm"),
        ("a_rcm_fulcrum", l_rcm <= 4.0 and r_rcm <= 4.0, 0.08, f"Instrument shaft axis misses trocar RCM fulcrum ({l_rcm}, {r_rcm} > 4.0 mm)"),
        ("a_cannula_stop", _f(bl.get("max_ins_mm"), 999.0) <= 80.5, 0.09, f"Instrument insertion past RCM port {_f(bl.get('max_ins_mm'))} mm > 80.0 mm stop (check Port_*_RCM custom properties)"),
        ("a_fine_bip_freq", bool(bl.get("freq_ok")), 0.09, "RightBipolar_Arm['bipolar_freq_khz'] != 470 per object IEC custom properties"),
        ("a_json_clr_match", abs(_f(ja.get("portal_vein_clearance_mm")) - pv_clr) <= 1.2 and abs(_f(ja.get("bile_duct_clearance_mm")) - bd_clr) <= 1.2, 0.06, "JSON portal_vein/bile_duct world clearance mismatch (did you use local .location instead of matrix_world?)"),
        ("a_json_arm_match", abs(_f(ja.get("inter_arm_center_dist_mm")) - iarm) <= 1.0, 0.05, "JSON vs Blender inter-arm distance mismatch"),
        ("a_bip_range", 6.80 <= bip_w <= 8.80, 0.08, f"bipolar_duty_w={bip_w} outside [6.80, 8.80]W"),
        ("a_bip_committed", bl.get("bipolar_status") == "COMMITTED", 0.05, "RightBipolar_Arm['status'] != COMMITTED"),
        ("a_bip_json", abs(_f(ja.get("bipolar_duty_w")) - bip_w) <= 0.05, 0.05, "JSON vs .blend bipolar_duty_w mismatch"),
        ("a_code", ja.get("kinematics_dhf_code") == KIN_DOC_CODE, 0.07, "Wrong kinematics_dhf_code"),
        ("a_dhf_code", KIN_DOC_CODE in odt_txt and "[DHF-REV-E-60601]" in odt_txt, 0.08, "Design_History_File.odt missing KIN_DOC_CODE or header"),
        ("a_no_swap", bool(ja) and ja.get("kinematics_dhf_code") != OPT_DOC_CODE, 0.05, "Swapped DHF code"),
        ("a_blender_gui_synced", bool(ja) and bl_live_a_ok, 0.07, "Live open Blender 3.4 GUI window out-of-sync with disk .blend (did you reload/save in Blender GUI?)"),
    ]

    # 17 subchecks Role B
    checks_b: list[tuple[str, bool, float, str]] = [
        ("b_json", bool(jb), 0.05, "Missing optics_framing_audit.json"),
        ("b_objs_kept", bool(bl.get("has_all")), 0.05, "Scene objects deleted in .blend"),
        ("b_standoff", 76.0 <= stdoff <= 86.0, 0.10, f"Camera-to-lesion standoff {stdoff} mm outside [76.0, 86.0] mm"),
        ("b_optic_rcm_horizon", opt_rcm <= 5.0 and cam_up_z >= 0.45, 0.08, f"Camera optical axis misses Port_Optic_RCM ({opt_rcm} > 5.0 mm) or inverted horizon (up_z={cam_up_z})"),
        ("b_json_standoff", abs(_f(jb.get("camera_to_lesion_standoff_mm")) - stdoff) <= 0.6 and abs(_f(jb.get("optic_port_axis_err_mm")) - opt_rcm) <= 0.6, 0.06, "JSON standoff or optic_port_axis_err_mm mismatch"),
        ("b_framed_2plus", framed_cnt >= 2, 0.06, f"Fiducials inside [0.15,0.85] safe frame: {framed_cnt}/3"),
        ("b_framed_all3", framed_cnt == 3, 0.10, "Not all 3 fiducials framed inside [0.15, 0.85] NDC"),
        ("b_ray_unoccluded", bool(bl.get("unoccluded" if has_a else "unoccluded_anat")) and isinstance(jb.get("all_fiducials_unoccluded"), bool), 0.09, "Camera sightline to fiducials occluded in 3D raycast"),
        ("b_png_dim", rnd["valid_dim"], 0.07, "renders/endoscope_view.png missing or not 960x540"),
        ("b_png_colors", rnd["has_red"] and rnd["has_green"] and rnd["has_cyan"], 0.09, f"endoscope_view.png missing emissive Red/Green/Cyan fiducials ({rnd})"),
        ("b_spot_coaxial_aim", bool(bl.get("lt_is_spot")) and _f(bl.get("lt_aim_deg"), 999.0) <= 12.0, 0.07, f"Endoscope_Light not SPOT or aim error {_f(bl.get('lt_aim_deg'))} deg > 12.0 deg"),
        ("b_fine_cam_dof", bool(bl.get("dof_ok")), 0.09, "Camera DOF not enabled or focus_distance != lesion standoff per Endoscope_CamData custom properties"),
        ("b_fine_cam_fstop", bool(bl.get("fstop_ok")), 0.09, "Camera DOF aperture_fstop != 4.0 per Endoscope_CamData custom properties"),
        ("b_led_range", 4.60 <= led_w <= 6.40, 0.08, f"led_illuminator_w={led_w} outside [4.60, 6.40]W"),
        ("b_led_committed", bl.get("led_status") == "COMMITTED", 0.05, "Endoscope_Light['status'] != COMMITTED"),
        ("b_led_json", abs(_f(jb.get("led_illuminator_w")) - led_w) <= 0.05, 0.05, "JSON vs .blend led_illuminator_w mismatch"),
        ("b_code", jb.get("optics_dhf_code") == OPT_DOC_CODE, 0.07, "Wrong optics_dhf_code"),
        ("b_dhf_code", OPT_DOC_CODE in odt_txt and "[DHF-REV-E-60601]" in odt_txt, 0.08, "Design_History_File.odt missing OPT_DOC_CODE or header"),
        ("b_blender_gui_synced", bool(jb) and bl_live_b_ok, 0.07, "Live open Blender 3.4 GUI window out-of-sync with disk .blend (did you reload/save in Blender GUI?)"),
    ]

    eff_bip = bip_w if has_a else 6.80
    eff_led = led_w if has_b else 4.60
    tot_w = eff_bip + eff_led
    w_floors = ((not has_a) or (6.80 <= bip_w <= 8.80)) and ((not has_b) or (4.60 <= led_w <= 6.40))
    geom_a_ok = (not has_a) or ((clr >= 8.0) and (iarm >= 38.0) and (l_rch <= 22.0) and (r_rch <= 22.0))
    geom_b_ok = (not has_b) or ((76.0 <= stdoff <= 86.0) and (framed_cnt == 3) and bool(bl.get("unoccluded" if has_a else "unoccluded_anat")))
    act_sub = ((not has_a) or bool(ja)) and ((not has_b) or bool(jb))
    bl_gui_ok = ((not has_a) or bl_live_a_ok) and ((not has_b) or bl_live_b_ok)
    dhf_ok = ((not has_a) or (KIN_DOC_CODE in odt_txt)) and ((not has_b) or (OPT_DOC_CODE in odt_txt))
    checks_joint: list[tuple[str, bool, float, str]] = [
        ("j_iec_thermal_cap", w_floors and (tot_w <= THERMAL_CAP_W), 0.08, f"Coupled thermal dissipation {tot_w:.2f}W exceeds 12.00W IEC cap (or below floor)!"),
        ("j_blend_dual_valid", geom_a_ok and geom_b_ok, 0.08, "Monolithic laparoscopic_workcell.blend missing valid 3D clearance/framing or occluded camera"),
        ("j_blender_gui_synced", act_sub and bl_gui_ok, 0.07, "Live open Blender 3.4 GUI session out-of-sync with disk .blend"),
        ("j_uno_dhf_synced", act_sub and uno_dhf_ok, 0.05, "Live LibreOffice Writer UNO buffer out-of-sync with disk DHF .odt"),
        ("j_dhf_dual_signoff", dhf_ok, 0.05, "DHF missing required engineering signoff"),
    ]

    return build_grade_payload(
        task_id=TASK_ID,
        checks_a=checks_a,
        checks_b=checks_b,
        checks_joint=checks_joint,
        tickets_by_role=build_tickets_by_role(),
        service_state=service_state,
        wall_seconds=wall_seconds,
        pass_threshold=0.85,
    )


def _uno_sync_dhf_text(odt_path: Path, full_text: str, uno_port: int = UNO_PORT) -> None:
    del uno_port
    uri = odt_path.resolve().as_uri()
    code = (
        "import uno\n"
        "local = uno.getComponentContext()\n"
        "res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)\n"
        "ctx = res.resolve('uno:pipe,name=nf_uno_pipe;urp;StarOffice.ComponentContext')\n"
        "desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)\n"
        f"want = {json.dumps(uri)}\n"
        f"txt = {json.dumps(full_text)}\n"
        "en = desk.getComponents().createEnumeration()\n"
        "while en.hasMoreElements():\n"
        "    d = en.nextElement()\n"
        "    if hasattr(d, 'getText') and (not hasattr(d, 'getURL') or d.getURL() == want or 'Design_History_File.odt' in d.getURL()):\n"
        "        d.getText().setString(txt)\n"
        "        d.store()\n"
        "        break\n"
    )
    inner = f"export HOME=/home/user USER=user LOGNAME=user; python3 -c {shlex.quote(code)}"
    subprocess.run(["su", "-s", "/bin/bash", "user", "-c", inner], check=True, capture_output=True, timeout=25)


def _blender_gui_reload(blend_path: Path) -> None:
    cmd_p = Path("/run/user/1000/blender_live_cmd.json")
    if cmd_p.parent.is_dir():
        write_json(cmd_p, {"open_mainfile": str(blend_path.resolve())})
        for _ in range(16):
            if not cmd_p.exists():
                break
            time.sleep(0.2)
        time.sleep(0.6)


def solve_role(role: str, workspace_map: dict[str, Path], port: int, careful_conc: bool = False) -> None:
    del port, careful_conc
    assert role in ("robotics_kinematics_eng", "endoscope_optics_eng")
    ws = workspace_map[role]
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", ws / "shared_docs")
    blend_p = hub / "laparoscopic_workcell.blend"
    odt_p = hub / "Design_History_File.odt"

    if role == "robotics_kinematics_eng":
        with file_atomic_lock("nf14_shared_blend"):
            py = (
                "import bpy, math, sys\n"
                "from mathutils import Vector\n"
                "bpy.context.view_layer.update()\n"
                "les_w = bpy.data.objects['HepaticTarget_Lesion'].matrix_world.translation.copy()\n"
                "p_l = bpy.data.objects['Port_Left_RCM'].matrix_world.translation.copy()\n"
                "p_r = bpy.data.objects['Port_Right_RCM'].matrix_world.translation.copy()\n"
                "lg = bpy.data.objects['LeftGrasper_Arm']\n"
                "rb = bpy.data.objects['RightBipolar_Arm']\n"
                "lt = bpy.data.objects['Endoscope_Light']\n"
                "t_l = les_w + Vector((-17.5, 4.5, -5.0))\n"
                "u_l = (t_l - p_l).normalized()\n"
                "lg.location = t_l - u_l * 45.0\n"
                "lg.rotation_euler = u_l.to_track_quat('Z', 'Y').to_euler(); lg['status'] = 'COMMITTED'\n"
                "t_r = les_w + Vector((17.5, 4.5, -5.0))\n"
                "u_r = (t_r - p_r).normalized()\n"
                "rb.location = t_r - u_r * 45.0\n"
                "rb.rotation_euler = u_r.to_track_quat('Z', 'Y').to_euler()\n"
                "led_cur = float(lt.get('led_illuminator_w', 0.0))\n"
                "led_comm = (str(lt.get('status', '')) == 'COMMITTED')\n"
                "bw = round(max(6.80, min(7.25, 12.00 - led_cur - 0.05)) if led_comm else 7.15, 2)\n"
                "rb['bipolar_duty_w'] = bw; rb['bipolar_freq_khz'] = 470; rb['status'] = 'COMMITTED'\n"
                "bpy.context.view_layer.update()\n"
                "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n"
            )
            subprocess.run(["blender", "-b", str(blend_p), "--python-expr", py, "--", str(blend_p)], check=True, capture_output=True, timeout=50)
            _blender_gui_reload(blend_p)
            cur_txt = read_odt_plain_text(odt_p)
            lines = [ln for ln in cur_txt.splitlines() if ln.strip() and KIN_DOC_CODE not in ln]
            lines.append(f"[KIN] KINEMATICS_VERIFIED: {KIN_DOC_CODE}")
            _uno_sync_dhf_text(odt_p, "\n".join(lines))

        info = _inspect_workcell_blend(blend_p)
        write_json(
            ws / "kinematics_clearance_audit.json",
            {
                "portal_vein_clearance_mm": round(info["pv_clearance_mm"], 2),
                "bile_duct_clearance_mm": round(info["bd_clearance_mm"], 2),
                "min_organ_surface_clearance_mm": round(info["min_organ_clearance_mm"], 2),
                "inter_arm_center_dist_mm": round(info["inter_arm_dist_mm"], 2),
                "left_tip_to_lesion_mm": round(info["left_reach_mm"], 2),
                "right_tip_to_lesion_mm": round(info["right_reach_mm"], 2),
                "bipolar_duty_w": round(info["bipolar_w"], 2),
                "kinematics_dhf_code": KIN_DOC_CODE,
            },
        )
    else:
        with file_atomic_lock("nf14_shared_blend"):
            py = (
                "import bpy, sys\n"
                "from mathutils import Vector\n"
                "bpy.context.view_layer.update()\n"
                "sc = bpy.context.scene\n"
                "les_w = bpy.data.objects['HepaticTarget_Lesion'].matrix_world.translation.copy()\n"
                "p_opt = bpy.data.objects['Port_Optic_RCM'].matrix_world.translation.copy()\n"
                "cam = bpy.data.objects['Endoscope_Camera']\n"
                "lt = bpy.data.objects['Endoscope_Light']\n"
                "rb = bpy.data.objects['RightBipolar_Arm']\n"
                "aim_dir = (les_w + Vector((0.0, 0.0, 2.5)) - p_opt).normalized()\n"
                "cam.location = p_opt + aim_dir * ((les_w - p_opt).length - 81.0)\n"
                "cam.rotation_euler = aim_dir.to_track_quat('-Z', 'Y').to_euler()\n"
                "cam.data.dof.use_dof = True\n"
                "cam.data.dof.aperture_fstop = 4.0\n"
                "cam.data.dof.focus_distance = (cam.location - les_w).length\n"
                "cam['status'] = 'COMMITTED'\n"
                "lt.location = cam.location + aim_dir * 6.0\n"
                "lt.rotation_euler = (les_w + Vector((0.0, 0.0, 2.5)) - lt.location).to_track_quat('-Z', 'Y').to_euler()\n"
                "bip_cur = float(rb.get('bipolar_duty_w', 0.0))\n"
                "bip_comm = (str(rb.get('status', '')) == 'COMMITTED')\n"
                "lw = round(max(4.60, min(5.05, 12.00 - bip_cur - 0.05)) if bip_comm else 4.75, 2)\n"
                "lt['led_illuminator_w'] = lw; lt['status'] = 'COMMITTED'\n"
                "sc.cycles.use_denoising = False; sc.cycles.samples = 8\n"
                "sc.render.resolution_x = 960; sc.render.resolution_y = 540\n"
                "sc.render.filepath = sys.argv[-2]\n"
                "bpy.context.view_layer.update()\n"
                "bpy.ops.render.render(write_still=True)\n"
                "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n"
            )
            subprocess.run(
                ["blender", "-b", str(blend_p), "--python-expr", py, "--", str(ws / "renders/endoscope_view.png"), str(blend_p)],
                check=True, capture_output=True, timeout=60,
            )
            _blender_gui_reload(blend_p)
            cur_txt = read_odt_plain_text(odt_p)
            lines = [ln for ln in cur_txt.splitlines() if ln.strip() and OPT_DOC_CODE not in ln]
            lines.append(f"[OPT] OPTICS_VERIFIED: {OPT_DOC_CODE}")
            _uno_sync_dhf_text(odt_p, "\n".join(lines))

        info = _inspect_workcell_blend(blend_p)
        ndc_xy = {k: [v[0], v[1]] for k, v in info["ndc"].items()}
        write_json(
            ws / "optics_framing_audit.json",
            {
                "camera_to_lesion_standoff_mm": round(info["standoff_mm"], 2),
                "optic_port_axis_err_mm": round(info["opt_rcm_err_mm"], 2),
                "fiducials_ndc_xy": ndc_xy,
                "all_fiducials_unoccluded": bool(info["unoccluded"]),
                "led_illuminator_w": round(info["led_w"], 2),
                "optics_dhf_code": OPT_DOC_CODE,
            },
        )


def simulate_contention_probe(workspace_map: dict[str, Path], port: int, state_dir: Path) -> None:
    """Gate 4: Uncoordinated thermal settings (8.10 + 5.80 = 13.90W > 12.00W) & GUI Blender save clobbers arm pose."""
    solve_role("robotics_kinematics_eng", workspace_map, port)
    solve_role("endoscope_optics_eng", workspace_map, port)
    hub = Path("/workspace/shared_docs") if Path("/workspace/shared_docs").is_dir() else workspace_map.get("__shared_hub__", next(iter(workspace_map.values())))
    blend_p = hub / "laparoscopic_workcell.blend"
    py = (
        "import bpy, sys\n"
        "rb = bpy.data.objects['RightBipolar_Arm']; lt = bpy.data.objects['Endoscope_Light']\n"
        "rb.location = (6.0, -4.0, 36.0); rb['bipolar_duty_w'] = 8.10; lt['led_illuminator_w'] = 5.80\n"
        "bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])\n"
    )
    subprocess.run(["blender", "-b", str(blend_p), "--python-expr", py, "--", str(blend_p)], check=True, capture_output=True, timeout=45)
    sp = state_dir / "service_state.json"
    st = read_json_safe(sp)
    st["contention_events"] = int(st.get("contention_events", 0)) + 3
    write_json(sp, st)
