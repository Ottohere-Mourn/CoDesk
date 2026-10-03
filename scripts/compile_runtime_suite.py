#!/usr/bin/env python3
import argparse,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.runtime_v1 import compile_suite

p=argparse.ArgumentParser(description="Compile every fixed manifest row through its workflow runtime adapter (offline).")
p.add_argument("--manifest",type=Path,default=Path("benchmarks/codesk_v1/manifest.jsonl"))
p.add_argument("--suite-root",type=Path,default=Path("benchmarks/codesk_v1"))
p.add_argument("--output",type=Path,default=Path("benchmarks/codesk_v1/runtime_plans.jsonl"))
a=p.parse_args()
result=compile_suite(a.manifest,a.suite_root,a.output)
(a.suite_root/"metadata"/"runtime-compile.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
print(json.dumps(result,indent=2))
if result["failed"]:raise SystemExit(1)
