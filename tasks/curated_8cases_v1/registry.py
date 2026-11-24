"""Unified registry, hardened grading wrappers, and container CLI for the curated 8-case suite.

Selected high-quality cases:
  - RBS3-04: No-CDP ICU Unit Toggle, 16-Bed VTach Waveform & Single soffice.bin Coupled Fluid Ledger
  - RBS3-05: No-CDP Hardware/Bus Portal, 8-Zone IRCam Hotspots, Live :19515 Gateway & Calc TDP BOM
  - RBS3-02: Singleton :9222 4-Breakpoint Pixel-Verified FinOps QA vs. 8-Scene Fullscreen Sweep
  - RBS2-06: MailDesk Visual Blackout Heatmap & RFC-5545 .ics Scheduling vs. LibreOffice Calc SLA
  - RBS-06:  CiteVault SQLite & BibTeX Dedup + Single soffice.bin (Writer + Calc) Meta-Analysis
  - RBS3-01: Zero-Spoiler 5-Surface Recreation: Autohide F10 Popovers & Twin 3-Tab Preferences
  - EC-01:   Multi-Entity M&A Due-Diligence Data Room, ~/Downloads CSV Overwrite & Leverage Covenant
  - EC-03:   1U Sheet-Metal Enclosure FreeCAD B-Rep, Inkscape Prepress & Thermal/EMI Preload Coupling
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import time
from typing import Any
import xml.etree.ElementTree as ET

from tasks.exam_contention_v1 import ec01_ma_dataroom_calc, ec03_enclosure_cad_emi
from tasks.exam_contention_v1.common import extract_pdf_text
from tasks.rb_osw2_synth_v1 import rbs06_citevault_bibtex_soffice
from tasks.rb_osw2_synth_v2 import rbs2_06_maildesk_ics_vs_calc_contracts
from tasks.rb_osw2_synth_v3 import (
    rbs3_01_zerospoiler_popovers_recreation,
    rbs3_02_cdp_live_frames_vs_8scene_sweep,
    rbs3_04_icu_sso_nomogram_soffice,
    rbs3_05_ircam_firmware_gateway_calc,
)
from tasks.rb_osw2_synth_v3.common import read_json_safe, write_json

CURATED_8_IDS: tuple[str, ...] = (
    "RBS3-04",
    "RBS3-05",
    "RBS3-02",
    "RBS2-06",
    "RBS-06",
    "RBS3-01",
    "EC-01",
    "EC-03",
)

CURATED_8_MODULES: dict[str, Any] = {
    "RBS3-04": rbs3_04_icu_sso_nomogram_soffice,
    "RBS3-05": rbs3_05_ircam_firmware_gateway_calc,
    "RBS3-02": rbs3_02_cdp_live_frames_vs_8scene_sweep,
    "RBS2-06": rbs2_06_maildesk_ics_vs_calc_contracts,
    "RBS-06": rbs06_citevault_bibtex_soffice,
    "RBS3-01": rbs3_01_zerospoiler_popovers_recreation,
    "EC-01": ec01_ma_dataroom_calc,
    "EC-03": ec03_enclosure_cad_emi,
}

_SOURCE_PATHS: dict[str, str] = {
    "RBS3-04": "tasks/rb_osw2_synth_v3/rbs3_04_icu_sso_nomogram_soffice.py",
    "RBS3-05": "tasks/rb_osw2_synth_v3/rbs3_05_ircam_firmware_gateway_calc.py",
    "RBS3-02": "tasks/rb_osw2_synth_v3/rbs3_02_cdp_live_frames_vs_8scene_sweep.py",
    "RBS2-06": "tasks/rb_osw2_synth_v2/rbs2_06_maildesk_ics_vs_calc_contracts.py",
    "RBS-06": "tasks/rb_osw2_synth_v1/rbs06_citevault_bibtex_soffice.py",
    "RBS3-01": "tasks/rb_osw2_synth_v3/rbs3_01_zerospoiler_popovers_recreation.py",
    "EC-01": "tasks/exam_contention_v1/ec01_ma_dataroom_calc.py",
    "EC-03": "tasks/exam_contention_v1/ec03_enclosure_cad_emi.py",
}

_ZH_TITLES: dict[str, str] = {
    "RBS3-04": "无 CDP ICU 互斥单位门户 + 16 床室速波形 + Calc/Writer [1900, 1908] mL 耦合",
    "RBS3-05": "无 CDP 硬件合规门户 + 8 区热像 + :19515 CAN-FD 守护进程 + Calc [190.0, 190.8] W 耦合",
    "RBS3-02": "单实例 :9222 4 断点色带截屏 QA vs 8 幕全屏可见性扫描录制",
    "RBS2-06": "MailDesk 拉闸热力图与 RFC-5545 .ics 排期 vs 单实例 Calc 供应商 SLA 核算",
    "RBS-06": "CiteVault SQLite + BibTeX 勘误去重 vs 单进程 Writer+Calc 荟萃分析",
    "RBS3-01": "零剧透 5 表面探索复刻：SpectrumPad 音频 DSP vs PacketForge 抓包台",
    "EC-01": "跨国并购尽调数据室、同名 CSV 导出互覆与 [3.03, 3.09]x 净杠杆契约",
    "EC-03": "1U 机箱三维钣金开孔、EMC 屏蔽与丝印制版耦合",
}

DEFAULT_LOOP_SAFETY_CUA_CEILING = 150


def _normalize_curated_meta(task_id: str) -> dict[str, Any]:
    mod = CURATED_8_MODULES[task_id]
    meta = copy.deepcopy(mod.META)
    is_ec1 = task_id.startswith("EC-")
    meta["id"] = task_id
    meta["title_zh"] = _ZH_TITLES[task_id]
    meta["source_file"] = _SOURCE_PATHS[task_id]
    meta["runner_family"] = "ec_v1_astra_desktop" if is_ec1 else "ec_v2_multi_driver_desktop"
    meta["workspace_mode"] = str(meta.get("workspace_mode") or "shared")
    meta["max_cua_calls"] = max(DEFAULT_LOOP_SAFETY_CUA_CEILING, int(meta.get("max_cua_calls") or 0))
    meta["share_desk_pid"] = bool(task_id == "RBS3-05")
    meta["absent_peer_reference_fill_in_isolated"] = bool(meta["workspace_mode"] == "shared")
    if is_ec1 and "open_gui_docs" not in meta:
        doc_p = str(meta.get("open_gui_doc") or "")
        tag = str(meta.get("open_gui_unsaved_tag") or "")
        kind = "writer" if doc_p.endswith(".odt") else "calc"
        meta["open_gui_docs"] = ((doc_p, tag, kind),) if doc_p else ()
    return meta


CURATED_8_CATALOG: list[dict[str, Any]] = [_normalize_curated_meta(tid) for tid in CURATED_8_IDS]
CURATED_8_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in CURATED_8_CATALOG}


def resolve_workspace_map(task_id: str, ws_root: Path) -> dict[str, Path]:
    meta = CURATED_8_BY_ID[task_id]
    ra, rb = meta["roles"]
    if meta["workspace_mode"] == "isolated":
        return {ra: ws_root / ra, rb: ws_root / rb}
    shared = ws_root / "shared"
    return {ra: shared, rb: shared}


def verify_svg_group_layers_non_empty(svg_path: Path, required_group_ids: tuple[str, ...]) -> list[str]:
    """Ensure required SVG <g id=...> layers exist AND contain non-empty geometry or text."""
    if not svg_path.is_file():
        return [f"{svg_path.name} missing"]
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8", errors="replace"))
    except ET.ParseError as exc:
        return [f"{svg_path.name} XML parse error: {exc}"]

    by_id: dict[str, ET.Element] = {}
    for elem in root.iter():
        eid = elem.attrib.get("id")
        if eid:
            by_id[eid] = elem

    errs: list[str] = []
    for gid in required_group_ids:
        node = by_id.get(gid)
        if node is None:
            errs.append(f"{svg_path.name} missing #{gid}")
            continue
        has_children = len(list(node)) > 0
        has_text = bool("".join(node.itertext()).strip())
        if not (has_children or has_text):
            errs.append(f"{svg_path.name} layer #{gid} is empty (no child shapes or text)")
    return errs


def grade_curated_case(
    task_id: str,
    ws_root: Path,
    service_state: dict[str, Any],
    wall_seconds: float,
) -> dict[str, Any]:
    """Unified grading entrypoint applying review-hardened checks on EC-01 and EC-03."""
    mod = CURATED_8_MODULES[task_id]
    ws_map = resolve_workspace_map(task_id, ws_root)
    if task_id.startswith("EC-"):
        shared_ws = next(iter(ws_map.values()))
        res = mod.grade(shared_ws, service_state, wall_seconds)
        if task_id == "EC-01":
            tax_pdf = shared_ws / "deal_model" / "Tax_Treasury_Pack.pdf"
            if tax_pdf.is_file() and tax_pdf.stat().st_size > 1000:
                t_txt = extract_pdf_text(tax_pdf).replace(",", "")
                if ec01_ma_dataroom_calc.TAX_VDR_SEAL not in t_txt:
                    msg = "Tax_Treasury_Pack.pdf missing VDR_Tax_Attestation_Seal (TAX_VDR_SEAL)"
                    if msg not in res["errors_b"]:
                        res["errors_b"].append(msg)
                        res["pass_b"] = False
                        res["joint_pass"] = False
        elif task_id == "EC-03":
            svg_p = shared_ws / "enclosure_revC" / "front_bezel_silkscreen.svg"
            svg_errs = verify_svg_group_layers_non_empty(
                svg_p,
                ("iec-emc-class-a-badge", "port-legend-qsfp", "thermal-airflow-notice"),
            )
            for msg in svg_errs:
                if msg not in res["errors_b"]:
                    res["errors_b"].append(msg)
            if svg_errs:
                res["pass_b"] = False
                res["joint_pass"] = False
        res.setdefault("score_a", 1.0 if res["pass_a"] else 0.0)
        res.setdefault("score_b", 1.0 if res["pass_b"] else 0.0)
        res.setdefault("mean_score", round(0.5 * (float(res["score_a"]) + float(res["score_b"])), 4))
        return res
    return mod.grade(ws_map, service_state, wall_seconds)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cname in ("build", "serve", "boot_apps", "solve_role", "careful_conc", "sim_contention", "grade"):
        p = sub.add_parser(cname)
        p.add_argument("--task", required=True, choices=CURATED_8_IDS)
        p.add_argument("--workspace-root", type=Path, required=True)
        if cname == "build":
            p.add_argument("--tickets-root", type=Path, required=True)
        elif cname == "serve":
            p.add_argument("--port", type=int, required=True)
            p.add_argument("--state-dir", type=Path, required=True)
            p.add_argument("--boot-file", type=Path, required=True)
        elif cname == "boot_apps":
            p.add_argument("--state-dir", type=Path, required=True)
        elif cname == "solve_role":
            p.add_argument("--role", required=True)
            p.add_argument("--careful-conc", action="store_true")
        elif cname == "sim_contention":
            p.add_argument("--state-dir", type=Path, required=True)
        elif cname == "grade":
            p.add_argument("--state-file", type=Path, required=True)
            p.add_argument("--wall-seconds", type=float, default=0.0)
            p.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    tid = args.task
    mod = CURATED_8_MODULES[tid]
    meta = CURATED_8_BY_ID[tid]
    port = int(meta["portal_port"])
    ws_map = resolve_workspace_map(tid, args.workspace_root)
    is_ec1 = tid.startswith("EC-")
    shared_ws = next(iter(ws_map.values()))

    if args.cmd == "build":
        if is_ec1:
            shared_ws.mkdir(parents=True, exist_ok=True)
            mod.build_pristine(shared_ws, args.tickets_root)
        else:
            mod.build_pristine(ws_map, args.tickets_root)
        return 0
    if args.cmd == "serve":
        if is_ec1:
            mod.run_portal_service(args.port, shared_ws, args.state_dir, args.boot_file)
        else:
            mod.run_portal_service(args.port, ws_map, args.state_dir, args.boot_file)
        return 0
    if args.cmd == "boot_apps":
        if hasattr(mod, "boot_desktop_apps"):
            mod.boot_desktop_apps(ws_map, args.state_dir)
        return 0
    if args.cmd == "solve_role":
        if is_ec1:
            mod.solve_role(args.role, shared_ws, port, careful_conc=args.careful_conc)
        else:
            mod.solve_role(args.role, ws_map, port, careful_conc=args.careful_conc)
        return 0
    if args.cmd == "careful_conc":
        ra, rb = meta["roles"]
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            if is_ec1:
                fa = pool.submit(mod.solve_role, ra, shared_ws, port, True)
                fb = pool.submit(mod.solve_role, rb, shared_ws, port, True)
            else:
                fa = pool.submit(mod.solve_role, ra, ws_map, port, True)
                fb = pool.submit(mod.solve_role, rb, ws_map, port, True)
            fa.result()
            fb.result()
        print("CAREFUL_CONC_JSON:" + json.dumps({"ok": True, "elapsed_s": round(time.monotonic() - t0, 2)}), flush=True)
        return 0
    if args.cmd == "sim_contention":
        if is_ec1:
            mod.simulate_naive_race(shared_ws, port)
        else:
            mod.simulate_contention_probe(ws_map, port, args.state_dir)
        return 0
    if args.cmd == "grade":
        res = grade_curated_case(tid, args.workspace_root, read_json_safe(args.state_file), args.wall_seconds)
        write_json(args.out, res)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
