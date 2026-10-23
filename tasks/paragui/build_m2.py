"""m2 - one Thunderbird: booking meeting requests into the calendar vs cleaning up the address book.

Persona: Dr. Amara Okafor, Director of Clinical Programs at Harbor Point Community Health (Boston). Her chief of
staff Grace Liu is on leave and left two handover e-mails.
Task A (pgm2calendar): six meeting requests for the week of 16 Nov 2026 -> events in the Home calendar (time, location,
                       attendees) following Grace's scheduling rules (priority conflict, blocked Wednesday morning,
                       a time change, a poll result that exists only as a screenshot); reply drafts for moved meetings.
Task B (pgm2contacts): merge three duplicate contacts, delete a leaver, add four contacts from e-mail signatures and a
                       scanned business card, create a mailing list, export the address book as CSV.
Both work in the same Thunderbird window (Calendar tab vs Address Book tab) and read the same e-mails; the attendee
addresses A types are auto-completed from the address book B is rewriting (the duplicates hold stale addresses).
"""
from __future__ import annotations

import datetime as dt
import os

from PIL import Image, ImageDraw

from lib_mmail import build_profile, dump_expected, font, make_abook, msg, png_bytes

ME = ("Amara Okafor", "amara.okafor@harborpointhealth.org")
HOST = "pop.harborpointhealth.org"
EDT = dt.timezone(dt.timedelta(hours=-4))
EST = dt.timezone(dt.timedelta(hours=-5))
AMARA = f"Dr. {ME[0]} <{ME[1]}>"
D = "harborpointhealth.org"


def at(month, day, hh, mm=0):
    return dt.datetime(2026, month, day, hh, mm, tzinfo=EDT if (month, day) < (11, 1) else EST)


def mid(tag, dom=D):
    return f"<pgm2.{tag}@{dom}>"


SIG = {
    "margaret": "Margaret Doyle\nChair, Board of Directors - Harbor Point Community Health\nPartner, Doyle & Partners LLP\n"
                "T (617) 555-0119 | margaret.doyle@doylepartners.com",
    "paul": "Paul Mercer\nGrants Manager | Lindqvist Foundation\n200 Clarendon Street, Boston MA 02116\n"
            "Tel. (617) 555-0158\npaul.mercer@lindqvistfdn.org",
    "priya": "Priya Shah\nData Analyst, Clinical Programs\nHarbor Point Community Health\nDirect: (617) 555-0171",
}
CARD = dict(first="Helen", last="Park", email="helen.park@northshorefamily.org", org="Northshore Family Clinics",
            title="Medical Director", phone="(978) 555-0162")


def poll_png():
    im = Image.new("RGB", (1180, 560), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1180, 70), fill=(36, 99, 235))
    d.text((24, 18), "MeetPoll  -  Volunteer appreciation planning  (poll closed)", fill="white", font=font(26, True))
    slots = ["Mon 16 Nov\n3:00-3:45 pm", "Tue 17 Nov\n4:00-4:45 pm", "Thu 19 Nov\n11:30-12:15", "Fri 20 Nov\n9:00-9:45 am"]
    people = ["Kayla Brooks", "Marcus Lee", "Ana Souza", "Devon Price", "Lily Chen", "Omar Haddad", "Ruth Adler"]
    votes = [[1, 1, 1, 0], [1, 0, 1, 1], [1, 1, 0, 0], [1, 0, 1, 1], [0, 1, 1, 0], [1, 1, 0, 0], [1, 0, 1, 1]]
    x0, w, y0, h = 230, 230, 110, 46
    for j, s in enumerate(slots):
        d.multiline_text((x0 + j * w + 20, y0 - 30), s, fill=(30, 30, 30), font=font(19, True), spacing=2)
    y = y0 + 30
    for i, p in enumerate(people):
        d.text((24, y + 10), p, fill=(40, 40, 40), font=font(19))
        for j in range(4):
            box = (x0 + j * w + 10, y + 4, x0 + (j + 1) * w - 10, y + h - 4)
            d.rectangle(box, fill=(209, 250, 229) if votes[i][j] else (243, 244, 246))
            d.text((box[0] + 90, box[1] + 6), "yes" if votes[i][j] else "-", fill=(20, 90, 50) if votes[i][j] else (150, 150, 150),
                   font=font(19))
        y += h
    totals = [sum(v[j] for v in votes) for j in range(4)]
    d.text((24, y + 14), "Total", fill="black", font=font(20, True))
    best = totals.index(max(totals))
    for j, t in enumerate(totals):
        d.text((x0 + j * w + 80, y + 14), f"{t}" + ("  BEST" if j == best else ""), fill=(200, 30, 30) if j == best else "black",
               font=font(20, True))
    assert best == 0 and totals == [6, 4, 5, 3], totals
    return png_bytes(im)


