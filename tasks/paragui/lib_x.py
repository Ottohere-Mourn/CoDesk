"""Build-time helpers shared by the F6 cross-application pairs (build_x1.py .. build_x4.py).

Runs on the node with the OSWorld venv python (PIL, PyMuPDF, openpyxl available).
- Page / scanned_pdf / scanned_image: paper documents rendered to pixels (image-only PDFs, phone photos of forms)
- text_pdf: a normal "digital" PDF with a text layer (PyMuPDF)
- mail: an EmailMessage with a stable Message-ID, optional reply headers and attachments
- seed_db: create a sqlite db from a schema string and {table: [row dicts]}
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import random
import shutil
import sqlite3
from email.message import EmailMessage
from email.utils import format_datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
W, H = 1240, 1754  # A4 at 150 dpi


def md5(path: str) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def font(size: int, bold: bool = False, mono: bool = False, serif: bool = False, oblique: bool = False):
    fam = "DejaVuSansMono" if mono else ("DejaVuSerif" if serif else "DejaVuSans")
    suffix = "-Bold" if bold else ""
    if oblique and not serif:
        suffix += "Oblique" if bold else "-Oblique"
    for name in (fam + suffix + ".ttf", fam + ("-Bold" if bold else "") + ".ttf", fam + ".ttf"):
        p = os.path.join(FONT_DIR, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def money(v: float, cur: str = "£") -> str:
    return f"{'-' if v < 0 else ''}{cur}{abs(v):,.2f}"


class Page:
    """A white page you draw a paper document on (letterheads, tables, forms)."""

    def __init__(self, w: int = W, h: int = H, bg=(255, 255, 255)):
        self.im = Image.new("RGB", (w, h), bg)
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h = w, h

    def text(self, x, y, s, size=24, bold=False, mono=False, serif=False, fill=(25, 25, 25), anchor="la", oblique=False):
        self.d.text((x, y), s, fill=fill, font=font(size, bold, mono, serif, oblique), anchor=anchor)
        return y + int(size * 1.45)

    def lines(self, x, y, rows, size=24, gap=1.45, **kw):
        for r in rows:
            self.text(x, y, r, size=size, **kw)
            y += int(size * gap)
        return y

    def hline(self, x1, x2, y, width=2, fill=(60, 60, 60)):
        self.d.line((x1, y, x2, y), fill=fill, width=width)

    def rect(self, box, outline=(60, 60, 60), width=2, fill=None):
        self.d.rectangle(box, outline=outline, width=width, fill=fill)

    def table(self, x, y, cols, rows, size=21, row_h=34, header=True, grid=True, header_fill=(228, 228, 228), mono=False):
        """cols: [(title, width, 'l'|'r')]; rows: list of tuples of str. Returns the y below the table."""
        total = sum(c[1] for c in cols)
        allrows = ([tuple(c[0] for c in cols)] if header else []) + list(rows)
        for i, row in enumerate(allrows):
            is_head = header and i == 0
            if is_head and header_fill:
                self.d.rectangle((x, y, x + total, y + row_h), fill=header_fill)
            cx = x
            for (title, width, align), cell in zip(cols, row):
                f = font(size, bold=is_head, mono=mono and not is_head)
                if align == "r":
                    self.d.text((cx + width - 8, y + row_h // 2), str(cell), fill=(20, 20, 20), font=f, anchor="rm")
                else:
                    self.d.text((cx + 8, y + row_h // 2), str(cell), fill=(20, 20, 20), font=f, anchor="lm")
                cx += width
            if grid:
                self.d.line((x, y + row_h, x + total, y + row_h), fill=(150, 150, 150), width=1)
            y += row_h
        if grid:
            self.d.rectangle((x, y - row_h * len(allrows), x + total, y), outline=(90, 90, 90), width=2)
            cx = x
            for _, width, _ in cols[:-1]:
                cx += width
                self.d.line((cx, y - row_h * len(allrows), cx, y), fill=(150, 150, 150), width=1)
        return y

    def stamp(self, x, y, s, color=(170, 30, 30), size=40, angle=12):
        """A rubber stamp (e.g. PAID, RECEIVED) drawn rotated onto the page."""
        f = font(size, bold=True)
        tw = int(self.d.textlength(s, font=f)) + 40
        layer = Image.new("RGBA", (tw, size + 40), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        dl.rectangle((2, 2, tw - 3, size + 37), outline=color + (200,), width=4)
        dl.text((20, 18), s, font=f, fill=color + (210,))
        layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.im.paste(layer, (x, y), layer)

    def handwriting(self, x, y, s, size=34, fill=(20, 40, 120), seed=0):
        """Pen-like text: oblique font, jittered baseline, blue ink."""
        r = random.Random(seed)
        f = font(size, oblique=True)
        cx = x
        for ch in s:
            self.d.text((cx, y + r.randint(-2, 2)), ch, font=f, fill=fill)
            cx += int(self.d.textlength(ch, font=f)) + r.randint(-1, 1)
        return cx


def _degrade(im: Image.Image, r: random.Random, angle: float | None = None, paper=(247, 245, 236)) -> Image.Image:
    """Make a clean render look like a flatbed scan: paper tint, tilt, blur, noise, slightly washed-out ink."""
    im = im.convert("RGB")
    tint = Image.new("RGB", im.size, paper)
    im = Image.blend(im, tint, 0.10)
    a = angle if angle is not None else r.uniform(-0.9, 0.9)
    im = im.rotate(a, resample=Image.BICUBIC, expand=False, fillcolor=paper)
    im = im.filter(ImageFilter.GaussianBlur(0.7))
    noise = Image.effect_noise(im.size, 22).convert("RGB")
    im = Image.blend(im, noise, 0.06)
    return im


def scanned_pdf(path: str, pages: list[Page], seed: int = 0, dpi: int = 150):
    """Image-only PDF (no text layer) that looks like a scan of the given pages."""
    r = random.Random(seed)
    ims = [_degrade(p.im, r) for p in pages]
    ims[0].save(path, "PDF", resolution=dpi, save_all=True, append_images=ims[1:], quality=72)


def photo_jpg(path: str, page: Page, seed: int = 0, size=(1200, 1600)):
    """A phone photo of a small paper document (receipt, card): on a desk background, perspective-ish tilt."""
    r = random.Random(seed)
    doc = _degrade(page.im, r, angle=0)
    bg = Image.new("RGB", (size[0] + 200, size[1] + 200), (118, 96, 74))
    bg = Image.blend(bg, Image.effect_noise(bg.size, 40).convert("RGB"), 0.15)
    scale = min((size[0] - 120) / doc.width, (size[1] - 120) / doc.height)
    doc = doc.resize((int(doc.width * scale), int(doc.height * scale)), Image.LANCZOS)
    rot = doc.convert("RGBA").rotate(r.uniform(-4, 4), resample=Image.BICUBIC, expand=True)
    bg.paste(rot, ((bg.width - rot.width) // 2, (bg.height - rot.height) // 2), rot)
    bg = bg.crop((100, 100, 100 + size[0], 100 + size[1])).filter(ImageFilter.GaussianBlur(0.8))
    bg.save(path, "JPEG", quality=78)


def text_pdf(path: str, pages: list[list[tuple]], title: str = ""):
    """Digital PDF with a text layer. pages: [[(x, y, text, size, bold), ...], ...] in points on A4 (595x842)."""
    import fitz
    doc = fitz.open()
    for items in pages:
        pg = doc.new_page(width=595, height=842)
        for it in items:
            x, y, s, size = it[:4]
            bold = len(it) > 4 and it[4]
            color = it[5] if len(it) > 5 else (0.1, 0.1, 0.1)
            pg.insert_text((x, y), s, fontsize=size, fontname="hebo" if bold else "helv", color=color)
    doc.set_metadata({"title": title, "producer": "Microsoft® Word for Microsoft 365", "creator": "Microsoft® Word"})
    doc.save(path, garbage=3, deflate=True)


def flow(items: list[tuple], x0=56, y0=72, width_chars=92, bottom=790) -> list[list[tuple]]:
    """Lay out ('h1'|'h2'|'p'|'li'|'sp', text) blocks into text_pdf pages with naive word wrapping."""
    import textwrap
    pages, cur, y = [], [], y0
    style = {"h1": (18, True, 26, 0), "h2": (12.5, True, 20, 0), "p": (10, False, 14, 0), "li": (10, False, 14, 12),
             "small": (8.5, False, 12, 0)}
    for kind, text in items:
        if kind == "sp":
            y += 8
            continue
        size, bold, lh, indent = style[kind]
        wrap = textwrap.wrap(text, int(width_chars * 10 / size) - (2 if indent else 0)) or [""]
        for i, ln in enumerate(wrap):
            if y > bottom:
                pages.append(cur)
                cur, y = [], y0
            prefix = ("• " if i == 0 else "  ") if kind == "li" else ""
            cur.append((x0 + indent, y, prefix + ln, size, bold))
            y += lh
        if kind in ("h1", "h2"):
            y += 4
    pages.append(cur)
    return pages


def mail(frm: tuple[str, str], to: list[tuple[str, str]], subject: str, body: str, when: dt.datetime, mid: str,
         cc: list[tuple[str, str]] | None = None, irt: str | None = None, refs: list[str] | None = None,
         atts=(), html: str | None = None) -> EmailMessage:
    """atts: [(filename, bytes, 'maintype/subtype')]."""
    m = EmailMessage()
    m["From"] = f"{frm[0]} <{frm[1]}>"
    m["To"] = ", ".join(f"{n} <{a}>" for n, a in to)
    if cc:
        m["Cc"] = ", ".join(f"{n} <{a}>" for n, a in cc)
    m["Subject"] = subject
    m["Date"] = format_datetime(when)
    m["Message-ID"] = mid
    if irt:
        m["In-Reply-To"] = irt
        m["References"] = " ".join((refs or []) + ([irt] if irt not in (refs or []) else []))
    m["MIME-Version"] = "1.0"
    m.set_content(body)
    if html:
        m.add_alternative(html, subtype="html")
    for name, data, mime in atts:
        maintype, subtype = mime.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return m


def seed_db(path: str, schema: str, rows: dict[str, list[dict]]):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(schema)
    for table, items in rows.items():
        for r in items:
            keys = list(r)
            con.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
                        [r[k] for k in keys])
    con.commit()
    con.execute("VACUUM")
    con.close()


def copy_app(src_name: str, out_dir: str):
    """Copy app_x<n>.py next to the other assets (start_webapp uploads it from the assets dir)."""
    here = os.path.dirname(os.path.abspath(__file__))
    shutil.copy(os.path.join(here, src_name), os.path.join(out_dir, src_name))


def pw_hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()
