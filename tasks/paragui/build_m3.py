"""m3 - one Thunderbird: building a trip itinerary + calendar entries vs reorganising the inbox.

Persona: Lukas Brandt, senior consultant at Aldervane Consulting (Munich).
Task A (pgm3trip): booking confirmations (two image-only PDFs, one schedule change) -> PDFs saved, an itinerary .docx,
                   calendar events for three journeys + the conference, a reply draft with the trip's total cost.
Task B (pgm3inbox): project + Travel folders, move mail, archive everything older than 1 Oct 2026, star the messages
                    with a deadline, a saved search "Follow-up", and a follow-up list file.
B moves exactly the booking mails A is working through (and the client mail with the workshop times) while A reads.
"""
from __future__ import annotations

import datetime as dt
import os

from lib_mmail import DocPage, build_profile, dump_expected, md5, msg, pdf_scan, scan_look

ME = ("Lukas Brandt", "lukas.brandt@aldervane.de")
HOST = "pop.aldervane.de"
LUKAS = f"{ME[0]} <{ME[1]}>"


def at(y, mo, d, hh, mm=0):
    off = 2 if (mo, d) >= (3, 29) and (mo, d) < (10, 25) else 1  # CEST / CET
    return dt.datetime(y, mo, d, hh, mm, tzinfo=dt.timezone(dt.timedelta(hours=off)))


def mid(tag, dom):
    return f"<pgm3.{tag}@{dom}>"


# ---------------------------------------------------------------- booking documents
def db_ticket(path):
    page = DocPage("DB  Online-Ticket", "Deutsche Bahn Fernverkehr AG - booking channel bahn.de", "e-Ticket / Online-Ticket",
                   meta=[("Order (Auftrag):", "7KQ4MZ"), ("Traveller:", "Lukas Brandt"), ("Class:", "2nd class, Flexpreis"),
                         ("Date of travel:", "Wednesday, 09.12.2026"), ("Price:", "EUR 89.90 (paid, company card)")],
                   table=(["Station", "Date", "Time", "Train", "Coach/Seat"],
                          [("Muenchen Hbf  dep.", "09.12.", "08:24", "RJX 63", "25 / 61"),
                           ("Wien Hbf  arr.", "09.12.", "12:30", "", "")]), widths=[180, 80, 80, 90, 82],
                   notes=["Valid only with photo ID. Seat reservation included.",
                          "Ticket is personal and not transferable. Show this ticket on your phone or printed."],
                   footer="DB Fernverkehr AG - this is not a VAT invoice")
    pdf_scan(path, [scan_look(page.image(), seed=301, angle=-0.5)])


def os_itinerary(path):
    DocPage("AUSTRIAN AIRLINES", "Office Park 2, 1300 Vienna Airport, Austria", "Itinerary / Receipt",
            meta=[("Booking reference:", "QX4T7B"), ("Passenger:", "BRANDT/LUKAS MR"), ("Ticket number:", "257-2419983107"),
                  ("Fare paid:", "EUR 212.40 (incl. taxes and fees)")],
            table=(["Flight", "Date", "From", "Dep.", "To", "Arr."],
                   [("OS 305", "10 DEC 2026", "Vienna VIE", "17:05", "Copenhagen CPH", "18:55")]),
            widths=[70, 90, 110, 60, 122, 60],
            notes=["Economy Classic, 1 checked bag 23 kg. Check-in closes 40 minutes before departure.",
                   "Times are local times."]).pdf_text(path)


