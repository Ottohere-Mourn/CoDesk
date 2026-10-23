"""W2 - Fenwick Spend (expense portal on :8102): deciding 12 expense reports vs filing a trip report + CSV export.

build(out_dir) writes: app_w2.py, seed.db, Fenwick_TE_Policy_2026.pdf, Downloads/* (Dana's trip receipts and two
unrelated files), expected.json.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lib_w  # noqa: E402
from lib_w import font  # noqa: E402
from lib_w2_receipts import document, photo, rideshare, thermal  # noqa: E402

PASSWORD = "Fenwick-Spend-26"
# id, username, name, department, title, manager
USERS = [
    (1, "dana.okafor", "Dana Okafor", "Marketing", "Marketing Director", 2),
    (2, "victor.hale", "Victor Hale", "Executive", "VP Commercial", None),
    (3, "leo.marsh", "Leo Marsh", "Marketing", "Brand Manager", 1),
    (4, "aisha.bello", "Aisha Bello", "Marketing", "Field Marketing Manager", 1),
    (5, "tom.becker", "Tom Becker", "Marketing", "Content Lead", 1),
    (6, "grace.ito", "Grace Ito", "Marketing", "Events Coordinator", 1),
    (7, "ravi.menon", "Ravi Menon", "Marketing", "Digital Marketing Specialist", 1),
    (8, "sofia.lindqvist", "Sofia Lindqvist", "Sales", "Key Account Manager", 9),
    (9, "marco.ruiz", "Marco Ruiz", "Sales", "Head of Sales", 2),
    (10, "hannah.price", "Hannah Price", "Finance", "Finance Controller", 2),
    (11, "ben.carter", "Ben Carter", "Operations", "Supply Chain Lead", 2),
    (12, "owen.hart", "Owen Hart", "Sales", "Account Executive", 9),
]
NAMES = {u[0]: u[2] for u in USERS}


def jpg(im, q=82):
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue(), "image/jpeg"


def png(im):
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue(), "image/png"


def day(s):
    return dt.date.fromisoformat(s)


def us(s):  # 2026-10-06 -> 10/06/2026
    return day(s).strftime("%m/%d/%Y")


def head(merchant, addr, when, extra=()):
    rows = [("c", merchant, 24, True)] + [("c", a) for a in addr] + [("gap", 8), ("l", when)] + [("l", e) for e in extra] + [("sep",)]
    return rows


def tail(card="VISA ****4471", seed=1, thanks="THANK YOU"):
    return [("sep",), ("l", f"{card}  APPROVED"), ("l", f"AUTH {random.Random(seed).randint(100000, 999999)}"), ("gap", 6),
            ("c", thanks), ("barcode", seed)]


def items_rows(items):
    out = []
    for name, qty, unit in items:
        amt = qty * unit
        out.append(("lr", f"{qty} x {name}" if qty > 1 else name, f"{amt:.2f}"))
    return out


# ------------------------------------------------------------------ the 12 reports waiting for Dana (task A)
def pending_receipts():
    """{(report, line no): (filename, bytes, ctype)} for the reports in Dana's queue."""
    R = {}
    R[(2041, 1)] = ("metro_cab_1006.jpg",) + jpg(photo(thermal(
        head("METRO CAB CO.", ["Columbus, OH", "Cab #2217  Lic. CMH-4412"], "10/06/2026  08:42") +
        [("l", "From: CMH Airport"), ("l", "To: 3500 W Broad St"), ("sep",), ("lr", "Fare", "31.90"), ("lr", "Tip", "6.50"),
         ("lr", "TOTAL", "$38.40", True)] + tail(seed=2041, card="MC ****8812")), 2041))
    R[(2042, 1)] = ("officehub_receipt.jpg",) + jpg(photo(thermal(
        head("OfficeHub", ["Store #212", "1450 Nicollet Mall, Minneapolis MN"], "10/09/2026 17:03  REG 04") +
        items_rows([("FOAM BOARD 20X30 WHT", 6, 8.99), ("RETRACT BANNER STAND", 1, 89.99), ("GAFFER TAPE 2IN BLK", 3, 7.49),
                    ("MARKERS 12PK", 1, 3.85)]) +
        [("sep",), ("lr", "SUBTOTAL", "170.25"), ("lr", "SALES TAX", "13.95"), ("lr", "TOTAL", "$184.20", True)] +
        tail(seed=2042, card="VISA ****3390")), 2042))
    R[(2043, 1)] = ("riverside_folio.png",) + png(document(
        "Guest folio", "RIVERSIDE TOWER HOTEL", (23, 43, 77), "320 N Wacker Dr, Chicago IL 60606  ·  +1 312 555 0140",
        [("Guest", "Tom Becker"), ("Folio no.", "RT-5520931"), ("Arrival", "07 Oct 2026"), ("Departure", "09 Oct 2026"),
         ("Room", "1412 · King Deluxe"), ("Rate", "USD 289.00 / night")],
        ["Date", "Description", "Amount (USD)"],
        [["10/07/2026", "Room charge", "289.00"], ["10/07/2026", "Room tax 17.4%", "50.29"],
         ["10/08/2026", "Room charge", "289.00"], ["10/08/2026", "Room tax 17.4%", "50.28"],
         ["10/09/2026", "Payment VISA ****5521", "-678.57"]],
        [("Total charges", "678.57", True), ("Balance due", "0.00", False)],
        ["Thank you for staying with us.", "Riverside Tower Hotel LLC · Tax ID 36-4471902"], [180, 600, 120]))
    R[(2043, 2)] = ("checker_taxi.jpg",) + jpg(photo(thermal(
        head("CHECKER TAXI", ["Chicago, IL", "Medallion 5531"], "10/07/2026  10:17") +
        [("l", "From: ORD Terminal 2"), ("l", "To: 320 N Wacker Dr"), ("sep",), ("lr", "Fare", "26.00"), ("lr", "Tip", "5.00"),
         ("lr", "TOTAL", "$31.00", True)] + tail(seed=2043, card="VISA ****5521")), 2043))
    R[(2044, 1)] = ("copper_pot_dinner.jpg",) + jpg(photo(thermal(
        head("THE COPPER POT", ["Kitchen & Bar", "212 N 2nd St, Minneapolis MN"], "10/10/2026  21:34",
             ["Table 9   Guests: 4   Server: Jess"]) +
        items_rows([("Charcuterie board", 1, 24.00), ("Caesar salad", 2, 13.00), ("Walleye", 1, 32.00), ("Braised short rib", 1, 38.00),
                    ("Roast chicken", 1, 29.00), ("Mushroom risotto", 1, 26.50), ("Pinot Noir (btl)", 1, 42.00), ("Craft beer", 2, 7.00)]) +
        [("sep",), ("l", "All prices include sales tax"), ("lr", "TOTAL", "$231.50", True)] + tail(seed=2044, card="AMEX ****1007")), 2044))
    R[(2045, 1)] = ("adtech_order_confirmation.png",) + _adtech_png()
    R[(2046, 1)] = ("madison_park_folio.png",) + png(document(
        "Guest folio", "HOTEL MADISON PARK", (92, 31, 46), "27 E 28th St, New York NY 10016  ·  +1 212 555 0170",
        [("Guest", "Leo Marsh"), ("Folio no.", "HMP-208813"), ("Arrival", "12 Oct 2026"), ("Departure", "14 Oct 2026"),
         ("Room", "806 · Queen Standard"), ("Rate", "USD 329.00 / night")],
        ["Date", "Description", "Amount (USD)"],
        [["10/12/2026", "Room charge", "329.00"], ["10/12/2026", "NYC hotel tax 14.75%", "48.53"],
         ["10/12/2026", "NYC occupancy fee", "3.50"], ["10/13/2026", "Room charge", "329.00"],
         ["10/13/2026", "NYC hotel tax 14.75%", "48.53"], ["10/13/2026", "NYC occupancy fee", "3.50"],
         ["10/14/2026", "Payment MC ****8812", "-762.06"]],
        [("Total charges", "762.06", True), ("Balance due", "0.00", False)],
        ["We hope to welcome you back soon."], [180, 600, 120]))
    R[(2046, 2)] = ("nyc_cab.jpg",) + jpg(photo(thermal(
        head("NYC TAXI", ["Medallion 7K42", "Driver #5530912"], "10/12/2026  14:05") +
        [("l", "From: JFK Airport"), ("l", "To: 27 E 28th St"), ("sep",), ("lr", "Flat fare JFK-Manhattan", "70.00"),
         ("lr", "Tolls", "6.94"), ("lr", "Tip", "12.36"), ("lr", "TOTAL", "$89.30", True)] + tail(seed=2046, card="MC ****8812")), 2046))
    R[(2047, 1)] = ("lucias_dinner.jpg",) + jpg(photo(thermal(
        head("LUCIA'S TRATTORIA", ["1432 W 31st St, Minneapolis MN"], "10/13/2026  20:51", ["Table 4   Guests: 4"]) +
        items_rows([("Antipasti misti", 1, 22.00), ("Burrata", 1, 16.00), ("Lasagna", 1, 24.00), ("Branzino", 1, 34.00),
                    ("Pappardelle ragu", 1, 26.00), ("Veal milanese", 1, 36.00), ("Tiramisu", 2, 11.00),
                    ("Sparkling water", 2, 5.00), ("Espresso", 4, 5.50)]) +
        [("sep",), ("l", "Tax included"), ("lr", "TOTAL", "$212.00", True)] + tail(seed=2047, card="VISA ****3390")), 2047))
    R[(2049, 1)] = ("badger_rental.png",) + png(document(
        "Rental agreement / receipt", "BADGER CAR RENTAL", (22, 99, 59), "MKE Airport, 5300 S Howell Ave, Milwaukee WI",
        [("Renter", "Grace Ito"), ("Agreement", "BCR-77120458"), ("Pick-up", "28 Sep 2026 08:05"),
         ("Return", "28 Sep 2026 19:32"), ("Vehicle", "Toyota Corolla · Compact"), ("Mileage", "164 mi")],
        ["Date", "Description", "Amount (USD)"],
        [["09/28/2026", "Time & mileage, 1 day @ 89.00", "89.00"], ["09/28/2026", "Fuel service option", "24.50"],
         ["09/28/2026", "Taxes, airport concession & fees", "29.10"], ["09/28/2026", "Charged to VISA ****6604", "-142.60"]],
        [("Total", "142.60", True)], ["Thank you for renting with Badger."], [180, 600, 120]))
    R[(2050, 1)] = ("atlantic_eticket.png",) + png(document(
        "E-ticket receipt", "ATLANTIC AIRWAYS", (12, 52, 110), "Ticket office · atlanticairways.example",
        [("Passenger", "MENON / RAVI MR"), ("Ticket number", "176 2290017745"), ("Booking ref", "QX8LMT"),
         ("Date of issue", "05 Oct 2026"), ("Cabin", "Business (J)"), ("Form of payment", "AMEX ****1007")],
        ["Date", "Flight / route", "Class"],
        [["11 Oct 2026", "AA 712  MSP 17:40 - LHR 07:25+1", "J"], ["15 Oct 2026", "AA 715  LHR 11:05 - MSP 14:10", "J"]],
        [("Fare", "3,412.00", False), ("Taxes, fees & charges", "428.00", False), ("Total (USD)", "3,840.00", True)],
        ["This receipt is not a boarding pass."], [180, 640, 80]))
    R[(2050, 2)] = ("kensington_folio.png",) + png(document(
        "Guest folio", "THE KENSINGTON ROOMS", (60, 60, 60), "18 Queen's Gate Terrace, London SW7  ·  +44 20 7946 0811",
        [("Guest", "Ravi Menon"), ("Folio no.", "KR-31877"), ("Arrival", "11 Oct 2026"), ("Departure", "15 Oct 2026"),
         ("Room", "Superior Double"), ("Rate", "USD 338.00 / night incl. VAT")],
        ["Date", "Description", "Amount (USD)"],
        [["11/10/2026", "Accommodation incl. 20% VAT", "338.00"], ["12/10/2026", "Accommodation incl. 20% VAT", "338.00"],
         ["13/10/2026", "Accommodation incl. 20% VAT", "338.00"], ["14/10/2026", "Accommodation incl. 20% VAT", "338.00"],
         ["15/10/2026", "Payment AMEX ****1007", "-1,352.00"]],
        [("Total", "1,352.00", True), ("Balance", "0.00", False)], ["VAT reg. GB 553 1120 87"], [180, 600, 120]))
    R[(2051, 1)] = ("mile_high_folio.png",) + png(document(
        "Guest folio", "MILE HIGH INN", (150, 72, 18), "1550 Court Pl, Denver CO 80202  ·  +1 303 555 0119",
        [("Guest", "Leo Marsh"), ("Folio no.", "MHI-90321"), ("Arrival", "16 Oct 2026"), ("Departure", "18 Oct 2026"),
         ("Room", "512 · King"), ("Rate", "USD 199.00 / night")],
        ["Date", "Description", "Amount (USD)"],
        [["10/16/2026", "Room charge", "199.00"], ["10/16/2026", "Lodging tax 15.75%", "31.35"],
         ["10/17/2026", "Room charge", "199.00"], ["10/17/2026", "Lodging tax 15.75%", "31.34"],
         ["10/17/2026", "Minibar", "18.00"], ["10/18/2026", "Payment MC ****8812", "-478.69"]],
        [("Total charges", "478.69", True), ("Balance due", "0.00", False)], ["Thank you for your stay."], [180, 600, 120]))
    R[(2051, 2)] = ("union_station_grill.jpg",) + jpg(photo(thermal(
        head("UNION STATION GRILL", ["1701 Wynkoop St, Denver CO"], "10/17/2026  19:12", ["Guests: 1"]) +
        items_rows([("Steak salad", 1, 22.00), ("Soup of the day", 1, 8.50), ("Iced tea", 1, 4.00)]) +
        [("sep",), ("lr", "SUBTOTAL", "34.50"), ("lr", "TAX 8.81%", "3.04"), ("lr", "TIP", "4.26"), ("lr", "TOTAL", "$41.80", True)]
        + tail(seed=2051, card="MC ****8812")), 2051))
    R[(2052, 1)] = ("swiftship_receipt.jpg",) + jpg(photo(thermal(
        head("SWIFTSHIP COURIER", ["Same-day · Minneapolis/St Paul"], "10/20/2026  11:26", ["Job 88-41207"]) +
        [("l", "From: Fenwick & Hale, 800 Marquette Ave"), ("l", "To: Brightline Agency, St Paul"), ("sep",),
         ("lr", "Same-day service", "54.00"), ("lr", "Fuel surcharge", "6.48"), ("lr", "Tax", "4.27"), ("lr", "TOTAL", "$64.75", True)]
        + tail(seed=2052, card="VISA ****3390")), 2052))
    return R


