"""W2 - one expense portal (Fenwick Spend on :8102) in one Chrome session: deciding the 12 reports waiting for Dana's
approval vs filing Dana's own Chicago trip report and exporting the department's approved reports. See spec_w2.md."""
from __future__ import annotations

import csv
import io
import re

from evaluation_examples.task_class.pg_common import (HOME, expected, fetch, open_chrome, result, sh, sql,
                                                      start_webapp, upload, webapp_db)

NAME, PORT = "w2", 8102
URL = f"http://127.0.0.1:{PORT}/"
POLICY = "Fenwick_TE_Policy_2026.pdf"


def setup(sc):
    exp = expected(NAME)
    start_webapp(sc, f"{NAME}/app_w2.py", NAME, PORT, f"{NAME}/seed.db")
    cache = f"{HOME}/.cache/pg{NAME}"
    upload(sc, [(f"{NAME}/{POLICY}", f"{cache}/Documents/{POLICY}")]
           + [(f"{NAME}/Downloads/{f}", f"{cache}/Downloads/{f}") for f in exp["downloads"]])
    # copy the documents only once: setup runs again before the second task of a sequential run
    sh(sc, f"mkdir -p ~/Documents ~/Downloads && [ -f {cache}/.placed ] || {{ cp -n {cache}/Documents/* ~/Documents/ && "
           f"cp -n {cache}/Downloads/* ~/Downloads/ && touch {cache}/.placed; }}")
    open_chrome(sc, [URL])


def _state(env, exp):
    return sql(env, webapp_db(NAME), {
        "reports": "SELECT r.id, r.employee_id, r.title, r.status, r.submitted, r.decided, r.decided_by, r.comment, "
                   "e.department FROM reports r JOIN users e ON e.id=r.employee_id",
        "lines": "SELECT l.id, l.report_id, l.date, l.category, l.merchant, l.amount, l.attendees, c.md5 FROM lines l "
                 f"LEFT JOIN receipts c ON c.id=l.receipt_id WHERE l.report_id > {exp['seed_max_report']}",
        "totals": "SELECT report_id, ROUND(SUM(amount), 2) AS tot FROM lines GROUP BY report_id"})


def _text(env, path, dest):
    p = fetch(env, f"{HOME}/{path}", dest)
    if not p:
        return None
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


# ---------------------------------------------------------------- task A: approvals
def evaluate_approve(env, dest: str) -> dict:
    exp = expected(NAME)
    st = _state(env, exp)
    if not st:
        return result(0.0, {"app_db": "unreadable"})
    reps = {str(r["id"]): r for r in st["reports"]}
    checks, score, decided, wrong = {}, 0.0, 0, []
    app_dec = {}
    for rid, want in exp["pending"].items():
        r = reps.get(rid, {})
        status = r.get("status")
        by_dana = r.get("decided_by") == exp["dana_id"]
        app_dec[rid] = status if by_dana else None
        decided += status in ("Approved", "Rejected")
        target = "Approved" if want["decision"] == "approve" else "Rejected"
        ok = status == target and by_dana
        reason_ok = None
        if want["decision"] == "approve":
            score += 0.04 * ok
        else:
            score += 0.08 * ok
            reason_ok = bool(ok and re.search(want["reason"], r.get("comment") or "", re.I))
            score += 0.024 * reason_ok
        if not ok or reason_ok is False:
            wrong.append(f"EXP-{rid}: {status} (want {target})" + ("" if reason_ok in (None, True) else
                                                                  f", comment lacks the reason: {(r.get('comment') or '')[:80]!r}"))
    n = len(exp["pending"])
    checks.update({"decided": f"{decided}/{n}", "wrong": wrong})
    # the summary file, cross-checked with the app
    text = _text(env, exp["summary_path"], dest + ".txt")
    good_lines = 0
    if text:
        lines = text.splitlines()
        for rid, want in exp["pending"].items():
            line = next((ln for ln in lines if re.search(rf"(?<!\d){rid}(?!\d)", ln)), "")
            said = "Rejected" if re.search(r"reject|declin|denied", line, re.I) else ("Approved" if re.search(r"approv", line, re.I) else None)
            target = "Approved" if want["decision"] == "approve" else "Rejected"
            good_lines += said == target == app_dec.get(rid)
        checks["summary_lines_ok"] = f"{good_lines}/{n}"
    else:
        checks["summary"] = "missing"
    score += 0.15 * good_lines / n
    # nothing else decided or changed
    changed = sorted(int(k) for k, s in exp["seed"].items() if k not in exp["pending"] and reps.get(k, {}).get("status") != s["status"])
    checks["other_reports_changed"] = changed
    score += 0.05 * (decided / n) * (not changed)
    if decided < n / 2:
        score = min(score, 0.4)
        checks["cap"] = "fewer than half of the reports decided -> score <= 0.4"
    return result(score, checks)


