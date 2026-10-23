"""A6 - Kestrel Lane Accountants: one client-files tree, restructured (A) while the morning post is filed into it (B).

A (pga6restructure): new filing convention from a scanned partner memo -> ~/Clients/{Active,Ceased}/<Surname>,
   <First> (<ID>)/<ID>_<Type>_<YYYY-MM-DD>.pdf (IDs, legal names and status only on the intake-form scans), README.txt
   rewritten, ~/Clients/index.csv.
B (pga6filing): 12 scans in ~/Scans/Inbox -> each into its client's folder, named per ~/Clients/README.txt (whichever
   convention it describes when read), a duplicate dropped, a non-client letter left, ~/Scans/filed_log.csv.
Shared live state: the user's one file tree. A renames/moves exactly the folders B files into, and rewrites the README
B takes its naming rule from. See spec_a6.md.
"""
from __future__ import annotations

import csv
import io
import os
import re

from evaluation_examples.task_class import pg_common as pc

CLIENTS = f"{pc.HOME}/Clients"
INBOX = f"{pc.HOME}/Scans/Inbox"
LOG = f"{pc.HOME}/Scans/filed_log.csv"


def setup(sc):
    pc.upload(sc, [("a6/a6.tar.gz", "/tmp/pga6.tar.gz")])
    pc.sh(sc, "mkdir -p ~/.cache; [ -f ~/.cache/.pga6_ready ] || { tar xzf /tmp/pga6.tar.gz -C ~ && "
              "touch ~/.cache/.pga6_ready; }; rm -f /tmp/pga6.tar.gz")
    sc.launch(f"[ -e /tmp/.pga6_nautilus ] || {{ touch /tmp/.pga6_nautilus; exec nautilus --new-window '{CLIENTS}'; }}",
              shell=True)
    sc.launch(f"[ -e /tmp/.pga6_nautilus2 ] || {{ touch /tmp/.pga6_nautilus2; sleep 4; exec nautilus --new-window "
              f"'{INBOX}'; }}", shell=True)


STATE = r"""python3 - <<'PY'
import hashlib, json, os
H = os.path.expanduser('~')
out = {'files': {}, 'dirs': [], 'text': {}}
for root in ('Clients', 'Scans'):
    for d, ds, fs in os.walk(os.path.join(H, root)):
        out['dirs'].append(os.path.relpath(d, H))
        for f in fs:
            p = os.path.join(d, f)
            try:
                out['files'][os.path.relpath(p, H)] = hashlib.md5(open(p, 'rb').read()).hexdigest()
            except OSError:
                pass
for rel in ('Clients/README.txt', 'Clients/index.csv', 'Scans/filed_log.csv'):
    try:
        out['text'][rel] = open(os.path.join(H, rel), 'rb').read().decode('utf-8', 'replace')[:20000]
    except OSError:
        pass
print('A6STATE' + json.dumps(out))
PY"""


def state(env) -> dict | None:
    return pc.guest_json(env, STATE, tag="A6STATE")


# ---------------------------------------------------------------- name rules
NEW_FILE = re.compile(r"^(KL-\d{4})_([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})\.pdf$", re.I)
OLD_FILE = re.compile(r"^(\d{4})(\d{2})(\d{2})[ _-]+(.+?)\.pdf$", re.I)
NEW_FOLDER = re.compile(r"^(Active|Ceased)/(.+), (.+) \((KL-\d{4})\)$")
OLD_FOLDER = re.compile(r"^[A-Z]+_[A-Za-z]+$")
KEYWORDS = {"Intake": r"intake", "Engagement": r"engagement", "P60": r"p\s*60", "BankStatement": r"bank\s*statement",
            "HMRCLetter": r"hmrc", "Payslip": r"pay\s*slip", "TaxReturn": r"tax\s*return|sa\s*100", "Receipts": r"receipt"}


