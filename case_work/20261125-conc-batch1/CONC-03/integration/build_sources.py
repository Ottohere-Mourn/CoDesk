"""Stage the CONC-03 task pair and English-only Guest assets."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from build_assets import build as build_assets

CASE = Path(__file__).resolve().parents[1]


def _copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(destination: Path):
    dest = Path(destination).resolve()
    runner = dest / "runner-source"
    assets = dest / "task-assets" / "CONC-03"
    build_assets(assets)
    _copy(CASE / "integration" / "service.py", assets / "service.py")
    for name in ("task_conc03a.py", "task_conc03b.py"):
        _copy(CASE / "integration" / name,
              runner / "case_work/20261125-conc-batch1/CONC-03/integration" / name)
    _copy(CASE / "integration" / "pg_conc03.py", runner / "evaluation_examples/task_class/pg_conc03.py")
    _copy(CASE.parent / "common" / "stateless_cua.py", runner / "paragui_batch/stateless_cua.py")
    _copy(CASE / "private" / "grade.py", runner / "evaluation_examples/task_class/conc03_grade.py")
    for package in (runner / "evaluation_examples", runner / "evaluation_examples/task_class", runner / "paragui_batch"):
        package.mkdir(parents=True, exist_ok=True)
        init = package / "__init__.py"
        if not init.exists():
            init.write_text("from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n", encoding="utf-8")
    return runner, assets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("destination", type=Path)
    args = ap.parse_args()
    runner, assets = build(args.destination)
    print(f"runner-source={runner}")
    print(f"task-assets={assets}")


if __name__ == "__main__":
    main()
