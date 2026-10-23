"""A1 - Elmbrook House Care Home: leave approvals vs filling the open shifts of the same week (RotaDesk, port 8131).

A (pga1leave): decide the pending leave requests for w/c 16 Nov 2026 by the leave policy; for every approval take the
   person off their shifts in the leave and put an eligible colleague on each; summary text file.
B (pga1rota):  fill the 8 OPEN slots of the same week with eligible staff (rota rules incl. approved leave), then print
   the rota from the print view to PDF.
Shared live state: one RotaDesk database (one week's rota, the leave records) and one Chrome. The two chores meet in a
cross-task invariant: nobody may be rostered on a day of approved leave, staffing levels/rest/max-shift rules must
hold for everybody. Both checkers judge the FINAL rota.

The rule engine below (pure python) is also used by build_a1.py and the self-test.
"""
from __future__ import annotations

import datetime as dt
import re

try:
    from evaluation_examples.task_class import pg_common as pc
except Exception:  # build time on the node (the build only needs the rule engine)
    pc = None

APP, PORT = "rotadesk", 8131
WEEK = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"]
SHIFTS = ["E", "L", "N"]
SHIFT_NAME = {"E": "Early", "L": "Late", "N": "Night"}
NEED = {"E": 3, "L": 3, "N": 2}
FORBID = {("L", "E"), ("N", "E"), ("N", "L")}  # (shift on day d, shift on day d+1) breaks the 11-hour rest rule
SUMMARY = "/home/user/Documents/Leave/leave_decisions_wk47.txt"
PDF = "/home/user/Documents/Rota/Rota_wk47.pdf"


# ---------------------------------------------------------------- rule engine
def avail_ok(code: str, day: str, shift: str) -> bool:
    return not ((code == "no_nights" and shift == "N") or (code == "nights_only" and shift != "N")
                or (code == "earlies_only" and shift != "E") or (code == "not_sun" and day == WEEK[6]))


def violations(rota: dict, staff: dict, leave: dict) -> list:
    """rota {(day, shift): [names]}, staff {name: {"senior", "max", "avail"}}, leave {name: set(days)}.
    Returns [(name, day, shift, rule)] for every assignment that breaks a person rule."""
    out = []
    mine = {}
    for (d, s), names in rota.items():
        for n in names:
            mine.setdefault(n, []).append((d, s))
    for n, shs in mine.items():
        st = staff.get(n, {"senior": 0, "max": 0, "avail": ""})
        days = [d for d, _ in shs]
        for d, s in shs:
            if d in leave.get(n, ()):
                out.append((n, d, s, "on approved leave"))
            if not avail_ok(st["avail"], d, s):
                out.append((n, d, s, "availability"))
            if days.count(d) > 1:
                out.append((n, d, s, "two shifts in one day"))
            i = WEEK.index(d) if d in WEEK else -9
            for d2, s2 in shs:
                j = WEEK.index(d2) if d2 in WEEK else -9
                if j == i + 1 and (s, s2) in FORBID:
                    out.append((n, d, s, "rest before next day"))
                if j == i - 1 and (s2, s) in FORBID:
                    out.append((n, d, s, "rest after previous day"))
        if len(shs) > st["max"]:
            out += [(n, d, s, "over maximum shifts") for d, s in shs]
    return out


def staffing_ok(rota: dict, staff: dict, key) -> bool:
    names = rota.get(key, [])
    return len(names) >= NEED[key[1]] and any(staff.get(n, {}).get("senior") for n in names)


# ---------------------------------------------------------------- setup
def setup(sc):
    pc.sh(sc, "mkdir -p ~/Documents/Leave ~/Documents/Rota")
    pc.start_webapp(sc, "a1/app_a1.py", APP, PORT, "a1/rotadesk_seed.db")
    pc.open_chrome(sc, [f"http://127.0.0.1:{PORT}/login"])


# ---------------------------------------------------------------- shared readers
def _world(env):
    q = pc.sql(env, pc.webapp_db(APP), {
        "staff": "SELECT id, name FROM staff",
        "asg": "SELECT a.id, a.day, a.shift, a.deleted, s.name FROM assignments a JOIN staff s ON s.id=a.staff_id",
        "req": "SELECT r.id, r.status, r.comment, r.start, r.end, s.name FROM leave_requests r JOIN staff s ON s.id=r.staff_id"})
    if q is None:
        return None
    exp = pc.expected("a1")
    staff = {n: dict(v) for n, v in exp["staff"].items()}
    rota = {(d, s): [] for d in WEEK for s in SHIFTS}
    for a in q["asg"]:
        if not a["deleted"] and (a["day"], a["shift"]) in rota:
            rota[(a["day"], a["shift"])].append(a["name"])
    leave = {}
    for r in q["req"]:
        if r["status"] == "Approved":
            d0, d1 = dt.date.fromisoformat(r["start"]), dt.date.fromisoformat(r["end"])
            while d0 <= d1:
                leave.setdefault(r["name"], set()).add(d0.isoformat())
                d0 += dt.timedelta(days=1)
    pristine = {tuple(k.split("|")): v for k, v in exp["pristine"].items()}
    return {"q": q, "exp": exp, "staff": staff, "rota": rota, "leave": leave, "pristine": pristine,
            "viol": violations(rota, staff, leave)}


