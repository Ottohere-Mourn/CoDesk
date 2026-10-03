#!/usr/bin/env python3
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser();p.add_argument("results_root",type=Path);p.add_argument("--output-dir",type=Path,required=True);a=p.parse_args()
groups=defaultdict(list);invalid=[]
for f in a.results_root.glob("*/result.json"):
 try:r=json.loads(f.read_text())
 except Exception:continue
 if r.get("status")=="INVALID_INFRA":invalid.append(r);continue
 key=(r.get("family","unknown"),r.get("workflow_id","unknown"),r.get("topology","unknown"),r.get("model","unknown"));groups[key].append(r)
rows=[]
for key,items in sorted(groups.items()):
 def mean(k):
  vals=[x[k] for x in items if isinstance(x.get(k),(int,float))];return sum(vals)/len(vals) if vals else None
 rows.append(dict(zip(("family","workflow_id","topology","model"),key),episodes=len(items),
   actor_a_success=sum(bool(x.get("actor_success",{}).get("A")) for x in items),
   actor_b_success=sum(bool(x.get("actor_success",{}).get("B")) for x in items),
   joint_success=sum(bool(x.get("joint_success")) for x in items),
   scheduled_exposure=sum(bool(x.get("scheduled_exposure")) for x in items),
   actual_exposure=sum(bool(x.get("actual_exposure")) for x in items),
   observed_interference=sum(bool(x.get("observed_interference")) for x in items),
   autonomous_recovery=sum(bool(x.get("autonomous_recovery")) for x in items),
   recovery_success=sum(bool(x.get("recovery_success")) for x in items),
   mean_action_count=mean("action_count"),mean_episode_seconds=mean("episode_seconds"),
   mean_inference_latency_ms=mean("inference_latency_ms")))
a.output_dir.mkdir(parents=True,exist_ok=True)
(a.output_dir/"summary.json").write_text(json.dumps({"groups":rows,"invalid_infra_count":len(invalid)},indent=2)+"\n")
if rows:
 with (a.output_dir/"summary.csv").open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=["# CoDesk result summary","",f"Valid result groups: {len(rows)}",f"INVALID_INFRA episodes (excluded from success denominators): {len(invalid)}","","| Family | Workflow | Topology | Model | n | A | B | Joint | Exposure | Interference | Recovery |","|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
for r in rows:lines.append(f"| {r['family']} | {r['workflow_id']} | {r['topology']} | {r['model']} | {r['episodes']} | {r['actor_a_success']} | {r['actor_b_success']} | {r['joint_success']} | {r['actual_exposure']} | {r['observed_interference']} | {r['autonomous_recovery']} |")
(a.output_dir/"summary.md").write_text("\n".join(lines)+"\n")
print(f"groups={len(rows)} invalid_infra={len(invalid)}")
