"""Shared evaluator helpers for the F2 Thunderbird pairs m1..m4 (deployed next to pg_common.py in task_class/).

Readers (one Guest round trip each):
  profile_state(env) -> {folders, filters{account: text}, tags{key: name}, prefs{...}, virtual}
  calendar_events(env, tz) -> [event dicts]   (calendar-data/local.sqlite, copied with its -wal first)
  sqlite_dump(env, ["abook.sqlite"]) + cards_from_dump()/lists_from_dump() for the address book
  raw_messages(env, ("drafts", "templates")) -> full MIME messages; draft_replies() -> replies with the quoted
  original stripped (own_text), html_parts() -> inline images / links of an HTML draft
Mail: mail_folders() from pg_common, plus where()/replies() helpers. Thunderbird keeps moved-away copies in the old
mbox with the "deleted" status bit until the folder is compacted; mail_folders() already skips those.
Storage formats were checked against the comm-esr115 sources (nsMsgFilterList, nsMsgTagService, nsMsgBrkMBoxStore,
CalStorageItemModel, AddrBookDirectory, MessageSend, nsMsgAccountManager::SaveVirtualFolders).
Filters: parse msgFilterRules.dat and *simulate* the rules on probe messages, so any correct way of writing a rule
(e.g. "from contains riversidelibrary.org" vs "from ends with @riversidelibrary.org") passes.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import zipfile
from email.utils import getaddresses
from urllib.parse import unquote

from evaluation_examples.task_class.pg_common import guest_json

# ---------------------------------------------------------------- Guest-side readers
PROFILE_STATE = r"""python3 - <<'PY'
import glob, json, os, re
out = {'folders': [], 'filters': {}, 'tags': {}, 'prefs': {}, 'virtual': ''}
for prof in glob.glob(os.path.expanduser('~/.thunderbird/*.default-release')):
    mail = os.path.join(prof, 'Mail')
    for d, dirs, fs in os.walk(mail):
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, mail).replace('.sbd/', '/')
            if f == 'msgFilterRules.dat':
                out['filters'][os.path.relpath(d, mail)] = open(p, encoding='utf-8', errors='replace').read()
            elif '.' not in f:
                out['folders'].append(rel)
        for x in dirs:
            if x.endswith('.sbd'):
                rel = os.path.relpath(os.path.join(d, x[:-4]), mail).replace('.sbd/', '/')
                if rel not in out['folders']:
                    out['folders'].append(rel)
    try:
        for ln in open(os.path.join(prof, 'prefs.js'), encoding='utf-8', errors='replace'):
            m = re.match(r'user_pref\("([^"]+)",\s*(.*)\);\s*$', ln)
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            try:
                v = json.loads(v)
            except Exception:
                pass
            if k.startswith('mailnews.tags.') or k.startswith('calendar.') or k.startswith('mail.identity.') \
                    or k.startswith('mail.server.') or k.startswith('ldap_2.') or k.startswith('mail.spam'):
                out['prefs'][k] = v
    except OSError:
        pass
    try:
        out['virtual'] = open(os.path.join(prof, 'virtualFolders.dat'), encoding='utf-8', errors='replace').read()
    except OSError:
        pass
for k, v in out['prefs'].items():
    m = re.match(r'mailnews\.tags\.(.+)\.tag$', k)
    if m:
        out['tags'][m.group(1)] = v
