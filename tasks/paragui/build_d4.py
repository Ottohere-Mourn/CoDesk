"""D4 - shorebirds: a research group's survey-analysis package + report server (port 8114).

A (pgd4table): `run_all` crashes on the 2026 survey sheet and Table 2 drifted from the paper; the paper's Table 2 and
               its footnote (rules) exist only as a scanned PDF page. Fix, regenerate results/, test, restart, commit.
B (pgd4release): release 1.4.0 per RELEASING.md: changelog from the git history since v1.3.0, version in 3 places,
               Zenodo DOI + date only in a screenshot, annotated tag, dist archive from a clean tree, restart.
"""
import datetime as dt
import json
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_devrepo import dev_sh, font, make_repo, scan_pdf, scanify  # noqa: E402

PORT = 8114
FEMKE = ("Femke de Vries", "f.devries@wadden-lab.example")
NOOR = ("Noor Haddad", "n.haddad@wadden-lab.example")
LARS = ("Lars Jessen", "l.jessen@wadden-lab.example")
OLD_DOI, NEW_DOI, RELEASE_DATE = "10.5281/zenodo.15012345", "10.5281/zenodo.17463021", "2026-10-23"
SPECIES = ["Eurasian Oystercatcher", "Dunlin", "Red Knot", "Bar-tailed Godwit", "Common Redshank", "Eurasian Curlew"]
GENUS_ONLY = ["Calidris sp.", "Numenius sp.", "Tringa sp."]
SITES = ["Hallig Hooge", "Amrum Odde", "Sylt Ellenbogen", "Beltringharder Koog"]
OBSERVERS = ["N. Haddad", "L. Jessen", "F. de Vries", "M. Paulsen"]
OLD_HEAD = ["survey_id", "date", "site", "observer", "duration_min", "species", "count"]
NEW_HEAD = ["survey_id", "date", "site", "observer", "tide", "species", "count", "duration_min"]

# ------------------------------------------------------------------ package sources
INIT_PY = '"""shorebirds - analysis of the Wadden Sea high-tide roost counts."""\n__version__ = "%s"\n'

IO_PY = '''"""Reading the survey sheets (data/counts_<year>.csv, one row per survey and species)."""
import csv
import glob
import os
from dataclasses import dataclass


@dataclass
class Record:
    survey_id: str
    date: str          # YYYY-MM-DD
    site: str
    observer: str
    duration_min: int  # duration of the whole survey (repeated on every row of the survey)
    species: str
    count: int


def normalise_observer(name):
    """'haddad, noor' / 'N Haddad' / 'n. haddad' -> 'N. Haddad'"""
    name = name.strip()
    if ',' in name:
        last, first = [x.strip() for x in name.split(',', 1)]
        name = first + ' ' + last
    parts = name.replace('.', ' ').split()
    if len(parts) < 2:
        return name.title()
    return '%s. %s' % (parts[0][0].upper(), ' '.join(p.capitalize() if p.islower() else p for p in parts[1:]))


def read_counts(path):
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    out = []
    for row in rows[1:]:  # first row is the header
        if not row:
            continue
        out.append(Record(row[0], row[1], row[2], normalise_observer(row[3]), int(row[4]), row[5].strip(), int(row[6])))
    return out


def load_all(data_dir='data'):
    records = []
    for path in sorted(glob.glob(os.path.join(data_dir, 'counts_*.csv'))):
        records += read_counts(path)
    return records
'''

ANALYSIS_V13 = '''"""Table 2 of the paper: birds per 10 h of survey effort, per species and year."""
from collections import defaultdict

PER_HOURS = 10


def is_identified(species):
    """Records identified to genus only ('Calidris sp.') are not used."""
    return not species.endswith(' sp.')


def table2(records):
    counts = defaultdict(lambda: defaultdict(int))
    effort = defaultdict(int)
    seen = set()
    for r in records:
        year = r.date[:4]
        if r.survey_id not in seen:
            seen.add(r.survey_id)
            effort[year] += r.duration_min
        if is_identified(r.species):
            counts[r.species][year] += r.count
    return {sp: {y: round(PER_HOURS * 60 * n / effort[y], 1) for y, n in sorted(ys.items())}
            for sp, ys in counts.items()}
'''

