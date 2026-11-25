"""Stage case-unique runner modules, English assets, and host-only answer key."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from build_assets import build as build_assets

CASE = Path(__file__).resolve().parents[1]


def copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build(destination: Path):
    dest = Path(destination).resolve()
    runner, assets = dest / "runner-source", dest / "task-assets"
    build_assets(assets)
    copy(CASE / "integration/service.py", assets / "CONC-04/service.py")
    for name in ("task_conc04a.py", "task_conc04b.py"):
        copy(CASE / "integration" / name, runner / "case_work/20261125-conc-batch1/CONC-04/integration" / name)
    copy(CASE / "integration/pg_conc04.py", runner / "evaluation_examples/task_class/pg_conc04.py")
    copy(CASE / "private/grade.py", runner / "evaluation_examples/task_class/conc04_grade.py")
    copy(CASE.parent / "common/stateless_cua.py", runner / "paragui_batch/stateless_cua.py")
    for package in (runner / "evaluation_examples", runner / "evaluation_examples/task_class", runner / "paragui_batch"):
        package.mkdir(parents=True, exist_ok=True)
        init = package / "__init__.py"
        if not init.exists():
            init.write_text("from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n", encoding="utf-8")
    return runner, assets


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("destination", type=Path)
    runner, assets = build(ap.parse_args().destination)
    print(f"runner-source={runner}")
    print(f"task-assets={assets}")
