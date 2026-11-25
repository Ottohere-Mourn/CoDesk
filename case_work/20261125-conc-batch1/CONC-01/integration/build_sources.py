"""Build isolated, versioned runner and Guest-asset trees for CONC-01."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]


def _copy(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def build(destination: Path):
    dest = Path(destination).resolve()
    runner = dest / "runner-source"
    assets = dest / "task-assets"
    _copy(CASE / "integration" / "task_conc01a.py", runner / "case_work/20261125-conc-batch1/CONC-01/integration/task_conc01a.py")
    _copy(CASE / "integration" / "task_conc01b.py", runner / "case_work/20261125-conc-batch1/CONC-01/integration/task_conc01b.py")
    _copy(CASE / "integration" / "task_conc01gate5.py", runner / "case_work/20261125-conc-batch1/CONC-01/integration/task_conc01gate5.py")
    _copy(CASE / "integration" / "pg_conc01.py", runner / "evaluation_examples/task_class/pg_conc01.py")
    _copy(CASE / "private" / "grade.py", runner / "evaluation_examples/task_class/conc01_grade.py")
    _copy(CASE / "integration" / "service.py", assets / "CONC-01/service.py")
    _copy(CASE / "integration" / "gate5_reference.py", assets / "CONC-01/gate5_reference.py")
    _copy(CASE.parent / "common" / "stateless_cua.py", runner / "paragui_batch/stateless_cua.py")
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
