"""F2 - a bakery's scanned paperwork: filing the scans (file) vs the accounts-payable three-way match (match).

Shared live state: one LibreOffice Calc window with bookkeeping_2026-10.xlsx (task A fills "Document register",
task B fills "AP check" and reads "PO list" - same open document), one Nautilus window on the scans folder; task A
moves/renames/deletes exactly the scans task B has to read (invoices, delivery notes, a duplicate scan).
"""
from __future__ import annotations

import os
import re

from evaluation_examples.task_class.pg_common import HOME, expected, fetch, result, sh, tree, upload
from evaluation_examples.task_class import pg_fimg as fi

SCANS = f"{HOME}/Documents/Scans/2026-10"
WB = f"{HOME}/Documents/Bookkeeping/bookkeeping_2026-10.xlsx"
MEMO = f"{HOME}/Documents/Bookkeeping/supplier_queries.txt"
TYPES = ["Invoices", "Credit notes", "Receipts", "Delivery notes", "Utilities", "Letters"]


def setup(sc):
    upload(sc, [("f2/f2.tar.gz", "/tmp/pgf2.tar.gz")])
    sh(sc, "mkdir -p ~/.cache; [ -f ~/.cache/.pgf2_ready ] || { tar xzf /tmp/pgf2.tar.gz -C ~ && "
           "touch ~/.cache/.pgf2_ready; }; rm -f /tmp/pgf2.tar.gz")
    sc.launch(f"[ -e /tmp/.pgf2_nautilus ] || {{ touch /tmp/.pgf2_nautilus; exec nautilus '{SCANS}'; }}", shell=True)
    sc._open_setup(WB)


def _workbook(env, dest):
    return fetch(env, WB, dest + ".xlsx") or fetch(env, WB[:-5] + ".ods", dest + ".ods")


# ---------------------------------------------------------------- task A: file the scans
def _name_ok(name: str, d: dict) -> bool:
    """YYYY-MM-DD_<Vendor>_<number>.pdf with the document's date, issuer's first word and number (any separators)."""
    m = re.match(rf"^{d['date']}_{re.escape(d['vendor'].lower())}_(.+)\.pdf$", name.strip().lower())
    return bool(m) and fi.alnum(d["docno"]) in fi.alnum(m.group(1))


def evaluate_file(env, dest: str) -> dict:
    exp = expected("f2")
    docs = [d for d in exp["docs"] if d["kind"] == "doc"]
    junk = [d for d in exp["docs"] if d["kind"] != "doc"]
    t = tree(env, ["~/Documents"])
    by_md5 = {}
    for p, m in t.items():
        by_md5.setdefault(m, []).append(p)
    filed = named = 0
    detail = []
    for d in docs:
        folder = f"documents/paperwork/2026/{d['type'].lower()}/"
        hits = [p for p in by_md5.get(d["md5"], []) if p.lower().startswith(folder)]
        ok_name = any(_name_ok(os.path.basename(p), d) for p in hits)
        filed += bool(hits)
        named += ok_name
        if not (hits and ok_name):
            detail.append([d["scan"], d["new_name"], [p for p in by_md5.get(d["md5"], [])][:2]])
    junk_gone = sum(not by_md5.get(d["md5"]) for d in junk)
    left = [p for p in t if p.startswith("Documents/Scans/2026-10/")]
    # the register
    path = _workbook(env, dest)
    _, rows = fi.table(fi.sheet_rows(path, "Document register"), "File name")
    reg = {}
    for r in rows:
        reg.setdefault(fi.alnum(r.get("doc no")), r)
    r_date = r_type = r_total = r_file = 0
    wrong = []
    for d in docs:
        r = reg.get(fi.alnum(d["docno"]))
        if r is None:
            r = next((x for k, x in reg.items() if k and (fi.alnum(d["docno"]) in k)), None)
        if r is None:
            wrong.append([d["docno"], "missing"])
            continue
        a = fi.iso_date(r.get("date")) == d["date"]
        b = fi.alnum(r.get("type"))[:6] == fi.alnum(d["type"])[:6]
        v = fi.num(r.get("total"))
        c = (v is not None and abs(abs(v) - d["total"]) < 0.011) if d["total"] is not None else (v in (None, 0.0))
        e = _name_ok(os.path.basename(fi.cell_text(r.get("file name")).replace("\\", "/")), d)
        r_date += a
        r_type += b
        r_total += c
        r_file += e
        if not (a and b and c and e):
            wrong.append([d["docno"], r.get("date"), r.get("type"), r.get("total"), r.get("file name")])
    n = len(docs)
    sheets = {s.strip().lower() for s in fi.sheet_names(path)} if path else set()
    intact = {"document register", "ap check", "po list"} <= sheets
    score = (0.25 * filed / n + 0.25 * named / n + 0.10 * junk_gone / len(junk) + 0.05 * (not left)
             + 0.10 * r_date / n + 0.05 * r_type / n + 0.15 * r_total / n + 0.05 * r_file / n)
    if not filed:
        score = min(score, 0.3)
    if path and not intact:
        score = min(score, 0.7)
    checks = {"filed": f"{filed}/{n}", "named": f"{named}/{n}", "blank_and_duplicate_deleted": f"{junk_gone}/{len(junk)}",
              "left_in_scans": left[:6], "not_ok": detail[:8], "register_date": f"{r_date}/{n}",
              "register_type": f"{r_type}/{n}", "register_total": f"{r_total}/{n}", "register_file": f"{r_file}/{n}",
              "register_wrong": wrong[:8], "sheets": sorted(sheets)}
    return result(score, checks)