ANALYSIS_FAST = '''"""Table 2 of the paper: birds per 10 h of survey effort, per species and year."""
from collections import defaultdict

PER_HOURS = 10


def table2(records):
    # single pass, no per-survey bookkeeping (#45)
    counts = defaultdict(lambda: defaultdict(int))
    effort = defaultdict(int)
    for r in records:
        year = r.date[:4]
        counts[r.species][year] += r.count
        effort[year] += r.duration_min
    return {sp: {y: round(PER_HOURS * 60 * n / effort[y], 1) for y, n in sorted(ys.items())}
            for sp, ys in counts.items()}
'''

FIGURES_PY = '''"""Figure 2: grouped bar chart of Table 2 as a standalone SVG (no plotting library needed)."""
from html import escape

COLOURS = ['#4e79a7', '#f28e2b', '#59a14f', '#e15759']


def fig2_svg(table):
    years = sorted({y for ys in table.values() for y in ys})
    species = sorted(table)
    vmax = max([v for ys in table.values() for v in ys.values()] + [1])
    W, H, left, top, bottom = 900, 420, 70, 30, 120
    group = (W - left - 20) / max(len(species), 1)
    bar = group * 0.8 / max(len(years), 1)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="sans-serif" font-size="12">' % (W, H),
           '<text x="%d" y="18" font-size="14">Figure 2. Birds per 10 h of survey effort</text>' % left]
    for i, sp in enumerate(species):
        for j, y in enumerate(years):
            v = table[sp].get(y)
            if v is None:
                continue
            h = (H - top - bottom) * v / vmax
            x = left + i * group + j * bar
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" data-species="%s" data-year="%s" '
                       'data-value="%s"><title>%s %s: %s</title></rect>' % (
                           x, H - bottom - h, bar - 1, h, COLOURS[j % 4], escape(sp), y, v, escape(sp), y, v))
        out.append('<text x="%.1f" y="%d" transform="rotate(30 %.1f %d)">%s</text>' % (
            left + i * group, H - bottom + 16, left + i * group, H - bottom + 16, escape(sp)))
    for j, y in enumerate(years):
        out.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/><text x="%d" y="%d">%s</text>' % (
            W - 220 + 70 * j, 10, COLOURS[j % 4], W - 204 + 70 * j, 21, y))
    out.append('</svg>')
    return '\\n'.join(out) + '\\n'
'''

RUN_ALL_PY = '''"""Regenerate the paper's results: results/table2.csv and results/fig2_trends.svg.

    python3 -m shorebirds.run_all [--data data] [--out results]
"""
import argparse
import csv
import os

from .analysis import table2
from .figures import fig2_svg
from .io import load_all


def write_table(table, path):
    years = sorted({y for ys in table.values() for y in ys})
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['species'] + years)
        for sp in sorted(table):
            w.writerow([sp] + ['%.1f' % table[sp][y] if y in table[sp] else '' for y in years])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--out', default='results')
    args = ap.parse_args(argv)
    t = table2(load_all(args.data))
    os.makedirs(args.out, exist_ok=True)
    write_table(t, os.path.join(args.out, 'table2.csv'))
    with open(os.path.join(args.out, 'fig2_trends.svg'), 'w') as f:
        f.write(fig2_svg(t))
    print('wrote %s/table2.csv and %s/fig2_trends.svg (%d species)' % (args.out, args.out, len(t)))


if __name__ == '__main__':
    main()
'''

