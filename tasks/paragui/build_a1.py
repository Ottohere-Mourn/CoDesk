"""A1 - Elmbrook House Care Home: leave approvals vs filling the open shifts (RotaDesk).

build(out_dir) writes:
  app_a1.py          RotaDesk web app (copied)
  rotadesk_seed.db   seeded sqlite db: 17 staff, week-47 rota with 8 OPEN slots, 8 leave requests (1 approved earlier,
                     6 pending for week 47, 1 pending for December)
  expected.json      ground truth (host only): staff rule codes, pristine rota, open slots, expected decisions

The rota is generated deterministically and then verified exhaustively: whichever valid way the open slots are filled
first, every approved request can still be covered, and whichever valid cover is chosen first, the open slots can still
be filled - so both chores are completable in either order and the approve/decline set never depends on the order.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib_x as X  # noqa: E402

_spec = importlib.util.spec_from_file_location("pg_a1_rules", os.path.join(HERE, "pg_a1.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

WEEK = R.WEEK
D = {k: WEEK[i] for i, k in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])}

# name: (role, employment, contracted, max, availability text, rule code, phone, balance, start date)
STAFF = [
    ("Grace Okafor", "Senior carer", "Permanent", 5, 5, "Any shift", "", "07700 900 311", 4.0, "2017-03-06"),
    ("Daniel Price", "Senior carer", "Permanent", 5, 5, "Any shift", "", "07700 900 527", 11.0, "2019-09-02"),
    ("Priya Nair", "Senior carer", "Permanent", 4, 5, "Any shift", "", "07700 900 148", 8.0, "2020-01-13"),
    ("Tom Whitley", "Senior carer", "Permanent", 4, 5, "No night shifts (childcare)", "no_nights", "07700 900 662", 6.0, "2021-05-17"),
    ("Helen Marsh", "Senior carer", "Permanent", 3, 4, "Nights only", "nights_only", "07700 900 905", 9.5, "2015-11-30"),
    ("Marek Nowak", "Senior carer", "Permanent", 4, 5, "Not available on Sundays", "not_sun", "07700 900 284", 7.0, "2022-02-21"),
    ("Rosa Lindqvist", "Senior carer", "Bank", 0, 3, "Bank staff - day shifts only, no nights", "no_nights", "07700 900 731", 0.0, "2024-06-03"),
    ("Amy Clarke", "Care assistant", "Permanent", 4, 5, "Any shift", "", "07700 900 402", 9.0, "2022-08-08"),
    ("Ben Foster", "Care assistant", "Permanent", 5, 5, "Any shift", "", "07700 900 816", 5.0, "2018-04-23"),
    ("Chloe Dunn", "Care assistant", "Permanent", 4, 5, "No night shifts", "no_nights", "07700 900 239", 10.0, "2023-01-09"),
    ("Femi Adeyemi", "Care assistant", "Permanent", 4, 5, "Any shift", "", "07700 900 574", 12.0, "2021-10-04"),
    ("Jess Walker", "Care assistant", "Permanent", 3, 4, "Early shifts only (second job in the evenings)", "earlies_only", "07700 900 690", 6.5, "2023-07-31"),
    ("Liam Doyle", "Care assistant", "Permanent", 4, 5, "Any shift", "", "07700 900 157", 6.0, "2020-06-15"),
    ("Megan Rhys", "Care assistant", "Permanent", 4, 5, "Not available on Sundays", "not_sun", "07700 900 943", 3.0, "2019-02-25"),
    ("Nadia Hussain", "Care assistant", "Permanent", 3, 4, "No night shifts", "no_nights", "07700 900 368", 8.0, "2024-01-15"),
    ("Oliver Grant", "Care assistant", "Permanent", 5, 5, "Any shift", "", "07700 900 725", 7.0, "2016-09-12"),
    ("Ruth Bell", "Care assistant", "Permanent", 4, 5, "Any shift", "", "07700 900 481", 1.0, "2018-12-03"),
]
NAMES = [s[0] for s in STAFF]
RULES = {s[0]: {"senior": int(s[1].startswith("Senior")), "max": s[4], "avail": s[6], "contracted": s[3]} for s in STAFF}

# requests: (name, kind, start, end, days, reason, submitted, status, expected decision, why)
REQUESTS = [
    ("Megan Rhys", "Annual leave", D["Sat"], D["Sun"], 2, "Sister's wedding in Cardiff", "2026-09-28", "Approved", None, ""),
    ("Grace Okafor", "Annual leave", D["Fri"], D["Fri"], 1, "Long weekend", "2026-10-20", "Pending", "Approved", "ok"),
    ("Ruth Bell", "Annual leave", D["Sat"], D["Sun"], 2, "Visiting family", "2026-10-22", "Pending", "Declined", "balance 1 day < 2"),
    ("Amy Clarke", "Annual leave", D["Wed"], D["Thu"], 2, "Moving house", "2026-10-26", "Pending", "Approved", "ok"),
    ("Daniel Price", "Annual leave", D["Fri"], D["Sat"], 2, "Football tournament with my son", "2026-10-30", "Pending", "Declined",
     "Grace (senior, submitted earlier) already off on Fri 20"),
    ("Liam Doyle", "Annual leave", D["Tue"], D["Tue"], 1, "Driving test", "2026-11-06", "Pending", "Declined", "11 days notice < 14"),
    ("Femi Adeyemi", "Compassionate leave", D["Mon"], D["Tue"], 2, "Grandmother's funeral in Leeds", "2026-11-07", "Pending",
     "Approved", "compassionate: exempt from notice"),
    ("Oliver Grant", "Annual leave", "2026-12-01", "2026-12-02", 2, "Christmas shopping trip", "2026-11-02", "Pending", None, ""),
]
FIXED = {(D["Mon"], "E"): ["Amy Clarke"], (D["Wed"], "E"): ["Amy Clarke"], (D["Sat"], "L"): ["Amy Clarke"],
         (D["Mon"], "N"): ["Femi Adeyemi"], (D["Wed"], "N"): ["Femi Adeyemi"], (D["Thu"], "N"): ["Femi Adeyemi"],
         (D["Fri"], "E"): ["Grace Okafor", "Marek Nowak"]}
# OPEN slots: "s" = the shift still lacks its senior carer
OPEN = {(D["Tue"], "N"): "c", (D["Thu"], "E"): "c", (D["Thu"], "L"): "s", (D["Fri"], "L"): "c", (D["Sat"], "E"): "c",
        (D["Sat"], "N"): "s", (D["Sun"], "E"): "c", (D["Sun"], "L"): "c"}
LEAVE0 = {"Megan Rhys": {D["Sat"], D["Sun"]}}
APPROVE = {"Grace Okafor": {D["Fri"]}, "Amy Clarke": {D["Wed"], D["Thu"]}, "Femi Adeyemi": {D["Mon"], D["Tue"]}}


def can_add(rota, p, d, s, leave, cap="max"):
    st = RULES[p]
    if d in leave.get(p, ()) or not R.avail_ok(st["avail"], d, s):
        return False
    mine = [(dd, ss) for (dd, ss), names in rota.items() if p in names]
    if any(dd == d for dd, _ in mine):
        return False
    i = WEEK.index(d)
    for dd, ss in mine:
        j = WEEK.index(dd)
        if (j == i - 1 and (ss, s) in R.FORBID) or (j == i + 1 and (s, ss) in R.FORBID):
            return False
    return len(mine) < (st["max"] if cap == "max" else st["contracted"])


def make_rota(seed=2):
    rng = random.Random(seed)
    rota = {(d, s): list(FIXED.get((d, s), [])) for d in WEEK for s in R.SHIFTS}
    order = []
    for d in WEEK:
        for s in R.SHIFTS:
            order += [(d, s)] * (R.NEED[s] - (1 if (d, s) in OPEN else 0) - len(rota[(d, s)]))

    def rec(i):
        if i == len(order):
            return True
        d, s = order[i]
        cur = rota[(d, s)]
        remaining = R.NEED[s] - (1 if (d, s) in OPEN else 0) - len(cur)
        has_sen = any(RULES[x]["senior"] for x in cur)
        cands = [p for p in NAMES if p not in cur and can_add(rota, p, d, s, LEAVE0, cap="contract")]
        if OPEN.get((d, s)) == "s":
            cands = [p for p in cands if not RULES[p]["senior"]]
        elif not has_sen and remaining == 1:
            cands = [p for p in cands if RULES[p]["senior"]]
        rng.shuffle(cands)
        cands.sort(key=lambda p: sum(p in v for v in rota.values()))
        for p in cands:
            cur.append(p)
            if rec(i + 1):
                return True
            cur.pop()
        return False
    assert rec(0)
    return rota


def fill_options(rota, slots, leave):
    def rec(i):
        if i == len(slots):
            yield []
            return
        d, s, sen = slots[i]
        for p in NAMES:
            if p in rota[(d, s)] or (sen and not RULES[p]["senior"]):
                continue
            if can_add(rota, p, d, s, leave):
                rota[(d, s)].append(p)
                for rest in rec(i + 1):
                    yield [p] + rest
                rota[(d, s)].remove(p)
    yield from rec(0)


def vacate(rota):
    out = []
    for p, days in APPROVE.items():
        for (d, s), names in rota.items():
            if d in days and p in names:
                names.remove(p)
                out.append((d, s))
    return [(d, s, not any(RULES[x]["senior"] for x in rota[(d, s)])) for d, s in out]


def cp(r):
    return {k: list(v) for k, v in r.items()}


def verify(rota):
    full = dict(LEAVE0, **APPROVE)
    oslots = [(d, s, OPEN[(d, s)] == "s") for d, s in OPEN]
    nb = 0
    for fill in fill_options(cp(rota), oslots, LEAVE0):        # B first, then A must still be able to cover
        nb += 1
        r2 = cp(rota)
        for (d, s, _), p in zip(oslots, fill):
            r2[(d, s)].append(p)
        cs = vacate(r2)
        assert next(fill_options(r2, cs, full), None) is not None, ("A blocked after B", fill)
    r1 = cp(rota)
    cs = vacate(r1)
    na = 0
    for fill in fill_options(cp(r1), cs, full):                # A first, then B must still be able to fill
        na += 1
        r2 = cp(r1)
        for (d, s, _), p in zip(cs, fill):
            r2[(d, s)].append(p)
        assert next(fill_options(r2, oslots, full), None) is not None, ("B blocked after A", fill)
    # the pristine rota itself breaks no rule
    assert not R.violations(rota, RULES, {k: set(v) for k, v in LEAVE0.items()})
    return nb, na


SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, salt TEXT, pw TEXT);
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE staff(id INTEGER PRIMARY KEY, name TEXT, role TEXT, employment TEXT, contracted INTEGER, max_shifts INTEGER,
  availability TEXT, phone TEXT, leave_balance REAL, start_date TEXT);
CREATE TABLE assignments(id INTEGER PRIMARY KEY, day TEXT, shift TEXT, staff_id INTEGER, created_at TEXT, created_by TEXT,
  deleted INTEGER DEFAULT 0, deleted_at TEXT);
CREATE TABLE leave_requests(id INTEGER PRIMARY KEY, staff_id INTEGER, kind TEXT, start TEXT, end TEXT, days INTEGER, reason TEXT,
  submitted TEXT, status TEXT, decided_at TEXT, decided_by TEXT, comment TEXT DEFAULT '');
CREATE TABLE sessions(sid TEXT PRIMARY KEY, user_id INTEGER, created TEXT, state TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
"""


