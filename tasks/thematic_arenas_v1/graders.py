"""4-dimensional graders (Milestones + Final Rubric & Delayed Canary + Efficiency + Side-Effects) for TA-A1..TA-E1."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

from PIL import Image

from tasks.thematic_arenas_v1.catalog import TA_BY_ID
from tasks.thematic_arenas_v1.services import _evaluate_cluster_health
from tasks.thematic_arenas_v1.suite import read_pptx_info, sha256_file
from tasks.thematic_arenas_v1.xlsx_utils import evaluate_xlsx_via_libreoffice, read_multisheet_xlsx


def _wrap_4d_grade(
    task_id: str,
    role_passes: dict[str, bool],
    milestones: dict[str, bool],
    rubric: dict[str, bool],
    canary_passed: bool,
    portal_state: dict,
    wall_seconds: float,
    diagnostics: dict,
) -> dict:
    meta = TA_BY_ID[task_id]
    lb_s = float(meta["critical_section_lower_bound_s"])
    eff_wall = max(1.0, float(wall_seconds or lb_s))
    eff_ratio = round(min(1.0, lb_s / eff_wall), 4)
    m_score = round(sum(1 for v in milestones.values() if v) / max(1, len(milestones)), 4)
    r_score = round(sum(1 for v in rubric.values() if v) / max(1, len(rubric)), 4)
    side = dict((portal_state.get("collateral_side_effects") or {}))
    if "total" not in side:
        side["total"] = sum(int(v) for v in side.values() if isinstance(v, (int, float)))
    joint = bool(all(role_passes.values()) and all(rubric.values()) and canary_passed)
    return {
        "task_id": task_id,
        "arena": meta["arena"],
        "variant": meta["variant"],
        "roles": list(meta["roles"]),
        "role_passes": role_passes,
        "passed_roles_count": sum(1 for v in role_passes.values() if v),
        "joint_pass": joint,
        "canary_passed": bool(canary_passed),
        "milestone_score": m_score,
        "milestone_checks": milestones,
        "final_rubric_score": r_score,
        "final_rubric_checks": rubric,
        "efficiency": {
            "critical_section_lower_bound_s": lb_s,
            "actual_wall_s": round(eff_wall, 2),
            "efficiency_score": eff_ratio,
            "effective_throughput_score": round(r_score * eff_ratio, 4),
        },
        "collateral_side_effects": side,
        "diagnostics": diagnostics,
    }


def grade_arena_a(task_id: str, workspace: Path, portal_state: dict, wall_s: float) -> dict:
    meta = TA_BY_ID[task_id]
    is_fx = bool(meta.get("fx_restatement_canary"))
    exp_rev = 2660.0 if is_fx else 2840.0
    exp_cost = 1100.0
    exp_ops = 455.0
    exp_noi = exp_rev - exp_cost - exp_ops  # 1105.0 or 1285.0
    exp_pipe = 959.5 if is_fx else 935.0
    exp_code = "QBR-2026-Q3-RESTATED" if is_fx else "QBR-2026-Q3-GOLD"

    xlsx_p = workspace / "Q3_Operating_Model.xlsx"
    pptx_p = workspace / "Q3_Executive_Deck.pptx"
    pdf_p = workspace / "exports/Q3_Executive_Deck.pdf"
    chart_p = workspace / "exports/ops_sla_chart.png"
    fin_j = workspace / "exports/fin_reconciliation.json"
    sales_md = workspace / "exports/regional_commentary.md"

    raw_wb = read_multisheet_xlsx(xlsx_p) if xlsx_p.is_file() else {}
    eval_wb = evaluate_xlsx_via_libreoffice(xlsx_p) if xlsx_p.is_file() else {}
    sum_raw = raw_wb.get("Summary", {})
    sum_ev = eval_wb.get("Summary", {})

    formulas_intact = all(
        bool((sum_raw.get(cell) or {}).get("formula"))
        for cell in ("B2", "B3", "B4", "B5", "B6")
    )
    v_rev = float((sum_ev.get("B2") or {}).get("value") or 0.0)
    v_cost = float((sum_ev.get("B3") or {}).get("value") or 0.0)
    v_ops = float((sum_ev.get("B4") or {}).get("value") or 0.0)
    v_noi = float((sum_ev.get("B5") or {}).get("value") or 0.0)
    v_pipe = float((sum_ev.get("B6") or {}).get("value") or 0.0)

    fin_ok = math.isclose(v_rev, exp_rev, abs_tol=0.25) and math.isclose(v_cost, exp_cost, abs_tol=0.25) and fin_j.is_file()
    chart_ok = False
    if chart_p.is_file():
        try:
            im = Image.open(chart_p)
            chart_ok = im.width >= 600 and im.height >= 340
        except Exception:
            pass
    ops_ok = math.isclose(v_ops, exp_ops, abs_tol=0.25) and chart_ok
    sales_ok = math.isclose(v_pipe, exp_pipe, abs_tol=0.25) and sales_md.is_file() and len(sales_md.read_text(encoding="utf-8", errors="ignore")) >= 40

    emails = portal_state.get("sent_emails") or []
    last_mail = emails[-1] if emails else {}
    pptx_txt, pptx_has_img = read_pptx_info(pptx_p)
    pptx_norm = pptx_txt.replace(",", "")
    deck_ok = (exp_code in pptx_txt) and (str(int(exp_noi)) in pptx_norm) and pptx_has_img and pdf_p.is_file() and pdf_p.stat().st_size > 800
    mail_fresh = (
        bool(emails)
        and last_mail.get("board_code") == exp_code
        and math.isclose(float(last_mail.get("net_operating_income_kusd") or -999), exp_noi, abs_tol=0.3)
        and math.isclose(float(last_mail.get("total_ops_cost_kusd") or -999), exp_ops, abs_tol=0.3)
        and math.isclose(float(last_mail.get("weighted_pipeline_kusd") or -999), exp_pipe, abs_tol=0.3)
        and last_mail.get("model_sha256_at_send") == sha256_file(xlsx_p)
    )
    exec_ok = deck_ok and mail_fresh and formulas_intact
    canary_ok = bool(formulas_intact and fin_ok and ops_ok and sales_ok and math.isclose(v_noi, exp_noi, abs_tol=0.3) and mail_fresh)

    exported_ids = {e.get("table_id") for e in (portal_state.get("exported_tables") or [])}
    milestones = {
        "M1_FIN_12_tables_exported": sum(1 for i in range(1, 13) if f"fin_m{i:02d}" in exported_ids) == 12,
        "M2_OPS_10_tables_and_chart": sum(1 for i in range(1, 11) if f"ops_w{i:02d}" in exported_ids) == 10 and chart_ok,
        "M3_SALES_8_territories_and_note": sum(1 for i in range(1, 9) if f"crm_r{i:02d}" in exported_ids) == 8 and sales_md.is_file(),
        "M4_EXEC_deck_and_email_dispatched": deck_ok and bool(emails),
    }
    rubric = {
        "R1_summary_cross_sheet_formulas_preserved": formulas_intact,
        "R2_finance_sheet_reconciled": fin_ok,
        "R3_ops_sheet_and_chart_reconciled": ops_ok,
        "R4_sales_pipeline_weighted_reconciled": sales_ok,
        "R5_exec_deck_pdf_and_fresh_email_canary": exec_ok and canary_ok,
    }
    role_passes = {"FIN": fin_ok and formulas_intact, "OPS": ops_ok and formulas_intact, "SALES": sales_ok and formulas_intact, "EXEC": exec_ok and canary_ok}
    return _wrap_4d_grade(task_id, role_passes, milestones, rubric, canary_ok, portal_state, wall_s, {
        "evaluated_summary": {"rev": v_rev, "cost": v_cost, "ops": v_ops, "noi": v_noi, "pipe": v_pipe},
        "expected_summary": {"rev": exp_rev, "cost": exp_cost, "ops": exp_ops, "noi": exp_noi, "pipe": exp_pipe, "board_code": exp_code},
        "formulas_intact": formulas_intact,
        "mail_count": len(emails),
    })


def grade_arena_b(task_id: str, workspace: Path, portal_state: dict, wall_s: float) -> dict:
    meta = TA_BY_ID[task_id]
    is_branch = bool(meta.get("branch_schema_race"))
    repo = workspace / "launch-repo"
    cms_db = workspace / "staging_data/cms.db"

    git_clean = False
    head_sha = ""
    if (repo / ".git").is_dir():
        st = subprocess.run(["git", "-c", "safe.directory=*", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout.strip()
        br = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        head_sha = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
        git_clean = (st == "" and br == "main")

    pages_ok = all(
        (repo / f"templates/{pg}.html").is_file() and 'data-launch-v4="ready"' in (repo / f"templates/{pg}.html").read_text(encoding="utf-8", errors="ignore")
        for pg in ("index", "pricing", "features", "enterprise", "changelog")
    )
    logic_ok = False
    lp = repo / "app_logic.json"
    if lp.is_file():
        try:
            lg = json.loads(lp.read_text(encoding="utf-8"))
            tax_ok = (int(lg.get("checkout_tax_bps", 0)) == 825) if is_branch else True
            logic_ok = math.isclose(float(lg.get("annual_multiplier", 0.0)), 0.80, abs_tol=1e-3) and lg.get("changelog_timezone") == "UTC" and tax_ok
        except Exception:
            pass
    fe_ok = pages_ok and logic_ok and git_clean

    svg_ok = (repo / "static/assets/nav_logo.svg").is_file() and 'viewBox="0 0 120 40"' in (repo / "static/assets/nav_logo.svg").read_text(encoding="utf-8", errors="ignore")
    assets_ok = False
    try:
        hb = Image.open(repo / "static/assets/hero_banner.png").convert("RGB")
        px = hb.getpixel((600, 300))
        cards_valid = all(Image.open(repo / f"static/assets/card_0{i}.png").size == (600, 400) for i in range(1, 5))
        assets_ok = hb.size == (1200, 600) and cards_valid and abs(px[0] - 14) <= 12 and abs(px[1] - 165) <= 12 and abs(px[2] - 233) <= 12
    except Exception:
        pass
    design_ok = svg_ok and assets_ok and git_clean

    cms_cnt = 0
    if cms_db.is_file():
        try:
            con = sqlite3.connect(str(cms_db))
            cms_cnt = con.execute("SELECT COUNT(*) FROM cms_articles WHERE published=1").fetchone()[0]
            con.close()
        except sqlite3.Error:
            pass
    cms_ok = (cms_cnt == 20)

    filed_codes = {str(i.get("bug_code") or "").strip().upper() for i in (portal_state.get("qa_issues") or []) if str(i.get("bug_code") or "").strip()}
    real_3 = {"BUG-ANNUAL-SIGN", "BUG-SVG-VIEWBOX", "BUG-CHANGELOG-TZ"}
    false_issues = sum(1 for i in (portal_state.get("qa_issues") or []) if str(i.get("bug_code") or "").strip() and str(i.get("bug_code") or "").strip().upper() not in real_3)
    if "collateral_side_effects" in portal_state and isinstance(portal_state["collateral_side_effects"], dict):
        portal_state = dict(portal_state)
        se = dict(portal_state["collateral_side_effects"])
        se["false_transient_issues"] = false_issues
        se["total"] = sum(int(v) for k, v in se.items() if k != "total" and isinstance(v, (int, float)))
        portal_state["collateral_side_effects"] = se
    signoff = portal_state.get("qa_signoff") or {}
    signoff_ok = (signoff.get("release_gate") == "LNCH-2026-V4" and bool(head_sha) and signoff.get("git_commit") == head_sha and len(set(signoff.get("verified_pages") or [])) == 5)
    qa_ok = real_3.issubset(filed_codes) and false_issues == 0 and signoff_ok and fe_ok and design_ok and cms_ok
    canary_ok = bool(qa_ok and int(portal_state.get("staging_redeploys", 0)) >= 1)

    milestones = {
        "M1_FE_templates_and_pricing_fixed": pages_ok and logic_ok,
        "M2_DESIGN_multi_size_assets_and_svg": svg_ok and assets_ok,
        "M3_CMS_20_articles_published": cms_ok,
        "M4_QA_3_seeded_defects_identified": real_3.issubset(filed_codes),
    }
    rubric = {
        "R1_git_main_clean_and_merged": git_clean,
        "R2_frontend_logic_and_5_pages": fe_ok,
        "R3_design_assets_and_viewbox": design_ok,
        "R4_cms_20_articles_bound": cms_ok,
        "R5_qa_zero_false_alarms_and_head_signoff_canary": canary_ok,
    }
    role_passes = {"FE": fe_ok, "DESIGN": design_ok, "CMS": cms_ok, "QA": canary_ok}
    return _wrap_4d_grade(task_id, role_passes, milestones, rubric, canary_ok, portal_state, wall_s, {
        "git_clean": git_clean,
        "head_sha": head_sha,
        "published_cms_count": cms_cnt,
        "filed_bug_codes": sorted(filed_codes),
        "false_transient_issues": false_issues,
    })


def grade_arena_c(task_id: str, workspace: Path, portal_state: dict, wall_s: float) -> dict:
    meta = TA_BY_ID[task_id]
    prof = str(meta.get("fault_profile", "triple_mask"))
    exp_inc = "INC-4401" if prof == "triple_mask" else "INC-4402"
    burst_metrics, _ = _evaluate_cluster_health(workspace, prof, burst_mult=1.35)

    fp_p = workspace / "forensics/db_fingerprint.json"
    fp_ok = False
    if fp_p.is_file():
        try:
            fpd = json.loads(fp_p.read_text(encoding="utf-8"))
            fp_ok = bool(fpd.get("sufficient_window")) and bool(fpd.get("samples"))
        except Exception:
            pass
    pollutions = int(((portal_state.get("collateral_side_effects") or {}).get("observation_pollutions", 0)))

    rca_p = workspace / "INC_Runbook_RCA.md"
    rca_txt = rca_p.read_text(encoding="utf-8", errors="ignore") if rca_p.is_file() else ""
    sec_ok = {}
    for sec in ("Forensics", "DB Mitigation", "App/Gateway Mitigation", "Infra/Storage Mitigation", "Canary Verification"):
        m = re.search(rf"## {re.escape(sec)}\s+(.+?)(?=\n## |\Z)", rca_txt, re.S)
        body = m.group(1).strip() if m else ""
        sec_ok[sec] = bool(body and "PENDING" not in body and len(body) >= 12)

    db_ok = bool(burst_metrics.get("db_ok")) and fp_ok and sec_ok["DB Mitigation"]
    app_ok = bool(burst_metrics.get("gateway_ok")) and sec_ok["App/Gateway Mitigation"]
    inf_key = "storage_ok" if prof == "triple_mask" else "probe_ok"
    infra_ok = bool(burst_metrics.get(inf_key)) and sec_ok["Infra/Storage Mitigation"]

    sp_list = portal_state.get("statuspage_updates") or []
    last_sp = sp_list[-1] if sp_list else {}
    sp_ok = (last_sp.get("incident_code") == exp_inc and str(last_sp.get("status", "")).upper() == "RESOLVED" and len(last_sp.get("root_causes") or []) >= 3)
    canary_replay = portal_state.get("canary_replay_result") or {}
    canary_ok = bool(
        burst_metrics["healthy"]
        and burst_metrics["p99_ms"] <= 85.0
        and burst_metrics["error_rate"] == 0.0
        and canary_replay.get("healthy") is True
        and pollutions == 0
        and fp_ok
    )
    ic_ok = canary_ok and sp_ok and sec_ok["Forensics"] and sec_ok["Canary Verification"]

    milestones = {
        "M1_DB_undisturbed_forensic_capture": fp_ok and pollutions == 0,
        "M2_DB_root_cause_remediated": bool(burst_metrics.get("db_ok")),
        "M3_APP_gateway_remediated": bool(burst_metrics.get("gateway_ok")),
        "M4_INFRA_storage_or_probe_remediated": bool(burst_metrics.get(inf_key)),
    }
    rubric = {
        "R1_zero_observation_pollution_and_forensics": fp_ok and pollutions == 0,
        "R2_all_three_masked_faults_resolved": bool(burst_metrics["healthy"]),
        "R3_canary_burst_replay_p99_under_85ms": canary_ok,
        "R4_collaborative_rca_all_5_sections_intact": all(sec_ok.values()),
        "R5_statuspage_resolved_with_3_root_causes": sp_ok,
    }
    role_passes = {"DB": db_ok and pollutions == 0, "APP": app_ok, "INFRA": infra_ok, "IC": ic_ok}
    return _wrap_4d_grade(task_id, role_passes, milestones, rubric, canary_ok, portal_state, wall_s, {
        "burst_canary_metrics": burst_metrics,
        "rca_sections_ok": sec_ok,
        "observation_pollutions": pollutions,
        "statuspage_count": len(sp_list),
    })


def _measure_lufs(media_path: Path) -> float | None:
    if not media_path.is_file():
        return None
    cp = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(media_path), "-filter_complex", "ebur128=framelog=verbose", "-f", "null", "-"],
        capture_output=True, text=True, timeout=45,
    )
    matches = re.findall(r"I:\s*(-?\d+\.\d+)\s*LUFS", cp.stderr)
    return float(matches[-1]) if matches else None


def grade_arena_d(task_id: str, workspace: Path, portal_state: dict, wall_s: float) -> dict:
    mlt_p = workspace / "master_episode.mlt"
    lt_p = workspace / "vfx/lower_third.png"
    wav_p = workspace / "audio/dialogue_ebu.wav"
    mp4_p = workspace / "exports/final_episode.mp4"
    mlt_txt = mlt_p.read_text(encoding="utf-8", errors="ignore") if mlt_p.is_file() else ""

    cut_ok = ('out="119"' in mlt_txt) and ("end_slate.mp4" in mlt_txt) and ('out="47"' in mlt_txt)
    vfx_img_ok = False
    if lt_p.is_file():
        try:
            im = Image.open(lt_p).convert("RGBA")
            px_bar = im.getpixel((320, 310))
            px_top = im.getpixel((320, 100))
            vfx_img_ok = im.size == (640, 360) and px_top[3] == 0 and abs(px_bar[0] - 20) <= 5 and abs(px_bar[1] - 150) <= 5 and abs(px_bar[2] - 168) <= 5 and px_bar[3] >= 240
        except Exception:
            pass
    vfx_ok = vfx_img_ok and ("lower_third.png" in mlt_txt)

    wav_lufs = _measure_lufs(wav_p)
    audio_ok = (wav_lufs is not None and -23.45 <= wav_lufs <= -22.55) and ("dialogue_ebu.wav" in mlt_txt)

    mp4_frames = 0
    mp4_bar_ok = False
    mp4_lufs = _measure_lufs(mp4_p)
    if mp4_p.is_file():
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(mp4_p)],
            capture_output=True, text=True, timeout=30,
        )
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            mp4_frames = int(st.get("nb_read_frames") or 0)
            wh_ok = (int(st.get("width", 0)), int(st.get("height", 0))) == (640, 360)
        except Exception:
            wh_ok = False
        with tempfile.TemporaryDirectory() as tmp:
            fr_p = Path(tmp) / "f.png"
            subprocess.run(["ffmpeg", "-y", "-ss", "2.0", "-i", str(mp4_p), "-frames:v", "1", str(fr_p)], capture_output=True, timeout=20)
            if fr_p.is_file() and wh_ok:
                px = Image.open(fr_p).convert("RGB").getpixel((320, 310))
                mp4_bar_ok = abs(px[0] - 20) <= 18 and abs(px[1] - 150) <= 18 and abs(px[2] - 168) <= 18

    uploads = portal_state.get("cms_uploads") or []
    last_up = uploads[-1] if uploads else {}
    premature = int(((portal_state.get("collateral_side_effects") or {}).get("premature_upload_snapshots", 0)))
    canary_ok = bool(
        118 <= mp4_frames <= 122
        and mp4_bar_ok
        and (mp4_lufs is not None and -23.6 <= mp4_lufs <= -22.4)
        and last_up.get("release_tag") == "EP-2026-MASTER"
        and last_up.get("all_tracks_present_at_upload") is True
        and last_up.get("mp4_sha256") == sha256_file(mp4_p)
        and premature == 0
    )
    pub_ok = canary_ok and cut_ok and vfx_ok and audio_ok

    milestones = {
        "M1_CUT_120_frames_conformed": cut_ok,
        "M2_VFX_lower_third_rendered_and_wired": vfx_ok,
        "M3_AUDIO_ebu_r128_calibrated_and_wired": audio_ok,
        "M4_PUB_master_encoded_and_uploaded": bool(uploads) and mp4_p.is_file(),
    }
    rubric = {
        "R1_mlt_contains_all_3_tracks": cut_ok and vfx_ok and audio_ok,
        "R2_mp4_120_frames_and_lower_third_pixels": 118 <= mp4_frames <= 122 and mp4_bar_ok,
        "R3_mp4_integrated_loudness_ebu": mp4_lufs is not None and -23.6 <= mp4_lufs <= -22.4,
        "R4_cms_upload_matches_final_master_canary": canary_ok,
    }
    role_passes = {"CUT": cut_ok, "VFX": vfx_ok, "AUDIO": audio_ok, "PUB": pub_ok}
    return _wrap_4d_grade(task_id, role_passes, milestones, rubric, canary_ok, portal_state, wall_s, {
        "wav_lufs": wav_lufs,
        "mp4_lufs": mp4_lufs,
        "mp4_frames": mp4_frames,
        "mp4_bar_ok": mp4_bar_ok,
        "premature_uploads": premature,
    })


def grade_arena_e(task_id: str, workspace: Path, portal_state: dict, wall_s: float) -> dict:
    fc_p = workspace / "turbine_review.FCStd"
    bom_p = workspace / "Engineering_Review_BOM.xlsx"
    cert_p = workspace / "exports/cae_cert.json"
    sign_p = workspace / "exports/review_signoff.json"

    fc_info = {"bore": 0.0, "rod": 0.0, "hub": 0.0, "inter": 999.0, "c_cm3": 0.0, "r_cm3": 0.0}
    if fc_p.is_file():
        code = (
            "import FreeCAD as App, json\n"
            f"doc = App.openDocument({str(fc_p)!r})\n"
            "c = doc.getObject('Casing'); r = doc.getObject('Rotor'); ms = doc.getObject('DesignSpec')\n"
            "print('FC_GRADE:' + json.dumps({'bore': float(ms.get('B2')), 'rod': float(ms.get('B3')), 'hub': float(ms.get('B4')), 'inter': c.Shape.common(r.Shape).Volume, 'c_cm3': c.Shape.Volume/1000.0, 'r_cm3': r.Shape.Volume/1000.0}))\n"
        )
        cp = subprocess.run(["freecadcmd", "-c", code], capture_output=True, text=True, timeout=60)
        for ln in (cp.stdout + "\n" + cp.stderr).splitlines():
            if "FC_GRADE:" in ln:
                fc_info = json.loads(ln.split("FC_GRADE:", 1)[1])

    housing_ok = math.isclose(fc_info["bore"], 84.0, abs_tol=0.05) and (workspace / "exports/casing.step").is_file()
    rotor_ok = math.isclose(fc_info["rod"], 83.10, abs_tol=0.05) and fc_info["hub"] >= 14.0 and (workspace / "exports/rotor.step").is_file()

    cert = json.loads(cert_p.read_text(encoding="utf-8")) if cert_p.is_file() else {}
    fc_sha = sha256_file(fc_p)
    cae_ok = (
        cert.get("review_code") == "ENG-REV-84"
        and cert.get("passed") is True
        and float(cert.get("safety_factor") or 0.0) >= 1.85
        and cert.get("fcstd_sha256") == fc_sha
    )

    raw_bom = read_multisheet_xlsx(bom_p) if bom_p.is_file() else {}
    ev_bom = evaluate_xlsx_via_libreoffice(bom_p) if bom_p.is_file() else {}
    sum_raw = raw_bom.get("Summary", {})
    sum_ev = ev_bom.get("Summary", {})
    bom_formulas = all(bool((sum_raw.get(c) or {}).get("formula")) for c in ("B2", "B3", "B4"))
    exp_vol = fc_info["c_cm3"] + fc_info["r_cm3"]
    exp_mass = exp_vol * 4.43
    exp_cost = exp_mass * 0.85
    v_mass = float((sum_ev.get("B3") or {}).get("value") or 0.0)
    v_cost = float((sum_ev.get("B4") or {}).get("value") or 0.0)
    sign = json.loads(sign_p.read_text(encoding="utf-8")) if sign_p.is_file() else {}
    bom_ok = (
        bom_formulas
        and exp_vol > 10.0
        and math.isclose(v_mass, exp_mass, rel_tol=0.01, abs_tol=1.0)
        and math.isclose(v_cost, exp_cost, rel_tol=0.01, abs_tol=1.0)
        and sign.get("review_code") == "ENG-REV-84"
    )
    canary_ok = bool(housing_ok and rotor_ok and fc_info["inter"] < 1e-3 and cae_ok and bom_ok)

    milestones = {
        "M1_HOUSING_84mm_and_step": housing_ok,
        "M2_ROTOR_83_1mm_hub_and_step": rotor_ok,
        "M3_CAE_certificate_passed": bool(cert.get("passed")),
        "M4_BOM_formulas_and_signoff": bom_ok,
    }
    rubric = {
        "R1_zero_interference_and_radial_gap_in_band": fc_info["inter"] < 1e-3 and 0.35 <= (fc_info["bore"] - fc_info["rod"]) / 2.0 <= 0.55,
        "R2_exclusive_cae_cert_matches_final_fcstd": cae_ok,
        "R3_bom_live_formulas_match_cad_volumes": bom_ok,
        "R4_end_to_end_engineering_canary": canary_ok,
    }
    role_passes = {"HOUSING": housing_ok, "ROTOR": rotor_ok, "CAE": cae_ok, "BOM": bom_ok and canary_ok}
    return _wrap_4d_grade(task_id, role_passes, milestones, rubric, canary_ok, portal_state, wall_s, {
        "freecad_geometry": fc_info,
        "expected_mass_g": round(exp_mass, 2),
        "evaluated_bom_mass_g": round(v_mass, 2),
        "cae_cert_sha_match": cert.get("fcstd_sha256") == fc_sha,
    })


def grade_case(task_id: str, workspace: Path, portal_state: dict, wall_seconds: float = 180.0) -> dict:
    arena = TA_BY_ID[task_id]["arena"]
    if arena == "A_quarterly_business_review":
        return grade_arena_a(task_id, workspace, portal_state, wall_seconds)
    if arena == "B_product_launch_day":
        return grade_arena_b(task_id, workspace, portal_state, wall_seconds)
    if arena == "C_live_incident_war_room":
        return grade_arena_c(task_id, workspace, portal_state, wall_seconds)
    if arena == "D_video_production_studio":
        return grade_arena_d(task_id, workspace, portal_state, wall_seconds)
    if arena == "E_engineering_cad_cae_review":
        return grade_arena_e(task_id, workspace, portal_state, wall_seconds)
    raise ValueError(arena)
