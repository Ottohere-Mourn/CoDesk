"""Registry and container CLI entrypoints for fair_contention_v1 bespoke 2-agent cases."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tasks.fair_contention_v1 import (
    fc01_aero_actuator_cad,
    fc02_git_staging_webapp,
    fc03_treasury_sso_clipboard,
    fc04_sre_observability_pollution,
    fc05_qgis_spatialite_corridor,
    fc06_mlt_ffmpeg_lufs_mastering,
    fc07_gimp_icc_packaging_prepress,
    fc08_green_bms_idf_dscr,
    fc09_spice_pcb_emi_thermal,
    fc10_lims_pkpd_bioassay,
    fc11_seismic_frame_geotech,
    fc12_quant_factor_margin_var,
    fc13_envoy_mtls_mesh_slo,
    fc14_optics_zemax_cryo_baffle,
    fc15_opc_litho_cmp_dishing,
)
from tasks.fair_contention_v1.common import write_json

CASE_MODULES = {
    fc01_aero_actuator_cad.TASK_ID: fc01_aero_actuator_cad,
    fc02_git_staging_webapp.TASK_ID: fc02_git_staging_webapp,
    fc03_treasury_sso_clipboard.TASK_ID: fc03_treasury_sso_clipboard,
    fc04_sre_observability_pollution.TASK_ID: fc04_sre_observability_pollution,
    fc05_qgis_spatialite_corridor.TASK_ID: fc05_qgis_spatialite_corridor,
    fc06_mlt_ffmpeg_lufs_mastering.TASK_ID: fc06_mlt_ffmpeg_lufs_mastering,
    fc07_gimp_icc_packaging_prepress.TASK_ID: fc07_gimp_icc_packaging_prepress,
    fc08_green_bms_idf_dscr.TASK_ID: fc08_green_bms_idf_dscr,
    fc09_spice_pcb_emi_thermal.TASK_ID: fc09_spice_pcb_emi_thermal,
    fc10_lims_pkpd_bioassay.TASK_ID: fc10_lims_pkpd_bioassay,
    fc11_seismic_frame_geotech.TASK_ID: fc11_seismic_frame_geotech,
    fc12_quant_factor_margin_var.TASK_ID: fc12_quant_factor_margin_var,
    fc13_envoy_mtls_mesh_slo.TASK_ID: fc13_envoy_mtls_mesh_slo,
    fc14_optics_zemax_cryo_baffle.TASK_ID: fc14_optics_zemax_cryo_baffle,
    fc15_opc_litho_cmp_dishing.TASK_ID: fc15_opc_litho_cmp_dishing,
}

FAIR_CONTENTION_CATALOG = [mod.META for mod in CASE_MODULES.values()]
FC_BY_ID = {mod.TASK_ID: mod.META for mod in CASE_MODULES.values()}


def get_case_module(task_id: str):
    if task_id not in CASE_MODULES:
        raise KeyError(f"Unknown fair_contention_v1 task_id: {task_id}")
    return CASE_MODULES[task_id]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--task", required=True)
    p_build.add_argument("--workspace", type=Path, required=True)
    p_build.add_argument("--tickets-root", type=Path, required=True)

    p_sim = sub.add_parser("simulate")
    p_sim.add_argument("--task", required=True)
    p_sim.add_argument("--port", type=int, required=True)
    p_sim.add_argument("--workspace", type=Path, required=True)
    p_sim.add_argument("--state-dir", type=Path, required=True)
    p_sim.add_argument("--boot-file", type=Path, required=True)

    p_grade = sub.add_parser("grade")
    p_grade.add_argument("--task", required=True)
    p_grade.add_argument("--workspace", type=Path, required=True)
    p_grade.add_argument("--portal-state", type=Path, required=True)
    p_grade.add_argument("--wall-seconds", type=float, required=True)
    p_grade.add_argument("--out", type=Path, required=True)

    p_solve = sub.add_parser("solve_role")
    p_solve.add_argument("--task", required=True)
    p_solve.add_argument("--role", required=True)
    p_solve.add_argument("--workspace", type=Path, required=True)

    p_race = sub.add_parser("sim_race")
    p_race.add_argument("--task", required=True)
    p_race.add_argument("--workspace", type=Path, required=True)

    p_trans = sub.add_parser("audit_transparency")
    p_trans.add_argument("--task", required=True)

    args = p.parse_args(argv)
    mod = get_case_module(args.task)

    if args.cmd == "build":
        mod.build_pristine(args.workspace, args.tickets_root)
        return 0

    if args.cmd == "simulate":
        fast = os.environ.get("PARAGUI_FC_FAST_SELFVAL") == "1"
        mod.run_simulator(args.port, args.workspace, args.state_dir, args.boot_file, fast_selfval=fast)
        return 0

    if args.cmd == "grade":
        pstate = {}
        if args.portal_state.is_file():
            pstate = json.loads(args.portal_state.read_text(encoding="utf-8"))
        res = mod.grade(args.workspace, pstate, args.wall_seconds)
        write_json(args.out, res)
        return 0

    if args.cmd == "solve_role":
        mod.solve_role(args.role, args.workspace, int(mod.META["portal_port"]))
        return 0

    if args.cmd == "sim_race":
        mod.simulate_naive_race(args.workspace, int(mod.META["portal_port"]))
        return 0

    if args.cmd == "audit_transparency":
        print(json.dumps(mod.audit_case_transparency(), ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
