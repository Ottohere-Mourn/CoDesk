"""D2 - meterflow: smart-meter ingest pipeline + dashboard (port 8112) of a municipal utility.

A (pgd2toml):   migrate settings.ini -> settings.toml across code/tests/CLI/VS Code launch config/README per ADR-0007,
                and write deploy/prod.toml from ops' terminal screenshot of the production config (pixels only).
B (pgd2kelvar): add a parser for the new vendor Kelvar, whose fixed-width KMF format is defined only in a scanned
                PDF; register it, configure the vendor, tests, README vendor table, restart the dashboard.
Both edit the settings file and README and restart the same dashboard; each must commit separately.
"""
import datetime as dt
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_devrepo import dev_sh, font, make_repo, scan_pdf, scanify, tomli_files  # noqa: E402

PORT = 8112
JANA = ("Jana Petersen", "jana.petersen@elbmark-energie.example")
OLE = ("Ole Brandt", "ole.brandt@elbmark-energie.example")
BERLIN = ZoneInfo("Europe/Berlin")
UTC = dt.timezone.utc

SETTINGS_INI = """; meterflow settings (development)
; Paths are relative to the repository root.

[pipeline]
inbox_dir = data/inbox
out_dir = data/out
timezone = Europe/Berlin
interval_minutes = 15

[alerts]
enabled = yes
max_kwh_per_interval = 12.5
notify = grid-ops@elbmark-energie.example, jana.petersen@elbmark-energie.example

[dashboard]
title = Meterflow (dev)
port = 8112

[vendor:acme]
enabled = true
format = acme_csv
inbox = acme
meter_prefix = AC

[vendor:voltis]
enabled = true
format = voltis_jsonl
inbox = voltis
meter_prefix = VT
"""

DEV_EXPECTED = {
    "pipeline": {"inbox_dir": "data/inbox", "out_dir": "data/out", "timezone": "Europe/Berlin", "interval_minutes": 15},
    "alerts": {"enabled": True, "max_kwh_per_interval": 12.5,
               "notify": ["grid-ops@elbmark-energie.example", "jana.petersen@elbmark-energie.example"]},
    "dashboard": {"title": "Meterflow (dev)", "port": 8112},
    "vendors": {"acme": {"enabled": True, "format": "acme_csv", "inbox": "acme", "meter_prefix": "AC"},
                "voltis": {"enabled": True, "format": "voltis_jsonl", "inbox": "voltis", "meter_prefix": "VT"}},
}

PROD_INI = """; meterflow settings (production) - managed by ops, do not edit by hand
[pipeline]
inbox_dir = /srv/meterflow/inbox
out_dir = /srv/meterflow/out
timezone = Europe/Berlin
interval_minutes = 15

[alerts]
enabled = on
max_kwh_per_interval = 9.75
notify = leitstelle@elbmark-energie.example, grid-ops@elbmark-energie.example, oncall-data@elbmark-energie.example

[dashboard]
title = Meterflow PROD
port = 8080

[vendor:acme]
enabled = true
format = acme_csv
inbox = acme
meter_prefix = AC

[vendor:voltis]
enabled = no
format = voltis_jsonl
inbox = voltis-archive
meter_prefix = VT
"""

PROD_EXPECTED = {
    "pipeline": {"inbox_dir": "/srv/meterflow/inbox", "out_dir": "/srv/meterflow/out", "timezone": "Europe/Berlin",
                 "interval_minutes": 15},
    "alerts": {"enabled": True, "max_kwh_per_interval": 9.75,
               "notify": ["leitstelle@elbmark-energie.example", "grid-ops@elbmark-energie.example",
                          "oncall-data@elbmark-energie.example"]},
    "dashboard": {"title": "Meterflow PROD", "port": 8080},
    "vendors": {"acme": {"enabled": True, "format": "acme_csv", "inbox": "acme", "meter_prefix": "AC"},
                "voltis": {"enabled": False, "format": "voltis_jsonl", "inbox": "voltis-archive", "meter_prefix": "VT"}},
}

INIT_PY = '"""meterflow - smart-meter readings ingest for Elbmark Energie."""\n__version__ = "0.9.0"\n'

MODEL_PY = '''from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reading:
    """One interval reading. ts is the END of the interval as a timezone-aware UTC datetime."""
    meter_id: str
    ts: datetime
    kwh: float
    quality: str  # 'valid' | 'estimated'
'''

TIMEUTIL_PY = '''from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def local_to_utc(naive, tz_name):
    """A naive wall-clock datetime in tz_name -> aware UTC datetime."""
    return naive.replace(tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc)


def parse_utc(text):
    """'2026-10-05T08:15:00Z' -> aware UTC datetime."""
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
'''

