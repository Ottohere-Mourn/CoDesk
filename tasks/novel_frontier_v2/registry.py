"""20-candidate authentic real-software benchmark registry & container CLI entrypoints for novel_frontier_v2."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from typing import Any

from tasks.novel_frontier_v2 import (
    nf2_01_azerty_horology_patent_vibrometry,
    nf2_02_serviceworker_cache_finops_chaos,
    nf2_03_indexeddb_versionchange_clinical_adam,
    nf2_04_sharedworker_lng_charter_euets,
    nf2_05_qtassistant_arinc429_flight_calc,
    nf2_06_gimp_singleton_conservation_multispectral,
    nf2_07_inkscape_singleton_opc_microfluidics,
    nf2_08_x11_clipboard_pki_ceremony_sbom,
    nf2_09_print_modal_acoustics_sox_writer,
    nf2_10_qgis_live_bathymetry_cathodic_calc,
    nf2_11_blender_vse_broadcast_nle_ebur128,
    nf2_12_freecad_cubesat_mass_cg_coupled,
    nf2_13_qgis_spatialite_feeder_hosting_coupled,
    nf2_14_git_barerepo_frtb_cva_coupled,
    nf2_15_qtdesigner_linguist_etcs_rail_coupled,
    nf2_16_sqlite_wal_trigger_tpn_pharmacy,
    nf2_17_inkscape_pid_hydrogen_psv_coupled,
    nf2_18_gimp_shared_xcf_gmp_blister_coupled,
    nf2_19_graphviz_fab_upw_turnaround_coupled,
    nf2_20_blender_3d_gantry_mezzanine_coupled,
)
from tasks.novel_frontier_v2.common import read_json_safe, write_json

ALL_20_MODULES = (
    nf2_01_azerty_horology_patent_vibrometry,
    nf2_02_serviceworker_cache_finops_chaos,
    nf2_03_indexeddb_versionchange_clinical_adam,
    nf2_04_sharedworker_lng_charter_euets,
    nf2_05_qtassistant_arinc429_flight_calc,
    nf2_06_gimp_singleton_conservation_multispectral,
    nf2_07_inkscape_singleton_opc_microfluidics,
    nf2_08_x11_clipboard_pki_ceremony_sbom,
    nf2_09_print_modal_acoustics_sox_writer,
    nf2_10_qgis_live_bathymetry_cathodic_calc,
    nf2_11_blender_vse_broadcast_nle_ebur128,
    nf2_12_freecad_cubesat_mass_cg_coupled,
    nf2_13_qgis_spatialite_feeder_hosting_coupled,
    nf2_14_git_barerepo_frtb_cva_coupled,
    nf2_15_qtdesigner_linguist_etcs_rail_coupled,
    nf2_16_sqlite_wal_trigger_tpn_pharmacy,
    nf2_17_inkscape_pid_hydrogen_psv_coupled,
    nf2_18_gimp_shared_xcf_gmp_blister_coupled,
    nf2_19_graphviz_fab_upw_turnaround_coupled,
    nf2_20_blender_3d_gantry_mezzanine_coupled,
)

CANDIDATE_MODULES: dict[str, Any] = {m.TASK_ID: m for m in ALL_20_MODULES}
ALL_20_CATALOG: list[dict[str, Any]] = [m.META for m in ALL_20_MODULES]
NF2_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in ALL_20_CATALOG}

# Retained Top-5 orthogonal real-software contention cases (NF2-05 promoted over saturated Git-only NF2-14)
RETAINED_TOP5_IDS: tuple[str, ...] = ("NF2-05", "NF2-11", "NF2-12", "NF2-13", "NF2-15")
RETAINED_TOP5_CATALOG: list[dict[str, Any]] = [NF2_BY_ID[tid] for tid in RETAINED_TOP5_IDS]


def _resolve_workspace_map(mod: Any, ws_root: Path) -> dict[str, Path]:
    ra, rb = mod.META["roles"]
    m = {ra: ws_root / ra, rb: ws_root / rb}
    if mod.META["workspace_mode"] == "shared":
        m["__shared_hub__"] = ws_root / "shared_hub"
    return m


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
            p.add_argument("--active-roles", default="")
        elif cname == "solve_role":
            p.add_argument("--role", required=True)
        elif cname == "sim_contention":
            p.add_argument("--state-dir", type=Path, required=True)
        elif cname == "grade":
            p.add_argument("--state-file", type=Path, required=True)
            p.add_argument("--wall-seconds", type=float, default=0.0)
            p.add_argument("--active-roles", default="")
            p.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    mod = CANDIDATE_MODULES[args.task]
    port = int(mod.META["portal_port"])
    ws_map = _resolve_workspace_map(mod, args.workspace_root)

    if args.cmd == "build":
        mod.build_pristine(ws_map, args.tickets_root)
        return 0
    if args.cmd == "serve":
        mod.run_portal_service(args.port, ws_map, args.state_dir, args.boot_file)
        return 0
    if args.cmd == "boot_apps":
        act = tuple(x.strip() for x in args.active_roles.split(",") if x.strip()) or None
        mod.boot_desktop_apps(ws_map, args.state_dir, active_roles=act)
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
        act = tuple(x.strip() for x in args.active_roles.split(",") if x.strip()) or None
        res = mod.grade(ws_map, read_json_safe(args.state_file), args.wall_seconds, active_roles=act)
        write_json(args.out, res)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