print('PSTATE' + json.dumps(out))
PY"""

# Thunderbird may hold the databases open (WAL journal): copy every file of the database before reading it.
SQLITE_DUMP = r"""python3 - <<'PY'
import glob, json, os, shutil, sqlite3, tempfile
out = {}
for prof in glob.glob(os.path.expanduser('~/.thunderbird/*.default-release')):
    for db in %s:
        for path in glob.glob(os.path.join(prof, db)):
            tmp = tempfile.mkdtemp()
            for f in glob.glob(path + '*'):
                shutil.copy(f, os.path.join(tmp, os.path.basename(f)))
            try:
                con = sqlite3.connect(os.path.join(tmp, os.path.basename(path)))
                res = {}
                for t, in con.execute("select name from sqlite_master where type='table'"):
                    rows = con.execute('select * from "%%s"' %% t)
                    cols = [c[0] for c in rows.description]
                    res[t] = [dict(zip(cols, [v.decode('utf-8', 'replace') if isinstance(v, bytes) else v for v in r]))
                              for r in rows]
                out[os.path.relpath(path, prof)] = res
            except Exception as e:
                out[os.path.relpath(path, prof)] = {'error': str(e)}
            shutil.rmtree(tmp, ignore_errors=True)
print('SQLDUMP' + json.dumps(out, default=str))
PY"""


RAW_MESSAGES = r"""python3 - <<'PY'
import base64, glob, json, os, re
out = {}
for prof in glob.glob(os.path.expanduser('~/.thunderbird/*/Mail')):
    for d, _, fs in os.walk(prof):
        for f in fs:
            p = os.path.join(d, f)
            if '.' in f or f.lower() not in %s:
                continue
            data = open(p, 'rb').read()
            folder = os.path.relpath(p, prof).replace('.sbd/', '/')
            starts = [m.start() for m in re.finditer(rb'(?m)^From .*\r?\n', data)]
            for s, e in zip(starts, starts[1:] + [len(data)]):
                chunk = data[s:e].split(b'\n', 1)[1]
                m = re.search(rb'(?m)^X-Mozilla-Status: ([0-9a-fA-F]{4})', chunk[:2000])
                if m and int(m.group(1), 16) & 0x0008:
                    continue
                out.setdefault(folder, []).append(base64.b64encode(chunk).decode())
