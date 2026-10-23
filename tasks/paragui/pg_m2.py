"""m2 - one Thunderbird: booking meeting requests into the Home calendar vs cleaning up the address book.

Both tasks start in the same Thunderbird main window (Dr. Amara Okafor, amara.okafor@harborpointhealth.org): task A
lives in the Calendar tab and the event dialogs, task B in the Address Book tab; both read the same e-mails. The
attendee addresses A enters are auto-completed from the address book B is rewriting.
"""
from __future__ import annotations

import re

from evaluation_examples.task_class.pg_common import HOME, expected, fetch, result, sh, start_thunderbird
from evaluation_examples.task_class.pg_mcommon import (calendar_events, cards_from_dump, csv_rows, draft_replies,
                                                       lists_from_dump, norm, raw_messages, sqlite_dump)

CSV = f"{HOME}/Documents/HPCH_contacts.csv"


def setup(sc):
    start_thunderbird(sc, "m2/thunderbird-profile.tar.gz", "pgm2")
    sh(sc, "mkdir -p ~/Documents")


# ---------------------------------------------------------------- A: calendar
def _hm(t):
    return t.strftime("%Y-%m-%d %H:%M") if t is not None and hasattr(t, "hour") else str(t)


def evaluate_calendar(env, dest: str) -> dict:
    exp = expected("m2")
    events = calendar_events(env, exp["tz"])
    if events is None:
        return result(0.0, {"calendar": "unreadable"})
    week = [e for e in events if not e["allday"] and e["start"] is not None and "2026-11-16" <= _hm(e["start"])[:10] <= "2026-11-20"]
    allowed = set(exp["allowed_attendees"])
    per, used, score = {}, set(), 0.0
    for want in exp["events"]:
        cands = [e for e in week if any(norm(w) in norm(e["title"]) for w in want["words"])]
        best, best_pts = None, -1
        for e in cands:
            t = _hm(e["start"]) == want["start"] and _hm(e["end"]) == want["end"]
            loc = norm(e["location"])
            lo = any(norm(x) in loc for x in want["loc"]) and (want["key"] != "debrief" or norm(exp["zoom"])[-11:] in loc)
            att = set(e["attendees"])
            at = set(want["attendees"]) <= att and att <= allowed
            pts = 3 * t + lo + at
            if pts > best_pts:
                best, best_pts = (e, t, lo, at), pts
        if best:
            e, t, lo, at = best
            used.add(e["id"])
            score += 0.06 * t + 0.02 * lo + 0.03 * at
            per[want["key"]] = {"time": t, "location": lo, "attendees": at, "copies": len(cands),
                                "got": f"{_hm(e['start'])}-{_hm(e['end'])[11:]} @{e['location'][:30]} {sorted(e['attendees'])}"}
        else:
            per[want["key"]] = {"time": False, "location": False, "attendees": False, "copies": 0}
    times_ok = sum(p["time"] for p in per.values())
    extras = [f"{e['title'][:30]} {_hm(e['start'])}" for e in week if e["id"] not in used]
    tidy = times_ok >= 3 and not extras and all(p["copies"] <= 1 for p in per.values())
    # Grace's rules on the whole week: no overlaps, nothing on Wednesday morning, 9:00-17:00 only
    clash = []
    for i, a in enumerate(week):
        if _hm(a["start"])[:10] == "2026-11-18" and a["start"].hour < 12:
            clash.append(f"Wed morning: {a['title'][:30]}")
        if a["start"].hour < 9 or (a["end"].hour, a["end"].minute) > (17, 0):
            clash.append(f"outside hours: {a['title'][:30]}")
        for b in week[i + 1:]:
            if a["start"] < b["end"] and b["start"] < a["end"]:
                clash.append(f"overlap: {a['title'][:25]} / {b['title'][:25]}")
    rules_ok = times_ok >= 4 and not clash
    score += 0.08 * tidy + 0.08 * rules_ok

    raw = raw_messages(env, ("drafts",))
    rep = {}
    for key, r in exp["replies"].items():
        ds = draft_replies(env, r["ids"], r["to"], raw=raw)
        text = " ".join(m["text"] for m in ds).lower()  # own words: the quoted request names both slots
        content = bool(ds) and any(d in text for d in r["day"]) and any(t in text for t in r["time"])
        rep[key] = {"draft": bool(ds), "says_new_time": content}
        score += 0.03 * bool(ds) + 0.06 * content
    checks = {"events": per, "unmatched_events_that_week": extras[:8], "no_duplicates_or_extras": tidy,
              "rule_violations": clash[:8], "replies": rep, "calendar_events_total": len(events)}
    return result(score, checks)


