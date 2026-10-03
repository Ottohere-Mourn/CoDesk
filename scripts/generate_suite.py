#!/usr/bin/env python3
import argparse, json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import create_suite, workflow_registry, FAMILIES

p=argparse.ArgumentParser(description="Generate fixed CoDesk V1 suite offline.")
p.add_argument("--quota-per-workflow",type=int,default=40);p.add_argument("--seed",type=int,default=2026)
p.add_argument("--output",type=Path,required=True);a=p.parse_args()
result=create_suite(a.output,a.seed,a.quota_per_workflow)
(a.output/"metadata"/"workflow-registry.json").write_text(json.dumps(workflow_registry(),indent=2,ensure_ascii=False)+"\n")
(a.output/"metadata"/"family-registry.json").write_text(json.dumps(FAMILIES,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(result,indent=2))
