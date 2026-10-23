"""X1 - month-end close at Harbour & Pine Coffee Roasters: bank reconciliation vs the management report.

build(out_dir) writes:
  app_x1.py                      Ledgerline web app (copied)
  ledgerline_seed.db             seeded sqlite db (invoices Jul-Oct 2026, receipts up to 1 Sep, two old board packs)
  uploads/1_*.pdf, 2_*.pdf       the July/August board-pack PDFs referenced by the db
  thunderbird-profile.tar.gz     Sam Whitaker's offline mailbox (scanned bank statement, Priya's template, Tom's request)
  expected.json                  ground truth (host only)
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import random
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_x as X  # noqa: E402
from lib_thunderbird import make_profile  # noqa: E402

ME = ("Sam Whitaker", "sam.whitaker@harbourpine.co.uk")
TOM = ("Tom Reyes", "tom.reyes@harbourpine.co.uk")
PRIYA = ("Priya Shah", "priya@shahcole.co.uk")
GUEST_DIR = "/home/user/.local/share/intranet/ledgerline"
CH_W, CH_O, CH_T = "Wholesale", "Online shop", "Training & equipment"
CHANNELS = [CH_W, CH_O, CH_T]
BUSINESS_DATE = "2026-10-02"
TZ = dt.timezone(dt.timedelta(hours=1))

# id: (name, default channel, contact, email, phone, terms, address)
CUSTOMERS = {
    1: ("Blue Door Café", CH_W, "Hannah Lowe", "hannah@bluedoorcafe.co.uk", "01326 210 448", 30, "14 Church Street, Falmouth TR11 3EG"),
    2: ("Kestrel Bakery Ltd", CH_W, "Owen Pritchard", "accounts@kestrelbakery.co.uk", "01872 553 120", 30, "Unit 2, Kenwyn Trading Estate, Truro TR1 3QE"),
    3: ("Marlow Deli & Co", CH_W, "Giulia Marlow", "giulia@marlowdeli.co.uk", "01326 377 902", 30, "3 Arwenack Street, Falmouth TR11 3JA"),
    4: ("Northgate Offices Ltd", CH_W, "Raj Patel", "facilities@northgateoffices.co.uk", "01872 410 300", 30, "Northgate House, Lemon Street, Truro TR1 2LS"),
    5: ("The Copper Kettle", CH_W, "Siobhan Kerr", "siobhan@copperkettle-penryn.co.uk", "01326 371 554", 30, "22 Lower Market Street, Penryn TR10 8BG"),
    6: ("Fieldfare Hotel", CH_W, "Laura Benson", "purchasing@fieldfarehotel.co.uk", "01326 312 600", 30, "Cliff Road, Falmouth TR11 4NZ"),
    7: ("Saltmarsh Bistro", CH_W, "Ed Carver", "ed@saltmarshbistro.co.uk", "01326 250 117", 30, "The Quay, Flushing TR11 5TY"),
    8: ("Greenway Co-operative", CH_W, "Accounts team", "accounts@greenwaycoop.org.uk", "01209 615 220", 30, "Trevithick Road, Camborne TR14 8LQ"),
    9: ("Oak & Anchor", CH_W, "Pete Doyle", "pete@oakandanchor.pub", "01326 340 019", 30, "Quay Hill, Penryn TR10 8EL"),
    10: ("Wren Books Café", CH_W, "Amira Wren", "amira@wrenbooks.co.uk", "01326 318 077", 30, "9 High Street, Falmouth TR11 2AD"),
    11: ("Larkspur Studios", CH_W, "Nell Hart", "ap@larkspurstudios.co.uk", "01872 262 811", 30, "Old Bakery Studios, Truro TR1 2RY"),
    12: ("Shopify Payments", CH_O, "Online shop payouts", "payouts@shopify.com", "-", 14, "Shopify International Ltd, Dublin"),
    13: ("Pinecrest College", CH_T, "Dr Alan Moss", "finance@pinecrest.ac.uk", "01872 267 000", 30, "College Road, Truro TR1 3XX"),
    14: ("Harrow Lane Café", CH_W, "Becky Harrow", "becky@harrowlanecafe.co.uk", "01209 711 404", 30, "41 Harrow Lane, Redruth TR15 2LP"),
    15: ("Moss & Stone Coffee", CH_T, "Kit Stone", "kit@mossandstone.coffee", "01736 330 129", 30, "6 Market Jew Street, Penzance TR18 2HN"),
}
WHOLESALE = [("House Espresso Blend 1kg", "17.50"), ("Harbour Breakfast Blend 1kg", "15.00"),
             ("Single Origin Ethiopia Guji 1kg", "24.00"), ("Single Origin Colombia Huila 1kg", "22.00"),
             ("Swiss Water Decaf 1kg", "21.00"), ("Cold Brew Concentrate 5L", "38.00"), ("Chai Syrup 1L", "9.50")]
TRAINING = [("Barista training - half day", "180.00"), ("Barista training - full day", "320.00"),
            ("Grinder service & burr replacement", "145.00"), ("Espresso machine annual service", "260.00"),
            ("Milk jug & tamper set", "42.00")]


def D(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def vat(net: Decimal) -> Decimal:
    return (net * Decimal("0.2")).quantize(Decimal("0.01"), ROUND_HALF_UP)


def day(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


# Invoices with a fixed role in the story: number -> (issue date, customer id, channel, lines, reference, note)
FIXED = {
    371: ("2026-07-01", 12, CH_O, [("Online shop sales 16-30 Jun 2026 (Shopify payout)", 1, "2391.40")], "", ""),
    376: ("2026-07-10", 4, CH_W, [("Office coffee service - July 2026 (2 floors)", 2, "650.00")], "PO NG-0726", ""),
    377: ("2026-07-10", 11, CH_W, [("Office coffee service - July 2026", 2, "650.00")], "", ""),
    382: ("2026-07-16", 12, CH_O, [("Online shop sales 1-15 Jul 2026 (Shopify payout)", 1, "2614.75")], "", ""),
    386: ("2026-07-21", 7, CH_W, [("House Espresso Blend 1kg", 12, "17.50"), ("Swiss Water Decaf 1kg", 4, "21.00")], "", ""),
    394: ("2026-08-01", 12, CH_O, [("Online shop sales 16-31 Jul 2026 (Shopify payout)", 1, "2287.90")], "", ""),
    398: ("2026-08-04", 9, CH_W, [("House Espresso Blend 1kg", 12, "17.50"), ("Chai Syrup 1L", 15, "10.00")], "", ""),
    399: ("2026-08-06", 10, CH_W, [("Harbour Breakfast Blend 1kg", 14, "15.00"), ("Cold Brew Concentrate 5L", 2, "38.00")], "", ""),
    400: ("2026-08-06", 10, CH_W, [("Harbour Breakfast Blend 1kg", 14, "15.00"), ("Cold Brew Concentrate 5L", 2, "38.00")], "",
          "Duplicate of INV-2026-0399 - voided by Priya Shah 24 Sep 2026."),
    402: ("2026-08-07", 1, CH_W, [("House Espresso Blend 1kg", 20, "17.50"), ("Single Origin Colombia Huila 1kg", 4, "25.00")], "Standing order", ""),
    405: ("2026-08-10", 11, CH_W, [("Office coffee service - August 2026", 2, "650.00")], "", ""),
    409: ("2026-08-13", 3, CH_W, [("Single Origin Ethiopia Guji 1kg", 15, "24.00"), ("House Espresso Blend 1kg", 23, "17.50"),
                                  ("Sample pack - autumn filter", 1, "6.50")], "", ""),
    411: ("2026-08-14", 4, CH_W, [("Office coffee service - August 2026 (2 floors)", 2, "650.00")], "PO NG-0826", ""),
    412: ("2026-08-17", 12, CH_O, [("Online shop sales 1-15 Aug 2026 (Shopify payout)", 1, "2508.30")], "", ""),
    415: ("2026-08-24", 3, CH_W, [("House Espresso Blend 1kg", 20, "17.50"), ("Swiss Water Decaf 1kg", 12, "21.00"),
                                  ("Chai Syrup 1L", 3, "11.00")], "", ""),
    418: ("2026-09-01", 12, CH_O, [("Online shop sales 16-31 Aug 2026 (Shopify payout)", 1, "2848.85")], "", ""),
    420: ("2026-09-02", 1, CH_W, [("House Espresso Blend 1kg", 20, "17.50"), ("Single Origin Colombia Huila 1kg", 4, "25.00")], "Standing order", ""),
    421: ("2026-09-03", 5, CH_W, [("House Espresso Blend 1kg", 20, "17.50"), ("Harbour Breakfast Blend 1kg", 10, "15.00"),
                                  ("Grinder call-out (visit 1 Sep)", 1, "100.00")], "", ""),
    425: ("2026-09-07", 6, CH_W, [("House Espresso Blend 1kg", 40, "17.50"), ("Single Origin Ethiopia Guji 1kg", 25, "24.00"),
                                  ("Swiss Water Decaf 1kg", 10, "21.00"), ("Cold Brew Concentrate 5L", 4, "37.50")], "Wedding season", ""),
    427: ("2026-09-09", 4, CH_W, [("Office coffee service - September 2026 (1 floor)", 1, "650.00")], "PO NG-0926", ""),
    428: ("2026-09-10", 11, CH_W, [("Office coffee service - September 2026", 2, "650.00")], "", ""),
    430: ("2026-09-14", 8, CH_W, [("Harbour Breakfast Blend 1kg", 12, "15.00"), ("Single Origin Ethiopia Guji 1kg", 6, "24.00")], "", ""),
    431: ("2026-09-16", 12, CH_O, [("Online shop sales 1-15 Sep 2026 (Shopify payout)", 1, "2420.15")], "", ""),
    433: ("2026-09-17", 7, CH_W, [("House Espresso Blend 1kg", 30, "17.50"), ("Single Origin Colombia Huila 1kg", 18, "22.00"),
                                  ("Chai Syrup 1L", 2, "4.00")], "", ""),
    434: ("2026-09-17", 2, CH_W, [("House Espresso Blend 1kg", 36, "17.50"), ("Harbour Breakfast Blend 1kg", 25, "15.00"),
                                  ("Delivery charge", 1, "5.00")], "PO KB-3310", ""),
    440: ("2026-09-29", 2, CH_W, [("Harbour Breakfast Blend 1kg", 22, "15.00")], "PO KB-3342", ""),
    441: ("2026-10-01", 12, CH_O, [("Online shop sales 16-30 Sep 2026 (Shopify payout)", 1, "2733.60")], "", ""),
}
# numbers that must stay unpaid in the seed (open items of the story)
OPEN_FIXED = {386, 402, 405, 409, 411, 415, 418, 420, 421, 425, 427, 428, 430, 431, 433, 434, 440, 441}

# September statement, money in: (date, description, invoice numbers, status, comment)
CREDITS = [
    ("2026-09-01", "FPI OAK AND ANCHOR INV0398", [398], "Already posted", ""),
    ("2026-09-03", "FPI BLUE DOOR CAFE INV-2026-0402", [402], "Posted", ""),
    ("2026-09-09", "FPI MARLOW DELI & CO 0409/0415", [409, 415], "Posted", ""),
    ("2026-09-12", "SHOPIFY PAYMENTS PAYOUT P8841203", [418], "Posted", ""),
    ("2026-09-15", "BGC NORTHGATE OFFICES LTD", [411], "Posted", ""),
    ("2026-09-18", "FPI THE COPPER KETTLE INV 0421", [421], "Posted", "short payment"),
    ("2026-09-22", "HMRC VAT REPAYMENT 0626", [], "Unmatched", "VAT repayment"),
    ("2026-09-23", "FPI J MORGAN COURSE DEP", [], "Unmatched", "course deposit, no invoice"),
    ("2026-09-24", "FPI FIELDFARE HOTEL INV-2026-0425", [425], "Posted", ""),
    ("2026-09-25", "FPI KESTREL BAKERY LTD REF INV0433", [434], "Posted", "customer quoted 0433"),
    ("2026-09-28", "BGC GREENWAY COOP REF HPCR", [430], "Posted", ""),
    ("2026-09-30", "SHOPIFY PAYMENTS PAYOUT P8853377", [431], "Posted", ""),
]
CREDIT_FIXED_AMOUNT = {"HMRC VAT REPAYMENT 0626": Decimal("2145.30"), "FPI J MORGAN COURSE DEP": Decimal("250.00"),
                       "FPI THE COPPER KETTLE INV 0421": Decimal("600.00")}
DEBITS = [
    ("2026-09-01", "DD NORTHSHORE PROPERTY LTD RENT", "2450.00"), ("2026-09-02", "FPO CAFE IMPORTS LTD INV 77120", "6820.50"),
    ("2026-09-04", "DD SSE ENERGY SUPPLY", "412.37"), ("2026-09-05", "CHARGES AUG 2026", "24.50"),
    ("2026-09-08", "FPO ROASTWORKS ENGINEERING", "580.00"), ("2026-09-10", "DD HMRC PAYE CUMBERNAULD", "1236.40"),
    ("2026-09-11", "FPO PACKFORM BAGS LTD", "914.40"), ("2026-09-15", "DD BT BUSINESS", "64.80"),
    ("2026-09-16", "FPO DPD GROUP UK", "322.18"), ("2026-09-19", "CARD 4471 SCREWFIX TRURO", "86.94"),
    ("2026-09-25", "BACS SALARIES SEP 2026", "9850.00"), ("2026-09-29", "DD ALPHABET VAN LEASE", "389.00"),
    ("2026-09-30", "CHARGES SEP 2026", "26.00"),
]
OPENING = Decimal("21418.62")


def make_invoices(rng: random.Random):
    anchors = {n: day(v[0]) for n, v in FIXED.items()}
    anchors.update({393: day("2026-07-31"), 417: day("2026-08-31"), 439: day("2026-09-28"), 442: day("2026-10-02")})
    keys = sorted(anchors)
    dates = dict(anchors)
    for a, b in zip(keys, keys[1:]):
        gap = list(range(a + 1, b))
        span = (anchors[b] - anchors[a]).days
        ds = sorted(anchors[a] + dt.timedelta(days=rng.randint(0, span)) for _ in gap)
        dates.update(zip(gap, ds))
    regular = [1, 1, 2, 3, 5, 6, 6, 7, 8, 9, 10, 14, 14, 3, 1, 6, 9]
    invoices = []
    for n in range(371, 443):
        issued = dates[n]
        if n in FIXED:
            _, cid, ch, lines, ref, note = FIXED[n]
            lines = [(d, q, D(p)) for d, q, p in lines]
        else:
            ref, note = "", ""
            if rng.random() < 0.3:
                cid = rng.choice([13, 15, 15, 14, 6, 5])
                ch = CH_T
                lines = [(d, rng.choice([1, 1, 2]), D(p)) for d, p in rng.sample(TRAINING, rng.choice([1, 1, 2]))]
            else:
                cid = rng.choice(regular)
                ch = CH_W
                lines = [(d, rng.choice([4, 6, 8, 10, 12, 15, 20, 24]), D(p)) for d, p in rng.sample(WHOLESALE, rng.choice([1, 2, 2, 3]))]
        net = sum((D(Decimal(str(q)) * p) for _, q, p in lines), Decimal("0"))
        terms = CUSTOMERS[cid][5]
        invoices.append({"n": n, "number": f"INV-2026-{n:04d}", "cid": cid, "issue": issued, "due": issued + dt.timedelta(days=terms),
                         "channel": ch, "lines": lines, "net": net, "vat": vat(net), "gross": net + vat(net),
                         "ref": ref, "note": note, "void": n == 400})
    return invoices


def seed_payments(rng: random.Random, invoices):
    pays = []
    for inv in invoices:
        if inv["void"] or inv["n"] in OPEN_FIXED or inv["issue"] >= day("2026-09-01"):
            continue
        if inv["n"] == 398:
            pays.append((inv, day("2026-09-01"), inv["gross"], "tom", "2026-09-01 10:14:07", "FPI OAK AND ANCHOR INV0398"))
            continue
        lag = rng.randint(6, 28)
        when = inv["issue"] + dt.timedelta(days=lag)
        if when > day("2026-08-31"):
            if inv["issue"].month == 8 and rng.random() < 0.6:
                continue  # still open: these become the ordinary overdue items
            when = day("2026-08-31") - dt.timedelta(days=rng.randint(0, 3))
            if when <= inv["issue"]:
                continue
        pays.append((inv, when, inv["gross"], "sam", f"{when + dt.timedelta(days=rng.randint(0, 2))} 1{rng.randint(0, 7)}:{rng.randint(10, 59)}:0{rng.randint(0, 9)}",
                     f"FPI {CUSTOMERS[inv['cid']][0].upper()[:18]}"))
    return pays


def report_numbers(invoices, include_void=False):
    rev = {m: {c: Decimal("0") for c in CHANNELS} for m in ("2026-07", "2026-08", "2026-09")}
    count = {m: 0 for m in rev}
    cust = {}
    for inv in invoices:
        m = inv["issue"].isoformat()[:7]
        if m not in rev or (inv["void"] and not include_void):
            continue
        rev[m][inv["channel"]] += inv["net"]
        count[m] += 1
        cust[inv["cid"]] = cust.get(inv["cid"], Decimal("0")) + inv["net"]
    return rev, count, cust


# ---------------------------------------------------------------- documents
def statement_pdf(path, credits, debits):
    """Two-page scanned paper statement (image-only PDF)."""
    lines = sorted([(c["date"], c["desc"], None, c["amount"]) for c in credits] +
                   [(d, desc, Decimal(a), None) for d, desc, a in debits], key=lambda x: (x[0], x[3] is None))
    bal = OPENING
    rows = []
    for date, desc, out, inn in lines:
        bal += (inn or 0) - (out or 0)
        rows.append((dt.date.fromisoformat(date).strftime("%d %b"), desc, f"{out:,.2f}" if out else "", f"{inn:,.2f}" if inn else "", f"{bal:,.2f}"))
    total_in = sum(c["amount"] for c in credits)
    total_out = sum(Decimal(a) for _, _, a in debits)
    assert bal == OPENING + total_in - total_out and min(Decimal(r[4].replace(",", "")) for r in rows) > 0
    cols = [("Date", 110, "l"), ("Description", 520, "l"), ("Paid out", 165, "r"), ("Paid in", 165, "r"), ("Balance", 165, "r")]
    pages = []
    for k, chunk in enumerate((rows[:14], rows[14:])):
        p = X.Page()
        p.d.rectangle((70, 70, 350, 150), fill=(18, 62, 96))
        p.text(92, 88, "NORTHSHORE", size=34, bold=True, fill=(255, 255, 255))
        p.text(92, 126, "B A N K", size=16, fill=(200, 220, 235))
        p.text(1170, 80, "Business Current Account", size=26, bold=True, anchor="ra")
        p.text(1170, 120, f"Statement 112 · page {k + 1} of 2", size=20, anchor="ra")
        if k == 0:
            p.lines(90, 200, ["HARBOUR & PINE COFFEE ROASTERS LTD", "UNIT 4 QUAYSIDE WORKS", "FALMOUTH", "TR11 2AB"], size=22)
            p.lines(720, 200, ["Sort code   40-22-17", "Account     61844471", "Period      01 Sep 2026 - 30 Sep 2026",
                               "Branch      Falmouth, 31 Market St"], size=21, mono=True)
            p.rect((90, 380, 1150, 520), outline=(18, 62, 96), width=3)
            p.text(110, 395, "Your account summary", size=24, bold=True, fill=(18, 62, 96))
            summary = [("Opening balance 01 Sep", OPENING), ("Money in", total_in), ("Money out", total_out), ("Closing balance 30 Sep", bal)]
            for i, (lbl, v) in enumerate(summary):
                x = 110 + (i % 2) * 520
                y = 440 + (i // 2) * 36
                p.text(x, y, lbl, size=21)
                p.text(x + 470, y, f"£{v:,.2f}", size=21, bold=True, anchor="ra")
            y = p.table(90, 560, cols, [("01 Sep", "BALANCE BROUGHT FORWARD", "", "", f"{OPENING:,.2f}")] + chunk, size=19, row_h=36)
        else:
            y = p.table(90, 200, cols, chunk + [("30 Sep", "BALANCE CARRIED FORWARD", "", "", f"{bal:,.2f}")], size=19, row_h=36)
            p.lines(90, y + 40, ["FPI = Faster Payment in   FPO = Faster Payment out   BGC = Bank Giro Credit   DD = Direct Debit",
                                 "Please check this statement carefully and tell us about any entry you do not recognise."], size=17,
                    fill=(90, 90, 90))
        p.text(620, 1690, "Northshore Bank plc is authorised by the Prudential Regulation Authority. Registered in England No. 2065.",
               size=14, fill=(110, 110, 110), anchor="ma")
        pages.append(p)
    X.scanned_pdf(path, pages, seed=11)
    return {"opening": float(OPENING), "paid_in": float(total_in), "paid_out": float(total_out), "closing": float(bal)}


def rec_template(path, filled=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "Bank rec"
    thin = Side(style="thin", color="999999")
    ws["A1"] = "Harbour & Pine Coffee Roasters Ltd - bank reconciliation"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Account: Northshore Bank business current account 40-22-17 / 61844471"
    ws["A3"] = "Period:"
    ws["B3"] = filled["period"] if filled else ""
    ws["A5"] = "Statement summary"
    ws["A5"].font = Font(bold=True)
    for i, lbl in enumerate(["Opening balance", "Total paid in", "Total paid out", "Closing balance"]):
        ws.cell(6 + i, 1, lbl)
        c = ws.cell(6 + i, 3, filled["summary"][i] if filled else None)
        c.number_format = "#,##0.00"
        c.border = Border(bottom=thin)
    heads = ["Date", "Bank description", "Amount (£)", "Invoice(s)", "Status", "Comment"]
    for j, h in enumerate(heads, 1):
        c = ws.cell(11, j, h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E8DFD0")
    ws["A10"] = "Money in - one line per credit on the statement"
    ws["A10"].font = Font(bold=True)
    for r, row in enumerate((filled or {}).get("rows", []), 12):
        for j, v in enumerate(row, 1):
            c = ws.cell(r, j, v)
            if j == 3:
                c.number_format = "#,##0.00"
    ws["A28"] = "Status key: Posted = receipt recorded in Ledgerline this month; Already posted = it was already in Ledgerline;"
    ws["A29"] = "Unmatched = not a payment of one of our sales invoices, or no invoice found (explain in Comment)."
    for a in ("A28", "A29"):
        ws[a].font = Font(italic=True, color="666666")
        ws[a].alignment = Alignment(wrap_text=False)
    for col, w in zip("ABCDEF", (12, 40, 14, 22, 16, 40)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def chart_png(rev, months, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=110)
    w = 0.26
    for k, ch in enumerate(CHANNELS):
        ax.bar([i + (k - 1) * w for i in range(len(months))], [float(rev[m][ch]) for m in months], w, label=ch)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([dt.date.fromisoformat(m + "-01").strftime("%B") for m in months])
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=.3)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def august_pack_pdf(path, rev, cust):
    """Last month's report as Sam sent it (figures as they were on 2 Sep, i.e. before INV-2026-0400 was voided)."""
    import fitz
    months = ["2026-07", "2026-08"]
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text((56, 70), "Management report - August 2026", fontsize=18, fontname="hebo")
    pg.insert_text((56, 92), "Harbour & Pine Coffee Roasters Ltd · prepared by Sam Whitaker, 2 September 2026", fontsize=9, fontname="helv")
    y = 130
    pg.insert_text((56, y), "1. Net revenue by channel (ex VAT)", fontsize=12, fontname="hebo")
    y += 22
    for row in [["Channel", "July", "August"]] + [[c] + [f"£{rev[m][c]:,.2f}" for m in months] for c in CHANNELS] + \
            [["Total"] + [f"£{sum(rev[m].values()):,.2f}" for m in months]]:
        for x, s in zip((60, 260, 380), row):
            pg.insert_text((x, y), s, fontsize=10, fontname="hebo" if row[0] in ("Channel", "Total") else "helv")
        y += 16
    y += 10
    pg.insert_image(fitz.Rect(56, y, 540, y + 240), stream=chart_png(rev, months, "Net revenue by channel"))
    y += 262
    a, b = sum(rev["2026-07"].values()), sum(rev["2026-08"].values())
    pg.insert_text((56, y), f"2. August net revenue was £{b:,.2f}, {(b - a) / a * 100:+.1f}% on July.", fontsize=10, fontname="helv")
    y += 24
    top = sorted(((v, CUSTOMERS[c][0]) for c, v in cust.items() if c != 12), reverse=True)[:3]
    pg.insert_text((56, y), "3. Top customers so far this quarter: " + "; ".join(f"{n} £{v:,.2f}" for v, n in top) + ".", fontsize=10, fontname="helv")
    doc.set_metadata({"title": "Management report - August 2026", "creator": "Writer", "producer": "LibreOffice 7.3"})
    doc.save(path, garbage=3, deflate=True)


