"""a2 - one Thunderbird calendar (Ines Varga, Varga & Hale Architects): two chores booking into the same free time.

  pga2requests  six meeting requests -> first choice if free, else the alternative; reply drafts for moved ones
  pga2visits    three inspection trips (fixed) + three 1-hour design reviews at the EARLIEST free slots + team mail

Both checkers judge the FINAL calendar: what counts as "free" is decided by the entries that are not the task's own.
Run one after the other, the second task routes around the first (both pass, with different outcomes); double
bookings made from a stale view of the calendar fail both.
"""
from __future__ import annotations

import datetime as dt
import re

from evaluation_examples.task_class.pg_common import expected, result, sh, start_thunderbird
from evaluation_examples.task_class.pg_mcommon import calendar_events, norm, own_text, raw_messages, addrs

PAIR = "a2"


def setup(sc):
    start_thunderbird(sc, "a2/thunderbird-profile.tar.gz", "pga2")
    sh(sc, "mkdir -p ~/Documents")


# ---------------------------------------------------------------- calendar model
def _hm(t) -> str:
    return t.strftime("%Y-%m-%d %H:%M") if t is not None and hasattr(t, "hour") else str(t)


def _p(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")


def _iv(e):
    return _p(_hm(e["start"])), _p(_hm(e["end"]))


def _overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _load(env, exp):
    evs = calendar_events(env, exp["tz"])
    if evs is None:
        return None
    lo, hi = exp["week"]
    out = []
    for e in evs:
        if e["allday"] or e["start"] is None or e["end"] is None:
            continue
        if lo <= _hm(e["start"])[:10] <= hi:
            e = dict(e, iv=_iv(e))
            out.append(e)
    return out


def classify(events, exp) -> dict:
    """Split the week's events into seeded / per-request (A) / per-inspection and per-review (B) / other.
    Matching is by the requester's attendee addresses or title keywords; for B by title keywords."""
    seed_ids = {s["id"] for s in exp["seed"]}
    new = [e for e in events if e["id"] not in seed_ids]
    a, used = {}, set()
    for r in exp["requests"]:
        cands = []
        for e in new:
            att = set(e["attendees"]) & {x.lower() for x in r["attendees"]}
            kw = any(norm(w) in norm(e["title"]) for w in r["words"])
            if att or kw:
                cands.append(e)
        a[r["key"]] = cands
        used |= {e["id"] for e in cands}
    rest = [e for e in new if e["id"] not in used]
    reviews, insp = {}, {}
    for rv in exp["reviews"]:
        reviews[rv["key"]] = [e for e in rest if "review" in e["title"].lower()
                              and any(norm(w) in norm(e["title"]) for w in rv["words"])]
    rv_ids = {e["id"] for v in reviews.values() for e in v}
    for ins in exp["inspections"]:
        span = (_p(ins["span"][0]), _p(ins["span"][1]))
        insp[ins["key"]] = [e for e in rest if e["id"] not in rv_ids and _overlap(e["iv"], span) and (
            any(norm(w) in norm(e["title"]) for w in ins["words"])
            or re.search(r"travel|drive|journey|inspection|site visit|building control", e["title"], re.I))]
    return {"a": a, "reviews": reviews, "insp": insp, "new": new}


def _clashes(e, events) -> list:
    return [o["title"][:30] for o in events if o["id"] != e["id"] and _overlap(e["iv"], o["iv"])]


def _tokens(slot_start: dt.datetime):
    day = [slot_start.strftime("%a").lower(), slot_start.strftime("%A").lower()]
    dnum = str(slot_start.day)
    h, m = slot_start.hour, slot_start.minute
    h12 = h % 12 or 12
    times = {f"{h}:{m:02d}", f"{h:02d}:{m:02d}", f"{h}.{m:02d}", f"{h12}:{m:02d}", f"{h12}.{m:02d}"}
    if m == 0:
        times |= {f"{h12}pm" if h >= 12 else f"{h12}am", f"{h12} pm" if h >= 12 else f"{h12} am", f"{h}h"}
    return day, dnum, times


def _says(text: str, slot_start: dt.datetime) -> bool:
    t = " " + text.lower() + " "
    day, dnum, times = _tokens(slot_start)
    has_day = any(d in t for d in day) or re.search(rf"(?<!\d){dnum}(?:st|nd|rd|th)?(?!\d|:|\.\d)", t) is not None
    has_time = any(re.search(rf"(?<![\d:.]){re.escape(x)}(?![\d])", t) for x in times)
    return has_day and has_time


# ---------------------------------------------------------------- A: meeting requests
def evaluate_requests(env, dest: str) -> dict:
    exp = expected(PAIR)
    events = _load(env, exp)
    if events is None:
        return result(0.0, {"calendar": "unreadable"})
    cl = classify(events, exp)
    a_ids = {e["id"] for v in cl["a"].values() for e in v}
    others = [e for e in events if e["id"] not in a_ids]
    raw = raw_messages(env, ("drafts",))
    drafts = [m for f, ms in raw.items() if f.rsplit("/", 1)[-1].lower() == "drafts" for m in ms]
    score, per, overlaps, n_slot, dupes = 0.0, {}, [], 0, []
    need_reply, replies = {}, {}
    for r in exp["requests"]:
        first, alt = (_p(r["first"][0]), _p(r["first"][1])), (_p(r["alt"][0]), _p(r["alt"][1]))
        first_free = not any(_overlap(first, o["iv"]) for o in others)
        want = first if first_free else alt
        cands = cl["a"][r["key"]]
        if len(cands) > 1:
            dupes.append(r["key"])
        best, pts = None, -1
        for e in cands:
            slot = e["iv"] == want
            loc = any(norm(x) in norm(e["location"]) for x in r["loc"])
            att = {x.lower() for x in r["attendees"]} <= set(e["attendees"])
            p = 3 * slot + loc + att
            if p > pts:
                best, pts = (e, slot, loc, att), p
        if best:
            e, slot, loc, att = best
            cl_ = _clashes(e, events)
            if cl_:
                overlaps.append(f"{r['key']} {_hm(e['start'])} x {cl_}")
            n_slot += slot
            score += 0.07 * slot + 0.02 * loc + 0.02 * att
            per[r["key"]] = {"want": _hm(want[0]) + ("" if first_free else " (alt)"), "got": f"{_hm(e['start'])}-{_hm(e['end'])[11:]}",
                             "slot": slot, "location": loc, "attendees": att}
        else:
            per[r["key"]] = {"want": _hm(want[0]) + ("" if first_free else " (alt)"), "got": None}
        # reply drafts to this request
        mine = [m for m in drafts if any(i in f"{m['In-Reply-To'] or ''} {m['References'] or ''}" for i in r["ids"])
                and r["requester"] in addrs(str(m["To"] or "")) | addrs(str(m["Cc"] or ""))]
        if not first_free:
            need_reply[r["key"]] = bool(mine) and any(_says(own_text(m), want[0]) for m in mine)
        else:
            replies[r["key"]] = bool(mine)
    any_event = n_slot > 0 or any(per[k].get("got") for k in per)
    no_overlap = any_event and not overlaps
    score += 0.08 * no_overlap
    rep_frac = (sum(need_reply.values()) / len(need_reply)) if need_reply else (1.0 if any_event else 0.0)
    spurious = [k for k, v in replies.items() if v]
    score += 0.16 * rep_frac + 0.04 * (any_event and not spurious)
    seed_ok = _seed_intact(events, exp)
    score += 0.06 * (any_event and seed_ok and not dupes)
    checks = {"requests": per, "overlaps": overlaps, "replies_needed_ok": need_reply, "spurious_replies": spurious,
              "duplicate_entries": dupes, "seed_intact": seed_ok,
              "other_new_entries": [f"{e['title'][:30]} {_hm(e['start'])}" for e in cl["new"] if e["id"] not in a_ids][:8]}
    score = min(score, 0.6) if overlaps else score
    score = min(score, 0.4) if n_slot < 3 else score
    return result(score, checks)


def _seed_intact(events, exp) -> bool:
    by = {e["id"]: e for e in events}
    for s in exp["seed"]:
        e = by.get(s["id"])
        if not e or _hm(e["start"]) != s["start"] or _hm(e["end"]) != s["end"] or e["title"] != s["title"]:
            return False
    return True


# ---------------------------------------------------------------- B: inspections + design reviews
def _allowed_slots(exp):
    w = exp["review_window"]
    out = []
    for day in w["days"]:
        t = _p(f"{day} {w['from']}")
        end = _p(f"{day} {w['to']}")
        while t + dt.timedelta(minutes=w["minutes"]) <= end:
            out.append((t, t + dt.timedelta(minutes=w["minutes"])))
            t += dt.timedelta(minutes=30)
    return out


def evaluate_visits(env, dest: str) -> dict:
    exp = expected(PAIR)
    events = _load(env, exp)
    if events is None:
        return result(0.0, {"calendar": "unreadable"})
    cl = classify(events, exp)
    score, checks = 0.0, {}
    # inspection trips: the B entries around each inspection must cover exactly leave-studio .. back-at-studio
    ins_ok = {}
    b_ids = set()
    for ins in exp["inspections"]:
        span = (_p(ins["span"][0]), _p(ins["span"][1]))
        es = cl["insp"][ins["key"]]
        b_ids |= {e["id"] for e in es}
        ivs = sorted(e["iv"] for e in es)
        cover, cur, ok = [], None, bool(ivs) and any(any(norm(w) in norm(e["title"]) for w in ins["words"]) for e in es)
        for s, e in ivs:
            if cur and s <= cur[1]:
                cur = (cur[0], max(cur[1], e))
            else:
                if cur:
                    cover.append(cur)
                cur = (s, e)
        if cur:
            cover.append(cur)
        exact = ok and cover == [span]
        foreign = [o["title"][:30] for o in events if o["id"] not in {e["id"] for e in es} and _overlap(span, o["iv"])]
        ins_ok[ins["key"]] = {"blocked": [f"{_hm(a)}-{_hm(b)[11:]}" for a, b in cover], "exact_trip": exact,
                              "clashes": foreign}
        score += 0.12 * exact
    checks["inspections"] = ins_ok
    # design reviews
    rv = {}
    starts, overlaps, valid_n = [], [], 0
    slots = _allowed_slots(exp)
    for r in exp["reviews"]:
        es = cl["reviews"][r["key"]]
        b_ids |= {e["id"] for e in es}
        if not es:
            rv[r["key"]] = {"found": False}
            continue
        e = es[0]
        valid = e["iv"] in slots
        cl_ = _clashes(e, events)
        if cl_:
            overlaps.append(f"{r['key']} {_hm(e['start'])} x {cl_}")
        rv[r["key"]] = {"got": f"{_hm(e['start'])}-{_hm(e['end'])[11:]}", "in_window_1h": valid, "clashes": cl_,
                        "copies": len(es)}
        valid_n += valid
        score += 0.06 * valid + 0.04 * (valid and not cl_ and len(es) == 1)
        if valid:
            starts.append(e["iv"][0])
    earliest = False
    if valid_n == 3:
        last = max(starts)
        free_earlier = [_hm(s[0]) for s in slots if s[0] < last and not any(_overlap(s, o["iv"]) for o in events)]
        earliest = not free_earlier
        checks["free_slots_left_before_last_review"] = free_earlier
    order = valid_n == 3 and [cl["reviews"][r["key"]][0]["iv"][0] for r in exp["reviews"]] == sorted(starts)
    score += 0.12 * earliest + 0.04 * order
    checks.update({"reviews": rv, "review_overlaps": overlaps, "earliest_free": earliest, "in_marco_order": bool(order)})
    # mail to the team listing the review times
    raw = raw_messages(env, ("drafts",))
    team = [m for f, ms in raw.items() if f.rsplit("/", 1)[-1].lower() == "drafts" for m in ms
            if exp["team"] in addrs(str(m["To"] or "")) | addrs(str(m["Cc"] or ""))]
    listed = 0
    if team and starts:
        text = " ".join(own_text(m) for m in team)
        listed = sum(_says(text, s) for s in starts)
    score += 0.04 * bool(team) + 0.10 * listed / 3
    any_b = bool(b_ids)
    seed_ok = _seed_intact(events, exp)
    score += 0.04 * (any_b and seed_ok)
    checks.update({"team_draft": bool(team), "team_draft_lists_times": f"{listed}/3", "seed_intact": seed_ok})
    if overlaps or any(v["clashes"] for v in ins_ok.values() if v["exact_trip"]):
        score = min(score, 0.6)
    if not any(v["exact_trip"] for v in ins_ok.values()):
        score = min(score, 0.4)
    return result(score, checks)
