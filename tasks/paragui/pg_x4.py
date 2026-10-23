"""X4 - research-group admin at the University of Northbridge (Thunderbird + LabDesk web app in Chrome + Calc + git repo).

A (pgx4claims): ECCV 2026 travel claims - receipts (phone photos / scans) from four travellers' mails + the Finance
   policy -> one submitted LabDesk claim per traveller (caps, exclusions, grant) -> receipt mails filed into
   Claims/ECCV 2026 -> summary workbook -> draft to School Finance with claim numbers and totals.
B (pgx4pubs): publication lists - acceptance mails, camera-ready PDFs (attached to the same receipt mails) and an
   arXiv notice -> LabDesk publication records of both groups (update a preprint, add three) -> BibTeX entries in the
   Marsh Lab website repo + commit -> announcement draft to the groups' mailing list.
Shared live state: one Thunderbird (A moves the mails that carry B's camera-readies), one Chrome with one LabDesk
session whose Group selector (Marsh / Okafor) scopes claim and publication lists and the default group of new records.
"""
from __future__ import annotations

import re
import unicodedata

from evaluation_examples.task_class import pg_common as pc
from evaluation_examples.task_class import pg_xcommon as xc

APP, PORT = "labdesk", 8124
SUMMARY = f"{pc.HOME}/Documents/Lab/ECCV2026_travel_summary.xlsx"
REPO = f"{pc.HOME}/projects/marsh-lab-website"
BIB = "_bibliography/papers.bib"


def setup(sc):
    stage = f"{pc.HOME}/.cache/pgx4"
    pc.upload(sc, [("x4/ECCV2026_travel_summary.xlsx", f"{stage}/ECCV2026_travel_summary.xlsx"),
                   ("x4/marsh-lab-website.tar.gz", f"{stage}/marsh-lab-website.tar.gz")])
    pc.sh(sc, f"mkdir -p ~/Documents/Lab ~/projects; [ -f {SUMMARY} ] || cp {stage}/ECCV2026_travel_summary.xlsx {SUMMARY}; "
              f"[ -d {REPO}/.git ] || tar xzf {stage}/marsh-lab-website.tar.gz -C ~/projects; "
              "mkdir -p ~/.config/Code/User && python3 - <<'PY'\n"
              "import json, os\np = os.path.expanduser('~/.config/Code/User/settings.json')\n"
              "try:\n    s = json.load(open(p))\nexcept Exception:\n    s = {}\n"
              "s.update({'security.workspace.trust.enabled': False, 'git.openRepositoryInParentFolders': 'always'})\n"
              "json.dump(s, open(p, 'w'), indent=1)\nPY")
    pc.start_webapp(sc, "x4/app_x4.py", APP, PORT, "x4/labdesk_seed.db")
    pc.start_thunderbird(sc, "x4/thunderbird-profile.tar.gz", "pgx4")
    pc.open_chrome(sc, [f"http://127.0.0.1:{PORT}/login"])
    sc.launch(["code", REPO])  # a second call just focuses the already open window


def _ascii(s) -> str:
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()


def _flat(s) -> str:
    return xc.flat(_ascii(re.sub(r"\\['`^\"~]|[{}]", "", str(s or ""))))


def _lastnames(names) -> list:
    return [_flat(n.split()[-1]) for n in names]


def _authors_ok(text, names) -> bool:
    return xc.in_order(_flat(text), _lastnames(names))