def _adtech_png():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    def body(dr, im, top):
        y = top + 40
        dr.text((60, y), "AdTech Summit 2026", fill=(20, 20, 60), font=font(30, bold=True))
        dr.text((60, y + 48), "Order confirmation  #ATS-26-11873", fill=(60, 60, 60), font=font(20))
        dr.text((60, y + 100), "Order date: July 8, 2026", fill=(30, 30, 30), font=font(19, bold=True))
        dr.text((60, y + 132), "Billed to: Ravi Menon, Fenwick & Hale · VISA ending 7731", fill=(60, 60, 60), font=font(17))
        dr.rectangle((60, y + 180, im.width - 60, y + 300), outline=(210, 210, 220))
        dr.text((80, y + 198), "Early-bird full pass · 17-19 Nov 2026, Austin TX", fill=(30, 30, 30), font=font(18))
        dr.text((im.width - 180, y + 198), "$450.00", fill=(30, 30, 30), font=font(18))
        dr.text((80, y + 250), "Total charged", fill=(30, 30, 30), font=font(19, bold=True))
        dr.text((im.width - 180, y + 250), "$450.00", fill=(30, 30, 30), font=font(19, bold=True))
        dr.text((60, y + 330), "Your badge will be emailed two weeks before the event.", fill=(100, 100, 100), font=font(16))
    lib_w.browser_shot(path, "tickets.adtechsummit.example/orders/ATS-26-11873", "Order confirmed", body, (1000, 560))
    data = open(path, "rb").read()
    os.remove(path)
    return data, "image/png"


