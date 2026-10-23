"""m1 - one Thunderbird: project mail rules (folders + tags + filters, run on the Inbox) vs comparing furniture quotes.

Persona: Sofia Marquez, office & project coordinator at Larchmont Design Group (architects, Chicago).
Task A (pgm1rules): set up the folders / tags / ordered filters from a scanned memo, run them on the Inbox, report counts.
Task B (pgm1quotes): four vendor quotes (one revised; two image-only PDFs, one only in the mail body) -> workbook,
                     pick the vendor by the director's criteria, two reply drafts.
The quote e-mails carry "[RLP]" in the subject, so A's filters move them while B works with them.
"""
from __future__ import annotations

import datetime as dt
import os

from lib_mmail import DocPage, build_profile, dump_expected, md5, msg, pdf_scan, scan_look

ME = ("Sofia Marquez", "sofia.marquez@larchmontdg.com")
HOST = "pop.larchmontdg.com"
TZ = dt.timezone(dt.timedelta(hours=-5))  # Chicago, CDT in October
DANIEL = "Daniel Okoye <daniel.okoye@larchmontdg.com>"
SOFIA = f"{ME[0]} <{ME[1]}>"


def at(day, hh, mm=0):
    return dt.datetime(2026, 10, day, hh, mm, tzinfo=TZ)


def mid(tag, dom="larchmontdg.com"):
    return f"<pgm1.{tag}@{dom}>"


# ---------------------------------------------------------------- the memo (image-only PDF)
MEMO_RULES = [
    "F1  Subject contains \"RLP\" and also contains \"invoice\"",
    "      -> add tag \"RLP Billing\", star the message, move it to Riverside Library / Invoices",
    "F2  Sender address is at riversidelibrary.org (our client)",
    "      -> add tag \"RLP\", move it to Riverside Library / Client",
    "F3  Sender address is at kalmarstructural.com or at greenfieldmep.com (our consultants)",
    "      -> add tag \"RLP\", move it to Riverside Library / Consultants",
    "F4  Any other message with \"[RLP]\" in the subject",
    "      -> add tag \"RLP\", move it to Riverside Library",
]


def memo_pdf(path):
    page = DocPage(
        "LARCHMONT DESIGN GROUP", "Architecture | Interiors | Planning\n410 N. Wells Street, Suite 900, Chicago, IL 60654",
        "INTERNAL MEMO",
        meta=[("To:", "Riverside Library project team"), ("From:", "Daniel Okoye, Project Director"),
              ("Date:", "19 October 2026"), ("Subject:", "Mail handling for the Riverside Library project (RLP)")],
        notes=["From Monday everyone on the team files RLP mail the same way, so that nothing gets lost",
               "when people cover for each other. Please set up your Thunderbird as follows.", "",
               "**1. Folders",
               "Create a folder \"Riverside Library\" directly under your mail account, with three",
               "subfolders: \"Client\", \"Consultants\" and \"Invoices\".", "",
               "**2. Tags",
               "Create two message tags named exactly \"RLP\" and \"RLP Billing\" (colours are up to you).", "",
               "**3. Message filters (create them in this order - the first rule that matches wins)", *MEMO_RULES, "",
               "All four filters must run automatically on new mail and must also be runnable manually.", "",
               "**4. Existing mail",
               "Run the filters once on your current Inbox. Leave everything else in the Inbox as it is.", "",
               "Questions -> Daniel (ext. 2214)."],
        footer="LDG internal - do not forward outside the firm")
    pdf_scan(path, [scan_look(page.image(), seed=11, angle=0.7)])