ACME_PY = '''"""ACME Metering: semicolon CSV with a header row, UTC timestamps, kWh.

    meter;timestamp_utc;kwh;status
    AC-100231;2026-10-05T08:15:00Z;0.412;OK          status: OK | EST (estimated) | ERR (drop)
"""
import csv

from ..model import Reading
from ..timeutil import parse_utc

QUALITY = {'OK': 'valid', 'EST': 'estimated'}


def parse(path):
    out = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter=';'):
            if row['status'] == 'ERR':
                continue
            out.append(Reading(row['meter'].strip(), parse_utc(row['timestamp_utc']), float(row['kwh']),
                               QUALITY[row['status']]))
    return out
'''

VOLTIS_PY = '''"""Voltis: JSON lines, local wall-clock time + IANA zone, energy in Wh.

    {"device": "VT-7781", "end": "2026-10-05 10:15", "tz": "Europe/Berlin", "wh": 388, "q": "measured"}
    q: measured | substituted (-> estimated)
"""
import json
from datetime import datetime

from ..model import Reading
from ..timeutil import local_to_utc

QUALITY = {'measured': 'valid', 'substituted': 'estimated'}


def parse(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            ts = local_to_utc(datetime.strptime(rec['end'], '%Y-%m-%d %H:%M'), rec['tz'])
            out.append(Reading(rec['device'], ts, rec['wh'] / 1000.0, QUALITY[rec['q']]))
    return out
'''

PARSERS_INIT = '''"""Vendor file parsers. Each parser is a function parse(path) -> list[Reading] and raises ValueError for a file
that must be rejected as a whole. The vendor sections of the settings refer to parsers by these format names."""
from . import acme, voltis

PARSERS = {
    'acme_csv': acme.parse,
    'voltis_jsonl': voltis.parse,
}


def get_parser(fmt):
    try:
        return PARSERS[fmt]
    except KeyError:
        raise ValueError('unknown vendor file format: %r' % fmt) from None
'''

CONFIG_PY = '''"""Settings loader. Returns plain dicts with typed values:

    {'pipeline': {...}, 'alerts': {...}, 'dashboard': {...}, 'vendors': {name: {...}}}
"""
import configparser
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, 'settings.ini')


def load_config(path=None):
    path = path or DEFAULT_PATH
    cp = configparser.ConfigParser()
    if not cp.read(path, encoding='utf-8'):
        raise FileNotFoundError(path)
    cfg = {
        'pipeline': {
            'inbox_dir': cp.get('pipeline', 'inbox_dir'),
            'out_dir': cp.get('pipeline', 'out_dir'),
            'timezone': cp.get('pipeline', 'timezone'),
            'interval_minutes': cp.getint('pipeline', 'interval_minutes'),
        },
        'alerts': {
            'enabled': cp.getboolean('alerts', 'enabled'),
            'max_kwh_per_interval': cp.getfloat('alerts', 'max_kwh_per_interval'),
            'notify': [x.strip() for x in cp.get('alerts', 'notify').split(',') if x.strip()],
        },
        'dashboard': {
            'title': cp.get('dashboard', 'title'),
            'port': cp.getint('dashboard', 'port'),
        },
        'vendors': {},
    }
    for section in cp.sections():
        if section.startswith('vendor:'):
            cfg['vendors'][section[len('vendor:'):]] = {
                'enabled': cp.getboolean(section, 'enabled'),
                'format': cp.get(section, 'format'),
                'inbox': cp.get(section, 'inbox'),
                'meter_prefix': cp.get(section, 'meter_prefix'),
            }
    cfg['_source'] = os.path.relpath(path, ROOT) if os.path.abspath(path).startswith(ROOT) else path
    return cfg


def resolve(path):
    """Paths in the settings are relative to the repository root."""
    return path if os.path.isabs(path) else os.path.join(ROOT, path)
'''

