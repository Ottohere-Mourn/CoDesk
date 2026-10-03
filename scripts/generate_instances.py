#!/usr/bin/env python3
import argparse, json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import generate_workflow, audit_records,sha256,evaluate_oracle

p=argparse.ArgumentParser(description="Generate deterministic CoDesk V1 workflow instances (offline).")
p.add_argument("--workflow",required=True); p.add_argument("--count",type=int,default=3)
p.add_argument("--seed",type=int,default=2026); p.add_argument("--output",type=Path,required=True)
p.add_argument("--validate",action="store_true")
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
for d in ("instances","fixtures","evaluators","workflows","families","metadata"):(a.output/d).mkdir()
rows=generate_workflow(a.workflow,a.count,a.seed,a.output)
(a.output/"manifest.jsonl").write_text("".join(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n" for x in rows))
audit=audit_records(rows)
(a.output/"metadata"/"audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
if a.validate and audit["retained"]!=len(rows):raise SystemExit("DIVERSITY_GATE_FAILED")
if a.validate:
 for row in rows:
  for asset in row["fixture_files"]:
   data=(a.output/asset["path"]).read_bytes()
   if sha256(data)!=asset["sha256"]:raise SystemExit("FIXTURE_HASH_FAILED")
  evaluator=json.loads((a.output/row["evaluator_path"]).read_text())
  if not evaluate_oracle({"evaluator":evaluator},evaluator["expected_state"])["joint_success"]:raise SystemExit("POSITIVE_ORACLE_FAILED")
  bad=json.loads(json.dumps(evaluator["expected_state"]));bad["actors"]["A"]["value"]=evaluator["initial_state"]["actors"]["A"]["value"]
  if evaluate_oracle({"evaluator":evaluator},bad)["joint_success"]:raise SystemExit("NEGATIVE_ORACLE_FAILED")
print(json.dumps({"workflow":a.workflow,"generated":len(rows),"audit":audit},indent=2))