def card_jpg():
    im = Image.new("RGB", (1050, 600), (250, 248, 242))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 28, 600), fill=(15, 118, 110))
    d.text((80, 70), "NORTHSHORE", fill=(15, 118, 110), font=font(40, True))
    d.text((80, 118), "FAMILY CLINICS", fill=(15, 118, 110), font=font(26))
    d.text((80, 250), "Helen Park, MD, MPH", fill=(20, 20, 20), font=font(44, True))
    d.text((80, 310), "Medical Director", fill=(60, 60, 60), font=font(30))
    d.text((80, 420), "helen.park@northshorefamily.org", fill=(20, 20, 20), font=font(28))
    d.text((80, 462), "Office (978) 555-0162", fill=(20, 20, 20), font=font(28))
    d.text((80, 504), "41 Cabot Street, Beverly MA 01915", fill=(90, 90, 90), font=font(24))
    im = im.rotate(-2.0, resample=Image.BICUBIC, expand=True, fillcolor=(120, 112, 100))
    return png_bytes(im, "JPEG")


# address book before clean-up: three people have two cards, Tom Becker has left
CARDS = [
    dict(first="Jamal", last="Whitaker", email="jamal.whitaker@harborpointhealth.org", org="Harbor Point Community Health",
         title="CHW Program Manager", phone="(617) 555-0131"),
    dict(first="Jamal", last="W.", display="Jamal W.", email="jwhitaker84@gmail.com"),
    dict(first="Ingrid", last="Lindqvist", email="i.lindqvist@lindqvist-foundation.org", org="Lindqvist Foundation",
         title="Program Officer"),
    dict(first="Ingrid", last="Lindqvist", display="Ingrid Lindqvist (Foundation)", email="ingrid.lindqvist@lindqvistfdn.org"),
    dict(first="Luis", last="Ferreira", display="Dr. Luis Ferreira", email="luis.ferreira@bphc-boston.org",
         org="Boston Public Health Commission", title="Deputy Commissioner"),
    dict(first="Luis", last="Ferreira", email="lferreira@boston-health.gov"),
    dict(first="Nadia", last="Haddad", email="nadia.haddad@harborpointhealth.org", org="Harbor Point Community Health",
         title="Mobile Clinic Lead", phone="(617) 555-0134"),
    dict(first="Rosa", last="Delgado", email="rosa.delgado@harborpointhealth.org", org="Harbor Point Community Health",
         title="Community Outreach Manager"),
    dict(first="Samuel", last="Osei", email="samuel.osei@harborpointhealth.org", org="Harbor Point Community Health",
         title="Director of Operations"),
    dict(first="Grace", last="Liu", email="grace.liu@harborpointhealth.org", org="Harbor Point Community Health",
         title="Chief of Staff"),
    dict(first="Tom", last="Becker", email="tom.becker@harborpointhealth.org", org="Harbor Point Community Health",
         title="Quality Improvement Analyst"),
    dict(first="Kayla", last="Brooks", email="kayla.brooks@harborpointhealth.org", org="Harbor Point Community Health",
         title="Volunteer Coordinator"),
    dict(first="Mei", last="Chen", email="mei.chen@harborpointhealth.org", org="Harbor Point Community Health",
         title="HR Business Partner"),
    dict(first="Maria", last="Santos", email="msantos@massleague.org", org="Mass League of Community Health Centers"),
    dict(first="Kevin", last="O'Brien", email="kobrien@bcbsfoundation.org", org="Blue Cross Foundation"),
    dict(first="Aisha", last="Rahman", email="aisha.rahman@childrens.harvard.edu", org="Boston Children's Hospital"),
    dict(first="Ethan", last="Wright", email="orders@wrightcatering.com", org="Wright Catering"),
    dict(first="Fatima", last="Noor", email="fatima.noor@langbridge.org", org="Langbridge Interpreters"),
    dict(first="Robert", last="Tan", email="robert.tan@tanadvisory.com", org="Tan Advisory LLC",
         title="Treasurer, Board of Directors"),
]
MERGES = [  # (primary = address they currently e-mail from, secondary)
    ("Jamal Whitaker", "jamal.whitaker@harborpointhealth.org", "jwhitaker84@gmail.com"),
    ("Ingrid Lindqvist", "ingrid.lindqvist@lindqvistfdn.org", "i.lindqvist@lindqvist-foundation.org"),
    ("Luis Ferreira", "lferreira@boston-health.gov", "luis.ferreira@bphc-boston.org"),
]
NEW = [
    dict(first="Margaret", last="Doyle", email="margaret.doyle@doylepartners.com", org="Doyle & Partners LLP",
         org_alt=["Harbor Point"], title="Chair, Board of Directors", title_alt=["Chair", "Partner"],
         phone="(617) 555-0119"),
    dict(first="Paul", last="Mercer", email="paul.mercer@lindqvistfdn.org", org="Lindqvist Foundation",
         title="Grants Manager", phone="(617) 555-0158"),
    dict(CARD),
    dict(first="Priya", last="Shah", email="priya.shah@harborpointhealth.org", org="Harbor Point Community Health",
         title="Data Analyst", phone="(617) 555-0171"),
]
LIST = dict(name="Program Leads", members=["nadia.haddad@harborpointhealth.org", "jamal.whitaker@harborpointhealth.org",
                                           "rosa.delgado@harborpointhealth.org", "kayla.brooks@harborpointhealth.org",
                                           "priya.shah@harborpointhealth.org"])
