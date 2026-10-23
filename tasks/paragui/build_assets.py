#!/usr/bin/env python3
"""Build the files for the paraGUI shared-resource contention tasks (run on the node with the OSWorld venv python).

  python build_assets.py OUT_DIR [c1 c4 ...]     # all pairs by default; normally via `python -m oscombo tasks install`

Pairs added later keep their builder in build_<pair>.py (function build(out_dir)); they are picked up automatically.

Every pair of tasks shares one resource (a workbook, the Downloads folder, a slide deck, a git repo). Both tasks of a
pair upload the same files, so either can run alone, and in a dual run the second setup just rewrites identical bytes.
All content is deterministic (fixed seed) so evaluators can recompute the expected answers.
"""
import datetime as dt
import hashlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PARAGUI_TASK_ASSETS", os.path.expanduser("~/.cache/oscombo/paragui/assets"))
rng = random.Random(20261020)


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def font(size):
    return ImageFont.load_default(size=size)


# ---------------------------------------------------------------- C1: one workbook, cleaning vs summarising
def build_c1(d):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    os.makedirs(d, exist_ok=True)
    regions = {"North America": ["N. America", "North-America", "north america"],
               "EMEA": ["Emea", "EMEA ", "E.M.E.A."],
               "APAC": ["Apac", "Asia Pacific", "APAC "],
               "LATAM": ["Latam", "Latin America", "LATAM "]}
    reps = ["Avery Kim", "Jordan Patel", "Morgan Silva", "Riley Chen", "Casey Novak", "Taylor Brooks"]
    products = {"Sensor Kit": 129.0, "Edge Gateway": 899.0, "Cloud Seat": 49.0, "Install Service": 350.0}
    rows = []
    for i in range(140):
        day = dt.date(2026, 7, 1) + dt.timedelta(days=rng.randrange(92))
        region = rng.choice(list(regions))
        product = rng.choice(list(products))
        units = rng.randint(1, 40)
        rows.append({"id": f"SO-{26000 + i}", "date": day, "region": region, "rep": rng.choice(reps),
                     "product": product, "units": units, "price": products[product],
                     "revenue": round(units * products[product], 2)})
    raw = []
    for r in rows:
        shown = dict(r)
        x = rng.random()  # dirty date and region spellings, as a CRM export typically has them
        if x < 0.55:
            shown["date_cell"] = r["date"]
        elif x < 0.70:
            shown["date_cell"] = r["date"].strftime("%Y/%m/%d")
        elif x < 0.82:
            shown["date_cell"] = r["date"].strftime("%m-%d-%Y")
        elif x < 0.92:
            shown["date_cell"] = r["date"].strftime("%d.%m.%Y")
        else:
            shown["date_cell"] = r["date"].strftime("%b %d, %Y").replace(" 0", " ")
        shown["region_cell"] = rng.choice(regions[r["region"]]) if rng.random() < 0.35 else r["region"]
        raw.append(shown)
    for r in rng.sample(raw, 12):  # exact duplicate lines from a double export
        raw.insert(rng.randrange(len(raw)), dict(r))
    wb = Workbook()
    ws = wb.active
    ws.title = "Raw"
    head = ["Order ID", "Date", "Region", "Sales Rep", "Product", "Units", "Unit Price", "Revenue"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in raw:
        ws.append([r["id"], r["date_cell"], r["region_cell"], r["rep"], r["product"], r["units"], r["price"], r["revenue"]])
        if isinstance(r["date_cell"], dt.date):
            ws.cell(ws.max_row, 2).number_format = "dd/mm/yyyy"
    for col, w in zip("ABCDEFGH", (11, 13, 15, 14, 15, 7, 10, 11)):
        ws.column_dimensions[col].width = w
    notes = wb.create_sheet("Notes")
    notes.append(["Q3 2026 CRM export (pulled 2026-10-02 by ops)."])
    wb.save(f"{d}/sales_2026Q3.xlsx")
    json.dump({"regions": regions,
               "unique": {r["id"]: {"date": r["date"].isoformat(), "region": r["region"], "revenue": r["revenue"]}
                          for r in rows}},
              open(f"{d}/expected.json", "w"), indent=1)


# ---------------------------------------------------------------- C2: the Downloads folder, tidying vs a claim
def pdf_page(path, title, lines):
    im = Image.new("RGB", (1240, 1754), "white")
    dr = ImageDraw.Draw(im)
    dr.text((90, 110), title, fill="black", font=font(52))
    y = 230
    for ln in lines:
        dr.text((90, y), ln, fill="black", font=font(32))
        y += 54
    im.save(path, "PDF", resolution=150)


def picture(path, color, text):
    im = Image.new("RGB", (1024, 768), color)
    ImageDraw.Draw(im).text((60, 60), text, fill="white", font=font(60))
    im.save(path)


def build_c2(d):
    dl = f"{d}/Downloads"
    os.makedirs(dl, exist_ok=True)
    os.makedirs(f"{d}/claims", exist_ok=True)
    files = []

    def add(name, kind, target, maker):
        maker(f"{dl}/{name}")
        files.append({"name": name, "kind": kind, "target": target})

    add("bank_statement_2026-07.pdf", "pdf", "Documents/Archive/2026-07", lambda p: pdf_page(
        p, "Monthly statement July 2026", ["Account ****4821", "Opening balance 3,402.17", "Closing balance 2,918.40"]))
    add("payslip_2026-08.pdf", "pdf", "Documents/Archive/2026-08", lambda p: pdf_page(
        p, "Payslip August 2026", ["Northwind Labs GmbH", "Net pay 4,215.00 EUR"]))
    add("invoice_ACME_2026-08-14.pdf", "pdf", "Documents/Archive/2026-08", lambda p: pdf_page(
        p, "ACME Office Supplies - Invoice 8812", ["Date 2026-08-14", "Toner, paper", "Total 186.40 EUR"]))
    add("receipt_taxi_2026-08-03.pdf", "pdf", "Documents/Archive/2026-08", lambda p: pdf_page(
        p, "City Cabs Hamburg - Receipt", ["Date 2026-08-03", "Airport -> Hafencity", "Fare 41.20 EUR"]))
    add("insurance_renewal_2026-09-02.pdf", "pdf", "Documents/Archive/2026-09", lambda p: pdf_page(
        p, "Home insurance renewal", ["Policy HR-55102", "Annual premium 312.00 EUR"]))
    add("eticket_LH2034_2026-09-16.pdf", "pdf", "Documents/Archive/2026-09", lambda p: pdf_page(
        p, "Lufthansa e-ticket receipt", ["Flight LH2034 Hamburg -> Berlin, 16 Sep 2026",
                                          "Return LH2039 Berlin -> Hamburg, 19 Sep 2026",
                                          "Passenger: Pat Lee", "Fare paid: 412.80 EUR"]))
    add("receipt_hotel_Berlin_2026-09-19.pdf", "pdf", "Documents/Archive/2026-09", lambda p: pdf_page(
        p, "Hotel Spreeblick Berlin - Invoice", ["Guest: Pat Lee", "Arrival 16 Sep 2026, departure 19 Sep 2026",
                                                 "3 nights x 199.00 EUR", "Total paid: 597.00 EUR"]))
    add("taxi_receipt_2026-09-18.pdf", "pdf", "Documents/Archive/2026-09", lambda p: pdf_page(
        p, "Berlin Taxi Zentrale - Receipt", ["Date 18 Sep 2026", "Hotel -> Client office Mitte (return)",
                                              "Fare 38.50 EUR"]))
    add("conference_badge_2026-09-16.pdf", "pdf", "Documents/Archive/2026-09", lambda p: pdf_page(
        p, "Visitor badge", ["Client visit, 16 Sep 2026", "Pat Lee, Northwind Labs"]))
    add("user_manual.pdf", "pdf", "Documents/Archive/undated", lambda p: pdf_page(
        p, "Edge Gateway EG-200 User Manual", ["Chapter 1: Getting started"]))
    add("lease_agreement_signed.pdf", "pdf", "Documents/Archive/undated", lambda p: pdf_page(
        p, "Residential lease agreement", ["Signed copy"]))
    add("IMG_2041.jpg", "image", "Pictures/Downloads", lambda p: picture(p, (40, 90, 140), "Team offsite"))
    add("whiteboard_notes.jpg", "image", "Pictures/Downloads", lambda p: picture(p, (90, 90, 90), "Sprint plan"))
    add("screenshot_dashboard.png", "image", "Pictures/Downloads", lambda p: picture(p, (20, 120, 60), "KPI dashboard"))
    for name in ("zoom_amd64.deb", "slack-desktop-4.33.deb", "vscode-extensions-backup.zip"):
        add(name, "installer", None, lambda p: open(p, "wb").write(os.urandom(200_000)))
    for orig, dup in (("invoice_ACME_2026-08-14.pdf", "invoice_ACME_2026-08-14 (1).pdf"), ("IMG_2041.jpg", "IMG_2041 (1).jpg")):
        shutil.copy(f"{dl}/{orig}", f"{dl}/{dup}")
        files.append({"name": dup, "kind": "duplicate", "target": None})
    for f in files:
        f["md5"] = md5(f"{dl}/{f['name']}")
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Claim"
    ws["A1"] = "Travel expense claim"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"], ws["B2"] = "Employee", "Pat Lee"
    ws["A3"], ws["B3"] = "Trip", "Berlin client visit, 16-19 Sep 2026"
    for col, h in zip("ABCD", ("Date", "Vendor", "Category", "Amount (EUR)")):
        ws[f"{col}5"] = h
        ws[f"{col}5"].font = Font(bold=True)
    ws["C11"] = "Total"
    ws["C11"].font = Font(bold=True)
    for col, w in zip("ABCD", (14, 30, 14, 14)):
        ws.column_dimensions[col].width = w
    wb.save(f"{d}/claims/expense_form.xlsx")
    receipts = {"eticket_LH2034_2026-09-16.pdf": 412.80, "receipt_hotel_Berlin_2026-09-19.pdf": 597.00,
                "taxi_receipt_2026-09-18.pdf": 38.50}
    json.dump({"files": files, "receipts": {n: {"amount": a, "md5": md5(f"{dl}/{n}")} for n, a in receipts.items()},
               "total": round(sum(receipts.values()), 2)}, open(f"{d}/expected.json", "w"), indent=1)


# ---------------------------------------------------------------- C5: one slide deck, new results vs re-branding
def logo(path, kind):
    im = Image.new("RGBA", (400, 400), (255, 255, 255, 0))
    dr = ImageDraw.Draw(im)
    if kind == "old":
        dr.ellipse((20, 20, 380, 380), fill=(200, 30, 30, 255))
        dr.text((120, 140), "NW", fill="white", font=font(110))
    else:
        dr.rounded_rectangle((20, 20, 380, 380), 50, fill=(31, 56, 100, 255))
        dr.text((140, 120), "N", fill="white", font=font(150))
    im.save(path)


def build_c5(d):
    from openpyxl import Workbook
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt
    os.makedirs(f"{d}/brand", exist_ok=True)
    logo(f"{d}/old_logo.png", "old")
    logo(f"{d}/brand/northwind_logo_2026.png", "new")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    content = [("Q3 Model Evaluation", "Northwind Labs - Applied ML team, October 2026"),
               ("Agenda", "Dataset and setup\nModels compared\nResults\nNext steps"),
               ("Dataset", "PlantVillage-ext: 61,486 leaf images, 39 classes\n80/10/10 split, stratified"),
               ("Setup", "Same augmentation and 90-epoch schedule for all models\nSingle A100, mixed precision"),
               ("Models compared", "ResNet-50, ViT-B/16, ConvNeXt-T, Swin-T\nAll ImageNet-1k pretrained")]
    for i, (title, body) in enumerate(content):
        s = prs.slides.add_slide(prs.slide_layouts[0 if i == 0 else 1])
        s.shapes.title.text = title
        for r in s.shapes.title.text_frame.paragraphs[0].runs:
            r.font.name, r.font.size, r.font.bold = "DejaVu Serif", Pt(28), False
            r.font.color.rgb = RGBColor(0, 0, 0)
        s.placeholders[1].text = body
        pic = s.shapes.add_picture(f"{d}/old_logo.png", Inches(12.0), Inches(0.25), Inches(1.0), Inches(1.0))
        pic.name = "Logo"
    prs.save(f"{d}/Q3_model_review.pptx")
    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["Model", "Accuracy", "F1"])
    res = [("ResNet-50", 0.842, 0.811), ("ViT-B/16", 0.873, 0.856), ("ConvNeXt-T", 0.881, 0.862), ("Swin-T", 0.869, 0.851)]
    for r in res:
        ws.append(list(r))
    wb.save(f"{d}/results.xlsx")
    open(f"{d}/brand_guide.txt", "w").write(
        "Northwind Labs presentation brand guide (2026)\n\n"
        "1. Slide titles: Liberation Sans, bold, 32 pt, colour navy #1F3864.\n"
        "2. Logo: the old red circular logo is retired. Every slide shows the new logo\n"
        "   (Pictures/brand/northwind_logo_2026.png) in the top-right corner, about 1 inch wide.\n"
        "3. Every slide carries the word 'Confidential' in the bottom-left corner.\n")
    json.dump({"slides": len(content), "results": res, "best": "ConvNeXt-T"}, open(f"{d}/expected.json", "w"), indent=1)


