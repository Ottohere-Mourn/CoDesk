"""Stage CONC-05 English scan images, host-only oracle, and task bridge."""
from __future__ import annotations
import argparse,shutil
from pathlib import Path
from build_assets import build as build_assets
CASE=Path(__file__).resolve().parents[1]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def build(destination:Path):
 dest=Path(destination).resolve();runner=dest/"runner-source";assets=dest/"task-assets"
 build_assets(assets)
 copy(CASE/"integration/service.py",assets/"CONC-05/service.py")
 copy(CASE/"private/expected.json",assets/"CONC-05/private/expected.json")
 for n in ("task_conc05a.py","task_conc05b.py"):copy(CASE/"integration"/n,runner/"case_work/20261125-conc-batch1/CONC-05/integration"/n)
 copy(CASE/"integration/pg_conc05.py",runner/"evaluation_examples/task_class/pg_conc05.py")
 copy(CASE/"private/grade.py",runner/"evaluation_examples/task_class/conc05_grade.py")
 copy(CASE.parent/"common/stateless_cua.py",runner/"paragui_batch/stateless_cua.py")
 for p in (runner/"evaluation_examples",runner/"evaluation_examples/task_class",runner/"paragui_batch"):
  p.mkdir(parents=True,exist_ok=True);f=p/"__init__.py"
  if not f.exists():f.write_text("from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n",encoding="utf-8")
 return runner,assets
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("destination",type=Path);r,a=build(ap.parse_args().destination);print(f"runner-source={r}");print(f"task-assets={a}")
