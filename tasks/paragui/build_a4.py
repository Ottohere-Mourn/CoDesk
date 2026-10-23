"""A4 - Tidewater Community Libraries website: one repo, one working tree + index, one dev server (port 8134).

A (pga4closures): "Holiday closures" page /closures from the council's scanned festive-opening notice.
B (pga4fees):     "Fees & charges" page /fees from a phone photo of the laminated fees sheet.
By the repo's CONTRIBUTING.md every new page touches the same shared files: tidewater/routes.py,
tidewater/templates/nav.html, tests/test_routes.py, CHANGELOG.md (Unreleased > Added) and README.md (Pages table).
Each task must commit exactly its own change.
"""
import datetime as dt
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_devrepo import dev_sh, make_repo  # noqa: E402
from lib_x import Page, _degrade, photo_jpg  # noqa: E402

PORT = 8134
NAME = "tidewater-libraries"
ROSA = ("Rosa Delgado", "rosa.delgado@tidewater-libraries.example")
OWEN = ("Owen Pryce", "owen@pryce-digital.example")
MAUREEN = ("Maureen Achebe", "maureen.achebe@tidewater-libraries.example")

BRANCHES = ["Central Library", "Millbrook Library", "Eastgate Library"]

# ground truth of the notice (after the handwritten correction on Eastgate 30 Dec)
CLOSURES = [
    ("Central Library", "2026-12-24", "09:00-13:00"),
    ("Central Library", "2026-12-25", "closed"),
    ("Central Library", "2026-12-26", "closed"),
    ("Central Library", "2026-12-31", "09:00-16:00"),
    ("Central Library", "2027-01-01", "closed"),
    ("Millbrook Library", "2026-12-24", "closed"),
    ("Millbrook Library", "2026-12-26", "closed"),
    ("Millbrook Library", "2026-12-29", "closed"),
    ("Millbrook Library", "2026-12-30", "10:00-14:00"),
    ("Millbrook Library", "2027-01-02", "closed"),
    ("Eastgate Library", "2026-12-25", "closed"),
    ("Eastgate Library", "2026-12-28", "closed"),
    ("Eastgate Library", "2026-12-30", "10:00-13:00"),
    ("Eastgate Library", "2027-01-01", "closed"),
]

# (label on the sheet, fee in GBP, per, keyword regex the checker uses to identify the entry)
FEES = [
    ("Overdue items - adults", 0.25, "day", r"overdue|late"),
    ("Maximum overdue charge", 6.00, "item", r"max|cap|limit"),
    ("Overdue items - children & teens", 0.0, "item", r"child|teen|junior|young"),
    ("Reservations (any item)", 0.80, "item", r"reserv|request|hold"),
    ("Inter-library loan request", 4.50, "item", r"inter.?library|\bill\b"),
    ("Replacement library card", 2.50, "card", r"card"),
    ("Printing / photocopying A4 black & white", 0.15, "page", r"black|b\s*&\s*w|b/w|mono|gr[ae]y"),
    ("Printing / photocopying A4 colour", 0.50, "page", r"colou?r"),
    ("Scan to email", 0.0, "scan", r"scan"),
    ("Meeting room hire (community groups)", 12.00, "hour", r"room|hire"),
    ("DVD loan", 1.50, "week", r"dvd|film"),
]

A_MARK = {"routes": "/closures", "nav": "/closures", "tests": "/closures", "readme": "/closures", "changelog": r"closure"}
B_MARK = {"routes": "/fees", "nav": "/fees", "tests": "/fees", "readme": "/fees", "changelog": r"\bfees?\b|charges"}

# ------------------------------------------------------------------ repo sources
HOURS = []
for day, h in [("Monday", "09:00-18:00"), ("Tuesday", "09:00-18:00"), ("Wednesday", "09:00-18:00"),
               ("Thursday", "09:00-19:30"), ("Friday", "09:00-18:00"), ("Saturday", "09:00-16:00"),
               ("Sunday", "closed")]:
    HOURS.append({"branch": "Central Library", "day": day, "hours": h})