# ---------------------------------------------------------------- C6: one git repository, two coding chores
FILES_C6 = {
    "README.md": "# invoicer\n\nSmall invoice reporting helpers used by the finance dashboard.\n\n"
                 "Run tests: `python3 -m unittest`\n",
    "requirements.txt": "click==8.0.1\njinja2==2.11.3\nrequests==2.25.1\nurllib3==1.26.4\n",
    "CHANGELOG.md": "# Changelog\n\n## Unreleased\n\n## 0.3.0 - 2026-09-12\n\n- Add overdue summary to the report.\n\n"
                    "## 0.2.0 - 2026-07-30\n\n- First public version.\n",
    "SECURITY_ADVISORY.md": "# Security advisory SA-2026-07\n\nAffected dependencies and fixed versions:\n\n"
                            "| package  | affected | fixed   |\n|----------|----------|---------|\n"
                            "| jinja2   | < 3.1.4  | 3.1.4   |\n| requests | < 2.32.0 | 2.32.3  |\n"
                            "| urllib3  | < 1.26.19| 1.26.19 |\n\n"
                            "Projects must pin the fixed versions and record the bump in their changelog.\n",
    "app/__init__.py": "",
    "app/models.py": "from dataclasses import dataclass\n\n\n@dataclass\nclass Invoice:\n    id: str\n    customer: str\n"
                     "    amount: float\n    status: str  # 'paid' | 'open' | 'overdue'\n",
    "app/report.py": "from collections import defaultdict\n\n\ndef summarize(invoices):\n"
                     "    \"\"\"Total amount per status.\"\"\"\n    totals = defaultdict(float)\n"
                     "    for inv in invoices:\n        totals[inv.status] += inv.amount\n    return dict(totals)\n\n\n"
                     "def overdue_customers(invoices):\n    return sorted({inv.customer for inv in invoices if inv.status == 'overdue'})\n",
    "tests/__init__.py": "",
    "tests/test_report.py": "import unittest\n\nfrom app.models import Invoice\nfrom app.report import overdue_customers, summarize\n\n"
                            "INVOICES = [Invoice('I-1', 'Acme', 120.0, 'paid'), Invoice('I-2', 'Globex', 80.5, 'open'),\n"
                            "            Invoice('I-3', 'Acme', 40.0, 'overdue'), Invoice('I-4', 'Initech', 15.0, 'overdue')]\n\n\n"
                            "class ReportTest(unittest.TestCase):\n    def test_summarize(self):\n"
                            "        self.assertEqual(summarize(INVOICES), {'paid': 120.0, 'open': 80.5, 'overdue': 55.0})\n\n"
                            "    def test_overdue_customers(self):\n"
                            "        self.assertEqual(overdue_customers(INVOICES), ['Acme', 'Initech'])\n\n\n"
                            "if __name__ == '__main__':\n    unittest.main()\n",
}


