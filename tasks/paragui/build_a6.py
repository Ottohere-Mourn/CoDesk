"""A6 - Kestrel Lane Accountants: one client-files tree (~/Clients), restructured to a new convention (A) while the
morning post is filed into it (B). Build with the OSWorld venv python (PIL, PyMuPDF).

Assets (out_dir): a6.tar.gz (Clients/, Scans/Inbox/, Documents/Filing_memo_2026-11.pdf; extracted into ~),
expected.json (host only).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import random
import shutil
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_x import Page, _degrade  # noqa: E402

FIRM = "Kestrel Lane Accountants"
FIRM_ADDR = "4 Kestrel Lane, Harrogate HG1 2QT  ·  01423 556 210  ·  office@kestrellane.co.uk"

# id, old folder, first, surname, status, ceased date, address, utr, onboarded
CLIENTS = [
    ("KL-1043", "SMITH_Jon", "Jonathan", "Smith", "Active", None, "22 Beech Grove, Harrogate HG2 0LT", "73104 55821", "2019-04-02"),
    ("KL-1017", "PATEL_James", "James", "Patel", "Active", None, "14 Orchard Rise, Knaresborough HG5 8DP", "51920 33407", "2017-09-18"),
    ("KL-1062", "PATEL_Jamal", "Jamal", "Patel", "Active", None, "7 Mill Lane, Ripon HG4 1RS", "60218 74913", "2024-01-15"),
    ("KL-1051", "DESOUZA_Maria", "Maria", "De Souza", "Active", None, "Flat 3, 18 Station Parade, Harrogate HG1 1TS", "48271 09336", "2021-06-07"),
    ("KL-1008", "HUGHES_Owen", "Owen", "Hughes", "Ceased", "2026-06-30", "31 Kings Road, Harrogate HG1 5JW", "35562 81470", "2016-03-21"),
    ("KL-1029", "NOWAK_Kasia", "Katarzyna", "Nowak", "Active", None, "9 Skipton Road, Harrogate HG1 4LE", "92013 46658", "2019-11-11"),
    ("KL-1035", "BRENNAN_Ciara", "Ciara", "Brennan", "Active", None, "The Old Forge, Pannal HG3 1JN", "27739 60185", "2020-08-24"),
    ("KL-1012", "OKAFOR_Tunde", "Tunde", "Okafor", "Ceased", "2026-03-31", "56 Valley Drive, Harrogate HG2 0JS", "84406 12957", "2016-10-03"),
    ("KL-1047", "LINDQVIST_Erik", "Erik", "Lindqvist", "Active", None, "2 Abbey Court, Knaresborough HG5 0QB", "19985 27740", "2020-02-17"),
    ("KL-1055", "MORGAN_Rhys", "Rhys", "Morgan", "Active", None, "41 Cold Bath Road, Harrogate HG2 0NA", "66340 85219", "2022-05-30"),
    ("KL-1021", "ASHWORTH_Helen", "Helen", "Ashworth", "Ceased", "2026-08-31", "12 Wetherby Road, Harrogate HG2 7SA", "70452 31108", "2018-01-29"),
    ("KL-1066", "YATES_Callum", "Callum", "Yates", "Active", None, "5 Low Bridge, Knaresborough HG5 8HU", "43817 52296", "2025-02-10"),
]

TYPES = {  # new-convention type word -> old-convention description
    "Intake": "intake form", "Engagement": "engagement letter", "P60": "P60", "BankStatement": "bank statement",
    "HMRCLetter": "HMRC letter", "Payslip": "payslip", "TaxReturn": "tax return", "Receipts": "receipts",
}

# extra seeded documents per client: (type, date, messy_old_name or None)
EXTRA = {
    "KL-1043": [("TaxReturn", "2026-01-24", None), ("BankStatement", "2026-09-30", None)],
    "KL-1017": [("P60", "2025-05-28", None)],
    "KL-1062": [("Payslip", "2026-09-30", "scan0042.pdf")],
    "KL-1051": [("HMRCLetter", "2026-07-14", None), ("Receipts", "2026-04-05", None)],
    "KL-1008": [("TaxReturn", "2025-12-19", None)],
    "KL-1029": [("P60", "2025-06-02", "P60 2025.pdf")],
    "KL-1035": [("TaxReturn", "2026-01-30", None), ("HMRCLetter", "2026-08-21", None)],
    "KL-1012": [],
    "KL-1047": [("BankStatement", "2026-08-31", None)],
    "KL-1055": [("Receipts", "2026-03-31", "Morgan receipts box.pdf")],
    "KL-1021": [("HMRCLetter", "2026-05-12", None)],
    "KL-1066": [("TaxReturn", "2026-01-29", None)],
}

# the morning post: scan file, client id (None = not a client), type, date, addressee line, dup_of
SCANS = [
    ("scan_0001.pdf", "KL-1043", "P60", "2026-05-22", "Jonathan Smith", None),
    ("scan_0002.pdf", "KL-1062", "HMRCLetter", "2026-10-28", "Mr J Patel", None),
    ("scan_0003.pdf", "KL-1051", "BankStatement", "2026-10-31", "Ms M De Souza", None),
    ("scan_0004.pdf", "KL-1008", "HMRCLetter", "2026-10-20", "Mr O Hughes", None),
    ("scan_0005.pdf", "KL-1029", "Payslip", "2026-10-30", "Katarzyna Nowak", None),
    ("scan_0006.pdf", "KL-1035", "BankStatement", "2026-10-31", "Ms C Brennan", None),
    ("scan_0007.pdf", "KL-1051", "BankStatement", "2026-10-31", "Ms M De Souza", "scan_0003.pdf"),
    ("scan_0008.pdf", "KL-1017", "HMRCLetter", "2026-10-27", "Mr J Patel", None),
    ("scan_0009.pdf", "KL-1047", "P60", "2026-05-29", "Erik Lindqvist", None),
    ("scan_0010.pdf", None, "HMRCLetter", "2026-10-26", "Mrs D Fairweather", None),
    ("scan_0011.pdf", "KL-1055", "BankStatement", "2026-10-31", "Mr R Morgan", None),
    ("scan_0012.pdf", "KL-1066", "HMRCLetter", "2026-11-02", "Mr C Yates", None),
]
NONCLIENT_ADDR = "88 Otley Road, Harrogate HG2 0DP"

OLD_README = """KESTREL LANE ACCOUNTANTS - CLIENT FILES
=======================================

