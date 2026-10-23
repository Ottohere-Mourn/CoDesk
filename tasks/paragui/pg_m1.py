"""m1 - one Thunderbird: project mail rules (folders, tags, ordered filters, run on the Inbox) vs vendor-quote comparison.

Both tasks start in the same Thunderbird main window (Sofia Marquez, sofia.marquez@larchmontdg.com). The quote e-mails
task B needs carry "[RLP]" in the subject, so task A's filters move (and tag) them while B reads them.
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import (HOME, expected, fetch, mail_folders, result, sh,
                                                      start_thunderbird, tree)
from evaluation_examples.task_class.pg_mcommon import (account_path, draft_replies, filters_for, has_amount, norm,
                                                       number_near, profile_state, raw_messages, simulate, tag_names,
                                                       to_date, to_number, where, xlsx_rows)

RLP = f"{HOME}/Documents/RLP"
WORKBOOK = f"{RLP}/Furniture_Quotes.xlsx"
WORDS = "zero one two three four five six seven eight nine ten eleven twelve".split()


def setup(sc):
    start_thunderbird(sc, "m1/thunderbird-profile.tar.gz", "pgm1")
    sh(sc, "mkdir -p ~/Documents")


# ---------------------------------------------------------------- A: mail rules
def evaluate_rules(env, dest: str) -> dict:
    exp = expected("m1")
    state, boxes = profile_state(env), mail_folders(env)
    if not state or boxes is None:
        return result(0.0, {"profile": "unreadable"})
    tags = state.get("tags", {})
    names = {str(v).strip().lower() for v in tags.values()}
    rlp_tags = {t.lower() for t in exp["tags"]}
    have_folders = {f.split("/", 1)[1].lower() for f in state.get("folders", []) if "/" in f}
    folders_ok = [f.lower() in have_folders for f in exp["folders"]]

    filters = filters_for(state, exp["host"])
    # probes: project mail must be routed; non-project probes only count once some routing works
    pos_ok, neg_ok, manual_ok, probe_log = 0, 0, 0, []
    for p in exp["probes"]:
        mail = {"from": p["from"], "subject": p["subject"], "to": exp["me"], "body": ""}
        want = (p["folder"].lower(), {t.lower() for t in p["tags"]}, p["flagged"])
        for new_mail in (True, False):
            st = simulate(filters, mail, tags, new_mail=new_mail)
            got = (st["folder"], st["tags"] & rlp_tags, st["flagged"])
            if new_mail:
                if p["folder"] == "Inbox":
                    neg_ok += got == want
                else:
                    pos_ok += got == want
                if got != want:
                    probe_log.append(f"{p['subject'][:30]} -> {got[0]} {sorted(got[1])} flag={got[2]}")
            else:
                manual_ok += got == want
    n_probe = len(exp["probes"])
    probe_ok = pos_ok + (neg_ok if pos_ok else 0)

    loc = where(boxes)
    placed, tagged, moved_wrongly, misplaced = 0, 0, 0, []
    project = [e for e in exp["existing"] if e["folder"] != "Inbox"]
    others = [e for e in exp["existing"] if e["folder"] == "Inbox"]
    for e in exp["existing"]:
        copies = loc.get(e["id"], [])
        paths = {account_path(f) for f, _ in copies}
        good = paths == {e["folder"].lower()}
        if e["folder"] != "Inbox":
            placed += good
        else:
            moved_wrongly += not good
        if not good:
            misplaced.append(f"{e['subject'][:36]} -> {sorted(paths)}")
        if e["folder"] != "Inbox" and good:
            m = copies[0][1]
            tagged += (tag_names(m["keys"], tags) & rlp_tags == {t.lower() for t in e["tags"]}
                       and m["flagged"] == e["flagged"])

    reply = draft_replies(env, exp["policy_id"], exp["daniel"])
    counts = exp["counts"]
    count_ok = []
    if reply:
        text = reply[-1]["text"]  # own words only: the quoted memo e-mail does not count
        for key, folder in (("invoice", "Riverside Library/Invoices"), ("client", "Riverside Library/Client"),
                            ("consultant", "Riverside Library/Consultants")):
            count_ok.append(number_near(text, key) == counts[folder])
        # the top-level folder has no distinctive keyword ("Riverside Library" prefixes every path): any mention
        root = counts["Riverside Library"]
        count_ok.append(bool(re.search(rf"\b({root}|{WORDS[root]})\b", text.lower())))

    checks = {
        "tag_RLP": "rlp" in names, "tag_RLP_Billing": "rlp billing" in names,
        "folders": f"{sum(folders_ok)}/{len(folders_ok)}",
        "filters": [f"{f['name']}: {f['raw_condition'][:60]} -> {[a for a, _ in f['actions']]}" for f in filters][:8],
        "probes_new_mail": f"{pos_ok}+{neg_ok}/{n_probe}", "probes_manual": f"{manual_ok}/{n_probe}",
        "probe_failures": probe_log[:8],
        "existing_placed": f"{placed}/{len(project)}", "other_mail_moved": f"{moved_wrongly}/{len(others)}",
        "existing_tagged": f"{tagged}/{len(project)}",
        "misplaced": misplaced[:10], "reply_draft": bool(reply), "reply_counts": count_ok,
    }
    score = (0.04 * ("rlp" in names) + 0.04 * ("rlp billing" in names) + 0.04 * sum(folders_ok) / len(folders_ok)
             + 0.32 * probe_ok / n_probe + 0.04 * (manual_ok == n_probe)
             + 0.22 * max(0.0, placed / len(project) - 0.5 * moved_wrongly / len(others))
             + 0.10 * tagged / len(project)
             + 0.05 * bool(reply) + 0.15 * (sum(count_ok) / 4 if count_ok else 0))
    if pos_ok == 0:  # mail sorted by hand, no working rules: the primary deliverable is missing
        score = min(score, 0.4)
    return result(score, checks)


# ---------------------------------------------------------------- B: quotes
def _cells(row):
    return [c for c in row if c not in (None, "")]


def _vendor_row_score(row, v, key):
    cells = _cells(row)
    total = any(to_number(c) is not None and abs(to_number(c) - v["total"]) < 0.02 for c in cells)
    quote = any(norm(v["quote"]) in norm(str(c)) for c in cells)  # "Q-2291" alone does not contain "q2291r1"
    want = to_date(v["date"])
    dates = [to_date(c) for c in cells if not isinstance(c, (int, float)) or 40000 < c < 60000]
    if key == "benchmark":  # "estimated delivery week of 7 December"
        date = any(d is not None and 0 <= (d - want).days <= 4 for d in dates)
    else:
        date = want in dates
    warranty = any((isinstance(c, (int, float)) and not isinstance(c, bool) and float(c) == v["warranty"])
                   or re.fullmatch(rf"\s*{v['warranty']}\s*(years?|yrs?|y)?\s*", str(c), re.I) is not None
                   for c in cells)
    flags = [str(c).strip().lower() for c in cells if str(c).strip().lower() in
             ("y", "yes", "n", "no", "true", "false", "meets", "does not meet")]
    meets = bool(flags) and (flags[-1] in ("y", "yes", "true", "meets")) == v["meets"]
    return {"total": total, "quote": quote, "date": date, "warranty": warranty, "meets": meets}


def evaluate_quotes(env, dest: str) -> dict:
    exp = expected("m1")
    files = tree(env, [RLP])
    in_quotes = {h for p, h in files.items() if p.startswith("Documents/RLP/Quotes/")}
    pdfs = sum(h in in_quotes for h in exp["pdfs"].values())

    path = fetch(env, WORKBOOK, dest + ".xlsx")
    rows = xlsx_rows(path) if path else []
    per_vendor, one_row_each = {}, True
    for key, v in exp["vendors"].items():
        kw = {"northline": "northline", "benchmark": "benchmark", "lumen": "lumen", "ashford": "ashford"}[key]
        vrows = [r for r in rows if any(kw in str(c).lower() for c in _cells(r))]
        one_row_each &= len(vrows) == 1
        scored = [_vendor_row_score(r, v, key) for r in vrows]
        per_vendor[key] = max(scored, key=lambda s: sum(s.values())) if scored else \
            {"total": False, "quote": False, "date": False, "warranty": False, "meets": False}
        # listing the superseded Q-2291 next to the revision is a wrong total for Northline
        if key == "northline" and vrows and any(to_number(c) is not None and abs(to_number(c) - exp["northline_original_total"]) < 0.02
                                                for r in vrows for c in _cells(r)):
            per_vendor[key]["total"] = per_vendor[key]["total"] and len(vrows) == 1
    agg = {k: sum(per_vendor[v][k] for v in per_vendor) for k in ("total", "quote", "date", "warranty", "meets")}

    raw = raw_messages(env, ("drafts",))
    winner = exp["winner"]
    w = exp["vendors"][winner]
    vendor_drafts = {k: draft_replies(env, ids, exp["vendors"][k]["email"], raw=raw)
                     for k, ids in exp["vendor_ids"].items()}
    vd = vendor_drafts[winner]
    vtext = " ".join(m["text"] for m in vd)  # the quoted quote e-mail / "Re:" subject do not count
    v_content = bool(re.search(r"Q-?\s?2291\s?-?\s?R1", vtext, re.I)) and exp["po"].lower() in vtext.lower()
    wrong_vendor = [k for k, ds in vendor_drafts.items() if ds and k != winner]
    dd = draft_replies(env, exp["furniture_id"], exp["daniel"], raw=raw)
    dtext = " ".join(m["text"] for m in dd)
    d_content = "northline" in dtext.lower() and has_amount(dtext, w["total"])

    checks = {"pdfs_saved": f"{pdfs}/{len(exp['pdfs'])}", "workbook": bool(path), "rows": len(rows),
              "per_vendor": per_vendor, "one_row_per_vendor": one_row_each,
              "vendor_draft": bool(vd), "vendor_draft_quote_and_po": v_content, "drafts_to_other_vendors": wrong_vendor,
              "daniel_draft": bool(dd), "daniel_draft_winner_total": d_content}
    score = (0.12 * pdfs / len(exp["pdfs"])
             + 0.16 * agg["total"] / 4 + 0.08 * agg["quote"] / 4 + 0.06 * agg["date"] / 4
             + 0.06 * agg["warranty"] / 4 + 0.08 * agg["meets"] / 4 + 0.04 * (one_row_each and bool(rows))
             + 0.10 * bool(vd) + 0.12 * (bool(vd) and v_content)
             + 0.06 * bool(dd) + 0.12 * (bool(dd) and d_content))
    if not path:
        score = min(score, 0.4)
    if wrong_vendor:  # accepted a vendor that fails the criteria (or two vendors at once)
        score = min(score, 0.5)
    return result(score, checks)
