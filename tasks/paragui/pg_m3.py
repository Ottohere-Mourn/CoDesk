"""m3 - one Thunderbird: trip itinerary + calendar entries vs inbox reorganisation (folders, archive, stars, saved search).

Both tasks start in the same Thunderbird main window (Lukas Brandt, lukas.brandt@aldervane.de). Task B moves the
booking confirmations task A is reading into Travel (and the client's workshop mail into Projects/Donauwerke),
archives old mail and stars messages, while A saves attachments, works in the Calendar tab and writes a reply.
"""
from __future__ import annotations

import re
from urllib.parse import unquote

from evaluation_examples.task_class.pg_common import (HOME, expected, fetch, mail_folders, result, sh,
                                                      start_thunderbird, tree)
from evaluation_examples.task_class.pg_mcommon import (account_path, calendar_events, doc_text, draft_replies,
                                                       folder_from_uri, has_amount, norm, profile_state, where)

TRAVEL = f"{HOME}/Documents/Travel"
FOLLOWUPS = f"{HOME}/Documents/followups.txt"


def setup(sc):
    start_thunderbird(sc, "m3/thunderbird-profile.tar.gz", "pgm3")
    sh(sc, "mkdir -p ~/Documents")


def _hm(t):
    return t.strftime("%Y-%m-%d %H:%M") if hasattr(t, "hour") else str(t)


# ---------------------------------------------------------------- A: trip
def evaluate_trip(env, dest: str) -> dict:
    exp = expected("m3")
    trip = exp["trip"]
    files = tree(env, [TRAVEL])
    saved = {h for p, h in files.items() if p.startswith("Documents/Travel/")}
    pdfs = sum(h in saved for h in exp["pdfs"].values())

    path = None
    for ext in (".docx", ".odt"):
        path = fetch(env, f"{TRAVEL}/Itinerary_Dec2026{ext}", dest + ext)
        if path:
            break
    text = doc_text(path) if path else ""
    up = text.upper()
    refs = [v["ref"] for v in trip.values()]
    refs_ok = sum(r in up for r in refs)
    times = ["08:24", "12:30", "17:35", "19:25", "19:40", "21:35"]
    times_ok = sum(bool(re.search(t.replace(":", "[:.]"), text)) for t in times)
    stale = bool(re.search(r"17[:.]05", text))
    workshop = "donauwerke" in text.lower() and bool(re.search(r"17[:.]30", text)) and bool(re.search(r"13[:.]00", text))
    conference = "norddata" in text.lower()
    pos = [up.find(r) for r in ("7KQ4MZ", "QX4T7B", "8ZPLMK")]
    hpos = [up.find(r) for r in ("LGW-48213", "NHH-20931")]
    order = min(pos + hpos) >= 0 and pos == sorted(pos) and hpos == sorted(hpos)
    doc = {"file": bool(path), "refs": f"{refs_ok}/5", "times": f"{times_ok}/6", "old_flight_time_present": stale,
           "workshop": workshop, "conference": conference, "chronological": order}
    score = (0.12 * pdfs / 3 + 0.04 * bool(text.strip()) + 0.10 * refs_ok / 5 + 0.08 * times_ok / 6
             + 0.04 * (bool(text.strip()) and not stale and times_ok >= 4) + 0.04 * workshop + 0.02 * conference
             + 0.04 * order)

    events = calendar_events(env, exp["tz"]) or []
    cal = {}
    for key, labels in (("train", ["7kq4mz"]), ("flight1", ["qx4t7b", "os305"]), ("flight2", ["8zplmk", "sk1637"])):
        v = trip[key]
        cands = [e for e in events if not e["allday"] and any(
            lab in norm(e["title"] + " " + e["description"] + " " + e["location"]) for lab in labels)]
        ref_in = [e for e in cands if norm(v["ref"]) in norm(e["title"] + " " + e["description"] + " " + e["location"])]
        timed = [e for e in cands if _hm(e["start"]) == v["start"] and _hm(e["end"]) == v["end"]]
        cal[key] = {"time": bool(timed), "booking_ref": bool(ref_in),
                    "got": [f"{_hm(e['start'])}-{_hm(e['end'])[11:]} {e['title'][:30]}" for e in cands][:3]}
        score += 0.06 * bool(timed) + 0.03 * bool(ref_in)
    covered = set()
    for e in events:
        if e["allday"] and "norddata" in norm(e["title"]) and e["start"] is not None:
            d = e["start"]
            while d < (e["end"] or d):
                covered.add(d.isoformat())
                d = d.fromordinal(d.toordinal() + 1)
    summit = covered == set(exp["summit_days"])
    cal["summit_all_day"] = {"ok": summit, "days": sorted(covered)}
    score += 0.07 * summit

    ds = draft_replies(env, exp["desk_id"], exp["desk"])
    total_ok = any(has_amount(m["text"], exp["total"]) for m in ds)
    score += 0.06 * bool(ds) + 0.12 * total_ok
    if not text.strip():
        score = min(score, 0.5)
    return result(score, {"pdfs_saved": f"{pdfs}/3", "itinerary": doc, "calendar": cal,
                          "desk_reply": bool(ds), "desk_reply_total": total_ok})


