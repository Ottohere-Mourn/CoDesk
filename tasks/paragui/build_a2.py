"""a2 - one Thunderbird calendar, two chores that book into the same free time.

Persona: Ines Varga, principal of Varga & Hale Architects (Bristol). Her assistant Ruth is on maternity leave and
left a handover mail on how the calendar is run. Week of Mon 23 - Fri 27 Nov 2026, Home calendar ~60% full.
Task A (pga2requests): six meeting requests (one only in a handwritten note image, one changed by a follow-up mail)
                       -> first choice if free, else the alternative; reply drafts where the first choice was not booked.
Task B (pga2visits):   three building-control inspections from a scanned schedule -> one trip block each (travel from
                       Marco's mail); three 1-hour design reviews at the EARLIEST free slots Tue-Thu 10:00-17:00;
                       a draft to the studio team listing the review times.
Contention: three of A's first choices are exactly B's earliest free review slots in the pristine calendar. Run one
after the other, the second task sees the first's entries and goes elsewhere (both pass, different outcomes); run at
the same time from the same snapshot, both book the same hours (double booking) - which both checkers reject.
"""
from __future__ import annotations

import datetime as dt
import os
import random
import sqlite3
import tarfile
import tempfile
import uuid
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from lib_mmail import (HOME_CAL, DocPage, build_profile, dump_expected, font, msg, pdf_scan, png_bytes, scan_look)
from lib_thunderbird import PROFILE, TB_BASE

TZ = "Europe/London"
LON = ZoneInfo(TZ)
ME = ("Ines Varga", "ines.varga@vargahale.co.uk")
HOST = "pop.vargahale.co.uk"
INES = f"{ME[0]} <{ME[1]}>"
TEAM = "team@vargahale.co.uk"


def at(month, day, hh, mm=0):
    return dt.datetime(2026, month, day, hh, mm, tzinfo=LON)


def mid(tag, dom="vargahale.co.uk"):
    return f"<pga2.{tag}@{dom}>"


# ---------------------------------------------------------------- the calendar before the week starts
SEED = [  # (title, start, end, location)
    ("Studio stand-up", "2026-11-23 09:00", "2026-11-23 09:30", "Studio"),
    ("Lunch (keep free)", "2026-11-23 12:30", "2026-11-23 13:30", ""),
    ("Fee proposal workshop - Q1 bids", "2026-11-23 14:00", "2026-11-23 15:30", "Studio meeting room"),
    ("Call: Kerr family (Ashby Road)", "2026-11-23 16:30", "2026-11-23 17:30", "Phone"),
    ("Practice meeting", "2026-11-24 09:00", "2026-11-24 10:30", "Studio meeting room"),
    ("Call: Halden Associates - Fenwick steelwork", "2026-11-24 11:30", "2026-11-24 12:30", "Phone"),
    ("Lunch (keep free)", "2026-11-24 12:30", "2026-11-24 13:30", ""),
    ("Sign off drawings - Fenwick residence", "2026-11-24 13:30", "2026-11-24 14:00", "Studio"),
    ("Weekly fee tracker", "2026-11-24 17:00", "2026-11-24 17:30", ""),
    ("Portfolio review with Marco", "2026-11-25 09:00", "2026-11-25 10:00", "Studio"),
    ("Lunch (keep free)", "2026-11-25 12:30", "2026-11-25 13:30", ""),
    ("Team stand-up", "2026-11-25 13:30", "2026-11-25 14:00", "Studio"),
    ("Client: Fenwick residence - interiors", "2026-11-25 15:00", "2026-11-25 16:00", "Studio meeting room"),
    ("Project leads meeting", "2026-11-26 09:00", "2026-11-26 10:00", "Studio meeting room"),
    ("Planning committee prep - Ashby Road", "2026-11-26 11:00", "2026-11-26 12:30", "Studio"),
    ("Lunch (keep free)", "2026-11-26 12:30", "2026-11-26 13:30", ""),
    ("Supplier CPD: Kingspan insulation", "2026-11-26 14:30", "2026-11-26 15:30", "Studio meeting room"),
    ("Studio stand-up", "2026-11-27 09:00", "2026-11-27 09:30", "Studio"),
    ("Lunch (keep free)", "2026-11-27 12:30", "2026-11-27 13:30", ""),
    ("Friday pin-up", "2026-11-27 16:30", "2026-11-27 17:30", "Studio"),
]


def prtime(local: str) -> int:
    t = dt.datetime.strptime(local, "%Y-%m-%d %H:%M").replace(tzinfo=LON)
    return int(t.timestamp()) * 1_000_000