PIPELINE_PY = '''"""Ingest all enabled vendors' inbox files, validate, write data/out/readings.csv and summary.json."""
import csv
import glob
import json
import os

from .config import resolve
from .parsers import get_parser


def run(cfg, out_dir=None):
    inbox = resolve(cfg['pipeline']['inbox_dir'])
    limit = cfg['alerts']['max_kwh_per_interval']
    summary = {'vendors': {}, 'alerts': []}
    rows = []
    for name, v in sorted(cfg['vendors'].items()):
        if not v.get('enabled'):
            continue
        parse = get_parser(v['format'])
        st = {'format': v['format'], 'files': 0, 'rejected': [], 'skipped': 0, 'meters': {}, 'readings': 0}
        for path in sorted(glob.glob(os.path.join(inbox, v['inbox'], '*'))):
            if not os.path.isfile(path) or os.path.basename(path).startswith('.'):
                continue
            try:
                readings = parse(path)
            except ValueError as e:
                st['rejected'].append('%s: %s' % (os.path.basename(path), e))
                continue
            st['files'] += 1
            for r in readings:
                if not r.meter_id.startswith(v.get('meter_prefix', '')):
                    st['skipped'] += 1
                    continue
                st['readings'] += 1
                st['meters'][r.meter_id] = round(st['meters'].get(r.meter_id, 0.0) + r.kwh, 6)
                rows.append([name, r.meter_id, r.ts.strftime('%Y-%m-%dT%H:%M:%SZ'), '%.3f' % r.kwh, r.quality])
                if cfg['alerts']['enabled'] and r.kwh > limit:
                    summary['alerts'].append({'vendor': name, 'meter': r.meter_id, 'kwh': r.kwh,
                                              'ts': r.ts.strftime('%Y-%m-%dT%H:%M:%SZ')})
        st['total_kwh'] = round(sum(st['meters'].values()), 3)
        summary['vendors'][name] = st
    out = out_dir or resolve(cfg['pipeline']['out_dir'])
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'readings.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['vendor', 'meter_id', 'ts_utc', 'kwh', 'quality'])
        w.writerows(sorted(rows))
    with open(os.path.join(out, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    return summary
'''

CLI_PY = '''"""meterflow command line.

    python3 -m meterflow.cli run [--config PATH] [--out DIR]
    python3 -m meterflow.cli show-config [--config PATH]
"""
import argparse
import json

from .config import DEFAULT_PATH, load_config
from .pipeline import run


def main(argv=None):
    ap = argparse.ArgumentParser(prog='meterflow')
    ap.add_argument('command', choices=['run', 'show-config'])
    ap.add_argument('--config', default=DEFAULT_PATH)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.command == 'show-config':
        print(json.dumps(cfg, indent=1))
        return 0
    s = run(cfg, args.out)
    for name, st in s['vendors'].items():
        print('%-8s %3d files  %4d readings  %3d meters  %10.3f kWh  rejected: %d' % (
            name, st['files'], st['readings'], len(st['meters']), st['total_kwh'], len(st['rejected'])))
    print('alerts:', len(s['alerts']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
'''

DASHBOARD_PY = '''"""meterflow dashboard (stdlib only). Loads the settings and runs the pipeline once at start-up.

    python3 -m meterflow.dashboard --port 8112 [--config PATH]      (or ./dev.sh start|restart)
"""
import argparse
import sys
import urllib.parse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import DEFAULT_PATH, load_config
from .pipeline import run

STATE = {}
CSS = """body{font:14px/1.45 'DejaVu Sans',Arial,sans-serif;margin:0;background:#f4f6f8;color:#1d2733}
header{background:#123b5c;color:#fff;padding:14px 28px;display:flex;gap:28px;align-items:baseline}
header b{font-size:20px} header a{color:#cfe3f5;text-decoration:none} main{padding:20px 28px}
table{border-collapse:collapse;background:#fff;margin:10px 0 24px;min-width:640px}
th,td{padding:7px 12px;border-bottom:1px solid #e3e8ee;text-align:left} th{background:#eef2f6;font-size:12px}
td.num{text-align:right;font-variant-numeric:tabular-nums} .bad{color:#b3261e} pre{background:#fff;padding:12px}"""


def page(title, body):
    cfg = STATE['cfg']
    return ('<!doctype html><html><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>'
            '<header><b>%s</b><a href="/">Overview</a><a href="/alerts">Alerts</a><a href="/config">Config</a></header>'
            '<main>%s</main></body></html>' % (escape(title), CSS, escape(cfg['dashboard']['title']), body))


def overview():
    s = STATE['summary']
    rows = ''.join(
        '<tr id="vendor-%s"><td>%s</td><td>%s</td><td class="num files">%d</td><td class="num rejected">%d</td>'
        '<td class="num meters">%d</td><td class="num readings">%d</td><td class="num kwh">%.3f</td></tr>' % (
            n, n, escape(st['format']), st['files'], len(st['rejected']), len(st['meters']), st['readings'],
            st['total_kwh']) for n, st in s['vendors'].items())
    meters = ''.join('<tr id="meter-%s"><td>%s</td><td>%s</td><td class="num kwh">%.3f</td></tr>' % (
        m, n, m, kwh) for n, st in s['vendors'].items() for m, kwh in sorted(st['meters'].items()))
    rej = ''.join('<li class="bad">%s: %s</li>' % (n, escape(r)) for n, st in s['vendors'].items() for r in st['rejected'])
    return page('Overview', '<h2>Vendors</h2><table><tr><th>Vendor</th><th>Format</th><th>Files</th><th>Rejected</th>'
                            '<th>Meters</th><th>Readings</th><th>Total kWh</th></tr>%s</table>'
                            '<h2>Rejected files</h2><ul>%s</ul><h2>Meters</h2><table><tr><th>Vendor</th><th>Meter</th>'
                            '<th>Total kWh</th></tr>%s</table>' % (rows, rej or '<li>none</li>', meters))


def alerts():
    a = STATE['summary']['alerts']
    rows = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="num">%.3f</td></tr>' % (
        x['ts'], x['vendor'], x['meter'], x['kwh']) for x in a)
    return page('Alerts', '<h2>%d alerts</h2><table><tr><th>Interval end (UTC)</th><th>Vendor</th><th>Meter</th>'
                          '<th>kWh</th></tr>%s</table>' % (len(a), rows))


def config_page():
    cfg = dict(STATE['cfg'])
    src = cfg.pop('_source', '?')
    import json
    return page('Config', '<h2>Configuration</h2><p>Loaded from: <code id="config-source">%s</code></p><pre>%s</pre>' % (
        escape(src), escape(json.dumps(cfg, indent=2))))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\\n' % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        routes = {'/': overview, '/alerts': alerts, '/config': config_page}
        status, body = (200, routes[path]()) if path in routes else (404, page('Not found', '<h2>Not found</h2>'))
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=None)
    ap.add_argument('--config', default=DEFAULT_PATH)
    args = ap.parse_args()
    STATE['cfg'] = load_config(args.config)
    STATE['summary'] = run(STATE['cfg'])
    port = args.port or STATE['cfg']['dashboard']['port']
    print('meterflow dashboard on http://127.0.0.1:%d/' % port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
'''

