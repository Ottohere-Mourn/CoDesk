"""Registry and container CLI entrypoints for exam_contention_v1 (EC-01..EC-05)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from tasks.exam_contention_v1 import (
    ec01_ma_dataroom_calc,
    ec03_enclosure_cad_emi,
)
from tasks.exam_contention_v1.common import write_json

CASE_MODULES = {
    ec01_ma_dataroom_calc.TASK_ID: ec01_ma_dataroom_calc,
    ec03_enclosure_cad_emi.TASK_ID: ec03_enclosure_cad_emi,
}

EXAM_CONTENTION_CATALOG = [mod.META for mod in CASE_MODULES.values()]
EC_BY_ID = {mod.TASK_ID: mod.META for mod in CASE_MODULES.values()}


def get_case_module(task_id: str):
    if task_id not in CASE_MODULES:
        raise KeyError(f"Unknown exam_contention_v1 task_id: {task_id}")
    return CASE_MODULES[task_id]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build")
    p_b.add_argument("--task", required=True)
    p_b.add_argument("--workspace", type=Path, required=True)
    p_b.add_argument("--tickets-root", type=Path, required=True)

    p_s = sub.add_parser("serve")
    p_s.add_argument("--task", required=True)
    p_s.add_argument("--port", type=int, required=True)
    p_s.add_argument("--workspace", type=Path, required=True)
    p_s.add_argument("--state-dir", type=Path, required=True)
    p_s.add_argument("--boot-file", type=Path, required=True)

    p_g = sub.add_parser("grade")
    p_g.add_argument("--task", required=True)
    p_g.add_argument("--workspace", type=Path, required=True)
    p_g.add_argument("--service-state", type=Path, required=True)
    p_g.add_argument("--wall-seconds", type=float, required=True)
    p_g.add_argument("--out", type=Path, required=True)

    p_sol = sub.add_parser("solve_role")
    p_sol.add_argument("--task", required=True)
    p_sol.add_argument("--role", required=True)
    p_sol.add_argument("--workspace", type=Path, required=True)
    p_sol.add_argument("--careful-conc", action="store_true")

    p_nr = sub.add_parser("sim_naive_race")
    p_nr.add_argument("--task", required=True)
    p_nr.add_argument("--workspace", type=Path, required=True)

    p_cc = sub.add_parser("sim_careful_conc")
    p_cc.add_argument("--task", required=True)
    p_cc.add_argument("--workspace", type=Path, required=True)

    args = ap.parse_args(argv)
    mod = get_case_module(args.task)
    port = int(mod.META["portal_port"])

    if args.cmd == "build":
        mod.build_pristine(args.workspace, args.tickets_root)
        return 0
    if args.cmd == "serve":
        mod.run_portal_service(args.port, args.workspace, args.state_dir, args.boot_file)
        return 0
    if args.cmd == "grade":
        st = json.loads(args.service_state.read_text(encoding="utf-8")) if args.service_state.is_file() else {}
        res = mod.grade(args.workspace, st, args.wall_seconds)
        write_json(args.out, res)
        return 0
    if args.cmd == "solve_role":
        mod.solve_role(args.role, args.workspace, port, careful_conc=args.careful_conc)
        return 0
    if args.cmd == "sim_naive_race":
        mod.simulate_naive_race(args.workspace, port)
        return 0
    if args.cmd == "sim_careful_conc":
        ra, rb = mod.META["roles"]
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(mod.solve_role, ra, args.workspace, port, True)
            fb = pool.submit(mod.solve_role, rb, args.workspace, port, True)
            fa.result()
            fb.result()
        print(json.dumps({"careful_conc_elapsed_s": round(time.monotonic() - t0, 2)}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
