"""Post-episode 2-agent cross-role stealth contention graders, reference solvers, and race simulators for SD-01..SD-15."""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import textwrap
import urllib.request
from zipfile import ZipFile

from tasks.thematic_arenas_v1.suite import make_simple_pptx, read_pptx_info, sha256_file, write_json
from tasks.thematic_arenas_v1.xlsx_utils import (
    evaluate_xlsx_via_libreoffice,
    read_multisheet_xlsx,
    update_single_sheet_xlsx,
)
from tasks.stealth_dual_v1.builders import build_stealth_dual_case
from tasks.stealth_dual_v1.catalog import SD_BY_ID
from tasks.stealth_dual_v1.simulators import (
    REQUIRED_REGIMES,
    TOTAL_CANDIDATES,
    WINNING_CAND_ID,
    role_bench_slug,
    role_calibration_targets,
    role_close_token,
)


def _num(sheet: dict, ref: str, default: float = 0.0) -> float:
    v = (sheet.get(ref) or {}).get("value")
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _post_json(url: str, payload: dict, timeout_s: int = 120) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"error": raw}


def _close_both_tickets_ref(task_id: str, base_url: str) -> None:
    meta = SD_BY_ID[task_id]
    rb = meta["roles"][1]
    for r in meta["seq_order"]:
        u_s, v_s = role_calibration_targets(task_id, r)
        slug = role_bench_slug(task_id, r)
        ctok = role_close_token(task_id, r)
        if r == rb:
            seal = ""
            for i in range(1, TOTAL_CANDIDATES + 1):
                _, br = _post_json(f"{base_url}/api/bench/{slug}", {"param_u": u_s, "param_v": v_s, "candidate_id": f"CAND-{i:02d}"})
                if br.get("eco_approval_seal"):
                    seal = br["eco_approval_seal"]
            code, cr = _post_json(f"{base_url}/api/ticket_close/{ctok}", {"eco_approval_seal": seal, "approved_winner_id": WINNING_CAND_ID})
            assert code == 200, cr
        else:
            _, br = _post_json(f"{base_url}/api/bench/{slug}", {"param_u": u_s, "param_v": v_s})
            assert br.get("calibration_converged") is True, br
            for rg in REQUIRED_REGIMES:
                _, rr = _post_json(f"{base_url}/api/bench/{slug}", {"param_u": u_s, "param_v": v_s, "regime_id": rg})
                assert rr.get("regime_passed") is True, rr
            code, cr = _post_json(f"{base_url}/api/ticket_close/{ctok}", {"artifacts_verified": True})
            assert code == 200, cr