TEST_CONFIG = '''import os
import tempfile
import unittest

from meterflow.config import load_config


class ConfigTest(unittest.TestCase):
    def test_repo_settings(self):
        cfg = load_config()
        self.assertEqual(cfg['dashboard']['port'], 8112)
        self.assertIs(cfg['alerts']['enabled'], True)
        self.assertEqual(cfg['alerts']['notify'][0], 'grid-ops@elbmark-energie.example')
        self.assertEqual(cfg['vendors']['acme']['format'], 'acme_csv')

    def test_types(self):
        path = os.path.join(tempfile.mkdtemp(), 'settings.ini')
        with open(path, 'w') as f:
            f.write("""[pipeline]
inbox_dir = in
out_dir = out
timezone = UTC
interval_minutes = 5
[alerts]
enabled = no
max_kwh_per_interval = 1.5
notify = a@x, b@x
[dashboard]
title = T
port = 9000
[vendor:x]
enabled = false
format = acme_csv
inbox = x
meter_prefix = X
""")
        cfg = load_config(path)
        self.assertEqual(cfg['pipeline']['interval_minutes'], 5)
        self.assertIs(cfg['alerts']['enabled'], False)
        self.assertEqual(cfg['alerts']['max_kwh_per_interval'], 1.5)
        self.assertEqual(cfg['alerts']['notify'], ['a@x', 'b@x'])
        self.assertEqual(cfg['vendors']['x'], {'enabled': False, 'format': 'acme_csv', 'inbox': 'x', 'meter_prefix': 'X'})


if __name__ == '__main__':
    unittest.main()
'''

TEST_PARSERS = '''import os
import unittest
from datetime import datetime, timezone

from meterflow.parsers import acme, voltis

INBOX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'inbox')


class ParserTest(unittest.TestCase):
    def test_acme(self):
        rs = acme.parse(os.path.join(INBOX, 'acme', 'acme_20261005.csv'))
        self.assertTrue(rs)
        self.assertTrue(all(r.meter_id.startswith('AC-') for r in rs))
        self.assertEqual(rs[0].ts.tzinfo, timezone.utc)

    def test_voltis_local_time_and_wh(self):
        rs = voltis.parse(os.path.join(INBOX, 'voltis', 'voltis_20261005.jsonl'))
        first = rs[0]
        self.assertEqual(first.ts, datetime(2026, 10, 4, 22, 15, tzinfo=timezone.utc))   # 00:15 CEST
        self.assertLess(first.kwh, 5)


if __name__ == '__main__':
    unittest.main()
'''

