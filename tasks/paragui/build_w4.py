"""W4 - Quillon Talent (applicant tracking web app on :8104): processing scanned interview feedback (scorecards,
stage moves, onsite bookings) vs scheduling hiring-manager interviews and the weekly recruiting summary.

build(out_dir) writes: app_w4.py, seed.db, Interview_Decision_Rubric.pdf, expected.json.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import lib_w  # noqa: E402
from lib_w import font  # noqa: E402

PASSWORD = "Quillon-Talent-26"
WEEK = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
SOURCES = ["LinkedIn", "Referral", "Careers site", "Indeed", "Agency"]
CRITERIA = ["Technical skills", "Problem solving", "Communication", "Values & collaboration"]

USERS = [(1, "jordan.ellis", "Jordan Ellis", "Talent Acquisition Lead", 1), (2, "laura.chen", "Laura Chen", "Recruiter", 0)]
# id, name, title, team
PEOPLE = [
    (1, "Priya Raman", "Director of Engineering", "Engineering"),
    (2, "Tomas Novak", "Staff Software Engineer", "Engineering"),
    (3, "Aisha Bello", "Senior Software Engineer", "Engineering"),
    (4, "Kenji Watanabe", "Senior Software Engineer", "Engineering"),
    (5, "Helen Park", "Head of Clinical Data", "Clinical Data"),
    (6, "Samuel Osei", "Clinical Data Scientist", "Clinical Data"),
    (7, "Ben Carter", "Design Lead", "Product"),
    (8, "Kofi Mensah", "Engineering Manager, Platform", "Engineering"),
    (9, "Rachel Adams", "VP Customer Success", "Customer Success"),
    (10, "Nina Petrova", "Senior Data Engineer", "Engineering"),
]
# person: {weekday: [(start, end)]}
AVAIL = {
    1: {0: [("09:00", "12:00"), ("13:00", "17:00")], 1: [("09:00", "12:00")], 2: [("13:00", "17:00")], 3: [("09:00", "12:30")], 4: [("09:00", "12:00")]},
    2: {0: [("09:00", "11:00"), ("14:00", "17:00")], 1: [("09:00", "11:00")], 3: [("10:00", "12:00")]},
    3: {1: [("10:00", "12:00")], 2: [("13:00", "17:00")], 4: [("09:00", "12:00")]},
    4: {0: [("13:00", "17:00")], 2: [("13:00", "17:00")], 3: [("13:00", "16:00")]},
    5: {0: [("09:00", "12:00")], 2: [("09:00", "12:00")], 3: [("13:00", "17:00")]},
    6: {0: [("10:00", "12:00")], 3: [("14:00", "17:00")], 4: [("13:00", "16:00")]},
    7: {1: [("13:00", "17:00")], 3: [("09:00", "12:00")]},
    8: {0: [("10:00", "12:00")], 2: [("14:00", "17:00")], 3: [("09:00", "12:00")]},
    9: {1: [("09:00", "11:00")]},
    10: {0: [("13:00", "16:00")], 4: [("09:00", "12:00")]},
}
OOO = [(1, "2026-10-30", "HLTH conference"), (7, "2026-10-29", "Vacation"), (3, "2026-10-16", "Sick leave")]

PLAN_214 = ("1. Recruiter screen (30 min, recruiter)\n2. Phone interview (45 min) with one engineer from the panel\n"
            "3. Onsite loop: ONE 90-minute session, interview type \"Onsite loop\", with the hiring manager Priya Raman and "
            "exactly one engineer from the panel (Tomas Novak, Aisha Bello or Kenji Watanabe)\n4. Offer")
REQS = [  # id, code, title, dept, location, hm, recruiter, status, opened, plan
    (1, "REQ-208", "Customer Success Manager", "Customer Success", "Boston, MA", 9, 2, "On hold", "2026-08-03",
     "1. Recruiter screen\n2. Hiring manager interview (45 min) with Rachel Adams\n3. Onsite loop (2 h)"),
    (2, "REQ-214", "Senior Backend Engineer", "Engineering", "Remote (US)", 1, 1, "Open", "2026-08-24", PLAN_214),
    (3, "REQ-216", "Clinical Data Analyst", "Clinical Data", "Boston, MA (hybrid)", 5, 1, "Open", "2026-09-07",
     "1. Recruiter screen (30 min)\n2. Phone interview (45 min) with Helen Park or Dr. Samuel Osei\n"
     "3. Onsite loop: ONE 60-minute session, interview type \"Onsite loop\", with both Helen Park and Samuel Osei\n4. Offer"),
    (4, "REQ-219", "Product Designer", "Product", "Boston, MA (hybrid)", 7, 2, "Open", "2026-09-14",
     "1. Recruiter screen\n2. Portfolio review (60 min) with Ben Carter\n3. Onsite loop (2 h)"),
    (5, "REQ-221", "Staff Data Engineer", "Engineering", "Remote (US)", 1, 1, "Open", "2026-09-21",
     "1. Recruiter screen (30 min)\n2. Hiring manager interview: 45 minutes with Priya Raman (interview type "
     "\"Hiring manager interview\"); move the candidate to the stage \"HM interview\" once it is booked\n"
     "3. Onsite loop (2 h) with Priya Raman, Nina Petrova and Kofi Mensah"),
    (6, "REQ-223", "Engineering Manager, Platform", "Engineering", "Remote (US)", 8, 2, "Open", "2026-09-28",
     "1. Recruiter screen\n2. Hiring manager interview (45 min) with Kofi Mensah\n3. Technical interview (60 min) with Priya Raman\n4. Onsite loop"),
]

# ---------------------------------------------------------------- task A: the eight candidates awaiting a decision
# name, req id, interviewer (people id), scores, recommendation, interview date, comment, availability note,
# expected stage
A_CANDS = [
    ("Ethan Brooks", 2, 2, (4, 4, 3, 4), "Hire", "2026-10-19", "Solid API design, explained trade-offs clearly. A bit quiet "
     "when discussing on-call, but good overall.", "Flexible - any time", "Onsite"),
    ("Mariam Haddad", 2, 3, (5, 4, 4, 5), "Strong hire", "2026-10-20", "Excellent. Designed the queue consumer from scratch, "
     "great questions about our HIPAA constraints.", "Not available Tuesday 27 Oct", "Onsite"),
    ("Lucas Meyer", 2, 4, (4, 4, 4, 3), "No hire", "2026-10-20", "Strong coder, but dismissive about code review and blamed "
     "teammates for past incidents. Collaboration concerns.", "Mornings preferred", "Rejected"),
    ("Chloe Dubois", 2, 2, (3, 3, 4, 3), "Strong hire", "2026-10-21", "Very motivated, great communicator. Technical depth "
     "average for senior level - would like a second opinion.", "Flexible", "Hiring manager review"),
    ("Victor Lindqvist", 2, 3, (2, 2, 3, 2), "Hire", "2026-10-21", "Nice person, but struggled with the concurrency question "
     "and needed many hints.", "Flexible", "Rejected"),
    ("Amara Okafor", 3, 6, (4, 3, 4, 4), "Hire", "2026-10-19", "Good SQL and R, sensible on missing data in trial datasets. "
     "Clear communicator.", "Afternoons only (start 13:00 ET or later)", "Onsite"),
    ("Daniel Kim", 3, 6, (3, 2, 3, 3), "Hire", "2026-10-20", "Knows CDISC basics, weaker on statistics. Could grow into "
     "the role.", "Flexible", "Hiring manager review"),
    ("Sofia Marin", 3, 5, (2, 3, 2, 2), "No hire", "2026-10-22", "Limited hands-on experience with clinical data; answers "
     "stayed generic.", "Flexible", "Rejected"),
]
# candidate availability constraints used by the checkers: allowed dates, earliest start, latest end (minutes)
CONSTRAINTS = {
    "Ethan Brooks": {}, "Mariam Haddad": {"not_dates": ["2026-10-27"]}, "Amara Okafor": {"min_start": 13 * 60},
    "Nadia Rahman": {"max_end": 12 * 60}, "Owen Fischer": {"not_dates": ["2026-10-26"]},
    "Keiko Sato": {"dates": ["2026-10-28", "2026-10-29"]}, "Luis Ortega": {"min_start": 13 * 60}, "Grace Mwangi": {},
}
ONSITE = {2: {"minutes": 90, "required": [1], "pool": [2, 3, 4]}, 3: {"minutes": 60, "required": [5, 6], "pool": []}}
# ---------------------------------------------------------------- task B: five REQ-221 candidates
B_CANDS = [("Nadia Rahman", "Mornings only (must finish by 12:00 ET)", "Referral"),
           ("Owen Fischer", "Not available Monday 26 Oct", "LinkedIn"),
           ("Keiko Sato", "Only Wednesday 28 or Thursday 29 Oct", "Agency"),
           ("Luis Ortega", "Afternoons only (start 13:00 ET or later)", "LinkedIn"),
           ("Grace Mwangi", "Flexible - any time", "Careers site")]

FIRST = ["Aaron", "Bianca", "Carlos", "Diana", "Elif", "Farah", "Gabriel", "Hana", "Ivan", "Julia", "Kwame", "Leah", "Mateo",
         "Noor", "Oscar", "Paula", "Quinn", "Ravi", "Sara", "Theo", "Uma", "Viktor", "Wen", "Ximena", "Yusuf", "Zoe",
         "Adil", "Brianna", "Cyrus", "Dalia", "Emeka", "Fiona", "Gustavo", "Hiro", "Ines", "Jamal", "Katya", "Liam"]
LAST = ["Adler", "Banerjee", "Costa", "Dimitrov", "Eriksen", "Fontaine", "Gallagher", "Hosseini", "Ibrahim", "Jensen",
        "Kowalski", "Larsen", "Moreau", "Nakamura", "Oyelaran", "Petrov", "Quintero", "Rossi", "Silva", "Tanaka",
        "Uddin", "Varga", "Walsh", "Xu", "Yilmaz", "Zimmerman", "Abbott", "Brennan", "Chowdhury", "Delgado"]
TITLES = {1: ["Customer Success Lead", "Account Manager", "Implementation Specialist"],
          2: ["Backend Engineer", "Software Engineer II", "Senior Software Engineer", "Platform Engineer"],
          3: ["Data Analyst", "Clinical Data Coordinator", "Biostatistics Associate"],
          4: ["UX Designer", "Product Designer", "Visual Designer"],
          5: ["Data Engineer", "Senior Data Engineer", "Analytics Engineer"],
          6: ["Engineering Manager", "Tech Lead", "Senior Engineering Manager"]}
CITIES = ["Boston, MA", "Austin, TX", "Denver, CO", "Chicago, IL", "Raleigh, NC", "Seattle, WA", "Atlanta, GA", "Portland, OR",
          "Philadelphia, PA", "Columbus, OH"]


# ---------------------------------------------------------------- scanned feedback form (pixel-only)
INK = (28, 52, 140)


def _x_mark(dr, cx, cy, rng, r=13):
    j = lambda: rng.uniform(-2.5, 2.5)  # noqa: E731
    dr.line((cx - r + j(), cy - r + j(), cx + r + j(), cy + r + j()), fill=INK, width=4)
    dr.line((cx + r + j(), cy - r + j(), cx - r + j(), cy + r + j()), fill=INK, width=4)


def _check(dr, x, y, rng):
    dr.line((x + 4, y + 14 + rng.uniform(-2, 2), x + 12, y + 24), fill=INK, width=4)
    dr.line((x + 12, y + 24, x + 28 + rng.uniform(-2, 2), y - 2), fill=INK, width=4)


def feedback_scan(path, cand, req, interviewer, date, scores, rec, comment, seed):
    rng = random.Random(seed)
    W, H = 1100, 1240
    im = Image.new("RGB", (W, H), (252, 252, 249))
    dr = ImageDraw.Draw(im)
    dr.rectangle((60, 50, 120, 110), fill=(15, 76, 69))
    dr.text((74, 58), "Q", fill="white", font=font(40, bold=True))
    dr.text((140, 52), "QUILLON HEALTH", fill=(15, 76, 69), font=font(30, bold=True))
    dr.text((140, 92), "People team - Interview feedback form (v3)", fill=(60, 60, 60), font=font(18))
    dr.text((W - 330, 60), "CONFIDENTIAL", fill=(150, 40, 40), font=font(20, bold=True))
    y = 150
    hand = font(24)
    for label, value in (("Candidate", cand), ("Position", f"{req[0]}  {req[1]}"), ("Interview", "Phone interview (45 min)"),
                         ("Date", date), ("Interviewer", interviewer)):
        dr.text((60, y), label + ":", fill=(40, 40, 40), font=font(19, bold=True))
        dr.line((230, y + 30, W - 60, y + 30), fill=(120, 120, 120), width=1)
        dr.text((245 + rng.randint(-3, 6), y - 2 + rng.randint(-2, 2)), value, fill=INK, font=hand)
        y += 52
    y += 20
    dr.text((60, y), "Ratings - mark ONE box per row (1 = poor, 5 = excellent)", fill=(30, 30, 30), font=font(19, bold=True))
    y += 40
    cols = [60, 430, 550, 670, 790, 910, 1040]
    dr.rectangle((cols[0], y, cols[-1], y + 44), fill=(232, 238, 236))
    dr.text((cols[0] + 10, y + 11), "Criterion", fill=(30, 30, 30), font=font(18, bold=True))
    for k in range(5):
        dr.text((cols[k + 1] + 50, y + 11), str(k + 1), fill=(30, 30, 30), font=font(18, bold=True))
    top = y
    y += 44
    for crit, sc in zip(CRITERIA, scores):
        dr.text((cols[0] + 10, y + 22), crit, fill=(30, 30, 30), font=font(18))
        for k in range(5):
            bx = cols[k + 1] + 40
            dr.rectangle((bx, y + 16, bx + 36, y + 52), outline=(70, 70, 70), width=2)
            if k + 1 == sc:
                _x_mark(dr, bx + 18, y + 34, rng)
        y += 68
    for x in cols:
        dr.line((x, top, x, y), fill=(150, 150, 150), width=1)
    dr.line((cols[0], y, cols[-1], y), fill=(150, 150, 150), width=1)
    y += 40
    dr.text((60, y), "Overall recommendation:", fill=(30, 30, 30), font=font(19, bold=True))
    x = 340
    for opt in ("Strong hire", "Hire", "No hire"):
        dr.rectangle((x, y - 2, x + 30, y + 28), outline=(70, 70, 70), width=2)
        if opt == rec:
            _check(dr, x, y, rng)
        dr.text((x + 42, y), opt, fill=(30, 30, 30), font=font(19))
        x += 230
    y += 70
    dr.text((60, y), "Comments:", fill=(30, 30, 30), font=font(19, bold=True))
    y += 40
    for ln in lib_w.wrap(dr, comment, font(22), W - 160):
        dr.text((80 + rng.randint(0, 6), y), ln, fill=INK, font=font(22))
        y += 38
    y = max(y + 50, H - 150)
    dr.line((60, y + 40, 460, y + 40), fill=(120, 120, 120), width=1)
    dr.text((60, y + 48), "Interviewer signature", fill=(90, 90, 90), font=font(15))
    first, last = interviewer.split(" ", 1)
    dr.text((80, y), f"{first[0]}. {last}", fill=INK, font=font(30))
    dr.text((W - 420, y + 48), "Return to the recruiter within 24 h", fill=(90, 90, 90), font=font(15))
    im = im.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, fillcolor=(252, 252, 249))
    lib_w.photo_noise(im, seed, 7)
    im.save(path, optimize=True)


def rubric_pdf(path):
    blocks = [
        ("title", "Interview decision rubric"),
        ("p", "Quillon Health - Talent Acquisition. Version 2, effective 1 September 2026. Applies to all requisitions after "
              "the phone interview."),
        ("h", "1. Scorecards"),
        ("p", "Interviewers hand in a paper feedback form; the recruiter scans it to the candidate's profile. Enter every form "
              "as a scorecard in Quillon Talent exactly as written: the interviewer named on the form, round \"Phone "
              "interview\", the four ratings and the overall recommendation. Do not round or adjust ratings."),
        ("h", "2. Decision (apply the rules in this order)"),
        ("p", "The average is the mean of the four ratings on the form."),
        ("table", [["#", "Condition", "Move the candidate to"],
                   ["1", "Recommendation is \"No hire\" (whatever the ratings)", "Rejected - reason \"Did not pass interview\""],
                   ["2", "Average of 3.5 or higher", "Onsite"],
                   ["3", "Average below 2.5", "Rejected - reason \"Did not pass interview\""],
                   ["4", "Anything else (average 2.5 to 3.49)", "Hiring manager review"]], [70, 520, 430]),
        ("p", "A \"Strong hire\" recommendation does not override the average."),
        ("h", "3. Booking the onsite loop"),
        ("li", "Book the onsite loop for the week after the decision, exactly as the requisition's interview plan describes "
               "(interview type, length, panel)."),
        ("li", "Every panelist must be available for the whole slot: use their weekly interview availability on the "
               "Interviewers page; out-of-office days override it."),
        ("li", "Never double-book: the slot must not overlap any interview already in the calendar for any panelist."),
        ("li", "Respect the candidate's availability note on their profile."),
        ("h", "4. Keep the hiring team informed"),
        ("p", "After a batch of decisions, add a note on each requisition listing who goes to onsite (with the date), who "
              "goes to hiring manager review and who was rejected."),
    ]
    lib_w.doc_pdf(path, blocks, header="Quillon Health · Talent Acquisition · INTERNAL", footer="Interview_Decision_Rubric v2")


# ---------------------------------------------------------------- build
def build(out):
    os.makedirs(out, exist_ok=True)
    rng = random.Random(20261104)
    lib_w.copy_app(HERE, out, "app_w4.py")
    con, app = lib_w.fresh_db(HERE, "app_w4.py", f"{out}/seed.db")
    for uid, user, name, title, login in USERS:
        con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (uid, user, PASSWORD if login else "", name,
                                                                 f"{user}@quillonhealth.com", title, login))
    for pid, name, title, team in PEOPLE:
        con.execute("INSERT INTO people VALUES (?,?,?,?,?)", (pid, name, title, team, name.lower().replace(" ", ".") + "@quillonhealth.com"))
    for pid, days in AVAIL.items():
        for wd, wins in days.items():
            for s, e in wins:
                con.execute("INSERT INTO avail (person_id,weekday,start,end) VALUES (?,?,?,?)", (pid, wd, s, e))
    for o in OOO:
        con.execute("INSERT INTO ooo (person_id,date,reason) VALUES (?,?,?)", o)
    for r in REQS:
        con.execute("INSERT INTO reqs VALUES (?,?,?,?,?,?,?,?,?,?)", r)
    req_by_id = {r[0]: r for r in REQS}
    cid = [100]
    used = set()

    def add_cand(name, req, stage, source, applied, avail="", title=None, reason=None, updated=None):
        cid[0] += 1
        used.add(name)
        rid = req_by_id[req]
        first, last = name.split(" ", 1)
        con.execute("INSERT INTO cands VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid[0], name, f"{first.lower()}.{last.lower().replace(' ', '')}@{rng.choice(['gmail.com', 'outlook.com', 'proton.me', 'icloud.com'])}",
                     f"+1 ({rng.randint(201, 989)}) 555-{rng.randint(1000, 9999)}", rng.choice(CITIES), title or rng.choice(TITLES[req]),
                     req, stage, reason, source, applied, rid[6], avail, updated or f"{applied} {rng.randint(9, 17):02d}:{rng.randint(0, 59):02d}:00"))
        return cid[0]

    def add_iv(cand, kind, date, start, minutes, panel, created="2026-10-16 10:00:00"):
        iid = con.execute("INSERT INTO interviews (cand_id,kind,date,start,minutes,notes,user_id,created,updated) VALUES (?,?,?,?,?,?,?,?,?)",
                          (cand, kind, date, start, minutes, "", 1, created, created)).lastrowid
        for p in panel:
            con.execute("INSERT INTO panel VALUES (?,?)", (iid, p))

    tmp = os.path.join(out, "_scans")
    os.makedirs(tmp, exist_ok=True)

    def add_scan(cand, name, req, interviewer, date, scores, rec, comment, seed):
        fn = f"feedback_{name.split()[1].lower()}_{date}.png"
        feedback_scan(f"{tmp}/{fn}", name, (req_by_id[req][1], req_by_id[req][2]), dict((p[0], p[1]) for p in PEOPLE)[interviewer],
                      date, scores, rec, comment, seed)
        con.execute("INSERT INTO atts (cand_id,filename,label,ctype,data,created) VALUES (?,?,?,?,?,?)",
                    (cand, fn, "Interview feedback (scan)", "image/png", open(f"{tmp}/{fn}", "rb").read(), f"{date} 18:{seed % 50 + 5:02d}:00"))
        os.remove(f"{tmp}/{fn}")

    # --- two REQ-214 candidates already processed last week (examples of a finished scorecard + onsite)
    jonas = add_cand("Jonas Weber", 2, "Onsite", "Referral", "2026-09-02", "Flexible", "Senior Software Engineer")
    add_scan(jonas, "Jonas Weber", 2, 4, "2026-10-13", (4, 5, 4, 4), "Strong hire", "Very strong systems thinking.", 7)
    con.execute("INSERT INTO scorecards (cand_id,person_id,round,s1,s2,s3,s4,rec,notes,user_id,created) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (jonas, 4, "Phone interview", 4, 5, 4, 4, "Strong hire", "", 1, "2026-10-14 09:10:00"))
    add_iv(jonas, "Phone interview", "2026-10-13", "10:00", 45, [4])
    add_iv(jonas, "Onsite loop", "2026-10-27", "09:00", 90, [1, 2])
    rhea = add_cand("Rhea Kapoor", 2, "Rejected", "LinkedIn", "2026-09-05", "", reason="Did not pass interview")
    add_scan(rhea, "Rhea Kapoor", 2, 2, "2026-10-14", (2, 2, 2, 3), "No hire", "Could not finish the exercise.", 8)
    con.execute("INSERT INTO scorecards (cand_id,person_id,round,s1,s2,s3,s4,rec,notes,user_id,created) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rhea, 2, "Phone interview", 2, 2, 2, 3, "No hire", "", 1, "2026-10-15 09:00:00"))
    add_iv(rhea, "Phone interview", "2026-10-14", "14:00", 45, [2])
    # --- task A's eight
    a_exp = {}
    for k, (name, req, iv, scores, rec, date, comment, avail, stage) in enumerate(A_CANDS):
        c = add_cand(name, req, "Interviewed - awaiting decision", rng.choice(SOURCES[:4]), f"2026-09-{10 + k * 2:02d}", avail,
                     updated=f"{date} 18:30:00")
        add_iv(c, "Phone interview", date, ["10:00", "14:00", "15:00", "11:00"][k % 4], 45, [iv])
        add_scan(c, name, req, iv, date, scores, rec, comment, 100 + k)
        a_exp[str(c)] = {"name": name, "req": req, "interviewer": iv, "scores": list(scores), "rec": rec, "stage": stage,
                         "constraint": CONSTRAINTS.get(name, {})}
    # --- task B's five (REQ-221, phone screen passed)
    b_exp = {}
    for k, (name, avail, src) in enumerate(B_CANDS):
        c = add_cand(name, 5, "Phone screen", src, f"2026-10-{1 + k * 2:02d}", avail, updated=f"2026-10-{15 + k % 3} 16:00:00")
        b_exp[str(c)] = {"name": name, "constraint": CONSTRAINTS[name]}
    # --- everybody else
    names = [f"{f} {l}" for f, l in zip(FIRST * 2, LAST + LAST[::-1]) if f"{f} {l}" not in used]
    rng.shuffle(names)
    stage_pool = {"old": ["Rejected", "Rejected", "Withdrawn", "Phone screen", "Hiring manager review", "Applied"],
                  "new": ["Applied", "Applied", "Applied", "Phone screen"]}
    others = []
    for k in range(57):
        name = names[k]
        req = [2, 2, 3, 4, 5, 6, 1, 5, 2, 6][k % 10]
        recent = k % 5 in (0, 2) or k >= 50
        if recent:
            applied = f"2026-10-{19 + rng.randrange(5)}"
            stage = rng.choice(stage_pool["new"])
        else:
            day = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(48))
            applied = day.isoformat()
            stage = rng.choice(stage_pool["old"])
        src = rng.choices(SOURCES, weights=[5, 2, 4, 3, 1])[0]
        reason = rng.choice(["Not qualified (screen)", "Salary expectations"]) if stage == "Rejected" else None
        others.append((add_cand(name, req, stage, src, applied, rng.choice(["Flexible", "", "Mornings preferred", ""]), reason=reason), req, stage))
    # --- calendar: candidates in later stages of other requisitions with interviews next week
    hm221 = add_cand("Tariq Aziz", 5, "HM interview", "Referral", "2026-09-29", "Flexible")
    em1 = add_cand("Sophie Laurent", 6, "Hiring manager review", "Agency", "2026-09-30", "Flexible")
    em2 = add_cand("Marcus Lee", 6, "Phone screen", "LinkedIn", "2026-10-02", "")
    be1 = add_cand("Hannah Vogel", 2, "Phone screen", "Careers site", "2026-10-05", "")
    be2 = add_cand("Rohan Mehta", 2, "Phone screen", "LinkedIn", "2026-10-06", "")
    be3 = add_cand("Ana Ribeiro", 2, "Phone screen", "Indeed", "2026-10-07", "")
    cd1 = add_cand("Peter Novak", 3, "Hiring manager review", "Referral", "2026-09-20", "")
    cd2 = add_cand("Lina Haddad", 3, "Phone screen", "LinkedIn", "2026-10-08", "")
    pd1 = add_cand("Clara Jensen", 4, "Onsite", "Referral", "2026-09-18", "")
    de2 = add_cand("Mehmet Kaya", 5, "Phone screen", "Indeed", "2026-10-09", "")
    for cand, kind, date, start, m, panel in [
            (em1, "Technical interview", "2026-10-26", "13:00", 60, [1]), (hm221, "Hiring manager interview", "2026-10-28", "14:30", 45, [1]),
            (em2, "Technical interview", "2026-10-29", "11:30", 60, [1]), (be1, "Phone interview", "2026-10-26", "15:30", 60, [2]),
            (be2, "Phone interview", "2026-10-28", "13:00", 60, [3]), (be3, "Phone interview", "2026-10-28", "16:00", 60, [4]),
            (cd1, "Hiring manager interview", "2026-10-26", "09:00", 60, [5]), (cd2, "Phone interview", "2026-10-29", "13:00", 60, [5]),
            (cd2, "Technical interview", "2026-10-29", "15:00", 60, [6]), (pd1, "Onsite loop", "2026-10-27", "14:00", 120, [7]),
            (em2, "Phone interview", "2026-10-26", "10:00", 60, [8]), (de2, "Phone interview", "2026-10-30", "09:30", 60, [10])]:
        add_iv(cand, kind, date, start, m, panel)
    # a few interviews this week for the calendar's current-week view
    for cand, _, _ in [o for o in others if o[2] in ("Phone screen", "Hiring manager review")][:6]:
        add_iv(cand, "Phone interview", f"2026-10-{19 + cand % 5}", ["09:00", "11:00", "14:00", "16:00"][cand % 4], 30, [cand % 10 + 1])
    con.execute("INSERT INTO notes (kind,ref_id,user_id,body,created) VALUES (?,?,?,?,?)",
                ("req", 2, 1, "Update 16 Oct: Jonas Weber -> onsite Tue 27 Oct 09:00 (Priya + Tomas). Rhea Kapoor rejected.", "2026-10-16 17:20:00"))
    os.rmdir(tmp)
    con.commit()
    # ground truth
    apps = {}
    for code, src, n in con.execute("SELECT r.code, c.source, COUNT(*) FROM cands c JOIN reqs r ON r.id=c.req_id WHERE c.applied "
                                    "BETWEEN '2026-10-19' AND '2026-10-23' GROUP BY r.code, c.source"):
        apps.setdefault(code, {})[src] = n
    maxes = {k: con.execute(f"SELECT COALESCE(MAX(id),0) FROM {k}").fetchone()[0] for k in ("scorecards", "notes", "interviews", "events")}
    seed_stage = {str(r[0]): r[1] for r in con.execute("SELECT id, stage FROM cands")}
    con.close()
    rubric_pdf(f"{out}/Interview_Decision_Rubric.pdf")
    json.dump({"port": 8104, "user": "jordan.ellis", "password": PASSWORD, "jordan_id": 1, "priya_id": 1, "week": WEEK,
               "people": {str(p[0]): p[1] for p in PEOPLE}, "a_cands": a_exp, "onsite": {str(k): v for k, v in ONSITE.items()},
               "reqs": {str(r[0]): r[1] for r in REQS}, "b_cands": b_exp, "b_minutes": 45, "applications": apps,
               "sources": SOURCES, "seed_max": maxes, "seed_stage": seed_stage, "xlsx": "Documents/recruiting_weekly_wk43.xlsx"},
              open(f"{out}/expected.json", "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/w4_out")