def build(d):
    os.makedirs(d, exist_ok=True)
    X.copy_app("app_a1.py", d)
    rota = make_rota()
    nb, na = verify(rota)
    sid = {n: i + 1 for i, n in enumerate(NAMES)}
    rows = {"users": [{"id": 1, "username": "sam.ellison", "name": "Sam Ellison", "salt": "e1b", "pw": X.pw_hash("Elmbrook-Rota-26", "e1b")},
                      {"id": 2, "username": "jo.hart", "name": "Jo Hart (registered manager)", "salt": "9fa", "pw": X.pw_hash("x-unused-77", "9fa")}],
            "settings": [{"key": "business_date", "value": "2026-11-09"}],
            "staff": [], "assignments": [], "leave_requests": [], "audit": []}
    for n, role, emp, con, mx, av, _, ph, bal, start in STAFF:
        rows["staff"].append({"id": sid[n], "name": n, "role": role, "employment": emp, "contracted": con, "max_shifts": mx,
                              "availability": av, "phone": ph, "leave_balance": bal, "start_date": start})
    k = 0
    for day in WEEK:
        for s in R.SHIFTS:
            for n in rota[(day, s)]:
                k += 1
                rows["assignments"].append({"id": k, "day": day, "shift": s, "staff_id": sid[n],
                                            "created_at": "2026-11-02 16:4%d:00" % (k % 10), "created_by": "jo.hart", "deleted": 0})
    exp_reqs, oos = [], []
    for i, (n, kind, a, b, days, reason, sub, status, want, why) in enumerate(REQUESTS, 1):
        rows["leave_requests"].append({"id": i, "staff_id": sid[n], "kind": kind, "start": a, "end": b, "days": days, "reason": reason,
                                       "submitted": sub, "status": status,
                                       "decided_at": "2026-09-29 10:12:00" if status == "Approved" else None,
                                       "decided_by": "jo.hart" if status == "Approved" else None,
                                       "comment": "Approved - enjoy the wedding!" if status == "Approved" else ""})
        if want:
            ds = sorted(x for x in WEEK if a <= x <= b)
            exp_reqs.append({"id": i, "name": n, "decision": want, "days": ds, "why": why})
        elif status == "Pending":
            oos.append(i)
    rows["audit"] = [{"id": 1, "ts": "2026-11-02 16:48:10", "user": "jo.hart", "action": "rota drafted", "detail": "Week 47 draft, 8 shifts open"},
                     {"id": 2, "ts": "2026-11-07 09:02:44", "user": "jo.hart", "action": "note", "detail": "Agency cancelled week 47 bookings"}]
    X.seed_db(f"{d}/rotadesk_seed.db", SCHEMA, rows)
    exp = {"staff": RULES, "pristine": {f"{a}|{b}": v for (a, b), v in rota.items()},
           "open_slots": [f"{a}|{b}" for a, b in OPEN], "requests": exp_reqs, "out_of_scope_requests": oos,
           "verified": {"b_first_fills": nb, "a_first_covers": na}, "login": ["sam.ellison", "Elmbrook-Rota-26"]}
    json.dump(exp, open(f"{d}/expected.json", "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/a1_assets")