# ---------------------------------------------------------------- B: inbox
def _virtual(text: str) -> list:
    out, cur = [], None
    for ln in (text or "").splitlines():
        k, _, v = ln.partition("=")
        if k == "uri":
            cur = {"uri": v, "scope": [], "terms": ""}
            out.append(cur)
        elif cur is not None and k == "scope":
            cur["scope"] = v.split("|")
        elif cur is not None and k == "terms":
            cur["terms"] = v
    return out


def evaluate_inbox(env, dest: str) -> dict:
    exp = expected("m3")
    state, boxes = profile_state(env), mail_folders(env)
    if not state or boxes is None:
        return result(0.0, {"profile": "unreadable"})
    have = {f.split("/", 1)[1].lower() for f in state.get("folders", []) if f.startswith(exp["host"] + "/")}
    folders_ok = sum(f.lower() in have for f in exp["folders"])

    loc = where(boxes)
    movers = [m for m in exp["mails"] if m["folder"] != "Inbox"]
    stayers = [m for m in exp["mails"] if m["folder"] == "Inbox"]
    moved_ok, stayed, wrong = 0, 0, []
    flagged = set()
    for m in exp["mails"]:
        copies = loc.get(m["id"], [])
        paths = {account_path(f) for f, _ in copies}
        if any(x["flagged"] for _, x in copies):
            flagged.add(m["id"])
        want = m["folder"].lower()
        if want == "archives":
            good = len(paths) == 1 and next(iter(paths)).startswith("archives")
        else:
            good = paths == {want}
        if m["folder"] == "Inbox":
            stayed += good
        else:
            moved_ok += good
        if not good:
            wrong.append(f"{m['subject'][:34]} -> {sorted(paths)} (want {m['folder']})")
    want_flag = {m["id"] for m in exp["mails"] if m["flag"]}
    tp, fp = len(flagged & want_flag), len(flagged - want_flag)
    flag_score = max(0, tp - max(0, fp - 1)) / len(want_flag)

    vf = [v for v in _virtual(state.get("virtual", "")) if norm(unquote(v["uri"].rsplit("/", 1)[-1])) == "followup"]
    vinfo = {"found": bool(vf)}
    v_score = 0.0
    if vf:
        v = vf[0]
        terms_ok = "(status,is,flagged)" in v["terms"].lower().replace(" ,", ",")
        scope = {folder_from_uri(u) for u in v["scope"]}
        need = {m["folder"].lower() for m in exp["mails"] if m["flag"]}
        scope_ok = "" in scope or need <= scope
        vinfo.update(terms=v["terms"], scope=sorted(scope), terms_flagged=terms_ok, scope_covers_starred=scope_ok)
        v_score = 0.03 + 0.05 * terms_ok + 0.06 * scope_ok

    path = fetch(env, FOLLOWUPS, dest + ".txt")
    lines = [norm(ln) for ln in (open(path, encoding="utf-8", errors="replace").read().splitlines() if path else [])]
    fu = {}
    for m in exp["mails"]:
        if m["flag"]:
            date = norm(m["flag"])
            fu[m["key"]] = any(date in ln and any(t and t in ln for t in m["tokens"]) for ln in lines)
    extra_lines = max(0, sum(bool(re.search(r"2026\d{4}", ln)) for ln in lines) - len(fu))
    fu_score = max(0.0, sum(fu.values()) - extra_lines) / len(fu)

    score = (0.05 * folders_ok / len(exp["folders"]) + 0.40 * moved_ok / len(movers)
             + 0.06 * (stayed / len(stayers) if moved_ok else 0) + 0.20 * flag_score + v_score + 0.15 * fu_score)
    checks = {"folders": f"{folders_ok}/{len(exp['folders'])}", "moved_ok": f"{moved_ok}/{len(movers)}",
              "inbox_kept": f"{stayed}/{len(stayers)}", "wrong": wrong[:10], "starred_ok": f"{tp}/{len(want_flag)}",
              "starred_extra": fp, "saved_search": vinfo, "followups": fu, "followup_extra_lines": extra_lines}
    return result(score, checks)
