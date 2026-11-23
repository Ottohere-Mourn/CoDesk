"""Registry and container CLI entrypoints for rb_osw2_synth_v3 (RBS3-01..RBS3-05)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from typing import Any

from tasks.rb_osw2_synth_v3 import (
    rbs3_01_zerospoiler_popovers_recreation,
    rbs3_02_cdp_live_frames_vs_8scene_sweep,
    rbs3_03_vectorforge_single_mdi_coupled,
    rbs3_04_icu_sso_nomogram_soffice,
    rbs3_05_ircam_firmware_gateway_calc,
)
from tasks.rb_osw2_synth_v3.common import read_json_safe, write_json

RBS3_MODULES = {
    m.TASK_ID: m
    for m in (
        rbs3_01_zerospoiler_popovers_recreation,
        rbs3_02_cdp_live_frames_vs_8scene_sweep,
        rbs3_03_vectorforge_single_mdi_coupled,
        rbs3_04_icu_sso_nomogram_soffice,
        rbs3_05_ircam_firmware_gateway_calc,
    )
}

RBS3_CATALOG: list[dict[str, Any]] = [m.META for m in RBS3_MODULES.values()]
RBS3_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in RBS3_CATALOG}


def _resolve_workspace_map(mod: Any, ws_root: Path) -> dict[str, Path]:
    ra, rb = mod.META["roles"]
    if mod.META["workspace_mode"] == "isolated":
        return {ra: ws_root / ra, rb: ws_root / rb}
    shared = ws_root / "shared"
    return {ra: shared, rb: shared}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for cname in ("build", "serve", "boot_apps", "solve_role", "careful_conc", "sim_contention", "grade"):
        p = sub.add_parser(cname)
        p.add_argument("--task", required=True)
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
        elif cname == "sim_contention":
            p.add_argument("--state-dir", type=Path, required=True)
        elif cname == "grade":
            p.add_argument("--state-file", type=Path, required=True)
            p.add_argument("--wall-seconds", type=float, default=0.0)
            p.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    mod = RBS3_MODULES[args.task]
    port = int(mod.META["portal_port"])
    ws_map = _resolve_workspace_map(mod, args.workspace_root)

    if args.cmd == "build":
        mod.build_pristine(ws_map, args.tickets_root)
        return 0
    if args.cmd == "serve":
        mod.run_portal_service(args.port, ws_map, args.state_dir, args.boot_file)
        return 0
    if args.cmd == "boot_apps":
        mod.boot_desktop_apps(ws_map, args.state_dir)
        return 0
    if args.cmd == "solve_role":
        mod.solve_role(args.role, ws_map, port, careful_conc=False)
        return 0
    if args.cmd == "careful_conc":
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
        mod.simulate_contention_probe(ws_map, port, args.state_dir)
        return 0
    if args.cmd == "grade":
        res = mod.grade(ws_map, read_json_safe(args.state_file), args.wall_seconds)
        write_json(args.out, res)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