# ---------------------------------------------------------------- task B: three-way match
def _issue_ok(text: str, issues: list) -> bool:
    """The Issue cell names exactly the expected problems (price / qty / not on PO); empty or 'OK' for clean lines."""
    s = text.lower()
    if re.match(r"^\s*(ok|none|n/?a|-+|fine|match|no issue|correct)\b", s) or not s.strip():
        return not issues
    flags = set()
    if re.search(r"price", s):
        flags.add("price")
    if re.search(r"qty|quant|short|receiv|deliver", s):
        flags.add("qty")
    if re.search(r"not\s*(on|in)\s*(the\s*)?po|not\s*ordered|no\s*po\b|unordered|never\s*ordered", s):
        flags.add("not on PO")
    return flags == set(issues)


def evaluate_match(env, dest: str) -> dict:
    exp = expected("f2")
    lines = exp["ap_lines"]
    path = _workbook(env, dest)
    _, rows = fi.table(fi.sheet_rows(path, "AP check"), "Item")
    rows = [r for r in rows if fi.cell_text(r.get("item")) or fi.cell_text(r.get("invoice no"))]
    used, ok_lines, detail = set(), 0, []
    ok_issue = {"problem": 0, "clean": 0}
    qty_found = 0
    for ln in lines:
        hit = None
        for i, r in enumerate(rows):
            if i in used:
                continue
            if fi.alnum(r.get("invoice no")) == fi.alnum(ln["invoice"]) and ln["kw"] in fi.cell_text(r.get("item")).lower():
                hit = i
                break
        if hit is None:
            detail.append([ln["invoice"], ln["item"], "missing"])
            continue
        used.add(hit)
        r = rows[hit]
        q, p, tot = fi.num(r.get("qty")), fi.num(r.get("unit price")), fi.num(r.get("line total"))
        vals = (q == ln["qty"] and p is not None and abs(p - ln["price"]) < 0.006 and tot is not None
                and abs(tot - ln["total"]) < 0.011 and fi.alnum(r.get("po no")) == fi.alnum(ln["po"]))
        iss = _issue_ok(fi.cell_text(r.get("issue")), ln["issues"])
        ok_lines += vals
        ok_issue["problem" if ln["issues"] else "clean"] += iss
        qty_found += iss and "qty" in ln["issues"]
        if not (vals and iss):
            detail.append([ln["invoice"], ln["item"], r.get("qty"), r.get("unit price"), r.get("line total"),
                           r.get("issue"), "want", ln["issues"]])
    extra = [[r.get("invoice no"), r.get("item")] for i, r in enumerate(rows) if i not in used]
    # supplier queries memo
    mp = fetch(env, MEMO, dest + "_queries.txt")
    memo = open(mp, encoding="utf-8", errors="replace").read() if mp else ""
    memo_ok, memo_detail = 0, {}
    for inv, amount in exp["memo"].items():
        if amount <= 0:
            continue
        found = False
        for line in memo.splitlines():
            if fi.alnum(inv) in fi.alnum(line):
                nums = [fi.num(x) for x in re.findall(r"\d[\d,]*\.\d{2}|\d+", line.replace("£", " "))]
                found |= any(v is not None and abs(v - amount) < 0.011 for v in nums)
        memo_ok += found
        memo_detail[inv] = found
    clean = [inv for inv, a in exp["memo"].items() if a <= 0]
    clean_ok = bool(memo) and not any(fi.alnum(inv) in fi.alnum(memo) for inv in clean)
    n_bad = sum(1 for a in exp["memo"].values() if a > 0)
    # PO list must be untouched
    _, po_rows = fi.table(fi.sheet_rows(path, "PO list"), "PO no.")
    po_now = [[fi.cell_text(r.get("po no")), fi.num(r.get("qty ordered")), fi.num(r.get("agreed unit price"))]
              for r in po_rows]
    po_ok = bool(rows) and po_now == [[x[0], float(x[4]), float(x[5])] for x in exp["po_list"]]
    n = len(lines)
    n_prob = sum(1 for ln in lines if ln["issues"])
    score = (0.25 * ok_lines / n + 0.25 * ok_issue["problem"] / n_prob + 0.05 * ok_issue["clean"] / (n - n_prob)
             + 0.05 * (bool(rows) and not extra) + 0.30 * memo_ok / n_bad + 0.05 * clean_ok + 0.05 * po_ok)
    if not rows:
        score = min(score, 0.3)
    qty_invoices = {ln["invoice"] for ln in lines if "qty" in ln["issues"]}
    if not qty_found and not any(memo_detail.get(i) for i in qty_invoices):
        score = min(score, 0.6)  # the received-quantity shortages (handwritten on the delivery notes) were missed
    checks = {"lines_correct": f"{ok_lines}/{n}", "problem_lines_flagged": f"{ok_issue['problem']}/{n_prob}",
              "clean_lines_unflagged": f"{ok_issue['clean']}/{n - n_prob}", "extra_rows": extra[:6],
              "line_problems": detail[:10], "memo_found": bool(mp), "memo_amounts": memo_detail,
              "clean_invoice_not_queried": clean_ok, "po_list_unchanged": po_ok}
    return result(score, checks)
