"""Stage isolated CONC-02 task modules and blind grader."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
from build_assets import build as build_assets


def copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(destination: Path):
    dest = Path(destination).resolve()
    runner = dest / "runner-source"
    assets = dest / "task-assets" / "CONC-02"
    build_assets(assets)
    for name in ("task_conc02a.py", "task_conc02b.py"):
        copy(CASE / "integration" / name, runner / "case_work/20261125-conc-batch1/CONC-02/integration" / name)
    # Version the task-side evaluator module so a prior run's OSWorld install
    # is never overwritten in place by the active queue's collision guard.
    copy(CASE / "integration/pg_conc02.py", runner / "evaluation_examples/task_class/pg_conc02_retry.py")
    copy(CASE / "private/grade.py", runner / "evaluation_examples/task_class/conc02_grade.py")
    copy(CASE.parent / "common/stateless_cua.py", runner / "paragui_batch/stateless_cua.py")
    for package in (runner / "evaluation_examples", runner / "evaluation_examples/task_class",
                    runner / "paragui_batch"):
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
    print(f"case-assets={assets}")


if __name__ == "__main__":
    main()
