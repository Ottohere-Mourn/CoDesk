#!/usr/bin/env python3
"""Summarise paraGUI dataset v1 from build_index.py output (one or more jsonl files, e.g. one per node).

    python3 analyze_v1.py idx_node0.jsonl idx_node1.jsonl [--md out.md]

Per pair and mode (solo / seq / par / sg): runs, both-pass rate (both tasks >= 0.8), mean task score, give-up rate,
plus outcome classes of the failed tasks. Placeholder runs that were moved to the other node are skipped; for a run
name present on both nodes the one with a real result wins.
"""
import collections
import json
import statistics as st
import sys

PASS = 0.8
FAMILY = {"c": "C (round 1, revised)", "m": "F2 mail/calendar", "o": "F1 office docs", "w": "F3 browser + intranet app",
          "d": "F4 developer", "f": "F5 files/media", "x": "F6 cross-app"}


def load(paths):
    runs = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            if not r.get("agents") or r.get("error"):  # placeholders, infra failures without scores
                continue
            if any(a["score"] is None for a in r["agents"].values()):
                continue
            runs[r["run"]] = r
    return list(runs.values())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    md_path = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None
    if md_path in args:
        args.remove(md_path)
    runs = load(args)
    by = collections.defaultdict(list)
    for r in runs:
        by[(r["pair"], r["mode"])].append(r)
    lines = []
    out = lines.append
    out("| pair | solo: tasks passed | seq: both pass | par: both pass | sg: both pass | par+sg: a task gave up |")
    out("|---|---|---|---|---|---|")
    totals = collections.defaultdict(lambda: [0, 0])
    gave_up = [0, 0]
    outcomes = collections.Counter()
    for pair in sorted({r["pair"] for r in runs}, key=lambda p: (p[0] != "c", p)):
        cells = []
        solo = by.get((pair, "solo"), [])
        sp = sum(a["score"] >= PASS for r in solo for a in r["agents"].values())
        cells.append(f"{sp}/{len(solo)}")
        for mode in ("seq", "par", "sg"):
            rs = by.get((pair, mode), [])
            ok = sum(r["all_pass"] for r in rs)
            totals[mode][0] += ok
            totals[mode][1] += len(rs)
            cells.append(f"{ok}/{len(rs)}" if rs else "-")
        conc = by.get((pair, "par"), []) + by.get((pair, "sg"), [])
        gu = sum(any(a["status"] == "fail" for a in r["agents"].values()) for r in conc)
        gave_up[0] += gu
        gave_up[1] += len(conc)
        cells.append(f"{gu}/{len(conc)}" if conc else "-")
        for r in conc:
            for a in r["agents"].values():
                if a["score"] < PASS:
                    outcomes[(r["mode"], a["outcome"])] += 1
        out(f"| {pair} | " + " | ".join(cells) + " |")
    tot = {m: f"{v[0]}/{v[1]} ({100 * v[0] / v[1]:.0f}%)" if v[1] else "-" for m, v in totals.items()}
    out(f"| **all** | | **{tot.get('seq')}** | **{tot.get('par')}** | **{tot.get('sg')}** | "
        f"**{gave_up[0]}/{gave_up[1]}** |")
    out("")
    out("Failed tasks in concurrent runs (score < 0.8), by outcome:")
    out("")
    out("| outcome | par | sg |")
    out("|---|---|---|")
    for oc in sorted({o for _, o in outcomes}):
        out(f"| {oc} | {outcomes[('par', oc)]} | {outcomes[('sg', oc)]} |")
    steps = [a["steps"] for r in runs if r["mode"] == "solo" for a in r["agents"].values()]
    if steps:
        out("")
        out(f"Solo steps: median {st.median(steps)}, range {min(steps)}-{max(steps)}; "
            f"runs analysed: {len(runs)} ({collections.Counter(r['mode'] for r in runs)})")
    text = "\n".join(lines)
    print(text)
    if md_path:
        open(md_path, "w").write(text + "\n")


if __name__ == "__main__":
    main()