def seeded_calendar(seed=48) -> tuple[bytes, list]:
    """The base profile's (empty) local.sqlite with the seeded week, rows as CalStorageItemModel writes them."""
    r = random.Random(seed)
    tmp = tempfile.mkdtemp()
    with tarfile.open(TB_BASE) as t:
        data = t.extractfile(t.getmember(f".thunderbird/{PROFILE}/calendar-data/local.sqlite")).read()
    path = f"{tmp}/local.sqlite"
    open(path, "wb").write(data)
    con = sqlite3.connect(path)
    now = int(dt.datetime(2026, 11, 2, 9, tzinfo=dt.timezone.utc).timestamp()) * 1_000_000
    ids = []
    for title, s, e, loc in SEED:
        uid = str(uuid.UUID(int=r.getrandbits(128), version=4))
        ids.append({"id": uid, "title": title, "start": s, "end": e})
        con.execute("INSERT INTO cal_events (cal_id,id,time_created,last_modified,title,priority,privacy,ical_status,"
                    "flags,event_start,event_end,event_stamp,event_start_tz,event_end_tz) VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (HOME_CAL, uid, now, now, title, None, None, None, 4, prtime(s), prtime(e), now, TZ, TZ))
        for k, v in (("LOCATION", loc), ("TRANSP", "OPAQUE")):
            if v:
                con.execute("INSERT INTO cal_properties (item_id,key,value,recurrence_id,recurrence_id_tz,cal_id) "
                            "VALUES (?,?,?,?,?,?)", (uid, k, v, None, None, HOME_CAL))
    con.commit()
    con.close()
    out = open(path, "rb").read()
    os.remove(path)
    os.rmdir(tmp)
    return out, ids


# ---------------------------------------------------------------- task A: requests
TEAMS = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_MoorPlanning48Varga%40thread.v2/0"
REQUESTS = [
    dict(key="harlow", requester="emma@harlowfinch.co.uk", attendees=["emma@harlowfinch.co.uk", "daniel@harlowfinch.co.uk"],
         words=["harlow", "finch"], first=("2026-11-24 10:30", "2026-11-24 11:30"),
         alt=("2026-11-23 15:30", "2026-11-23 16:30"), loc=["meetingroom", "studio"]),
    dict(key="brightwell", requester="sean@brightwellbuild.co.uk",
         attendees=["sean@brightwellbuild.co.uk", "priya.nair@brightwellbuild.co.uk"],
         words=["brightwell", "lindencourt"], first=("2026-11-25 14:00", "2026-11-25 15:00"),
         alt=("2026-11-27 10:00", "2026-11-27 11:00"), loc=["linden"]),
    dict(key="moor", requester="hannah@moorplanning.co.uk", attendees=["hannah@moorplanning.co.uk"],
         words=["moor", "preapp"], first=("2026-11-24 16:00", "2026-11-24 17:00"),
         alt=("2026-11-27 14:00", "2026-11-27 15:00"), loc=["teamsmicrosoft"]),
    dict(key="halden", requester="tom.halden@halden-eng.co.uk", attendees=["tom.halden@halden-eng.co.uk"],
         words=["halden", "beam", "loft"], first=("2026-11-23 10:00", "2026-11-23 10:45"),
         alt=("2026-11-27 16:00", "2026-11-27 16:30"), loc=["phone", "call", "01174960321"]),
    dict(key="okonjo", requester="grace.okonjo@gmail.com", attendees=["grace.okonjo@gmail.com"],
         words=["okonjo", "gardenstudio"], first=("2026-11-23 14:00", "2026-11-23 15:00"),
         alt=("2026-11-27 11:30", "2026-11-27 12:30"), loc=["meetingroom", "studio"]),
    dict(key="ridgeway", requester="l.marsh@ridgewayha.org.uk", attendees=["l.marsh@ridgewayha.org.uk", "omar.siddiqui@ridgewayha.org.uk"],
         words=["ridgeway", "feasibility"], first=("2026-11-27 15:00", "2026-11-27 16:00"),
         alt=("2026-11-23 11:00", "2026-11-23 12:00"), loc=["millane", "ridgeway"]),
]

# ---------------------------------------------------------------- task B: inspections and reviews
INSPECTIONS = [  # site, keywords, inspection start/end, travel minutes each way -> blocked span
    dict(key="wharf", site="14 Wharf Street", words=["wharf"], start="2026-11-24 14:30", end="2026-11-24 15:15", travel=30,
         span=("2026-11-24 14:00", "2026-11-24 15:45")),
    dict(key="elm", site="Elm Grove Primary School", words=["elm"], start="2026-11-25 11:00", end="2026-11-25 11:45",
         travel=45, span=("2026-11-25 10:15", "2026-11-25 12:30")),
    dict(key="castle", site="3 Castle Mews", words=["castle"], start="2026-11-26 16:00", end="2026-11-26 16:30", travel=20,
         span=("2026-11-26 15:40", "2026-11-26 16:50")),
]
REVIEWS = [dict(key="wharf", words=["wharf"]), dict(key="elm", words=["elm"]), dict(key="castle", words=["castle"])]
REVIEW_WINDOW = {"days": ["2026-11-24", "2026-11-25", "2026-11-26"], "from": "10:00", "to": "17:00", "minutes": 60}


def note_png():
    """Tom Halden's handwritten availability, photographed on a train table."""
    im = Image.new("RGB", (1000, 700), (238, 232, 214))
    d = ImageDraw.Draw(im)
    for y in range(90, 700, 46):
        d.line((40, y, 960, y), fill=(190, 205, 225), width=2)
    d.line((110, 0, 110, 700), fill=(225, 160, 160), width=2)
    r = random.Random(7)
    lines = ["Ines -", "Ashby Rd loft beam calcs: quick call?", "Best for me: Mon 23rd, 10.00 - 10.45",
             "Failing that: Fri 27th, 4pm (half an hour)", "my mobile 0117 496 0321", "   - Tom H."]
    y = 52
    for ln in lines:
        x = 130
        f = font(38)
        for ch in ln:
            d.text((x, y + r.randint(-3, 3)), ch, font=f, fill=(25, 45, 120))
            x += int(d.textlength(ch, font=f)) + r.randint(-1, 1)
        y += 92
    im = im.rotate(-3.5, resample=Image.BICUBIC, expand=True, fillcolor=(96, 80, 64))
    return png_bytes(im, "JPEG")


def schedule_pdf(path):
    page = DocPage(
        "Bristol City Council - Building Control", "Temple Street, Bristol BS1 6AN  |  0117 922 3000  |  building.control@bristol.gov.uk",
        "Site inspection appointments - week commencing 23 November 2026",
        meta=[("Agent", "Varga & Hale Architects (Ines Varga)"), ("Issued", "17 November 2026"),
              ("Officer", "D. Okafor, Senior Building Control Surveyor")],
        table=(["Ref", "Site", "Stage", "Date / time", "Allow", "Architect"],
               [["BC/26/0412", "14 Wharf Street, BS1", "Foundations (pre-pour)", "Tue 24 Nov 14:30", "45 min", "YES"],
                ["BC/26/0388", "Linden Court, BS6", "Drainage test", "Thu 26 Nov 09:00", "30 min", "No"],
                ["BC/26/0397", "Elm Grove Primary School, BS7", "Drainage / below ground", "Wed 25 Nov 11:00", "45 min", "YES"],
                ["BC/26/0435", "3 Castle Mews, BS8", "Roof structure", "Thu 26 Nov 16:00", "30 min", "YES"]]),
        notes=["**Architect = YES: the agent/architect must attend the inspection on site.",
               "Please arrive on time; the surveyor cannot wait beyond 10 minutes.",
               "To rearrange, call 0117 922 3000 at least 48 hours in advance quoting the reference."],
        widths=[70, 140, 120, 100, 45, 37], footer="Bristol City Council Building Control - appointments are confirmed by this schedule only.")
    pdf_scan(path, [scan_look(page.image(), seed=482, angle=0.6, stamp="CONFIRMED")])


def build(d):
    os.makedirs(d, exist_ok=True)
    mails = []

    def add(key, frm, subject, when, body, unread=True, atts=(), cc=None, to=INES, irt=None):
        dom = frm.split("@")[1].rstrip(">")
        m = msg(frm, to, subject, when, mid(key, dom), body=body, attachments=atts, cc=cc, irt=irt)
        mails.append((m, when, unread))
        return m["Message-ID"]

    ruth = "Ruth Collins <ruth.collins@vargahale.co.uk>"
    rules = add("rules", ruth, "Your calendar - how I do it (handover)", at(11, 13, 16, 40),
                "Hi Ines,\n\nbefore I go off on maternity leave, here is how I have been running your calendar, so it "
                "keeps working while I'm away:\n\n"
                "1. Everything goes into your Home calendar in Thunderbird (it's what your phone syncs).\n"
                "2. Working day is 9:00-17:30. Lunch 12:30-13:30 is in the calendar every day - never book over it.\n"
                "3. Never double-book you. If a time is already taken by anything in the calendar, it is not free.\n"
                "4. Meeting requests: people always give a first choice and an alternative. Book the first choice if it "
                "is free, otherwise the alternative. If someone changes their request later, the latest email wins.\n"
                "5. Put the meeting place (room, address, phone number or video link) in the Location field and add "
                "the people named in the request as attendees with their email addresses - but don't send "
                "invitations, you prefer to confirm things yourself.\n"
                "6. When someone doesn't get their first choice, reply to their email telling them the day and time "
                "you booked, and leave it in Drafts for you to check.\n"
                "7. Site inspections: block the whole trip, from leaving the studio to getting back, as one entry.\n\n"
                "Good luck - see you in the spring!\nRuth\n\n--\nRuth Collins | Studio Manager | Varga & Hale Architects",
                unread=False)
    ids = {}
    ids["harlow"] = [add("harlow", "Emma Harlow <emma@harlowfinch.co.uk>", "Kitchen extension - design sign-off meeting",
                         at(11, 16, 9, 12),
                         "Dear Ines,\n\nDaniel and I have been through the revised kitchen extension drawings and we're "
                         "nearly ready to sign them off. Could we come in to go through the last points with you on "
                         "Tuesday 24 November, 10:30-11:30, at your studio (meeting room)? If that doesn't suit, Monday "
                         "23 November 15:30-16:30 would work for us too.\n\nDaniel's email is daniel@harlowfinch.co.uk.\n\n"
                         "Best wishes,\nEmma Harlow\nHarlow & Finch", cc="Daniel Finch <daniel@harlowfinch.co.uk>")]
    ids["brightwell"] = [add("brightwell", "Sean Brightwell <sean@brightwellbuild.co.uk>",
                             "Linden Court refurbishment - programme review", at(11, 16, 14, 5),
                             "Hi Ines,\n\nwe need to review the programme for the Linden Court refurbishment now that the "
                             "windows are delayed. Can you meet me and our site manager Priya Nair "
                             "(priya.nair@brightwellbuild.co.uk) on site, in the site cabin at Linden Court, 22 Linden "
                             "Road, on Wednesday 25 November from 14:00 to 15:00? Second option: Friday 27 November "
                             "10:00-11:00, same place.\n\nCheers,\nSean\n\nSean Brightwell | Contracts Director | "
                             "Brightwell Build Ltd | 07700 900412")]
    ids["moor"] = [add("moor", "Hannah Moor <hannah@moorplanning.co.uk>", "Pre-app strategy - Ashby Road",
                       at(11, 17, 8, 50),
                       "Dear Ines,\n\nahead of the pre-application meeting with the council I'd like an hour with you "
                       "to agree the strategy. I'm working from home next week, so Teams would be best: Tuesday 24 "
                       f"November 16:00-17:00. Link: {TEAMS}\nIf that's no good, Friday 27 November 14:00-15:00 on "
                       "the same link.\n\nKind regards,\nHannah Moor MRTPI\nMoor Planning Consultancy")]
    ids["halden"] = [add("halden", "Tom Halden <tom.halden@halden-eng.co.uk>", "Ashby Road - loft beam calcs",
                         at(11, 17, 18, 31),
                         "Ines,\n\nI'd like a quick call to go through the loft beam calcs for Ashby Road before I issue "
                         "them. I scribbled my availability on the train - photo attached. A phone call is fine, I'll "
                         "ring you.\n\nTom\n\nTom Halden CEng MIStructE | Halden Associates",
                         atts=[("availability.jpg", note_png(), "image/jpeg")])]
    ids["okonjo"] = [add("okonjo", "Grace Okonjo <grace.okonjo@gmail.com>", "Garden studio - first meeting",
                         at(11, 18, 20, 14),
                         "Hello Ms Varga,\n\nyou were recommended to us by the Kerr family. We'd love to talk to you "
                         "about a garden studio for our house in Redland. Could we come to your studio on Monday 23 "
                         "November at 2pm for an hour? Otherwise Friday 27 November 11:30-12:30 also works.\n\n"
                         "Many thanks,\nGrace Okonjo")]
    rid1 = add("ridgeway", "Lisa Marsh <l.marsh@ridgewayha.org.uk>", "Mill Lane infill - feasibility discussion",
               at(11, 16, 11, 0),
               "Dear Ines,\n\nthank you for the feasibility sketches for the Mill Lane infill site. My colleague Omar "
               "Siddiqui (omar.siddiqui@ridgewayha.org.uk) and I would like to discuss them with you at our offices "
               "(Ridgeway HA, 5 Mill Lane, BS3) on Monday 23 November, 11:00-12:00. Alternatively Friday 27 November "
               "15:00-16:00.\n\nBest regards,\nLisa Marsh\nDevelopment Manager, Ridgeway Housing Association",
               cc="Omar Siddiqui <omar.siddiqui@ridgewayha.org.uk>")
    rid2 = add("ridgeway2", "Lisa Marsh <l.marsh@ridgewayha.org.uk>", "Re: Mill Lane infill - feasibility discussion",
               at(11, 19, 9, 40),
               "Dear Ines,\n\napologies - Omar can't do Monday after all. Could we make it Friday 27 November, 15:00-16:00, "
               "at our offices instead? If Friday is impossible for you, the original Monday slot (11:00-12:00) would "
               "be our fallback.\n\nBest regards,\nLisa", cc="Omar Siddiqui <omar.siddiqui@ridgewayha.org.uk>",
               irt=mid("ridgeway", "ridgewayha.org.uk"))
    ids["ridgeway"] = [rid1, rid2]

    sched = f"{d}/Inspection_appointments_wc23Nov.pdf"
    schedule_pdf(sched)
    bc = add("bc", "Building Control <building.control@bristol.gov.uk>",
             "Site inspection appointments w/c 23 November - Varga & Hale", at(11, 17, 12, 2),
             "Dear Ms Varga,\n\nplease find attached the confirmed site inspection appointments for the week commencing "
             "23 November 2026. Where the schedule says the architect must attend, please make sure you are on site at "
             "the time shown.\n\nBristol City Council - Building Control\n\n(This is a scanned copy of the signed "
             "schedule.)", atts=[("Inspection_appointments_wc23Nov.pdf", open(sched, "rb").read(), "application/pdf")])
    os.remove(sched)
    marco = add("marco", "Marco Bellini <marco.bellini@vargahale.co.uk>", "Design reviews + site visits next week",
                at(11, 18, 17, 25),
                "Hi Ines,\n\ntwo things for next week.\n\n1) Travel times from the studio for the inspections "
                "(by car, each way, with parking):\n   - 14 Wharf Street: 30 min\n   - Linden Court: 25 min\n"
                "   - Elm Grove Primary School: 45 min\n   - 3 Castle Mews: 20 min\n\n"
                "2) We need three internal design reviews with you, one hour each, in this order:\n"
                "   1. Wharf Street - stage 4 package\n   2. Elm Grove School - drainage redesign\n"
                "   3. Castle Mews - roof options\nThe team can do any time Tuesday to Thursday between 10:00 and "
                "17:00, starting on the hour or half hour - the earlier the better, we're waiting on these. Please "
                "call them 'Design review - <project>' so they're easy to spot, and let the whole team "
                f"({TEAM}) know the times.\n\nThanks!\nMarco\n\nMarco Bellini | Associate | Varga & Hale Architects",
                cc=f"Studio team <{TEAM}>", unread=True)
    add("riba", "RIBA Journal <newsletter@ribaj.com>", "This week: retrofit special", at(11, 18, 7, 0),
        "Retrofit first: twelve projects that prove it.\n\nUnsubscribe", unread=False)
    add("print", "Clifton Reprographics <accounts@cliftonrepro.co.uk>", "Invoice CR-20981", at(11, 16, 10, 0),
        "Please find our invoice for A1 plots (Fenwick residence) on your account. Payment terms 30 days.", unread=False)
    add("kerr", "Alan Kerr <alan.kerr@btinternet.com>", "Ashby Road - neighbours' comments", at(11, 19, 21, 4),
        "Ines, the neighbours have commented on the planning portal - nothing serious I think. Speak Monday. Alan",
        unread=True)
    add("it", "Studio IT <it@vargahale.co.uk>", "Server maintenance Saturday", at(11, 19, 15, 0),
        "The file server will be offline on Saturday 28 Nov from 8:00 to 12:00.", unread=False)
    mails.sort(key=lambda x: x[1])

    cal, seed_ids = seeded_calendar()
    build_profile(f"{d}/thunderbird-profile.tar.gz", ME, {"Inbox": mails}, tz=TZ,
                  extra_files={"calendar-data/local.sqlite": cal})
    dump_expected(d, {
        "tz": TZ, "me": ME[1], "team": TEAM, "seed": seed_ids, "teams_link": TEAMS,
        "week": ["2026-11-23", "2026-11-27"],
        "requests": [dict(r, ids=ids[r["key"]]) for r in REQUESTS],
        "inspections": INSPECTIONS, "reviews": REVIEWS, "review_window": REVIEW_WINDOW,
        "msg": {"rules": rules, "bc": bc, "marco": marco},
    })