SERVE_PY = '''"""Lab report server: runs the analysis once at start-up and serves the results page.

    python3 -m shorebirds.serve --port 8114        (or ./dev.sh start|restart)
"""
import argparse
import os
import re
import sys
import traceback
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .analysis import table2
from .figures import fig2_svg
from .io import load_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = {}


def doi():
    try:
        m = re.search(r'(?m)^doi:\\s*"?([^"\\s]+)', open(os.path.join(ROOT, 'CITATION.cff')).read())
        return m.group(1) if m else ''
    except OSError:
        return ''


def render():
    try:
        t = table2(load_all(os.path.join(ROOT, 'data')))
        years = sorted({y for ys in t.values() for y in ys})
        rows = ''.join('<tr data-species="%s"><th>%s</th>%s</tr>' % (
            escape(sp), escape(sp), ''.join('<td data-year="%s">%s</td>' % (y, '%.1f' % t[sp][y] if y in t[sp] else '')
                                            for y in years)) for sp in sorted(t))
        body = ('<h2>Table 2 &ndash; birds per 10 h of survey effort</h2><table id="table2"><tr><th>Species</th>%s</tr>%s'
                '</table><h2>Figure 2</h2>%s' % (''.join('<th>%s</th>' % y for y in years), rows, fig2_svg(t)))
    except Exception:
        body = '<div class="error"><h2>Analysis failed</h2><pre>%s</pre></div>' % escape(traceback.format_exc())
    d = doi()
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Wadden Sea roost counts</title><style>'
            'body{font-family:"DejaVu Sans",sans-serif;margin:30px 50px;color:#222}table{border-collapse:collapse}'
            'th,td{border-bottom:1px solid #ddd;padding:6px 14px;text-align:right}th:first-child{text-align:left}'
            '.error{background:#fde8e8;border:1px solid #e0a0a0;padding:10px 20px}footer{margin-top:40px;color:#666}'
            '</style></head><body><h1>Wadden Sea high-tide roost counts &ndash; results</h1>%s'
            '<footer id="footer">shorebirds %s &middot; cite as <a href="https://doi.org/%s">doi:%s</a></footer>'
            '</body></html>' % (body, __version__, d, d))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\\n' % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        ok = self.path.split('?')[0] in ('/', '/index.html')
        data = (PAGE['html'] if ok else '<h1>Not found</h1>').encode()
        self.send_response(200 if ok else 404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8114)
    args = ap.parse_args()
    PAGE['html'] = render()
    print('report on http://127.0.0.1:%d/' % args.port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
'''

GPX_PY = '''"""Export transect routes as GPX (#41)."""
from html import escape


def to_gpx(name, points):
    """points: [(lat, lon)] -> GPX 1.1 document with one track."""
    pts = ''.join('<trkpt lat="%.6f" lon="%.6f"/>' % p for p in points)
    return ('<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="shorebirds" '
            'xmlns="http://www.topografix.com/GPX/1/1"><trk><name>%s</name><trkseg>%s</trkseg></trk></gpx>' % (escape(name), pts))
'''

MAKE_DIST_PY = '''#!/usr/bin/env python3
"""Build dist/shorebirds-<version>.tar.gz from the tracked files of a CLEAN working tree.

    python3 tools/make_dist.py
"""
import hashlib
import os
import re
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    os.chdir(ROOT)
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout
    if dirty.strip():
        sys.exit('make_dist: the working tree has uncommitted changes - commit them first:\\n' + dirty)
    version = re.search(r'__version__ = "([^"]+)"', open('shorebirds/__init__.py').read()).group(1)
    files = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True).stdout.split('\\n')
    os.makedirs('dist', exist_ok=True)
    out = 'dist/shorebirds-%s.tar.gz' % version
    with tarfile.open(out, 'w:gz') as t:
        for f in files:
            if f:
                t.add(f, arcname='shorebirds-%s/%s' % (version, f), recursive=False)
    digest = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    with open('dist/SHA256SUMS', 'a') as f:
        f.write('%s  %s\\n' % (digest, os.path.basename(out)))
    print('built', out, digest)


if __name__ == '__main__':
    main()
'''