def _flat(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


# ---------------------------------------------------------------- A: leave decisions
def evaluate_leave(env, dest: str) -> dict:
    w = _world(env)
    if w is None:
        return pc.result(0.0, {"app_db": "unreadable"})
    exp, rota, staff, viol = w["exp"], w["rota"], w["staff"], w["viol"]
    checks = {}
    reqs = {r["id"]: r for r in w["q"]["req"]}
    dec_ok, comments_ok, wrong = 0, 0, []
    for e in exp["requests"]:
        r = reqs.get(e["id"], {})
        ok = r.get("status") == e["decision"]
        dec_ok += ok
        if not ok:
            wrong.append(f"{e['name']}: {r.get('status')} (want {e['decision']})")
        if e["decision"] == "Declined" and r.get("status") == "Declined" and len(_flat(r.get("comment"))) >= 8:
            comments_ok += 1
    n_dec = sum(e["decision"] == "Declined" for e in exp["requests"])
    other_untouched = all(reqs.get(i, {}).get("status") == "Pending" for i in exp["out_of_scope_requests"])
    checks.update({"decisions_ok": f"{dec_ok}/{len(exp['requests'])}", "decision_errors": wrong,
                   "decline_reasons": f"{comments_ok}/{n_dec}", "december_request_still_pending": other_untouched})

    approved = {e["name"]: set(e["days"]) for e in exp["requests"] if e["decision"] == "Approved"}
    # 1) requesters off every shift during their leave
    off = {n: not any(n in rota[(d, s)] for d in days for s in SHIFTS) for n, days in approved.items()}
    # 2) every shift they held during the leave at any time (pristine or added later) is staffed again
    held = set()
    for a in w["q"]["asg"]:
        if a["name"] in approved and a["day"] in approved[a["name"]]:
            held.add((a["day"], a["shift"]))
    gone = {k: not any(n in rota[k] for n, days in approved.items() if k[0] in days) for k in held}
    covered = {f"{k[0]} {k[1]}": gone[k] and staffing_ok(rota, staff, k) for k in sorted(held)}
    # 3) whoever works those shifts now breaks no rota rule
    bad = sorted({(n, d, s, why) for n, d, s, why in viol if (d, s) in held})
    legal = {f"{k[0]} {k[1]}": gone[k] and not any((d, s) == k for _, d, s, _ in bad) for k in sorted(held)}
    # 4) no other shift was stripped to provide cover
    stripped = [f"{d} {s}" for (d, s), names in w["pristine"].items()
                if (d, s) not in held and len(rota[(d, s)]) < len(names) and not staffing_ok(rota, staff, (d, s))]
    checks.update({"requesters_off_shift": off, "vacated_shifts_covered": covered, "cover_legal": legal,
                   "cover_rule_breaks": [list(b) for b in bad][:8], "other_shifts_stripped": stripped})

    # summary file
    txt = pc.guest(env, f"cat {SUMMARY} 2>/dev/null") if pc else ""
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    line_ok, cover_named = 0, 0
    names_all = list(staff)
    for e in exp["requests"]:
        first, last = e["name"].split()[0].lower(), e["name"].split()[-1].lower()
        mine = [ln for ln in lines if first in ln.lower() or last in ln.lower()]
        word = "approv" if e["decision"] == "Approved" else "declin"
        hits = [re.search(r"not approv|approv|declin|refus|reject", ln.lower()) for ln in mine]
        if any(m and (m.group(0) == word or (word == "declin" and m.group(0) in ("refus", "reject", "not approv")))
               for m in hits):
            line_ok += 1
            if e["decision"] == "Approved" and any(
                    n != e["name"] and (n.split()[0].lower() in ln.lower() or n.split()[-1].lower() in ln.lower())
                    for ln in mine for n in names_all):
                cover_named += 1
    n_app = len(approved)
    checks.update({"summary_found": bool(lines), "summary_lines_ok": f"{line_ok}/{len(exp['requests'])}",
                   "summary_cover_named": f"{cover_named}/{n_app}"})

    score = (0.30 * dec_ok / len(exp["requests"]) + 0.05 * comments_ok / n_dec + 0.03 * other_untouched
             + 0.15 * sum(off.values()) / n_app
             + 0.15 * (sum(covered.values()) / len(covered) if covered else 0)
             + 0.12 * (sum(legal.values()) / len(legal) if legal else 0)
             + 0.05 * (not stripped) + 0.10 * line_ok / len(exp["requests"]) + 0.05 * cover_named / n_app)
    decided = sum(reqs.get(e["id"], {}).get("status") != "Pending" for e in exp["requests"])
    caps = [(decided == 0, 0.2), (not all(off.values()), 0.6), (bool(bad), 0.7), (bool(wrong), 0.75)]
    for cond, cap in caps:
        if cond:
            score = min(score, cap)
    return pc.result(score, checks)


# ---------------------------------------------------------------- B: open shifts + printed rota
def _pdf_text(path):
    try:
        import fitz
        with fitz.open(path) as doc:
            return "\n".join(p.get_text() for p in doc)
    except Exception:
        return ""


def _pdf_rows(text: str) -> dict:
    """{(day, shift): text of that row} for the print view layout 'Mon 16 Nov  Early ...  names'."""
    lab = {f"{dt.date.fromisoformat(d).strftime('%a')} {int(d[8:])} Nov": d for d in WEEK}
    rx = re.compile(r"(" + "|".join(re.escape(k) for k in lab) + r")\s+(Early|Late|Night)\b")
    hits = list(rx.finditer(text))
    out = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        out[(lab[m.group(1)], m.group(2)[0])] = text[m.end(): end]
    return out


def evaluate_rota(env, dest: str) -> dict:
    w = _world(env)
    if w is None:
        return pc.result(0.0, {"app_db": "unreadable"})
    exp, rota, staff, viol, pristine = w["exp"], w["rota"], w["staff"], w["viol"], w["pristine"]
    checks = {}
    open_slots = [tuple(k.split("|")) for k in exp["open_slots"]]
    filled, eligible, detail = 0, 0, {}
    for k in open_slots:
        ok_fill = staffing_ok(rota, staff, k)
        newcomers = [n for n in rota[k] if n not in pristine[k]]
        bad = [(n, why) for n, d, s, why in viol if (d, s) == k and n in newcomers]
        ok_el = ok_fill and bool(newcomers) and not bad
        filled += ok_fill
        eligible += ok_el
        detail[f"{k[0]} {k[1]}"] = {"now": rota[k], "problems": bad}
    all_staffed = all(staffing_ok(rota, staff, (d, s)) for d in WEEK for s in SHIFTS)
    on_leave_b = [f"{n} {d} {s}" for n, d, s, why in viol
                  if why == "on approved leave" and (d, s) in open_slots and n not in pristine[(d, s)]]
    approved_days = {e["name"]: set(e["days"]) for e in exp["requests"] if e["decision"] == "Approved"}
    removed = [f"{n} {d} {s}" for (d, s), names in pristine.items() for n in names
               if n not in rota[(d, s)] and d not in approved_days.get(n, ())]
    checks.update({"open_slots_filled": f"{filled}/{len(open_slots)}", "fillers_eligible": f"{eligible}/{len(open_slots)}",
                   "slots": detail, "week_fully_staffed": all_staffed, "rostered_on_leave_in_open_slots": on_leave_b,
                   "seed_assignments_removed": removed})
    # printed rota
    path = pc.fetch(env, PDF, dest + "_rota.pdf")
    is_pdf = bool(path) and open(path, "rb").read(5) == b"%PDF-"
    text = _pdf_text(path) if is_pdf else ""
    ever = {}
    for a in w["q"]["asg"]:
        ever.setdefault((a["day"], a["shift"]), set()).add(a["name"])
    labels = all(f"{int(d[8:])} Nov" in text for d in WEEK) and bool(re.search(r"16\s*[-–]\s*22 Nov", text))
    no_open = is_pdf and "OPEN" not in text
    rows = _pdf_rows(text)
    pdf_slots = 0.0
    for k in open_slots:
        cand = ever.get(k, set()) - set(pristine[k])
        seg = rows.get(k)
        if seg is not None:
            pdf_slots += 1.0 if any(n in seg for n in cand) and "OPEN" not in seg else 0.0
        elif text:
            pdf_slots += 0.5 if any(n in text for n in cand) else 0.0
    checks.update({"pdf_found": is_pdf, "pdf_week_labels": labels, "pdf_no_open": no_open,
                   "pdf_rows_parsed": len(rows), "pdf_open_slots_shown_filled": f"{pdf_slots:g}/{len(open_slots)}"})
    score = (0.24 * filled / len(open_slots) + 0.32 * eligible / len(open_slots) + 0.10 * all_staffed
             + 0.06 * (not removed) + 0.06 * is_pdf + 0.04 * labels + 0.08 * no_open + 0.10 * pdf_slots / len(open_slots))
    caps = [(filled == 0, 0.2), (bool(on_leave_b), 0.6), (eligible < len(open_slots), 0.75)]
    for cond, cap in caps:
        if cond:
            score = min(score, cap)
    return pc.result(score, checks)
