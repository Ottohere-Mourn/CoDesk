"""m4 - one Thunderbird: HTML customer newsletter (template + draft) vs the customer-support queue.

Both tasks start in the same Thunderbird main window (Hana Kim, hello@fernandfennel.shop). The unsubscribe and
address-change requests task A must honour are support e-mails that task B answers and moves to Support/Done;
both have composer windows open at the same time and save into the same Drafts folder.
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import (HOME, expected, fetch, mail_folders, result,
                                                      start_thunderbird, upload)
from evaluation_examples.task_class.pg_mcommon import (account_path, addrs, draft_replies, html_parts, norm,
                                                       raw_messages, where, xlsx_rows)

LOG = f"{HOME}/Documents/support_log.xlsx"
FILES = ["Pictures/newsletter/monstera_dec.jpg", "Pictures/newsletter/planter_speckled_L.jpg",
         "Pictures/newsletter/marble_queen_basket.jpg", "Pictures/newsletter/monstera_2025.jpg",
         "Pictures/newsletter/planter_speckled_S.jpg", "Pictures/newsletter/pothos_golden.jpg",
         "Documents/KB/Support_Macros.docx", "Documents/customers.csv"]


def setup(sc):
    upload(sc, [(f"m4/{f}", f"{HOME}/{f}") for f in FILES])
    start_thunderbird(sc, "m4/thunderbird-profile.tar.gz", "pgm4")


# ---------------------------------------------------------------- A: newsletter
def _content(m, exp):
    p = html_parts(m)
    md5s = {i["md5"]: i for i in p["images"]}
    names = {i["filename"].lower(): i for i in p["images"]}
    photos = {}
    for fn, h in exp["photo_md5"].items():
        img = md5s.get(h) or names.get(fn.lower())
        photos[fn] = bool(img) and img["referenced"]  # embedded in the HTML, not just attached
    decoys = sum(h in md5s for h in exp["decoy_md5"].values()) + sum(
        fn.lower() in names for fn in exp["decoy_md5"])
    hrefs = [h.strip().rstrip("/").lower() for h in p["hrefs"]]
    links = {pr["key"]: pr["url"].lower() in hrefs for pr in exp["products"]}
    unsub = exp["unsub_url"].lower() in hrefs
    text = p["text"]
    prices = {}
    for pr in exp["products"]:  # "$34.00" may be written "$34"; "$28.50" needs its cents
        dollars, cents = pr["price"].lstrip("$").split(".")
        pat = rf"\$\s?{dollars}([.,]{cents})" + ("?" if cents == "00" else "") + r"(?!\d)"
        prices[pr["key"]] = bool(re.search(pat, text))
    names_ok = sum(norm(pr["name"])[:14] in norm(text) for pr in exp["products"])
    return {"html": bool(p["html"]), "photos": photos, "decoy_images": decoys, "links": links, "unsubscribe": unsub,
            "prices": prices, "names": names_ok, "coupon": exp["coupon"] in text.upper()}


def evaluate_newsletter(env, dest: str) -> dict:
    exp = expected("m4")
    raw = raw_messages(env, ("drafts", "templates"))
    subj = norm(exp["subject"])

    def pick(leaf):
        ms = [m for f, msgs in raw.items() if f.rsplit("/", 1)[-1].lower() == leaf for m in msgs
              if "decemberpicks" in norm(str(m["Subject"] or ""))]
        return ms[-1] if ms else None

    draft, tmpl = pick("drafts"), pick("templates")
    checks = {"draft": bool(draft), "template": bool(tmpl),
              "subject_exact": bool(draft) and norm(str(draft["Subject"])) == subj}
    score = 0.05 * bool(draft)
    if tmpl:
        c = _content(tmpl, exp)
        tmpl_ok = sum(c["photos"].values()) == 3 and all(c["links"].values())
        checks["template_layout"] = tmpl_ok
        score += 0.08 + 0.07 * tmpl_ok
    main = draft or tmpl
    if main:
        c = _content(main, exp)
        checks["content"] = c
        score += (0.06 * sum(c["photos"].values()) - 0.03 * min(c["decoy_images"], 3)
                  + 0.05 * sum(c["links"].values()) + 0.04 * c["unsubscribe"]
                  + 0.03 * sum(c["prices"].values()) + 0.04 * c["coupon"] + 0.05 * c["names"] / 3)
    if draft:
        bcc, to = addrs(str(draft["Bcc"] or "")), addrs(str(draft["To"] or "")) | addrs(str(draft["Cc"] or ""))
        want = set(exp["recipients"])
        customers = set(a.lower() for a in exp["all_customers"]) | want
        exposed = sorted(to & customers)
        tp, fp = len(bcc & want), len(bcc - want)
        rec = max(0.0, (tp - fp) / len(want)) if not exposed else 0.0
        checks["recipients"] = {"bcc": len(bcc), "correct": tp, "missing": sorted(want - bcc)[:6],
                                "should_not_get_it": sorted(bcc - want)[:6], "customers_in_to_or_cc": exposed[:4],
                                "to_self": exp["me"] in to}
        score += 0.25 * rec
    else:
        score = min(score, 0.5)
    return result(max(0.0, score), checks)


# ---------------------------------------------------------------- B: support
def evaluate_support(env, dest: str) -> dict:
    exp = expected("m4")
    boxes = mail_folders(env)
    if boxes is None:
        return result(0.0, {"mail": "unreadable"})
    loc = where(boxes)
    phrases = exp["macros"]
    support = [m for m in exp["mails"] if m["kind"] == "support"]
    per, score = {}, 0.0
    raw = raw_messages(env, ("drafts",))
    for m in support:
        ds = draft_replies(env, m["id"], m["from"], raw=raw)
        text = " ".join(d["text"] for d in ds).lower()  # own words: the quoted customer mail does not count
        used = {c for c, ph in phrases.items() if ph.lower() in text}
        macro_ok = used == {m["macro"]}
        order_ok = m["order"] is None or m["order"].lower() in text
        paths = {account_path(f) for f, _ in loc.get(m["id"], [])}
        moved = paths == {"support/done"}
        per[m["key"]] = {"reply": bool(ds), "macro": macro_ok, "order_no": order_ok if m["order"] else None,
                         "done_folder": moved, "macros_found": sorted(used)}
        score += 0.015 * bool(ds) + 0.03 * macro_ok + (0.02 * order_ok if m["order"] else 0) + 0.015 * moved
    junk = {}
    for m in exp["mails"]:
        if m["kind"] == "junk":
            paths = {account_path(f) for f, _ in loc.get(m["id"], [])}
            junk[m["key"]] = 1.0 if paths and all(p.endswith("junk") for p in paths) else (
                0.5 if not paths or all(p.endswith("trash") for p in paths) else 0.0)
    score += 0.04 * sum(junk.values())
    others = [m for m in exp["mails"] if m["kind"] == "other"]
    kept = sum({account_path(f) for f, _ in loc.get(m["id"], [])} == {"inbox"} for m in others)
    progress = any(p["done_folder"] or p["reply"] for p in per.values())
    score += 0.04 * (progress and kept == len(others))

    path = fetch(env, LOG, dest + ".xlsx")
    rows = xlsx_rows(path) if path else []
    log = {}
    for m in support:
        mrows = [r for r in rows if any(m["from"] in str(c).lower() for c in r if c is not None)]
        cells = [str(c) for r in mrows for c in r if c is not None]
        macro = any(norm(m["macro"]) == norm(c) or norm(m["macro"]) in norm(c) for c in cells)
        order = m["order"] is None or any(m["order"].lower() in c.lower() for c in cells)
        log[m["key"]] = {"row": bool(mrows), "macro": macro, "order": order if m["order"] else None}
        score += 0.014 * (bool(mrows) and macro) + (0.015 * (bool(mrows) and order) if m["order"] else 0)
    if not path:
        score = min(score, 0.7)
    checks = {"support": per, "junk": junk, "non_support_left_in_inbox": f"{kept}/{len(others)}",
              "log_rows": len(rows), "log": log}
    return result(score, checks)