TEST_IO = '''import os
import unittest

from shorebirds.io import normalise_observer, read_counts

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


class IoTest(unittest.TestCase):
    def test_read_2024(self):
        recs = read_counts(os.path.join(DATA, 'counts_2024.csv'))
        self.assertGreater(len(recs), 50)
        self.assertTrue(all(r.date.startswith('2024') for r in recs))

    def test_observer(self):
        self.assertEqual(normalise_observer('haddad, noor'), 'N. Haddad')
        self.assertEqual(normalise_observer('L Jessen'), 'L. Jessen')


if __name__ == '__main__':
    unittest.main()
'''

TEST_ANALYSIS = '''import unittest

from shorebirds.analysis import table2
from shorebirds.io import Record


class Table2Test(unittest.TestCase):
    def test_rate_per_10h(self):
        recs = [Record('S1', '2025-03-01', 'A', 'N. Haddad', 120, 'Dunlin', 40),
                Record('S2', '2025-03-08', 'A', 'N. Haddad', 180, 'Dunlin', 20)]
        self.assertEqual(table2(recs), {'Dunlin': {'2025': 120.0}})   # 60 birds in 5 h


if __name__ == '__main__':
    unittest.main()
'''

TEST_GPX = '''import unittest

from shorebirds.gpx import to_gpx


class GpxTest(unittest.TestCase):
    def test_track(self):
        g = to_gpx('T1', [(54.5, 8.6), (54.51, 8.61)])
        self.assertIn('<trkpt lat="54.500000" lon="8.600000"/>', g)


if __name__ == '__main__':
    unittest.main()
'''

PYPROJECT = '''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "shorebirds"
version = "%s"
description = "Analysis of the Wadden Sea high-tide roost counts"
authors = [{name = "Femke de Vries"}, {name = "Noor Haddad"}, {name = "Lars Jessen"}]
license = {text = "MIT"}
requires-python = "%s"
'''

CITATION = '''cff-version: 1.2.0
message: "If you use this software, please cite it as below."
title: "shorebirds: analysis of the Wadden Sea high-tide roost counts"
authors:
  - family-names: "de Vries"
    given-names: "Femke"
    orcid: "https://orcid.org/0000-0002-4411-2873"
  - family-names: "Haddad"
    given-names: "Noor"
  - family-names: "Jessen"
    given-names: "Lars"
version: %s
date-released: %s
doi: %s
license: MIT
repository-code: "https://git.wadden-lab.example/roosts/shorebirds"
'''

README = '''# shorebirds

[![DOI](https://zenodo.org/badge/DOI/%s.svg)](https://doi.org/%s)

Analysis code for the Wadden Sea high-tide roost counts (Wadden Lab, Kiel). It produces Table 2 and Figure 2 of
de Vries, Haddad & Jessen (in prep.).

    python3 -m shorebirds.run_all        # -> results/table2.csv, results/fig2_trends.svg
    ./dev.sh start                       # lab report page on http://127.0.0.1:8114/ (stop|restart|status|log)
    python3 -m unittest                  # tests

The report server runs the analysis once when it starts: restart it (`./dev.sh restart`) after changing code or data.

Data: `data/counts_<year>.csv`, one row per survey and species. Releases: see RELEASING.md.
'''

