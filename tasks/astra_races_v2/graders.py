"""Deterministic graders and CLI entrypoints for the 10 Astra-High race tasks (AR-01..AR-10)."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ElementTree
from zipfile import ZipFile

from tasks.astra_races_v2.builders import build_task_bundle, run_checked, sha256_file, write_json
from tasks.astra_races_v2.catalog import ASTRA_RACE_CATALOG, CATALOG_BY_ID


def mean_rgb_diff(first_png: Path, second_png: Path) -> float:
    from PIL import Image

    if not first_png.is_file() or not second_png.is_file():
        return 255.0
    with Image.open(first_png) as img_one, Image.open(second_png) as img_two:
        rgb_one = img_one.convert("RGB")
        rgb_two = img_two.convert("RGB")
        if rgb_one.size != rgb_two.size:
            return 255.0
        raw_one = rgb_one.tobytes()
        raw_two = rgb_two.tobytes()
        return sum(abs(va - vb) for va, vb in zip(raw_one, raw_two)) / max(1, len(raw_one))


def read_json_safe(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def grade_task(task_id: str, workspace: Path, work_a: Path, work_b: Path, portal_state: dict | None = None) -> dict:
    sign_a = read_json_safe(work_a / "signoff.json")
    sign_b = read_json_safe(work_b / "signoff.json")
    pstate = portal_state or {}

    if task_id == "AR-01":
        out_json = Path(tempfile.mktemp(suffix=".json"))
        rerender = Path(tempfile.mktemp(suffix=".png"))
        probe = textwrap.dedent(f'''
            import bpy, json, math
            bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'robot_wrist.blend'}")
            scene = bpy.context.scene
            scene.frame_set(20)
            bpy.context.view_layer.update()
            key_l = bpy.data.objects.get("KeyLight")
            fill_l = bpy.data.objects.get("FillLight")
            cam_o = bpy.data.objects.get("InspectCam")
            wrist_o = bpy.data.objects.get("WristPitch")
            jaw_o = bpy.data.objects.get("GripperJaw")
            mat = bpy.data.materials.get("JawCoat")
            bsdf = mat.node_tree.nodes.get("Principled BSDF") if (mat and mat.use_nodes) else None
            info = {{
                "key_w": float(key_l.data.energy) if key_l else 0.0,
                "fill_w": float(fill_l.data.energy) if fill_l else 0.0,
                "lens": float(cam_o.data.lens) if cam_o else 0.0,
                "pitch_deg": math.degrees(float(wrist_o.rotation_euler.x)) if wrist_o else 0.0,
                "jaw_z": float(jaw_o.matrix_world.translation.z) if jaw_o else 0.0,
                "color": list(bsdf.inputs["Base Color"].default_value)[:3] if bsdf else [0, 0, 0],
                "rough": float(bsdf.inputs["Roughness"].default_value) if bsdf else 1.0,
            }}
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 24
            scene.cycles.use_denoising = False
            scene.render.resolution_x = 640
            scene.render.resolution_y = 360
            scene.render.filepath = r"{rerender}"
            bpy.ops.render.render(write_still=True)
            open(r"{out_json}", "w").write(json.dumps(info))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as py_f:
            py_f.write(probe)
            py_path = Path(py_f.name)
        try:
            run_checked(["blender", "-b", "--python", str(py_path)])
            info = json.loads(out_json.read_text(encoding="utf-8"))
            f20_png = workspace / "exports/cam_f020.png"
            f01_png = workspace / "exports/cam_f001.png"
            diff20 = mean_rgb_diff(f20_png, rerender)
            checks_a = {
                "lights_and_cam_calibrated": abs(info["key_w"] - 920.0) <= 3.0 and abs(info["fill_w"] - 360.0) <= 3.0 and abs(info["lens"] - 58.0) <= 0.5,
                "keyframes_rendered_and_signed": f01_png.is_file() and f20_png.is_file() and sign_a.get("f020_sha256") == sha256_file(f20_png),
                "jaw_z_and_f20_match_saved_blend": diff20 <= 8.5 and abs(float(sign_a.get("gripper_world_z_f20") or -99.0) - info["jaw_z"]) <= 0.05,
            }
            col = info["color"]
            sweeps_ok = sum(1 for p in work_b.glob("sweep_*.png")) >= 6
            checks_b = {
                "wrist_pitch_52deg_in_blend": abs(info["pitch_deg"] - 52.0) <= 1.5,
                "emerald_coat_in_blend": abs(col[0] - 0.08) <= 0.05 and abs(col[1] - 0.68) <= 0.05 and abs(col[2] - 0.42) <= 0.05 and abs(info["rough"] - 0.18) <= 0.04,
                "six_sweeps_and_preview": sweeps_ok and (workspace / "exports/kinematics_f020.png").is_file(),
            }
            return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"info": info, "f20_rgb_diff": round(diff20, 3)}}
        finally:
            py_path.unlink(missing_ok=True)
            out_json.unlink(missing_ok=True)
            rerender.unlink(missing_ok=True)

    if task_id == "AR-02":
        gpkg = workspace / "data/corridor.gpkg"
        qgz = workspace / "grid_corridor.qgz"
        conn = sqlite3.connect(str(gpkg))
        cur = conn.cursor()
        feeders_map = {fid: (st, float(mw)) for fid, st, mw in cur.execute("SELECT feeder_id, status, mw_limit FROM feeders")}
        subs_map = {sid: (float(ld), fid, float(hr), ds) for sid, ld, fid, hr, ds in cur.execute("SELECT sub_id, load_mw, feeder_id, headroom_mw, dispatch_state FROM substations")}
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        buf_ids = sorted(row[0] for row in cur.execute("SELECT feeder_id FROM tripped_corridor_buffer")) if "tripped_corridor_buffer" in tables else []
        conn.close()
        exp_tripped = ["FDR-01", "FDR-04", "FDR-07", "FDR-10", "FDR-12", "FDR-15"]
        subs_match = True
        for sid, (ld, fid, hr, ds) in subs_map.items():
            st, mw = feeders_map[fid]
            exp_hr = round(mw - ld * 1.08, 3) if st == "IN_SERVICE" else round(-ld * 1.08, 3)
            exp_ds = "SHED_LOAD" if exp_hr < 0.0 else ("SPIN_RESERVE" if exp_hr < 8.0 else "NORMAL")
            if abs(hr - exp_hr) > 0.03 or ds != exp_ds:
                subs_match = False
                break
        with ZipFile(qgz) as zf:
            qnames = [nm for nm in zf.namelist() if nm.endswith(".qgs")]
            qxml = zf.read(qnames[0]).decode("utf-8", errors="replace") if qnames else ""
        pdf_a = workspace / "exports/grid_headroom.pdf"
        pdf_b = workspace / "exports/outage_buffer.pdf"
        checks_a = {
            "substations_match_committed_feeders": subs_match,
            "headroom_layout_and_pdf": "Grid_Headroom_A4" in qxml and pdf_a.is_file() and pdf_a.stat().st_size > 1200,
            "qgz_hash_matches_signoff": sign_a.get("qgz_sha256") == sha256_file(qgz),
        }
        actual_tripped = sorted(fid for fid, (st, mw) in feeders_map.items() if st == "TRIPPED" and abs(mw) <= 1e-6)
        sweeps_ok = sum(1 for p in work_b.glob("ice_r*.png")) >= 7
        checks_b = {
            "six_feeders_tripped": actual_tripped == exp_tripped,
            "buffer_layer_and_outage_layout": buf_ids == exp_tripped and "tripped_corridor_buffer" in qxml and "Outage_Buffer_A4" in qxml,
            "seven_sweeps_and_pdf": sweeps_ok and pdf_b.is_file() and pdf_b.stat().st_size > 1200,
        }
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"tripped": actual_tripped}}

    if task_id == "AR-03":
        out_json = Path(tempfile.mktemp(suffix=".json"))
        fc_probe = textwrap.dedent(f'''
            import json, math, FreeCAD, Part
            from pathlib import Path
            ws = Path(r"{workspace}")
            doc = FreeCAD.openDocument(str(ws / "gearbox_housing.FCStd"))
            sheet = doc.getObject("SpecSheet")
            bore_d = float(sheet.get("B2"))
            dowel_r = float(sheet.get("B3"))
            casing = doc.getObject("MainCasing").Shape
            carrier = doc.getObject("PinionCarrier").Shape
            inter_v = float(casing.common(carrier).Volume)
            slice_s = Part.makeCylinder(70.0, 4.0, FreeCAD.Vector(0, 0, 32.0)).common(carrier)
            pilot_od = round(max(slice_s.BoundBox.XLength, slice_s.BoundBox.YLength), 3) if slice_s.Volume > 1.0 else 0.0
            pin_casing = 0.0
            pin_carrier = 0.0
            for idx in range(6):
                ang = idx * math.pi / 3.0
                pin = Part.makeCylinder(3.4, 56.0, FreeCAD.Vector(dowel_r * math.cos(ang), dowel_r * math.sin(ang), -2.0))
                pin_casing += float(pin.common(casing).Volume)
                pin_carrier += float(pin.common(carrier).Volume)
            bore_clear = float(Part.makeCylinder(30.5, 20.0, FreeCAD.Vector(0, 0, 5.0)).common(casing).Volume) <= 0.05
            open(r"{out_json}", "w").write(json.dumps({{"bore_d": bore_d, "dowel_r": dowel_r, "inter_v": inter_v, "pilot_od": pilot_od, "pin_casing": pin_casing, "pin_carrier": pin_carrier, "bore_clear": bore_clear}}))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as py_f:
            py_f.write(fc_probe)
            py_path = Path(py_f.name)
        try:
            run_checked(["freecadcmd", str(py_path)])
            info = json.loads(out_json.read_text(encoding="utf-8"))
            stl_cnt = sum(1 for p in work_b.rglob("*.stl"))
            checks_a = {
                "pilot_machined_to_spec": abs(info["pilot_od"] - (info["bore_d"] - 0.50)) <= 0.20,
                "six_dowels_aligned_and_zero_interference": info["inter_v"] <= 0.05 and info["pin_carrier"] <= 0.05,
                "step_and_signoff_match_doc": (workspace / "exports/pinion_carrier.step").is_file() and abs(float(sign_a.get("center_bore_mm") or 0.0) - info["bore_d"]) <= 0.15,
            }
            checks_b = {
                "spec_upgraded_62_and_46": abs(info["bore_d"] - 62.0) <= 0.1 and abs(info["dowel_r"] - 46.0) <= 0.1,
                "casing_62mm_bore_and_46mm_dowels": info["bore_clear"] and info["pin_casing"] <= 0.05,
                "45_stl_sweeps_and_casing_step": stl_cnt >= 45 and (workspace / "exports/main_casing.step").is_file(),
            }
            return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {**info, "stl_cnt": stl_cnt}}
        finally:
            py_path.unlink(missing_ok=True)
            out_json.unlink(missing_ok=True)

    if task_id == "AR-04":
        from PIL import Image

        flat_png = Path(tempfile.mktemp(suffix=".png"))
        layers_txt = Path(tempfile.mktemp(suffix=".txt"))
        scm = (
            f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{workspace}/packaging_master.xcf" "{workspace}/packaging_master.xcf"))) '
            f'(lyrs (cadr (gimp-image-get-layers img))) '
            f'(names (mapcar (lambda (l) (car (gimp-item-get-name l))) (vector->list lyrs))) '
            f'(port (open-output-file "{layers_txt}"))) '
            f'(display names port) (close-output-port port) '
            f'(let ((merged (car (gimp-image-flatten img)))) '
            f'(file-png-save-defaults RUN-NONINTERACTIVE img merged "{flat_png}" "{flat_png}")))'
        )
        try:
            run_checked(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"])
            lnames = layers_txt.read_text(encoding="utf-8", errors="replace")
            with Image.open(flat_png) as im_flat:
                rgb_im = im_flat.convert("RGB")
                px_bar = rgb_im.getpixel((320, 26))
                px_center = rgb_im.getpixel((320, 240))
            proof_png = workspace / "exports/press_proof_flat.png"
            proof_diff = mean_rgb_diff(proof_png, flat_png)
            checks_a = {
                "bleed_layer_and_white_bar_in_xcf": "bleed_trim_ticks" in lnames and min(px_bar) >= 235,
                "proof_png_matches_flattened_xcf": proof_png.is_file() and proof_diff <= 2.5,
                "xcf_sha_matches_signoff": sign_a.get("xcf_sha256") == sha256_file(workspace / "packaging_master.xcf"),
            }
            trials_cnt = sum(1 for p in work_b.glob("gimp_trial_*.png"))
            checks_b = {
                "teal_grade_in_xcf": abs(px_center[0] - 18) <= 15 and abs(px_center[1] - 152) <= 15 and abs(px_center[2] - 168) <= 15,
                "eight_gimp_trials_and_preview": trials_cnt >= 8 and (workspace / "exports/color_graded_preview.png").is_file(),
            }
            return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"layers": lnames, "px_bar": px_bar, "px_center": px_center, "proof_diff": round(proof_diff, 3)}}
        finally:
            flat_png.unlink(missing_ok=True)
            layers_txt.unlink(missing_ok=True)

    if task_id == "AR-05":
        mlt_path = workspace / "commercial_cut.mlt"
        mlt_text = mlt_path.read_text(encoding="utf-8", errors="replace")
        mp4_a = workspace / "exports/broadcast_master.mp4"
        frames_a = 0
        if mp4_a.is_file():
            pr = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(mp4_a)], capture_output=True, text=True, timeout=30)
            try:
                frames_a = int(pr.stdout.strip().splitlines()[0])
            except Exception:
                frames_a = 0
        exp_frames = 120 if "shot_02_extended" in mlt_text else 72
        checks_a = {
            "broadcast_mp4_matches_mlt_timeline": mp4_a.is_file() and abs(frames_a - exp_frames) <= 2,
            "qc_property_and_signoff_hashes": (
                (f">{frames_a}<" in mlt_text.replace(" ", "") or str(exp_frames) in mlt_text)
                and sign_a.get("mlt_sha256") == sha256_file(mlt_path)
                and sign_a.get("mp4_sha256") == (sha256_file(mp4_a) if mp4_a.is_file() else "")
            ),
        }
        bench_cnt = sum(1 for p in work_b.glob("codec_bench_*.mp4"))
        checks_b = {
            "extended_shot02_in_mlt": "shot_02_extended.mp4" in mlt_text and 'out="71"' in mlt_text,
            "six_veryslow_benches_and_director_mp4": bench_cnt >= 6 and (workspace / "exports/director_check.mp4").is_file(),
        }
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"frames_a": frames_a, "exp_frames": exp_frames, "bench_cnt": bench_cnt}}

    if task_id == "AR-06":
        ods_path = workspace / "q4_covenant_model.ods"
        odt_path = workspace / "board_certification.odt"
        pdf_path = workspace / "exports/board_certification.pdf"
        vals = {}
        with ZipFile(ods_path) as z_ods:
            cxml = ElementTree.fromstring(z_ods.read("content.xml"))
        for row_el in cxml.iter():
            if row_el.tag.endswith("table-row"):
                cells = [c for c in list(row_el) if c.tag.endswith("table-cell")]
                if len(cells) >= 2:
                    label = "".join(cells[0].itertext()).strip()
                    v_attr = cells[1].attrib.get("{urn:oasis:names:tc:opendocument:xmlns:office:1.0}value")
                    v_txt = "".join(cells[1].itertext()).strip()
                    try:
                        vals[label] = float(v_attr if v_attr is not None else v_txt)
                    except Exception:
                        pass
        ebitda = vals.get("ebitda", 15.0)
        net_debt = vals.get("senior_debt", 48.0) + vals.get("capitalized_leases", 0.0) + vals.get("hedge_offset", 0.0)
        exp_ratio = round(net_debt / ebitda, 2)
        exp_status = "COMPLIANT" if exp_ratio <= 3.50 else "BREACH"
        with ZipFile(odt_path) as z_odt:
            odt_txt = "".join(ElementTree.fromstring(z_odt.read("content.xml")).itertext())
        pdf_txt = ""
        if pdf_path.is_file():
            pdf_txt = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True).stdout
        expected_tag = f"RATIO={exp_ratio:.2f} STATUS={exp_status}"
        checks_a = {
            "hedge_offset_saved_in_ods": abs(vals.get("hedge_offset", 0.0) - (-1.50)) <= 0.02,
            "odt_and_pdf_match_committed_ods_covenant": expected_tag in odt_txt and expected_tag in pdf_txt,
            "ods_hash_matches_signoff": sign_a.get("ods_sha256") == sha256_file(ods_path),
        }
        scen_pdfs = sum(1 for p in work_b.rglob("*.pdf"))
        checks_b = {
            "capitalized_leases_15_in_ods": abs(vals.get("capitalized_leases", 0.0) - 15.0) <= 0.05,
            "twenty_scenario_pdfs": scen_pdfs >= 20,
        }
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"ods_vals": vals, "expected_tag": expected_tag, "odt_txt": odt_txt[:120]}}

    if task_id == "AR-07":
        approvals = pstate.get("approvals") or {}
        a_rec = approvals.get("treasury_ops") or {}
        b_rec = approvals.get("risk_officer") or {}
        locked = bool(pstate.get("terminal_locked") or pstate.get("concurrent_session_violation"))
        checks_a = {"treasury_batch_approved": (not locked) and a_rec.get("batch_id") == "TB-2026-Q4" and a_rec.get("computed_checksum") == "SHA-TB-991"}
        checks_b = {"risk_batch_approved": (not locked) and b_rec.get("batch_id") == "RB-2026-Q4" and b_rec.get("computed_checksum") == "SHA-RB-442"}
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"terminal_locked": locked, "session_clobber_events": pstate.get("session_clobber_events", []), "approvals": approvals}}

    if task_id == "AR-08":
        svg_path = workspace / "icons_sprite.svg"
        svg_txt = svg_path.read_text(encoding="utf-8", errors="replace")
        pubs = pstate.get("published_releases") or {}
        latest_sha = sha256_file(svg_path)
        has_nav = 'id="nav_menu"' in svg_txt and 'stroke-width="2.5"' in svg_txt
        has_alert = "#0EA5E9" in svg_txt.upper() and 'id="alert_warn"' in svg_txt and 'id="alert_ok"' in svg_txt
        pub_shas = {v.get("svg_sha256") for v in pubs.values()}
        tainted = bool(pstate.get("staging_collision_tainted"))
        nav_png = workspace / "exports/nav_sheet_300dpi.png"
        rerender_svg = Path(tempfile.mktemp(suffix=".png"))
        try:
            run_checked(["inkscape", "--export-type=png", "--export-dpi=300", f"--export-filename={rerender_svg}", str(svg_path)])
            nav_diff = mean_rgb_diff(nav_png, rerender_svg)
        finally:
            rerender_svg.unlink(missing_ok=True)
        checks_a = {
            "nav_glyphs_and_proof_match_saved_svg": has_nav and nav_png.is_file() and nav_diff <= 2.5,
            "rel_nav_published_clean_staging": (not tainted) and "REL-NAV" in pubs and latest_sha in pub_shas,
        }
        hint_cnt = sum(1 for p in work_b.glob("hint_*.png"))
        checks_b = {
            "alert_glyphs_and_cyan_in_svg": has_alert,
            "rel_alert_published_and_hints": (not tainted) and "REL-ALERT" in pubs and hint_cnt >= 8,
        }
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"pubs": pubs, "tainted": tainted, "nav_rgb_diff": round(nav_diff, 3), "staging_overwrites": pstate.get("staging_overwrites", [])}}

    if task_id == "AR-09":
        out_json = Path(tempfile.mktemp(suffix=".json"))
        rerender = Path(tempfile.mktemp(suffix=".png"))
        bl_probe = textwrap.dedent(f'''
            import bpy, bmesh, json
            bpy.ops.wm.open_mainfile(filepath=r"{workspace / 'valve_assembly.blend'}")
            scene = bpy.context.scene
            bpy.context.view_layer.update()
            valve = bpy.data.objects["ValveBody"]
            bm = bmesh.new()
            bm.from_object(valve, bpy.context.evaluated_depsgraph_get())
            bm.transform(valve.matrix_world)
            vol = float(bm.calc_volume())
            bm.free()
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 20
            scene.cycles.use_denoising = False
            scene.render.resolution_x = 480
            scene.render.resolution_y = 320
            scene.render.filepath = r"{rerender}"
            bpy.ops.render.render(write_still=True)
            open(r"{out_json}", "w").write(json.dumps({{"vol": vol}}))
        ''')
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as py_f:
            py_f.write(bl_probe)
            py_path = Path(py_f.name)
        try:
            run_checked(["blender", "-b", "--python", str(py_path)])
            actual_vol = json.loads(out_json.read_text(encoding="utf-8"))["vol"]
            q_rec = (pstate.get("locked_quotes") or {}).get("QT-904") or {}
            q_png = workspace / "exports/quote_render.png"
            q_diff = mean_rgb_diff(q_png, rerender)
            checks_a = {
                "quote_locked_with_current_alloy_and_volume": (
                    q_rec.get("alloy_code") == pstate.get("alloy_code")
                    and abs(float(q_rec.get("volume_cm3") or 0.0) - actual_vol) <= 3.5
                ),
                "quote_render_matches_saved_valve": q_png.is_file() and q_diff <= 8.5,
            }
            sweeps_ok = sum(1 for p in work_b.glob("valve_scale_*.png")) >= 6
            checks_b = {
                "valve_thickened_and_inconel_active": actual_vol >= 110.0 and pstate.get("alloy_code") == "INCONEL-625" and abs(float(pstate.get("rate_usd_per_cm3") or 0.0) - 4.80) <= 0.02,
                "six_pressure_renders": sweeps_ok,
            }
            return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"actual_vol": round(actual_vol, 2), "quote": q_rec, "q_rgb_diff": round(q_diff, 3)}}
        finally:
            py_path.unlink(missing_ok=True)
            out_json.unlink(missing_ok=True)
            rerender.unlink(missing_ok=True)

    if task_id == "AR-10":
        repo = workspace / "service_repo"
        branch_now = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip()
        reg_txt = (repo / "app/registry.py").read_text(encoding="utf-8", errors="replace") if (repo / "app/registry.py").is_file() else ""
        db_path = repo / "docs/reconciliation.sqlite3"
        row_cnt = 0
        if db_path.is_file():
            conn = sqlite3.connect(str(db_path))
            try:
                row_cnt = conn.execute("SELECT COUNT(*) FROM reconciled_batches").fetchone()[0]
            except Exception:
                row_cnt = 0
            conn.close()
        active_dep = (pstate.get("active_deployment") or {}).get("commit_sha")
        checks_a = {
            "clean_main_with_telemetry_dag_and_graphviz": (
                branch_now == "main" and dirty == "" and "telemetry_dag" in reg_txt
                and (repo / "docs/pipeline.svg").is_file() and (repo / "docs/pipeline.png").is_file()
            ),
            "active_staging_matches_main_head": active_dep == head_sha,
        }
        checks_b = {
            "clean_main_with_ledger_guard_and_sqlite": (
                branch_now == "main" and dirty == "" and "ledger_guard" in reg_txt and "0.0005" in reg_txt and row_cnt == 500
            ),
            "deployed_to_release_gate": len(pstate.get("deployments") or []) >= 1,
        }
        return {"task_id": task_id, "role_a_pass": all(checks_a.values()), "role_b_pass": all(checks_b.values()), "joint_pass": all(checks_a.values()) and all(checks_b.values()), "checks_a": checks_a, "checks_b": checks_b, "diagnostics": {"branch": branch_now, "dirty": dirty[:120], "head_sha": head_sha, "active_dep": active_dep, "row_cnt": row_cnt}}

    raise KeyError(f"Unknown task_id: {task_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--task", required=True)
    p_build.add_argument("--workspace", type=Path, required=True)
    p_build.add_argument("--ticket-a", type=Path, required=True)
    p_build.add_argument("--ticket-b", type=Path, required=True)

    p_grade = sub.add_parser("grade")
    p_grade.add_argument("--task", required=True)
    p_grade.add_argument("--workspace", type=Path, required=True)
    p_grade.add_argument("--work-a", type=Path, required=True)
    p_grade.add_argument("--work-b", type=Path, required=True)
    p_grade.add_argument("--portal-state", type=Path, default=None)
    p_grade.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "build":
        build_task_bundle(args.task, args.workspace.resolve(), args.ticket_a.resolve(), args.ticket_b.resolve())
        print(json.dumps({"built": args.task}))
        return 0
    if args.cmd == "grade":
        pstate = read_json_safe(args.portal_state.resolve()) if (args.portal_state and args.portal_state.is_file()) else {}
        try:
            res = grade_task(args.task, args.workspace.resolve(), args.work_a.resolve(), args.work_b.resolve(), pstate)
        except Exception as exc:
            res = {
                "task_id": args.task,
                "role_a_pass": False,
                "role_b_pass": False,
                "joint_pass": False,
                "checks_a": {"project_uncorrupted": False},
                "checks_b": {"project_uncorrupted": False},
                "diagnostics": {"corruption_or_grade_error": f"{type(exc).__name__}: {str(exc)[:300]}"},
            }
        write_json(args.out.resolve(), res)
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