How the client files in this folder are organised (last updated March 2019).

Folders
  One folder per client, named SURNAME_Firstname, e.g. SMITH_Jon.
  SURNAME in capitals, no spaces; first name as we usually call the client.

Files
  Every document is a PDF named "YYYYMMDD description.pdf"
    YYYYMMDD     = the date printed on the document
    description  = one of: intake form, engagement letter, P60, bank statement,
                   HMRC letter, payslip, tax return, receipts
  Example: SMITH_Jon/20260124 tax return.pdf

The client's intake form (first page of the file) has the client ID, contact details
and the engagement status.

Post that is not for one of our clients stays in the scan inbox for the office manager.
"""


def nice(d: str) -> str:
    return dt.date.fromisoformat(d).strftime("%-d %B %Y")


def uk(d: str) -> str:
    return dt.date.fromisoformat(d).strftime("%d/%m/%Y")


def shrink(p: Page, f=0.7) -> Page:
    p.im = p.im.resize((int(p.w * f), int(p.h * f)))
    return p


def write_scan(path: str, pages: list[Page], seed: int):
    r = random.Random(seed)
    ims = [_degrade(shrink(p).im, r) for p in pages]
    ims[0].save(path, "PDF", resolution=105, save_all=True, append_images=ims[1:], quality=60)


def letterhead(p: Page, title: str, org: str, sub: str, date: str, color=(30, 60, 110)):
    p.d.rectangle((0, 0, p.w, 150), fill=color)
    p.text(70, 40, org, size=40, bold=True, fill=(255, 255, 255))
    p.text(70, 98, sub, size=20, fill=(225, 230, 240))
    p.text(70, 200, title, size=34, bold=True)
    p.text(p.w - 70, 210, f"Date: {nice(date)}", size=24, anchor="ra")


def addressee(p: Page, y: int, name: str, addr: str):
    for i, ln in enumerate([name] + [s.strip() for s in addr.split(",")]):
        p.text(70, y + i * 32, ln, size=23)
    return y + 32 * (len(addr.split(",")) + 1) + 30


def intake_page(c, seed: int) -> Page:
    cid, old, first, sur, status, ceased, addr, utr, onb = c
    p = Page()
    p.d.rectangle((0, 0, p.w, 130), fill=(22, 72, 64))
    p.text(70, 32, FIRM, size=38, bold=True, fill=(255, 255, 255))
    p.text(70, 86, FIRM_ADDR, size=17, fill=(220, 236, 230))
    p.text(70, 175, "CLIENT INTAKE FORM", size=36, bold=True)
    p.text(p.w - 70, 185, "Form KL-INT-3 (rev. 2016)", size=18, anchor="ra", fill=(90, 90, 90))
    rows = [("Client ID", cid), ("Full legal name", f"{first} {sur}"), ("Name we use", old.split("_")[1]),
            ("Home address", addr), ("UTR", utr), ("Services", "Self assessment; bookkeeping review"),
            ("Date onboarded", uk(onb)), ("Engagement partner", "R. Haldane" if seed % 2 else "S. Iqbal")]
    y = 260
    for k, v in rows:
        p.rect((70, y, p.w - 70, y + 62), width=2)
        p.text(90, y + 18, k, size=21, bold=True)
        p.text(430, y + 16, v, size=24, mono=k in ("Client ID", "UTR"))
        y += 62
    y += 40
    p.text(70, y, "Engagement status (office use)", size=24, bold=True)
    p.rect((70, y + 45, p.w - 70, y + 185), width=3)
    p.text(90, y + 60, "Tick / note:", size=19, fill=(100, 100, 100))
    if status == "Active":
        p.handwriting(330, y + 95, "Active - acting", size=38, seed=seed)
    else:
        p.handwriting(330, y + 70, "Acting from " + uk(onb), size=32, seed=seed)
        p.handwriting(330, y + 120, "CEASED " + uk(ceased) + " - disengaged", size=36, seed=seed + 1,
                      fill=(150, 20, 20))
        p.d.line((325, y + 92, 800, y + 92), fill=(150, 20, 20), width=3)
    y += 230
    p.text(70, y, "Identity checked (AML): passport + utility bill", size=21)
    p.text(70, y + 40, "Signed: ______________________", size=21)
    p.handwriting(200, y + 28, f"{first[0]}. {sur}", size=30, seed=seed + 7)
    return p


def doc_page(kind: str, date: str, name: str, addr: str, seed: int) -> Page:
    r = random.Random(seed)
    p = Page()
    if kind == "HMRCLetter":
        letterhead(p, "Your tax account", "HM Revenue & Customs", "Self Assessment · BX9 1AS", date, (0, 90, 70))
        y = addressee(p, 290, name, addr)
        p.lines(70, y, [f"Dear {name},", "",
                        "We have reviewed your Self Assessment account for the 2025-26 tax year.",
                        f"Balancing payment due by 31 January 2027: £{r.randint(300, 4800):,}.{r.randint(10, 99)}",
                        "If you have an agent, they can view this on your behalf.", "",
                        "Yours sincerely,", "Self Assessment team"], size=23)
    elif kind == "BankStatement":
        bank = r.choice(["Yorkshire Building Society", "Barclays Bank UK PLC", "Nationwide"])
        letterhead(p, "Current account statement", bank, "Statement of account", date, (70, 40, 90))
        y = addressee(p, 290, name, addr)
        rows, bal = [], r.randint(800, 5000) + 0.0
        d0 = dt.date.fromisoformat(date).replace(day=1)
        for i in range(9):
            amt = round(r.uniform(-400, 250), 2)
            bal += amt
            rows.append(((d0 + dt.timedelta(days=3 * i + 1)).strftime("%d %b"), r.choice(
                ["Card payment", "Direct debit", "Transfer in", "Standing order", "Faster payment"]),
                f"{amt:,.2f}", f"{bal:,.2f}"))
        p.table(70, y, [("Date", 160, "l"), ("Description", 520, "l"), ("Amount", 200, "r"), ("Balance", 200, "r")], rows)
    elif kind == "P60":
        letterhead(p, "P60 End of Year Certificate", "Employer: " + r.choice(["Nidd Valley Foods Ltd", "Crown Hotels Ltd",
                   "Harrogate Borough Council"]), "Tax year to 5 April " + date[:4], date, (60, 60, 60))
        y = addressee(p, 290, name, addr)
        p.table(70, y, [("Item", 600, "l"), ("Amount", 300, "r")],
                [("Pay in this employment", f"£{r.randint(18000, 52000):,}.00"),
                 ("Tax deducted", f"£{r.randint(1500, 9000):,}.00"), ("Final tax code", "1257L")])
    elif kind == "Payslip":
        letterhead(p, "Payslip", r.choice(["Bettys & Taylors Group", "Harrogate District NHS FT"]), "Monthly pay advice",
                   date, (120, 70, 20))
        y = addressee(p, 290, name, addr)
        p.table(70, y, [("Payments", 500, "l"), ("£", 250, "r")],
                [("Basic pay", f"{r.randint(1800, 3600):,}.00"), ("Tax", f"-{r.randint(200, 600)}.00"),
                 ("NI", f"-{r.randint(60, 240)}.00")])
    elif kind == "TaxReturn":
        letterhead(p, "SA100 Tax Return - filed copy", "HM Revenue & Customs", "Self Assessment", date, (0, 90, 70))
        y = addressee(p, 290, name, addr)
        p.lines(70, y, ["Submission receipt: " + "".join(r.choice("ABCDEFGHJK0123456789") for _ in range(16)),
                        "Tax year 2024-25", f"Total tax due: £{r.randint(400, 9000):,}.00"], size=23)
    elif kind == "Receipts":
        letterhead(p, "Receipts envelope - contents list", FIRM, "Client receipts summary", date, (22, 72, 64))
        y = addressee(p, 290, name, addr)
        p.table(70, y, [("Supplier", 600, "l"), ("£", 250, "r")],
                [(r.choice(["Screwfix", "Staples", "Shell", "Amazon", "Travis Perkins"]), f"{r.uniform(5, 300):.2f}") for _ in range(8)])
    elif kind == "Engagement":
        letterhead(p, "Letter of engagement", FIRM, FIRM_ADDR, date, (22, 72, 64))
        y = addressee(p, 290, name, addr)
        p.lines(70, y, [f"Dear {name},", "", "Thank you for appointing us as your accountants.",
                        "This letter sets out the basis on which we will act for you,", "including Self Assessment and bookkeeping review.",
                        "", "Yours sincerely,", "Kestrel Lane Accountants"], size=23)
    return p


def memo_pages() -> list[Page]:
    p = Page()
    p.d.rectangle((0, 0, p.w, 130), fill=(22, 72, 64))
    p.text(70, 32, FIRM, size=38, bold=True, fill=(255, 255, 255))
    p.text(70, 86, "Internal memo - partners", size=20, fill=(220, 236, 230))
    p.text(70, 170, "New filing convention for client files", size=34, bold=True)
    p.text(70, 220, "From: R. Haldane, S. Iqbal   To: office manager   Date: 2 November 2026", size=21)
    rows = [
        "From this month all client files in ~/Clients follow this convention:",
        "",
        "1. Two top-level folders: Active and Ceased.",
        "   A client goes under Ceased if their intake form says the engagement",
        "   has ceased; otherwise under Active.",
        "2. Client folder name:  <Surname>, <First name> (<Client ID>)",
        "   Use the FULL LEGAL NAME exactly as written on the intake form",
        "   (not the name we use day to day).  e.g.  Active/Smith, Jonathan (KL-1043)",
        "3. File name:  <Client ID>_<Type>_<YYYY-MM-DD>.pdf",
        "   Date = the date printed on the document.",
        "   Type = one of these words exactly:",
        "     Intake  Engagement  P60  BankStatement  HMRCLetter",
        "     Payslip  TaxReturn  Receipts",
        "   e.g.  KL-1043_TaxReturn_2026-01-24.pdf",
        "4. Nothing else in the client folders - no sub-folders, no copies.",
        "5. Keep README.txt in ~/Clients up to date with this convention,",
        "   and keep an index of clients: ~/Clients/index.csv",
        "   columns ClientID, Name, Status, Folder.",
        "",
        "Old names were 'SURNAME_Firstname' / 'YYYYMMDD description.pdf'.",
        "A few files never followed even that - open them to see what they are.",
    ]
    y = 290
    for ln in rows:
        p.text(70, y, ln, size=24, mono=ln.startswith("   ") or ln.startswith("     "))
        y += 38
    p.handwriting(760, y + 40, "Thanks! - RH", size=36, seed=99)
    return [p]


def md5b(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def build(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp()
    home = os.path.join(tmp, "home")
    cl = os.path.join(home, "Clients")
    inbox = os.path.join(home, "Scans", "Inbox")
    os.makedirs(inbox)
    os.makedirs(os.path.join(home, "Documents"))
    exp = {"clients": [], "files": [], "scans": [], "nonclient": "scan_0010.pdf"}
    seed = 600
    for c in CLIENTS:
        cid, old, first, sur, status, ceased, addr, utr, onb = c
        d = os.path.join(cl, old)
        os.makedirs(d)
        new_folder = f"{status}/{sur}, {first} ({cid})"
        exp["clients"].append({"id": cid, "old": old, "first": first, "surname": sur, "status": status,
                               "folder": new_folder, "address": addr})
        docs = [("Intake", onb, None), ("Engagement", onb, None)] + EXTRA[cid]
        for typ, date, messy in docs:
            seed += 1
            path = os.path.join(d, messy or f"{date.replace('-', '')} {TYPES[typ]}.pdf")
            page = intake_page(c, seed) if typ == "Intake" else doc_page(typ, date, f"{first} {sur}", addr, seed)
            write_scan(path, [page], seed)
            exp["files"].append({"client": cid, "old_name": os.path.basename(path), "type": typ, "date": date,
                                 "new_name": f"{cid}_{typ}_{date}.pdf", "md5": md5b(open(path, "rb").read())})
    open(os.path.join(cl, "README.txt"), "w").write(OLD_README)
    by_id = {c[0]: c for c in CLIENTS}
    pages = {}
    for scan, cid, typ, date, name, dup in SCANS:
        seed += 1
        addr = by_id[cid][6] if cid else NONCLIENT_ADDR
        if dup:
            page = pages[dup]
        else:
            page = doc_page(typ, date, name, addr, seed)
            pages[scan] = Page()
            pages[scan].im = page.im.copy()
            pages[scan].w, pages[scan].h = page.w, page.h
        path = os.path.join(inbox, scan)
        write_scan(path, [page], seed + 1000)
        exp["scans"].append({"scan": scan, "client": cid, "type": typ, "date": date, "dup_of": dup,
                             "md5": md5b(open(path, "rb").read()),
                             "old_name": f"{date.replace('-', '')} {TYPES[typ]}.pdf",
                             "new_name": f"{cid}_{typ}_{date}.pdf" if cid else None})
    memo = os.path.join(home, "Documents", "Filing_memo_2026-11.pdf")
    write_scan(memo, memo_pages(), 4242)
    exp["types"] = TYPES
    exp["old_readme_md5"] = md5b(OLD_README.encode())
    tar = os.path.join(out_dir, "a6.tar.gz")
    with tarfile.open(tar, "w:gz") as t:
        for top in ("Clients", "Scans", "Documents"):
            t.add(os.path.join(home, top), arcname=top)
    json.dump(exp, open(os.path.join(out_dir, "expected.json"), "w"), indent=1)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/a6_assets")
