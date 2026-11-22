"""Candidate pool & curated top-5 registry + container CLI entrypoints for exam_contention_v2."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from typing import Any

from tasks.exam_contention_v2 import (
    c01_cdp_responsive_storyboard,
    c02_gtk_qt_recreation_hotkeys,
    c03_canvas_drag_zorder_gamut,
    c04_gimp_singleton_prepress,
    c05_broadcast_scope_isolated,
    c06_impress_calc_actuarial,
    c07_oncology_ehr_writer,
    c08_enclosure_freecad_plm,
    c09_fintech_git_port_recon,
)
from tasks.exam_contention_v2.common import read_json_safe, write_json

CANDIDATE_MODULES = {
    m.TASK_ID: m
    for m in (
        c01_cdp_responsive_storyboard,
        c02_gtk_qt_recreation_hotkeys,
        c03_canvas_drag_zorder_gamut,
        c04_gimp_singleton_prepress,
        c05_broadcast_scope_isolated,
        c06_impress_calc_actuarial,
        c07_oncology_ehr_writer,
        c08_enclosure_freecad_plm,
        c09_fintech_git_port_recon,
    )
}

CANDIDATE_POOL_CATALOG: list[dict[str, Any]] = [m.META for m in CANDIDATE_MODULES.values()]
EC2_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in CANDIDATE_POOL_CATALOG}

# Empirically selected top-5 retained cases from the 9-candidate Stage-1 broad search (2026-11-22):
#   - Track 1 (Isolated-Workspace Shared-Screen): EC2-C01, EC2-C03
#   - Track 2 (Shared-Process/Session/Artifact):  EC2-C06, EC2-C07, EC2-C08
RETAINED_TOP5_IDS: tuple[str, ...] = (
    "EC2-C01",
    "EC2-C03",
    "EC2-C06",
    "EC2-C07",
    "EC2-C08",
)

RETAINED_TOP5_CATALOG: list[dict[str, Any]] = [EC2_BY_ID[tid] for tid in RETAINED_TOP5_IDS]
FILTERED_OUT_CANDIDATE_IDS: tuple[str, ...] = tuple(
    m["id"] for m in CANDIDATE_POOL_CATALOG if m["id"] not in RETAINED_TOP5_IDS
)


def _resolve_workspace_map(mod: Any, ws_root: Path) -> dict[str, Path]:
    ra, rb = mod.META["roles"]
    if mod.META["workspace_mode"] == "isolated":
        return {ra: ws_root / ra, rb: ws_root / rb}
    shared = ws_root / "shared"
    return {ra: shared, rb: shared}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build")
    p_b.add_argument("--task", required=True)
    p_b.add_argument("--workspace-root", type=Path, required=True)
    p_b.add_argument("--tickets-root", type=Path, required=True)

    p_s = sub.add_parser("serve")
    p_s.add_argument("--task", required=True)
    p_s.add_argument("--port", type=int, required=True)
    p_s.add_argument("--workspace-root", type=Path, required=True)
    p_s.add_argument("--state-dir", type=Path, required=True)
    p_s.add_argument("--boot-file", type=Path, required=True)

    p_ba = sub.add_parser("boot_apps")
    p_ba.add_argument("--task", required=True)
    p_ba.add_argument("--workspace-root", type=Path, required=True)
    p_ba.add_argument("--state-dir", type=Path, required=True)

    p_sr = sub.add_parser("solve_role")
    p_sr.add_argument("--task", required=True)
    p_sr.add_argument("--role", required=True)
    p_sr.add_argument("--workspace-root", type=Path, required=True)

    p_cc = sub.add_parser("careful_conc")
    p_cc.add_argument("--task", required=True)
    p_cc.add_argument("--workspace-root", type=Path, required=True)

    p_sc = sub.add_parser("sim_contention")
    p_sc.add_argument("--task", required=True)
    p_sc.add_argument("--workspace-root", type=Path, required=True)
    p_sc.add_argument("--state-dir", type=Path, required=True)

    p_g = sub.add_parser("grade")
    p_g.add_argument("--task", required=True)
    p_g.add_argument("--workspace-root", type=Path, required=True)
    p_g.add_argument("--state-file", type=Path, required=True)
    p_g.add_argument("--wall-seconds", type=float, default=0.0)
    p_g.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    mod = CANDIDATE_MODULES[args.task]
    port = int(mod.META["portal_port"])

    if args.cmd == "build":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        mod.build_pristine(ws_map, args.tickets_root)
        return 0
    if args.cmd == "serve":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        mod.run_portal_service(args.port, ws_map, args.state_dir, args.boot_file)
        return 0
    if args.cmd == "boot_apps":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        mod.boot_desktop_apps(ws_map, args.state_dir)
        return 0
    if args.cmd == "solve_role":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        mod.solve_role(args.role, ws_map, port, careful_conc=False)
        return 0
    if args.cmd == "careful_conc":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        ra, rb = mod.META["roles"]
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(mod.solve_role, ra, ws_map, port, True)
            fb = pool.submit(mod.solve_role, rb, ws_map, port, True)
            fa.result()
            fb.result()
        print("CAREFUL_CONC_JSON:" + json.dumps({"ok": True, "elapsed_s": round(time.monotonic() - t0, 2)}), flush=True)
        return 0
    if args.cmd == "sim_contention":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        mod.simulate_contention_probe(ws_map, port, args.state_dir)
        return 0
    if args.cmd == "grade":
        ws_map = _resolve_workspace_map(mod, args.workspace_root)
        sstate = read_json_safe(args.state_file)
        res = mod.grade(ws_map, sstate, args.wall_seconds)
        write_json(args.out, res)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