print('RAWMSG' + json.dumps(out))
PY"""


def raw_messages(env, leaves=("drafts", "templates")) -> dict:
    """{folder: [email.message.EmailMessage]} for the live messages of the mbox files with these leaf names."""
    import base64
    import email
    import email.policy
    got = guest_json(env, RAW_MESSAGES % repr([x.lower() for x in leaves]), tag="RAWMSG") or {}
    return {f: [email.message_from_bytes(base64.b64decode(b), policy=email.policy.default) for b in msgs]
            for f, msgs in got.items()}


def html_parts(m) -> dict:
    """{'html': str, 'images': [{cid, filename, md5, referenced}], 'hrefs': [...], 'text': plain text}."""
    import hashlib
    html, images, text = "", [], ""
    for part in m.walk():
        ctype = part.get_content_type()
        if part.is_multipart():
            continue
        if ctype == "text/html" and not html:
            html = part.get_content()
        elif ctype == "text/plain" and not text and part.get_content_disposition() != "attachment":
            text = part.get_content()
        elif part.get_content_maintype() == "image":
            data = part.get_payload(decode=True) or b""
            images.append({"cid": (part.get("Content-ID") or "").strip("<> "), "filename": part.get_filename() or "",
                           "md5": hashlib.md5(data).hexdigest(), "disposition": part.get_content_disposition() or ""})
    srcs = re.findall(r"""<img[^>]+src\s*=\s*["']([^"']+)["']""", html, re.I)
    for img in images:
        img["referenced"] = bool(img["cid"]) and any(s.lower() == "cid:" + img["cid"].lower() for s in srcs)
    import base64
    import hashlib as _h
    for s in srcs:  # data: URIs stay inline in the HTML
        mm = re.match(r"data:image/[\w.+-]+;base64,(.*)", s, re.S)
        if mm:
            try:
                data = base64.b64decode(mm.group(1))
                images.append({"cid": "", "filename": "", "md5": _h.md5(data).hexdigest(), "disposition": "inline",
                               "referenced": True})
            except ValueError:
                pass
    hrefs = re.findall(r"""<a[^>]+href\s*=\s*["']([^"']+)["']""", html, re.I)
    plain = re.sub(r"<[^>]+>", " ", html) if html else text
    return {"html": html, "images": images, "hrefs": hrefs, "text": re.sub(r"&nbsp;|\s+", " ", plain), "srcs": srcs}


def _drop_cited(html: str) -> str:
    """Remove Thunderbird's quoted original (<blockquote type="cite">, nested blockquotes included) and its
    "On <date>, X wrote:" prefix from an HTML reply."""
    html = re.sub(r'(?is)<div[^>]*class="?moz-cite-prefix"?[^>]*>.*?</div>', " ", html)
    out, i = [], 0
    for m in re.finditer(r'(?is)<blockquote[^>]*type\s*=\s*"?cite"?[^>]*>', html):
        if m.start() < i:
            continue
        out.append(html[i:m.start()])
        depth, j = 1, m.end()
        for t in re.finditer(r"(?is)<(/?)blockquote\b[^>]*>", html[j:]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                j += t.end()
                break
        else:
            j = len(html)
        i = j
    out.append(html[i:])
    return "".join(out)


def own_text(m) -> str:
    """What the user wrote in a draft reply, without the quoted original (HTML or plain-text composer)."""
    from html import unescape
    html = plain = ""
    for part in m.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() == "text/html" and not html:
            html = part.get_content()
        elif part.get_content_type() == "text/plain" and not plain:
            plain = part.get_content()
    if html:
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", _drop_cited(html))))
    keep = [ln for ln in plain.splitlines() if not ln.lstrip().startswith(">")
            and not re.match(r"^\s*On .{4,120} wrote:\s*$", ln)]
    return re.sub(r"\s+", " ", "\n".join(keep))


def draft_replies(env, irt_ids, to: str | None = None, folder="drafts", raw: dict | None = None) -> list:
    """Drafts replying to one of the messages (In-Reply-To/References), optionally addressed to `to`:
    [{subject, to, cc, bcc, text (own text only)}]."""
    ids = [irt_ids] if isinstance(irt_ids, str) else list(irt_ids)
    out = []
    raw = raw if raw is not None else raw_messages(env, (folder,))
    for f, msgs in raw.items():
        if f.rsplit("/", 1)[-1].lower() != folder:
            continue
        for m in msgs:
            ref = f"{m['In-Reply-To'] or ''} {m['References'] or ''}"
            if not any(i in ref for i in ids):
                continue
            if to and to.lower() not in addrs(str(m["To"] or "")) | addrs(str(m["Cc"] or "")):
                continue
            out.append({"subject": str(m["Subject"] or ""), "to": str(m["To"] or ""), "text": own_text(m)})
    return out


def profile_state(env) -> dict:
    return guest_json(env, PROFILE_STATE, tag="PSTATE") or {}


def sqlite_dump(env, patterns) -> dict:
    return guest_json(env, SQLITE_DUMP % json.dumps(list(patterns)), tag="SQLDUMP") or {}


# ---------------------------------------------------------------- mail helpers
def account_path(folder: str) -> str:
    """'pop.x.com/Riverside Library/Client' -> 'riverside library/client' (path inside the account, lower case)."""
    return folder.split("/", 1)[1].lower() if "/" in folder else ""


def where(boxes: dict) -> dict:
    """{message-id: [(folder, message), ...]} over all live copies."""
    out = {}
    for folder, msgs in (boxes or {}).items():
        for m in msgs:
            out.setdefault(m["id"], []).append((folder, m))
    return out


def leaf(folder: str) -> str:
    return folder.rsplit("/", 1)[-1].lower()


def in_folder(boxes: dict, name: str) -> list:
    return [m for f, msgs in (boxes or {}).items() if leaf(f) == name for m in msgs]


def replies(boxes: dict, irt_ids, folder="drafts") -> list:
    ids = [irt_ids] if isinstance(irt_ids, str) else list(irt_ids)
    return [m for m in in_folder(boxes, folder) if any(i in m["irt"] for i in ids)]


def addrs(field: str) -> set:
    return {a.lower() for _, a in getaddresses([field or ""]) if a}


def tag_names(keys, tags: dict) -> set:
    """X-Mozilla-Keys keywords -> lower-case tag names (unknown keys are kept as they are)."""
    return {str(tags.get(k, k)).strip().lower() for k in keys}


# ---------------------------------------------------------------- msgFilterRules.dat
def _unesc(v: str) -> str:
    """nsMsgFilterList writes attribute values with '"' escaped as '\\"' (backslashes themselves are not escaped)."""
    return v.replace('\\"', '"')


def parse_filters(text: str) -> list:
    """[{name, enabled, type, actions:[(action, value)], terms:[(bool_op, attrib, op, value)], match_all}]"""
    filters, cur = [], None
    for ln in (text or "").splitlines():
        m = re.match(r'\s*([A-Za-z]+)="(.*)"\s*$', ln)
        if not m:
            continue
        k, v = m.group(1), _unesc(m.group(2))
        if k == "name":
            cur = {"name": v, "enabled": True, "type": 17, "actions": [], "terms": [], "raw_condition": ""}
            filters.append(cur)
        elif cur is None:
            continue
        elif k == "enabled":
            cur["enabled"] = v == "yes"
        elif k == "type":
            cur["type"] = int(v) if v.isdigit() else 0
        elif k == "action":
            cur["actions"].append([v, None])
        elif k == "actionValue" and cur["actions"]:
            cur["actions"][-1][1] = v
        elif k == "condition":
            cur["raw_condition"] = v
            cur["terms"] = parse_condition(v)
    return filters


def parse_condition(cond: str) -> list:
    cond = cond.strip()
    if cond.upper() == "ALL":
        return [("AND", "all", "all", "")]
    terms, i = [], 0
    while i < len(cond):
        m = re.compile(r'\s*(AND|OR)\s*\(').match(cond, i)
        if not m:
            break
        i = m.end()
        parts, buf, quoted = [], "", False
        while i < len(cond):
            c = cond[i]
            if quoted:
                if c == "\\" and i + 1 < len(cond):
                    buf += cond[i + 1]
                    i += 2
                    continue
                if c == '"':
                    quoted = False
                else:
                    buf += c
            elif c == '"':
                quoted = True
            elif c == "\\" and i + 1 < len(cond):
                buf += cond[i + 1]
                i += 2
                continue
            elif c == "," and len(parts) < 2:
                parts.append(buf)
                buf = ""
            elif c == ")":
                i += 1
                break
            else:
                buf += c
            i += 1
        parts.append(buf)
        while len(parts) < 3:
            parts.append("")
        terms.append((m.group(1).upper(), parts[0].strip().lower(), parts[1].strip().lower(), parts[2]))
    return terms


def _match_str(op: str, hay: str, needle: str) -> bool | None:
    hay, needle = (hay or "").lower(), (needle or "").lower()
    if op == "contains":
        return needle in hay
    if op == "doesn't contain":
        return needle not in hay
    if op == "is":
        return hay == needle
    if op == "isn't":
        return hay != needle
    if op == "begins with":
        return hay.startswith(needle)
    if op == "ends with":
        return hay.endswith(needle)
    if op == "matches":
        try:
            return re.search(needle, hay) is not None
        except re.error:
            return False
    return None


def _match_addr(op: str, header: str, needle: str) -> bool:
    """Thunderbird matches address fields per mailbox against the display name and the address."""
    pairs = getaddresses([header or ""]) or [("", header or "")]
    neg = op in ("doesn't contain", "isn't")
    pos = {"doesn't contain": "contains", "isn't": "is"}.get(op, op)
    hits = []
    for name, addr in pairs:
        cands = [name, addr, f"{name} <{addr}>".strip()]
        hits.append(any(_match_str(pos, c, needle) for c in cands))
    return not any(hits) if neg else any(hits)


def term_matches(term, mail: dict) -> bool:
    _, attrib, op, value = term
    if attrib == "all":
        return True
    if attrib == "subject":
        return bool(_match_str(op, mail.get("subject", ""), value))
    if attrib in ("from", "sender"):
        return _match_addr(op, mail.get("from", ""), value)
    if attrib == "to":
        return _match_addr(op, mail.get("to", ""), value)
    if attrib == "cc":
        return _match_addr(op, mail.get("cc", ""), value)
    if attrib in ("to or cc", "all addresses"):
        hdr = ", ".join(x for x in (mail.get("to"), mail.get("cc"), mail.get("from") if attrib == "all addresses" else "")
                        if x)
        return _match_addr(op, hdr, value)
    if attrib == "body":
        return bool(_match_str(op, mail.get("body", ""), value))
    if attrib.startswith('"') or attrib not in ("date", "priority", "status", "age in days", "tag", "size"):
        hdr = attrib.strip('"').lower()  # custom header
        return bool(_match_str(op, mail.get("headers", {}).get(hdr, ""), value))
    return False


def filter_matches(f: dict, mail: dict) -> bool:
    terms = f["terms"]
    if not terms:
        return False
    if any(t[0] == "OR" for t in terms[1:]):
        return any(term_matches(t, mail) for t in terms)
    return all(term_matches(t, mail) for t in terms)


def folder_from_uri(uri: str) -> str:
    """mailbox://user@host/Riverside%20Library/Client -> 'riverside library/client' (inside the account)."""
    m = re.match(r"^[a-z\-]+://[^/]+/?(.*)$", uri or "")
    return unquote(m.group(1)).lower() if m else ""