def flat(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def new_name_ok(name: str, cid: str, typ: str, date: str) -> bool:
    m = NEW_FILE.match(name.strip())
    return bool(m) and m.group(1).upper() == cid and m.group(2).lower() == typ.lower() and m.group(3) == date


def old_name_ok(name: str, typ: str, date: str) -> bool:
    m = OLD_FILE.match(name.strip())
    return bool(m) and f"{m.group(1)}-{m.group(2)}-{m.group(3)}" == date and bool(re.search(KEYWORDS[typ], m.group(4), re.I))


def parse_csv(text: str) -> list[dict]:
    if not text:
        return []
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), dialect))
    if not rows:
        return []
    head = [flat(h) for h in rows[0]]
    return [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head)} for r in rows[1:] if any(x.strip() for x in r)]


def col(row: dict, *keys) -> str:
    for k in keys:
        for h, v in row.items():
            if h.startswith(k):
                return v
    return ""


def _index(st: dict):
    """md5 -> [Clients-relative paths]; the folder holding each client's intake form."""
    by_md5 = {}
    for p, m in st["files"].items():
        by_md5.setdefault(m, []).append(p)
    return by_md5


def capped(score, caps):
    for cond, cap in caps:
        if cond:
            score = min(score, cap)
    return score


# ---------------------------------------------------------------- A: restructure
def evaluate_restructure(env, dest: str) -> dict:
    exp = pc.expected("a6")
    st = state(env)
    if st is None:
        return pc.result(0.0, {"state": "unreadable"})
    checks = {}
    by_md5 = _index(st)
    dirs = {d[len("Clients/"):] for d in st["dirs"] if d.startswith("Clients/")}
    seeded = {f["md5"] for f in exp["files"]}
    # 1. client folders
    folders_ok = 0
    bad_folders = []
    for c in exp["clients"]:
        ok = c["folder"] in dirs
        folders_ok += ok
        if not ok:
            intake = next(f for f in exp["files"] if f["client"] == c["id"] and f["type"] == "Intake")
            bad_folders.append([c["folder"], [os.path.dirname(p) for p in by_md5.get(intake["md5"], [])]])
    done = folders_ok / len(exp["clients"])
    checks["folders_ok"] = f"{folders_ok}/{len(exp['clients'])}"
    checks["folder_problems"] = bad_folders[:6]
    # 2. nothing else: only Active/, Ceased/ (+ README, index) at top, only expected client folders below, no sub-dirs
    want = {"Active", "Ceased"} | {c["folder"] for c in exp["clients"]}
    stray = sorted(d for d in dirs if d not in want)
    top_files = sorted(p for p in st["files"] if p.startswith("Clients/") and p.count("/") == 1
                       and os.path.basename(p) not in ("README.txt", "index.csv"))
    loose = sorted(p for p in st["files"] if p.startswith("Clients/") and p.count("/") == 2)  # files directly in Active/Ceased
    clean = not stray and not top_files and not loose
    checks["stray_dirs_or_files"] = (stray + top_files + loose)[:10]
    # 3. seeded documents renamed
    named = 0
    bad_names = []
    for f in exp["files"]:
        c = next(x for x in exp["clients"] if x["id"] == f["client"])
        hit = f"Clients/{c['folder']}/{f['new_name']}"
        alt = [p for p in by_md5.get(f["md5"], []) if os.path.dirname(p) == f"Clients/{c['folder']}"
               and new_name_ok(os.path.basename(p), f["client"], f["type"], f["date"])]
        if st["files"].get(hit) == f["md5"] or alt:
            named += 1
        else:
            bad_names.append([f["new_name"], by_md5.get(f["md5"], [])[:2]])
    checks["files_named_ok"] = f"{named}/{len(exp['files'])}"
    checks["file_problems"] = bad_names[:8]
    # 4. every other document in a client folder follows the convention too (e.g. post filed in the meantime)
    other, other_ok = [], 0
    folder_id = {c["folder"]: c["id"] for c in exp["clients"]}
    for p, m in st["files"].items():
        if m in seeded or not p.startswith("Clients/"):
            continue
        rel = p[len("Clients/"):]
        if rel in ("README.txt", "index.csv"):
            continue
        fold = os.path.dirname(rel)
        cid = folder_id.get(fold)
        mm = NEW_FILE.match(os.path.basename(rel))
        ok = bool(cid and mm and mm.group(1).upper() == cid and mm.group(2).lower() in {t.lower() for t in exp["types"]})
        other.append([rel, ok])
        other_ok += ok
    others_clean = all(ok for _, ok in other)
    checks["other_documents"] = other[:12]
    # 5. no seeded document lost or duplicated
    counts = {m: len([p for p in by_md5.get(m, []) if p.startswith("Clients/")]) for m in seeded}
    lost = [f["old_name"] for f in exp["files"] if counts[f["md5"]] == 0]
    dup = [f["old_name"] for f in exp["files"] if counts[f["md5"]] > 1]
    checks["lost"], checks["duplicated"] = lost, dup
    intact = not lost and not dup
    # 6. README
    rd = st["text"].get("Clients/README.txt", "")
    low = rd.lower()
    readme_ok = ("active" in low and "ceased" in low and ("client id" in low or "kl-" in low or "clientid" in low)
                 and "yyyy-mm-dd" in low and "surname_firstname" not in low)
    checks["readme_updated"] = readme_ok
    # 7. index.csv
    rows = parse_csv(st["text"].get("Clients/index.csv", ""))
    idx_pts = 0.0
    idx_bad = []
    for c in exp["clients"]:
        r = next((x for x in rows if flat(col(x, "clientid", "id")) == flat(c["id"])), None)
        if not r:
            idx_bad.append([c["id"], "missing"])
            continue
        nm = flat(col(r, "name"))
        name_ok = nm in (flat(c["surname"] + c["first"]), flat(c["first"] + c["surname"]))
        st_ok = flat(col(r, "status")) == flat(c["status"])
        fo = col(r, "folder").replace("\\", "/").rstrip("/")
        fo_ok = fo.endswith(c["folder"])
        idx_pts += (name_ok + st_ok + fo_ok) / 3
        if not (name_ok and st_ok and fo_ok):
            idx_bad.append([c["id"], name_ok, st_ok, fo_ok])
    checks["index_rows_ok"] = f"{idx_pts:.2f}/{len(exp['clients'])}"
    checks["index_problems"] = idx_bad[:6]

    score = (0.25 * done + 0.10 * clean * done + 0.25 * named / len(exp["files"]) + 0.10 * others_clean * done
             + 0.10 * intact * done + 0.05 * readme_ok + 0.15 * idx_pts / len(exp["clients"]))
    score = capped(score, [(done < 0.5, 0.4), (bool(lost), 0.6), (not others_clean, 0.75)])
    return pc.result(score, checks)


