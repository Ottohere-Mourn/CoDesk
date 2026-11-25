"""Stage English inputs, private expected values and host runner modules."""
from __future__ import annotations
import argparse,shutil
from pathlib import Path
from build_assets import build as build_assets
CASE=Path(__file__).resolve().parents[1]
def cp(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def build(destination:Path):
    dest=Path(destination).resolve();runner=dest/"runner-source";assets=dest/"task-assets";build_assets(assets)
    cp(CASE/"integration/service.py",assets/"CONC-07/service.py")
    for n in ("task_conc07a.py","task_conc07b.py"):cp(CASE/"integration"/n,runner/"case_work/20261125-conc-batch1/CONC-07/integration"/n)
    cp(CASE/"integration/pg_conc07.py",runner/"evaluation_examples/task_class/pg_conc07.py");cp(CASE/"private/grade.py",runner/"evaluation_examples/task_class/conc07_grade.py");cp(CASE.parent/"common/stateless_cua.py",runner/"paragui_batch/stateless_cua.py")
    for p in (runner/"evaluation_examples",runner/"evaluation_examples/task_class",runner/"paragui_batch"):
        p.mkdir(parents=True,exist_ok=True);f=p/"__init__.py"
        if not f.exists():f.write_text("from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n",encoding="utf-8")
    return runner,assets
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("destination",type=Path);r,a=build(p.parse_args().destination);print(f"runner-source={r}");print(f"task-assets={a}")
