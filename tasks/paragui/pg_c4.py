"""C4 - one Thunderbird: getting the inbox to zero vs dealing with the team-offsite mails (save attachments, draft a reply)."""
from __future__ import annotations

import json
import re

from evaluation_examples.task_class.pg_common import HOME, expected, guest, result, sh, tree, upload

OFFSITE = "~/Documents/Offsite"

# Every mbox file under the profile's Mail/ tree: which live (not deleted) messages it holds, keyed by Message-ID.
INSPECT = r"""python3 - <<'PY'
import email, email.policy, glob, json, os, re
out = {}
for prof in glob.glob(os.path.expanduser('~/.thunderbird/*/Mail')):
    for d, _, fs in os.walk(prof):
        for f in fs:
            p = os.path.join(d, f)
            if '.' in f or os.path.getsize(p) == 0:
                continue
            data = open(p, 'rb').read()
            if not data.startswith(b'From '):
                continue
            folder = os.path.relpath(p, prof).replace('.sbd/', '/')
            for chunk in re.split(rb'(?m)^From .*\r?\n', data)[1:]:
                m = email.message_from_bytes(chunk, policy=email.policy.default)
                status = int((m.get('X-Mozilla-Status') or '0').strip() or '0', 16)
                if status & 0x0008:
                    continue
                body = m.get_body(('plain', 'html'))
                text = body.get_content() if body is not None else ''
                out.setdefault(folder, []).append({
                    'id': (m.get('Message-ID') or '').strip(), 'subject': str(m.get('Subject') or ''),
                    'to': str(m.get('To') or ''), 'irt': str(m.get('In-Reply-To') or '') + ' ' + str(m.get('References') or ''),
                    'text': re.sub(r'<[^>]+>', ' ', text)[:3000]})
print('MBOX' + json.dumps(out))
PY"""


def setup(sc):
    upload(sc, [("c4/thunderbird-profile.tar.gz", f"{HOME}/thunderbird-profile.tar.gz")])
    # in a dual run the second setup must not reset the profile or start a second Thunderbird window
    sh(sc, "mkdir -p ~/Documents; [ -f ~/.thunderbird/.pgc4 ] || { rm -rf ~/.thunderbird && "
           "tar xzf ~/thunderbird-profile.tar.gz -C ~ && touch ~/.thunderbird/.pgc4; }; rm -f ~/thunderbird-profile.tar.gz")
    sc.launch("pgrep -x thunderbird >/dev/null || exec /usr/bin/thunderbird", shell=True)


def _folders(env) -> dict | None:
    out = guest(env, INSPECT)
    m = re.search(r"MBOX(\{.*\})", out, re.S)
    return json.loads(m.group(1)) if m else None


def _leaf(folder: str) -> str:
    return folder.rsplit("/", 1)[-1].lower()


def evaluate_inbox(env, dest: str) -> dict:
    boxes, exp = _folders(env), expected("c4")
    if boxes is None:
        return result(0.0, {"mail": "unreadable"})
    where = {}
    for folder, msgs in boxes.items():
        for m in msgs:
            where.setdefault(m["id"], set()).add(_leaf(folder))
    inbox_left = sum(len(msgs) for f, msgs in boxes.items() if _leaf(f) == "inbox")
    ok, wrong = 0, []
    for mail in exp["mails"]:
        places = where.get(mail["id"], set())
        if mail["folder"] == "Delete":
            good = not (places - {"trash", "junk", "deleted"})
        else:
            good = mail["folder"].lower() in places and "inbox" not in places
        ok += good
        if not good:
            wrong.append(f"{mail['subject'][:40]} -> {sorted(places)} (want {mail['folder']})")
    n = len(exp["mails"])
    checks = {"filed_ok": f"{ok}/{n}", "inbox_left": inbox_left, "wrong": wrong[:10], "folders": sorted(boxes)}
    return result(0.85 * ok / n + 0.15 * (inbox_left == 0), checks)


def evaluate_offsite(env, dest: str) -> dict:
    exp = expected("c4")
    saved = set(tree(env, [OFFSITE]).values())
    agenda = exp["attachments"]["Offsite_Agenda_Nov2026.pdf"] in saved
    booking = exp["attachments"]["Lakeview_Lodge_Booking_JLee.pdf"] in saved
    boxes = _folders(env) or {}
    drafts = [m for f, msgs in boxes.items() if _leaf(f) == "drafts" for m in msgs]
    reply = next((m for m in drafts if exp["reply_to"] in m["irt"] and exp["dana"] in m["to"].lower()), None)
    diet = bool(reply) and "vegetarian" in reply["text"].lower()
    sent = [m["subject"] for f, msgs in boxes.items() if _leaf(f) in ("sent", "unsent messages") for m in msgs]
    checks = {"agenda_saved": agenda, "booking_saved": booking, "reply_draft": bool(reply), "mentions_vegetarian": diet,
              "drafts": [m["subject"] for m in drafts][:5], "sent_or_outbox": sent[:5]}
    return result((agenda + booking + bool(reply) + diet) / 4, checks)