TEST_PIPELINE = '''import tempfile
import unittest

from meterflow.config import load_config
from meterflow.pipeline import run


class PipelineTest(unittest.TestCase):
    def test_run_dev_inbox(self):
        s = run(load_config(), tempfile.mkdtemp())
        self.assertIn('acme', s['vendors'])
        self.assertIn('voltis', s['vendors'])
        for st in s['vendors'].values():
            self.assertGreater(st['readings'], 0)
            self.assertEqual(st['rejected'], [])


if __name__ == '__main__':
    unittest.main()
'''

CHECK_SH = """#!/usr/bin/env bash
# Run before every commit: unit tests + a full pipeline run on the dev inbox.
set -e
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -t . -q
python3 -m meterflow.cli run --out "$(mktemp -d)"
echo "check.sh: all good"
"""

LAUNCH_JSON = """{
    // VS Code run/debug configurations for meterflow
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Dashboard",
            "type": "python",
            "request": "launch",
            "module": "meterflow.dashboard",
            "args": ["--port", "8112", "--config", "settings.ini"],
            "cwd": "${workspaceFolder}"
        },
        {
            "name": "Run pipeline",
            "type": "python",
            "request": "launch",
            "module": "meterflow.cli",
            "args": ["run", "--config", "settings.ini"],
            "cwd": "${workspaceFolder}"
        }
    ]
}
"""

README = """# meterflow

Ingest pipeline for the smart-meter readings that our metering vendors deliver to Elbmark Energie, plus a small
dashboard. Python 3.10+, standard library only.

## Running

    ./dev.sh start                                   # dashboard on http://127.0.0.1:8112/ (stop|restart|status|log)
    python3 -m meterflow.cli run                     # pipeline -> data/out/readings.csv + summary.json
    python3 -m meterflow.cli show-config

The dashboard loads the settings and runs the pipeline once at start-up: restart it (`./dev.sh restart`) after
changing code, settings or inbox files.

## Configuration

All settings live in `settings.ini` in the repository root (paths are relative to it):

| section | keys |
|---|---|
| `[pipeline]` | `inbox_dir`, `out_dir`, `timezone`, `interval_minutes` |
| `[alerts]` | `enabled`, `max_kwh_per_interval`, `notify` (comma-separated addresses) |
| `[dashboard]` | `title`, `port` |
| `[vendor:<name>]` | `enabled`, `format` (parser name), `inbox` (sub-folder of `inbox_dir`), `meter_prefix` |

Pass `--config PATH` to the CLI or the dashboard to use another file.

## Supported vendors

| vendor | format | files | notes |
|---|---|---|---|
| ACME Metering | `acme_csv` | `*.csv`, semicolon separated | UTC timestamps, kWh |
| Voltis | `voltis_jsonl` | `*.jsonl` | local time + zone, Wh |

Adding a vendor: see `docs/vendors/ONBOARDING.md`.

## Checks

    scripts/check.sh            # unit tests + full pipeline run; must pass before every commit
"""

ADR = """# ADR-0007: TOML instead of INI for meterflow settings

Status: accepted (2026-10-14, Jana Petersen, Ole Brandt)

## Context
`settings.ini` only has strings; `config.py` converts types by hand, lists are comma-separated strings and booleans
are spelled `yes`/`on`/`true` depending on who edited the file. Deployment configs are copied around by hand.

## Decision
1. The settings move to **`settings.toml`** in the repository root; `settings.ini` is deleted in the same change.
   Nothing (code, tests, scripts, VS Code launch configurations, docs) may refer to the INI file afterwards.
2. Same keys and sections, with native TOML types:
   - section `[vendor:<name>]` becomes the table `[vendors.<name>]`;
   - integers and floats unquoted, booleans `true`/`false`, `notify` becomes an array of strings;
   - all values must be identical to what `load_config()` returns today (same dict, same types).
3. `meterflow.config.load_config()` keeps its signature and return value, reads TOML with `tomllib` on Python 3.11+
   and with the vendored `meterflow._vendor.tomli` on 3.10 (our servers). Default path: `settings.toml`.
4. Environment-specific files live in `deploy/<env>.toml` and have the same structure. Ops will hand over the current
   production values; they become `deploy/prod.toml`.

## Consequences
Ops deploy `deploy/prod.toml` to `/etc/meterflow/settings.toml` from the next release on.
"""