for day, h in [("Monday", "closed"), ("Tuesday", "10:00-17:00"), ("Wednesday", "10:00-17:00"),
               ("Thursday", "10:00-17:00"), ("Friday", "10:00-17:00"), ("Saturday", "10:00-16:00"), ("Sunday", "closed")]:
    HOURS.append({"branch": "Millbrook Library", "day": day, "hours": h})
for day, h in [("Monday", "10:00-16:00"), ("Tuesday", "closed"), ("Wednesday", "10:00-16:00"), ("Thursday", "closed"),
               ("Friday", "10:00-16:00"), ("Saturday", "10:00-13:00"), ("Sunday", "closed")]:
    HOURS.append({"branch": "Eastgate Library", "day": day, "hours": h})

BRANCH_DATA = [
    {"name": "Central Library", "address": "14 Harbour Street, Tidewater TW1 2AB", "phone": "01632 960 410",
     "access": "Step-free entrance on Quay Lane, lift to all floors, hearing loop at the help desk."},
    {"name": "Millbrook Library", "address": "Millbrook Community Centre, Fenwick Road, Tidewater TW4 7QD",
     "phone": "01632 960 422", "access": "Ground floor only, accessible toilet in the community centre."},
    {"name": "Eastgate Library", "address": "2 Eastgate Parade, Tidewater TW6 1LP", "phone": "01632 960 435",
     "access": "Step-free, small reading room; parking for blue badge holders behind the parade."},
]

EVENTS = [
    {"date": "2026-11-03", "time": "10:30", "branch": "Central Library", "title": "Baby Rhyme Time",
     "text": "Songs and rhymes for babies and their grown-ups. Free, no booking."},
    {"date": "2026-11-05", "time": "18:00", "branch": "Central Library", "title": "Local history talk: the Tidewater ferries",
     "text": "Illustrated talk by the Tidewater Heritage Society."},
    {"date": "2026-11-07", "time": "10:00", "branch": "Millbrook Library", "title": "Lego club",
     "text": "Build, share and show off. Ages 6-11."},
    {"date": "2026-11-11", "time": "14:00", "branch": "Eastgate Library", "title": "Digital drop-in",
     "text": "Help with phones, tablets and online forms."},
    {"date": "2026-11-14", "time": "11:00", "branch": "Central Library", "title": "Author visit: Hannah Lowe",
     "text": "Reading and signing. Booking via the help desk."},
    {"date": "2026-11-19", "time": "18:30", "branch": "Millbrook Library", "title": "Book group",
     "text": "This month: 'The Lighthouse Keepers'."},
]

INIT_PY = '"""Tidewater Community Libraries - public website (Python standard library only)."""\n__version__ = "1.3.0"\n'

LAYOUT_PY = '''"""Shared page layout: templates/base.html with the menu from templates/nav.html."""
import json
import os
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))


def template(name):
    with open(os.path.join(HERE, 'templates', name), encoding='utf-8') as f:
        return f.read()


def load_data(name):
    """Contents of tidewater/data/<name> (JSON)."""
    with open(os.path.join(HERE, 'data', name), encoding='utf-8') as f:
        return json.load(f)


def layout(title, body, active='/'):
    nav = template('nav.html').replace('href="%s"' % active, 'href="%s" class="on"' % active, 1)
    return (template('base.html').replace('{{title}}', escape(title)).replace('{{nav}}', nav)
            .replace('{{body}}', body))
'''

ROUTES_PY = '''"""URL routes: path -> page module in tidewater/pages/ (each module has render() -> HTML).

Keep the paths in alphabetical order. Every page also needs a menu link in templates/nav.html and an entry in
tests/test_routes.py (see CONTRIBUTING.md). The server reads this table at start-up: restart it after changes.
"""

ROUTES = {
    '/': 'home',
    '/branches': 'branches',
    '/events': 'events',
    '/hours': 'hours',
}
'''