def simulate(filters: list, mail: dict, tags: dict, new_mail=True) -> dict:
    """Run the enabled filters on one message the way Thunderbird does (in list order; a filter that moves or deletes
    the message ends processing, as does 'Stop execution'). Returns {folder, tags, flagged, copies}."""
    st = {"folder": "inbox", "tags": set(), "flagged": False, "read": False, "copies": []}
    for f in filters:
        if not f["enabled"]:
            continue
        if new_mail and not (f["type"] & (1 | 32)):
            continue
        if not new_mail and not (f["type"] & 16):
            continue
        if not filter_matches(f, mail):
            continue
        stop = False
        for action, value in f["actions"]:
            a = action.lower()
            if a == "addtag":
                st["tags"].add(str(tags.get(value, value)).strip().lower())
            elif a == "mark flagged":
                st["flagged"] = True
            elif a == "mark read":
                st["read"] = True
            elif a == "copy to folder":
                st["copies"].append(folder_from_uri(value))
            elif a == "move to folder":
                st["folder"] = folder_from_uri(value)
                stop = True
            elif a == "delete":
                st["folder"] = "trash"
                stop = True
            elif a == "stop execution":
                stop = True
        if stop:
            break
    return st


def filters_for(state: dict, host: str) -> list:
    """Filters of the POP account (falls back to Local Folders' list if the agent put them there)."""
    texts = state.get("filters", {})
    own = parse_filters(texts.get(host, ""))
    return own if own else parse_filters(texts.get("Local Folders", ""))