# report id: (employee, submitted, title, purpose, preapproval,
#             [(date, category, merchant, amount, attendees, description, has receipt)], expected decision, reason regex)
PENDING = {
    2041: (3, "2026-10-12", "Store visits - Columbus, 6 Oct", "Checked the autumn display roll-out in four Columbus stores.", "",
           [("2026-10-06", "Ground transport", "Metro Cab Co.", 38.40, 1, "Airport to stores", True),
            ("2026-10-06", "Meals", "Brew & Bagel", 22.50, 1, "Lunch", False)], "approve", None),
    2042: (4, "2026-10-13", "Booth supplies - Midwest Grocers Expo", "Booth materials for the Midwest Grocers Expo (15-16 Oct).", "",
           [("2026-10-09", "Office supplies", "OfficeHub #212", 248.20, 1, "Foam boards, banner stand, tape", True)],
           "reject", r"amount|total|184|248|match|differ|overstat|inflat|exceed|higher|more than"),
    2043: (5, "2026-10-14", "Content shoot - Chicago, 7-9 Oct", "Product video shoot with the agency.", "",
           [("2026-10-09", "Lodging", "Riverside Tower Hotel", 678.57, 1, "2 nights, 7-9 Oct", True),
            ("2026-10-07", "Ground transport", "Checker Taxi", 31.00, 1, "Airport to hotel", True)],
           "reject", r"rate|night|250|289|limit|cap\b|lodging|hotel|room"),
    2044: (6, "2026-10-14", "Dinner with Northstar Grocers buyers", "Dinner with three category buyers from Northstar Grocers.", "",
           [("2026-10-10", "Meals", "The Copper Pot", 231.50, 4, "Client dinner, 4 people", True)],
           "reject", r"alcohol|wine|beer|pinot|liquor|\bbar\b"),
    2045: (7, "2026-10-15", "AdTech Summit 2026 registration", "Early-bird registration for AdTech Summit (17-19 Nov).", "",
           [("2026-07-08", "Conference fees", "AdTech Summit 2026", 450.00, 1, "Early-bird pass", True)],
           "reject", r"60|days?\b|late|old|july|\bjul\b|deadline|stale|expired|outside|too long"),
    2046: (3, "2026-10-16", "Retailer meetings - New York, 12-14 Oct", "Range review meetings with two NYC retail chains.", "",
           [("2026-10-14", "Lodging", "Hotel Madison Park", 762.06, 1, "2 nights, 12-14 Oct", True),
            ("2026-10-12", "Ground transport", "NYC Taxi", 89.30, 1, "JFK to hotel", True)], "approve", None),
    2047: (4, "2026-10-16", "Distributor partner dinner", "Dinner with the two regional distributor partners.", "",
           [("2026-10-13", "Meals", "Lucia's Trattoria", 212.00, 4, "Partner dinner, 4 people", True)], "approve", None),
    2048: (5, "2026-10-17", "Stock photo subscription - October", "Monthly stock photo plan for campaign assets.", "",
           [("2026-10-01", "Software & subscriptions", "PhotoStock Pro", 19.00, 1, "Monthly plan", False)], "approve", None),
    2049: (6, "2026-10-17", "Venue scouting - Milwaukee", "Visited three venues for the spring trade event.", "",
           [("2026-10-08", "Ground transport", "Badger Car Rental", 142.60, 1, "Car rental for venue visits", True)],
           "reject", r"date|sep|09[/-]28|9/28|28"),
    2050: (7, "2026-10-19", "EMEA brand summit - London, 11-15 Oct", "Presented the 2027 brand plan at the EMEA summit.",
           "Business class pre-approved by Victor Hale (VP Commercial), ref PA-2291",
           [("2026-10-05", "Airfare", "Atlantic Airways", 3840.00, 1, "MSP-LHR return, business class", True),
            ("2026-10-15", "Lodging", "The Kensington Rooms", 1352.00, 1, "4 nights, 11-15 Oct", True)], "approve", None),
    2051: (3, "2026-10-20", "Sales training - Denver, 16-18 Oct", "Key-account selling course.", "",
           [("2026-10-18", "Lodging", "Mile High Inn", 460.69, 1, "2 nights; minibar (18.00) removed - personal", True),
            ("2026-10-17", "Meals", "Union Station Grill", 41.80, 1, "Dinner", True)], "approve", None),
    2052: (4, "2026-10-21", "Courier - print proofs to agency", "Same-day delivery of print proofs to Brightline Agency.", "",
           [("2026-10-20", "Courier & postage", "SwiftShip Courier", 64.75, 1, "Same-day proofs", True)], "approve", None),
}