SERVER_PY = '''"""Tidewater Libraries website - development server (Python stdlib only).

    python3 -m tidewater.server --port 8134      (or ./dev.sh start|stop|restart)

The route table (tidewater/routes.py) is read once at start-up: restart the server after adding a page.
"""
import argparse
import importlib
import os
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .layout import layout
from .routes import ROUTES

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')


def render(path):
    """(status, html) for a path."""
    name = ROUTES.get(path)
    if not name:
        return 404, layout('Page not found', '<h1>Page not found</h1><p><a href="/">Home</a></p>', '')
    try:
        mod = importlib.import_module('tidewater.pages.' + name)
        return 200, mod.render()
    except Exception:
        traceback.print_exc()
        return 500, layout('Error', '<h1>Something went wrong</h1><pre>%s</pre>' % traceback.format_exc()[-1500:], '')


class Handler(BaseHTTPRequestHandler):
    server_version = 'TidewaterDev/1.3'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\\n' % (self.log_date_time_string(), fmt % args))

    def send(self, status, body, ctype='text/html; charset=utf-8'):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/static/style.css':
            with open(os.path.join(STATIC, 'style.css'), 'rb') as f:
                return self.send(200, f.read(), 'text/css')
        status, html = render(path)
        return self.send(status, html)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', type=int, default=8134)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('Tidewater Libraries dev server on http://127.0.0.1:%d/' % args.port, flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
'''

PAGES_INIT = '"""One module per page; each has render() -> HTML (see tidewater/routes.py)."""\n'

HOME_PY = '''"""Home page."""
from ..layout import layout, load_data


def render():
    events = load_data('events.json')[:3]
    items = ''.join('<li><strong>%s</strong> - %s, %s</li>' % (e['title'], e['branch'], e['date']) for e in events)
    body = ('<h1>Welcome to Tidewater Community Libraries</h1>'
            '<p class="lead">Three libraries, one card: borrow books, e-books, DVDs and use our computers and '
            'meeting rooms for free.</p><h2>Coming up</h2><ul>%s</ul>'
            '<p><a href="/events">All events</a> &middot; <a href="/hours">Opening hours</a></p>' % items)
    return layout('Home', body, '/')
'''

HOURS_PY = '''"""Opening hours page (data: tidewater/data/hours.json)."""
from html import escape

from ..layout import layout, load_data


def render():
    rows = load_data('hours.json')
    branches = []
    for r in rows:
        if r['branch'] not in branches:
            branches.append(r['branch'])
    body = '<h1>Opening hours</h1>'
    for b in branches:
        body += '<h2>%s</h2><table class="hours">' % escape(b)
        for r in rows:
            if r['branch'] == b:
                body += '<tr><td>%s</td><td>%s</td></tr>' % (escape(r['day']), escape(r['hours']))
        body += '</table>'
    return layout('Opening hours', body, '/hours')
'''

BRANCHES_PY = '''"""Branches page (data: tidewater/data/branches.json)."""
from html import escape

from ..layout import layout, load_data


def render():
    body = '<h1>Our branches</h1>'
    for b in load_data('branches.json'):
        body += ('<div class="card"><h2>%s</h2><p>%s<br>Phone %s</p><p class="muted">%s</p></div>'
                 % (escape(b['name']), escape(b['address']), escape(b['phone']), escape(b['access'])))
    return layout('Branches', body, '/branches')
'''

EVENTS_PY = '''"""What's on page (data: tidewater/data/events.json)."""
import datetime
from html import escape

from ..layout import layout, load_data


def render():
    body = '<h1>What&#39;s on</h1><table class="events">'
    for e in sorted(load_data('events.json'), key=lambda e: (e['date'], e['time'])):
        d = datetime.date.fromisoformat(e['date'])
        body += ('<tr><td>%s %d %s</td><td>%s</td><td><strong>%s</strong><br><span class="muted">%s</span></td>'
                 '<td>%s</td></tr>' % (d.strftime('%A'), d.day, d.strftime('%B'), e['time'], escape(e['title']),
                                       escape(e['text']), escape(e['branch'])))
    return layout("What's on", body + '</table>', '/events')
'''

BASE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{{title}} &middot; Tidewater Libraries</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><header><div class="wrap"><a class="logo" href="/">Tidewater Libraries</a>
{{nav}}</div></header>
<main class="wrap">{{body}}</main>
<footer class="wrap">Tidewater Community Libraries &middot; a service of Tidewater Borough Council &middot; development server</footer>
</body></html>
"""

NAV_HTML = """<nav>
  <a href="/">Home</a>
  <a href="/events">What's on</a>
  <a href="/hours">Opening hours</a>
  <a href="/branches">Branches</a>
