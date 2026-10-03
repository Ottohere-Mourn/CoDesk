#!/usr/bin/env python3
"""Manifest planner/executor. No Guest effects occur without an explicit backend plugin."""
import argparse,importlib,json,os,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swcub.production_v1 import make_run_plan,read_manifest
from swcub.runtime_v1 import build_runtime_registry,bind_run_plan

def main() -> int:
 p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,required=True)
 p.add_argument("--topology",choices=["solo","ma_id","ma_sd"],action="append",required=True)
 p.add_argument("--model",required=True);p.add_argument("--repeats",type=int,default=1)
 p.add_argument("--results",type=Path,default=Path("runs"));p.add_argument("--plan",type=Path,required=True)
 p.add_argument("--resume",action="store_true");p.add_argument("--max-infra-retries",type=int,default=1)
 p.add_argument("--dry-run",action="store_true");p.add_argument("--execute",action="store_true")
 p.add_argument("--family");p.add_argument("--workflow");p.add_argument("--instance",action="append")
 p.add_argument("--suite-root",type=Path);p.add_argument("--offset",type=int,default=0);p.add_argument("--limit",type=int)
 a=p.parse_args()
 if a.execute and a.dry_run:raise SystemExit("choose one of --dry-run or --execute")
 if a.offset<0 or (a.limit is not None and a.limit<1) or a.max_infra_retries<0:raise SystemExit("invalid range/retry argument")
 rows=read_manifest(a.manifest);suite_root=a.suite_root or a.manifest.parent
 if a.family:rows=[r for r in rows if r["family"]==a.family]
 if a.workflow:rows=[r for r in rows if r["workflow_id"]==a.workflow]
 if a.instance:
  chosen=set(a.instance);rows=[r for r in rows if r["instance_id"] in chosen]
  missing=chosen-{r["instance_id"] for r in rows}
  if missing:raise SystemExit(f"instances not found after filters: {sorted(missing)}")
 rows=rows[a.offset:a.offset+a.limit if a.limit is not None else None]
 done=set();infra_attempts=defaultdict(int)
 if a.resume and a.results.exists():
  for f in a.results.glob("*/result.json"):
   try:
    result=json.loads(f.read_text());base=result.get("base_run_id",result.get("run_id"))
    if result.get("status")=="INVALID_INFRA":infra_attempts[base]+=1
    elif result.get("status") in ("PASS","TASK_FAILURE","MODEL_FAILURE"):done.add(base)
   except Exception:pass
 plan=make_run_plan(rows,a.topology,a.model,a.repeats,done,infra_attempts,a.max_infra_retries)
 registry=build_runtime_registry();compiled={};errors={}
 for row in rows:
  try:compiled[row["instance_id"]]=registry.compile(row,suite_root,a.topology)
  except Exception as exc:errors[row["instance_id"]]=repr(exc)
 bound_runs={}
 for run in plan:
  if run["instance_id"] in errors:
   run.update({"adapter_status":"ADAPTER_COMPILE_FAILED","adapter_error":errors[run["instance_id"]]})
  else:
   rp=compiled[run["instance_id"]];run.update({"runtime_adapter_id":rp["adapter_id"],
    "runtime_plan_sha256":rp["plan_sha256"],"schedule_policy_id":rp["topologies"][run["topology"]]["schedule_policy_id"],
    "adapter_status":"PLAN_COMPILED_GUEST_RUNTIME_UNVALIDATED"})
   bound=bind_run_plan(rp,run);run["bound_runtime_plan_sha256"]=bound["plan_sha256"]
   bound_runs[run["run_id"]]=bound
 a.plan.parent.mkdir(parents=True,exist_ok=True);a.plan.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in plan))
 summary={"planned":len(plan),"compiled_instances":len(compiled),"adapter_compile_errors":len(errors),
  "skipped_completed":len(done),"invalid_infra_retries_seen":sum(infra_attempts.values()),"plan":str(a.plan),"guest_started":False}
 if a.execute:
  factory_path=os.environ.get("SWCUB_RUNTIME_EXECUTOR_FACTORY")
  if not factory_path:
   blocked=0;missing=0
   for run in plan:
    run_dir=a.results/run["run_id"];run_dir.mkdir(parents=True,exist_ok=True)
    status="ADAPTER_MISSING" if run["instance_id"] in errors else "BLOCKED_RUNTIME_BACKEND"
    if status=="ADAPTER_MISSING":missing+=1
    else:blocked+=1
    (run_dir/"execution-status.json").write_text(json.dumps({"run_id":run["run_id"],"base_run_id":run["base_run_id"],
      "instance_id":run["instance_id"],"status":status,"reason":errors.get(run["instance_id"],
      "no SWCUB_RUNTIME_EXECUTOR_FACTORY configured; Guest not started"),"guest_started":False,
      "adapter_id":run.get("runtime_adapter_id")},indent=2)+"\n")
   summary.update({"execution_status":"per_run_blocked","adapter_missing_runs":missing,"runtime_backend_missing_runs":blocked})
  else:
   module,attr=factory_path.split(":",1);executor=getattr(importlib.import_module(module),attr)()
   completed=0;failed=0
   for run in plan:
    if run["instance_id"] in errors:failed+=1;continue
    try:
     executor.execute_run(registry.get(run["workflow_id"]),bound_runs[run["run_id"]],run,a.results/run["run_id"])
     completed+=1
    except Exception as exc:
     failed+=1;out=a.results/run["run_id"];out.mkdir(parents=True,exist_ok=True)
     (out/"result.json").write_text(json.dumps({"run_id":run["run_id"],"base_run_id":run["base_run_id"],
       "status":"INVALID_INFRA","failure_reason":"runtime_executor_exception","error":repr(exc)},indent=2)+"\n")
   summary.update({"execution_status":"executor_plugin_used","completed_calls":completed,"adapter_compile_errors":failed})
 elif not a.dry_run:raise SystemExit("Choose --dry-run or --execute explicitly.")
 print(json.dumps(summary,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
