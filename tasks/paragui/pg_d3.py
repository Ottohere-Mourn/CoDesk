"""D3 - kestrel-site (~/projects/kestrel-site, live preview on 8113): one repo, one shared page frame
(templates/base.html), one live preview that rebuilds on every change, one VS Code window, one Chrome tab.

  pgd3restyle  landing page to the 2026 design (scanned style guide PDF + mockup PNG) + header phone button
  pgd3pages    three pages from a Writer document (price list only as a scanned image) + nav order + broken links
"""
from __future__ import annotations

import html as htmlmod
import re

from evaluation_examples.task_class.pg_common import HOME, expected, sh, upload
from evaluation_examples.task_class.pg_dlib import failed, inspect, mine, score, setup_repo, touched

NAME = "kestrel-site"
REPO = f"{HOME}/projects/{NAME}"
PORT = 8113
A_FILES = {"static/css/tokens.css", "static/css/site.css", "templates/home.html", "templates/base.html", "content/index.md"}
B_PAGES = {"content/treatments.md", "content/team.md", "content/prices.md"}


def setup(sc):
    upload(sc, [("d3/Website_update_Oct2026.docx", f"{HOME}/Documents/Website_update_Oct2026.docx")])
    setup_repo(sc, "d3/kestrel-site.tar.gz", NAME, PORT, [f"http://127.0.0.1:{PORT}/"])


BODY = r'''
from html.parser import HTMLParser
base = P['base']
OUT['commits'] = commits(base)
OUT['status'] = git('status', '--porcelain')
OUT['tracked'] = git('ls-files').split('\n')
OUT['base_diffs'] = {c['hash']: diff_text(c['hash'], ['templates/base.html']) for c in OUT['commits']}

def tokens(css):
    css = re.sub(r'/\*.*?\*/', '', css or '', flags=re.S)
    return {m.group(1): m.group(2).strip() for m in re.finditer(r'--([\w-]+)\s*:\s*([^;]+);', css)}
OUT['tokens'] = tokens(read('static/css/tokens.css'))
c = Client(P['port'])
st, _, css = c.req('/static/css/tokens.css')
OUT['served_tokens'] = tokens(css) if st == 200 else None
OUT['pages'] = {}
for path in ('/', '/contact.html', '/news.html', '/treatments.html', '/team.html', '/prices.html'):
    st, _, body = c.req(path)
    OUT['pages'][path] = [st, body if st == 200 else body[:300]]

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('href', 'src') and v:
                self.links.append(v)
start = 'http://127.0.0.1:%d/' % P['port']
todo, seen, status, broken = [start], set(), {}, []
while todo and len(seen) < 60:
    url = todo.pop()
    if url in seen:
        continue
    seen.add(url)
    st, hd, body = Client(P['port']).req(url[len(start) - 1:])
    status[url] = st
    if st != 200 or 'html' not in {k.lower(): v for k, v in hd.items()}.get('content-type', ''):
        continue
    p = Links()
    p.feed(body)
    for link in p.links:
        target = urllib.parse.urljoin(url, link).split('#')[0]
        parts = urllib.parse.urlsplit(target)
        if parts.scheme not in ('http', 'https') or parts.netloc != urllib.parse.urlsplit(start).netloc:
            continue
        if target not in status:
            status[target] = Client(P['port']).req(target[len(start) - 1:])[0]
        if status[target] != 200:
            broken.append([url, link, status[target]])
        elif target.endswith('.html') or target.endswith('/'):
            todo.append(target)
OUT['broken'] = broken
OUT['crawled'] = len(seen)
'''


def _inspect(env):
    exp = expected("d3")
    return inspect(env, REPO, BODY, {"base": exp["base"], "port": PORT}), exp


