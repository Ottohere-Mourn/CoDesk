#!/usr/bin/env python3
"""One-command five-family smoke planner; --execute requires an explicit runtime plugin."""
import argparse,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument("--model",default="qwen3vl");p.add_argument("--topology",choices=["solo","ma_id","ma_sd"],action="append")
p.add_argument("--results",type=Path,default=Path("artifacts/smoke"));p.add_argument("--resume",action="store_true")
p.add_argument("--execute",action="store_true");p.add_argument("--plan",type=Path,default=Path("/tmp/codesk-smoke-plan.jsonl"));a=p.parse_args()
cmd=[sys.executable,str(root/"scripts/run_benchmark.py"),"--manifest",str(root/"benchmarks/codesk_v1/smoke_suite.jsonl"),
 "--suite-root",str(root/"benchmarks/codesk_v1"),"--model",a.model,"--repeats","1","--plan",str(a.plan),
 "--results",str(a.results)]
for topology in (a.topology or ["solo","ma_id","ma_sd"]):cmd.extend(["--topology",topology])
cmd.append("--resume" if a.resume else "--dry-run")
if a.execute:cmd=[x for x in cmd if x!="--dry-run"];cmd.append("--execute")
raise SystemExit(subprocess.call(cmd,cwd=root))