def july_pack_pdf(path):
    import fitz
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text((56, 70), "Management report - July 2026", fontsize=18, fontname="hebo")
    pg.insert_text((56, 100), "First month on Ledgerline. Figures in the attached schedule.", fontsize=10, fontname="helv")
    doc.save(path, garbage=3, deflate=True)


# ---------------------------------------------------------------- mailbox
def mailbox(d, st_pdf, template_xlsx, aug_pdf, aug_rec_xlsx, credits):
    when = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=TZ)  # noqa: E731
    host = "harbourpine.co.uk"
    ids = {}

    def mid(key, dom=host):
        ids[key] = f"<x1.{key}.{len(ids) + 1:02d}@{dom}>"
        return ids[key]

    rd = lambda p: open(p, "rb").read()  # noqa: E731
    sh1, sh2 = (c["amount"] for c in credits if c["desc"].startswith("SHOPIFY"))
    inbox = [
        (X.mail(("Caffeine Trade Weekly", "news@caffeinetrade.co.uk"), [ME], "Green coffee prices: Colombia up 9% in a month",
                "This week: Colombian washed arabica jumps again, the UK roaster survey results, and why oat milk prices "
                "are finally falling.\n\nRead online | Unsubscribe", when("2026-09-14T07:30:00"), mid("news1", "caffeinetrade.co.uk")), False),
        (X.mail(("Siobhan Kerr", "siobhan@copperkettle-penryn.co.uk"), [ME], "Invoice 0421 - grinder call-out",
                "Hi Sam,\n\nThe grinder call-out on invoice INV-2026-0421 never happened - we cancelled the visit on the 1st "
                "because our own engineer fixed it. So we'll pay for the coffee only, that's £600.00 (the £100 + VAT for the "
                "call-out comes off).\n\nCould you send us a credit note for the £120.00?\n\nThanks,\nSiobhan\nThe Copper Kettle, Penryn",
                when("2026-09-15T11:02:00"), mid("copper", "copperkettle-penryn.co.uk")), False),
        (X.mail(("Shopify", "payouts@shopify.com"), [ME], f"Your payout of £{sh1:,.2f} is on its way",
                f"Hi Harbour & Pine,\n\nA payout of £{sh1:,.2f} for orders from 16-31 Aug 2026 has been sent to your bank "
                "account ending 4471 and should arrive within 3 business days.\n\nPayout ID P8841203\n\nShopify",
                when("2026-09-10T06:12:00"), mid("shopify1", "shopify.com")), False),
        (X.mail(("Jess Morgan", "jess.morgan.coffee@gmail.com"), [ME], "Barista course deposit",
                "Hi Sam,\n\nI've just transferred the £250.00 deposit for the full-day barista course on 14 November "
                "(reference J MORGAN COURSE DEP). Could you send me a receipt or an invoice for the balance when you get a chance?\n\n"
                "Thanks!\nJess", when("2026-09-23T19:41:00"), mid("morgan", "gmail.com")), True),
        (X.mail(("Owen Pritchard", "accounts@kestrelbakery.co.uk"), [ME], "Remittance advice - Kestrel Bakery Ltd",
                "Dear Harbour & Pine,\n\nPlease note we have today paid £1,212.00 by Faster Payment in settlement of your invoice "
                "INV-2026-0434 (our PO KB-3310).\n\nRegards,\nOwen Pritchard\nAccounts, Kestrel Bakery Ltd",
                when("2026-09-25T10:20:00"), mid("kestrel", "kestrelbakery.co.uk")), True),
        (X.mail(("Café Imports Ltd", "sales@cafeimports.co.uk"), [ME], "Shipment ETA - Guji lot 4471",
                "Hello,\n\nYour next lot (Ethiopia Guji, 18 bags) is due at Felixstowe on 9 October, delivery to Falmouth "
                "around the 14th.\n\nBest regards,\nCafé Imports", when("2026-09-26T09:00:00"), mid("imports", "cafeimports.co.uk")), True),
        (X.mail(("Nell Hart", "ap@larkspurstudios.co.uk"), [ME], "Re: Overdue invoice INV-2026-0405",
                "Hi Sam,\n\nApologies - 0405 got stuck in approvals. It's in our next payment run on 7 October together with "
                "September's invoice.\n\nNell", when("2026-09-29T14:15:00"), mid("larkspur", "larkspurstudios.co.uk")), True),
        (X.mail(PRIYA, [ME], "September close - bank reconciliation",
                "Hi Sam,\n\nHere's the bank reconciliation template for September (attached). Could you:\n\n"
                "- post every customer receipt on the September statement against its invoice in Ledgerline, dated the day "
                "the money reached the bank;\n"
                "- fill in the statement summary and one line per money-in item on the statement, with the invoice number(s) "
                "and a status: 'Posted' if you posted it now, 'Already posted' if it was already in Ledgerline, or "
                "'Unmatched' if it isn't a payment of one of our sales invoices (add a short comment);\n"
                "- if a customer has short-paid, post what they actually paid and tell me what is still outstanding so I "
                "can chase it or raise a credit note.\n\n"
                "The Q2 VAT repayment from HMRC should have landed in September too - that's not a sales receipt, so it "
                "doesn't go into Ledgerline; just list it as Unmatched.\n\n"
                "Reply to this email with the completed file when you're done.\n\nThanks,\nPriya\n\n--\nPriya Shah ACA\n"
                "Shah & Cole Accountants, Truro", when("2026-09-30T16:40:00"), mid("priya", "shahcole.co.uk"),
                atts=[("Bank_Rec_Template.xlsx", rd(template_xlsx), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]), True),
        (X.mail(("Shopify", "payouts@shopify.com"), [ME], f"Your payout of £{sh2:,.2f} is on its way",
                f"Hi Harbour & Pine,\n\nA payout of £{sh2:,.2f} for orders from 1-15 Sep 2026 has been sent to your bank "
                "account ending 4471 and should arrive within 3 business days.\n\nPayout ID P8853377\n\nShopify",
                when("2026-09-28T06:12:00"), mid("shopify2", "shopify.com")), True),
        (X.mail(TOM, [ME], "September bank statement (scanned)",
                "Hi Sam,\n\nThe paper statement for September came this morning - scan attached. Can you do the bank rec for "
                "Priya this week?\n\nI already put the Oak & Anchor payment into Ledgerline on the 1st when it came in, the "
                "rest is all yours.\n\nTom", when("2026-10-01T09:12:00"), mid("statement"),
                atts=[("Northshore_Statement_Sep2026.pdf", rd(st_pdf), "application/pdf")]), True),
        (X.mail(("Amira Wren", "amira@wrenbooks.co.uk"), [ME], "Order for next week",
                "Hi Sam, could we have 10 x Harbour Breakfast and 2 x cold brew for Tuesday? Thanks, Amira",
                when("2026-10-01T12:30:00"), mid("wren", "wrenbooks.co.uk")), True),
        (X.mail(TOM, [ME], "September management pack",
                "Hi Sam,\n\nCan you put together the September management report for Thursday's directors' meeting? Same idea "
                "as August's, but this time it should cover the whole quarter:\n\n"
                "1. A table of net revenue (ex VAT) by channel - Wholesale, Online shop, Training & equipment - for July, "
                "August and September, with the monthly totals and the Q3 total. To the penny, please.\n"
                "2. A column chart of that table (months along the bottom, one bar per channel).\n"
                "3. How September's total net revenue compares with August's, as a % change (one decimal place).\n"
                "4. Our top three customers for Q3 by net revenue, with their Q3 totals. Leave out Shopify Payments - "
                "that's just the online shop payouts, not a customer.\n"
                "5. How many invoices we issued in September.\n\n"
                "Take everything from the Reports page in Ledgerline as it stands now - Priya voided a duplicate August "
                "invoice (0400) last week, so August will come out a bit lower than in last month's pack.\n\n"
                "Keep the numbers and the chart in a spreadsheet so I can play with them, and write the report itself in "
                "Writer. Put the PDF up in Ledgerline as the September board pack and send it back to me as a PDF.\n\n"
                "Cheers,\nTom", when("2026-10-01T17:05:00"), mid("pack")), True),
        (X.mail(("Ledgerline", "no-reply@ledgerline.app"), [ME], "Ledgerline: scheduled maintenance 10 Oct",
                "Ledgerline will be unavailable on Saturday 10 October 06:00-07:00 for an upgrade.",
                when("2026-10-02T07:00:00"), mid("maint", "ledgerline.app")), True),
    ]
    sent = [
        (X.mail(ME, [TOM], "Management report - August 2026",
                "Hi Tom,\n\nAugust's management report is attached (also uploaded to Ledgerline as the August board pack).\n\nSam",
                when("2026-09-02T15:20:00"), mid("augpack"), atts=[("Management_Report_2026-08.pdf", rd(aug_pdf), "application/pdf")]), False),
        (X.mail(ME, [PRIYA], "Re: August close - bank reconciliation",
                "Hi Priya,\n\nAugust bank rec attached. One unmatched item (Sumup refund), see comment.\n\nSam",
                when("2026-09-04T11:05:00"), mid("augrec"),
                atts=[("Bank_Rec_2026-08.xlsx", rd(aug_rec_xlsx), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]), False),
    ]
    from email.utils import parsedate_to_datetime
    folders = {"Inbox": [(m, parsedate_to_datetime(m["Date"]), unread) for m, unread in inbox],
               "Sent": [(m, parsedate_to_datetime(m["Date"]), False) for m, _ in sent]}
    make_profile(f"{d}/thunderbird-profile.tar.gz", ME, folders)
    return ids


def build(d):
    os.makedirs(f"{d}/uploads", exist_ok=True)
    X.copy_app("app_x1.py", d)
    rng = random.Random(61021)
    invoices = make_invoices(rng)
    by_n = {i["n"]: i for i in invoices}
    pays = seed_payments(rng, invoices)
    # ---- statement credits
    credits = []
    for date, desc, invs, status, comment in CREDITS:
        amount = CREDIT_FIXED_AMOUNT.get(desc, sum((by_n[n]["gross"] for n in invs), Decimal("0")))
        credits.append({"date": date, "desc": desc, "amount": amount, "invoices": invs, "status": status, "comment": comment})
    expected_pay = []
    for c in credits:
        if c["status"] != "Posted":
            continue
        for n in c["invoices"]:
            amt = c["amount"] if len(c["invoices"]) == 1 else by_n[n]["gross"]
            expected_pay.append({"invoice": f"INV-2026-{n:04d}", "date": c["date"], "amount": float(amt)})
    # sanity: story invariants
    assert len(expected_pay) == 10
    paid_seed = {p[0]["n"] for p in pays}
    assert not (paid_seed & OPEN_FIXED) and 398 in paid_seed
    for c in credits:
        if c["status"] == "Posted" and len(c["invoices"]) == 1:
            n = c["invoices"][0]
            same = [i for i in invoices if i["cid"] == by_n[n]["cid"] and i["n"] != n and i["gross"] == c["amount"]
                    and i["n"] not in paid_seed and not i["void"]]
            assert all(i["n"] == 420 for i in same), (n, [i["n"] for i in same])
    assert by_n[421]["gross"] - Decimal("600.00") == Decimal("120.00")
    assert by_n[434]["gross"] == Decimal("1212.00") and by_n[433]["gross"] != by_n[434]["gross"]
    assert by_n[405]["gross"] == by_n[411]["gross"] == Decimal("1560.00")
    amounts = [c["amount"] for c in credits]
    assert len(set(amounts)) == len(amounts)
    # ---- report figures (B)
    rev, count, cust = report_numbers(invoices)
    q3_cust = sorted(((v, CUSTOMERS[c][0]) for c, v in cust.items() if c != 12), reverse=True)
    assert q3_cust[0][0] - q3_cust[1][0] > 50 and q3_cust[1][0] - q3_cust[2][0] > 50 and q3_cust[2][0] - q3_cust[3][0] > 50, q3_cust[:4]
    tot = {m: sum(rev[m].values()) for m in rev}
    pct = (tot["2026-09"] - tot["2026-08"]) / tot["2026-08"] * 100
    rev_old, _, cust_old = report_numbers(invoices, include_void=True)
    # ---- documents
    st = statement_pdf(f"{d}/Northshore_Statement_Sep2026.pdf", credits, DEBITS)
    rec_template(f"{d}/Bank_Rec_Template.xlsx")
    rec_template(f"{d}/Bank_Rec_2026-08.xlsx", {"period": "August 2026", "summary": [18210.44, 31904.12, 28695.94, 21418.62], "rows": [
        ("03 Aug", "SHOPIFY PAYMENTS PAYOUT P8790012", 2745.48, "INV-2026-0382", "Posted", ""),
        ("12 Aug", "SUMUP REFUND 0725", 18.40, "", "Unmatched", "card terminal fee refund"),
        ("14 Aug", "FPI FIELDFARE HOTEL INV-2026-0379", 1566.00, "INV-2026-0379", "Posted", "")]})
    aug_pdf = f"{d}/uploads/2_Management_Report_2026-08.pdf"
    august_pack_pdf(aug_pdf, rev_old, {c: v for c, v in cust_old.items()})
    july_pack_pdf(f"{d}/uploads/1_Management_Report_2026-07.pdf")
    ids = mailbox(d, f"{d}/Northshore_Statement_Sep2026.pdf", f"{d}/Bank_Rec_Template.xlsx", aug_pdf,
                  f"{d}/Bank_Rec_2026-08.xlsx", credits)
    for f in ("Northshore_Statement_Sep2026.pdf", "Bank_Rec_Template.xlsx", "Bank_Rec_2026-08.xlsx"):
        os.remove(f"{d}/{f}")  # they only live inside the mailbox
    # ---- database
    rows = {"settings": [{"key": "business_date", "value": BUSINESS_DATE}, {"key": "company", "value": "Harbour & Pine Coffee Roasters Ltd"}],
            "users": [{"id": 1, "username": "sam", "name": "Sam Whitaker", "role": "finance", "salt": "hp7Q",
                       "pw": X.pw_hash("HarbourPine26", "hp7Q")},
                      {"id": 2, "username": "tom", "name": "Tom Reyes", "role": "director", "salt": "tR2k",
                       "pw": X.pw_hash("Roastery!Director", "tR2k")},
                      {"id": 3, "username": "priya", "name": "Priya Shah (Shah & Cole)", "role": "accountant", "salt": "pS9x",
                       "pw": X.pw_hash("ShahCole#Audit", "pS9x")}],
            "customers": [{"id": k, "name": v[0], "channel": v[1], "contact": v[2], "email": v[3], "phone": v[4], "terms": v[5],
                           "address": v[6]} for k, v in CUSTOMERS.items()],
            "invoices": [], "invoice_lines": [], "payments": [], "boardpacks": [], "audit": []}
    for inv in invoices:
        rows["invoices"].append({"id": inv["n"], "number": inv["number"], "customer_id": inv["cid"], "issue_date": inv["issue"].isoformat(),
                                 "due_date": inv["due"].isoformat(), "channel": inv["channel"], "reference": inv["ref"],
                                 "net": float(inv["net"]), "vat": float(inv["vat"]), "gross": float(inv["gross"]),
                                 "void": int(inv["void"]), "notes": inv["note"]})
        for desc, q, p in inv["lines"]:
            rows["invoice_lines"].append({"invoice_id": inv["n"], "description": desc, "qty": float(q), "unit_price": float(p),
                                          "net": float(D(Decimal(str(q)) * p))})
    for k, (inv, when, amt, user, created, ref) in enumerate(sorted(pays, key=lambda p: (p[1], p[0]["n"])), 1):
        rows["payments"].append({"id": k, "invoice_id": inv["n"], "date": when.isoformat(), "amount": float(amt), "method": "Bank transfer",
                                 "reference": ref, "created_by": user, "created_at": created, "deleted": 0})
    for bid, (per, title, fn, by, at) in enumerate([
            ("2026-07", "Management report - July 2026", "Management_Report_2026-07.pdf", "sam", "2026-08-04 16:02:11"),
            ("2026-08", "Management report - August 2026", "Management_Report_2026-08.pdf", "sam", "2026-09-02 15:12:40")], 1):
        path = f"{d}/uploads/{bid}_{fn}"
        rows["boardpacks"].append({"id": bid, "period": per, "title": title, "filename": fn, "path": f"{GUEST_DIR}/uploads/{bid}_{fn}",
                                   "size": os.path.getsize(path), "uploaded_by": by, "uploaded_at": at, "deleted": 0})
    rows["audit"] = [{"ts": "2026-09-24 10:31:12", "user": "priya", "action": "invoice voided", "detail": "INV-2026-0400 duplicate of INV-2026-0399"},
                     {"ts": "2026-09-01 10:14:07", "user": "tom", "action": "receipt recorded", "detail": "INV-2026-0398 £432.00 received 2026-09-01"}]
    rows["audit"].sort(key=lambda a: a["ts"])
    X.seed_db(f"{d}/ledgerline_seed.db", SCHEMA, rows)
    exp = {
        "me": ME[1], "tom": TOM[1], "priya": PRIYA[1], "msg": ids,
        "statement": st,
        "credits": [{**c, "amount": float(c["amount"]), "invoices": [f"{n:04d}" for n in c["invoices"]]} for c in credits],
        "payments": expected_pay, "seed_payment_max_id": len(rows["payments"]),
        "outstanding_0421": float(by_n[421]["gross"] - Decimal("600.00")),
        "report": {"rev": {m: {c: float(v) for c, v in rev[m].items()} for m in rev}, "totals": {m: float(v) for m, v in tot.items()},
                   "q3_total": float(sum(tot.values())), "pct_sep_vs_aug": round(float(pct), 1), "pct_exact": float(pct),
                   "top3": [[n, float(v)] for v, n in q3_cust[:3]], "sep_count": count["2026-09"],
                   "aug_old_total": float(sum(rev_old["2026-08"].values()))},
    }
    json.dump(exp, open(f"{d}/expected.json", "w"), indent=1)


SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT, salt TEXT, pw TEXT);
CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, channel TEXT, contact TEXT, email TEXT, phone TEXT, terms INTEGER, address TEXT);
CREATE TABLE invoices(id INTEGER PRIMARY KEY, number TEXT UNIQUE, customer_id INTEGER, issue_date TEXT, due_date TEXT, channel TEXT,
    reference TEXT, net REAL, vat REAL, gross REAL, void INTEGER DEFAULT 0, notes TEXT);
CREATE TABLE invoice_lines(id INTEGER PRIMARY KEY, invoice_id INTEGER, description TEXT, qty REAL, unit_price REAL, net REAL);
CREATE TABLE payments(id INTEGER PRIMARY KEY, invoice_id INTEGER, date TEXT, amount REAL, method TEXT, reference TEXT,
    created_by TEXT, created_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE boardpacks(id INTEGER PRIMARY KEY, period TEXT, title TEXT, filename TEXT, path TEXT, size INTEGER, uploaded_by TEXT,
    uploaded_at TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE sessions(sid TEXT PRIMARY KEY, user_id INTEGER, created TEXT, state TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
"""

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp())