RELEASING = '''# Releasing shorebirds

Every release is archived on Zenodo (one DOI per version) and cited in our papers, so please follow these steps.

1. On Zenodo, open the next version of the record ("New version") and **reserve the DOI**. The draft shows the
   version DOI and the publication date that this release must carry.
2. `CHANGELOG.md`: add a section `## [X.Y.Z] - YYYY-MM-DD` (publication date) directly under `## [Unreleased]`
   and move the unreleased entries into it. The section must list **every change merged since the previous
   release tag** (`git log vPREVIOUS..HEAD`), each with its issue number (`#NN`), grouped under
   `### Added` / `### Changed` / `### Fixed` / `### Removed`. Leave `## [Unreleased]` empty.
3. Bump the version in **three** places: `pyproject.toml`, `shorebirds/__init__.py` and `CITATION.cff`. In
   `CITATION.cff` also set `date-released` (publication date) and `doi` (the new version DOI).
4. Update the DOI badge at the top of `README.md` to the new version DOI.
5. Commit only these release changes as `Release X.Y.Z` and create an **annotated** tag `vX.Y.Z` on that commit
   (message: `shorebirds X.Y.Z`).
6. Build the archive with `python3 tools/make_dist.py` (needs a clean working tree) -> `dist/shorebirds-X.Y.Z.tar.gz`;
   it is uploaded to the Zenodo draft by hand.
7. Restart the report server (`./dev.sh restart`) - its footer shows the version and DOI.
'''

CHANGELOG_13 = """# Changelog

All notable changes to this project are documented here (format: keepachangelog.com).

## [Unreleased]

## [1.3.0] - 2026-05-12

### Added
- Figure 2 as a standalone SVG, no plotting library needed (#35)
- Lab report server (#37)

### Fixed
- Survey effort counted once per survey (#33)

## [1.2.0] - 2025-11-03

### Added
- Table 2: birds per 10 h of survey effort (#29)
"""

CHANGELOG_BASE = CHANGELOG_13.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Added\n"
                                      "- GPX export of transect routes (#41)\n\n### Fixed\n"
                                      "- Observer initials normalised consistently (#43)\n")

GITIGNORE = "__pycache__/\n*.pyc\ndist/\nlogs/\n.devserver.pid\n"


# ------------------------------------------------------------------ data
def survey_data(r, year, n_surveys, new_layout=False):
    rows = []
    for k in range(n_surveys):
        sid = f"{year}-{k + 1:03d}"
        day = dt.date(year, 1, 10) + dt.timedelta(days=int(k * 340 / n_surveys) + r.randrange(5))
        site, obs = r.choice(SITES), r.choice(OBSERVERS)
        dur = r.choice([90, 120, 120, 150, 180, 210, 240])
        tide = r.choice(["high", "high", "spring high"])
        sp = r.sample(SPECIES, r.randint(3, 6))
        if r.random() < 0.35:
            sp.append(r.choice(GENUS_ONLY))
        for s in sp:
            base = {"Eurasian Oystercatcher": 140, "Dunlin": 260, "Red Knot": 120, "Bar-tailed Godwit": 60,
                    "Common Redshank": 35, "Eurasian Curlew": 45}.get(s, 20)
            cnt = max(1, int(r.gauss(base * (1 + 0.08 * (year - 2024)), base * 0.5)))
            rows.append({"survey_id": sid, "date": day.isoformat(), "site": site, "observer": obs, "duration_min": dur,
                         "tide": tide, "species": s, "count": cnt})
    head = NEW_HEAD if new_layout else OLD_HEAD
    text = ",".join(head) + "\n" + "".join(",".join(str(x[h]) for h in head) + "\n" for x in rows)
    return rows, text


def table2_ref(rows):
    counts, effort, seen = {}, {}, set()
    for x in rows:
        y = x["date"][:4]
        if x["survey_id"] not in seen:
            seen.add(x["survey_id"])
            effort[y] = effort.get(y, 0) + x["duration_min"]
        if not x["species"].endswith(" sp."):
            counts.setdefault(x["species"], {}).setdefault(y, 0)
            counts[x["species"]][y] += x["count"]
    return {s: {y: round(10 * 60 * n / effort[y], 1) for y, n in sorted(ys.items())} for s, ys in counts.items()}