# ---------------------------------------------------------------- task B: own report + export
def _line_score(line, want):
    got = {"amount": abs((line["amount"] or 0) - want["amount"]) < 0.006, "category": line["category"] == want["category"],
           "date": line["date"] in want["dates"], "merchant": bool(re.search(want["merchant"], line["merchant"] or "", re.I)),
           "receipt": line["md5"] == want["md5"]}
    if "attendees" in want:
        got["attendees"] = line["attendees"] == want["attendees"]
    return got


def _match(lines, wants):
    """Greedy best match of the report's lines to the expected lines; returns ({file: field checks}, extra lines)."""
    pool, out = list(lines), {}
    for w in wants:
        best, bs = None, -1
        for ln in pool:
            g = _line_score(ln, w)
            s = sum(g.values()) + 2 * g["amount"] + 2 * g["receipt"]
            if s > bs:
                best, bs = ln, s
        if best is not None and bs > 0:
            out[w["file"]] = _line_score(best, w)
            pool.remove(best)
        else:
            out[w["file"]] = None
    return out, pool


def _csv_rows(text):
    try:
        dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _num(c):
    try:
        return round(float(re.sub(r"[\s$,]|USD", "", str(c))), 2)
    except ValueError:
        return None


def evaluate_claim(env, dest: str) -> dict:
    exp = expected(NAME)
    st = _state(env, exp)
    if not st:
        return result(0.0, {"app_db": "unreadable"})
    totals = {str(t["report_id"]): t["tot"] for t in st["totals"]}
    mine = [r for r in st["reports"] if r["employee_id"] == exp["dana_id"] and r["id"] > exp["seed_max_report"]]
    checks, score = {}, 0.0
    best, best_s, best_m, best_extra = None, -1.0, None, None
    for r in mine:
        lines = [ln for ln in st["lines"] if ln["report_id"] == r["id"]]
        m, extra = _match(lines, exp["b_lines"])
        s = sum(sum(v.values()) / len(v) for v in m.values() if v) + 0.5 * (r["status"] == "Submitted")
        if s > best_s:
            best, best_s, best_m, best_extra = r, s, m, extra
    if best:
        title_ok = bool(re.search(r"chicago", best["title"] or "", re.I) and re.search(r"kestrel", best["title"] or "", re.I))
        lines_part = sum(sum(v.values()) / len(v) for v in best_m.values() if v) / len(exp["b_lines"])
        tot = totals.get(str(best["id"]))
        wine = [ln["amount"] for ln in st["lines"] if ln["report_id"] == best["id"]
                and min(abs(ln["amount"] - exp["dinner_full"]), abs(ln["amount"] - exp["dinner_wine"])) < 0.006]
        checks.update({"report": f"EXP-{best['id']} {best['title']!r}", "title_ok": title_ok, "status": best["status"],
                       "lines": best_m, "extra_lines": [(x["merchant"], x["amount"]) for x in best_extra],
                       "total": tot, "claimed_wine": bool(wine)})
        score += 0.08 * (best["status"] == "Submitted") + 0.02 * title_ok + 0.5 * lines_part
        score += 0.05 * (not best_extra and all(best_m.values())) + 0.05 * (tot is not None and abs(tot - exp["b_total"]) < 0.006)
    else:
        checks["report"] = "no new report by Dana"
    # the export
    text = _text(env, exp["csv_path"], dest + ".csv")
    if text:
        approved_now = {r["id"] for r in st["reports"] if r["status"] == "Approved" and (r["submitted"] or "")[:7] == "2026-10"
                        and r["department"] == "Marketing"}
        ids, tot_ok = set(), True
        for row in _csv_rows(text):
            m = next((re.search(r"EXP-?(\d{4,})", c, re.I) for c in row if re.search(r"EXP-?\d{4,}", c, re.I)), None)
            if not m:
                continue
            rid = int(m.group(1))
            ids.add(rid)
            want = totals.get(str(rid))
            tot_ok &= want is not None and any(_num(c) is not None and abs(_num(c) - want) < 0.006 for c in row)
        seed = set(exp["seed_approved_oct_marketing"])
        superset, subset = seed <= ids, bool(ids) and ids <= approved_now
        checks.update({"csv_reports": sorted(ids), "csv_has_all_seed_approved": superset,
                       "csv_only_approved_oct_marketing": subset, "csv_not_in_scope": sorted(ids - approved_now),
                       "csv_totals_match_app": bool(ids) and tot_ok})
        # rows outside the scope (wrong or stale filter) void the scope and totals credit
        score += 0.05 * bool(ids) + (0.2 if superset and subset else 0.1 if subset else 0.0) + 0.05 * (subset and tot_ok)
    else:
        checks["csv"] = "missing"
    if not best:
        score = min(score, 0.3)
        checks["cap"] = "no expense report filed -> score <= 0.3"
    return result(score, checks)