# ------------------------------------------------------------------ history (2001-2040)
KINDS = {
    "taxi": ("Ground transport", ["Metro Cab Co.", "Checker Taxi", "Zipp"], (18, 46)),
    "meal": ("Meals", ["Lucia's Trattoria", "The Copper Pot", "Union Station Grill", "Nolo Kitchen", "Brew & Bagel"], (38, 150)),
    "hotel": ("Lodging", ["Hampton Suites Des Moines", "Riverfront Inn Omaha", "Prairie Lodge Fargo"], (139, 219)),
    "air": ("Airfare", ["Northline Airways"], (210, 520)),
    "supplies": ("Office supplies", ["OfficeHub #212", "PaperWorks"], (28, 160)),
    "software": ("Software & subscriptions", ["Canvaspro Design", "PhotoStock Pro", "SurveyNest"], (12, 30)),
    "courier": ("Courier & postage", ["SwiftShip Courier"], (25, 90)),
    "conf": ("Conference fees", ["Retail Marketing Forum", "CPG Analytics Summit", "Supply Chain Live"], (295, 695)),
    "training": ("Other", ["Coursely Business"], (49, 199)),
}
# id, employee, submitted, status, title, kinds, comment
HIST = [
    (2001, 5, "2026-09-02", "Paid", "Photo props - autumn campaign", ["supplies"], ""),
    (2002, 8, "2026-09-03", "Paid", "Client lunch - Hy-Vee buyers", ["meal"], ""),
    (2003, 3, "2026-09-04", "Paid", "Store checks - Des Moines", ["hotel", "taxi"], ""),
    (2004, 10, "2026-09-07", "Paid", "Audit workshop materials", ["supplies"], ""),
    (2005, 7, "2026-09-08", "Paid", "Analytics tool - September", ["software"], ""),
    (2006, 4, "2026-09-09", "Rejected", "Expo shipping", ["courier!"], "The courier charge has no receipt. Please attach it and resubmit."),
    (2007, 9, "2026-09-10", "Paid", "Regional sales meeting - Omaha", ["air", "hotel", "meal"], ""),
    (2008, 6, "2026-09-11", "Paid", "Holiday event venue deposit", ["conf"], ""),
    (2009, 1, "2026-09-14", "Paid", "Agency kickoff lunch", ["meal"], ""),
    (2010, 11, "2026-09-15", "Paid", "Supplier visit - Fargo", ["air", "taxi"], ""),
    (2011, 12, "2026-09-16", "Paid", "Prospect dinner", ["meal"], ""),
    (2012, 3, "2026-09-17", "Paid", "Retail Marketing Forum", ["conf", "taxi"], ""),
    (2013, 5, "2026-09-18", "Rejected", "Studio lunch", ["meal"], "Beer is on the receipt - alcohol is not reimbursable. Resubmit with the food only."),
    (2014, 8, "2026-09-21", "Paid", "Customer visit - Sioux Falls", ["hotel", "meal"], ""),
    (2015, 7, "2026-09-22", "Paid", "Survey panel - September", ["software"], ""),
    (2016, 4, "2026-09-23", "Paid", "Sample shipping to retailers", ["courier", "supplies"], ""),
    (2017, 10, "2026-09-24", "Paid", "Finance offsite lunch", ["meal"], ""),
    (2018, 6, "2026-09-25", "Paid", "Event supplies", ["supplies"], ""),
    (2019, 9, "2026-09-28", "Rejected", "Team dinner", ["meal+"], "Above the $60 per attendee meal limit."),
    (2020, 11, "2026-09-29", "Paid", "Forklift safety course", ["training"], ""),
    (2021, 3, "2026-10-01", "Approved", "Store visits - Rochester", ["taxi", "meal"], ""),
    (2022, 8, "2026-10-01", "Approved", "Client lunch - Cub Foods", ["meal"], ""),
    (2023, 5, "2026-10-02", "Approved", "Video editing plug-in", ["software"], ""),
    (2024, 12, "2026-10-02", "Approved", "Prospect meetings - Madison", ["air", "taxi"], ""),
    (2025, 4, "2026-10-05", "Approved", "Expo booth graphics print", ["supplies", "courier"], ""),
    (2026, 10, "2026-10-05", "Approved", "IFRS update training", ["training"], ""),
    (2027, 1, "2026-10-06", "Approved", "Retail Marketing Forum - Atlanta", ["air", "hotel", "conf"], ""),
    (2028, 7, "2026-10-06", "Rejected", "Conference ticket", ["conf"], "Book this through the events budget (pre-approved conference list), not as an expense."),
    (2029, 9, "2026-10-07", "Approved", "Key account dinner", ["meal"], ""),
    (2030, 6, "2026-10-07", "Approved", "Venue walkthrough - St Paul", ["taxi"], ""),
    (2031, 11, "2026-10-08", "Approved", "Warehouse audit - Des Moines", ["hotel", "taxi"], ""),
    (2032, 3, "2026-10-08", "Approved", "Shelf-talker samples", ["courier"], ""),
    (2033, 8, "2026-10-09", "Submitted", "Customer visit - Fargo", ["air", "hotel"], ""),
    (2034, 12, "2026-10-09", "Approved", "CRM add-on licence", ["software"], ""),
    (2035, 10, "2026-10-09", "Submitted", "Audit committee dinner", ["meal"], ""),
    (2036, 11, "2026-10-10", "Submitted", "Supplier QA visit", ["taxi", "meal"], ""),
    (2037, 9, "2026-10-10", "Submitted", "Sales kickoff venue", ["conf"], ""),
    (2038, 8, "2026-10-11", "Approved", "Trade lunch", ["meal"], ""),
    (2039, 10, "2026-10-11", "Approved", "Finance systems course", ["training"], ""),
    (2040, 11, "2026-10-11", "Rejected", "Pallet labels", ["supplies"], "The receipt date does not match the line date."),
]