# ------------------------------------------------------------------ images
def paper_pdf(path, table):
    W, H = 1240, 1754
    p1 = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(p1)
    d.text((110, 120), "Rising numbers of roosting shorebirds on the", fill=0, font=font(36, serif=True, bold=True))
    d.text((110, 170), "North Frisian Wadden Sea coast, 2024-2026", fill=0, font=font(36, serif=True, bold=True))
    d.text((110, 240), "Femke de Vries, Noor Haddad, Lars Jessen  -  Wadden Lab, Kiel", fill=0, font=font(24, serif=True))
    d.text((110, 280), "Draft v3, 18 October 2026 - submitted to Wader Study", fill=60, font=font(20, serif=True))
    y = 360
    abstract = ("Abstract. We counted shorebirds on four high-tide roosts of the North Frisian coast between "
                "January 2024 and September 2026. Effort-corrected abundance of all six focal species increased "
                "over the three seasons, most strongly for Dunlin and Red Knot (Table 2, Figure 2). We discuss "
                "the role of the 2025 saltmarsh management changes and recommend continued standardised counts.")
    words, line = abstract.split(), ""
    for w_ in words:
        if d.textlength(line + " " + w_, font=font(23, serif=True)) > W - 240:
            d.text((110, y), line.strip(), fill=0, font=font(23, serif=True))
            y += 36
            line = ""
        line += " " + w_
    d.text((110, y), line.strip(), fill=0, font=font(23, serif=True))
    d.text((110, H - 100), "1", fill=0, font=font(20, serif=True))
    p2 = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(p2)
    d.text((110, 120), "Table 2. Shorebirds on the high-tide roosts, birds per 10 h of survey effort.",
           fill=0, font=font(25, serif=True, bold=True))
    years = sorted({yy for ys in table.values() for yy in ys})
    y = 190
    d.line((110, y, W - 110, y), fill=0, width=3)
    d.text((120, y + 12), "Species", fill=0, font=font(24, serif=True, bold=True))
    for j, yy in enumerate(years):
        d.text((700 + 160 * j, y + 12), yy, fill=0, font=font(24, serif=True, bold=True))
    y += 56
    d.line((110, y, W - 110, y), fill=0, width=1)
    for sp in SPECIES:
        d.text((120, y + 12), sp, fill=0, font=font(24, serif=True))
        for j, yy in enumerate(years):
            v = "%.1f" % table[sp][yy]
            d.text((760 + 160 * j - d.textlength(v, font=font(24, serif=True)), y + 12), v, fill=0, font=font(24, serif=True))
        y += 50
    d.line((110, y + 6, W - 110, y + 6), fill=0, width=3)
    y += 30
    for ln in ["Effort = total duration of all surveys of the year, each survey counted once.",
               "Records identified only to genus (e.g. 'Calidris sp.') are excluded.",
               "Counts from the four roosts pooled; 2026: January-September."]:
        d.text((120, y), ln, fill=0, font=font(21, serif=True))
        y += 34
    d.text((110, y + 60), "[Figure 2: grouped bar chart of Table 2 - see results/fig2_trends.svg]", fill=90,
           font=font(21, serif=True))
    d.text((110, H - 100), "4", fill=0, font=font(20, serif=True))
    scan_pdf([scanify(p1, 3), scanify(p2, 4)], path)


