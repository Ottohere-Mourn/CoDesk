#!/usr/bin/env python3
"""One-command five-family smoke planner; --execute requires an explicit runtime plugin."""
import argparse,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument("--model",default="qwen3vl");p.add_argument("--topology",choices=["solo","ma_id","ma_sd"],action="append")
p.add_argument("--results",type=Path);p.add_argument("--resume",action="store_true")
p.add_argument("--execute",action="store_true");p.add_argument("--backend",choices=["a6000","fake"])
p.add_argument("--model-endpoint",help="loopback/reverse-tunnel Qwen endpoint; recorded for executor integrations")
p.add_argument("--plan",type=Path,default=Path("/tmp/codesk-smoke-plan.jsonl"));a=p.parse_args()
default_results=(Path("/tmp/codesk-fake-orchestration-smoke") if a.backend=="fake" else Path("artifacts/smoke"))
results=a.results or default_results
cmd=[sys.executable,str(root/"scripts/run_benchmark.py"),"--manifest",str(root/"benchmarks/codesk_v1/smoke_suite.jsonl"),
 "--suite-root",str(root/"benchmarks/codesk_v1"),"--model",a.model,"--repeats","1","--plan",str(a.plan),
 "--results",str(results)]
if a.backend:cmd.extend(["--backend",a.backend])
for topology in (a.topology or ["solo","ma_id","ma_sd"]):cmd.extend(["--topology",topology])
if a.resume:cmd.append("--resume")
if not a.execute:cmd.append("--dry-run")
if a.execute:cmd.append("--execute")
if a.model_endpoint:
    import os
    os.environ["SWCUB_QWEN_INFERENCE_URL"]=a.model_endpoint
raise SystemExit(subprocess.call(cmd,cwd=root))