# ---------------------------------------------------------------- the quotes
TAX = 0.0825
VENDORS = {
    "northline": dict(name="Northline Office Interiors", contact="Rachel Kim <rkim@northlineinteriors.com>",
                      addr="2250 W. Fulton Market, Chicago, IL 60612", quote="Q-2291-R1", chair=155.00, table=600.00,
                      delivery=350.00, discount=0.0, date="2026-11-20", warranty=5, meets=True,
                      file="Northline_Q-2291-R1_signed.pdf"),
    "benchmark": dict(name="Benchmark Contract Furniture", contact="Tom Alvarez <t.alvarez@benchmarkcf.com>",
                      addr="1800 Busse Road, Elk Grove Village, IL 60007", quote="BCF-7730", chair=160.00, table=580.00,
                      delivery=0.0, discount=0.0, date="2026-12-07", warranty=7, meets=False, file="BCF-7730_Quote.pdf"),
    "lumen": dict(name="Studio Lumen Seating", contact="Ana Petrov <ana@studiolumen.co>",
                  addr="77 Water Street, Milwaukee, WI 53202", quote="SL-0912", chair=150.00, table=600.00,
                  delivery=275.00, discount=0.0, date="2026-11-24", warranty=3, meets=False,
                  file="StudioLumen_SL-0912.pdf"),
    "ashford": dict(name="Ashford & Pike Furnishings", contact="Liam Ashford <liam@ashfordpike.com>",
                    addr="", quote="AP-5521", chair=195.00, table=620.00, delivery=400.00, discount=0.10,
                    date="2026-11-25", warranty=5, meets=True, file=None),
}
NORTHLINE_ORIG = dict(quote="Q-2291", chair=189.00, table=640.00, delivery=350.00, file="Northline_Q-2291.pdf")
CHAIRS, TABLES = 40, 10
PO = "PO-RLP-0457"


def money(x):
    return f"${x:,.2f}"


def amounts(v):
    furn = CHAIRS * v["chair"] + TABLES * v["table"]
    disc = round(furn * v.get("discount", 0.0), 2)
    sub = round(furn - disc + v["delivery"], 2)
    tax = round(sub * TAX + 1e-9, 2)
    return furn, disc, sub, tax, round(sub + tax, 2)


def quote_page(v, quote, date, valid, chair, table, delivery, delivery_line, warranty_lines, extra_notes=()):
    vv = dict(v, chair=chair, table=table, delivery=delivery)
    furn, disc, sub, tax, total = amounts(vv)
    rows = [("Reading-room task chair, model 'Arden', oak / charcoal fabric", CHAIRS, money(chair), money(CHAIRS * chair)),
            ("Study table 72\" x 36\", white oak veneer, power module", TABLES, money(table), money(TABLES * table)),
            ("Delivery, inside placement and packaging removal", 1, money(delivery) if delivery else "incl.",
             money(delivery) if delivery else "$0.00")]
    return DocPage(v["name"].upper(), v["addr"] + "\nsales tel. (312) 555-0" + str(100 + len(v["name"])),
                   "QUOTATION",
                   meta=[("Quote no.:", quote), ("Date:", date), ("Valid until:", valid),
                         ("Customer:", "Larchmont Design Group - Riverside Library renovation"),
                         ("Attn.:", "Sofia Marquez")],
                   table=(["Description", "Qty", "Unit price", "Amount"], rows), widths=[300, 50, 80, 82],
                   totals=[("Subtotal", money(sub)), ("Sales tax 8.25%", money(tax)), ("TOTAL (USD)", money(total))],
                   notes=[delivery_line, *warranty_lines, "Payment: net 30 days from delivery.", *extra_notes]), total