def zenodo_png(path):
    W, H = 1366, 900
    im = Image.new("RGB", (W, H), "#f5f7fa")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 78), fill="#dee1e6")
    d.rounded_rectangle((10, 6, 330, 38), 8, fill="#f5f7fa")
    d.text((26, 13), "New version | Zenodo", fill="#333", font=font(15))
    d.rounded_rectangle((90, 44, W - 120, 72), 14, fill="#ffffff")
    d.text((110, 49), "zenodo.org/uploads/17463021", fill="#444", font=font(15))
    d.rectangle((0, 78, W, 130), fill="#0b3d91")
    d.text((40, 92), "zenodo", fill="white", font=font(26, bold=True))
    d.text((W - 300, 98), "Femke de Vries  v", fill="white", font=font(16))
    d.rounded_rectangle((40, 150, W - 40, 210), 6, fill="#fff8e1", outline="#f0c36d")
    d.text((60, 168), "Draft - new version of \"shorebirds: analysis of the Wadden Sea high-tide roost counts\". "
                      "Not published yet.", fill="#5d4037", font=font(17))
    x0, y = 60, 240
    d.rounded_rectangle((40, 230, W - 40, H - 40), 6, fill="white", outline="#d0d7de")
    d.text((x0, y + 10), "Basic information", fill="#222", font=font(22, bold=True))
    y += 60
    d.text((x0, y), "Digital Object Identifier", fill="#222", font=font(17, bold=True))
    y += 30
    d.text((x0, y), "Do you already have a DOI for this upload?   ( ) Yes    (o) No", fill="#333", font=font(16))
    y += 36
    d.rounded_rectangle((x0, y, x0 + 520, y + 44), 4, fill="#eef6ee", outline="#7cb87c")
    d.text((x0 + 14, y + 11), "DOI reserved:  " + NEW_DOI, fill="#1b5e20", font=font(18, bold=True))
    d.rounded_rectangle((x0 + 540, y + 4, x0 + 680, y + 40), 4, outline="#999")
    d.text((x0 + 556, y + 12), "Discard", fill="#555", font=font(15))
    y += 64
    d.text((x0, y), "Copy this DOI into your files before publishing; it becomes active when you publish.",
           fill="#666", font=font(15))
    y += 50
    fields = [("Resource type", "Software"), ("Title", "shorebirds: analysis of the Wadden Sea high-tide roost counts"),
              ("Publication date", RELEASE_DATE), ("Version", "1.4.0"),
              ("Creators", "de Vries, Femke;  Haddad, Noor;  Jessen, Lars")]
    for k, v in fields:
        d.text((x0, y), k, fill="#222", font=font(17, bold=True))
        d.rounded_rectangle((x0 + 230, y - 6, x0 + 1000, y + 30), 4, fill="#fff", outline="#c8ced6")
        d.text((x0 + 244, y), v, fill="#111", font=font(17))
        y += 56
    d.text((x0, y + 10), "Files:  (upload dist/shorebirds-1.4.0.tar.gz here)", fill="#888", font=font(16))
    d.rounded_rectangle((W - 330, H - 100, W - 70, H - 56), 4, fill="#2e7d32")
    d.text((W - 290, H - 90), "Publish", fill="white", font=font(18, bold=True))
    im.save(path, optimize=True)