# ---------------------------------------------------------------- B: contacts
def _digits(s):
    return re.sub(r"\D", "", s or "")


def evaluate_contacts(env, dest: str) -> dict:
    exp = expected("m2")
    dump = sqlite_dump(env, ["abook.sqlite"]).get("abook.sqlite")
    if not dump or "error" in dump:
        return result(0.0, {"abook": "unreadable"})
    cards = cards_from_dump(dump)
    lists = lists_from_dump(dump, cards)
    holders = {}
    for uid, c in cards.items():
        for e in c["emails"]:
            holders.setdefault(e, set()).add(uid)
    score, checks = 0.0, {}

    merges = {}
    for name, prim, sec in exp["merges"]:
        hp, hs = holders.get(prim, set()), holders.get(sec, set())
        ok = len(hp) == 1 and hp == hs and cards[next(iter(hp))]["emails"][0] == prim
        last = name.split()[-1].lower()
        named = ok and last in (cards[next(iter(hp))]["display"] + " " + cards[next(iter(hp))]["last"]).lower()
        merges[name] = {"one_card_both_addresses_primary_ok": ok, "name": named}
        score += 0.06 * ok + 0.02 * named
    checks["merges"] = merges
    leaver_gone = exp["leaver"] not in holders
    checks["leaver_deleted"] = leaver_gone
    special = {exp["leaver"]} | {e for _, p, s in exp["merges"] for e in (p, s)}
    others = [c["email"].lower() for c in exp["cards_before"] if c["email"].lower() not in special]
    kept = [e for e in others if e in holders]
    progress = any(m["one_card_both_addresses_primary_ok"] for m in merges.values()) or any(
        n["email"] in holders for n in exp["new"])
    checks["other_contacts_kept"] = f"{len(kept)}/{len(others)}"
    score += 0.05 * leaver_gone + 0.05 * (progress and len(kept) == len(others))

    new = {}
    for n in exp["new"]:
        uids = holders.get(n["email"], set())
        c = cards[next(iter(uids))] if uids else None
        f = {"email": bool(c) and c["emails"][0] == n["email"]}
        if c:
            full = f"{c['display']} {c['first']} {c['last']}".lower()
            f["name"] = n["first"].lower() in full and n["last"].lower() in full
            orgs = [n["org"]] + n.get("org_alt", [])
            f["org"] = any(norm(o)[:12] in norm(c["org"]) for o in orgs) and bool(c["org"])
            f["title"] = bool(c["title"]) and any(norm(t) in norm(c["title"])
                                                  for t in [n["title"]] + n.get("title_alt", []))
            f["phone"] = any(_digits(n["phone"])[-10:] == _digits(t)[-10:] for t in c["tels"])
        else:
            f.update(name=False, org=False, title=False, phone=False)
        new[n["email"]] = f
        score += 0.03 * f["email"] + 0.01 * f["name"] + 0.01 * f["org"] + 0.01 * f["title"] + 0.02 * f["phone"]
    checks["new_contacts"] = new

    want = set(exp["list"]["members"])
    lst = [x for x in lists if norm(x["name"]) == norm(exp["list"]["name"])]
    if lst:
        got = set(lst[0]["members"])
        frac = max(0.0, (len(got & want) - len(got - want)) / len(want))
        score += 0.04 + 0.12 * frac
        checks["list"] = {"members": sorted(got), "missing": sorted(want - got), "extra": sorted(got - want)}
    else:
        checks["list"] = {"found": [x["name"] for x in lists]}

    path = fetch(env, CSV, dest + ".csv")
    rows = csv_rows(path) if path else []
    row_mails = [{e.lower() for e in re.findall(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", " ".join(r))} for r in rows]
    row_mails = [s for s in row_mails if s]
    exported = set().union(*row_mails) if row_mails else set()
    finals = [n["email"] for n in exp["new"]] + [p for _, p, _ in exp["merges"]] + others
    csv_ok = bool(rows) and all(e in exported for e in finals) and exp["leaver"] not in exported and all(
        any(p in s and sec in s for s in row_mails) for _, p, sec in exp["merges"])
    # the export must show the cleaned-up book: one row per card of the address book as it is now
    persons = [c for c in cards.values() if c["emails"]]
    consistent = csv_ok and len(row_mails) == len(persons)
    checks["csv"] = {"exists": bool(path), "rows_with_email": len(row_mails), "cards": len(persons),
                     "complete_and_clean": csv_ok, "matches_address_book": consistent}
    score += 0.04 * bool(rows) + 0.08 * csv_ok + 0.06 * consistent
    return result(score, checks)