def build(d):
    os.makedirs(f"{d}/attachments", exist_ok=True)
    att = f"{d}/attachments"
    memo_pdf(f"{att}/RLP_Mail_Handling_Memo.pdf")

    n = VENDORS["northline"]
    page, total_orig = quote_page(n, "Q-2291", "9 October 2026", "8 November 2026", NORTHLINE_ORIG["chair"],
                                  NORTHLINE_ORIG["table"], NORTHLINE_ORIG["delivery"],
                                  "Delivery: by Friday 20 November 2026 (confirmed slot).",
                                  ["Warranty: chairs 5 years, tables 10 years."])
    page.pdf_text(f"{att}/{NORTHLINE_ORIG['file']}")
    page, total_n = quote_page(n, "Q-2291-R1", "16 October 2026", "15 November 2026", n["chair"], n["table"],
                               n["delivery"], "Delivery: by Friday 20 November 2026 (confirmed slot).",
                               ["Warranty: chairs 5 years, tables 10 years."],
                               ["Revision R1 replaces quotation Q-2291 of 9 October 2026 (revised unit prices).", "",
                                "Accepted for Northline: R. Kim  ______________________"])
    pdf_scan(f"{att}/{n['file']}", [scan_look(page.image(), seed=21, stamp="REVISED R1")])
    b = VENDORS["benchmark"]
    page, total_b = quote_page(b, "BCF-7730", "12 October 2026", "30 days", b["chair"], b["table"], 0.0,
                               "Lead time: 8 weeks ARO - estimated delivery week of 7 December 2026.",
                               ["Warranty: chairs 7 years, tables 7 years (commercial use)."])
    pdf_scan(f"{att}/{b['file']}", [scan_look(page.image(), seed=31)])
    lu = VENDORS["lumen"]
    page, total_l = quote_page(lu, "SL-0912", "13 October 2026", "13 November 2026", lu["chair"], lu["table"],
                               lu["delivery"], "Delivery: Tuesday 24 November 2026.",
                               ["Warranty: chairs 3 years, tables 5 years."])
    pdf_scan(f"{att}/{lu['file']}", [scan_look(page.image(), seed=41, angle=-0.6)])
    a = VENDORS["ashford"]
    furn_a, disc_a, sub_a, tax_a, total_a = amounts(a)

    def rd(name):
        return open(f"{att}/{name}", "rb").read()

    mails = []  # (key, message, when, unread, expectation for task A: (folder, tags, flagged) or None = stays in Inbox)

    def add(key, frm, subject, when, body, a_exp=None, unread=True, atts=(), dom=None, html=None, cc=None, irt=None):
        dom = dom or frm.split("@")[1].rstrip(">")
        m = msg(frm, SOFIA, subject, when, mid(key, dom), body=body, html=html, attachments=atts, cc=cc, irt=irt)
        mails.append((key, m, when, unread, a_exp))
        return m["Message-ID"]

    INV = ("Riverside Library/Invoices", ["RLP Billing"], True)
    CLI = ("Riverside Library/Client", ["RLP"], False)
    CON = ("Riverside Library/Consultants", ["RLP"], False)
    GEN = ("Riverside Library", ["RLP"], False)

    # --- mail that belongs to task A's story
    policy = add("memo", DANIEL, "Mail rules for the Riverside Library project", at(19, 16, 42),
                 "Hi Sofia,\n\nas discussed in Monday's stand-up, attached is the memo with the new mail-handling rules "
                 "for the Riverside Library project. Could you set your Thunderbird up this way this week and let me know "
                 "when it is done? A quick note on how much of your existing mail ended up in each project folder "
                 "would help me see whether the rules catch the right things.\n\nThanks,\nDaniel\n\n--\nDaniel Okoye, AIA\n"
                 "Project Director | Larchmont Design Group\n(312) 555-0142 ext. 2214",
                 atts=[("RLP_Mail_Handling_Memo.pdf", rd("RLP_Mail_Handling_Memo.pdf"), "application/pdf")])
    add("inv4471", "Kalmar Structural Accounts <accounts@kalmarstructural.com>",
        "[RLP] Invoice 4471 - structural design, stage 2", at(6, 9, 12),
        "Dear Sofia,\n\nplease find below our invoice 4471 for structural design services, stage 2 (design development), "
        "Riverside Library renovation.\n\nAmount due: USD 18,400.00\nDue date: 5 November 2026\n\n"
        "Kind regards,\nAccounts | Kalmar Structural Engineers", INV, unread=False)
    add("signinv", "Wayfinder Signs Billing <billing@wayfindersigns.com>",
        "Invoice INV-2026-118 for RLP signage mock-ups", at(8, 14, 3),
        "Hello,\n\nattached is invoice INV-2026-118 for the three wayfinding sign mock-ups delivered to the Riverside "
        "Library site on 2 October.\nTotal: USD 2,260.00, payable within 30 days.\n\nWayfinder Signs, Billing", INV)
    add("invq", DANIEL, "RE: [RLP] Invoice 4471 query", at(9, 11, 30),
        "Sofia - before we approve 4471, can you check with Kalmar whether the stage 2 fee includes the extra beam "
        "calcs for the mezzanine? I think they were meant to be part of the base scope.\n\nD.", INV)
    add("hours", "Joanna Ruiz <j.ruiz@riversidelibrary.org>", "Reading room hours during construction", at(7, 10, 5),
        "Hi Sofia,\n\nthe board approved reduced reading-room hours while the works are on: Mon-Fri 10am-4pm, closed on "
        "Saturdays from 2 November. Please share with your site team so deliveries avoid opening hours where possible.\n\n"
        "Best,\nJoanna Ruiz\nFacilities Manager, Riverside Public Library\n(708) 555-0177", CLI, unread=False)
    add("board", "Harold Becker <director@riversidelibrary.org>", "[RLP] Board presentation - 12 November", at(13, 8, 50),
        "Dear Sofia,\n\ncould Daniel present the updated interior scheme to the library board on Thursday 12 November "
        "at 6:30pm? Twenty minutes plus questions.\n\nWith thanks,\nHarold Becker\nLibrary Director", CLI)
    add("approval", "Riverside Library Finance <finance@riversidelibrary.org>", "Invoice approval process for 2027",
        at(15, 13, 20),
        "Dear vendors and partners,\n\nfrom 1 January 2027 all invoices to the Library must quote a purchase order "
        "number issued by our finance office. Invoices without a PO number will be returned.\n\nRiverside Library Finance",
        CLI)
    add("storage", "Joanna Ruiz <j.ruiz@riversidelibrary.org>", "[RLP] Book storage containers - access code",
        at(20, 9, 15),
        "Sofia,\n\nthe two storage containers for the displaced collection are now on the east lot. Access code for the "
        "padlocks: 4-8-1-9. Please only share with the site supervisor.\n\nJoanna", CLI)
    add("lighting", "Tara Ng <t.ng@greenfieldmep.com>", "Re: Stack lighting levels", at(12, 16, 40),
        "Sofia,\n\nwe re-ran the calcs with the new LED fixtures: 32 fc average at the stacks, 50 fc on the reading "
        "tables. Both within the library's brief. Updated layout to follow by Friday.\n\nTara Ng, PE\nGreenfield MEP",
        CON, unread=False)
    add("beam", "Martin Chen <m.chen@kalmarstructural.com>", "[RLP] Beam schedule rev C", at(14, 11, 2),
        "Hi Sofia,\n\nbeam schedule revision C is on the project share (\\\\ldg-fs01\\RLP\\Structural\\BeamSchedule_revC.pdf). "
        "Changes: B12-B14 upsized to W12x26 for the mezzanine.\n\nMartin Chen, SE\nKalmar Structural Engineers", CON)
    add("facade", "Stonecraft Supply Orders <orders@stonecraftsupply.com>",
        "[RLP] Facade sample delivery - Tue 27 Oct", at(16, 15, 10),
        "Hello,\n\nyour limestone facade samples (3 finishes) will be delivered to the Riverside Library site on Tuesday "
        "27 October between 8 and 10am. Please make sure someone can sign for them.\n\nStonecraft Supply - Orders", GEN)
    add("minutes", "Priya Natarajan <priya.natarajan@larchmontdg.com>", "[RLP] Site meeting minutes 14 Oct",
        at(15, 9, 0),
        "All,\n\nminutes of the 14 Oct site meeting attached to the project share. Main actions: (1) contractor to "
        "submit revised phasing plan by 23 Oct, (2) LDG to confirm reading-room furniture order by 30 Oct, "
        "(3) MEP to issue lighting layout rev B.\n\nPriya", GEN, unread=False)
    # --- mail that belongs to task B's story (all "[RLP]" -> F4 moves them to Riverside Library)
    req = add("furn", DANIEL, "[RLP] Reading room furniture - please compare the quotes", at(17, 10, 20),
              "Hi Sofia,\n\nwe now have quotes from four vendors for the reading-room furniture (40 task chairs + 10 study "
              "tables). Could you put them side by side and pick one? Criteria, in this order:\n\n"
              "  1. Everything must be delivered by Friday 27 November 2026 - the library reopens on 1 December.\n"
              "  2. The chairs need a warranty of at least 5 years (the library's procurement rule).\n"
              "  3. Of the vendors that meet 1 and 2, take the lowest total cost including delivery and sales tax.\n\n"
              "Our purchase order number for this order is PO-RLP-0457. Please let me know who you picked and the "
              "total.\n\nThanks!\nDaniel", GEN)
    n_orig = add("q2291", n["contact"], "[RLP] Quotation Q-2291 - reading room furniture", at(9, 15, 45),
                 "Dear Ms. Marquez,\n\nthank you for your enquiry. Please find our quotation Q-2291 attached.\n\n"
                 "Best regards,\nRachel Kim\nSales Manager, Northline Office Interiors\n(312) 555-0126",
                 GEN, atts=[(NORTHLINE_ORIG["file"], rd(NORTHLINE_ORIG["file"]), "application/pdf")])
    n_rev = add("q2291r1", n["contact"], "[RLP] Revised quotation Q-2291-R1 - reading room furniture", at(16, 11, 5),
                "Dear Ms. Marquez,\n\nfollowing our call I am happy to send a revised quotation with better unit prices "
                "for the chairs and tables (signed copy attached). It replaces Q-2291.\n\nBest regards,\nRachel Kim\n"
                "Sales Manager, Northline Office Interiors", GEN,
                atts=[(n["file"], rd(n["file"]), "application/pdf")])
    b_id = add("bcf", b["contact"], "[RLP] Quote BCF-7730 reading room seating and tables", at(12, 8, 30),
        "Sofia,\n\nattached is our quote BCF-7730 for the Riverside Library reading room. Note that our lead time is "
        "currently 8 weeks.\n\nTom Alvarez\nBenchmark Contract Furniture", GEN,
        atts=[(b["file"], rd(b["file"]), "application/pdf")])
    l_id = add("lumen", lu["contact"], "[RLP] Quotation SL-0912", at(13, 17, 55),
        "Hi Sofia,\n\nhere is our quotation for 40 Arden chairs and 10 study tables (scanned, signed).\n\nAna Petrov\n"
        "Studio Lumen Seating", GEN, atts=[(lu["file"], rd(lu["file"]), "application/pdf")])
    ash_html = (
        "<p>Dear Sofia,</p><p>thank you for inviting us to quote. Our offer <b>AP-5521</b> for the Riverside Library "
        "reading room:</p><table border='1' cellpadding='4' style='border-collapse:collapse'>"
        "<tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr>"
        f"<tr><td>Task chair 'Arden'</td><td>{CHAIRS}</td><td>{money(a['chair'])}</td><td>{money(CHAIRS * a['chair'])}</td></tr>"
        f"<tr><td>Study table 72x36</td><td>{TABLES}</td><td>{money(a['table'])}</td><td>{money(TABLES * a['table'])}</td></tr>"
        f"<tr><td>Volume discount 10% on furniture</td><td></td><td></td><td>-{money(disc_a)}</td></tr>"
        f"<tr><td>Delivery and installation</td><td>1</td><td>{money(a['delivery'])}</td><td>{money(a['delivery'])}</td></tr>"
        f"<tr><td colspan='3'>Subtotal</td><td>{money(sub_a)}</td></tr>"
        f"<tr><td colspan='3'>Sales tax 8.25%</td><td>{money(tax_a)}</td></tr>"
        f"<tr><td colspan='3'><b>Total</b></td><td><b>{money(total_a)}</b></td></tr></table>"
        "<p>Delivery: Wednesday 25 November 2026. Warranty: chairs 5 years, tables 5 years. Quote valid 30 days; "
        "we invoice on delivery.</p><p>Kind regards,<br>Liam Ashford<br>Ashford &amp; Pike Furnishings<br>"
        "(630) 555-0190</p>")
    a_id = add("ap", a["contact"], "[RLP] Ashford & Pike quotation AP-5521", at(14, 12, 40), None, GEN, html=ash_html)
    # --- everything else stays in the Inbox
    add("adobe", "Adobe <message@adobe.com>", "Your Adobe invoice is ready", at(5, 6, 0),
        "Your invoice for Creative Cloud All Apps (team, 6 seats) is available in your account. Amount: USD 539.94.",
        unread=False)
    add("invoicely", "Invoicely <hello@news.invoicely.io>", "Invoice templates for creative studios - free download",
        at(11, 7, 30), "20 beautiful invoice templates for architects and designers. Download now!\n\nUnsubscribe")
    add("hpk", "Marcus Bell <marcus.bell@larchmontdg.com>", "[HPK] Hyde Park clinic - zoning hearing moved",
        at(12, 13, 0), "FYI the zoning variance hearing for the Hyde Park clinic moved to 4 November, 2pm.\n\nMarcus",
        unread=False)
    add("parking", "Priya Natarajan <priya.natarajan@larchmontdg.com>", "Re: Riverside Library - parking permits",
        at(18, 12, 10), "Sofia, the street parking permits for the site vans expire on 31 Oct - can you renew them "
        "with the city when you have a minute?\n\nPriya")
    add("lunch", "LDG Events <events@larchmontdg.com>", "Lunch & learn Thursday: mass timber in public buildings",
        at(19, 9, 0), "Join us in the big conference room on Thursday at 12:15. Pizza provided.")
    add("benefits", "LDG People Team <hr@larchmontdg.com>", "Open enrollment closes 31 October", at(14, 8, 0),
        "Reminder: benefits open enrollment closes on 31 October. Log in to the HR portal to review your elections.",
        unread=False)
    add("plotter", "LDG IT <it@larchmontdg.com>", "Plotter maintenance Friday 8-10am", at(20, 15, 30),
        "The large-format plotter on 9 will be offline on Friday 8-10am for maintenance.")
    add("aia", "AIA Chicago <news@aiachicago.org>", "November continuing-education sessions", at(10, 10, 0),
        "Register now for November CE sessions: accessibility code update, embodied carbon, and more.\n\nUnsubscribe")
    add("party", "Elena Duarte <elena.duarte@larchmontdg.com>", "Re: Holiday party venue shortlist", at(21, 11, 45),
        "I like the second option (the loft on Kinzie). Can we get a quote for 45 people?\n\nElena")
    add("revit", "LDG IT <it@larchmontdg.com>", "Revit 2027 licence renewal", at(21, 16, 5),
        "Your Revit licence renews on 1 November. No action needed unless you no longer need it.", unread=False)

    mails.sort(key=lambda x: x[2])
    build_profile(f"{d}/thunderbird-profile.tar.gz", ME, {"Inbox": [(m, w, u) for _, m, w, u, _ in mails]},
                  tz="America/Chicago")

    existing = [{"key": k, "id": m["Message-ID"], "subject": m["Subject"], "folder": e[0] if e else "Inbox",
                 "tags": e[1] if e else [], "flagged": e[2] if e else False} for k, m, w, u, e in mails]
    counts = {}
    for e in existing:
        counts[e["folder"]] = counts.get(e["folder"], 0) + 1
    # hidden probe messages: what the filters must do with mail that arrives later
    probes = [
        {"from": "Parking Office <facilities@riversidelibrary.org>", "subject": "Parking during the works",
         "folder": "Riverside Library/Client", "tags": ["RLP"], "flagged": False},
        {"from": "Library Billing <billing@riversidelibrary.org>", "subject": "RLP invoice dispute - stage 1",
         "folder": "Riverside Library/Invoices", "tags": ["RLP Billing"], "flagged": True},
        {"from": "Akosua Osei <a.osei@greenfieldmep.com>", "subject": "Duct routing at level 2",
         "folder": "Riverside Library/Consultants", "tags": ["RLP"], "flagged": False},
        {"from": "Martin Chen <m.chen@kalmarstructural.com>", "subject": "[RLP] Rebar submittal review",
         "folder": "Riverside Library/Consultants", "tags": ["RLP"], "flagged": False},
        {"from": "Acme Hardware <sales@acmehardware.com>", "subject": "[RLP] Door hardware lead times",
         "folder": "Riverside Library", "tags": ["RLP"], "flagged": False},
        {"from": "Kalmar Structural Accounts <accounts@kalmarstructural.com>", "subject": "[RLP] Invoice 4502",
         "folder": "Riverside Library/Invoices", "tags": ["RLP Billing"], "flagged": True},
        {"from": "ArchDaily <news@archdaily.com>", "subject": "Invoice tips for small practices",
         "folder": "Inbox", "tags": [], "flagged": False},
        {"from": "LDG People Team <hr@larchmontdg.com>", "subject": "Benefits enrollment reminder",
         "folder": "Inbox", "tags": [], "flagged": False},
    ]
    totals = {"northline": total_n, "benchmark": total_b, "lumen": total_l, "ashford": total_a}
    vendors = {k: {"name": v["name"], "email": v["contact"].split("<")[1].rstrip(">"), "quote": v["quote"],
                   "total": totals[k], "date": v["date"], "warranty": v["warranty"], "meets": v["meets"]}
               for k, v in VENDORS.items()}
    winner = min((k for k in vendors if vendors[k]["meets"]), key=lambda k: vendors[k]["total"])
    assert winner == "northline" and total_n == 13585.38, (winner, total_n)
    assert min(totals.values()) == total_b and total_l < total_n < total_a < total_orig  # traps stay traps
    dump_expected(d, {
        "host": HOST, "me": ME[1], "existing": existing, "counts": counts, "probes": probes,
        "folders": ["Riverside Library", "Riverside Library/Client", "Riverside Library/Consultants",
                    "Riverside Library/Invoices"], "tags": ["RLP", "RLP Billing"],
        "policy_id": policy, "daniel": "daniel.okoye@larchmontdg.com",
        "furniture_id": req, "northline_ids": [n_orig, n_rev],
        "vendor_ids": {"northline": [n_orig, n_rev], "benchmark": [b_id], "lumen": [l_id], "ashford": [a_id]}, "vendors": vendors, "winner": winner, "po": PO,
        "northline_original_total": total_orig,
        "pdfs": {f: md5(f"{att}/{f}") for f in (NORTHLINE_ORIG["file"], n["file"], b["file"], lu["file"])},
    })