# ---------------------------------------------------------------- vCard / address book
def parse_vcard(text: str) -> dict:
    text = re.sub(r"\r?\n[ \t]", "", text or "")
    out = {"emails": [], "tels": [], "fn": "", "n": "", "org": "", "title": "", "note": ""}
    for ln in text.splitlines():
        if ":" not in ln:
            continue
        head, val = ln.split(":", 1)
        name = head.split(";")[0].upper()
        if "." in name:  # item1.EMAIL
            name = name.split(".", 1)[1]
        val = val.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n")
        if name == "EMAIL":
            out["emails"].append((val.strip().lower(), "PREF=1" in head.upper()))
        elif name == "TEL":
            out["tels"].append(val.strip())
        elif name == "FN":
            out["fn"] = val.strip()
        elif name == "N":
            out["n"] = val.strip()
        elif name == "ORG":
            out["org"] = val.split(";")[0].strip()
        elif name == "TITLE":
            out["title"] = val.strip()
        elif name == "NOTE":
            out["note"] = val
    return out


def cards_from_dump(db: dict) -> dict:
    """abook.sqlite dump -> {uid: {display, first, last, emails:[primary first], org, title, tels, raw}}"""
    props = {}
    for r in db.get("properties", []):
        props.setdefault(r["card"], {})[r["name"]] = r["value"] or ""
    cards = {}
    for uid, p in props.items():
        v = parse_vcard(p.get("_vCard", "")) if p.get("_vCard") else None
        # Thunderbird 115 derives PrimaryEmail/SecondEmail from the vCard (sorted by PREF) on every save; cards
        # that were never saved by 115 may only have these legacy rows
        emails = [e for e in ((p.get("PrimaryEmail") or "").strip().lower(), (p.get("SecondEmail") or "").strip().lower())
                  if e]
        if v:
            ranked = sorted(v["emails"], key=lambda x: not x[1])
            emails += [e for e, _ in ranked if e not in emails]
        n = (v["n"].split(";") if v and v["n"] else [])
        cards[uid] = {
            "display": (v["fn"] if v and v["fn"] else p.get("DisplayName", "")).strip(),
            "first": (n[1] if len(n) > 1 else p.get("FirstName", "")).strip(),
            "last": (n[0] if n else p.get("LastName", "")).strip(),
            "emails": emails, "org": (v["org"] if v and v["org"] else p.get("Company", "")).strip(),
            "title": (v["title"] if v and v["title"] else p.get("JobTitle", "")).strip(),
            "tels": (v["tels"] if v else []) + [p[k] for k in ("WorkPhone", "CellularNumber", "HomePhone") if p.get(k)],
        }
    return cards