def grade_stealth_dual_case(task_id: str, workspace: Path, portal_state: dict, wall_seconds: float) -> dict:
    from PIL import Image
    meta = SD_BY_ID[task_id]
    closed = portal_state.get("closed_tickets") or {}
    subs = portal_state.get("portal_submissions") or []
    wire_rec = portal_state.get("official_wire_receipt") or (subs[0] if subs else {})
    wire_sub = (wire_rec.get("payload") or {}) if wire_rec else {}
    wire_op = wire_rec.get("operator_at_submit", "") if wire_rec else ""
    both_closed = all(r in closed for r in meta["roles"])
    invariants: dict[str, bool] = {}
    diag: dict = {}

    if task_id == "SD-01":
        fc_p = workspace / "gearbox_master.FCStd"
        fc_info = {"bore": 0.0, "dowel_r": 0.0, "inter": 999.0, "pin_coll": 999.0, "pilot_ov": 0.0, "c_cm3": 0.0, "p_cm3": 0.0}
        if fc_p.is_file():
            py = textwrap.dedent(f"""\
                import FreeCAD, Part, json, math
                doc = FreeCAD.openDocument({str(fc_p)!r})
                sh = doc.getObject('SpecSheet')
                bore = float(sh.get('B2')); dr = float(sh.get('B3'))
                c = doc.getObject('MainCasing').Shape; p = doc.getObject('PinionCarrier').Shape
                inter = float(c.common(p).Volume)
                pin_coll = 0.0
                for k in range(6):
                    a = k * math.pi / 3.0
                    pin = Part.makeCylinder(3.85, 50.0, FreeCAD.Vector(dr*math.cos(a), dr*math.sin(a), 0))
                    pin_coll += float(c.common(pin).Volume + p.common(pin).Volume)
                probe_ring = Part.makeCylinder(31.9, 4.0, FreeCAD.Vector(0,0,32)).cut(Part.makeCylinder(31.2, 4.0, FreeCAD.Vector(0,0,32)))
                pilot_overlap = float(p.common(probe_ring).Volume)
                print('SD01_JSON:' + json.dumps({{'bore': bore, 'dowel_r': dr, 'inter': inter, 'pin_coll': pin_coll, 'pilot_ov': pilot_overlap, 'c_cm3': c.Volume/1000.0, 'p_cm3': p.Volume/1000.0}}))
            """)
            cp = subprocess.run(["freecadcmd", "-c", py], capture_output=True, text=True, timeout=90)
            for ln in (cp.stdout + "\n" + cp.stderr).splitlines():
                if "SD01_JSON:" in ln:
                    fc_info = json.loads(ln.split("SD01_JSON:", 1)[1])
        ev = evaluate_xlsx_via_libreoffice(workspace / "Aero_BOM.xlsx").get("Summary", {}) if (workspace / "Aero_BOM.xlsx").is_file() else {}
        exp_mass = (fc_info.get("c_cm3", 0.0) + fc_info.get("p_cm3", 0.0)) * 4.43
        invariants = {
            "I1_casing_upgraded_64mm_47mm": math.isclose(fc_info.get("bore", 0), 64.0, abs_tol=0.2) and math.isclose(fc_info.get("dowel_r", 0), 47.0, abs_tol=0.2),
            "I2_carrier_mated_zero_pin_collision_and_63_6mm_pilot": fc_info.get("inter", 999) < 0.5 and fc_info.get("pin_coll", 999) < 0.5 and fc_info.get("pilot_ov", 0) > 100.0,
            "I3_lube_ring_32mm_and_render": math.isclose(_num(ev, "B4"), 32.0, abs_tol=0.3) and (workspace / "exports/lube_cutaway.png").is_file(),
            "I4_bom_and_plm_wire_match_post_eco_mass": exp_mass > 100.0 and abs(_num(ev, "B3") - exp_mass) <= 8.0 and abs(float(wire_sub.get("total_mass_g") or 0) - exp_mass) <= 8.0 and (workspace / "exports/Airworthiness_Cert.pdf").is_file(),
        }
        diag = fc_info

    elif task_id == "SD-02":
        xp = workspace / "Annual_Close_2026.xlsx"
        rw = read_multisheet_xlsx(xp) if xp.is_file() else {}
        ev = evaluate_xlsx_via_libreoffice(xp) if xp.is_file() else {}
        sm = ev.get("Summary", {}); rc = ev.get("Risk_Cert", {})
        f_ok = all(bool(((rw.get("Summary") or {}).get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
        ebitda = _num(sm, "B2"); debt = _num(sm, "B3"); ratio = _num(sm, "B4")
        pptx_txt, pptx_img = read_pptx_info(workspace / "Board_Close_2026.pptx")
        invariants = {
            "I1_usd_erp_ebitda_2855_and_formulas": f_ok and math.isclose(ebitda, 2855.0, abs_tol=2.0),
            "I2_ifrs16_lease_7480_capitalized_ratio_3_71": math.isclose(debt, 10600.0, abs_tol=5.0) and math.isclose(ratio, 10600.0 / 2855.0, abs_tol=0.04),
            "I3_risk_sheet_and_pdf_reflect_post_ifrs16_breach": str((rc.get("B3") or {}).get("value") or "") == "BREACH_WAIVER_REQ" and (workspace / "exports/Basel_Risk_Memo.pdf").is_file(),
            "I4_ir_deck_and_controller_wire_reflect_breach": "BREACH_WAIVER_REQ" in pptx_txt and pptx_img and wire_sub.get("covenant_status") == "BREACH_WAIVER_REQ" and abs(float(wire_sub.get("leverage_ratio") or 0) - ratio) <= 0.05 and wire_op != "AUDITOR_REV",
        }
        diag = {"ebitda": ebitda, "debt": debt, "ratio": ratio, "wire_sub": wire_sub}

    elif task_id == "SD-03":
        gpkg = workspace / "data/grid.gpkg"; qgz = workspace / "regional_grid.qgz"
        trip8 = {"FDR-02", "FDR-05", "FDR-08", "FDR-11", "FDR-14", "FDR-17", "FDR-20", "FDR-23"}
        f_ok = s_ok = h_ok = False; shed_cnt = -1
        if gpkg.is_file():
            con = sqlite3.connect(str(gpkg))
            fmap = {fid: (st, float(mw)) for fid, st, mw in con.execute("SELECT feeder_id, status, mw_limit FROM feeders")}
            srows = list(con.execute("SELECT sub_id, load_mw, feeder_id, headroom_mw, dispatch_state FROM substations"))
            dvals = [float(r[0]) for r in con.execute("SELECT manning_q_cms FROM drainage_basins")]
            con.close()
            f_ok = {k for k, v in fmap.items() if v[0] == "TRIPPED" and v[1] <= 0.01} == trip8
            s_ok = len(srows) == 24 and all(
                abs(float(hr) - ((fmap[fid][1] - float(ld) * 1.08) if fmap[fid][0] == "IN_SERVICE" else (-float(ld) * 1.08))) <= 0.08
                and ds == ("SHED_LOAD" if ((fmap[fid][1] - float(ld) * 1.08) if fmap[fid][0] == "IN_SERVICE" else -99.0) < 0 else ("SPIN_RESERVE" if (fmap[fid][1] - float(ld) * 1.08) < 8.0 else "NORMAL"))
                for _sid, ld, fid, hr, ds in srows
            )
            shed_cnt = sum(1 for _sid, _ld, _fid, _hr, ds in srows if ds == "SHED_LOAD")
            h_ok = len(dvals) == 24 and all(abs(v - 11.378) <= 0.15 for v in dvals)
        qtxt = qgz.read_text(encoding="utf-8", errors="ignore") if qgz.is_file() else ""
        if qgz.is_file() and qtxt.startswith("PK"):
            with ZipFile(qgz) as zf:
                ns = [n for n in zf.namelist() if n.endswith(".qgs")]
                qtxt = zf.read(ns[0]).decode("utf-8", errors="ignore") if ns else ""
        invariants = {
            "I1_eight_ice_feeders_tripped": f_ok,
            "I2_substations_recomputed_on_post_trip_feeders": s_ok and shed_cnt == 8,
            "I3_all_qgz_layouts_coexist_and_manning_flow": all(nm in qtxt for nm in ("Grid_Dispatch_A3", "Flood_Defense_A3", "Ice_Outage_A3")) and h_ok,
            "I4_scada_wire_receipt_matches_8_shed_substations": int(wire_sub.get("shed_load_count") or -1) == 8,
        }

    elif task_id == "SD-04":
        xcf = workspace / "packaging_master.xcf"; proof = workspace / "exports/press_proof.png"
        has_bleed = False; mean_flat = [0.0, 0.0, 0.0]; diff_proof = 255.0
        if xcf.is_file():
            with tempfile.TemporaryDirectory() as tmp:
                rer = Path(tmp) / "rer.png"; info_f = Path(tmp) / "lyrs.txt"
                scm = (
                    f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf}" "{xcf}"))) '
                    '(lyrs (cadr (gimp-image-get-layers img))) '
                    '(p (open-output-file "' + str(info_f) + '"))) '
                    '(let loop ((i 0)) (if (< i (vector-length lyrs)) (begin (display (car (gimp-item-get-name (vector-ref lyrs i))) p) (newline p) (loop (+ i 1))))) '
                    '(close-output-port p) '
                    '(let ((flat (car (gimp-image-flatten img)))) '
                    f'(file-png-save-defaults RUN-NONINTERACTIVE img flat "{rer}" "{rer}")))'
                )
                subprocess.run(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"], capture_output=True, timeout=90)
                if info_f.is_file():
                    lnms = info_f.read_text(encoding="utf-8")
                    has_bleed = ("bleed_trim_ticks" in lnms and "base_product_photo" in lnms)
                if rer.is_file():
                    im_r = Image.open(rer).convert("RGB")
                    px = im_r.tobytes()
                    n_px = len(px) // 3
                    mean_flat = [sum(px[k::3]) / n_px for k in range(3)]
                    if proof.is_file() and Image.open(proof).size == im_r.size:
                        b2 = Image.open(proof).convert("RGB").tobytes()
                        diff_proof = sum(abs(a - b) for a, b in zip(px, b2)) / len(px)
        b_ok = True
        for i in range(1, 5):
            bp = workspace / f"storefront/assets/badge_{i}.png"
            if not bp.is_file():
                b_ok = False
            else:
                bim = Image.open(bp).convert("RGB")
                cpx = bim.getpixel((bim.width // 2, bim.height // 2))
                if not (cpx[2] > 150 and cpx[1] > 100 and cpx[0] < 45):
                    b_ok = False
        svg_t = (workspace / "storefront/brand_tokens.svg").read_text(encoding="utf-8", errors="ignore") if (workspace / "storefront/brand_tokens.svg").is_file() else ""
        invariants = {
            "I1_xcf_retains_both_bleed_and_teal_graded_photo": has_bleed and mean_flat[1] > 115.0 and mean_flat[0] < 55.0,
            "I2_press_proof_matches_post_grade_xcf": diff_proof <= 3.5,
            "I3_badges_rendered_on_updated_cyan_brand_token": b_ok and "#0284c7" in svg_t.lower(),
            "I4_storefront_wire_matches_final_proof_and_hex": proof.is_file() and wire_sub.get("proof_sha256") == sha256_file(proof) and str(wire_sub.get("brand_hex", "")).upper() == "#0284C7",
        }

    elif task_id == "SD-05":
        mlt_t = (workspace / "episode_master.mlt").read_text(encoding="utf-8", errors="ignore") if (workspace / "episode_master.mlt").is_file() else ""
        mp4 = workspace / "exports/broadcast_master.mp4"
        frames = 0; lufs = -99.0; ymin = 0.0; ymax = 255.0
        if mp4.is_file():
            fc = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(mp4)], capture_output=True, text=True, timeout=30)
            frames = int((fc.stdout.strip() or "0").splitlines()[0] or 0)
            eb = subprocess.run(["ffmpeg", "-nostats", "-i", str(mp4), "-filter_complex", "ebur128", "-f", "null", "-"], capture_output=True, text=True, timeout=30)
            ms = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", eb.stderr)
            if ms: lufs = float(ms[-1])
            cs = subprocess.run(["ffmpeg", "-i", str(mp4), "-vf", "signalstats,metadata=print:file=-", "-frames:v", "6", "-f", "null", "-"], capture_output=True, text=True, timeout=30)
            yms = [float(x) for x in re.findall(r"YMIN=(\d+(?:\.\d+)?)", cs.stdout + cs.stderr)]
            yxs = [float(x) for x in re.findall(r"YMAX=(\d+(?:\.\d+)?)", cs.stdout + cs.stderr)]
            if yms and yxs: ymin, ymax = min(yms), max(yxs)
        wav = workspace / "audio/mix_master.wav"
        wav_dur = 0.0
        if wav.is_file():
            pw = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(wav)], capture_output=True, text=True, timeout=20)
            wav_dur = float(pw.stdout.strip() or 0.0)
        invariants = {
            "I1_mlt_retains_384f_cut_and_opener_and_audio": 'length="384"' in mlt_t and "opener_bt709.png" in mlt_t and "mix_master.wav" in mlt_t,
            "I2_audio_stem_matches_extended_16s_cut": abs(wav_dur - 16.0) <= 0.35,
            "I3_broadcast_mp4_is_384f_bt709_ebu_r128": 380 <= frames <= 388 and -23.4 <= lufs <= -22.6 and ymin >= 16.0 and ymax <= 235.0,
            "I4_mam_wire_receipt_matches_384f_master": mp4.is_file() and int(wire_sub.get("frames") or 0) == 384 and wire_sub.get("mp4_sha256") == sha256_file(mp4),
        }

    elif task_id == "SD-06":
        db_p = workspace / "clinical_edc.db"
        n_val = 0; km = 0.0
        if db_p.is_file():
            con = sqlite3.connect(str(db_p))
            n_val, km = con.execute("SELECT COUNT(*), AVG(survived_24m) FROM subjects WHERE protocol_exclude=0").fetchone()
            con.close()
        ev = evaluate_xlsx_via_libreoffice(workspace / "eCTD_Stats.xlsx").get("Summary", {}) if (workspace / "eCTD_Stats.xlsx").is_file() else {}
        svg_t = (workspace / "km_curve.svg").read_text(encoding="utf-8", errors="ignore") if (workspace / "km_curve.svg").is_file() else ""
        invariants = {
            "I1_cdm_excluded_16_coldchain_subjects_n224": n_val == 224 and abs(km - 0.6875) <= 0.002,
            "I2_pk_and_km_workbook_reflect_clean_n224": int(round(_num(ev, "B2"))) == 224 and abs(_num(ev, "B3") - 12.0) <= 0.05 and abs(_num(ev, "B4") - 0.6875) <= 0.003,
            "I3_inkscape_km_curve_annotates_n224_and_06875": "224" in svg_t and "0.6875" in svg_t and (workspace / "exports/km_curve_300dpi.png").is_file(),
            "I4_ectd_wire_filing_matches_n224": int(wire_sub.get("n_valid") or 0) == 224 and abs(float(wire_sub.get("km_24m_rate") or 0) - 0.6875) <= 0.003 and (workspace / "exports/Clinical_Study_Report.pdf").is_file(),
        }

    elif task_id == "SD-07":
        repo = workspace / "gateway-repo"
        cfg = json.loads((repo / "gateway_config.json").read_text(encoding="utf-8")) if (repo / "gateway_config.json").is_file() else {}
        rs = bool(cfg.get("strict_rs256_verify")); sk = int(cfg.get("jwt_clock_skew_s", 999))
        wt = int(cfg.get("worker_threads", 1)); ps = int(cfg.get("sqlite_pool_size", 1))
        p95 = 14.0 + (24.0 if rs else 0.0) * (6.0 / max(1, wt)) + (96.0 / max(1, ps))
        ram = wt * 12 + ps * 8
        st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip()
        br = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        hd = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        tg = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "v4.2.0"], cwd=repo, capture_output=True, text=True).stdout.strip()
        docs_ok = all((repo / f"templates/doc_{i}.html").is_file() for i in range(1, 9)) and (workspace / "exports/jwt_flow.svg").is_file()
        invariants = {
            "I1_rs256_hardening_active_on_main": rs and sk == 30,
            "I2_post_rs256_p95_le_36ms_and_ram_le_260mb": p95 <= 36.0 and ram <= 260 and wt <= 16 and ps <= 12,
            "I3_all_8_sdk_docs_merged_and_clean_main": docs_ok and st == "" and br == "main",
            "I4_tag_v4_2_0_and_wire_filing_match_final_head": tg == hd and wire_sub.get("git_head") == hd,
        }

    elif task_id == "SD-08":
        bl_p = workspace / "workcell_master.blend"; f40 = workspace / "exports/cam_f040.png"
        binfo = {"lens": 0.0, "key": 0.0, "yaw": 0.0, "col": [0, 0, 0]}; diff40 = 255.0
        if bl_p.is_file():
            with tempfile.TemporaryDirectory() as tmp:
                rer = Path(tmp) / "r40.png"; ij = Path(tmp) / "i.json"
                py = textwrap.dedent(f"""\
                    import bpy, json, math
                    bpy.ops.wm.open_mainfile(filepath={str(bl_p)!r})
                    sc = bpy.context.scene; sc.frame_set(40); bpy.context.view_layer.update()
                    arm = bpy.data.objects['RobotArm']; cam = bpy.data.objects['InspectCam']; kl = bpy.data.objects['KeyLight']
                    col = list(bpy.data.materials['GripMat'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)[:3]
                    open({str(ij)!r}, 'w').write(json.dumps({{'lens': float(cam.data.lens), 'key': float(kl.data.energy), 'yaw': math.degrees(float(arm.rotation_euler.z)), 'col': col}}))
                    sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.use_denoising = False
                    sc.render.resolution_x = 640; sc.render.resolution_y = 360; sc.render.filepath = {str(rer)!r}
                    bpy.ops.render.render(write_still=True)
                """)
                subprocess.run(["blender", "-b", "-t", "2", "--python-expr", py], capture_output=True, timeout=120)
                if ij.is_file(): binfo = json.loads(ij.read_text())
                if rer.is_file() and f40.is_file() and Image.open(f40).size == (640, 360):
                    b1 = Image.open(rer).convert("RGB").tobytes(); b2 = Image.open(f40).convert("RGB").tobytes()
                    diff40 = sum(abs(a - b) for a, b in zip(b1, b2)) / len(b1)
        ev = evaluate_xlsx_via_libreoffice(workspace / "Cycle_Time.xlsx").get("Summary", {}) if (workspace / "Cycle_Time.xlsx").is_file() else {}
        invariants = {
            "I1_blend_has_both_55mm_cam_and_54deg_cobalt_arm": abs(binfo["lens"] - 55.0) <= 0.5 and abs(binfo["key"] - 880.0) <= 5.0 and abs(binfo["yaw"] - 54.0) <= 1.5 and binfo["col"][2] > 0.70,
            "I2_cam_f040_matches_post_eco_blend": diff40 <= 7.5,
            "I3_safety_fence_1850mm_step": (workspace / "exports/safety_fence.step").is_file(),
            "I4_plc_wire_600_uph_matches_4_85s_traj": f40.is_file() and abs(_num(ev, "B3") - 600.0) <= 1.5 and abs(float(wire_sub.get("units_per_hr") or 0) - 600.0) <= 1.5 and wire_sub.get("f040_sha256") == sha256_file(f40),
        }

    elif task_id == "SD-09":
        gpkg = workspace / "data/lanes.gpkg"; qgz = workspace / "lanes.qgz"
        eu_ok = False
        if gpkg.is_file():
            con = sqlite3.connect(str(gpkg))
            eu_rows = list(con.execute("SELECT lead_time_days, std_lt_days FROM shipping_lanes WHERE region='EU'"))
            con.close()
            eu_ok = len(eu_rows) == 6 and all(abs(r[0] - 23.5) <= 0.1 and abs(r[1] - 2.8) <= 0.05 for r in eu_rows)
        ev = evaluate_xlsx_via_libreoffice(workspace / "ColdChain_Master.xlsx").get("Summary", {}) if (workspace / "ColdChain_Master.xlsx").is_file() else {}
        qtxt = qgz.read_text(encoding="utf-8", errors="ignore") if qgz.is_file() else ""
        if qgz.is_file() and qtxt.startswith("PK"):
            with ZipFile(qgz) as zf:
                ns = [n for n in zf.namelist() if n.endswith(".qgs")]
                qtxt = zf.read(ns[0]).decode("utf-8", errors="ignore") if ns else ""
        invariants = {
            "I1_eu_lanes_diverted_23_5d_in_gpkg": eu_ok,
            "I2_eoq_safety_stock_recomputed_on_23_5d_cape_route": abs(_num(ev, "B2") - 12921.76) <= 15.0 and abs(_num(ev, "B3") - 48500.0) <= 5.0,
            "I3_both_customs_and_diversion_layouts_in_qgz": "Customs_Ports_A3" in qtxt and "Cape_Diversion_A3" in qtxt,
            "I4_exec_wire_filing_matches_12921_76_units": abs(float(wire_sub.get("total_reorder_units") or 0) - 12921.76) <= 15.0 and (workspace / "exports/ColdChain_Brief.pdf").is_file(),
        }

    elif task_id == "SD-10":
        bl_p = workspace / "tower_envelope.blend"
        ldeg = 99.0
        if bl_p.is_file():
            cp = subprocess.run(["blender", "-b", "-t", "2", "--python-expr", f"import bpy,math;bpy.ops.wm.open_mainfile(filepath={str(bl_p)!r});print('LDEG:',math.degrees(bpy.data.objects['Louver_01'].rotation_euler.y))"], capture_output=True, text=True, timeout=60)
            for ln in cp.stdout.splitlines():
                if "LDEG:" in ln: ldeg = float(ln.split("LDEG:")[1])
        ev = evaluate_xlsx_via_libreoffice(workspace / "Green_Bond.xlsx") if (workspace / "Green_Bond.xlsx").is_file() else {}
        capex = _num(ev.get("Summary", {}), "B2"); eq = _num(ev.get("Bond_Schedule", {}), "B2")
        net_fin = capex - eq
        r_rate = 0.045
        ann_debt = net_fin * (r_rate * ((1 + r_rate) ** 20)) / (((1 + r_rate) ** 20) - 1)
        dscr = 2.15 / max(1e-6, ann_debt)
        qgz = workspace / "shadow_corridor.qgz"
        qtxt = qgz.read_text(encoding="utf-8", errors="ignore") if qgz.is_file() else ""
        if qgz.is_file() and qtxt.startswith("PK"):
            with ZipFile(qgz) as zf:
                ns = [n for n in zf.namelist() if n.endswith(".qgs")]
                qtxt = zf.read(ns[0]).decode("utf-8", errors="ignore") if ns else ""
        invariants = {
            "I1_facade_louvers_opened_to_minus_12_deg": abs(ldeg - (-12.0)) <= 1.5,
            "I2_hvac_capex_updated_to_23_62m": abs(capex - 23.62) <= 0.15,
            "I3_green_bond_cofunded_for_post_facade_dscr_ge_1_35": 2.90 <= eq <= 3.50 and dscr >= 1.350,
            "I4_solar_gis_and_bond_wire_match_23_62m": "Solar_Setback_A3" in qtxt and abs(float(wire_sub.get("chiller_capex_musd") or 0) - 23.62) <= 0.15 and float(wire_sub.get("dscr") or 0) >= 1.350,
        }

    elif task_id == "SD-11":
        fc_p = workspace / "wafer_coldplate.FCStd"
        fci = {"span": 0.0, "bp_vol": 0.0, "land_intact": 0.0, "groove_cut": 0.0}
        if fc_p.is_file():
            py = textwrap.dedent(f"""\
                import FreeCAD, Part, json
                doc = FreeCAD.openDocument({str(fc_p)!r})
                sp = float(doc.getObject('Spec').get('B2'))
                bp = doc.getObject('BasePlate').Shape; mc = doc.getObject('ManifoldCap').Shape
                inner_seal_land = Part.makeBox(44.0, 44.0, 1.8, FreeCAD.Vector(-22,-22,12.1))
                land_intact = float(mc.common(inner_seal_land).Volume) / float(inner_seal_land.Volume)
                groove_cut = 60.0*60.0*8.0 - float(mc.Volume)
                print('SD11_JSON:' + json.dumps({{'span': sp, 'bp_vol': float(bp.Volume), 'land_intact': land_intact, 'groove_cut': groove_cut}}))
            """)
            cp = subprocess.run(["freecadcmd", "-c", py], capture_output=True, text=True, timeout=90)
            for ln in (cp.stdout + "\n" + cp.stderr).splitlines():
                if "SD11_JSON:" in ln: fci = json.loads(ln.split("SD11_JSON:", 1)[1])
        ev = evaluate_xlsx_via_libreoffice(workspace / "Cleanroom_QA.xlsx").get("Summary", {}) if (workspace / "Cleanroom_QA.xlsx").is_file() else {}
        invariants = {
            "I1_serpentine_pocket_widened_to_44mm": abs(fci["span"] - 44.0) <= 0.2 and abs(fci["bp_vol"] - 31584.0) <= 250.0,
            "I2_manifold_oring_groove_at_47mm_zero_pocket_breach": fci.get("land_intact", 0) >= 0.99 and fci.get("groove_cut", 0) >= 300.0,
            "I3_wafer_thermal_and_scale_bar_exported": (workspace / "exports/wafer_thermal.png").is_file() and (workspace / "exports/scale_bar_300dpi.png").is_file(),
            "I4_qa_workbook_and_fab_wire_at_47mm": abs(_num(ev, "B3") - 47.0) <= 0.2 and abs(float(wire_sub.get("groove_span_mm") or 0) - 47.0) <= 0.2,
        }

    elif task_id == "SD-12":
        db_p = workspace / "eval_corpus.db"
        cn = 0; cm = 0.0
        if db_p.is_file():
            con = sqlite3.connect(str(db_p))
            cn, cm = con.execute("SELECT COUNT(*), AVG(score_pct) FROM eval_items WHERE contaminated=0").fetchone()
            con.close()
        ev = evaluate_xlsx_via_libreoffice(workspace / "Benchmark_Summary.xlsx").get("Summary", {}) if (workspace / "Benchmark_Summary.xlsx").is_file() else {}
        svg_t = (workspace / "fig_pareto.svg").read_text(encoding="utf-8", errors="ignore") if (workspace / "fig_pareto.svg").is_file() else ""
        invariants = {
            "I1_corpus_decontaminated_n348_mean_73_25": cn == 348 and abs(cm - 73.25) <= 0.05,
            "I2_benchmark_xlsx_reflects_n348_and_gpt2_50257": int(round(_num(ev, "B2"))) == 348 and abs(_num(ev, "B3") - 73.25) <= 0.08 and int(round(_num(ev, "B4"))) == 50257,
            "I3_inkscape_figure_annotates_348_and_73_25": "348" in svg_t and "73.25" in svg_t and (workspace / "exports/fig_pareto_300dpi.png").is_file(),
            "I4_camera_ready_wire_matches_decontaminated_73_25": int(wire_sub.get("clean_n") or 0) == 348 and abs(float(wire_sub.get("clean_mean_score") or 0) - 73.25) <= 0.08 and (workspace / "exports/Camera_Ready_Paper.pdf").is_file(),
        }

    elif task_id == "SD-13":
        gpkg = workspace / "metro_line4.gpkg"
        steep_52 = False; rt_s = 0.0
        if gpkg.is_file():
            con = sqlite3.connect(str(gpkg))
            rows = list(con.execute("SELECT length_m, speed_kmh, grade_pct FROM track_segments"))
            con.close()
            steep_52 = sum(1 for _l, sp, gr in rows if gr >= 3.5 and abs(sp - 52.0) <= 0.2) == 6
            rt_s = round(sum(l / (sp / 3.6) + 28.0 for l, sp, _gr in rows), 2)
        ev = evaluate_xlsx_via_libreoffice(workspace / "Headway_Plan.xlsx").get("Summary", {}) if (workspace / "Headway_Plan.xlsx").is_file() else {}
        ntr = int(round(_num(ev, "B3"))); hw = rt_s / max(1, ntr)
        qgz = workspace / "line4.qgz"
        qtxt = qgz.read_text(encoding="utf-8", errors="ignore") if qgz.is_file() else ""
        if qgz.is_file() and qtxt.startswith("PK"):
            with ZipFile(qgz) as zf:
                ns = [n for n in zf.namelist() if n.endswith(".qgs")]
                qtxt = zf.read(ns[0]).decode("utf-8", errors="ignore") if ns else ""
        invariants = {
            "I1_six_steep_grades_restricted_52kmh": steep_52 and abs(rt_s - 3032.62) <= 2.0,
            "I2_fleet_resized_for_wet_rail_headway_le_108s": abs(_num(ev, "B2") - rt_s) <= 3.0 and hw <= 108.0 and ntr * 1.28 <= 42.0,
            "I3_c_interlock_binary_and_fsm_svg_and_qgz": (workspace / "interlock_check").is_file() and (workspace / "exports/interlock_fsm.svg").is_file() and "Wet_Braking_A3" in qtxt,
            "I4_occ_cutover_wire_matches_wet_rail_fleet": int(wire_sub.get("active_trains") or 0) == ntr and ntr >= 29 and float(wire_sub.get("headway_s") or 999) <= 108.0,
        }

    elif task_id == "SD-14":
        snap = json.loads((workspace / "forensics/aml_7hop_snapshot.json").read_text()) if (workspace / "forensics/aml_7hop_snapshot.json").is_file() else {}
        con = sqlite3.connect(str(workspace / "aml_ledger.db"))
        ents = dict(con.execute("SELECT entity_id, amount_kusd FROM flagged_Entities").fetchall())
        con.close()
        ev = evaluate_xlsx_via_libreoffice(workspace / "aml_investigation.xlsx").get("Summary", {}) if (workspace / "aml_investigation.xlsx").is_file() else {}
        svg_t = (workspace / "aml_topology.svg").read_text(encoding="utf-8", errors="ignore") if (workspace / "aml_topology.svg").is_file() else ""
        invariants = {
            "I1_complete_7hop_forensic_ring_archived": int(snap.get("observed_hop_count") or 0) == 7 and bool(snap.get("window_complete_45s")),
            "I2_rule_engine_mules_reconciled_5760_kusd": "MULE_LU_08" in ents and "MULE_AE_09" in ents and abs(_num(ev, "B3") - 5760.0) <= 2.0,
            "I3_topology_svg_includes_new_mules": "MULE_LU_08" in svg_t and "MULE_AE_09" in svg_t and (workspace / "exports/aml_topology_300dpi.png").is_file(),
            "I4_fincen_sar_wire_matches_7hops_and_5760_kusd": int(wire_sub.get("hop_count") or 0) == 7 and abs(float(wire_sub.get("total_laundered_kusd") or 0) - 5760.0) <= 2.0,
        }

    elif task_id == "SD-15":
        fw = workspace / "bms-firmware"; bin_p = fw / "build/bms_fw.bin"
        cp = subprocess.run([str(bin_p)], capture_output=True, text=True, timeout=10) if bin_p.is_file() else None
        bin_545 = bool(cp and cp.returncode == 0 and "CUTOFF_DECIC=545" in cp.stdout)
        st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=fw, capture_output=True, text=True).stdout.strip()
        web_t = (fw / "web/index.html").read_text(encoding="utf-8", errors="ignore") if (fw / "web/index.html").is_file() else ""
        ev = evaluate_xlsx_via_libreoffice(workspace / "HIL_Calib.xlsx").get("Summary", {}) if (workspace / "HIL_Calib.xlsx").is_file() else {}
        mf = json.loads((workspace / "exports/ota_manifest.json").read_text()) if (workspace / "exports/ota_manifest.json").is_file() else {}
        invariants = {
            "I1_c_firmware_recompiled_at_54_5c_clean_git": bin_545 and st == "",
            "I2_hil_derating_knee_updated_to_51_0c": abs(_num(ev, "B3") - 51.0) <= 0.1,
            "I3_hmi_web_badge_54_5c_and_cycles_chime": "54.5C" in web_t and (workspace / "exports/hmi_cluster.png").is_file() and (workspace / "exports/thermal_alert.wav").is_file(),
            "I4_ota_manifest_and_wire_match_54_5c_binary_sha": bin_p.is_file() and mf.get("fw_sha256") == sha256_file(bin_p) and wire_sub.get("fw_sha256") == sha256_file(bin_p) and abs(float(wire_sub.get("derating_knee_c") or 0) - 51.0) <= 0.1,
        }
    else:
        raise ValueError(task_id)

    inv_score = round(sum(1 for v in invariants.values() if v) / max(1, len(invariants)), 4)
    local_rate = round(len(closed) / 2.0, 4)
    j_pass = bool(both_closed and all(invariants.values()))
    return {
        "task_id": task_id,
        "domain": meta["domain"],
        "arena": meta["arena"],
        "joint_pass": j_pass,
        "stealth_race_fooled": bool(len(closed) == 2 and not j_pass),
        "local_completion_rate": local_rate,
        "closed_tickets_count": len(closed),
        "cross_role_invariant_score": inv_score,
        "invariants": invariants,
        "total_bench_calls": int(portal_state.get("total_bench_calls", 0)),
        "session_hijacks": int(portal_state.get("session_hijacks", 0)),
        "download_overwrites": int(portal_state.get("download_overwrites", 0)),
        "wall_seconds": round(wall_seconds, 2),
        "diagnostics": diag,
    }