def _norm_value(v: str) -> str:
    v = v.strip().lower()
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*1(?:\.0+)?\s*)?\)", v)
    if m:
        return "#%02x%02x%02x" % tuple(int(x) for x in m.groups())
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        return "#" + "".join(ch * 2 for ch in v[1:])
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(px|%|rem|em)?", v)
    if m:
        num = float(m.group(1))
        return ("%g" % num) + (m.group(2) or "")
    return v


def _token_ok(name: str, got: str | None, want: str) -> bool:
    if got is None:
        return False
    g = _norm_value(got)
    if name == "radius-button":
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(px|%)", g)
        return bool(m) and ((m.group(2) == "px" and float(m.group(1)) >= 100) or (m.group(2) == "%" and float(m.group(1)) >= 50))
    return g == _norm_value(want)


def _text(html: str) -> str:
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", html or ""))
    t = t.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", t).lower()


def _added(diff: str) -> str:
    return "\n".join(ln for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))


def _nav(html: str) -> list[str]:
    m = re.search(r"<nav\b[^>]*>(.*?)</nav>", html or "", re.S | re.I)
    if not m:
        return []
    out = []
    for h in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', m.group(1)):
        h = h.strip()
        if re.match(r"(tel|mailto|javascript):|#|https?://(?!127\.0\.0\.1)", h, re.I):
            continue  # not a page of the site (e.g. the header phone button)
        if h.startswith("http://127.0.0.1"):
            h = "/" + h.split("/", 3)[-1]
        if not h.startswith("/"):
            h = "/" + h.lstrip("./")
        if h in ("/index.html",):
            h = "/"
        out.append(h)
    return out


def _dirty(info) -> set[str]:
    return {ln[3:].strip() for ln in info["status"].splitlines() if ln[:2].strip()}