# ---------------------------------------------------------------- A: travel claims
def evaluate_claims(env, dest: str) -> dict:
    exp = pc.expected("x4")
    checks = {}
    q = pc.sql(env, pc.webapp_db(APP), {
        "claims": "SELECT c.id, c.number, c.member_id, c.group_id, c.grant_code, c.status FROM claims c WHERE c.id > %d" % exp["seed_claim_max_id"],
        "lines": "SELECT l.claim_id, l.date, l.currency, l.amount, l.gbp FROM claim_lines l WHERE l.deleted=0 AND l.claim_id > %d" % exp["seed_claim_max_id"]})
    if q is None:
        return pc.result(0.0, {"app_db": "unreadable"})
    lines = {}
    for ln in q["lines"]:
        lines.setdefault(ln["claim_id"], []).append(ln)
    per, info, got_claims = [], {}, {}
    for mid, t in exp["travellers"].items():
        cands = [c for c in q["claims"] if str(c["member_id"]) == mid]

        def parts(c):
            ls = lines.get(c["id"], [])
            sums = {}
            for ln in ls:
                sums[ln["currency"]] = round(sums.get(ln["currency"], 0) + ln["amount"], 2)
            total = round(sum(ln["gbp"] for ln in ls), 2)
            gbp_ok = abs(sums.get("GBP", 0) - t["sums"].get("GBP", 0)) < 0.006
            sek_ok = abs(sums.get("SEK", 0) - t["sums"].get("SEK", 0)) < 0.006
            rest_ok = not sums.get("EUR") and not sums.get("USD") and abs(total - t["gbp_total"]) <= 0.01 * t["gbp_total"]
            return [True, c["grant_code"] == t["grant"], c["status"] == "Submitted" and bool(c["number"]), gbp_ok, sek_ok, rest_ok], sums, total

        best = max(cands, key=lambda c: sum(parts(c)[0]), default=None)
        p, sums, total = parts(best) if best else ([False] * 6, {}, 0)
        per.append(sum(p) / 6)
        info[t["name"]] = {"claim": best["number"] if best else None, "grant": best["grant_code"] if best else None,
                           "status": best["status"] if best else None, "sums": sums, "gbp_total": total, "ok": p,
                           "extra_claims": max(0, len(cands) - 1)}
        if best:
            got_claims[mid] = {"number": best["number"], "total": total, "grant": best["grant_code"]}
    others = [c for c in q["claims"] if str(c["member_id"]) not in exp["travellers"]]
    no_extra = not others and all(v["extra_claims"] == 0 for v in info.values()) and any(per)
    checks["travellers"] = info
    checks["claims_for_others"] = len(others)

    # receipt mails filed
    boxes = xc.mailboxes(env) or {}
    loc = xc.where(boxes)
    filed = [any(f.lower().endswith("claims/eccv 2026") for f in loc.get(i, ())) and not any(xc.leaf(f) == "inbox" for f in loc.get(i, ()))
             for i in exp["receipt_mails"]]
    checks["receipt_mails_filed"] = f"{sum(filed)}/{len(filed)}"
    checks["folders"] = sorted(f for f in boxes if "claims" in f.lower())

    # summary workbook (cross-checked against LabDesk)
    path = pc.fetch(env, SUMMARY, dest + "_summary.xlsx")
    rows_ok = tot_ok = grant_ok = 0
    if path:
        try:
            rows = xc.xlsx_rows(path)
        except Exception as e:
            rows = []
            checks["summary_error"] = repr(e)[:150]
        for mid, t in exp["travellers"].items():
            g = got_claims.get(mid)
            last = _flat(t["name"].split()[-1])
            row = next((r for _, r in rows if any(last in _flat(v) for v in r if isinstance(v, str))), None)
            if row and g and g["number"]:
                rows_ok += any(g["number"] in str(v) for v in row)
                tot_ok += xc.has_amount(xc.cell_numbers([(0, 0, 0, v) for v in row]), g["total"], 0.011)
        want = {}
        for mid, t in exp["travellers"].items():
            g = got_claims.get(mid)
            want[t["grant"]] = round(want.get(t["grant"], 0) + (g["total"] if g else t["gbp_total"]), 2)
        lasts = [_flat(t["name"].split()[-1]) for t in exp["travellers"].values()]
        grant_rows = [r for _, r in rows if not any(ln in _flat(v) for v in r if isinstance(v, str) for ln in lasts)]
        for code, v in want.items():
            row = next((r for r in grant_rows if any(_flat(code) == _flat(x) for x in r if isinstance(x, str))
                        and xc.has_amount(xc.cell_numbers([(0, 0, 0, x) for x in r]), v, 0.011)), None)
            grant_ok += bool(row)
        checks.update({"summary_rows_with_claim_no": f"{rows_ok}/4", "summary_totals": f"{tot_ok}/4", "grant_totals": f"{grant_ok}/{len(want)}"})
    checks["summary_file"] = bool(path)

    # draft to Finance
    mine = [m for m in xc.outgoing(boxes, exp["msg"].values()) if xc.addressed(m, exp["finance"])]
    best_n = best_t = 0
    for m in mine:
        nums = xc.numbers(m["text"])
        n_ok = sum(bool(g["number"]) and g["number"] in m["text"] for g in got_claims.values())
        t_ok = sum(xc.has_amount(nums, g["total"], 0.011) for g in got_claims.values())
        if (n_ok, t_ok) > (best_n, best_t):
            best_n, best_t = n_ok, t_ok
    checks.update({"finance_draft": bool(mine), "draft_claim_numbers": f"{best_n}/4", "draft_totals": f"{best_t}/4"})

    score = (0.60 * sum(per) / 4 + 0.05 * no_extra + 0.07 * sum(filed) / len(filed) + 0.08 * rows_ok / 4 + 0.04 * tot_ok / 4
             + 0.04 * grant_ok / 3 + 0.06 * best_n / 4 + 0.06 * best_t / 4)
    submitted = sum(1 for v in info.values() if v["status"] == "Submitted")
    policy_errors = sum(1 for v in info.values() if not all(v["ok"][3:]))
    checks["claims_with_wrong_amounts"] = policy_errors
    score = xc.capped(score, [(submitted == 0, 0.3), (not path, 0.75), (policy_errors > 0, 0.7)])
    return pc.result(score, checks)


