#!/usr/bin/env python3
import argparse, json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import read_manifest, audit_records,sha256,evaluate_oracle
p=argparse.ArgumentParser();p.add_argument("manifest",type=Path);p.add_argument("--output",type=Path,required=True);p.add_argument("--suite-root",type=Path);a=p.parse_args()
rows=read_manifest(a.manifest);out=audit_records(rows);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
root=a.suite_root or a.manifest.parent;positive=negative=files_ok=0
for row in rows:
 for asset in row["fixture_files"]:
  path=(root/asset["path"]).resolve()
  if root.resolve() not in path.parents or not path.is_file():raise SystemExit(f"unsafe/missing fixture: {asset['path']}")
  data=path.read_bytes()
  if sha256(data)!=asset["sha256"] or len(data)!=asset["size_bytes"]:raise SystemExit(f"fixture hash/size mismatch: {asset['path']}")
  files_ok+=1
 ep=(root/row["evaluator_path"]).resolve()
 if root.resolve() not in ep.parents or not ep.is_file():raise SystemExit(f"unsafe/missing evaluator: {row['evaluator_path']}")
 if sha256(ep.read_bytes())!=row["evaluator_sha256"]:raise SystemExit(f"evaluator hash mismatch: {row['instance_id']}")
 evaluator=json.loads(ep.read_text());exp=evaluator["expected_state"]
 if not evaluate_oracle({"evaluator":evaluator},exp)["joint_success"]:raise SystemExit(f"positive oracle failed: {row['instance_id']}")
 positive+=1
 bad=json.loads(json.dumps(exp));bad["actors"]["A"]["value"]=evaluator["initial_state"]["actors"]["A"]["value"]
 if evaluate_oracle({"evaluator":evaluator},bad)["joint_success"]:raise SystemExit(f"negative oracle passed: {row['instance_id']}")
 negative+=1
out.update({"fixture_files_verified":files_ok,"evaluators_verified":len(rows),"positive_oracle_controls":positive,"negative_oracle_controls":negative})
a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps({k:out[k] for k in ("generated","retained","duplicate_rejected","near_duplicate_rejected")},indent=2))