def hist_line(rng, rid, kind, submitted):
    plus, missing = kind.endswith("+"), kind.endswith("!")  # meal over the limit / receipt not attached
    kind = kind.rstrip("+!")
    cat, merchants, (lo, hi) = KINDS[kind]
    merchant = rng.choice(merchants)
    when = (day(submitted) - dt.timedelta(days=rng.randint(1, 9))).isoformat()
    att, desc = 1, ""
    if kind == "hotel":
        nights, rate = rng.randint(1, 2), rng.randint(lo, hi)
        tax = round(rate * 0.12, 2)
        amount = round(nights * (rate + tax), 2)
        rows = head(merchant.upper(), ["Guest folio (summary)"], f"Check-out {us(when)}") + [
            ("lr", f"Room {nights} night(s) @ {rate:.2f}", f"{nights * rate:.2f}"), ("lr", "Taxes", f"{nights * tax:.2f}"),
            ("lr", "TOTAL", f"${amount:.2f}", True)]
        desc = f"{nights} night(s)"
    else:
        amount = round(rng.uniform(lo, hi), 2) if kind != "software" else rng.choice([12.99, 19.00, 29.00])
        if kind == "meal":
            att = 2 if plus else max(1, int(amount // 52) + 1)
            if plus:
                amount = round(rng.uniform(150, 190), 2)
            desc = f"{att} people" if att > 1 else "Meal"
        if kind == "meal":
            food = round(amount * 0.62, 2)
            rows = head(merchant.upper(), ["Minneapolis, MN"], f"{us(when)}  19:{rng.randint(10, 59)}", [f"Guests: {att}"]) + [
                ("lr", "Food", f"{food:.2f}"), ("lr", "Beverages" if rid != 2013 else "Beer (3)", f"{amount - food:.2f}"),
                ("lr", "TOTAL", f"${amount:.2f}", True)]
        else:
            rows = head(merchant.upper(), ["Minneapolis, MN"], f"{us(when)}  {rng.randint(8, 18)}:{rng.randint(10, 59)}") + [
                ("lr", {"taxi": "Fare + tip", "air": "Economy fare incl. taxes", "conf": "Registration"}.get(kind, cat), f"{amount:.2f}"),
                ("lr", "TOTAL", f"${amount:.2f}", True)]
    receipt = None if missing else jpg(thermal(rows + tail(seed=rid * 10 + len(rows))), 70)
    return (when, cat, merchant, amount, att, desc), receipt


# ------------------------------------------------------------------ Dana's trip (task B)
B_LINES = [  # category, amount, accepted dates, merchant regex, file
    {"category": "Airfare", "amount": 412.80, "dates": ["2026-10-14", "2026-10-02", "2026-10-16"], "merchant": r"northline",
     "file": "eticket_NL5KQ2.pdf"},
    {"category": "Lodging", "amount": 561.17, "dates": ["2026-10-14", "2026-10-15", "2026-10-16"], "merchant": r"lakeshore",
     "file": "Folio_LakeshoreGrand_88231907.pdf"},
    {"category": "Ground transport", "amount": 52.35, "dates": ["2026-10-14"], "merchant": r"yellow|cab|taxi",
     "file": "IMG_20261014_092733.jpg"},
    {"category": "Ground transport", "amount": 47.90, "dates": ["2026-10-16"], "merchant": r"zipp", "file": "Zipp_receipt_Oct16.png"},
    {"category": "Meals", "amount": 186.40, "dates": ["2026-10-15"], "merchant": r"harbor", "file": "IMG_20261015_221047.jpg",
     "attendees": 4},
]
DINNER_FULL, DINNER_WINE = 294.40, 108.00


def trip_files(d):
    os.makedirs(d, exist_ok=True)
    document("E-ticket receipt", "NORTHLINE AIRWAYS", (0, 84, 140), "northline.example · Customer care +1 800 555 0144",
             [("Passenger", "OKAFOR / DANA MS"), ("Booking ref", "NL5KQ2"), ("Ticket number", "629 2101554380"),
              ("Date of issue", "02 Oct 2026"), ("Cabin", "Economy (K)"), ("Form of payment", "VISA ****4471")],
             ["Date", "Flight / route", "Class"],
             [["14 Oct 2026", "NL 1418  MSP 07:10 - ORD 08:35", "K"], ["16 Oct 2026", "NL 1425  ORD 18:45 - MSP 20:12", "K"]],
             [("Fare", "356.00", False), ("Taxes, fees & charges", "56.80", False), ("Total (USD)", "412.80", True)],
             ["This receipt is not a boarding pass.", "Checked bag allowance: 0 (Economy Basic)."], [180, 640, 80]
             ).save(f"{d}/eticket_NL5KQ2.pdf", "PDF", resolution=120)
    document("Guest folio", "LAKESHORE GRAND HOTEL", (14, 70, 92), "301 E North Water St, Chicago IL 60611  ·  +1 312 555 0188",
             [("Guest", "Dana Okafor"), ("Folio no.", "88231907"), ("Arrival", "14 Oct 2026"), ("Departure", "16 Oct 2026"),
              ("Room", "1907 · King City View"), ("Rate", "USD 239.00 / night")],
             ["Date", "Description", "Amount (USD)"],
             [["10/14/2026", "Room charge", "239.00"], ["10/14/2026", "Room tax 17.4%", "41.59"],
              ["10/15/2026", "Room charge", "239.00"], ["10/15/2026", "Room tax 17.4%", "41.58"],
              ["10/16/2026", "Payment VISA ****4471", "-561.17"]],
             [("Total charges", "561.17", True), ("Balance due", "0.00", False)],
             ["Thank you for staying at the Lakeshore Grand.", "Lakeshore Grand Hotel LLC"], [180, 600, 120]
             ).save(f"{d}/Folio_LakeshoreGrand_88231907.pdf", "PDF", resolution=120)
    photo(thermal(head("CHICAGO YELLOW CAB", ["Medallion 4471", "Driver #2290531"], "10/14/2026  09:21") +
                  [("l", "From: O'Hare Intl (ORD) T1"), ("l", "To: 301 E North Water St"), ("sep",), ("lr", "Fare", "43.60"),
                   ("lr", "Tip", "8.75"), ("lr", "TOTAL", "$52.35", True)] + tail(seed=9001)), 9001, angle=-3.0
          ).convert("RGB").save(f"{d}/IMG_20261014_092733.jpg", "JPEG", quality=84)
    rideshare(f"{d}/Zipp_receipt_Oct16.png", "Fri, Oct 16, 2026 · 4:05 PM", "Lakeshore Grand Hotel, 301 E North Water St",
              "O'Hare International Airport (ORD)", [("Trip fare", "$39.40"), ("Booking fee", "$2.50"), ("Tip", "$6.00")],
              "$47.90", "VISA ••••4471", "Driver: Marcus · Toyota Camry", 9002)
    photo(thermal(head("HARBOR & VINE", ["Seafood · Steaks · Wine", "435 N Michigan Ave, Chicago IL"], "10/15/2026  21:58",
                       ["Table 12   Guests: 4   Server: Ana"]) +
                  items_rows([("Burrata", 1, 16.00), ("Fried calamari", 1, 18.50), ("Ribeye 14oz", 2, 48.00), ("Halibut", 1, 36.00),
                              ("Truffle fries", 1, 11.90), ("Sparkling water", 2, 4.00), ("Cabernet Sauv. (btl)", 1, 78.00),
                              ("Chardonnay (glass)", 2, 15.00)]) +
                  [("sep",), ("l", "All prices include 11.75% sales tax"), ("lr", "TOTAL", "$294.40", True), ("gap", 6),
                   ("l", "Tip: ____________")] + tail(seed=9003)), 9003, angle=1.6
          ).convert("RGB").save(f"{d}/IMG_20261015_221047.jpg", "JPEG", quality=84)
    # unrelated files that live in Downloads too
    photo(thermal(head("NOLO KITCHEN", ["Minneapolis, MN"], "09/22/2026  13:12") +
                  items_rows([("Grain bowl", 1, 15.50), ("Lemonade", 1, 4.50)]) + [("lr", "TOTAL", "$20.00", True)] + tail(seed=9004)),
          9004).convert("RGB").save(f"{d}/IMG_20260922_131205.jpg", "JPEG", quality=80)
    lib_w.doc_pdf(f"{d}/Kestrel_Foods_meeting_agenda.pdf", [
        ("title", "Kestrel Foods x Fenwick & Hale"), ("p", "Joint business planning, Chicago, 15 October 2026"),
        ("li", "09:30 Category review (snacks, beverages)"), ("li", "11:00 2027 promotional calendar"),
        ("li", "13:00 Lunch (Kestrel cafeteria)"), ("li", "14:00 Shelf-space proposal, Midwest stores"),
        ("li", "19:30 Dinner - Harbor & Vine (Dana Okafor + 3 from Kestrel Foods)")])


def policy_pdf(path):
    blocks = [
        ("title", "Travel & Expense Policy 2026"),
        ("p", "Fenwick & Hale Inc. - Finance. Applies to all employees from 1 January 2026. Questions: finance@fenwickhale.example"),
        ("h", "1. Receipts"),
        ("p", "An itemized receipt is required for every expense line of USD 25.00 or more. Lines under USD 25.00 do not need "
              "a receipt."),
        ("h", "2. The line must match the receipt"),
        ("p", "The date and the amount of each line must match its receipt. An employee may claim less than the receipt total "
              "only to remove non-reimbursable items (section 5) and should say so in the line description. A line that claims "
              "more than the receipt, or whose date differs from the receipt, is not accepted."),
        ("h", "3. Meals"),
        ("p", "Business meals are reimbursed up to USD 60.00 per attendee, including tax and tip. Record the number of attendees "
              "(including yourself) on the line."),
        ("h", "4. Lodging"),
        ("p", "Room rate up to USD 250 per night before taxes and fees; up to USD 350 per night in New York, San Francisco and "
              "London. Taxes and mandatory city fees are reimbursed in full."),
        ("h", "5. Not reimbursable"),
        ("li", "Alcohol of any kind (wine, beer, spirits)."), ("li", "Minibar, in-room movies, laundry for stays under 5 nights."),
        ("li", "Personal items, traffic and parking fines, upgrades bought by the traveller."),
        ("h", "6. Air travel"),
        ("p", "Economy class. Business class only with written pre-approval of a Vice President; the pre-approval reference must "
              "be recorded on the report."),
        ("h", "7. Deadline"),
        ("p", "Submit expenses within 60 days of the expense date. Lines older than 60 days at submission are not reimbursed."),
        ("h", "8. Ground transport and mileage"),
        ("p", "Taxis, ride-share and public transport at actual cost. Rental cars: compact or midsize. Private car mileage "
              "USD 0.67 per mile with a route description."),
        ("h", "9. Approver duties"),
        ("p", "Approvers check every line against its receipt. Approve a report only if every line complies with this policy. "
              "Otherwise reject the whole report with a comment that names the line and what is wrong, so the employee can "
              "correct it and resubmit. Approvers cannot approve their own reports."),
    ]
    lib_w.doc_pdf(path, blocks, header="Fenwick & Hale · Finance · Policy FIN-07", footer="Fenwick_TE_Policy_2026 · rev. 3")


def build(out):
    os.makedirs(out, exist_ok=True)
    rng = random.Random(20261022)
    lib_w.copy_app(HERE, out, "app_w2.py")
    con, app = lib_w.fresh_db(HERE, "app_w2.py", f"{out}/seed.db")
    for uid, user, name, dept, title, mgr in USERS:
        con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)", (uid, user, PASSWORD if uid == 1 else "", name,
                    f"{user}@fenwickhale.example", dept, title, mgr, int(uid == 1)))
    mgr = {u[0]: u[5] for u in USERS}

    def add_receipt(fname, data, ctype, when):
        import hashlib
        cur = con.execute("INSERT INTO receipts (filename,ctype,size,md5,data,uploaded) VALUES (?,?,?,?,?,?)",
                          (fname, ctype, len(data), hashlib.md5(data).hexdigest(), data, when))
        return cur.lastrowid

    def add_report(rid, emp, submitted, status, title, purpose, pre, decided=None, comment=""):
        created = (day(submitted) - dt.timedelta(days=1)).isoformat() + " 16:20:00"
        con.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, emp, title, purpose, pre, status, mgr[emp], created, submitted, decided,
                     mgr[emp] if decided else None, comment))
        con.execute("INSERT INTO events (report_id,user_id,ts,action,detail) VALUES (?,?,?,?,?)", (rid, emp, created, "created", title))
        con.execute("INSERT INTO events (report_id,user_id,ts,action,detail) VALUES (?,?,?,?,?)",
                    (rid, emp, submitted + " 09:05:00", "submitted", ""))
        if decided:
            con.execute("INSERT INTO events (report_id,user_id,ts,action,detail) VALUES (?,?,?,?,?)",
                        (rid, mgr[emp], decided, "approved" if status in ("Approved", "Paid") else "rejected", comment))

    for rid, emp, sub, status, title, kinds, comment in HIST:
        decided = None
        if status != "Submitted":
            dd = min(day(sub) + dt.timedelta(days=rng.randint(1, 3)), dt.date(2026, 9, 30) if sub < "2026-10" else dt.date(2026, 10, 14))
            decided = f"{dd.isoformat()} {rng.randint(9, 17):02d}:{rng.randint(0, 59):02d}:00"
        add_report(rid, emp, sub, status, title, "", "", decided, comment)
        for k in kinds:
            (when, cat, merchant, amount, att, desc), rec = hist_line(rng, rid, k, sub)
            rcid = add_receipt(f"receipt_{rid}_{merchant.split()[0].lower().strip(',.#')}.jpg", rec[0], rec[1], sub) if rec else None
            con.execute("INSERT INTO lines (report_id,date,category,merchant,amount,attendees,description,receipt_id,created) "
                        "VALUES (?,?,?,?,?,?,?,?,?)", (rid, when, cat, merchant, amount, att, desc, rcid, sub))
    recs = pending_receipts()
    for rid, (emp, sub, title, purpose, pre, lines, _, _) in PENDING.items():
        add_report(rid, emp, sub, "Submitted", title, purpose, pre)
        for i, (when, cat, merchant, amount, att, desc, has) in enumerate(lines, 1):
            rcid = add_receipt(*recs[(rid, i)], sub) if has else None
            con.execute("INSERT INTO lines (report_id,date,category,merchant,amount,attendees,description,receipt_id,created) "
                        "VALUES (?,?,?,?,?,?,?,?,?)", (rid, when, cat, merchant, amount, att, desc, rcid, sub))
    con.commit()
    seed = {str(r[0]): {"status": r[1], "decided": r[2]} for r in con.execute("SELECT id, status, decided FROM reports")}
    approved_oct_mkt = sorted(r[0] for r in con.execute(
        "SELECT r.id FROM reports r JOIN users e ON e.id=r.employee_id WHERE r.status='Approved' "
        "AND substr(r.submitted,1,7)='2026-10' AND e.department='Marketing'"))
    max_report = con.execute("SELECT MAX(id) FROM reports").fetchone()[0]
    con.close()
    policy_pdf(f"{out}/Fenwick_TE_Policy_2026.pdf")
    trip_files(f"{out}/Downloads")
    for ln in B_LINES:
        ln["md5"] = lib_w.md5(f"{out}/Downloads/{ln['file']}")
    json.dump({"port": 8102, "user": "dana.okafor", "password": PASSWORD, "dana_id": 1,
               "pending": {str(k): {"decision": v[6], "reason": v[7], "employee": NAMES[v[0]], "title": v[2]} for k, v in PENDING.items()},
               "seed": seed, "seed_max_report": max_report, "seed_approved_oct_marketing": approved_oct_mkt,
               "b_lines": B_LINES, "b_total": round(sum(x["amount"] for x in B_LINES), 2),
               "dinner_full": DINNER_FULL, "dinner_wine": DINNER_WINE,
               "downloads": sorted(os.listdir(f"{out}/Downloads")),
               "summary_path": "Documents/approvals_2026-10-22.txt", "csv_path": "Documents/marketing_approved_oct2026.csv"},
              open(f"{out}/expected.json", "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/w2_out")