ONBOARDING = """# Onboarding a new metering vendor

1. Put the vendor's interface specification in `docs/vendors/` and sample deliveries in `data/inbox/<vendor>/`.
2. Write `meterflow/parsers/<vendor>.py` with `parse(path) -> list[Reading]` (`meterflow/model.py`):
   - `meter_id` exactly as the vendor sends it (no padding),
   - `ts` = END of the interval, timezone-aware **UTC** (`meterflow.timeutil` has helpers),
   - `kwh` in kWh, `quality` `'valid'` or `'estimated'`; drop records the vendor marks as faulty;
   - raise `ValueError` if the whole file must be rejected.
3. Register it in `meterflow/parsers/__init__.py` (`PARSERS`, key = format name).
4. Add a vendor section to the settings (`enabled`, `format`, `inbox`, `meter_prefix`).
5. Unit tests in `tests/test_<vendor>.py` using the sample deliveries.
6. Add the vendor to the table in README.md, run `scripts/check.sh`, restart the dashboard and check the numbers.
"""

GITIGNORE = "__pycache__/\n*.pyc\ndata/out/\nlogs/\n.devserver.pid\n"


# ------------------------------------------------------------------ sample data
def acme_files(r):
    out = {}
    for day in (5, 6):
        lines = ["meter;timestamp_utc;kwh;status"]
        for m in ("AC-100231", "AC-100232", "AC-100519"):
            for k in range(8):
                ts = dt.datetime(2026, 10, day, 6, 15, tzinfo=UTC) + dt.timedelta(minutes=15 * k)
                st = r.choices(["OK", "EST", "ERR"], [20, 2, 1])[0]
                lines.append(f"{m};{ts:%Y-%m-%dT%H:%M:%SZ};{r.uniform(0.2, 2.4):.3f};{st}")
        out[f"data/inbox/acme/acme_202610{day:02d}.csv"] = "\n".join(lines) + "\n"
    return out


def voltis_files(r):
    out = {}
    for day in (5, 6):
        lines = []
        for m in ("VT-7781", "VT-7790"):
            for k in range(8):
                end = dt.datetime(2026, 10, day, 0, 15) + dt.timedelta(minutes=15 * k)
                lines.append(json.dumps({"device": m, "end": end.strftime("%Y-%m-%d %H:%M"), "tz": "Europe/Berlin",
                                         "wh": r.randint(120, 900), "q": r.choice(["measured"] * 6 + ["substituted"])}))
        out[f"data/inbox/voltis/voltis_202610{day:02d}.jsonl"] = "\n".join(lines) + "\n"
    return out


KELVAR_METERS = ["KV2210004417", "KV2210004418", "KV33017", "KV2210009902"]


def kmf(records, created, sender="KELV01", trailer=None):
    """records: (meter, local end datetime, wh, status)."""
    lines = [f"H{created:%Y%m%d}{sender}"]
    for m, end, wh, st in records:
        lines.append(f"D{m:<12}{end:%Y%m%d%H%M}{wh:010d}{st}15")
    lines.append(f"T{(len(records) if trailer is None else trailer):06d}")
    return "\r\n".join(lines) + "\r\n"


def kelvar_records(r, day, hour, n=8, meters=KELVAR_METERS):
    recs = []
    for m in meters:
        for k in range(n):
            end = dt.datetime(2026, 10, day, hour, 15) + dt.timedelta(minutes=15 * k)
            st = r.choices("VEF", [16, 2, 1])[0]
            recs.append((m, end, r.randint(150, 980), st))
    return recs


def kelvar_expected(recs):
    """[(meter, utc 'YYYY-MM-DDTHH:MM', kwh, quality)] following the KMF spec."""
    out = []
    for m, end, wh, st in recs:
        if st == "F":
            continue
        u = end.replace(tzinfo=BERLIN).astimezone(UTC)
        out.append([m, u.strftime("%Y-%m-%dT%H:%M"), round(wh / 1000, 4), "valid" if st == "V" else "estimated"])
    return out


