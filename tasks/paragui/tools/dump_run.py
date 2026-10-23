"""dump_run.py RUN OUT_DIR: one line per step of both agents (time, agent#step, active windows, reasoning, actions) plus checker details."""
import json, sys
run = sys.argv[1]
d = f"{sys.argv[2]}/{run}"
r = json.load(open(d + "/result.json"))
print("RUN", run, r["scores"], {k: (v["task"], v["status"], v["steps"]) for k, v in r["agents"].items()})
for k, v in (r.get("eval_checks") or {}).items():
    print("CHECK", k, json.dumps(v)[:500])
recs = [json.loads(l) for l in open(d + "/trace.jsonl")]
for x in sorted([x for x in recs if "step" in x], key=lambda x: x["t"]):
    acts = " ; ".join(" ".join(str(a.get("code")).split())[-120:] for a in x.get("actions") or [] if "sleep" not in str(a.get("code")))
    wins = sorted({str(a.get("window_before"))[:35] for a in x.get("actions") or []})
    resp = " ".join(str(x.get("response") or "").split())
    print(f"{x['t']:7.0f} {x['agent'][-1]}#{x['step']:<3} {wins} | {resp[:330]} || {acts[:260]}")