def lists_from_dump(db: dict, cards: dict) -> list:
    members = {}
    for r in db.get("list_cards", []):
        members.setdefault(r["list"], []).append(r["card"])
    return [{"uid": r["uid"], "name": r["name"] or "", "nick": r.get("nickName") or "",
             "description": r.get("description") or "",
             "members": [cards[c]["emails"][0] for c in members.get(r["uid"], []) if c in cards and cards[c]["emails"]]}
            for r in db.get("lists", [])]


# ---------------------------------------------------------------- calendar
CAL_FLAG_ALLDAY = 8


def _prtime(us, tz, local_tz):
    from zoneinfo import ZoneInfo
    if us is None:
        return None
    t = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(microseconds=int(us))
    if tz == "floating":
        return t.replace(tzinfo=None)  # floating times are stored as if they were UTC
    return t.astimezone(ZoneInfo(local_tz))


def calendar_events(env, local_tz: str) -> list | None:
    """Events of every storage calendar in local.sqlite as dicts with local wall-clock start/end."""
    dump = sqlite_dump(env, ["calendar-data/local.sqlite"]).get("calendar-data/local.sqlite")
    if not dump or "error" in dump:
        return None
    return events_from_dump(dump, local_tz)


def events_from_dump(dump: dict, local_tz: str) -> list:
    props, atts = {}, {}
    for r in dump.get("cal_properties", []):
        if r.get("recurrence_id") is None:
            props.setdefault(r["item_id"], {})[r["key"]] = r["value"]
    for r in dump.get("cal_attendees", []):
        if r.get("recurrence_id") is None:
            atts.setdefault(r["item_id"], []).append(r["icalString"] or "")
    out = []
    for e in dump.get("cal_events", []):
        if e.get("recurrence_id") is not None:
            continue
        allday = bool((e.get("flags") or 0) & CAL_FLAG_ALLDAY)
        start = _prtime(e["event_start"], e.get("event_start_tz"), local_tz)
        end = _prtime(e["event_end"], e.get("event_end_tz"), local_tz)
        if allday:
            start = _prtime(e["event_start"], "floating", local_tz).date() if e["event_start"] is not None else None
            end = _prtime(e["event_end"], "floating", local_tz).date() if e["event_end"] is not None else None
        p = props.get(e["id"], {})
        attendees, organizer = [], ""
        for s in atts.get(e["id"], []):
            m = re.search(r"mailto:([^\s;:]+)", s, re.I)
            addr = m.group(1).lower() if m else ""
            if s.upper().startswith("ORGANIZER"):
                organizer = addr
            elif addr:
                attendees.append(addr)
        out.append({"id": e["id"], "cal": e["cal_id"], "title": e.get("title") or "", "start": start, "end": end,
                    "allday": allday, "tz": e.get("event_start_tz"), "location": str(p.get("LOCATION") or ""),
                    "description": str(p.get("DESCRIPTION") or ""), "categories": str(p.get("CATEGORIES") or ""),
                    "attendees": attendees, "organizer": organizer, "status": e.get("ical_status") or ""})
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ---------------------------------------------------------------- office files / numbers / dates
def xlsx_rows(path: str) -> list:
    """All rows of all sheets as lists of cell values (strings/numbers/dates); [] if unreadable."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        rows = []
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                if any(c not in (None, "") for c in r):
                    rows.append(list(r))
        return rows
    except Exception:
        return []


def csv_rows(path: str) -> list:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return [r for r in csv.reader(f)]
        except (UnicodeError, csv.Error):
            continue
        except OSError:
            return []
    return []


def doc_text(path: str) -> str:
    """Plain text of a .docx / .odt / .txt / .md / .pdf document ('' if unreadable)."""
    try:
        low = path.lower()
        if low.endswith(".docx"):
            import docx
            d = docx.Document(path)
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            return "\n".join(parts)
        if low.endswith(".odt"):
            xml = zipfile.ZipFile(path).read("content.xml").decode("utf-8", "replace")
            xml = re.sub(r"<text:tab/>|</text:p>|</text:h>|</table:table-cell>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml)
        if low.endswith(".pdf"):
            import fitz
            return "\n".join(p.get_text() for p in fitz.open(path))
        return open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def to_number(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("$", "").replace("USD", "").replace("EUR", "").replace("€", "").strip()
    m = re.fullmatch(r"-?\d+(\.\d+)?", s)
    return float(s) if m else None


MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                          "dec"])}


def to_date(v, default_year=2026):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and 40000 < v < 60000:  # spreadsheet serial
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    s = str(v or "").strip().lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:  # US style m/d/y
        y = int(m.group(3))
        return _safe_date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\.?\s+([a-z]{3})[a-z]*\.?,?\s*(\d{4})?", s)
    if m and m.group(2) in MONTHS:
        return _safe_date(int(m.group(3) or default_year), MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", s)
    if m and m.group(1) in MONTHS:
        return _safe_date(int(m.group(3) or default_year), MONTHS[m.group(1)], int(m.group(2)))
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:  # European d.m.Y
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def _safe_date(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def has_amount(text: str, amount: float, tol=0.011) -> bool:
    """Does the text mention the amount (with or without thousands separators / currency signs)?"""
    for tok in re.findall(r"\d[\d,]*\.?\d*", text or ""):
        try:
            if abs(float(tok.replace(",", "").rstrip(".")) - amount) <= tol:
                return True
        except ValueError:
            pass
    return False


WORDNUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}


def number_near(text: str, keyword: str, window=40):
    """The number written closest to a keyword (digits or one..twelve), or None."""
    low = (text or "").lower()
    best = None
    for k in re.finditer(re.escape(keyword.lower()), low):
        for n in re.finditer(r"\b(\d{1,3}|" + "|".join(WORDNUM) + r")\b", low):
            gap = n.start() - k.end() if n.start() >= k.end() else k.start() - n.end()
            if 0 <= gap <= window and (best is None or gap < best[0]):
                val = int(n.group(1)) if n.group(1).isdigit() else WORDNUM[n.group(1)]
                best = (gap, val)
    return best[1] if best else None