def evaluate_restyle(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    mine_c = [c for c in mine(info, r"restyle|landing|design|2026") if not re.search(r"treatments|team|prices|pages", c["subject"], re.I)]
    files = touched(mine_c)
    added_base = "\n".join(_added(info["base_diffs"].get(c["hash"], "")) for c in mine_c)
    focused = bool(files) and all(f in A_FILES or f.startswith("static/img/") for f in files) and \
        not re.search(r"treatments\.html|team\.html|prices\.html|imprint\.html", added_base)
    tok = info["tokens"]
    colours = [k for k in exp["tokens"] if k.startswith("color-")]
    others = [k for k in exp["tokens"] if not k.startswith("color-")]
    col_ok = all(_token_ok(k, tok.get(k), exp["tokens"][k]) for k in colours)
    oth_ok = all(_token_ok(k, tok.get(k), exp["tokens"][k]) for k in others)
    served_ok = info["served_tokens"] is not None and all(
        _token_ok(k, info["served_tokens"].get(k), v) for k, v in exp["tokens"].items())
    st, home = info["pages"]["/"]
    text = _text(home)
    hero = exp["hero"]
    hero_ok = st == 200 and _text(hero["headline"]).strip(". ") in text and \
        "bremen-neustadt" in text and "appointments within five working days" in text
    cta_ok = any(re.search(r"/contact\.html$|^contact\.html$", h.strip()) and "book an appointment" in _text(t)
                 for h, t in re.findall(r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', home or "", re.S | re.I))
    pos = [text.find(c.lower()) for c in exp["cards"]]
    cards_ok = all(p >= 0 for p in pos) and pos == sorted(pos) and "welcome to kestrel physio" not in text and \
        "classic massage" not in text
    phone_ok = all(any(re.sub(r"\D", "", h).endswith("4215550193") for h in re.findall(r'href\s*=\s*["\']tel:([^"\']+)', info["pages"][p][1] or ""))
                   for p in ("/", "/contact.html", "/news.html"))
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", focused, 1),
        ("colour_tokens_from_style_guide", col_ok, 1.5),
        ("type_and_spacing_tokens_from_style_guide", oth_ok, 1.5),
        ("tokens_committed", "static/css/tokens.css" in files and "static/css/tokens.css" not in _dirty(info), 0.5),
        ("hero_copy_from_mockup", hero_ok, 1),
        ("cta_button_to_contact", cta_ok, 1),
        ("three_cards_in_mockup_order", cards_ok, 1),
        ("phone_button_on_every_page", phone_ok, 1),
        ("preview_serves_new_tokens", served_ok, 0.5),
    ]
    caps = [(not (col_ok or oth_ok), 0.4, "design tokens not updated"), (not mine_c, 0.5, "no restyle commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "tokens": tok, "home_status": st})


def evaluate_pages(env, dest: str) -> dict:
    info, exp = _inspect(env)
    if not info or "error" in info or info.get("missing"):
        return failed("repo not inspectable", info)
    mine_c = [c for c in mine(info, r"treatments|team|prices|pages") if not re.search(r"restyle|landing", c["subject"], re.I)]
    files = touched(mine_c)
    added_base = "\n".join(_added(info["base_diffs"].get(c["hash"], "")) for c in mine_c)
    focused = bool(files) and not (files & (A_FILES - {"templates/base.html"})) and "tel:" not in added_base
    pages = info["pages"]
    titles = {"/treatments.html": "treatments", "/team.html": "team", "/prices.html": "prices"}
    served = [p for p, t in titles.items() if pages[p][0] == 200 and
              re.search(r"<title>[^<]*%s" % t, pages[p][1] or "", re.I)]
    tr = _text(pages["/treatments.html"][1])
    treat_ok = pages["/treatments.html"][0] == 200 and all(n.lower() in tr for n in exp["treatments"])
    tm = _text(pages["/team.html"][1])
    team_ok = pages["/team.html"][0] == 200 and all(n.lower() in tm for n, _, _ in exp["team"]) and \
        all(k.lower() in tm for k in ("OMT", "DOSB", "MLD/CDT", "Bobath", "M.Sc. Sports Science"))
    phtml = pages["/prices.html"][1] or ""
    chunks = [_text(c) for c in re.split(r"<tr\b|<li\b|<p\b|<h\d\b|\n", phtml, flags=re.I)]
    price_rows = []
    for name, dur, price in exp["prices"]:
        num = price.split(".")[0]
        rx = re.compile(r"(?<![\d.,])%s(?:[.,]00|[.,]-)?(?![\d])" % num)
        dur_n = dur.split()[0]
        ok = any(name.lower() in ch and re.search(r"(?<!\d)%s\s*(min|sessions?|x)" % dur_n, ch) and rx.search(ch.replace(dur, ""))
                 for ch in chunks)
        price_rows.append(ok)
    prices_ok = pages["/prices.html"][0] == 200 and all(price_rows)
    navs = {p: _nav(pages[p][1]) for p in ("/", "/contact.html", "/prices.html") if pages[p][0] == 200}
    nav_ok = len(navs) == 3 and all(n == exp["nav"] for n in navs.values())
    dirty = _dirty(info)
    checks = [
        ("commit_exists", bool(mine_c), 1),
        ("commit_focused", focused, 1),
        ("three_pages_served_with_titles", len(served) == 3, 1),
        ("treatments_content", treat_ok, 1),
        ("team_content", team_ok, 1),
        ("prices_table_from_scan", prices_ok, 2),
        ("navigation_order_on_all_pages", nav_ok, 1),
        ("no_broken_links", not info["broken"] and info["crawled"] >= 5, 1),
        ("pages_committed", B_PAGES <= files and not (B_PAGES & dirty) and B_PAGES <= set(info["tracked"]), 0.5),
    ]
    caps = [(len(served) < 2, 0.4, "new pages not served"), (not mine_c, 0.5, "no pages commit")]
    return score(checks, caps, {"commits": [c["subject"] for c in info["commits"]], "commit_files": sorted(files),
                                "served": served, "price_rows": price_rows, "navs": navs, "broken": info["broken"][:8]})
