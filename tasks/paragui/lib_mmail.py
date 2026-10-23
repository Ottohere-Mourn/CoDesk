"""Build-side helpers for the F2 Thunderbird pairs m1..m4 (mail + calendar + address book in one Thunderbird 115).

Used only by build_m*.py (runs on the node with the OSWorld venv python). Wraps lib_thunderbird.make_profile and adds:
  * msg(...)                 an EmailMessage with the usual headers, optional HTML part and attachments
  * DocPage / pdf_text / pdf_scan   business documents (quotes, tickets, memos) as text PDFs or image-only "scans"
  * make_abook(cards, lists) a Thunderbird 115 abook.sqlite (schema copied from the base profile)
  * build_profile(...)       make_profile + enabled Home calendar, calendar time zone, identity for invitations
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import sqlite3
import tarfile
import tempfile
import uuid
from email.message import EmailMessage
from email.utils import format_datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from lib_thunderbird import PROFILE, TB_BASE, make_profile

HOME_CAL = "aadab6ae-07be-4346-8b4c-c725a3830658"  # the storage calendar "Home" of the base profile
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def md5(path) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def font(size, bold=False, mono=False, serif=False):
    name = "DejaVuSansMono" if mono else ("DejaVuSerif" if serif else "DejaVuSans")
    path = f"{FONT_DIR}/{name}{'-Bold' if bold else ''}.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size=size)


# ---------------------------------------------------------------- e-mail
def msg(frm, to, subject, when, mid, body=None, html=None, cc=None, irt=None, attachments=(), reply_to=None):
    """frm/to: 'Name <addr>' strings (to may be a list). attachments: [(filename, bytes, 'type/subtype')]."""
    m = EmailMessage()
    m["From"] = frm
    m["To"] = to if isinstance(to, str) else ", ".join(to)
    if cc:
        m["Cc"] = cc if isinstance(cc, str) else ", ".join(cc)
    if reply_to:
        m["Reply-To"] = reply_to
    m["Subject"] = subject
    m["Date"] = format_datetime(when)
    m["Message-ID"] = mid
    if irt:
        m["In-Reply-To"] = irt
        m["References"] = irt
    m.set_content(body or re.sub(r"<[^>]+>", "", html or ""))
    if html:
        m.add_alternative(html, subtype="html")
    for fname, data, mime in attachments:
        maintype, subtype = mime.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
    return m


# ---------------------------------------------------------------- documents
class DocPage:
    """A simple business-document layout (letterhead, title, key/value block, table, totals, notes) that can be
    rendered as a raster image (for scans / PNGs) or as a PDF with a real text layer (PyMuPDF)."""

    def __init__(self, letterhead, address="", title="", meta=(), table=None, totals=(), notes=(), footer="",
                 accent=(30, 60, 110), widths=None):
        self.letterhead, self.address, self.title = letterhead, address, title
        self.meta, self.table, self.totals, self.notes, self.footer = list(meta), table, list(totals), list(notes), footer
        self.accent, self.widths = accent, widths

    # layout in "points" of an A4/Letter page 612x792; images are drawn at 2x
    def _ops(self):
        ops = [("text", 50, 60, self.letterhead, 20, True, self.accent)]
        y = 82
        for ln in self.address.split("\n") if self.address else []:
            ops.append(("text", 50, y, ln, 9, False, (80, 80, 80)))
            y += 12
        ops.append(("line", 50, y + 6, 562, y + 6, self.accent))
        y += 34
        if self.title:
            ops.append(("text", 50, y, self.title, 15, True, (0, 0, 0)))
            y += 26
        for k, v in self.meta:
            ops.append(("text", 50, y, f"{k}", 10, True, (0, 0, 0)))
            ops.append(("text", 190, y, f"{v}", 10, False, (0, 0, 0)))
            y += 15
        y += 12
        if self.table:
            headers, rows = self.table
            n = len(headers)
            widths = self.widths or ([512 - 90 * (n - 1)] + [90] * (n - 1))
            xs = [50]
            for w in widths[:-1]:
                xs.append(xs[-1] + w)
            ops.append(("rect", 50, y - 12, 562, y + 5, (225, 230, 240)))
            for x, h in zip(xs, headers):
                ops.append(("text", x + 4, y, h, 9.5, True, (0, 0, 0)))
            y += 19
            for row in rows:
                for x, c in zip(xs, row):
                    ops.append(("text", x + 4, y, str(c), 9.5, False, (0, 0, 0)))
                y += 16
            ops.append(("line", 50, y - 8, 562, y - 8, (150, 150, 150)))
            y += 8
        for k, v in self.totals:
            bold = k.lower().startswith("total")
            ops.append(("text", 340, y, k, 10, bold, (0, 0, 0)))
            ops.append(("text", 480, y, v, 10, bold, (0, 0, 0)))
            y += 15
        y += 14
        for ln in self.notes:  # a leading "**" makes the line bold
            bold = ln.startswith("**")
            ops.append(("text", 50, y, ln[2:] if bold else ln, 9.5, bold, (0, 0, 0)))
            y += 14
        if self.footer:
            ops.append(("text", 50, 760, self.footer, 8, False, (110, 110, 110)))
        return ops

    def image(self, scale=2.0) -> Image.Image:
        im = Image.new("RGB", (int(612 * scale), int(792 * scale)), "white")
        dr = ImageDraw.Draw(im)
        for op in self._ops():
            if op[0] == "text":
                _, x, y, s, size, bold, col = op
                f = font(int(size * scale), bold)
                dr.text((x * scale, y * scale - size * scale * 0.95), s, fill=col, font=f)
            elif op[0] == "line":
                _, x0, y0, x1, y1, col = op
                dr.line((x0 * scale, y0 * scale, x1 * scale, y1 * scale), fill=col, width=max(1, int(scale)))
            elif op[0] == "rect":
                _, x0, y0, x1, y1, col = op
                dr.rectangle((x0 * scale, y0 * scale, x1 * scale, y1 * scale), fill=col)
        return im

    def pdf_text(self, path):
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        for op in self._ops():
            if op[0] == "text":
                _, x, y, s, size, bold, col = op
                page.insert_text((x, y), s, fontsize=size, fontname="hebo" if bold else "helv",
                                 color=tuple(c / 255 for c in col))
            elif op[0] == "line":
                _, x0, y0, x1, y1, col = op
                page.draw_line((x0, y0), (x1, y1), color=tuple(c / 255 for c in col), width=1)
            elif op[0] == "rect":
                _, x0, y0, x1, y1, col = op
                page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=tuple(c / 255 for c in col))
        doc.save(path, deflate=True)
        doc.close()


def scan_look(im: Image.Image, seed: int, angle=None, stamp=None) -> Image.Image:
    """Make a rendered page look scanned: grey paper, tiny rotation, speckles, slight blur, optional rubber stamp."""
    r = random.Random(seed)
    im = im.convert("RGB")
    if stamp:
        st = Image.new("RGBA", (520, 150), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        d.rounded_rectangle((4, 4, 516, 146), radius=18, outline=(170, 30, 40, 200), width=7)
        d.text((30, 38), stamp, fill=(170, 30, 40, 210), font=font(56, True))
        st = st.rotate(r.uniform(-12, 12), expand=True)
        im.paste(st, (im.width - st.width - 90, im.height - st.height - 260), st)
    paper = Image.new("RGB", im.size, (243, 241, 236))
    im = Image.blend(im, paper, 0.18)
    a = angle if angle is not None else r.uniform(-0.9, 0.9)
    im = im.rotate(a, resample=Image.BICUBIC, expand=False, fillcolor=(236, 234, 228))
    px = im.load()
    for _ in range(im.width * im.height // 900):
        x, y = r.randrange(im.width), r.randrange(im.height)
        g = r.randrange(90, 200)
        px[x, y] = (g, g, g)
    return im.filter(ImageFilter.GaussianBlur(0.6)).convert("L").convert("RGB")


def pdf_scan(path, images, resolution=144):
    """Image-only PDF (no text layer) from one or more PIL images."""
    images = [i.convert("RGB") for i in images]
    images[0].save(path, "PDF", resolution=resolution, save_all=True, append_images=images[1:])


# ---------------------------------------------------------------- address book (Thunderbird 115 abook.sqlite)
def vcard(c: dict, uid: str) -> str:
    first, last = c.get("first", ""), c.get("last", "")
    lines = ["BEGIN:VCARD", "VERSION:4.0", f"N:{last};{first};;;", f"FN:{c.get('display') or (first + ' ' + last).strip()}"]
    emails = [e for e in (c.get("email"), c.get("email2")) if e]
    for i, e in enumerate(emails):
        lines.append(f"EMAIL;PREF={i + 1}:{e}" if i == 0 else f"EMAIL:{e}")
    if c.get("org"):
        lines.append(f"ORG:{c['org']}")
    if c.get("title"):
        lines.append(f"TITLE:{c['title']}")
    if c.get("phone"):
        lines.append(f"TEL;TYPE=work;VALUE=TEXT:{c['phone']}")
    if c.get("cell"):
        lines.append(f"TEL;TYPE=cell;VALUE=TEXT:{c['cell']}")
    if c.get("note"):
        lines.append("NOTE:" + c["note"].replace("\n", "\\n").replace(",", "\\,"))
    lines += [f"UID:{uid}", "END:VCARD"]
    return "\r\n".join(lines) + "\r\n"


def make_abook(cards: list[dict], lists: list[dict] = (), seed: int = 1) -> tuple[bytes, dict]:
    """cards: {first,last,display,email,email2,org,title,phone,...}; lists: {name, nick, description, members:[email]}.
    Returns (sqlite bytes, {email: card uid}). Each card gets the _vCard property (what Thunderbird 115 reads) plus
    the derived plain properties Thunderbird writes next to it for searching/sorting."""
    r = random.Random(seed)
    tmp = tempfile.mkdtemp()
    with tarfile.open(TB_BASE) as t:
        member = t.getmember(f".thunderbird/{PROFILE}/abook.sqlite")
        open(f"{tmp}/abook.sqlite", "wb").write(t.extractfile(member).read())
    con = sqlite3.connect(f"{tmp}/abook.sqlite")
    con.execute("DELETE FROM properties")
    con.execute("DELETE FROM lists")
    con.execute("DELETE FROM list_cards")
    uids = {}
    for i, c in enumerate(cards):
        uid = str(uuid.UUID(int=r.getrandbits(128), version=4))
        uids[c["email"].lower()] = uid
        props = {"_vCard": vcard(c, uid), "DisplayName": c.get("display") or f"{c.get('first', '')} {c.get('last', '')}".strip(),
                 "FirstName": c.get("first", ""), "LastName": c.get("last", ""), "PrimaryEmail": c["email"],
                 "SecondEmail": c.get("email2", ""), "LastModifiedDate": str(1790000000 + i * 3600)}
        for k, v in props.items():
            if v:
                con.execute("INSERT INTO properties VALUES (?,?,?)", (uid, k, v))
    for lst in lists:
        luid = str(uuid.UUID(int=r.getrandbits(128), version=4))
        con.execute("INSERT INTO lists VALUES (?,?,?,?)", (luid, lst["name"], lst.get("nick", ""), lst.get("description", "")))
        for e in lst.get("members", []):
            con.execute("INSERT INTO list_cards VALUES (?,?)", (luid, uids[e.lower()]))
    con.commit()
    con.close()
    data = open(f"{tmp}/abook.sqlite", "rb").read()
    os.remove(f"{tmp}/abook.sqlite")
    os.rmdir(tmp)
    return data, uids


# ---------------------------------------------------------------- profile
def build_profile(out_tar, me, folders, tz: str, extra_files=None, extra_prefs=None):
    """make_profile + calendar settings: the base profile ships the Home calendar *disabled* and follows the system
    time zone; we enable it, pin the calendar time zone to the persona's, attach the mail identity (so the event
    dialog can invite attendees) and switch off iTIP e-mail notifications (there is no SMTP server)."""
    prefs = {
        f"calendar.registry.{HOME_CAL}.disabled": False,
        f"calendar.registry.{HOME_CAL}.imip.identity.key": "id1",
        "calendar.timezone.useSystemTimezone": False,
        "calendar.timezone.local": tz,
        "calendar.itip.notify": False,
        **(extra_prefs or {}),
    }
    box = make_profile(out_tar, me, folders, extra_prefs=prefs, extra_files=extra_files)
    _dedupe_prefs(out_tar)
    return box


def _dedupe_prefs(tar_path):
    """make_profile appends our prefs after the base ones; drop the earlier duplicates so prefs.js has one line each."""
    tmp = tempfile.mkdtemp()
    with tarfile.open(tar_path) as t:
        t.extractall(tmp)
    pj = f"{tmp}/.thunderbird/{PROFILE}/prefs.js"
    lines = open(pj).read().splitlines(True)
    last = {}
    for i, ln in enumerate(lines):
        m = re.match(r'user_pref\("([^"]+)"', ln)
        if m:
            last[m.group(1)] = i
    keep = [ln for i, ln in enumerate(lines)
            if not (re.match(r'user_pref\("([^"]+)"', ln) and last[re.match(r'user_pref\("([^"]+)"', ln).group(1)] != i)]
    open(pj, "w").writelines(keep)
    with tarfile.open(tar_path, "w:gz") as t:
        t.add(f"{tmp}/.thunderbird", arcname=".thunderbird")
    import shutil
    shutil.rmtree(tmp)


def dump_expected(d, data: dict):
    json.dump(data, open(f"{d}/expected.json", "w"), indent=1, default=str)


def png_bytes(im: Image.Image, fmt="PNG") -> bytes:
    b = io.BytesIO()
    im.save(b, fmt, **({"quality": 85} if fmt == "JPEG" else {}))
    return b.getvalue()