def nyhavn(path):
    page = DocPage("NYHAVN HARBOUR HOTEL", "Nyhavn 51, 1051 Copenhagen K, Denmark", "Booking confirmation",
                   meta=[("Confirmation no.:", "NHH-20931"), ("Guest:", "Mr Lukas Brandt"),
                         ("Arrival:", "Thursday 10 December 2026 (check-in from 15:00)"),
                         ("Departure:", "Saturday 12 December 2026 (check-out by 11:00)"),
                         ("Room:", "Harbour View Single, 2 nights, breakfast included")],
                   totals=[("Room 2 nights", "EUR 380.00"), ("City tax", "EUR 18.00"), ("TOTAL charged", "EUR 398.00")],
                   notes=["Charged to the card on file on 14 October 2026. Free cancellation until 8 December."])
    pdf_scan(path, [scan_look(page.image(), seed=303, stamp="CONFIRMED")])


TRIP = {
    "train": dict(ref="7KQ4MZ", start="2026-12-09 08:24", end="2026-12-09 12:30", cost=89.90),
    "hotel_vie": dict(ref="LGW-48213", cost=164.00),
    "flight1": dict(ref="QX4T7B", start="2026-12-10 17:35", end="2026-12-10 19:25", old_start="17:05", cost=212.40),
    "hotel_cph": dict(ref="NHH-20931", cost=398.00),
    "flight2": dict(ref="8ZPLMK", start="2026-12-12 19:40", end="2026-12-12 21:35", cost=176.30),
}
TOTAL = round(sum(v["cost"] for v in TRIP.values()), 2)
EXTRA_TOKENS = {"desk": ["traveldesk", "preapproval", "nina"], "dw5": ["agenda"], "he1": ["tariff"],
                "ma1": ["cr14", "changerequest"], "hr": ["vacation", "holiday"]}


