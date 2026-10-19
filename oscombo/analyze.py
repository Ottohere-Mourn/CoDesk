"""Aggregate run results: success by condition/position, partial-credit means, joint outcomes, steps, interference.

  python -m oscombo analyze OUT_ROOT [--prefix exp1- ...] [--threshold 0.95] [--app v2/052=chrome ...]

Condition = mode + the task's position in the run (``parallel-1`` = started as agent A, ...); solo is ``solo``.
Interference: a keyboard action counts as "into another agent's window" when the focused window right before it
(recorded per action) matches another task's application and not this agent's own. Runs that failed for
infrastructure reasons (no screenshot, VM boot, connection errors) are excluded and listed.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import re

INFRA_MARKERS = ("INFRA", "VM failed", "Connection error", "without previous response")

# window-title patterns per OSWorld app domain
APP_PATTERNS = {
    "chrome": r"Google Chrome|Chrome|Settings|New Tab|chrome://",
    "libreoffice_calc": r"LibreOffice Calc|\.xlsx|\.ods|Format Cells|Row Height",
    "libreoffice_writer": r"LibreOffice Writer|\.docx|\.odt|Paragraph",
    "libreoffice_impress": r"LibreOffice Impress|\.pptx|\.odp",
    "vs_code": r"Visual Studio Code|VS Code|\.txt - |settings\.json",
    "os": r"Files|Trash|Home|Nautilus",
    "thunderbird": r"Thunderbird|Account Settings",
    "gimp": r"GNU Image Manipulation Program|GIMP",
    "vlc": r"VLC media player",
    "blender": r"Blender",
}
# OSWorld 2.0 task classes all live under "v2/"; map the ones used so far to the app their agent works in
V2_APPS = {"052": "chrome", "070": "chrome", "072": "chrome", "073": "chrome", "100": "chrome", "092": "blender"}
KEYBOARD = r"typewrite|write\(|hotkey|press\(|keyDown|type_text\(|key\("


def is_infra(result: dict) -> bool:
    errs = [a.get("error") or "" for a in (result.get("agents") or {}).values()] + [result.get("error") or ""]
    return any(k in e for e in errs for k in INFRA_MARKERS)


def app_of(spec: str, overrides: dict[str, str]) -> str:
    if spec in overrides:
        return overrides[spec]
    domain, _, uid = spec.partition("/")
    return V2_APPS.get(uid, domain) if domain == "v2" else domain


def fisher_one_sided(a: int, n1: int, c: int, n2: int) -> float:
    """P(X <= a) for successes a/n1 vs c/n2 under the hypergeometric null."""
    k, n = a + c, n1 + n2
    return sum(math.comb(k, x) * math.comb(n - k, n1 - x) / math.comb(n, n1)
               for x in range(max(0, k - n2), a + 1))


def load(out: str, prefixes: list[str]) -> tuple[list[dict], list[str]]:
    rows, excluded = [], []
    for f in sorted(glob.glob(os.path.join(out, "*", "result.json"))):
        run_dir = os.path.dirname(f)
        run = os.path.basename(run_dir)
        if prefixes and not run.startswith(tuple(prefixes)):
            continue
        with open(f) as fh:
            r = json.load(fh)
        if is_infra(r) or not r.get("scores"):
            excluded.append(run)
            continue
        trace_path = os.path.join(run_dir, "trace.jsonl")
        trace = [json.loads(line) for line in open(trace_path)] if os.path.exists(trace_path) else []
        rows.append({"run": run, "result": r, "trace": trace})
    return rows, excluded


def task_ids(r: dict) -> list[str]:
    return r.get("task_ids") or [s.split("/")[-1] for s in r["tasks"]]


def analyze(rows: list[dict], threshold: float, apps_override: dict[str, str]) -> dict:
    per = collections.defaultdict(lambda: [0, 0])          # (task, condition) -> [ok, n]
    raw = collections.defaultdict(list)                     # (task, condition) -> scores (partial credit)
    joint = collections.defaultdict(lambda: collections.Counter())  # (combo, mode) -> #tasks solved -> runs
    steps = collections.defaultdict(list)                   # (task, mode) -> steps
    interf = collections.defaultdict(lambda: [0, 0])       # mode -> [keystrokes into another's window, keystrokes]
    for x in rows:
        r = x["result"]
        specs, ids = r["tasks"], task_ids(r)
        apps = [app_of(s, apps_override) for s in specs]
        agents = list((r.get("agents") or {}).values())
        solved = 0
        for pos, (spec, tid) in enumerate(zip(specs, ids)):
            score = r["scores"].get(tid)
            if score is None:  # not evaluated (shadow partner) or the evaluator itself failed: no observation
                continue
            cond = r["mode"] if r["mode"] == "solo" else f"{r['mode']}-{pos + 1}"
            good = score >= threshold
            solved += good
            per[(spec, cond)][0] += good
            per[(spec, cond)][1] += 1
            raw[(spec, cond)].append(score)
            if pos < len(agents):
                steps[(spec, r["mode"])].append(agents[pos]["steps"])
        if r["mode"] not in ("sequential", "parallel"):
            continue
        joint[(" + ".join(sorted(specs)), r["mode"])][solved] += 1
        names = sorted(r.get("agents") or {})
        for rec in x["trace"]:
            if "step" not in rec or rec.get("agent") not in names:
                continue
            me = names.index(rec["agent"])
            own = APP_PATTERNS.get(apps[me], "$^")
            others = [APP_PATTERNS.get(a, "$^") for j, a in enumerate(apps) if j != me and a != apps[me]]
            for act in rec.get("actions", []):
                # keyboard input goes to whatever window is focused; clicks are excluded because the first click
                # of a legitimate app switch starts in the other window
                if not re.search(KEYBOARD, act.get("code", "")):
                    continue
                w = act.get("window_before") or ""
                interf[r["mode"]][1] += 1
                if any(re.search(o, w) for o in others) and not re.search(own, w):
                    interf[r["mode"]][0] += 1
    return {"per": per, "raw": raw, "joint": joint, "steps": steps, "interf": interf}


def report(stats: dict) -> None:
    per, raw = stats["per"], stats["raw"]
    order = {"solo": 0, "sequential": 1, "parallel": 2, "isolated": 3, "shadow": 4}
    conds = sorted({c for _, c in per}, key=lambda c: (order.get(c.split("-")[0], 9), c))
    tasks = sorted({t for t, _ in per})
    w = max([len(t) for t in tasks] + [20])
    print(f"\nsuccess (ok/n)\n{'task':{w}s}" + "".join(f"{c:>15s}" for c in conds))
    for t in tasks:
        print(f"{t:{w}s}" + "".join(f"{(f'{per[(t, c)][0]}/{per[(t, c)][1]}' if per[(t, c)][1] else '-'):>15s}"
                                    for c in conds))
    tot = collections.defaultdict(lambda: [0, 0])
    for (_, c), (k, n) in per.items():
        for key in {c, c.split("-")[0]}:
            tot[key][0] += k
            tot[key][1] += n
    print("\nsuccess by condition:", {c: f"{k}/{n}={k / n:.0%}" for c, (k, n) in sorted(tot.items())})
    s_ok, s_n = tot["solo"][0] + tot["sequential"][0], tot["solo"][1] + tot["sequential"][1]
    if tot["parallel"][1] and s_n:
        p = fisher_one_sided(tot["parallel"][0], tot["parallel"][1], s_ok, s_n)
        print(f"parallel {tot['parallel'][0]}/{tot['parallel'][1]} vs solo+sequential {s_ok}/{s_n}: "
              f"one-sided Fisher p={p:.4f}")
    print(f"\nmean score (partial credit)\n{'task':{w}s}" + "".join(f"{c:>15s}" for c in conds))
    for t in tasks:
        cells = [f"{sum(raw[(t, c)]) / len(raw[(t, c)]):.2f} n={len(raw[(t, c)])}" if raw[(t, c)] else "-"
                 for c in conds]
        print(f"{t:{w}s}" + "".join(f"{c:>15s}" for c in cells))
    agg = collections.defaultdict(list)
    for (_, c), v in raw.items():
        agg[c.split("-")[0]] += v
    print("mean score by mode:", {m: f"{sum(v) / len(v):.3f} (n={len(v)})" for m, v in sorted(agg.items())})
    print("\njoint outcome (#tasks solved -> runs):")
    for k in sorted(stats["joint"]):
        print(f"  {k[1]:10s} {k[0]}  {dict(sorted(stats['joint'][k].items(), reverse=True))}")
    print("\nmedian steps:")
    for k in sorted(stats["steps"]):
        v = sorted(stats["steps"][k])
        print(f"  {k[1]:10s} {k[0]:{w}s} {v[len(v) // 2]} (n={len(v)})")
    print("\nkeystrokes sent while ANOTHER task's app was focused (cross-app combos only):")
    for m, (k, n) in sorted(stats["interf"].items()):
        print(f"  {m:10s} {k}/{n} = {k / max(n, 1):.1%}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="oscombo analyze", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="directory holding one sub-directory per run")
    ap.add_argument("--prefix", action="append", default=[], help="only runs whose name starts with this")
    ap.add_argument("--threshold", type=float, default=0.95, help="score counted as success")
    ap.add_argument("--app", action="append", default=[], metavar="SPEC=APP", help="app of a task spec")
    a = ap.parse_args(argv)
    rows, excluded = load(a.out, a.prefix)
    print(f"runs={len(rows)} excluded(infra/no scores)={len(excluded)} {excluded}")
    report(analyze(rows, a.threshold, dict(x.split("=", 1) for x in a.app)))
    return 0
