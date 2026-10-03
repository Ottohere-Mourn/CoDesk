#!/usr/bin/env python3
"""Fail-closed planner for CoDesk fixed suite; no Guest is launched by --dry-run."""
import argparse,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import make_run_plan,read_manifest
p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,required=True);p.add_argument("--topology",choices=["solo","ma_id","ma_sd"],action="append",required=True)
p.add_argument("--model",required=True);p.add_argument("--repeats",type=int,default=1);p.add_argument("--results",type=Path,default=Path("runs"))
p.add_argument("--plan",type=Path,required=True);p.add_argument("--resume",action="store_true");p.add_argument("--max-infra-retries",type=int,default=1);p.add_argument("--dry-run",action="store_true")
p.add_argument("--execute",action="store_true");p.add_argument("--family");p.add_argument("--workflow")
p.add_argument("--offset",type=int,default=0,help="zero-based position in filtered manifest")
p.add_argument("--limit",type=int,help="maximum fixed instances after offset");a=p.parse_args()
if a.offset<0 or (a.limit is not None and a.limit<1):raise SystemExit("invalid offset/limit")
rows=read_manifest(a.manifest)
if a.family: rows=[r for r in rows if r["family"]==a.family]
if a.workflow: rows=[r for r in rows if r["workflow_id"]==a.workflow]
rows=rows[a.offset:a.offset+a.limit if a.limit is not None else None]
done=set();infra_attempts=defaultdict(int)
if a.resume and a.results.exists():
 for f in a.results.glob("*/result.json"):
  try:
   r=json.loads(f.read_text());base=r.get("base_run_id",r.get("run_id"))
   if r.get("status")=="INVALID_INFRA":infra_attempts[base]+=1
   elif r.get("status") in ("PASS","TASK_FAILURE","MODEL_FAILURE"):done.add(base)
  except Exception:pass
plan=make_run_plan(rows,a.topology,a.model,a.repeats,done,infra_attempts,a.max_infra_retries)
a.plan.parent.mkdir(parents=True,exist_ok=True);a.plan.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in plan))
print(json.dumps({"planned":len(plan),"skipped_completed":len(done),"invalid_infra_retries_scheduled":sum(infra_attempts.values()),"plan":str(a.plan),"guest_started":False},indent=2))
if a.execute:
 raise SystemExit("LIVE_EXECUTION_BLOCKED: no parameterized workflow runtime adapters are registered; no Guest was started. Implement and validate an adapter before execution.")
if not a.dry_run: raise SystemExit("Choose --dry-run or --execute explicitly.")