LEAVER = "tom.becker@harborpointhealth.org"

ZOOM = "https://zoom.us/j/84011277305"
EVENTS = [  # what the calendar must contain afterwards (local Boston time)
    dict(key="finance", words=["finance"], start="2026-11-17 10:00", end="2026-11-17 11:00", loc=["3b"],
         attendees=["margaret.doyle@doylepartners.com", "robert.tan@tanadvisory.com"]),
    dict(key="jamal", words=["jamal", "whitaker", "staffing", "chw"], start="2026-11-19 14:00",
         end="2026-11-19 14:30", loc=["office"], attendees=["jamal.whitaker@harborpointhealth.org"]),
    dict(key="debrief", words=["debrief", "lindqvist", "sitevisit"], start="2026-11-18 14:00", end="2026-11-18 15:30",
         loc=["zoom"], attendees=["ingrid.lindqvist@lindqvistfdn.org", "paul.mercer@lindqvistfdn.org"]),
    dict(key="mou", words=["mou", "mobileclinic"], start="2026-11-20 11:00", end="2026-11-20 12:00", loc=["210"],
         attendees=["lferreira@boston-health.gov", "nadia.haddad@harborpointhealth.org"]),
    dict(key="review", words=["programreview", "quarterly"], start="2026-11-19 09:30", end="2026-11-19 11:00",
         loc=["harbor"], attendees=["samuel.osei@harborpointhealth.org", "nadia.haddad@harborpointhealth.org",
                                    "jamal.whitaker@harborpointhealth.org", "rosa.delgado@harborpointhealth.org"]),
    dict(key="volunteer", words=["volunteer", "appreciation"], start="2026-11-16 15:00", end="2026-11-16 15:45",
         loc=["2.14", "214"], attendees=["kayla.brooks@harborpointhealth.org"]),
]