# ---------------------------------------------------------------- B: filing
def _client_by_folder(exp: dict, folder: str):
    """A Clients-relative folder name (old or new style) -> client id."""
    folder = folder.strip("/")
    for c in exp["clients"]:
        if folder in (c["old"], c["folder"]) or folder.endswith("/" + c["folder"]) or folder.endswith("/" + c["old"]):
            return c["id"]
    return None


def evaluate_filing(env, dest: str) -> dict:
    exp = pc.expected("a6")
    st = state(env)
    if st is None:
        return pc.result(0.0, {"state": "unreadable"})
    checks = {}
    by_md5 = _index(st)
    intake_dir = {}
    for f in exp["files"]:
        if f["type"] == "Intake":
            locs = [os.path.dirname(p) for p in by_md5.get(f["md5"], []) if p.startswith("Clients/")]
            intake_dir[f["client"]] = locs[0] if len(locs) == 1 else None
    docs = [s for s in exp["scans"] if s["client"] and not s["dup_of"]]
    twins = {s["dup_of"]: s["md5"] for s in exp["scans"] if s["dup_of"]}
    placed = named = 0.0
    detail, misfiled = [], []
    for s in docs:
        md5s = {s["md5"]} | ({twins[s["scan"]]} if s["scan"] in twins else set())
        locs = [p for m in md5s for p in by_md5.get(m, []) if p.startswith("Clients/")]
        canon = intake_dir.get(s["client"])
        good = len(locs) == 1 and canon and os.path.dirname(locs[0]) == canon
        name_ok = False
        if good:
            base = os.path.basename(locs[0])
            new_style = bool(NEW_FOLDER.match(canon[len("Clients/"):]))
            name_ok = (new_name_ok(base, s["client"], s["type"], s["date"]) if new_style
                       else old_name_ok(base, s["type"], s["date"]))
        other_canon = {v for k, v in intake_dir.items() if k != s["client"] and v}
        if any(os.path.dirname(p) in other_canon for p in locs):
            misfiled.append(s["scan"])
        placed += bool(good)
        named += name_ok
        if not (good and name_ok):
            detail.append([s["scan"], s["client"], locs[:3], canon])
    checks["placed_ok"] = f"{placed:g}/{len(docs)}"
    checks["named_ok"] = f"{named:g}/{len(docs)}"
    checks["problems"] = detail[:8]
    # duplicate scan: exactly one copy of that document anywhere
    dupdoc = next(s for s in exp["scans"] if s["dup_of"])
    orig = next(s for s in exp["scans"] if s["scan"] == dupdoc["dup_of"])
    n_dup = sum(len(by_md5.get(m, [])) for m in (orig["md5"], dupdoc["md5"]))
    checks["duplicate_copies"] = n_dup
    dup_ok = n_dup == 1
    # the letter for a non-client stays in the Inbox and is not filed
    nc = next(s for s in exp["scans"] if s["client"] is None)
    nc_locs = by_md5.get(nc["md5"], [])
    nc_ok = nc_locs == [f"Scans/Inbox/{nc['scan']}"] or (len(nc_locs) == 1 and nc_locs[0].startswith("Scans/Inbox/"))
    checks["nonclient_left_in_inbox"] = nc_ok
    left = [p for p in st["files"] if p.startswith("Scans/Inbox/") and st["files"][p] != nc["md5"]]
    checks["inbox_left"] = left
    inbox_ok = not left
    # log
    rows = parse_csv(st["text"].get("Scans/filed_log.csv", ""))
    log_pts = 0.0
    log_bad = []
    for s in exp["scans"]:
        r = next((x for x in rows if flat(os.path.basename(col(x, "scan", "file", "original"))) == flat(s["scan"])), None)
        if not r:
            log_bad.append([s["scan"], "missing"])
            continue
        path = col(r, "path", "filed", "new", "location", "where").replace("\\", "/").rstrip()
        if s["client"] is None:
            ok = not re.search(r"(?i)clients/", path)
        elif s["dup_of"] or s["scan"] in twins:  # either copy of the twice-scanned page: marked duplicate or filed
            ok = bool(re.search(r"(?i)dup|delet|remov|same as|copy|twice", " ".join(r.values()))) or \
                _client_by_folder(exp, os.path.dirname(path).split("Clients/", 1)[-1]) == s["client"]
        else:
            fold = os.path.dirname(path).split("Clients/", 1)[-1]
            base = os.path.basename(path)
            ok = _client_by_folder(exp, fold) == s["client"] and (
                new_name_ok(base, s["client"], s["type"], s["date"]) or old_name_ok(base, s["type"], s["date"]))
        log_pts += ok
        if not ok:
            log_bad.append([s["scan"], path[:90]])
    checks["log_rows_ok"] = f"{log_pts:g}/{len(exp['scans'])}"
    checks["log_problems"] = log_bad[:6]

    score = (0.30 * placed / len(docs) + 0.25 * named / len(docs) + 0.10 * dup_ok + 0.10 * nc_ok * (placed > 0)
             + 0.10 * inbox_ok * (placed > 0) + 0.15 * log_pts / len(exp["scans"]))
    checks["filed_in_another_clients_folder"] = misfiled
    score = capped(score, [(placed < len(docs) / 2, 0.4), (bool(misfiled), 0.7)])
    return pc.result(score, checks)