</nav>
"""

STYLE_CSS = """* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.55 "DejaVu Sans", Arial, sans-serif; color: #1f2a33; background: #f5f7f8; }
.wrap { max-width: 1000px; margin: 0 auto; padding: 0 20px; }
header { background: #0f4c5c; color: #fff; }
header .wrap { display: flex; align-items: center; justify-content: space-between; min-height: 62px; flex-wrap: wrap; }
.logo { color: #fff; font: bold 22px Georgia, serif; text-decoration: none; }
nav a { color: #d7eef2; margin-left: 20px; text-decoration: none; }
nav a.on { color: #fff; border-bottom: 2px solid #f2b134; }
h1 { font: bold 30px Georgia, serif; margin: 28px 0 10px; } h2 { margin: 24px 0 8px; font-size: 20px; }
.lead { color: #4a5a66; font-size: 18px; }
table { border-collapse: collapse; background: #fff; margin: 8px 0 16px; }
td, th { padding: 7px 14px; border-bottom: 1px solid #e1e7ea; text-align: left; vertical-align: top; }
.card { background: #fff; border: 1px solid #dfe6e9; border-radius: 8px; padding: 6px 18px; margin: 14px 0; }
.muted { color: #6b7b86; font-size: 14px; }
footer { color: #8a99a3; font-size: 13px; padding: 40px 20px; }
"""

TEST_ROUTES = """import re
import unittest

from tidewater.layout import template
from tidewater.routes import ROUTES
from tidewater.server import render

# Every page of the website, in alphabetical order. Add new pages here (see CONTRIBUTING.md).
EXPECTED_PATHS = [
    '/',
    '/branches',
    '/events',
    '/hours',
]


def menu_links():
    return re.findall(r'href="([^"]+)"', template('nav.html'))


class RoutesTest(unittest.TestCase):
    def test_routes_are_the_expected_pages(self):
        self.assertEqual(sorted(ROUTES), sorted(EXPECTED_PATHS))

    def test_every_page_renders(self):
        for path in ROUTES:
            status, html = render(path)
            self.assertEqual(status, 200, path)
            self.assertIn('<nav>', html, path)

    def test_menu_links_resolve(self):
        for link in menu_links():
            self.assertIn(link, ROUTES)

    def test_every_page_is_in_the_menu(self):
        links = set(menu_links())
        for path in ROUTES:
            self.assertIn(path, links)

    def test_unknown_page(self):
        self.assertEqual(render('/no-such-page')[0], 404)


if __name__ == '__main__':
    unittest.main()
"""

TEST_DATA = """import datetime
import re
import unittest

from tidewater.layout import load_data

BRANCHES = {'Central Library', 'Millbrook Library', 'Eastgate Library'}


class DataTest(unittest.TestCase):
    def test_hours(self):
        rows = load_data('hours.json')
        self.assertEqual({r['branch'] for r in rows}, BRANCHES)
        for r in rows:
            self.assertRegex(r['hours'], r'^(closed|\\d\\d:\\d\\d-\\d\\d:\\d\\d)$')

    def test_events(self):
        for e in load_data('events.json'):
            datetime.date.fromisoformat(e['date'])
            self.assertIn(e['branch'], BRANCHES)
            self.assertRegex(e['time'], r'^\\d\\d:\\d\\d$')


if __name__ == '__main__':
    unittest.main()
"""

README = """# Tidewater Community Libraries - website

Public website of Tidewater Community Libraries (Central, Millbrook and Eastgate). Python 3 standard library only,
no dependencies. Maintained by volunteers; the original version was built by Pryce Digital.

## Run it

    ./dev.sh start        # also: stop, restart, status, log

then open http://127.0.0.1:8134/ . The dev server reads the route table at start-up and does not reload code:
run `./dev.sh restart` after adding or changing pages.

## Tests

    python3 -m unittest

## Pages

| path | page | data file |
|---|---|---|
| `/` | Home | `events.json` (next three events) |
| `/branches` | Branches | `branches.json` |
| `/events` | What's on | `events.json` |
| `/hours` | Opening hours | `hours.json` |

## Layout

| path | what |
|---|---|
| `tidewater/routes.py` | URL -> page module |
| `tidewater/pages/` | one module per page (`render()` returns the HTML) |
| `tidewater/data/` | page content as JSON |
| `tidewater/templates/` | `base.html` page frame, `nav.html` the menu |
| `docs/requests/` | change requests from library staff |
"""

CONTRIBUTING = """# Contributing

Small site, few rules - but please follow them, the council's web team reviews our history every quarter.

## Adding a page

1. Content goes into a JSON data file `tidewater/data/<page>.json`; use the format given in the request (look at
   `hours.json` for the style).
2. Page module `tidewater/pages/<page>.py` with a `render()` function (copy `pages/hours.py`).
3. Register the path in `tidewater/routes.py` (alphabetical order).
4. Link it in the menu, `tidewater/templates/nav.html`.
5. Add the path to `EXPECTED_PATHS` in `tests/test_routes.py` (alphabetical order).
6. Add a row to the *Pages* table in `README.md`.
7. Add a line to `CHANGELOG.md` under `## [Unreleased]` -> `### Added` (fixes go under `### Fixed`).

## Before committing

- `python3 -m unittest` must pass.
- Restart the dev server (`./dev.sh restart`) and look at the page in a browser.
- **One commit per change request**, containing that change and nothing else, with the commit message the
  requester asked for. Do not commit `logs/` or `.devserver.pid`.
"""

CHANGELOG = """# Changelog

All notable changes to the Tidewater Libraries website. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Branches page with addresses, phone numbers and accessibility information.

### Fixed
- What's on: events are listed in date order again.

## [1.3.0] - 2026-10-12

### Added
- What's on page (events from `events.json`).
- Opening hours page for all three branches.

## [1.2.0] - 2026-06-02

### Changed
- New colour scheme from the council's brand guidelines.
"""

CLOSURES_MD = """# Request: holiday closures page

From: Maureen Achebe (Library Services Manager) - 2 November 2026

The council has confirmed the Christmas and New Year opening for all three branches. Their notice is scanned in
`closures-notice-2026.png` (this folder) - please note my handwritten correction on it. Can we have a
"Holiday closures" page at `/closures`, linked from the menu, so people can check before they travel?

Data format for `tidewater/data/closures.json` - one entry per branch and day, like `hours.json`:

    {"branch": "Central Library", "date": "2026-12-24", "hours": "09:00-13:00"}

- `branch`: the branch name exactly as in `hours.json`
- `date`: ISO date (the notice covers December 2026 and January 2027)
- `hours`: `"closed"`, or the shortened opening time as `"HH:MM-HH:MM"`

Only the days listed on the notice; every other day is normal opening.

Commit message please: `Add holiday closures page`
"""

FEES_MD = """# Request: fees and charges page

From: Priya Nair (front desk, Central Library) - 2 November 2026

People keep phoning to ask what things cost. Could the charges from the laminated sheet on the front desk go on the
website? Photo attached: `fees-sheet.jpg` (this folder). The pen correction on it is right - colour printing went
down last month. We'd like a "Fees & charges" page at `/fees`, linked from the menu.

Data format for `tidewater/data/fees.json` - one entry per line on the sheet:

    {"item": "Reservations (any item)", "fee": 0.80, "per": "item"}

- `item`: the description as on the sheet
- `fee`: the charge in pounds as a number (`0` for free)
- `per`: what the charge is per (`item`, `day`, `page`, `hour`, `week`, ...)

Commit message please: `Add fees and charges page`
"""

GITIGNORE = "__pycache__/\n*.pyc\nlogs/\n.devserver.pid\n"


# ------------------------------------------------------------------ GUI-only inputs
def nice(d):
    x = dt.date.fromisoformat(d)
    return f"{x.strftime('%A')} {x.day} {x.strftime('%B')}"


def notice_png(path):
    p = Page(1240, 1500)
    p.rect((60, 50, 1180, 160), outline=(15, 76, 92), width=3, fill=(232, 242, 244))
    p.text(90, 70, "TIDEWATER BOROUGH COUNCIL", size=34, bold=True, fill=(15, 76, 92))
    p.text(90, 116, "Library & Information Service  -  Civic Offices, Quay Road, Tidewater TW1 1AA", size=19)
    p.text(80, 200, "Festive opening arrangements 2026/27", size=36, bold=True, serif=True)
    p.text(80, 256, "All libraries open as normal on days not listed below. Online services and the book drops", size=20)
    p.text(80, 284, "at Central and Millbrook remain available throughout.", size=20)
    y = 340
    groups = {b: [c for c in CLOSURES if c[0] == b] for b in BRANCHES}
    shown = dict(groups)
    # the printed notice still says Eastgate is closed on 30 Dec; Maureen corrected it by hand
    for b in BRANCHES:
        p.text(80, y, b + ("  (Harbour Street)" if b.startswith("Central") else ""), size=26, bold=True)
        y += 44
        rows = []
        for _, d, h in shown[b]:
            year = d[:4]
            label = f"{nice(d)} {year}"
            text = "Closed" if h == "closed" else "Open " + h.replace("-", " - ")
            if b.startswith("Eastgate") and d == "2026-12-30":
                text = "Closed"
            rows.append((label, text))
        y0 = y
        y = p.table(100, y, [("Date", 520, "l"), ("Opening", 420, "l")], rows, size=22, row_h=40)
        if b.startswith("Eastgate"):
            idx = [d for _, d, _ in shown[b]].index("2026-12-30")
            ry = y0 + 40 * (idx + 1) + 20
            p.d.line((628, ry, 720, ry), fill=(20, 40, 120), width=4)
            p.handwriting(760, ry - 22, "open 10:00-13:00!  M.A.", size=30, seed=4)
        y += 34
    p.text(80, y + 10, "Normal opening resumes on Monday 4 January 2027 at all branches.", size=21, bold=True)
    p.text(80, y + 60, "Ref LIS/OPN/26-27  -  issued 30 October 2026  -  Head of Library & Information Service", size=17,
           fill=(90, 90, 90))
    im = _degrade(p.im, random.Random(41), angle=0.6)
    im.save(path, "PNG", optimize=True)


def fees_jpg(path):
    p = Page(1100, 1500, bg=(253, 253, 248))
    p.rect((40, 40, 1060, 1460), outline=(15, 76, 92), width=6)
    p.text(80, 80, "Tidewater Libraries", size=40, bold=True, fill=(15, 76, 92))
    p.text(80, 140, "Fees & charges", size=54, bold=True, serif=True)
    p.text(80, 216, "from 1 April 2026", size=24, fill=(80, 80, 80))
    y = 290
    for label, fee, per, _ in FEES:
        if fee == 0:
            price = "free"
        else:
            price = (f"{int(round(fee * 100))}p" if fee < 1 else f"£{fee:.2f}")
        if "colour" in label:
            price = "60p"  # printed price; corrected by hand below
        perlab = {"day": "per item per day", "item": "per item", "card": "", "page": "per page", "scan": "",
                  "hour": "per hour", "week": "per week"}[per]
        p.text(80, y, label, size=29)
        p.text(1020, y, price, size=31, bold=True, anchor="ra")
        if perlab:
            p.text(1020, y + 40, perlab, size=19, fill=(90, 90, 90), anchor="ra")
        if "colour" in label:
            p.d.line((950, y + 20, 1025, y + 18), fill=(20, 40, 120), width=4)
            p.handwriting(700, y + 66, "now 50p", size=34, seed=7)
            y += 30
        y += 98 if perlab else 82
    p.text(80, 1400, "Children's items: no overdue charges. Ask at the desk about concessions.", size=19, fill=(80, 80, 80))
    photo_jpg(path, p, seed=12, size=(1200, 1600))


# ------------------------------------------------------------------ build
def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_img")
    os.makedirs(tmp, exist_ok=True)
    notice_png(os.path.join(tmp, "closures-notice-2026.png"))
    fees_jpg(os.path.join(tmp, "fees-sheet.jpg"))
    notice = open(os.path.join(tmp, "closures-notice-2026.png"), "rb").read()
    sheet = open(os.path.join(tmp, "fees-sheet.jpg"), "rb").read()
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)

    j = lambda x: json.dumps(x, indent=1, ensure_ascii=False) + "\n"  # noqa: E731
    base_files = {
        "tidewater/__init__.py": INIT_PY,
        "tidewater/layout.py": LAYOUT_PY,
        "tidewater/server.py": SERVER_PY,
        "tidewater/pages/__init__.py": PAGES_INIT,
        "tidewater/pages/home.py": HOME_PY,
        "tidewater/pages/hours.py": HOURS_PY,
        "tidewater/pages/events.py": EVENTS_PY,
        "tidewater/templates/base.html": BASE_HTML,
        "tidewater/static/style.css": STYLE_CSS,
        "tidewater/data/hours.json": j(HOURS),
        "tidewater/data/events.json": j(EVENTS),
        "tests/__init__.py": "",
        "tests/test_data.py": TEST_DATA,
        ".gitignore": GITIGNORE,
    }
    # history: v1.3.0 without the branches page, then the branches page, dev.sh, CONTRIBUTING, the two requests
    routes_v13 = ROUTES_PY.replace("    '/branches': 'branches',\n", "")
    nav_v13 = NAV_HTML.replace('  <a href="/branches">Branches</a>\n', "")
    test_v13 = TEST_ROUTES.replace("    '/branches',\n", "")
    readme_v13 = README.replace("| `/branches` | Branches | `branches.json` |\n", "")
    cl_v13 = CHANGELOG.split("## [Unreleased]")[0] + "## [1.3.0]" + CHANGELOG.split("## [1.3.0]")[1]
    history = [
        ("2026-06-02T10:12:00", OWEN, {**base_files, "README.md": readme_v13, "tidewater/routes.py": routes_v13,
                                       "tidewater/templates/nav.html": nav_v13, "tests/test_routes.py": test_v13,
                                       "CHANGELOG.md": CHANGELOG.split("## [Unreleased]")[0] + "## [1.2.0]"
                                       + CHANGELOG.split("## [1.2.0]")[1],
                                       "tidewater/pages/events.py": EVENTS_PY.replace(
                                           "sorted(load_data('events.json'), key=lambda e: (e['date'], e['time']))",
                                           "load_data('events.json')")},
         "Tidewater Libraries website 1.2"),
        ("2026-10-12T16:40:00", OWEN, {"CHANGELOG.md": cl_v13.replace(
            "## [1.3.0]", "## [1.3.0]", 1)}, "Release 1.3.0"),
        ("2026-10-21T19:05:00", ROSA, {"tidewater/pages/branches.py": BRANCHES_PY,
                                       "tidewater/data/branches.json": j(BRANCH_DATA),
                                       "tidewater/routes.py": ROUTES_PY, "tidewater/templates/nav.html": NAV_HTML,
                                       "tests/test_routes.py": TEST_ROUTES, "README.md": README,
                                       "CHANGELOG.md": CHANGELOG.replace(
                                           "\n### Fixed\n- What's on: events are listed in date order again.\n", "")},
         "Add branches page"),
        ("2026-10-24T11:30:00", ROSA, {"tidewater/pages/events.py": EVENTS_PY, "CHANGELOG.md": CHANGELOG},
         "Sort events by date"),
        ("2026-10-28T20:15:00", ROSA, {"dev.sh": dev_sh("tidewater.server", PORT, "Tidewater Libraries"),
                                       "CONTRIBUTING.md": CONTRIBUTING},
         "Add dev.sh and contributing notes"),
        ("2026-11-02T09:20:00", ROSA, {"docs/requests/closures.md": CLOSURES_MD,
                                       "docs/requests/closures-notice-2026.png": notice,
                                       "docs/requests/fees.md": FEES_MD, "docs/requests/fees-sheet.jpg": sheet},
         "Add change requests from Maureen and the front desk"),
    ]
    info = make_repo(os.path.join(out_dir, f"{NAME}.tar.gz"), NAME, history, ROSA)
    exp = {
        "base": info["base"], "port": PORT, "name": NAME,
        "closures": [{"branch": b, "date": d, "hours": h} for b, d, h in CLOSURES],
        "fees": [{"item": i, "fee": f, "per": p, "kw": kw} for i, f, p, kw in FEES],
        "marks": {"A": A_MARK, "B": B_MARK},
        "msg": {"A": "Add holiday closures page", "B": "Add fees and charges page"},
    }
    json.dump(exp, open(os.path.join(out_dir, "expected.json"), "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/a4_assets")