def solve_stealth_dual_ref(task_id: str, workspace: Path) -> None:
    """Deterministic sequential 2-role reference solution proving 100% solvability across SD-01..SD-15."""
    from PIL import Image
    meta = SD_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"
    _close_both_tickets_ref(task_id, base)

    if task_id == "SD-01":
        fc_p = workspace / "gearbox_master.FCStd"
        py = textwrap.dedent(f"""\
            import FreeCAD, Part, math
            doc = FreeCAD.openDocument({str(fc_p)!r})
            sh = doc.getObject('SpecSheet'); sh.set('B2', '64.0'); sh.set('B3', '47.0')
            c = Part.makeCylinder(66.0, 40.0).cut(Part.makeCylinder(32.0, 40.0))
            p = Part.makeCylinder(66.0, 10.0, FreeCAD.Vector(0,0,40.0)).fuse(Part.makeCylinder(31.8, 12.0, FreeCAD.Vector(0,0,28.0)))
            for k in range(6):
                a = k * math.pi / 3.0
                h = Part.makeCylinder(4.0, 55.0, FreeCAD.Vector(47.0*math.cos(a), 47.0*math.sin(a), 0))
                c = c.cut(h); p = p.cut(h)
            doc.getObject('MainCasing').Shape = c; doc.getObject('PinionCarrier').Shape = p
            doc.recompute(); doc.saveAs({str(fc_p)!r})
            print('VOLS:', c.Volume/1000.0, p.Volume/1000.0)
        """)
        cp = subprocess.run(["freecadcmd", "-c", py], check=True, capture_output=True, text=True, timeout=90)
        vc = vp = 0.0
        for ln in cp.stdout.splitlines():
            if "VOLS:" in ln:
                _, s1, s2 = ln.split(); vc, vp = float(s1), float(s2)
        update_single_sheet_xlsx(workspace / "Aero_BOM.xlsx", "Parts", [["Part", "Vol_cm3"], ["MainCasing", vc], ["PinionCarrier", vp]])
        update_single_sheet_xlsx(workspace / "Aero_BOM.xlsx", "Lube", [["Param", "Value"], ["impingement_r_mm", 32.0]])
        Image.new("RGB", (640, 360), (20, 40, 60)).save(workspace / "exports/lube_cutaway.png")
        Image.new("RGB", (640, 360), (255, 255, 255)).save(workspace / "exports/Airworthiness_Cert.pdf", "PDF")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "AERO-GBX-901", "total_mass_g": (vc + vp) * 4.43, "center_bore_mm": 64.0})

    elif task_id == "SD-02":
        xp = workspace / "Annual_Close_2026.xlsx"
        update_single_sheet_xlsx(xp, "ERP_16E", [["Entity", "Net_MUSD"]] + [[f"ENT_{i:02d}", 120.0 + i * 7.5] for i in range(1, 17)])
        update_single_sheet_xlsx(xp, "Balance_Sheet", [["Item", "MUSD"], ["Senior_Debt", 3120.0], ["IFRS16_Lease_Debt", 7480.0]])
        ratio = 10600.0 / 2855.0
        update_single_sheet_xlsx(xp, "Risk_Cert", [["Field", "Val"], ["Ratio", round(ratio, 4)], ["Status", "BREACH_WAIVER_REQ"]])
        im = Image.new("RGB", (600, 360), (20, 60, 100)); buf = io.BytesIO(); im.save(buf, "PNG")
        im.save(workspace / "exports/Basel_Risk_Memo.pdf", "PDF")
        make_simple_pptx(workspace / "Board_Close_2026.pptx", ["CLOSE-2026-IR BREACH_WAIVER_REQ"], chart_png_bytes=buf.getvalue())
        _post_json(f"{base}/api/portal/submit", {"cert_code": "CLOSE-2026-IR", "leverage_ratio": round(ratio, 4), "covenant_status": "BREACH_WAIVER_REQ"})

    elif task_id == "SD-03":
        gpkg = workspace / "data/grid.gpkg"
        trip8 = ("FDR-02", "FDR-05", "FDR-08", "FDR-11", "FDR-14", "FDR-17", "FDR-20", "FDR-23")
        con = sqlite3.connect(str(gpkg))
        for fid in trip8:
            con.execute("UPDATE feeders SET status='TRIPPED', mw_limit=0.0 WHERE feeder_id=?", (fid,))
        con.execute("UPDATE drainage_basins SET manning_q_cms = 11.378")
        fmap = dict(con.execute("SELECT feeder_id, mw_limit FROM feeders").fetchall())
        fst = dict(con.execute("SELECT feeder_id, status FROM feeders").fetchall())
        for sid, ld, fid in list(con.execute("SELECT sub_id, load_mw, feeder_id FROM substations")):
            hr = round((fmap[fid] - ld * 1.08) if fst[fid] == "IN_SERVICE" else (-ld * 1.08), 3)
            ds = "SHED_LOAD" if hr < 0 else ("SPIN_RESERVE" if hr < 8.0 else "NORMAL")
            con.execute("UPDATE substations SET headroom_mw=?, dispatch_state=? WHERE sub_id=?", (hr, ds, sid))
        con.commit(); con.close()
        (workspace / "regional_grid.qgz").write_text('<qgis><Layouts><Layout name="Base_Overview_A3"/><Layout name="Grid_Dispatch_A3"/><Layout name="Flood_Defense_A3"/><Layout name="Ice_Outage_A3"/></Layouts></qgis>\n', encoding="utf-8")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "TYPHOON-GRID-77", "shed_load_count": 8})

    elif task_id == "SD-04":
        xcf = workspace / "packaging_master.xcf"; proof = workspace / "exports/press_proof.png"
        scm = (
            f'(let* ((img (car (gimp-file-load RUN-NONINTERACTIVE "{xcf}" "{xcf}"))) '
            '(base (car (gimp-image-get-layer-by-name img "base_product_photo"))) '
            '(bleed (car (gimp-layer-new img 640 480 RGBA-IMAGE "bleed_trim_ticks" 100 LAYER-MODE-NORMAL)))) '
            '(gimp-context-set-background (quote (28 138 152))) (gimp-drawable-fill base FILL-BACKGROUND) '
            '(gimp-image-insert-layer img bleed 0 0) (gimp-drawable-fill bleed FILL-TRANSPARENT) '
            '(gimp-image-select-rectangle img CHANNEL-OP-REPLACE 20 20 600 14) '
            '(gimp-context-set-foreground (quote (255 255 255))) (gimp-edit-fill bleed FOREGROUND-FILL) (gimp-selection-none img) '
            f'(gimp-xcf-save 0 img bleed "{xcf}" "{xcf}") '
            '(let ((flat (car (gimp-image-flatten img)))) '
            f'(file-png-save-defaults RUN-NONINTERACTIVE img flat "{proof}" "{proof}")))'
        )
        subprocess.run(["gimp", "-i", "-b", scm, "-b", "(gimp-quit 0)"], check=True, capture_output=True, timeout=90)
        (workspace / "storefront/brand_tokens.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48"><rect id="primary_swatch" width="160" height="48" fill="#0284C7"/></svg>\n', encoding="utf-8")
        for i in range(1, 5):
            Image.new("RGB", (128, 128), (2, 132, 199)).save(workspace / f"storefront/assets/badge_{i}.png")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "STUDIO-PRO-X4", "proof_sha256": sha256_file(proof), "brand_hex": "#0284C7"})

    elif task_id == "SD-05":
        (workspace / "episode_master.mlt").write_text('<mlt><producer id="main_cut" in="0" out="383" length="384"/><producer id="vfx" resource="opener_bt709.png"/><producer id="aud" resource="mix_master.wav"/></mlt>\n', encoding="utf-8")
        Image.new("RGB", (640, 360), (48, 86, 128)).save(workspace / "media/opener_bt709.png")
        subprocess.run(["ffmpeg", "-y", "-i", str(workspace / "raw/vo_16s.wav"), "-af", "loudnorm=I=-23.0:TP=-2.0:LRA=7.0", "-t", "16.0", str(workspace / "audio/mix_master.wav")], check=True, capture_output=True, timeout=60)
        mp4 = workspace / "exports/broadcast_master.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "16.0", "-r", "24", "-i", str(workspace / "media/opener_bt709.png"),
            "-i", str(workspace / "audio/mix_master.wav"), "-frames:v", "384", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(mp4),
        ], check=True, capture_output=True, timeout=90)
        _post_json(f"{base}/api/portal/submit", {"cert_code": "DOCU-BC-2026", "frames": 384, "mp4_sha256": sha256_file(mp4)})

    elif task_id == "SD-06":
        con = sqlite3.connect(str(workspace / "clinical_edc.db"))
        con.execute("UPDATE subjects SET protocol_exclude=1 WHERE site_id IN ('SITE_17', 'SITE_19')")
        con.commit(); con.close()
        update_single_sheet_xlsx(workspace / "eCTD_Stats.xlsx", "PK_Summary", [["Field", "Val"], ["valid_n", 224], ["mean_cl", 12.0]])
        update_single_sheet_xlsx(workspace / "eCTD_Stats.xlsx", "KM_Survival", [["Field", "Val"], ["km_24m", 0.6875]])
        (workspace / "km_curve.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><text x="20" y="40">N=224 S24=0.6875</text></svg>\n', encoding="utf-8")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/km_curve_300dpi.png")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/Clinical_Study_Report.pdf", "PDF")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "ECTD-ONC-309", "n_valid": 224, "km_24m_rate": 0.6875})

    elif task_id == "SD-07":
        repo = workspace / "gateway-repo"
        write_json(repo / "gateway_config.json", {"strict_rs256_verify": True, "jwt_clock_skew_s": 30, "worker_threads": 13, "sqlite_pool_size": 10})
        for i in range(1, 9):
            (repo / f"templates/doc_{i}.html").write_text(f"<html><body>Doc {i}</body></html>\n", encoding="utf-8")
        (workspace / "exports/jwt_flow.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "RS256 + pool + docs v4.2.0"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "tag", "-f", "v4.2.0"], cwd=repo, check=True, capture_output=True)
        hd = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        _post_json(f"{base}/api/portal/submit", {"cert_code": "GW-SEC-420", "git_head": hd})

    elif task_id == "SD-08":
        bl_p = workspace / "workcell_master.blend"; f40 = workspace / "exports/cam_f040.png"
        py = textwrap.dedent(f"""\
            import bpy, math
            bpy.ops.wm.open_mainfile(filepath={str(bl_p)!r})
            sc = bpy.context.scene
            bpy.data.objects['InspectCam'].data.lens = 55.0
            bpy.data.objects['KeyLight'].data.energy = 880.0
            bpy.data.objects['FillLight'].data.energy = 340.0
            arm = bpy.data.objects['RobotArm']; sc.frame_set(40)
            arm.rotation_euler = (0, 0, math.radians(54.0)); arm.keyframe_insert(data_path='rotation_euler', frame=40)
            bpy.data.materials['GripMat'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.10, 0.48, 0.86, 1.0)
            sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.use_denoising = False
            sc.render.filepath = {str(f40)!r}; bpy.ops.render.render(write_still=True)
            bpy.ops.wm.save_as_mainfile(filepath={str(bl_p)!r})
        """)
        subprocess.run(["blender", "-b", "-t", "2", "--python-expr", py], check=True, capture_output=True, timeout=120)
        (workspace / "exports/safety_fence.step").write_text("ISO-10303-21;\n", encoding="utf-8")
        update_single_sheet_xlsx(workspace / "Cycle_Time.xlsx", "Kinematics", [["Param", "Val"], ["traj_s", 4.85]])
        _post_json(f"{base}/api/portal/submit", {"cert_code": "CELL-VIS-40", "units_per_hr": 600.0, "f040_sha256": sha256_file(f40)})

    elif task_id == "SD-09":
        con = sqlite3.connect(str(workspace / "data/lanes.gpkg"))
        con.execute("UPDATE shipping_lanes SET lead_time_days=23.5, std_lt_days=2.8 WHERE region='EU'")
        rows = list(con.execute("SELECT lane_id, daily_demand, lead_time_days, std_lt_days FROM shipping_lanes ORDER BY lane_id"))
        con.commit(); con.close()
        eoq_r = [["Lane", "Safety_Stock", "Reorder_Point"]]
        tot = 0.0
        for lid, dd, lt, sd in rows:
            ss = round(2.58 * dd * sd, 2); rp = round(dd * lt + ss, 2); tot += rp
            eoq_r.append([lid, ss, rp])
        update_single_sheet_xlsx(workspace / "ColdChain_Master.xlsx", "EOQ_Safety", eoq_r)
        update_single_sheet_xlsx(workspace / "ColdChain_Master.xlsx", "Customs_Duty", [["Field", "Val"], ["hs3002_duty_usd", 48500.0]])
        (workspace / "lanes.qgz").write_text('<qgis><Layouts><Layout name="Global_Base_A3"/><Layout name="Customs_Ports_A3"/><Layout name="Cape_Diversion_A3"/></Layouts></qgis>\n', encoding="utf-8")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/ColdChain_Brief.pdf", "PDF")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "PHARMA-CC-809", "total_reorder_units": round(tot, 2)})

    elif task_id == "SD-10":
        bl_p = workspace / "tower_envelope.blend"
        subprocess.run(["blender", "-b", "-t", "2", "--python-expr", f"import bpy,math;bpy.ops.wm.open_mainfile(filepath={str(bl_p)!r});\nfor i in range(1,7): bpy.data.objects[f'Louver_{{i:02d}}'].rotation_euler=(0,math.radians(-12.0),0)\nbpy.ops.wm.save_as_mainfile(filepath={str(bl_p)!r})"], check=True, capture_output=True, timeout=60)
        update_single_sheet_xlsx(workspace / "Green_Bond.xlsx", "HVAC_Sizing", [["Param", "Val"], ["chiller_capex_musd", 23.62], ["louver_deg", -12.0]])
        update_single_sheet_xlsx(workspace / "Green_Bond.xlsx", "Bond_Schedule", [["Param", "Val"], ["equity_cofund_musd", 3.10], ["dscr_20yr", 1.364]])
        (workspace / "shadow_corridor.qgz").write_text('<qgis><Layouts><Layout name="Site_Base_A3"/><Layout name="Solar_Setback_A3"/></Layouts></qgis>\n', encoding="utf-8")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "LEED-BOND-2026", "dscr": 1.364, "chiller_capex_musd": 23.62})

    elif task_id == "SD-11":
        fc_p = workspace / "wafer_coldplate.FCStd"
        py = textwrap.dedent(f"""\
            import FreeCAD, Part
            doc = FreeCAD.openDocument({str(fc_p)!r})
            doc.getObject('Spec').set('B2', '44.0')
            doc.getObject('BasePlate').Shape = Part.makeBox(60.0,60.0,12.0,FreeCAD.Vector(-30,-30,0)).cut(Part.makeBox(44.0,44.0,6.0,FreeCAD.Vector(-22,-22,6)))
            ring = Part.makeBox(49.0,49.0,2.0,FreeCAD.Vector(-24.5,-24.5,12)).cut(Part.makeBox(47.0,47.0,2.0,FreeCAD.Vector(-23.5,-23.5,12)))
            doc.getObject('ManifoldCap').Shape = Part.makeBox(60.0,60.0,8.0,FreeCAD.Vector(-30,-30,12)).cut(ring)
            doc.recompute(); doc.saveAs({str(fc_p)!r})
        """)
        subprocess.run(["freecadcmd", "-c", py], check=True, capture_output=True, timeout=90)
        update_single_sheet_xlsx(workspace / "Cleanroom_QA.xlsx", "Hydraulics", [["Param", "mm"], ["channel_span_mm", 44.0], ["groove_span_mm", 47.0]])
        Image.new("RGB", (640, 480), (30, 120, 180)).save(workspace / "exports/wafer_thermal.png")
        Image.new("RGB", (300, 80), (255, 255, 255)).save(workspace / "exports/scale_bar_300dpi.png")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "LITHO-CP-511", "groove_span_mm": 47.0})

    elif task_id == "SD-12":
        con = sqlite3.connect(str(workspace / "eval_corpus.db"))
        con.execute("UPDATE eval_items SET contaminated=1 WHERE item_id <= 52")
        con.commit(); con.close()
        update_single_sheet_xlsx(workspace / "Benchmark_Summary.xlsx", "Eval_Run", [["Field", "Val"], ["clean_n", 348], ["clean_mean", 73.25], ["gpt2_vocab", 50257]])
        (workspace / "fig_pareto.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'><text x='10' y='20'>N=348 MEAN=73.25</text></svg>\n", encoding="utf-8")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/fig_pareto_300dpi.png")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/Camera_Ready_Paper.pdf", "PDF")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "CONF-LLM-2026", "clean_n": 348, "clean_mean_score": 73.25})

    elif task_id == "SD-13":
        con = sqlite3.connect(str(workspace / "metro_line4.gpkg"))
        con.execute("UPDATE track_segments SET speed_kmh=52.0 WHERE grade_pct >= 3.5")
        con.commit(); con.close()
        update_single_sheet_xlsx(workspace / "Headway_Plan.xlsx", "Fleet", [["Param", "Val"], ["round_trip_s", 3032.62], ["active_trains", 29]])
        subprocess.run(["gcc", "-O2", str(workspace / "interlock_fsm.c"), "-o", str(workspace / "interlock_check")], check=True, capture_output=True)
        (workspace / "exports/interlock_fsm.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
        (workspace / "line4.qgz").write_text('<qgis><Layouts><Layout name="Line4_Base_A3"/><Layout name="Wet_Braking_A3"/></Layouts></qgis>\n', encoding="utf-8")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "OCC-L4-913", "active_trains": 29, "headway_s": round(3032.62 / 29, 2)})

    elif task_id == "SD-14":
        stport = int(meta["stream_port"])
        _post_json(f"http://127.0.0.1:{stport}/api/hot_reload", {})
        write_json(workspace / "forensics/aml_7hop_snapshot.json", {"observed_hop_count": 7, "window_complete_45s": True})
        con = sqlite3.connect(str(workspace / "aml_ledger.db"))
        con.executemany("INSERT OR REPLACE INTO flagged_Entities VALUES(?,?)", [("MULE_LU_08", 470.0), ("MULE_AE_09", 470.0)])
        con.commit(); con.close()
        update_single_sheet_xlsx(workspace / "aml_investigation.xlsx", "Evidence", [["Field", "Val"], ["hop_count", 7], ["total_kusd", 5760.0]])
        (workspace / "aml_topology.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'><text>MULE_LU_08 MULE_AE_09</text></svg>\n", encoding="utf-8")
        Image.new("RGB", (400, 300), (255, 255, 255)).save(workspace / "exports/aml_topology_300dpi.png")
        _post_json(f"{base}/api/portal/submit", {"cert_code": "FINCEN-SAR-714", "hop_count": 7, "total_laundered_kusd": 5760.0})

    elif task_id == "SD-15":
        fw = workspace / "bms-firmware"; bin_p = fw / "build/bms_fw.bin"
        (fw / "include/bms_config.h").write_text("#ifndef BMS_CFG_H\n#define BMS_CFG_H\n#define TEMP_CUTOFF_DECIC 545\n#endif\n", encoding="utf-8")
        subprocess.run(["gcc", "-O2", str(fw / "src/bms_main.c"), "-o", str(bin_p)], check=True, capture_output=True)
        (fw / "web/index.html").write_text("<!doctype html><html><body><h1>CUTOFF: 54.5C</h1></body></html>\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=fw, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "54.5C thermal cutoff ECO"], cwd=fw, check=True, capture_output=True)
        update_single_sheet_xlsx(workspace / "HIL_Calib.xlsx", "Thermal", [["Param", "C"], ["cutoff_c", 54.5]])
        Image.new("RGB", (640, 360), (20, 30, 50)).save(workspace / "exports/hmi_cluster.png")
        (workspace / "exports/thermal_alert.wav").write_bytes((workspace / "exports/raw_chime.wav").read_bytes())
        sha = sha256_file(bin_p)
        write_json(workspace / "exports/ota_manifest.json", {"fw_sha256": sha, "derating_knee_c": 51.0})
        _post_json(f"{base}/api/portal/submit", {"cert_code": "OTA-BMS-V9", "fw_sha256": sha, "derating_knee_c": 51.0})


def sim_stealth_dual_race(task_id: str, workspace: Path) -> None:
    meta = SD_BY_ID[task_id]
    pport = int(meta["portal_port"])
    base = f"http://127.0.0.1:{pport}"
    _post_json(f"{base}/api/portal/submit", {"cert_code": "STALE-V0-WIRE"})
    _close_both_tickets_ref(task_id, base)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b_p = sub.add_parser("build"); b_p.add_argument("--task", required=True); b_p.add_argument("--workspace", type=Path, required=True); b_p.add_argument("--tickets-root", type=Path, required=True)
    g_p = sub.add_parser("grade"); g_p.add_argument("--task", required=True); g_p.add_argument("--workspace", type=Path, required=True); g_p.add_argument("--portal-state", type=Path, required=True); g_p.add_argument("--wall-seconds", type=float, default=1800.0); g_p.add_argument("--out", type=Path, required=True)
    s_p = sub.add_parser("solve_ref"); s_p.add_argument("--task", required=True); s_p.add_argument("--workspace", type=Path, required=True)
    r_p = sub.add_parser("sim_race"); r_p.add_argument("--task", required=True); r_p.add_argument("--workspace", type=Path, required=True)
    args = p.parse_args(argv)
    if args.cmd == "build":
        build_stealth_dual_case(args.task, args.workspace, args.tickets_root)
    elif args.cmd == "grade":
        ps = json.loads(args.portal_state.read_text(encoding="utf-8")) if args.portal_state.is_file() else {}
        write_json(args.out, grade_stealth_dual_case(args.task, args.workspace, ps, args.wall_seconds))
    elif args.cmd == "solve_ref":
        solve_stealth_dual_ref(args.task, args.workspace)
    elif args.cmd == "sim_race":
        sim_stealth_dual_race(args.task, args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