def build_c6(d):
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp()
    repo = f"{tmp}/invoicer"
    env = {**os.environ, "GIT_AUTHOR_NAME": "Pat Lee", "GIT_AUTHOR_EMAIL": "pat.lee@northwind.example",
           "GIT_COMMITTER_NAME": "Pat Lee", "GIT_COMMITTER_EMAIL": "pat.lee@northwind.example"}
    git = lambda *a, **k: subprocess.run(["git", "-C", repo, *a], check=True, env={**env, **k}, capture_output=True)  # noqa
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    for i, (when, paths, msg) in enumerate([
            ("2026-07-30T10:00:00", ["README.md", "requirements.txt", "app/__init__.py", "app/models.py", "app/report.py",
                                     "tests/__init__.py"], "Initial invoicer package"),
            ("2026-09-12T15:20:00", ["tests/test_report.py", "CHANGELOG.md"], "Add overdue summary and tests"),
            ("2026-10-01T09:05:00", ["SECURITY_ADVISORY.md"], "Add security advisory SA-2026-07")]):
        for p in paths:
            os.makedirs(os.path.dirname(f"{repo}/{p}") or repo, exist_ok=True)
            open(f"{repo}/{p}", "w").write(FILES_C6[p])
        git("add", *paths)
        git("commit", "-q", "-m", msg, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    with open(f"{repo}/.git/config", "a") as f:
        f.write("[user]\n\tname = Pat Lee\n\temail = pat.lee@northwind.example\n")
    open(f"{repo}/.gitignore", "w").write("__pycache__/\n*.pyc\n")
    git("add", ".gitignore")
    git("commit", "-q", "-m", "Ignore bytecode", GIT_AUTHOR_DATE="2026-10-01T09:06:00", GIT_COMMITTER_DATE="2026-10-01T09:06:00")
    with tarfile.open(f"{d}/invoicer.tar.gz", "w:gz") as t:
        t.add(repo, arcname="invoicer")
    base = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    json.dump({"base": base, "fixed": {"jinja2": "3.1.4", "requests": "2.32.3", "urllib3": "1.26.19"}, "unchanged": {"click": "8.0.1"}},
              open(f"{d}/expected.json", "w"), indent=1)
    shutil.rmtree(tmp)


# ---------------------------------------------------------------- C4: one mail client, inbox zero vs the offsite mails
TB_BASE = os.environ.get("PARAGUI_TB_BASE", os.path.expanduser("~/.cache/oscombo/paragui/base/thunderbird-profile.tar.gz"))
ME = ("Jordan Lee", "jordan.lee@northwindlabs.com")
C4_MAILS = [  # (folder it belongs in, sender name, sender address, subject, body, attachment file name or None)
    ("Team", "Dana Whitfield", "dana.whitfield@northwindlabs.com", "Data team offsite, 12-14 Nov: agenda",
     "Hi all,\n\nThe offsite is confirmed for 12-14 November at Lakeview Lodge. The agenda is attached.\n\n"
     "Please reply to this email by Friday to confirm you can make it, and tell me about any dietary "
     "requirements so I can pass them to the venue.\n\nThanks,\nDana", "Offsite_Agenda_Nov2026.pdf"),
    ("Team", "Priya Raman", "priya.raman@northwindlabs.com", "Offsite hotel booking confirmation",
     "Hi Jordan,\n\nYour room at Lakeview Lodge is booked for 12-14 Nov (2 nights). The confirmation from the hotel "
     "is attached; please keep it for your expense claim.\n\nPriya (Ops)", "Lakeview_Lodge_Booking_JLee.pdf"),
    ("Team", "Dana Whitfield", "dana.whitfield@northwindlabs.com", "1:1 moved to Thursday",
     "Hi Jordan, can we move our 1:1 to Thursday 3pm? Same room.\nDana", None),
    ("Team", "Marco Bianchi", "marco.bianchi@northwindlabs.com", "PR #482 ready for review",
     "Hey, the churn feature pipeline PR is ready. Would appreciate your eyes on the backfill logic.\nMarco", None),
    ("Team", "Aisha Mensah", "aisha.mensah@northwindlabs.com", "Q4 OKR draft - comments by Wed",
     "Hi team, I've put the Q4 OKR draft in the shared drive. Comments by Wednesday please.\nAisha", None),
    ("Team", "IT Service Desk", "it-desk@northwindlabs.com", "Reminder: security awareness training due 31 Oct",
     "Hello Jordan,\n\nYour annual security awareness training is due on 31 October. It takes about 25 minutes.\n\n"
     "IT Service Desk", None),
    ("Team", "Sam Ortiz", "sam.ortiz@northwindlabs.com", "Lunch Friday?",
     "Ramen place on 5th, Friday 12:30? Marco is in too.\nSam", None),
    ("Team", "People Team", "people@northwindlabs.com", "All-hands on 23 October",
     "The Q3 all-hands is on 23 October at 4pm in the atrium and online. Agenda to follow.\nPeople Team", None),
    ("Team", "Marco Bianchi", "marco.bianchi@northwindlabs.com", "Re: dashboard numbers look off",
     "Found it - the timezone cast in the daily rollup. Fix is in PR #479.\nMarco", None),
    ("Team", "Aisha Mensah", "aisha.mensah@northwindlabs.com", "Standup notes 14 Oct",
     "Notes: model retrain blocked on labels; Jordan to sync with Marco on backfill; demo moved to next sprint.", None),
    ("Finance", "AWS Billing", "no-reply@aws-billing.amazon.com", "Your AWS invoice for September 2026 is available",
     "Invoice 2026-09-118842 for account northwind-data: USD 1,284.17. Payment due 25 Oct 2026.", None),
    ("Finance", "Figma", "receipts@figma.com", "Your receipt from Figma #4471-0927",
     "Amount paid: USD 15.00 (Professional, 1 seat). Paid 27 Sep 2026.", None),
    ("Finance", "Uber Receipts", "noreply@uber.com", "Your Tuesday evening trip with Uber",
     "Total: EUR 23.40. Trip from Berlin Hbf to Hotel Adlon, 16 Sep 2026.", None),
    ("Finance", "City Power & Light", "billing@citypowerlight.com", "Your October electricity bill",
     "Amount due: USD 87.52 by 5 Nov 2026. Account 55-2190-77.", None),
    ("Finance", "Expensify", "notifications@expensify.com", "Reimbursement sent: Berlin client visit",
     "Your report 'Berlin client visit' was reimbursed: EUR 1,048.30.", None),
    ("Finance", "JetBlue", "receipts@jetblue.com", "Payment confirmation - booking QX7P2L",
     "We received your payment of USD 412.60 for booking QX7P2L (BOS-SFO, 3 Nov).", None),
    ("Newsletters", "The Batch", "thebatch@deeplearning.ai", "The Batch: open-weight models catch up",
     "This week: open-weight models close the gap on reasoning benchmarks...\n\nUnsubscribe | Manage preferences", None),
    ("Newsletters", "Medium Daily Digest", "noreply@medium.com", "Stories for Jordan: Why your feature store is slow",
     "Top stories for you today...\n\nUnsubscribe from this list", None),
    ("Newsletters", "Product Hunt", "hello@digest.producthunt.com", "Today's top 5 launches",
     "1. Notebook copilots for analysts ...\n\nYou are receiving this because you subscribed. Unsubscribe", None),
    ("Newsletters", "IKEA", "news@email.ikea.com", "Autumn sale: up to 30% off home office",
     "Desks, chairs and lamps for your home office. Offer ends 31 Oct.\n\nUnsubscribe", None),
    ("Newsletters", "LinkedIn", "jobs-noreply@linkedin.com", "Jordan, 12 new jobs for 'Senior Data Scientist'",
     "New jobs matching your alert...\n\nUnsubscribe from job alerts", None),
    ("Newsletters", "Coursera", "no-reply@m.mail.coursera.org", "New course: Causal Inference for Practitioners",
     "Enroll today and get 20% off.\n\nUnsubscribe", None),
    ("Newsletters", "GitHub", "noreply@github.com", "GitHub Changelog: September roundup",
     "Copilot code review, merge queue updates and more.\n\nUnsubscribe from changelog emails", None),
    ("Delete", "Northwind IT Support", "it-support@northvvindlabs-mail.com", "ACTION REQUIRED: mailbox storage full",
     "Your mailbox is 99% full. Verify your account within 24 hours at http://northvvind-verify.top to avoid suspension.",
     None),
    ("Delete", "Prize Center", "winner@global-prize-center.biz", "Congratulations! You have been selected",
     "You have won a USD 1,000 gift card. Claim now by sending your details.", None),
    ("Delete", "Accounts Payable", "billing@acc0unts-secure.ru", "Invoice #8812 overdue - final notice",
     "Your payment is overdue. Open the attached document at http://acc0unts-secure.ru/inv8812 to avoid fees.", None),
    ("Delete", "CryptoMax", "profit@cryptomax-signals.io", "Turn $250 into $12,000 this month",
     "Our AI trading bot guarantees returns. Sign up now.", None),
]


def build_c4(d):
    from email.message import EmailMessage
    from email.utils import format_datetime
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp()
    with tarfile.open(TB_BASE) as t:
        t.extractall(tmp)
    prof = f"{tmp}/.thunderbird/t5q2a5hp.default-release"
    # drop the IMAP account and every cached index: Thunderbird rebuilds the .msf files from the mbox files
    shutil.rmtree(f"{prof}/ImapMail")
    for root, _, files in os.walk(prof):
        for f in files:
            if f.endswith(".msf") or f in ("folderCache.json", "folderTree.json", "session.json", "session.json.backup",
                                          "global-messages-db.sqlite", "lock"):
                os.remove(os.path.join(root, f))
    if os.path.lexists(f"{prof}/lock"):
        os.remove(f"{prof}/lock")
    os.remove(f"{prof}/Mail/Local Folders/Bills")
    shutil.rmtree(f"{prof}/Mail/Local Folders/Trash.sbd", ignore_errors=True)
    host = "pop.northwindlabs.com"
    box = f"mailbox://jordan.lee@{host}"
    keep = [ln for ln in open(f"{prof}/prefs.js") if not any(
        k in ln for k in ("mail.server.server1.", "mail.identity.id1.", "mail.smtpserver.smtp1.", "mail.root.",
                          "mail.last_msg_movecopy_target_uri", "mail.imap.", "server2.directory\""))]
    prefs = {
        "mail.server.server1.type": "pop3", "mail.server.server1.hostname": host,
        "mail.server.server1.userName": "jordan.lee", "mail.server.server1.name": ME[1],
        "mail.server.server1.directory-rel": f"[ProfD]Mail/{host}", "mail.server.server1.check_new_mail": False,
        "mail.server.server1.login_at_startup": False, "mail.server.server1.download_on_biff": False,
        "mail.server.server1.storeContractID": "@mozilla.org/msgstore/berkeleystore;1",
        "mail.server.server1.port": 995, "mail.server.server1.socketType": 3,
        "mail.identity.id1.fullName": ME[0], "mail.identity.id1.useremail": ME[1], "mail.identity.id1.valid": True,
        "mail.identity.id1.smtpServer": "smtp1", "mail.identity.id1.reply_on_top": 1,
        "mail.identity.id1.draft_folder": f"{box}/Drafts", "mail.identity.id1.drafts_folder_picker_mode": "0",
        "mail.identity.id1.fcc_folder": f"{box}/Sent", "mail.identity.id1.fcc_folder_picker_mode": "0",
        "mail.identity.id1.archive_folder": f"{box}/Archives", "mail.identity.id1.stationery_folder": f"{box}/Templates",
        "mail.identity.id1.tmpl_folder_picker_mode": "0",
        "mail.smtpserver.smtp1.hostname": "smtp.northwindlabs.com", "mail.smtpserver.smtp1.port": 587,
        "mail.smtpserver.smtp1.username": "jordan.lee", "mail.smtpserver.smtp1.try_ssl": 2,
        "mail.smtpserver.smtp1.authMethod": 3, "mail.smtpserver.smtp1.description": "Northwind",
        "mail.root.none-rel": "[ProfD]Mail", "mail.root.pop3-rel": "[ProfD]Mail",
        "mail.shell.checkDefaultClient": False, "mail.spam.manualMark": False,
        "datareporting.policy.dataSubmissionPolicyBypassNotification": True, "mailnews.start_page.enabled": False,
        # under QEMU without KVM the default (GL) compositor leaves the window and the message pane unpainted
        "gfx.webrender.software": True, "layers.acceleration.disabled": True,
    }
    with open(f"{prof}/prefs.js", "w") as f:
        f.writelines(keep)
        for k, v in prefs.items():
            f.write(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n")
    acct = f"{prof}/Mail/{host}"
    os.makedirs(acct)
    open(f"{acct}/msgFilterRules.dat", "w").write('version="9"\nlogging="no"\n')
    for name in ("Drafts", "Sent", "Trash", "Templates"):
        open(f"{acct}/{name}", "w").close()
    att_dir = f"{d}/attachments"
    os.makedirs(att_dir)
    pdf_page(f"{att_dir}/Offsite_Agenda_Nov2026.pdf", "Data Team Offsite - Lakeview Lodge, 12-14 Nov 2026", [
        "Thu 12 Nov  14:00  Arrival, check-in", "Thu 12 Nov  16:00  Q3 retro (Dana)",
        "Fri 13 Nov  09:00  Roadmap 2027 workshop", "Fri 13 Nov  14:00  Hike / free time",
        "Fri 13 Nov  19:00  Team dinner", "Sat 14 Nov  09:30  Hack morning, demos", "Sat 14 Nov  13:00  Departure"])
    pdf_page(f"{att_dir}/Lakeview_Lodge_Booking_JLee.pdf", "Lakeview Lodge - Booking Confirmation", [
        "Guest: Jordan Lee", "Confirmation no.: LL-26-55821", "Arrival: 12 Nov 2026   Departure: 14 Nov 2026",
        "Room: Standard King, 2 nights", "Billed to: Northwind Labs (company account)"])
    r4 = random.Random(4)  # own stream so adding C4 left the other pairs' files unchanged
    order = list(range(len(C4_MAILS)))
    r4.shuffle(order)
    start = dt.datetime(2026, 9, 21, 8, 0, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    mbox, mails = [], []
    for k, i in enumerate(order):
        folder, name, addr, subject, body, att = C4_MAILS[i]
        when = start + dt.timedelta(hours=k * 19 + r4.randrange(6), minutes=r4.randrange(60))
        m = EmailMessage()
        m["From"] = f"{name} <{addr}>"
        m["To"] = f"{ME[0]} <{ME[1]}>"
        m["Subject"] = subject
        m["Date"] = format_datetime(when)
        m["Message-ID"] = f"<pgc4.{i:02d}.{when:%Y%m%d%H%M}@{addr.split('@')[1]}>"
        m.set_content(body)
        if att:
            m.add_attachment(open(f"{att_dir}/{att}", "rb").read(), maintype="application", subtype="pdf", filename=att)
        raw = m.as_bytes(policy=m.policy.clone(linesep="\n")).replace(b"\nFrom ", b"\n>From ")
        unread = r4.random() < 0.5
        mbox.append(b"From - " + when.strftime("%a %b %d %H:%M:%S %Y").encode() + b"\n"
                    + b"X-Mozilla-Status: " + (b"0000" if unread else b"0001") + b"\n"
                    + b"X-Mozilla-Status2: 00000000\nX-Mozilla-Keys: " + b" " * 80 + b"\n" + raw.rstrip(b"\n") + b"\n\n")
        mails.append({"id": m["Message-ID"], "folder": folder, "from": addr, "subject": subject, "attachment": att})
    open(f"{acct}/Inbox", "wb").write(b"".join(mbox))
    with tarfile.open(f"{d}/thunderbird-profile.tar.gz", "w:gz") as t:
        t.add(f"{tmp}/.thunderbird", arcname=".thunderbird")
    dana = next(m for m in mails if m["attachment"] == "Offsite_Agenda_Nov2026.pdf")
    json.dump({"mails": mails, "reply_to": dana["id"], "dana": dana["from"],
               "attachments": {a: md5(f"{att_dir}/{a}") for a in os.listdir(att_dir)}},
              open(f"{d}/expected.json", "w"), indent=1)
    shutil.rmtree(tmp)


def builders() -> dict:
    """c1..c6 live in this file; every later pair <p> has its own build_<p>.py with build(out_dir)."""
    import importlib.util
    found = {"c1": build_c1, "c2": build_c2, "c5": build_c5, "c6": build_c6, "c4": build_c4}
    here = os.path.dirname(os.path.abspath(__file__))
    for f in sorted(os.listdir(here)):
        if f.startswith("build_") and f.endswith(".py") and f != "build_assets.py":
            spec = importlib.util.spec_from_file_location(f[:-3], os.path.join(here, f))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "build"):
                found[f[len("build_"):-3]] = mod.build
    return found


if __name__ == "__main__":
    only = set(sys.argv[2:])
    for name, fn in builders().items():
        if only and name not in only:
            continue
        if os.path.exists(f"{OUT}/{name}"):
            shutil.rmtree(f"{OUT}/{name}")
        fn(f"{OUT}/{name}")
        print(name, "ok", sorted(os.listdir(f"{OUT}/{name}")))
