"""X2 - recruiting at Fernleaf Analytics: CV screening for REQ-031 vs panel-interview scheduling for REQ-027.

build(out_dir) writes:
  app_x2.py                    HireDesk ATS web app (copied)
  hiredesk_seed.db             seeded sqlite db (5 requisitions, ~30 candidates, applications, interview slots)
  thunderbird-profile.tar.gz   Alex Moreno's offline mailbox (applications with CVs, Grace's rubric + tracker,
                               availability replies, Ben's constraints + panel sheet)
  expected.json                ground truth (host only)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_x as X  # noqa: E402
from lib_thunderbird import make_profile  # noqa: E402

ME = ("Alex Moreno", "alex.moreno@fernleaf.io")
GRACE = ("Grace Liu", "grace.liu@fernleaf.io")
BEN = ("Ben Okoro", "ben.okoro@fernleaf.io")
TZ = dt.timezone(dt.timedelta(hours=1))
BUSINESS_DATE = "2026-10-30"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REQS = [  # id, code, title, location, hiring manager, opened, status
    (1, "REQ-022", "Marketing Coordinator", "Leeds (office)", "Nadia Firth", "2026-02-09", "Filled"),
    (2, "REQ-024", "Data Engineer", "Leeds (hybrid)", "Grace Liu", "2026-03-02", "Filled"),
    (3, "REQ-027", "Product Designer", "Leeds (hybrid)", "Ben Okoro", "2026-09-01", "Open"),
    (4, "REQ-029", "Customer Success Manager", "Leeds (hybrid)", "Kofi Mensah", "2026-04-01", "Open"),
    (5, "REQ-031", "Data Analyst", "Leeds (hybrid)", "Grace Liu", "2026-10-12", "Open"),
]
RID = {r[1]: r[0] for r in REQS}

# ---------------------------------------------------------------- the five REQ-031 applicants (task A)
# scores: sql (0-2), code = Python or R (0-1), bi (0-1), degree (0-1); rtw Yes/No
APPLICANTS = [
    {"key": "desai", "name": "Priyanka Desai", "email": "priyanka.desai@gmail.com", "phone": "07700 900412", "loc": "Leeds",
     "scores": [2, 1, 1, 1], "rtw": "Yes", "stage": "Phone screen", "existing": False},
    {"key": "fairbairn", "name": "Tom Fairbairn", "email": "tom.fairbairn@btinternet.com", "phone": "07700 900233", "loc": "Wakefield",
     "scores": [1, 1, 0, 0], "rtw": "Yes", "stage": "Rejected", "existing": False},
    {"key": "romero", "name": "Lucia Romero", "email": "lucia.romero.data@gmail.com", "phone": "07700 900518", "loc": "Manchester",
     "scores": [2, 1, 1, 1], "rtw": "No", "stage": "Rejected", "existing": False},
    {"key": "okafor", "name": "Daniel Okafor", "email": "d.okafor@outlook.com", "phone": "07700 900671", "loc": "Leeds",
     "scores": [2, 0, 1, 1], "rtw": "Yes", "stage": "Phone screen", "existing": False},
    {"key": "boateng", "name": "Hannah Boateng", "email": "hannah.boateng@outlook.com", "phone": "07700 900877", "loc": "Leeds",
     "scores": [1, 1, 1, 1], "rtw": "Yes", "stage": "Phone screen", "existing": True},
]

CVS = {
    "desai": [
        ("h1", "Priyanka Desai"), ("small", "Leeds · 07700 900412 · priyanka.desai@gmail.com · linkedin.com/in/priyankadesai"),
        ("h2", "Profile"),
        ("p", "Data analyst who enjoys turning messy operational data into decisions. Four years of hands-on SQL, building "
              "dashboards for non-technical managers and automating recurring reporting."),
        ("h2", "Experience"),
        ("p", "Data Analyst - Yorkshire Water, Bradford (Jun 2023 - present)"),
        ("li", "Built and maintain the Tableau leakage KPI dashboards used by 40 operations managers."),
        ("li", "Rewrote the daily reporting pipeline in SQL (PostgreSQL), cutting refresh time from 3 hours to 20 minutes."),
        ("li", "Python (pandas) scripts for anomaly detection on smart-meter data."),
        ("p", "Junior Analyst - Asda Stores, Leeds (Sep 2022 - May 2023)"),
        ("li", "Weekly availability reporting for 120 stores; ad-hoc SQL for the supply chain team."),
        ("h2", "Education"),
        ("p", "BSc (Hons) Mathematics, University of Sheffield, 2019 - 2022 (2:1)"),
        ("h2", "Skills"),
        ("li", "SQL - 4 years (PostgreSQL, BigQuery)"), ("li", "Python (pandas, matplotlib)"), ("li", "Tableau"),
        ("li", "Excel and Google Sheets"),
        ("h2", "Right to work"), ("p", "Right to work in the UK: yes (British citizen)."),
    ],
    "fairbairn": [
        ("h1", "Tom Fairbairn"), ("small", "Wakefield · 07700 900233 · tom.fairbairn@btinternet.com"),
        ("h2", "Personal statement"),
        ("p", "Operations coordinator moving into data analysis. I produce the monthly performance pack for our region and "
              "have taught myself SQL and R over the last two years."),
        ("h2", "Experience"),
        ("p", "Operations Coordinator - Northern Trains, Leeds (Mar 2021 - present)"),
        ("li", "Monthly punctuality and staffing reports in Excel (pivot tables, Power Query)."),
        ("li", "R scripts (tidyverse) to analyse delay causes; SQL queries against the incident database."),
        ("p", "Sales Assistant - Waterstones, Wakefield (2019 - 2021)"),
        ("h2", "Education"),
        ("p", "BA (Hons) History, University of Leeds, 2017 - 2020"),
        ("h2", "Skills"),
        ("li", "SQL - 2 years (Microsoft SQL Server, self-taught)"), ("li", "R (tidyverse, ggplot2)"),
        ("li", "Excel (advanced: pivot tables, Power Query, VLOOKUP)"),
        ("h2", "Right to work"), ("p", "Right to work in the UK: yes (British citizen)."),
    ],
    "romero": [
        ("h1", "Lucia Romero"), ("small", "Manchester · 07700 900518 · lucia.romero.data@gmail.com"),
        ("h2", "Summary"),
        ("p", "Economist and BI analyst with three years in retail banking analytics in Madrid, now based in Manchester "
              "after completing my master's in the UK."),
        ("h2", "Experience"),
        ("p", "Data Analyst - Banco Sabadell, Madrid (Jul 2021 - Aug 2024)"),
        ("li", "Power BI reporting suite for the mortgage division; SQL (MySQL, Snowflake) data models."),
        ("li", "Python and R for credit-risk segmentation and forecasting."),
        ("p", "Research Assistant - University of Manchester (Sep 2024 - Jun 2025)"),
        ("h2", "Education"),
        ("p", "MSc Economics, University of Manchester, 2024 - 2025 (Distinction)"),
        ("p", "BSc Economics, Universidad Carlos III de Madrid, 2017 - 2021"),
        ("h2", "Skills"),
        ("li", "SQL - 3 years (MySQL, Snowflake)"), ("li", "Python and R"), ("li", "Power BI"),
        ("li", "Spanish (native), English (C2)"),
        ("h2", "Right to work"),
        ("p", "Right to work in the UK: I hold a Graduate visa valid until January 2027 and would need Skilled Worker visa "
              "sponsorship for a permanent role."),
    ],
    "okafor_v1": [
        ("h1", "Daniel Okafor"), ("small", "Leeds · 07700 900671 · d.okafor@outlook.com"),
        ("h2", "Profile"),
        ("p", "Civil engineering graduate who discovered a love of data while building cost dashboards. Looking for my "
              "first dedicated analyst role."),
        ("h2", "Experience"),
        ("p", "Graduate Engineer (Project Controls) - Arup, Leeds (Sep 2025 - present)"),
        ("li", "Looker dashboards for project cost and schedule tracking across 14 schemes."),
        ("li", "SQL in BigQuery to combine timesheet and procurement data."),
        ("p", "Placement year: Data & Insight Intern - Jacobs, Manchester (Jul 2023 - Jun 2024)"),
        ("li", "Cleaned asset-condition survey data and built monthly reports."),
        ("h2", "Education"),
        ("p", "BEng (Hons) Civil Engineering, University of Leeds, 2021 - 2025 (First)"),
        ("h2", "Skills"),
        ("li", "SQL - 1 year (BigQuery)"), ("li", "Looker / LookML"), ("li", "Excel"), ("li", "AutoCAD, Primavera P6"),
        ("h2", "Right to work"), ("p", "Right to work in the UK: yes (British citizen)."),
    ],
    "boateng": [
        ("h1", "Hannah Boateng"), ("small", "Leeds · 07700 900877 · hannah.boateng@outlook.com"),
        ("h2", "Profile"),
        ("p", "Customer insight analyst with a background in customer success. I combine survey and behavioural data to "
              "explain churn and help teams act on it."),
        ("h2", "Experience"),
        ("p", "Customer Insight Analyst - Sky, Leeds (Jan 2025 - present)"),
        ("li", "Power BI churn reporting for the retention team; Python notebooks for survey text analysis."),
        ("li", "SQL (Snowflake) for cohort and retention analysis."),
        ("p", "Customer Success Associate - Zoopla, London (2022 - 2024)"),
        ("h2", "Education"),
        ("p", "MSc Data Science, Leeds Beckett University, 2023 - 2024 (part-time)"),
        ("p", "BSc Psychology, University of York, 2018 - 2021"),
        ("h2", "Skills"),
        ("li", "SQL - 2 years (Snowflake)"), ("li", "Python (pandas, scikit-learn)"), ("li", "Power BI"),
        ("h2", "Right to work"), ("p", "Right to work in the UK: yes (British citizen)."),
    ],
}
# the updated CV Daniel sends a week later: same, but his SQL line now counts the placement year and final-year project
CVS["okafor_v2"] = [it if it != ("li", "SQL - 1 year (BigQuery)") else
                    ("li", "SQL - 3 years (BigQuery; SQL Server during my placement year and final-year project)") for it in CVS["okafor_v1"]]
CVS["okafor_v2"] = [it if it[0] != "li" or "Cleaned asset-condition" not in it[1] else
                    ("li", "Cleaned asset-condition survey data in SQL Server and built the monthly reports.") for it in CVS["okafor_v2"]]

# ---------------------------------------------------------------- REQ-027 interview slots (task B)
SLOTS = [  # key, start, booked-by (seed)
    ("S1", "2026-11-02 14:00", None), ("S2", "2026-11-03 10:00", None), ("S3", "2026-11-03 14:00", None),
    ("S4", "2026-11-04 11:00", None), ("S5", "2026-11-05 09:30", None), ("S6", "2026-11-05 15:00", "price"),
    ("S7", "2026-11-06 10:00", None), ("S8", "2026-11-06 14:30", None),
]
LINKS = {"S1": "pd-2b7-k4q", "S2": "pd-6t1-wq8", "S3": "pd-9mx-3rf", "S4": "pd-4hd-v2c", "S5": "pd-7ke-p5n",
         "S6": "pd-1zs-8gy", "S7": "pd-5ra-j6w", "S8": "pd-3uc-n9d"}
BOOK = {"chen": "S3", "leo": "S5", "amara": "S7"}  # earliest usable slot, first repliers first (S1 Monday and S2 Tue am blocked)
PD = {"leo": ("Leo Fischer", "leo.fischer@gmail.com"), "amara": ("Amara Nwosu", "amara.nwosu@proton.me"),
      "chen": ("Chen Wei", "chen.wei.design@outlook.com"), "sofia": ("Sofia Marín", "sofia.marin@hey.com")}


def scan_cv(path, items, seed):
    p = X.Page()
    y = 110
    for kind, text in items:
        if kind == "h1":
            y = p.text(100, y, text, size=46, bold=True) + 4
        elif kind == "small":
            y = p.text(100, y, text, size=19, fill=(80, 80, 80)) + 16
        elif kind == "h2":
            y += 12
            p.text(100, y, text.upper(), size=24, bold=True, fill=(30, 70, 60))
            p.hline(100, 1140, y + 34, width=2, fill=(30, 70, 60))
            y += 48
        else:
            width = 86 if kind == "p" else 82
            for i, ln in enumerate(textwrap.wrap(text, width)):
                x = 100 if kind == "p" else 130
                p.text(x, y, ("•  " if (kind == "li" and i == 0) else ("   " if kind == "li" else "")) + ln, size=21,
                       bold=(kind == "p" and " - " in text and "(" in text and i == 0 and len(text) < 90))
                y += 31
            y += 5
    X.scanned_pdf(path, [p], seed=seed)


def text_cv(path, items, title):
    X.text_pdf(path, X.flow(items), title=title)


def tracker(path, rows=()):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Screening"
    ws["A1"] = "REQ-031 Data Analyst - CV screening tracker"
    ws["A1"].font = Font(bold=True, size=14)
    heads = ["Candidate", "Email", "SQL (0-2)", "Python/R (0-1)", "BI tool (0-1)", "Quant. degree (0-1)", "Right to work (Y/N)",
             "Total (0-5)", "Decision", "Notes"]
    for j, h in enumerate(heads, 1):
        c = ws.cell(3, j, h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E8DF")
    for r, row in enumerate(rows, 4):
        for j, v in enumerate(row, 1):
            ws.cell(r, j, v)
    for col, w in zip("ABCDEFGHIJ", (22, 30, 10, 13, 12, 17, 18, 11, 16, 34)):
        ws.column_dimensions[col].width = w
    ws["A16"] = "Decision: 'Phone screen' (total 4-5 and right to work) or 'Rejected'."
    ws["A16"].font = Font(italic=True, color="666666")
    wb.save(path)


def panel_sheet(path, slot_rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Panel"
    ws["A1"] = "REQ-027 Product Designer - panel interviews, week of 2 November"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Panel: Ben Okoro, Ines Duarte · 60 min · video call (link in HireDesk)"
    for j, h in enumerate(["Date", "Time", "Length", "Panel", "Candidate", "Notes"], 1):
        c = ws.cell(4, j, h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E8DF")
    for r, row in enumerate(slot_rows, 5):
        for j, v in enumerate(row, 1):
            ws.cell(r, j, v)
    for col, w in zip("ABCDEF", (18, 9, 9, 24, 24, 40)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def date_label(start):
    t = dt.datetime.strptime(start, "%Y-%m-%d %H:%M")
    return t.strftime("%a ") + str(t.day) + t.strftime(" %b %Y"), t.strftime("%H:%M")


def build(d):
    os.makedirs(d, exist_ok=True)
    X.copy_app("app_x2.py", d)
    tmp = tempfile.mkdtemp()
    when = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=TZ)  # noqa: E731
    rd = lambda p: open(p, "rb").read()  # noqa: E731
    # ---- CVs
    text_cv(f"{tmp}/CV_Priyanka_Desai.pdf", CVS["desai"], "Priyanka Desai CV")
    scan_cv(f"{tmp}/Tom_Fairbairn_CV.pdf", CVS["fairbairn"], 21)
    text_cv(f"{tmp}/LRomero_CV_2026.pdf", CVS["romero"], "Lucia Romero - CV")
    text_cv(f"{tmp}/Daniel_Okafor_CV.pdf", CVS["okafor_v1"], "Daniel Okafor CV")
    scan_cv(f"{tmp}/Daniel_Okafor_CV_updated.pdf", CVS["okafor_v2"], 22)
    scan_cv(f"{tmp}/Hannah_Boateng_CV.pdf", CVS["boateng"], 23)
    # ---- workbooks
    tracker(f"{tmp}/REQ-031_screening_tracker.xlsx", [
        ("Oliver Grant", "oliver.grant@gmail.com", 2, 1, 1, 1, "Y", 5, "Phone screen", "Screened by Grace 14 Oct"),
        ("Sara Haddad", "sara.haddad@yahoo.co.uk", 1, 1, 0, 1, "Y", 3, "Rejected", "Below threshold")])
    slot_rows = []
    for key, start, booked in SLOTS:
        dl, tm = date_label(start)
        slot_rows.append((dl, tm, "60 min", "Ben Okoro, Ines Duarte", "Dan Price" if booked else "", ""))
    panel_sheet(f"{tmp}/PD_panel_schedule.xlsx", slot_rows)
    # ---- mailbox
    ids = {}

    def mid(key, dom):
        ids[key] = f"<x2.{key}.{len(ids) + 1:02d}@{dom}>"
        return ids[key]

    pdf = "application/pdf"
    A = {a["key"]: a for a in APPLICANTS}
    av_subject = "Interview availability - Product Designer at Fernleaf"
    sent, inbox = [], []
    for k in ("leo", "amara", "chen", "sofia"):
        name, addr = PD[k]
        first = name.split()[0]
        sent.append((X.mail(ME, [PD[k]], av_subject,
                            f"Hi {first},\n\nThanks for your time on the phone - Ben and Ines would love to meet you for a 60-minute "
                            "panel interview (video call) in the week of 2 November.\n\nCould you let me know which days and "
                            "times that week work for you? I'll then send you a calendar invite with the link.\n\n"
                            "Best wishes,\nAlex Moreno\nTalent Coordinator, Fernleaf Analytics",
                            when("2026-10-23T11:" + {"leo": "02", "amara": "04", "chen": "06", "sofia": "08"}[k] + ":00"),
                            mid("ask_" + k, "fernleaf.io")), False))

    def rep(k, ts, body, key):
        name, addr = PD[k]
        return X.mail((name, addr), [ME], "Re: " + av_subject, body, when(ts), mid(key, addr.split("@")[1]), irt=ids["ask_" + k])

    inbox += [
        (X.mail(("Priyanka Desai", A["desai"]["email"]), [ME], "Application: Data Analyst (REQ-031)",
                "Dear Alex,\n\nPlease find attached my CV for the Data Analyst role advertised on your careers page "
                "(REQ-031). I'd be delighted to discuss how my experience at Yorkshire Water could help Fernleaf's clients.\n\n"
                "Kind regards,\nPriyanka Desai", when("2026-10-19T20:14:00"), mid("app_desai", "gmail.com"),
                atts=[("CV_Priyanka_Desai.pdf", rd(f"{tmp}/CV_Priyanka_Desai.pdf"), pdf)]), False),
        (X.mail(("Tom Fairbairn", A["fairbairn"]["email"]), [ME], "Data Analyst role - application",
                "Hello,\n\nI would like to apply for the Data Analyst position. My CV is attached (scanned, sorry - my "
                "printer at home only scans).\n\nThanks,\nTom Fairbairn", when("2026-10-20T07:41:00"), mid("app_fairbairn", "btinternet.com"),
                atts=[("Tom_Fairbairn_CV.pdf", rd(f"{tmp}/Tom_Fairbairn_CV.pdf"), pdf)]), False),
        (X.mail(("Daniel Okafor", A["okafor"]["email"]), [ME], "Application for Data Analyst - Daniel Okafor",
                "Hi Alex,\n\nI'm applying for the Data Analyst role (REQ-031). CV attached.\n\nBest,\nDaniel",
                when("2026-10-21T12:30:00"), mid("app_okafor", "outlook.com"),
                atts=[("Daniel_Okafor_CV.pdf", rd(f"{tmp}/Daniel_Okafor_CV.pdf"), pdf)]), False),
        (X.mail(GRACE, [ME], "REQ-031 screening - rubric and tracker",
                "Hi Alex,\n\nThanks for covering the CV screening for the Data Analyst role (REQ-031) while I'm on the "
                "client project. Please score every applicant from their CV only:\n\n"
                "- SQL: years of SQL experience stated in the CV - none: 0, 1-2 years: 1, 3 or more years: 2\n"
                "- Python or R: 1 if either is listed (max 1)\n"
                "- BI tool (Tableau, Power BI or Looker): 1. Excel doesn't count.\n"
                "- Degree in a quantitative subject (maths, statistics, economics, computer science, physics, engineering "
                "or data science - any level, a master's counts): 1\n"
                "- Right to work in the UK without sponsorship: Yes/No. We can't sponsor for this role, so No means "
                "Rejected whatever the score.\n\n"
                "Total = the four scores (0-5). A total of 4 or 5 with right to work goes to Phone screen; everyone else is "
                "Rejected (reason 'Below threshold' or 'No right to work').\n\n"
                "Please put everyone into HireDesk on REQ-031 with their scorecard and stage - check first whether they're "
                "already on file, a few people have applied to other roles before and I don't want duplicate records. "
                "Then add them to my tracker (attached; Oliver and Sara are already in) and send it back to me with the "
                "shortlist.\n\nThanks!\nGrace", when("2026-10-22T08:05:00"), mid("grace", "fernleaf.io"),
                atts=[("REQ-031_screening_tracker.xlsx", rd(f"{tmp}/REQ-031_screening_tracker.xlsx"), XLSX_MIME)]), False),
        (X.mail(("Lucia Romero", A["romero"]["email"]), [ME], "REQ-031 Data Analyst application",
                "Dear Hiring Team,\n\nI am writing to apply for the Data Analyst role in Leeds. Please find my CV attached.\n\n"
                "Best regards,\nLucia Romero", when("2026-10-23T16:52:00"), mid("app_romero", "gmail.com"),
                atts=[("LRomero_CV_2026.pdf", rd(f"{tmp}/LRomero_CV_2026.pdf"), pdf)]), False),
        (X.mail(("LinkedIn Talent Solutions", "jobs-noreply@linkedin.com"), [ME], "Your job post 'Customer Success Manager' has 14 new applicants",
                "14 new applicants for Customer Success Manager - Fernleaf Analytics. Review them in LinkedIn Recruiter.\n\nUnsubscribe",
                when("2026-10-24T06:00:00"), mid("linkedin", "linkedin.com")), False),
        (X.mail(("Hannah Boateng", A["boateng"]["email"]), [ME], "Application - Data Analyst",
                "Hi Alex,\n\nYou may remember me from the Customer Success Manager process in the spring. Since then I've "
                "finished my MSc and moved into an insight role, so I'd love to be considered for the Data Analyst opening. "
                "Updated CV attached (scanned).\n\nAll the best,\nHannah", when("2026-10-26T09:33:00"), mid("app_boateng", "outlook.com"),
                atts=[("Hannah_Boateng_CV.pdf", rd(f"{tmp}/Hannah_Boateng_CV.pdf"), pdf)]), False),
        (rep("chen", "2026-10-26T09:14:00", "Hi Alex,\n\nThank you! I'm free on Tuesday or Wednesday that week, any time of day.\n\n"
             "Best,\nChen", "rep_chen"), True),
        (X.mail(("Kofi Mensah", "kofi.mensah@fernleaf.io"), [ME], "CSM interview feedback",
                "Alex - feedback for the two CSM interviews is in HireDesk notes. Happy to move Jade to final round.\nKofi",
                when("2026-10-27T10:10:00"), mid("kofi", "fernleaf.io")), True),
        (rep("amara", "2026-10-27T18:40:00", "Hi Alex,\n\nWednesday would be best for me - any time works that day.\n\nThanks,\nAmara",
             "rep_amara1"), True),
        (X.mail(("Daniel Okafor", A["okafor"]["email"]), [ME], "Re: Application for Data Analyst - Daniel Okafor",
                "Hi Alex,\n\nSorry - I realised my CV left out the SQL work from my placement year and final-year project. "
                "Please use this updated version instead of the one I sent last week.\n\nThanks,\nDaniel",
                when("2026-10-28T08:12:00"), mid("app_okafor2", "outlook.com"), irt=ids["app_okafor"],
                atts=[("Daniel_Okafor_CV_updated.pdf", rd(f"{tmp}/Daniel_Okafor_CV_updated.pdf"), pdf)]), True),
        (rep("leo", "2026-10-28T12:05:00", "Hello Alex,\n\nGreat to hear! I could do Monday afternoon, Tuesday afternoon or Thursday "
             "morning.\n\nKind regards,\nLeo", "rep_leo"), True),
        (X.mail(("Recruiting Brief", "news@recruitingbrief.co.uk"), [ME], "The Recruiting Brief: skills-based hiring in 2027",
                "This week: skills-based hiring, the new right-to-work checks, and the salary survey.\n\nUnsubscribe",
                when("2026-10-29T07:00:00"), mid("news", "recruitingbrief.co.uk")), True),
        (rep("amara", "2026-10-29T08:22:00", "Hi Alex,\n\nSorry to change things - something has come up and Wednesday is now "
             "impossible for me. Could we do Thursday afternoon or Friday morning instead?\n\nApologies,\nAmara", "rep_amara2"), True),
        (X.mail(BEN, [ME], "PD panel interviews next week",
                "Hi Alex,\n\nThanks for chasing the Product Designer candidates. Ines and I can do all the REQ-027 slots in "
                "HireDesk except two: Ines is in London all day on Monday 2 November, and I'm at the dentist on Tuesday "
                "morning (3 November) - so no Monday slots and nothing on Tuesday morning.\n\n"
                "Please book each candidate into the earliest slot that works for them. If two people want the same slot, "
                "whoever replied to you first gets it. Send each of them an invite with the date, time and the video link "
                "from HireDesk, and fill in our panel sheet (attached) so we know who we're seeing when.\n\n"
                "Dan Price is already booked for Thursday afternoon.\n\nCheers,\nBen", when("2026-10-29T13:47:00"), mid("ben", "fernleaf.io"),
                atts=[("PD_panel_schedule.xlsx", rd(f"{tmp}/PD_panel_schedule.xlsx"), XLSX_MIME)]), True),
        (X.mail(("IT Service Desk", "it@fernleaf.io"), [ME], "Your password expires in 5 days",
                "Your Fernleaf password expires on 4 November. Change it at https://id.fernleaf.io.", when("2026-10-30T07:30:00"),
                mid("it", "fernleaf.io")), True),
        (rep("sofia", "2026-10-30T08:50:00", "Dear Alex,\n\nThank you so much for the invitation. I've just accepted an offer "
             "elsewhere, so please withdraw my application for the Product Designer role.\n\nAll the best,\nSofia", "rep_sofia"), True),
    ]
    from email.utils import parsedate_to_datetime
    make_profile(f"{d}/thunderbird-profile.tar.gz", ME, {
        "Inbox": [(m, parsedate_to_datetime(m["Date"]), u) for m, u in inbox],
        "Sent": [(m, parsedate_to_datetime(m["Date"]), False) for m, _ in sent]})

    # ---- database
    people = [  # name, email, phone, location, source, created, [(req code, stage, applied, scores, rtw, reason, notes)]
        ("Hannah Boateng", "hannah.boateng@outlook.com", "07700 900877", "Leeds", "Careers page", "2026-04-14",
         [("REQ-029", "Rejected", "2026-04-14", None, None, "Not progressed after phone screen - keep on file", "Strong analytical answers; less client-facing experience.")]),
        ("Oliver Grant", "oliver.grant@gmail.com", "07700 900101", "Leeds", "LinkedIn", "2026-10-13",
         [("REQ-031", "Phone screen", "2026-10-13", (2, 1, 1, 1), "Yes", "", "Screened by Grace.")]),
        ("Sara Haddad", "sara.haddad@yahoo.co.uk", "07700 900102", "Bradford", "Careers page", "2026-10-14",
         [("REQ-031", "Rejected", "2026-10-14", (1, 1, 0, 1), "Yes", "Below threshold", "")]),
        ("Lucia Romano", "lucia.romano@protonmail.com", "07700 900103", "York", "Agency", "2026-03-18",
         [("REQ-024", "Rejected", "2026-03-18", None, None, "Position filled", "")]),
        ("Dan Price", "dan.price.design@gmail.com", "07700 900104", "Leeds", "Referral", "2026-09-08",
         [("REQ-027", "Interview scheduled", "2026-09-08", None, None, "", "Portfolio: fintech onboarding flows.")]),
        ("Leo Fischer", PD["leo"][1], "07700 900105", "Leeds", "Careers page", "2026-09-10",
         [("REQ-027", "Interview - to schedule", "2026-09-10", None, None, "", "Phone screen 21 Oct - strong systems thinking.")]),
        ("Amara Nwosu", PD["amara"][1], "07700 900106", "Manchester", "LinkedIn", "2026-09-12",
         [("REQ-027", "Interview - to schedule", "2026-09-12", None, None, "", "Phone screen 22 Oct.")]),
        ("Chen Wei", PD["chen"][1], "07700 900107", "Leeds", "Careers page", "2026-09-15",
         [("REQ-027", "Interview - to schedule", "2026-09-15", None, None, "", "Phone screen 20 Oct - great research portfolio.")]),
        ("Sofia Marín", PD["sofia"][1], "07700 900108", "Sheffield", "Referral", "2026-09-17",
         [("REQ-027", "Interview - to schedule", "2026-09-17", None, None, "", "Phone screen 22 Oct.")]),
        ("Maya Kerr", "maya.kerr@gmail.com", "07700 900109", "Leeds", "Careers page", "2026-09-09",
         [("REQ-027", "Rejected", "2026-09-09", None, None, "Portfolio not a fit", "")]),
        ("Jonas Berg", "jonas.berg@outlook.com", "07700 900110", "Harrogate", "LinkedIn", "2026-10-20",
         [("REQ-027", "Phone screen", "2026-10-20", None, None, "", "")]),
        ("Ruth Adeyemi", "ruth.adeyemi@gmail.com", "07700 900111", "Leeds", "Careers page", "2026-10-25",
         [("REQ-027", "Applied", "2026-10-25", None, None, "", "")]),
        ("Jade Thornton", "jade.thornton@gmail.com", "07700 900112", "Leeds", "LinkedIn", "2026-09-30",
         [("REQ-029", "Interview scheduled", "2026-09-30", None, None, "", "")]),
        ("Marcus Lee", "marcus.lee@outlook.com", "07700 900113", "Leeds", "Careers page", "2026-10-02",
         [("REQ-029", "Interview - to schedule", "2026-10-02", None, None, "", "")]),
        ("Ellie Shaw", "ellie.shaw@gmail.com", "07700 900114", "Wakefield", "Agency", "2026-10-05",
         [("REQ-029", "Phone screen", "2026-10-05", None, None, "", "")]),
        ("Priya Natarajan", "priya.natarajan@gmail.com", "07700 900115", "Leeds", "LinkedIn", "2026-10-11",
         [("REQ-029", "Applied", "2026-10-11", None, None, "", "")]),
        ("Ben Whitaker", "ben.whitaker@icloud.com", "07700 900116", "Huddersfield", "Careers page", "2026-04-20",
         [("REQ-029", "Withdrawn", "2026-04-20", None, None, "Relocated", "")]),
        ("Tomasz Nowak", "tomasz.nowak@gmail.com", "07700 900117", "Leeds", "Careers page", "2026-03-11",
         [("REQ-024", "Hired", "2026-03-11", None, None, "", "Started 1 June.")]),
        ("Aisha Rahman", "aisha.rahman@outlook.com", "07700 900118", "Bradford", "LinkedIn", "2026-03-14",
         [("REQ-024", "Rejected", "2026-03-14", None, None, "Below threshold", ""), ("REQ-029", "Rejected", "2026-05-02", None, None, "Salary expectations", "")]),
        ("George Fenwick", "g.fenwick@btinternet.com", "07700 900119", "Leeds", "Agency", "2026-03-20",
         [("REQ-024", "Withdrawn", "2026-03-20", None, None, "Accepted counter-offer", "")]),
        ("Holly Grant", "holly.grant@gmail.com", "07700 900120", "Otley", "Careers page", "2026-02-15",
         [("REQ-022", "Hired", "2026-02-15", None, None, "", "")]),
        ("Femi Adebayo", "femi.adebayo@gmail.com", "07700 900121", "Leeds", "Careers page", "2026-02-18",
         [("REQ-022", "Rejected", "2026-02-18", None, None, "Position filled", "")]),
        ("Rachel Doyle", "rachel.doyle@gmail.com", "07700 900122", "Leeds", "Referral", "2026-02-20",
         [("REQ-022", "Rejected", "2026-02-20", None, None, "Position filled", "")]),
        ("Kieran Walsh", "kieran.walsh@outlook.com", "07700 900123", "Leeds", "LinkedIn", "2026-10-15",
         [("REQ-031", "Applied", "2026-10-15", None, None, "", "Applied via LinkedIn - Grace to screen.")]),
        ("Daniela Ortiz", "daniela.ortiz@gmail.com", "07700 900124", "Leeds", "Careers page", "2026-10-16",
         [("REQ-029", "Applied", "2026-10-16", None, None, "", "")]),
    ]
    rows = {"settings": [{"key": "business_date", "value": BUSINESS_DATE}],
            "users": [{"id": 1, "username": "alex", "name": "Alex Moreno", "role": "talent", "salt": "fx41",
                       "pw": X.pw_hash("Fernleaf!Talent", "fx41"), "last_req": "REQ-029"},
                      {"id": 2, "username": "grace", "name": "Grace Liu", "role": "manager", "salt": "gl08",
                       "pw": X.pw_hash("Grace#Data2026", "gl08"), "last_req": "REQ-031"},
                      {"id": 3, "username": "ben", "name": "Ben Okoro", "role": "manager", "salt": "bo77",
                       "pw": X.pw_hash("Ben@Design!", "bo77"), "last_req": "REQ-027"}],
            "requisitions": [{"id": i, "code": c, "title": t, "location": l, "hiring_manager": hm, "opened": o, "status": s}
                             for i, c, t, l, hm, o, s in REQS],
            "candidates": [], "applications": [], "slots": [], "audit": []}
    app_ids, cand_ids = {}, {}
    for cid, (name, email, phone, loc, src, created, apps) in enumerate(people, 1):
        cand_ids[email] = cid
        rows["candidates"].append({"id": cid, "name": name, "email": email, "phone": phone, "location": loc, "source": src,
                                   "created_at": created + " 10:00:00", "created_by": "grace" if "REQ-031" in str(apps) else "alex"})
        for code, stage, applied, sc, rtw, reason, notes in apps:
            aid = len(rows["applications"]) + 1
            app_ids[(email, code)] = aid
            rows["applications"].append({"id": aid, "candidate_id": cid, "req_id": RID[code], "stage": stage, "applied_on": applied,
                                         "score_sql": sc[0] if sc else None, "score_code": sc[1] if sc else None,
                                         "score_bi": sc[2] if sc else None, "score_degree": sc[3] if sc else None,
                                         "rtw": rtw, "reason": reason, "notes": notes, "updated_at": applied + " 16:00:00"})
    for sid, (key, start, booked) in enumerate(SLOTS, 1):
        rows["slots"].append({"id": sid, "req_id": RID["REQ-027"], "start": start, "minutes": 60, "panel": "Ben Okoro, Ines Duarte",
                              "location": "Video call (Fernleaf Meet)", "video_link": f"https://meet.fernleaf.io/j/{LINKS[key]}",
                              "application_id": app_ids[("dan.price.design@gmail.com", "REQ-027")] if booked else None,
                              "booked_by": "alex" if booked else None, "booked_at": "2026-10-22 15:31:09" if booked else None})
    for start, booked in (("2026-11-03 11:00", "jade.thornton@gmail.com"), ("2026-11-04 15:00", None), ("2026-11-05 11:30", None)):
        rows["slots"].append({"id": len(rows["slots"]) + 1, "req_id": RID["REQ-029"], "start": start, "minutes": 45,
                              "panel": "Kofi Mensah, Dee Archer", "location": "Leeds office, room Larch",
                              "video_link": "-", "application_id": app_ids[(booked, "REQ-029")] if booked else None,
                              "booked_by": "alex" if booked else None, "booked_at": "2026-10-27 11:02:44" if booked else None})
    rows["audit"] = [{"ts": "2026-10-22 15:31:09", "user": "alex", "action": "interview booked", "detail": "Dan Price REQ-027 2026-11-05 15:00"},
                     {"ts": "2026-10-27 11:02:44", "user": "alex", "action": "interview booked", "detail": "Jade Thornton REQ-029 2026-11-03 11:00"}]
    X.seed_db(f"{d}/hiredesk_seed.db", SCHEMA, rows)

    slot_ids = {key: i for i, (key, _, _) in enumerate(SLOTS, 1)}
    latest = {"leo": ids["rep_leo"], "amara": ids["rep_amara2"], "chen": ids["rep_chen"]}
    exp = {
        "me": ME[1], "grace": GRACE[1], "ben": BEN[1], "msg": ids,
        "seed_max": {"candidates": len(rows["candidates"]), "applications": len(rows["applications"])},
        "applicants": [{"name": a["name"], "email": a["email"], "scores": a["scores"], "rtw": a["rtw"], "total": sum(a["scores"]),
                        "stage": a["stage"], "existing_id": cand_ids.get(a["email"])} for a in APPLICANTS],
        "shortlist": [a["name"] for a in APPLICANTS if a["stage"] == "Phone screen"],
        "bookings": [{"who": k, "name": PD[k][0], "email": PD[k][1], "slot": slot_ids[BOOK[k]], "slot_key": BOOK[k],
                      "start": dict((s[0], s[1]) for s in SLOTS)[BOOK[k]], "label": date_label(dict((s[0], s[1]) for s in SLOTS)[BOOK[k]]),
                      "link": LINKS[BOOK[k]], "app_id": app_ids[(PD[k][1], "REQ-027")], "latest": latest[k]} for k in ("chen", "leo", "amara")],
        "withdrawn": {"name": PD["sofia"][0], "email": PD["sofia"][1], "app_id": app_ids[(PD["sofia"][1], "REQ-027")]},
        "blocked_slots": [slot_ids["S1"], slot_ids["S2"]],
        "dan": {"slot": slot_ids["S6"], "app_id": app_ids[("dan.price.design@gmail.com", "REQ-027")]},
        "slot_labels": {str(slot_ids[k]): date_label(s) for k, s, _ in SLOTS},
    }
    json.dump(exp, open(f"{d}/expected.json", "w"), indent=1)


SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, role TEXT, salt TEXT, pw TEXT, last_req TEXT);
CREATE TABLE requisitions(id INTEGER PRIMARY KEY, code TEXT UNIQUE, title TEXT, location TEXT, hiring_manager TEXT, opened TEXT, status TEXT);
CREATE TABLE candidates(id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT, location TEXT, source TEXT, created_at TEXT, created_by TEXT);
CREATE TABLE applications(id INTEGER PRIMARY KEY, candidate_id INTEGER, req_id INTEGER, stage TEXT, applied_on TEXT,
    score_sql INTEGER, score_code INTEGER, score_bi INTEGER, score_degree INTEGER, rtw TEXT, reason TEXT, notes TEXT, updated_at TEXT);
CREATE TABLE slots(id INTEGER PRIMARY KEY, req_id INTEGER, start TEXT, minutes INTEGER, panel TEXT, location TEXT, video_link TEXT,
    application_id INTEGER, booked_by TEXT, booked_at TEXT);
CREATE TABLE sessions(sid TEXT PRIMARY KEY, user_id INTEGER, created TEXT, state TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, action TEXT, detail TEXT);
"""

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp())