# ---------------------------------------------------------------- B: publications
INSPECT = r"""cd %s 2>/dev/null && python3 - <<'PY'
import json, subprocess
def run(*a):
    p = subprocess.run(a, capture_output=True, text=True)
    return p.stdout
commits = []
for line in run('git', 'log', '--format=%%H%%x09%%s', '%s..HEAD').splitlines():
    if '\t' in line:
        h, s = line.split('\t', 1)
        commits.append({'hash': h, 'subject': s, 'files': [f for f in run('git', 'show', '--name-only', '--format=', h).split('\n') if f]})
try:
    work = open('%s').read()
except OSError:
    work = ''
print('REPO' + json.dumps({'commits': commits, 'status': run('git', 'status', '--porcelain'), 'head_bib': run('git', 'show', 'HEAD:%s'),
                           'work_bib': work}))
PY"""


def parse_bib(text: str) -> dict:
    """{key: {'type':..., field: value}} with brace-depth aware values (good enough for hand-edited BibTeX)."""
    out = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        typ, key, i = m.group(1).lower(), m.group(2), m.end()
        fields, depth, j = {"type": typ, "_dup": key in out}, 1, i
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[i:j - 1]
        for fm in re.finditer(r"(\w+)\s*=\s*", body):
            k, s = fm.group(1).lower(), fm.end()
            if s < len(body) and body[s] == "{":
                d, e = 0, s
                while e < len(body):
                    d += body[e] == "{"
                    d -= body[e] == "}"
                    e += 1
                    if d == 0:
                        break
                val = body[s + 1:e - 1]
            elif s < len(body) and body[s] == '"':
                e = body.find('"', s + 1)
                val = body[s + 1:e]
            else:
                val = re.match(r"[^,\n]*", body[s:]).group(0)
            fields.setdefault(k, val.strip())
        if key in out:
            out[key]["_dup"] = True
        else:
            out[key] = fields
    return out


def _bib_author_lasts(field: str) -> str:
    names = [a.strip() for a in re.split(r"\s+and\s+", field or "") if a.strip()]
    return " ".join(n.split(",")[0] if "," in n else n.split()[-1] for n in names)