# ------------------------------------------------------------------ images
def prod_screenshot(path):
    lines = ["jana@mf-prod-01:~$ cat /etc/meterflow/settings.ini"] + PROD_INI.rstrip("\n").split("\n") + \
            ["jana@mf-prod-01:~$ "]
    W, H = 1340, 40 + 24 * (len(lines) + 2) + 40
    im = Image.new("RGB", (W, H), "#300a24")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 36), fill="#2c2c2c")
    d.text((W // 2 - 150, 9), "jana@mf-prod-01: ~", fill="#dddddd", font=font(16, bold=True))
    for i, c in enumerate(("#e95420", "#888", "#888")):
        d.ellipse((W - 30 - 26 * i, 10, W - 14 - 26 * i, 26), fill=c)
    y = 50
    for ln in lines:
        color = "#8ae234" if ln.startswith("jana@") else ("#ad7fa8" if ln.startswith(";") else "#ffffff")
        if ln.startswith("jana@"):
            d.text((14, y), "jana@mf-prod-01", fill="#8ae234", font=font(17, mono=True, bold=True))
            d.text((14 + d.textlength("jana@mf-prod-01", font=font(17, mono=True, bold=True)), y),
                   ":~$" + ln.split("$", 1)[1], fill="#ffffff", font=font(17, mono=True))
        else:
            d.text((14, y), ln, fill=color, font=font(17, mono=True))
        y += 24
    im.save(path, optimize=True)


def kmf_spec_pdf(path, sample_lines):
    pages = []
    W, H = 1240, 1754
    # page 1
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    d.text((100, 90), "KELVAR METERING GmbH", fill=0, font=font(30, bold=True))
    d.text((100, 135), "Interface Specification  KMF Export  -  Version 2.1", fill=0, font=font(26))
    d.text((100, 175), "Document KM-IF-021, 2026-03-02, page 1 of 2", fill=60, font=font(18))
    d.line((100, 215, W - 100, 215), fill=0, width=2)
    y = 250
    paras = [
        ("1  General", ["One file per delivery, ASCII text, every line terminated by CR LF.",
                        "File name: KMF_<sender id>_<creation date YYYYMMDD>.kmf",
                        "Every file consists of exactly one header record (first line), any number of",
                        "data records and exactly one trailer record (last line)."]),
        ("2  Header record", ["Pos 1        record type 'H'", "Pos 2-9      creation date, YYYYMMDD",
                              "Pos 10-15    sender id (6 characters)"]),
        ("3  Data record (fixed width, positions are 1-based and inclusive)",
         ["Pos 1        record type 'D'",
          "Pos 2-13     meter id, 12 characters, left-aligned, padded with blanks",
          "Pos 14-25    END of the measuring interval, YYYYMMDDhhmm,",
          "             LOCAL time Europe/Berlin (CET/CEST), not UTC",
          "Pos 26-35    energy of the interval in Wh (watt-hours), 10 digits, leading zeros",
          "Pos 36       status:  V = valid measurement",
          "                      E = estimated (substitute value)",
          "                      F = faulty, value must not be used",
          "Pos 37-38    interval length in minutes (always 15)"]),
        ("4  Trailer record", ["Pos 1        record type 'T'",
                               "Pos 2-7      number of data records in the file, 6 digits, leading zeros"]),
    ]
    for head, body in paras:
        d.text((100, y), head, fill=0, font=font(24, bold=True))
        y += 44
        for ln in body:
            d.text((130, y), ln, fill=0, font=font(21, mono=True) if ln.startswith(("Pos", "  ", "     ")) else font(21))
            y += 34
        y += 26
    pages.append(scanify(im, 1))
    # page 2
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    d.text((100, 90), "KMF Export v2.1  -  page 2 of 2", fill=60, font=font(18))
    y = 150
    d.text((100, y), "5  Processing rules for the receiving party", fill=0, font=font(24, bold=True))
    y += 46
    for ln in ["a) Records with status F must be discarded.",
               "b) Records with status E are substitute values and must be flagged as such.",
               "c) If the number of data records does not match the trailer, the file is",
               "   incomplete and must be rejected AS A WHOLE (do not load any of its records).",
               "d) Meter ids are sent without the blank padding being significant."]:
        d.text((130, y), ln, fill=0, font=font(21))
        y += 34
    y += 30
    d.text((100, y), "6  Example (first lines of a delivery)", fill=0, font=font(24, bold=True))
    y += 50
    d.rectangle((110, y - 10, W - 110, y + 34 * len(sample_lines) + 10), outline=0, width=1)
    for ln in sample_lines:
        d.text((130, y), ln, fill=0, font=font(22, mono=True))
        y += 34
    y += 30
    d.text((130, y), "Positions:  1|2.........13|14........25|26......35|36|37-38", fill=0, font=font(20, mono=True))
    y += 70
    d.text((100, y), "Questions: integration@kelvar-metering.example", fill=0, font=font(20))
    pages.append(scanify(im, 2))
    scan_pdf(pages, path)


def build(out):
    os.makedirs(out, exist_ok=True)
    r = random.Random(20261022)
    k1 = kelvar_records(r, 5, 6)
    k2 = kelvar_records(r, 6, 6)
    k3 = kelvar_records(r, 7, 6)
    kfiles = {
        "data/inbox/kelvar/KMF_KELV01_20261005.kmf": kmf(k1, dt.date(2026, 10, 5)),
        "data/inbox/kelvar/KMF_KELV01_20261006.kmf": kmf(k2, dt.date(2026, 10, 6)),
        # incomplete delivery: the last three records are missing, the trailer still says 32
        "data/inbox/kelvar/KMF_KELV01_20261007.kmf": kmf(k3[:-3], dt.date(2026, 10, 7), trailer=len(k3)),
    }
    good = kelvar_expected(k1) + kelvar_expected(k2)
    meters = {}
    for m, _, kwh, _ in good:
        meters[m] = round(meters.get(m, 0) + kwh, 6)
    tmp_pdf, tmp_png = os.path.join(out, "_spec.pdf"), os.path.join(out, "_prod.png")
    kmf_spec_pdf(tmp_pdf, kfiles["data/inbox/kelvar/KMF_KELV01_20261005.kmf"].split("\r\n")[:5])
    prod_screenshot(tmp_png)

    # hidden test file for the checker: padded short id, an F record, an E record, winter time (CET), Wh values
    hidden = [("KV33017", dt.datetime(2026, 11, 3, 9, 0), 1234, "V"), ("KV33017", dt.datetime(2026, 11, 3, 9, 15), 87, "E"),
              ("KV2210004417", dt.datetime(2026, 10, 20, 23, 45), 450, "F"),
              ("KV2210004417", dt.datetime(2026, 10, 21, 0, 0), 9, "V"),
              ("KV0000000001", dt.datetime(2026, 12, 31, 23, 45), 2500, "V")]
    files = {".gitignore": GITIGNORE, "README.md": README, "settings.ini": SETTINGS_INI,
             "meterflow/__init__.py": INIT_PY, "meterflow/model.py": MODEL_PY, "meterflow/timeutil.py": TIMEUTIL_PY,
             "meterflow/config.py": CONFIG_PY, "meterflow/pipeline.py": PIPELINE_PY, "meterflow/cli.py": CLI_PY,
             "meterflow/dashboard.py": DASHBOARD_PY, "meterflow/parsers/__init__.py": PARSERS_INIT,
             "meterflow/parsers/acme.py": ACME_PY, "meterflow/parsers/voltis.py": VOLTIS_PY,
             "tests/__init__.py": "", "tests/test_config.py": TEST_CONFIG, "tests/test_parsers.py": TEST_PARSERS,
             "tests/test_pipeline.py": TEST_PIPELINE, "scripts/check.sh": CHECK_SH, ".vscode/launch.json": LAUNCH_JSON,
             ".vscode/settings.json": json.dumps({"python.testing.unittestEnabled": True,
                                                  "python.testing.unittestArgs": ["-s", "tests", "-t", "."]}, indent=4) + "\n",
             **acme_files(r), **voltis_files(r)}
    vendor = {"meterflow/_vendor/__init__.py": '"""Third-party code vendored for Python 3.10 servers."""\n',
              **tomli_files("meterflow/_vendor/")}
    history = [
        ("2026-06-03T10:00:00", JANA, files, "meterflow: ingest pipeline for ACME and Voltis + dashboard"),
        ("2026-09-22T15:10:00", OLE, {"dev.sh": dev_sh("meterflow.dashboard", PORT, "meterflow dashboard"),
                                      "docs/vendors/ONBOARDING.md": ONBOARDING}, "Add dev.sh and vendor onboarding notes"),
        ("2026-10-14T11:30:00", JANA, {"docs/adr/0007-toml-config.md": ADR, **vendor},
         "ADR-0007: move settings to TOML; vendor tomli 2.0.1 for Python 3.10"),
        ("2026-10-16T09:05:00", OLE, {"docs/ops/prod-settings.png": open(tmp_png, "rb").read()},
         "Add ops' screenshot of the current production settings"),
        ("2026-10-20T16:45:00", OLE, {**kfiles, "docs/vendors/Kelvar_KMF_Interface_v2.1.pdf": open(tmp_pdf, "rb").read()},
         "Kelvar: interface spec and first sample deliveries"),
    ]
    info = make_repo(os.path.join(out, "meterflow.tar.gz"), "meterflow", history, JANA)
    os.remove(tmp_pdf)
    os.remove(tmp_png)
    json.dump({"base": info["base"], "port": PORT, "dev": DEV_EXPECTED, "prod": PROD_EXPECTED,
               "kelvar": {"meters": {m: round(v, 3) for m, v in meters.items()}, "total_kwh": round(sum(meters.values()), 3),
                          "readings": len(good), "files_ok": 2, "rejected": 1, "meter_prefix": "KV", "inbox": "kelvar"},
               "hidden_kmf": kmf(hidden, dt.date(2026, 12, 31)), "hidden_expected": kelvar_expected(hidden),
               "hidden_bad_trailer": kmf(hidden, dt.date(2026, 12, 31), trailer=7)},
              open(os.path.join(out, "expected.json"), "w"), indent=1)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/d2_build")
