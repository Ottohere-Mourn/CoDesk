#!/usr/bin/env python3
"""Compile per-instance runtime/backend setup records without starting OSWorld."""
import argparse,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import read_manifest
from swcub.runtime_v1 import build_runtime_registry

p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,default=Path("benchmarks/codesk_v1/manifest.jsonl"));p.add_argument("--suite-root",type=Path,default=Path("benchmarks/codesk_v1"));p.add_argument("--output",type=Path,default=Path("benchmarks/codesk_v1/backend_preflight.jsonl"));p.add_argument("--summary",type=Path,default=Path("benchmarks/codesk_v1/metadata/backend-preflight.json"));a=p.parse_args()
registry=build_runtime_registry();rows=read_manifest(a.manifest);counts=Counter();missing=Counter();compiled=[]
for row in rows:
 plan=registry.compile(row,a.suite_root)
 binding=plan["runtime_execution_binding"]
 status="MISSING_IMPLEMENTATION" if binding["missing_components"] else "CODE_READY"
 counts[status]+=1
 for component in binding["missing_components"]: missing[component]+=1
 compiled.append({"instance_id":row["instance_id"],"workflow_id":row["workflow_id"],
  "plan_sha256":plan["plan_sha256"],"backend_binding":binding,
  "status":status,"guest_started":False,"model_started":False})
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in compiled))
summary={"compiled":len(compiled),"compile_failures":0,"status_counts":dict(counts),
 "workflow_counts":dict(Counter(x["workflow_id"] for x in compiled)),"missing_component_counts":dict(missing),
 "missing_implementation_workflows":sorted({x["workflow_id"] for x in compiled if x["status"]=="MISSING_IMPLEMENTATION"}),
 "guest_started":False,"model_started":False,"path":str(a.output)}
a.summary.parent.mkdir(parents=True,exist_ok=True);a.summary.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2))