def build(out):
    os.makedirs(out, exist_ok=True)
    r = random.Random(1404)
    rows24, t24 = survey_data(r, 2024, 34)
    rows25, t25 = survey_data(r, 2025, 36)
    rows26, t26 = survey_data(r, 2026, 30, new_layout=True)
    table = table2_ref(rows24 + rows25 + rows26)
    hr = random.Random(99)
    h22, ht22 = survey_data(hr, 2022, 9, new_layout=True)
    h23, ht23 = survey_data(hr, 2023, 8)
    hidden = table2_ref(h22 + h23)
    tmp_pdf, tmp_png = os.path.join(out, "_paper.pdf"), os.path.join(out, "_zen.png")
    paper_pdf(tmp_pdf, table)
    zenodo_png(tmp_png)

    # results as committed for v1.3.0 (only 2024/2025, correct code at that time)
    import io as _io
    import importlib.util
    spec = importlib.util.spec_from_loader("figs", loader=None)
    figs = importlib.util.module_from_spec(spec)
    exec(FIGURES_PY, figs.__dict__)
    t_old = table2_ref(rows24 + rows25)
    buf = _io.StringIO()
    years = ["2024", "2025"]
    buf.write("species," + ",".join(years) + "\n")
    for sp in sorted(t_old):
        buf.write(sp + "," + ",".join("%.1f" % t_old[sp][y] for y in years) + "\n")
    v13 = {".gitignore": GITIGNORE, "README.md": README % (OLD_DOI, OLD_DOI), "RELEASING.md": RELEASING,
           "CHANGELOG.md": CHANGELOG_13, "CITATION.cff": CITATION % ("1.3.0", "2026-05-12", OLD_DOI),
           "pyproject.toml": PYPROJECT % ("1.3.0", ">=3.8"), "shorebirds/__init__.py": INIT_PY % "1.3.0",
           "shorebirds/io.py": IO_PY.replace("normalise_observer(row[3])", "row[3].strip()"),
           "shorebirds/analysis.py": ANALYSIS_V13, "shorebirds/figures.py": FIGURES_PY,
           "shorebirds/run_all.py": RUN_ALL_PY, "shorebirds/serve.py": SERVE_PY, "tools/make_dist.py": MAKE_DIST_PY,
           "tests/__init__.py": "", "tests/test_analysis.py": TEST_ANALYSIS,
           "tests/test_io.py": TEST_IO.replace("""
    def test_observer(self):
        self.assertEqual(normalise_observer('haddad, noor'), 'N. Haddad')
        self.assertEqual(normalise_observer('L Jessen'), 'L. Jessen')
""", "").replace("normalise_observer, read_counts", "read_counts"),
           "data/counts_2024.csv": t24, "data/counts_2025.csv": t25,
           "results/table2.csv": buf.getvalue(), "results/fig2_trends.svg": figs.fig2_svg(t_old)}
    history = [
        ("2026-05-12T14:00:00", FEMKE, v13, "Release 1.3.0"),
        ("2026-06-02T10:20:00", LARS, {"shorebirds/gpx.py": GPX_PY, "tests/test_gpx.py": TEST_GPX,
                                       "CHANGELOG.md": CHANGELOG_13.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Added\n"
                                                                            "- GPX export of transect routes (#41)\n")},
         "Add GPX export of transect routes (#41)"),
        ("2026-07-15T16:45:00", NOOR, {"shorebirds/io.py": IO_PY, "tests/test_io.py": TEST_IO, "CHANGELOG.md": CHANGELOG_BASE},
         "Normalise observer initials (#43)"),
        ("2026-09-03T11:05:00", LARS, {"shorebirds/analysis.py": ANALYSIS_FAST}, "Faster aggregation for table 2 (#45)"),
        ("2026-09-20T09:30:00", FEMKE, {"pyproject.toml": PYPROJECT % ("1.3.0", ">=3.9")}, "Drop Python 3.8 support (#46)"),
        ("2026-10-01T08:50:00", NOOR, {"data/counts_2026.csv": t26}, "Add 2026 survey sheet (Jan-Sep, new field app export)"),
        ("2026-10-08T13:10:00", FEMKE, {"dev.sh": dev_sh("shorebirds.serve", PORT, "shorebirds report")},
         "Add dev.sh for the report server"),
        ("2026-10-20T17:30:00", NOOR, {"paper/draft_v3.pdf": open(tmp_pdf, "rb").read()}, "Paper draft v3 (as submitted)"),
        ("2026-10-22T09:00:00", FEMKE, {"docs/release/zenodo-draft-1.4.0.png": open(tmp_png, "rb").read()},
         "Zenodo draft for 1.4.0 (screenshot)"),
    ]
    info = make_repo(os.path.join(out, "shorebirds.tar.gz"), "shorebirds", history, FEMKE,
                     tags={"v1.3.0": (0, "shorebirds 1.3.0")})
    os.remove(tmp_pdf)
    os.remove(tmp_png)
    json.dump({"base": info["base"], "port": PORT, "table2": table, "species": SPECIES,
               "hidden_files": {"counts_2022.csv": ht22, "counts_2023.csv": ht23}, "hidden_table": hidden,
               "base_analysis_commit": info["commits"][0], "version": "1.4.0", "old_version": "1.3.0",
               "doi": NEW_DOI, "old_doi": OLD_DOI, "date": RELEASE_DATE, "issues": ["#41", "#43", "#45", "#46"]},
              open(os.path.join(out, "expected.json"), "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/d4_build")
