"""Registry and container entrypoint CLI for authentic_workstation_v1 (AW-01..AW-22; curated Top-5)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tasks.authentic_workstation_v1 import (
    aw12_chromium_zerospoiler_suite_recreation,
    aw14_gimp_crop_layers_inkscape_poster,
    aw15_qt_designer_2tab_linguist_10str,
    aw19_libreoffice_dense_budget_and_redline,
    aw20_inkscape_gimp_freecad_meddevice_enclosure,
)
from tasks.authentic_workstation_v1.common import read_json_safe, write_json

_ALL_MODS = (
    aw12_chromium_zerospoiler_suite_recreation,
    aw14_gimp_crop_layers_inkscape_poster,
    aw15_qt_designer_2tab_linguist_10str,
    aw19_libreoffice_dense_budget_and_redline,
    aw20_inkscape_gimp_freecad_meddevice_enclosure,
)

AW_MODULES: dict[str, Any] = {m.TASK_META["id"]: m for m in _ALL_MODS}
AW_CATALOG: list[dict[str, Any]] = [dict(m.TASK_META) for m in _ALL_MODS]
AW_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in AW_CATALOG}

# Curated Top-5 retained cases after 22-candidate dual-model screening under the sealed X11/UID harness
RETAINED_TOP5_IDS: tuple[str, ...] = ("AW-12", "AW-14", "AW-15", "AW-19", "AW-20")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_build.add_argument("--workspace-root", type=Path, required=True)
    p_build.add_argument("--tickets-root", type=Path, required=True)

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_serve.add_argument("--port", type=int, required=True)
    p_serve.add_argument("--workspace-root", type=Path, required=True)
    p_serve.add_argument("--state-dir", type=Path, required=True)
    p_serve.add_argument("--boot-file", type=Path, required=True)

    p_boot = sub.add_parser("boot_apps")
    p_boot.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_boot.add_argument("--workspace-root", type=Path, required=True)
    p_boot.add_argument("--state-dir", type=Path, required=True)
    p_boot.add_argument("--active-roles", default="")

    p_solve = sub.add_parser("solve_role")
    p_solve.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_solve.add_argument("--role", required=True)
    p_solve.add_argument("--workspace-root", type=Path, required=True)

    p_race = sub.add_parser("sim_contention")
    p_race.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_race.add_argument("--workspace-root", type=Path, required=True)
    p_race.add_argument("--state-dir", type=Path, required=True)

    p_conc = sub.add_parser("careful_conc")
    p_conc.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_conc.add_argument("--workspace-root", type=Path, required=True)

    p_grade = sub.add_parser("grade")
    p_grade.add_argument("--task", required=True, choices=sorted(AW_MODULES))
    p_grade.add_argument("--workspace-root", type=Path, required=True)
    p_grade.add_argument("--state-file", type=Path, required=True)
    p_grade.add_argument("--wall-seconds", type=float, default=0.0)
    p_grade.add_argument("--active-mode", choices=("isolated", "seq_ab", "seq_ba", "shared"), default="shared")
    p_grade.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    mod = AW_MODULES[args.task]

    if args.cmd == "build":
        mod.build(args.workspace_root.resolve(), args.tickets_root.resolve())
    elif args.cmd == "serve":
        mod.serve(args.port, args.workspace_root.resolve(), args.state_dir.resolve(), args.boot_file.resolve())
    elif args.cmd == "boot_apps":
        ar = tuple(x.strip() for x in args.active_roles.split(",") if x.strip()) or None
        mod.boot_apps(args.workspace_root.resolve(), args.state_dir.resolve(), active_roles=ar)
    elif args.cmd == "solve_role":
        mod.solve_role(args.role, args.workspace_root.resolve())
    elif args.cmd == "sim_contention":
        mod.sim_contention(args.workspace_root.resolve(), args.state_dir.resolve())
    elif args.cmd == "careful_conc":
        mod.careful_conc(args.workspace_root.resolve())
    elif args.cmd == "grade":
        res = mod.grade(
            args.workspace_root.resolve(),
            read_json_safe(args.state_file.resolve()),
            args.wall_seconds,
            active_mode=args.active_mode,
        )
        write_json(args.out.resolve(), res)
        print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