def evaluate_pubs(env, dest: str) -> dict:
    exp = pc.expected("x4")
    checks = {}
    q = pc.sql(env, pc.webapp_db(APP), {"pubs": "SELECT id, group_id, title, authors, venue, year, type, arxiv, deleted FROM pubs"})
    if q is None:
        return pc.result(0.0, {"app_db": "unreadable"})
    live = [p for p in q["pubs"] if not p["deleted"]]
    db_score, found = 0.0, 0
    detail = {}
    for k, P in exp["papers"].items():
        cands = [p for p in live if _flat(p["title"]) == _flat(P["title"])]
        best, bp = None, [False] * 4
        for p in cands:
            venue_ok = any(v in _flat(p["venue"] + " " + p["type"]) for v in P["venue_keys"]) and int(p["year"] or 0) == P["year"]
            if P["type"] == "preprint":
                venue_ok = venue_ok and "preprint" in _flat(p["type"] + p["venue"])
            parts = [p["group_id"] == P["group"], venue_ok, _authors_ok(p["authors"], P["authors"]),
                     (P["arxiv"] or "") == re.sub(r"(?i)^arxiv:", "", (p["arxiv"] or "").strip())]
            if sum(parts) > sum(bp):
                best, bp = p, parts
        found += bool(cands)
        db_score += (0.04 * bp[0] + 0.03 * bp[1] + 0.02 * bp[2] + 0.01 * bp[3]) if cands else 0
        detail[k] = {"records": len(cands), "group_venue_authors_arxiv": bp}
    p1 = exp["papers"]["P1"]
    p1_records = [p for p in live if _flat(p["title"]) in (_flat(p1["title"]), _flat(p1["old_title"]))]
    rejected = [p for p in live if _flat(exp["rejected"]["title"]) in _flat(p["title"])]
    seeded_gone = [p["id"] for p in q["pubs"] if p["id"] <= exp["seed_pub_max_id"] and p["deleted"]]
    db_hyg = found > 0 and len(p1_records) == 1 and not rejected and not seeded_gone
    checks.update({"labdesk": detail, "p1_records": len(p1_records), "rejected_listed": bool(rejected), "seeded_removed": seeded_gone})

    # website repo
    info = pc.guest_json(env, INSPECT % (REPO, exp["repo_base"], BIB, BIB), tag="REPO") or {}
    bib = parse_bib(info.get("work_bib", ""))
    head = parse_bib(info.get("head_bib", ""))
    bib_score = 0.0
    bdetail = {}
    for k, P in exp["papers"].items():
        if not P["bibkey"]:
            continue
        e = bib.get(P["bibkey"])
        if not e:
            bdetail[k] = "missing"
            continue
        venue = e.get("booktitle", "") + " " + e.get("journal", "")
        parts = [_flat(e.get("title")) == _flat(P["title"]), _authors_ok(_bib_author_lasts(e.get("author")), P["authors"]),
                 str(P["year"]) == e.get("year", "").strip() and any(v in _flat(venue) for v in P["venue_keys"]),
                 (not P["arxiv"]) or P["arxiv"] in (e.get("arxiv", "") + venue + e.get("eprint", ""))]
        if P["type"] == "conf":
            parts[2] = parts[2] and e["type"] == "inproceedings"
        bib_score += 0.0175 * sum(parts) * (0.0 if e.get("_dup") else 1.0)
        bdetail[k] = parts
    other_keys = {"P2": exp["papers"]["P2"]["title"], "R": exp["rejected"]["title"]}
    stray = [n for n, t in other_keys.items() if any(_flat(t) == _flat(e.get("title")) for e in bib.values())]
    kept = all(key in bib for key in exp["seeded_bib_keys"])
    dups = [key for key, e in bib.items() if e.get("_dup")]
    bib_hyg = bool(bib) and not stray and kept and not dups and len(bdetail) == 3 and "missing" not in bdetail.values()
    checks.update({"bib": bdetail, "bib_stray_entries": stray, "seeded_bib_keys_kept": kept, "bib_duplicate_keys": dups})

    commits = info.get("commits", [])
    only_bib = bool(commits) and all(set(c["files"]) <= {BIB} for c in commits)
    committed = bool(commits) and info.get("head_bib") == info.get("work_bib") and exp["papers"]["P3"]["bibkey"] in head
    checks.update({"commits": [(c["subject"], c["files"]) for c in commits][:5], "commits_only_bib": only_bib,
                   "bib_changes_committed": committed})

    # announcement draft
    boxes = xc.mailboxes(env) or {}
    mine = [m for m in xc.outgoing(boxes, exp["msg"].values()) if xc.addressed(m, exp["list"])]
    best_t, rej_ok = 0, False
    for m in mine:
        t = _flat(m["text"] + " " + m["subject"])
        n = sum(_flat(P["title"]) in t for P in exp["papers"].values())
        if n >= best_t:
            best_t, rej_ok = n, _flat(exp["rejected"]["title"]) not in t
    checks.update({"announcement_draft": bool(mine), "announced_titles": f"{best_t}/4", "announcement_without_rejected": rej_ok and bool(mine)})

    score = (db_score + 0.05 * db_hyg + bib_score + 0.04 * bib_hyg + 0.05 * only_bib + 0.05 * committed
             + 0.16 * best_t / 4 + 0.04 * (rej_ok and best_t > 0))
    rejected_anywhere = bool(rejected) or "R" in stray or any(_flat(exp["rejected"]["title"]) in _flat(m["text"] + m["subject"]) for m in mine)
    checks["rejected_paper_published"] = rejected_anywhere
    score = xc.capped(score, [(found == 0, 0.4), (not bib, 0.6), (rejected_anywhere, 0.6)])
    return pc.result(score, checks)