def build(d):
    os.makedirs(d, exist_ok=True)
    mails = []

    def add(key, frm, subject, when, body, unread=True, atts=(), cc=None, to=AMARA, irt=None):
        dom = frm.split("@")[1].rstrip(">")
        m = msg(frm, to, subject, when, mid(key, dom), body=body, attachments=atts, cc=cc, irt=irt)
        mails.append((m, when, unread))
        return m["Message-ID"]

    grace = "Grace Liu <grace.liu@harborpointhealth.org>"
    rules = add("rules", grace, "How I handle your calendar (handover)", at(10, 30, 17, 5),
                "Hi Amara,\n\nas promised, here is how I have been running your calendar, so whoever covers for me "
                "while I'm on leave can do the same:\n\n"
                "1. Meetings only Monday-Friday between 9:00 and 17:00.\n"
                "2. Wednesday mornings (until 12:00) are your clinic rounds - never book anything there.\n"
                "3. If two requests overlap, priority goes: (1) Board, (2) funders and government partners, "
                "(3) internal staff. The lower-priority meeting goes to the alternative slot the person offered "
                "(people always give a second option when they ask).\n"
                "4. If a request does not say how long, it is 30 minutes.\n"
                "5. Everything goes into your Home calendar in Thunderbird. Put the room or the video link in the "
                "Location field, and add everyone named in the request as attendees.\n"
                "6. When someone does not get their first-choice slot, reply to their request and tell them the time "
                "you booked.\n7. If someone changes a request later, the latest e-mail wins.\n\n"
                "Thanks and see you in January!\nGrace\n\n--\nGrace Liu | Chief of Staff | Harbor Point Community Health",
                unread=False)
    todo = add("todo", grace, "Address book clean-up", at(10, 30, 17, 20),
               "Amara,\n\none more thing I never got to - your address book in Thunderbird is a mess:\n\n"
               "- Some people are in there twice (old and new addresses, a private address...). They should be one "
               "card per person.\n"
               "- Tom Becker left us in September; his card can go.\n"
               "- Please add the people you have been corresponding with lately who are not in there yet: Margaret "
               "Doyle (our new board chair), Paul Mercer from the Lindqvist Foundation, Dr. Helen Park from Northshore "
               "(she sent you her card after the APHA conference) and our new data analyst Priya Shah. Their e-mail "
               "signatures have all the details.\n"
               "- A mailing list \"Program Leads\" would save you a lot of typing: Nadia, Jamal, Rosa, Kayla and Priya.\n\n"
               "Grace", unread=False)
    fin = add("finance", "Margaret Doyle <margaret.doyle@doylepartners.com>",
              "Finance committee pre-read - Tue 17 Nov", at(11, 4, 9, 12),
              "Dear Amara,\n\nbefore the December board meeting, Robert and I would like to go through the FY27 budget "
              "pre-read with you. Could we meet on Tuesday 17 November, 10:00-11:00, in Boardroom 3B? Robert Tan "
              "(robert.tan@tanadvisory.com) will join us.\nIf that really does not work, Thursday 19 November at 16:00 "
              "is our fallback.\n\nBest regards,\n\n" + SIG["margaret"], cc="Robert Tan <robert.tan@tanadvisory.com>")
    jam = add("jamal", "Jamal Whitaker <jamal.whitaker@harborpointhealth.org>", "1:1 - CHW staffing for Q1",
              at(11, 5, 14, 40),
              "Hi Amara,\n\ncould we have a 1:1 about community health worker staffing for Q1? I'd suggest Tuesday "
              "17 November at 10:30 in your office. If that's taken, Thursday 19 November at 14:00 works too.\n\n"
              "Thanks,\nJamal\n\nJamal Whitaker | CHW Program Manager | Harbor Point Community Health | (617) 555-0131")
    deb1 = add("debrief", "Ingrid Lindqvist <ingrid.lindqvist@lindqvistfdn.org>", "Site visit debrief",
               at(11, 5, 10, 3),
               "Dear Amara,\n\nthank you again for hosting us last week. We would like to debrief the site visit with "
               f"you on Wednesday 18 November, 13:00-14:30, on Zoom ({ZOOM}). My colleague Paul Mercer "
               "(paul.mercer@lindqvistfdn.org) will join as well. Alternatively Friday 20 November at 14:00.\n\n"
               "Warm regards,\nIngrid Lindqvist\nProgram Officer, Lindqvist Foundation", cc="Paul Mercer <paul.mercer@lindqvistfdn.org>")
    deb2 = add("debrief2", "Ingrid Lindqvist <ingrid.lindqvist@lindqvistfdn.org>", "Re: Site visit debrief",
               at(11, 9, 8, 47),
               "Dear Amara,\n\nsmall change on our side: could we push the debrief on Wednesday 18 November by one hour, "
               f"i.e. 14:00-15:30? Same Zoom link ({ZOOM}).\n\nThank you!\nIngrid",
               cc="Paul Mercer <paul.mercer@lindqvistfdn.org>", irt=mid("debrief", "lindqvistfdn.org"))
    add("paul", "Paul Mercer <paul.mercer@lindqvistfdn.org>", "Documents for the site visit debrief", at(11, 9, 11, 30),
        "Dear Dr. Okafor,\n\nahead of our debrief I am sending the foundation's site visit notes (two pages, see our "
        "grantee portal). Please let me know if anything is unclear.\n\nKind regards,\n\n" + SIG["paul"])
    mou = add("mou", "Dr. Luis Ferreira <lferreira@boston-health.gov>", "Mobile clinic MOU review", at(11, 6, 16, 20),
              "Dear Dr. Okafor,\n\nour legal team has finished its comments on the mobile clinic MOU. I would like to go "
              "through them with you and Nadia Haddad (nadia.haddad@harborpointhealth.org) on Wednesday 18 November, "
              "10:00-11:00, in City Hall, Room 210. Our alternative would be Friday 20 November, 11:00-12:00, same room.\n\n"
              "Best,\nLuis Ferreira, MD\nDeputy Commissioner, Boston Public Health Commission\n(617) 555-0190")
    rev = add("review", "Samuel Osei <samuel.osei@harborpointhealth.org>", "Quarterly program review",
              at(11, 2, 9, 0),
              "Amara,\n\nlet's do the quarterly program review on Thursday 19 November, 9:30-11:00 in the Harbor Room. "
              "Attendees: Nadia Haddad, Jamal Whitaker, Rosa Delgado and me. (Backup: Monday 16 November, 13:00.)\n\n"
              "Samuel\n\nSamuel Osei | Director of Operations")
    vol = add("volunteer", "Kayla Brooks <kayla.brooks@harborpointhealth.org>",
              "Volunteer appreciation planning - poll results", at(11, 9, 15, 10),
              "Hi Amara,\n\nthe poll for our volunteer appreciation planning meeting has closed - screenshot attached. "
              "Could you book us for the slot with the most votes? It's 45 minutes, in Room 2.14. Just the two of us.\n"
              "(If that slot doesn't work, the runner-up is fine.)\n\nThanks!\nKayla\n\nKayla Brooks | Volunteer Coordinator",
              atts=[("poll_results.png", poll_png(), "image/png")])
    add("helen", "Helen Park <hpark.md@gmail.com>", "Great meeting you at APHA", at(11, 3, 21, 5),
        "Hi Amara,\n\nit was great to meet you at the APHA conference. As promised, my card is attached - let's talk "
        "about the shared CHW training idea in the new year.\n\nHelen\n\nSent from my phone",
        atts=[("Helen_Park_card.jpg", card_jpg(), "image/jpeg")])
    add("priya", "Priya Shah <priya.shah@harborpointhealth.org>", "Hello from your new data analyst", at(11, 2, 10, 15),
        "Dear Amara,\n\nI started on Monday and wanted to introduce myself - I'll be supporting the clinical programs "
        "team with dashboards and the UDS reporting. Looking forward to working with you!\n\nBest,\n\n" + SIG["priya"])
    add("nadia", "Nadia Haddad <nadia.haddad@harborpointhealth.org>", "Mobile clinic December schedule",
        at(11, 4, 13, 0), "Amara, the December route schedule is on the shared drive. Two new stops in Dorchester.\n\nNadia",
        unread=False)
    add("rosa", "Rosa Delgado <rosa.delgado@harborpointhealth.org>", "Health fair volunteers", at(11, 6, 9, 30),
        "Hi Amara, we have 14 volunteers confirmed for the health fair. Kayla is coordinating shifts.\n\nRosa", unread=False)
    add("minutes", "Board Secretary <board@harborpointhealth.org>", "Board meeting minutes - October", at(11, 2, 12, 0),
        "Attached to the board portal: minutes of the October board meeting. No action needed.", unread=False)
    add("apha", "APHA <news@apha.org>", "Thank you for attending APHA 2026", at(11, 1, 7, 0),
        "Session recordings are now available to registered attendees.\n\nUnsubscribe", unread=False)
    add("it", "HPCH IT <it@harborpointhealth.org>", "Password expiry reminder", at(11, 7, 8, 0),
        "Your network password expires in 7 days.", unread=True)
    add("bcbs", "Kevin O'Brien <kobrien@bcbsfoundation.org>", "Coffee in December?", at(11, 8, 18, 22),
        "Amara - would love to catch up in December, no rush. Kevin", unread=True)
    mails.sort(key=lambda x: x[1])

    abook, _ = make_abook(CARDS, seed=2)
    build_profile(f"{d}/thunderbird-profile.tar.gz", ME, {"Inbox": mails}, tz="America/New_York",
                  extra_files={"abook.sqlite": abook})
    dump_expected(d, {
        "host": HOST, "me": ME[1], "tz": "America/New_York", "events": EVENTS, "zoom": ZOOM,
        "allowed_attendees": sorted({a for e in EVENTS for a in e["attendees"]} | {ME[1]}),
        "replies": {"jamal": {"ids": [jam], "to": "jamal.whitaker@harborpointhealth.org", "day": ["thu", "19"],
                              "time": ["14:00", "2 pm", "2pm", "2:00", "14.00", "14h"]},
                    "mou": {"ids": [mou], "to": "lferreira@boston-health.gov", "day": ["fri", "20"],
                            "time": ["11:00", "11 am", "11am", "11.00", "11h"]}},
        "no_reply_needed": [fin, deb1, deb2, rev, vol], "rules_id": rules, "todo_id": todo,
        "cards_before": CARDS, "merges": MERGES, "new": NEW, "list": LIST, "leaver": LEAVER,
    })
