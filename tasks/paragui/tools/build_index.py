#!/usr/bin/env python3
"""Index the paraGUI dataset runs: one JSON line per run (+ per-agent outcome and a coarse failure class).

    python3 build_index.py OUT_DIR PREFIX > index.jsonl        # e.g. runs v1-

Run naming: <prefix><pair>-solo-<task>-r<k> | <prefix><pair>-seq-<first>First-r<k> | <prefix><pair>-par-<first>First-r<k>
| <prefix><pair>-sg-<first>First-r<k> (parallel with SelfGuard).
"""
import glob
import json
import os
import re
import sys

PASS = 0.8
AWARE = re.compile(r"another (agent|user|process|program|instance|actor|automation|session)|other agent|someone else|"
                   r"concurren|interfer|external (process|change|actor|input)|typing source|not responding to input|"
                   r"being controlled|competing", re.I)
QUIT = re.compile(r"pkill|killall|kill -9|'ctrl', 'q'|--terminate|soffice --headless", re.I)


def agent_rows(trace, name):
    return [x for x in trace if x.get("agent") == name and "step" in x]


def classify(status, score, rows, other_rows):
    if score is None:
        return "infra"
    if score >= PASS:
        return "pass"
    text = " ".join(str(r.get("response") or "") for r in rows)
    other_quit = any(QUIT.search(str(a.get("code"))) for r in other_rows for a in r.get("actions") or [])
    if status == "fail":
        return "gave_up_interference" if AWARE.search(text) else "gave_up"
    if status in ("max_steps", "timeout"):
        return "out_of_budget"
    if status == "done":
        return "done_low_other_quit_app" if other_quit else "done_low"
    return status or "unknown"


def main():
    out, prefix = sys.argv[1], sys.argv[2]
    for res in sorted(glob.glob(f"{out}/{prefix}*/result.json")):
        d = os.path.dirname(res)
        name = os.path.basename(d)
        m = re.match(re.escape(prefix) + r"(?P<pair>[a-z0-9]+)-(?P<mode>solo|seq|par|sg)-(?P<first>[a-z0-9]+?)(First)?-r(?P<rep>\d+)$", name)
        r = json.load(open(res))
        env = json.load(open(f"{d}/run_env.json")) if os.path.exists(f"{d}/run_env.json") else {}
        trace = [json.loads(l) for l in open(f"{d}/trace.jsonl")] if os.path.exists(f"{d}/trace.jsonl") else []
        agents = r.get("agents") or {}
        scores = r.get("scores") or {}
        rec = {"run": name, "pair": m["pair"] if m else None, "mode": m["mode"] if m else r.get("mode"),
               "first": m["first"] if m else None, "rep": int(m["rep"]) if m else None,
               "tasks": r.get("tasks"), "model": r.get("model"), "node": env.get("node"), "code": env.get("code"),
               "max_steps": env.get("max_steps"), "selfguard": env.get("selfguard") == "1",
               "boot_s": r.get("boot_s"), "setup_s": r.get("setup_s"), "agents_s": r.get("agents_s"),
               "error": r.get("error"), "agents": {}}
        names = list(agents)
        for a in names:
            v = agents[a]
            rows = agent_rows(trace, a)
            other = [x for x in names if x != a]
            score = scores.get(v["task"])
            rec["agents"][a] = {
                "task": v["task"], "score": score, "status": v["status"], "steps": v["steps"],
                "chain_resets": v.get("chain_resets", 0), "error": v.get("error"),
                "outcome": classify(v["status"], score, rows, agent_rows(trace, other[0]) if other else []),
                "checks": (r.get("eval_checks") or {}).get(v["task"]),
                "screenshots": len(glob.glob(f"{d}/{a}-step*.png")),
            }
        vals = [x["score"] for x in rec["agents"].values()]
        rec["all_pass"] = bool(vals) and all(s is not None and s >= PASS for s in vals)
        print(json.dumps(rec))


if __name__ == "__main__":
    main()