def norm(s):
    import re
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build(d):
    att = f"{d}/attachments"
    os.makedirs(att, exist_ok=True)
    db_ticket(f"{att}/DB_eTicket_7KQ4MZ.pdf")
    os_itinerary(f"{att}/Austrian_Itinerary_QX4T7B.pdf")
    nyhavn(f"{att}/Nyhavn_Confirmation_NHH-20931.pdf")

    def rd(n):
        return open(f"{att}/{n}", "rb").read()

    mails, info = [], []

    def add(key, frm, subject, when, body=None, html=None, folder="Inbox", flag=None, unread=True, atts=(), cc=None):
        dom = frm.split("@")[1].rstrip(">")
        m = msg(frm, LUKAS, subject, when, mid(key, dom), body=body, html=html, attachments=atts, cc=cc)
        mails.append((m, when, unread))
        info.append({"key": key, "id": m["Message-ID"], "subject": subject, "from": frm, "date": when.isoformat(),
                     "folder": folder, "flag": flag})
        return m["Message-ID"]

    T, DW, HE, MA = "Travel", "Projects/Donauwerke", "Projects/Helios", "Projects/Marlow"
    ARCH, INBOX = "Archives", "Inbox"
    # ---- travel (task A's sources)
    add("db", "DB Fernverkehr <buchungsbestaetigung@bahn.de>", "Your booking confirmation - order 7KQ4MZ",
        at(2026, 10, 14, 9, 12),
        "Dear Mr Brandt,\n\nthank you for your booking. Your Online-Ticket for Munich - Vienna on 9 December 2026 is "
        "attached as a PDF.\n\nDeutsche Bahn", folder=T, atts=[("DB_eTicket_7KQ4MZ.pdf", rd("DB_eTicket_7KQ4MZ.pdf"), "application/pdf")])
    add("lgw", "Hotel Lindengarten Wien <reservations@lindengarten-wien.at>", "Reservation confirmed - LGW-48213",
        at(2026, 10, 14, 9, 40), html=(
            "<p>Dear Mr Brandt,</p><p>we are pleased to confirm your reservation:</p><table border='1' cellpadding='4'>"
            "<tr><td>Confirmation</td><td><b>LGW-48213</b></td></tr><tr><td>Check-in</td><td>Wednesday, 9 December 2026 "
            "(from 14:00)</td></tr><tr><td>Check-out</td><td>Thursday, 10 December 2026 (until 11:00)</td></tr>"
            "<tr><td>Room</td><td>Classic single, 1 night, breakfast</td></tr><tr><td>Total</td><td>EUR 164.00 incl. city "
            "tax</td></tr></table><p>Hotel Lindengarten, Lindengasse 12, 1070 Wien</p>"), folder=T)
    add("os", "Austrian Airlines <noreply@austrian.com>", "Your booking QX4T7B - Vienna to Copenhagen",
        at(2026, 10, 14, 10, 5), "Thank you for booking with Austrian Airlines. Your itinerary and receipt are attached.",
        folder=T, atts=[("Austrian_Itinerary_QX4T7B.pdf", rd("Austrian_Itinerary_QX4T7B.pdf"), "application/pdf")])
    add("nhh", "Nyhavn Harbour Hotel <booking@nyhavnharbour.dk>", "Booking confirmation NHH-20931", at(2026, 10, 14, 10, 30),
        "Dear Mr Brandt,\n\nplease find your booking confirmation attached. We look forward to welcoming you.\n\n"
        "Nyhavn Harbour Hotel", folder=T,
        atts=[("Nyhavn_Confirmation_NHH-20931.pdf", rd("Nyhavn_Confirmation_NHH-20931.pdf"), "application/pdf")])
    add("sas", "SAS <no-reply@flysas.com>", "Your SAS e-ticket - booking reference 8ZPLMK", at(2026, 10, 14, 11, 2),
        "Booking reference: 8ZPLMK\nPassenger: Lukas Brandt\n\nSK 1637  Sat 12 Dec 2026  Copenhagen (CPH) 19:40 -> "
        "Munich (MUC) 21:35\nSAS Go Light\n\nTotal price: EUR 176.30\n\nAll times are local.", folder=T)
    add("summit", "NordData Summit <registration@norddata.dk>", "Registration confirmed - NordData Summit 2026",
        at(2026, 10, 9, 16, 45),
        "Hi Lukas,\n\nyou are registered for NordData Summit 2026, Friday 11 and Saturday 12 December 2026, Bella Center "
        "Copenhagen. Badge pick-up: Thursday 10 Dec 18:00-21:00 or Friday from 08:00.\nRegistration fee EUR 650.00 "
        "(invoiced to Aldervane Marketing).\n\nSee you in Copenhagen!", folder=T)
    add("oschg", "Austrian Airlines <noreply@austrian.com>", "Schedule change for your booking QX4T7B",
        at(2026, 10, 20, 7, 15),
        "Dear Mr Brandt,\n\nunfortunately the schedule of your flight has changed:\n\nOS 305 on 10 December 2026, "
        "Vienna (VIE) - Copenhagen (CPH)\nNEW: departure 17:35, arrival 19:25 (previously 17:05 - 18:55)\n\n"
        "Your seat and baggage allowance are unchanged. No action is needed.\n\nAustrian Airlines", folder=T)
    desk = add("desk", "Aldervane Travel Desk <travel@aldervane.de>", "Pre-approval needed: Vienna / Copenhagen trip",
               at(2026, 10, 16, 13, 0),
               "Hi Lukas,\n\nfor the pre-approval of your December trip please reply with the total cost of transport "
               "and hotels (the NordData registration is paid by Marketing, leave it out) by 20 November 2026.\n\n"
               "Thanks,\nNina - Aldervane Travel Desk", folder=T, flag="2026-11-20")
    # ---- Donauwerke
    add("dw1", "Eva Kranz <eva.kranz@donauwerke.at>", "Kick-off notes", at(2026, 9, 15, 17, 30),
        "Hallo Lukas, attached our notes from the kick-off. Talk soon, Eva", folder=DW, unread=False)
    ws = add("dw2", "Eva Kranz <eva.kranz@donauwerke.at>", "Workshop dates confirmed", at(2026, 10, 12, 11, 20),
             "Hi Lukas,\n\nconfirmed: our two workshop sessions are on Wednesday 9 December, 14:00-17:30, and Thursday "
             "10 December, 09:00-13:00, at our office (Donauwerke AG, Am Hof 4, 1010 Wien, 3rd floor). Please ask for "
             "me at the reception.\n\nBest,\nEva Kranz\nHead of Strategy, Donauwerke AG", folder=DW)
    add("dw3", "Martin Huber <martin.huber@donauwerke.at>", "Data access for the workshop", at(2026, 10, 19, 8, 5),
        "Lukas, your guest account for our data room is active now. Martin", folder=DW)
    add("dw4", "Sabine Roth <sabine.roth@aldervane.de>", "[Donauwerke] staffing plan Q1", at(2026, 10, 13, 15, 0),
        "Lukas, see the attached staffing plan for Donauwerke in Q1. Sabine", folder=DW, unread=False)
    add("dw5", "Eva Kranz <eva.kranz@donauwerke.at>", "Workshop agenda", at(2026, 10, 21, 10, 40),
        "Hi Lukas,\n\ncould you please send me the final agenda for the workshop by 27 November 2026? I need to "
        "circulate it to our board members a week ahead.\n\nThanks,\nEva", folder=DW, flag="2026-11-27")
    # ---- Helios
    add("he1", "Jonas Weber <j.weber@helios-energie.de>", "Tariff model v3 - your comments", at(2026, 10, 19, 16, 10),
        "Hallo Lukas,\n\nattached is version 3 of the tariff model. Please send me your comments by Friday, "
        "6 November 2026 - we present it to the steering committee the week after.\n\nGruss, Jonas", folder=HE,
        flag="2026-11-06")
    add("he2", "Jonas Weber <j.weber@helios-energie.de>", "Steering committee minutes", at(2026, 9, 24, 12, 0),
        "Minutes of the September steering committee attached.", folder=HE, unread=False)
    add("he3", "Tobias Lang <tobias.lang@aldervane.de>", "RE: Helios invoice schedule", at(2026, 10, 7, 9, 45),
        "Lukas, finance confirmed the Helios invoice schedule (monthly, net 30). Tobias", folder=HE, unread=False)
    add("he4", "Helios Facility Desk <facility@helios-energie.de>", "Site access badges", at(2026, 10, 15, 14, 20),
        "Your visitor badge for the Helios headquarters is ready for collection at the gate.", folder=HE)
    # ---- Marlow
    add("ma1", "Olivia Grant <olivia.grant@marlowretail.co.uk>", "Change request CR-14", at(2026, 10, 17, 18, 0),
        "Hi Lukas,\n\nplease find change request CR-14 attached. We need it back signed by 30 October 2026 so that "
        "wave 2 can start on time.\n\nKind regards,\nOlivia Grant\nPMO, Marlow Retail", folder=MA, flag="2026-10-30")
    add("ma2", "Olivia Grant <olivia.grant@marlowretail.co.uk>", "Store rollout wave 2", at(2026, 10, 2, 9, 30),
        "FYI the wave 2 store list is final: 14 stores in the Midlands.", folder=MA, unread=False)
    add("ma3", "Sabine Roth <sabine.roth@aldervane.de>", "[Marlow] lessons learned draft", at(2026, 8, 27, 16, 0),
        "Draft of the wave 1 lessons learned for Marlow, comments welcome.", folder=MA, unread=False)
    # ---- recent, not project/travel: stays in the Inbox
    add("hr", "Aldervane People Team <people@aldervane.de>", "Your vacation plan for 2027", at(2026, 10, 15, 8, 30),
        "Dear Lukas,\n\nplease enter your vacation plan for 2027 in the HR portal by 15 November 2026.\n\n"
        "Your People Team", folder=INBOX, flag="2026-11-15")
    add("vpn", "Aldervane IT <it@aldervane.de>", "New VPN client", at(2026, 10, 19, 11, 0),
        "Please install the new VPN client from the software center when you get a chance.", folder=INBOX)
    add("lunch", "Sabine Roth <sabine.roth@aldervane.de>", "Team lunch on Friday", at(2026, 10, 20, 12, 15),
        "We're going to the Viktualienmarkt on Friday at 12:30, join us if you can!", folder=INBOX)
    add("hb", "Handelsblatt <newsletter@handelsblatt.com>", "Morning Briefing: Energy prices fall", at(2026, 10, 21, 6, 0),
        "Today's top stories... Subscribe to Handelsblatt Premium - offer ends 31 October.", folder=INBOX)
    add("li", "LinkedIn <jobs-noreply@linkedin.com>", "5 new jobs for Senior Consultant", at(2026, 10, 18, 7, 0),
        "Jobs you may be interested in...", folder=INBOX)
    add("allhands", "Aldervane Management <management@aldervane.de>", "All-hands on 4 November",
        at(2026, 10, 16, 17, 0), "Our winter all-hands takes place on 4 November in the Munich office, 16:00-18:00.",
        folder=INBOX, unread=False)
    # ---- before 1 October 2026, not project/travel: archive
    add("party", "Aldervane Events <events@aldervane.de>", "Summer party photos", at(2026, 7, 10, 10, 0),
        "The photos from our summer party are on the intranet.", folder=ARCH, unread=False)
    add("bonus", "Aldervane People Team <people@aldervane.de>", "Your Q2 bonus letter", at(2026, 6, 30, 9, 0),
        "Your Q2 bonus letter is available in the HR portal.", folder=ARCH, unread=False)
    add("maint", "Aldervane IT <it@aldervane.de>", "Maintenance weekend 19-20 September", at(2026, 9, 14, 15, 0),
        "Email and VPN will be unavailable on 19-20 September.", folder=ARCH, unread=False)
    add("hb_old", "Handelsblatt <newsletter@handelsblatt.com>", "Morning Briefing: DAX at record high",
        at(2026, 9, 29, 6, 0), "Today's top stories...", folder=ARCH, unread=False)
    add("welcome", "Aldervane People Team <people@aldervane.de>", "Welcome to Aldervane!", at(2025, 12, 1, 9, 0),
        "Welcome on board, Lukas! Your onboarding plan is attached.", folder=ARCH, unread=False)
    add("expense", "Aldervane Finance <finance@aldervane.de>", "Expense report approved", at(2026, 8, 18, 14, 0),
        "Your expense report 'Leeds client visit' was approved.", folder=ARCH, unread=False)
    add("cfp", "Data Innovation Forum <cfp@dataforum.eu>", "Call for papers closes soon", at(2026, 9, 3, 8, 0),
        "The Data Innovation Forum 2027 is looking for speakers. Read the guidelines on our website.", folder=ARCH)
    mails.sort(key=lambda x: x[1])
    build_profile(f"{d}/thunderbird-profile.tar.gz", ME, {"Inbox": mails}, tz="Europe/Berlin")
    flags = [i for i in info if i["flag"]]
    assert len(flags) == 5
    for i in flags:  # what a line of followups.txt must mention next to the date (sender or subject)
        name = i["from"].split("<")[0].strip()
        i["tokens"] = [norm(name), norm(name.split()[-1]), norm(i["subject"])[:14]] + EXTRA_TOKENS.get(i["key"], [])
    dump_expected(d, {
        "host": HOST, "me": ME[1], "tz": "Europe/Berlin", "mails": info,
        "folders": ["Travel", "Projects", "Projects/Donauwerke", "Projects/Helios", "Projects/Marlow"],
        "trip": TRIP, "total": TOTAL, "desk_id": desk, "desk": "travel@aldervane.de", "workshop_id": ws,
        "pdfs": {f: md5(f"{att}/{f}") for f in os.listdir(att)},
        "summit_days": ["2026-12-11", "2026-12-12"],
    })
