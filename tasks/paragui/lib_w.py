"""Build helpers shared by the F3 intranet-web-app pairs (build_w1..w4.py): fonts, scanned-looking documents,
app-like screenshots, a fresh database with the app's own schema. Runs in the OSWorld venv (PIL available)."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import sqlite3

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONTS = {}


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key not in _FONTS:
        name = "DejaVuSansMono" if mono else "DejaVuSans"
        name += "-Bold" if bold else ""
        path = os.path.join(FONT_DIR, name + ".ttf")
        _FONTS[key] = ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default(size=size)
    return _FONTS[key]


def wrap(draw, text, fnt, width):
    """Greedy word wrap to a pixel width."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            t = (cur + " " + w).strip() if cur else w
            if draw.textlength(t, font=fnt) <= width or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- scanned-looking multi-page documents (image PDF)
def doc_pdf(path, blocks, header=None, footer=None, size=(1240, 1754), margin=110, base=25):
    """blocks: ("title", s) | ("h", s) | ("p", s) | ("li", s) | ("table", [[cells]], [col widths px]) | ("gap", px)
    | ("img", PIL.Image). Writes an image-only PDF (text exists only as pixels, like a scan)."""
    pages, page, dr, y = [], None, None, 0
    width = size[0] - 2 * margin

    def new_page():
        nonlocal page, dr, y
        page = Image.new("RGB", size, "white")
        dr = ImageDraw.Draw(page)
        pages.append(page)
        y = margin
        if header:
            dr.text((margin, 50), header, fill=(110, 110, 110), font=font(17))
            dr.line((margin, 80, size[0] - margin, 80), fill=(180, 180, 180), width=1)
            y = margin + 10

    def need(h):
        if page is None or y + h > size[1] - margin - 30:
            new_page()
    new_page()
    for b in blocks:
        kind = b[0]
        if kind == "gap":
            y += b[1]
            continue
        if kind == "img":
            im = b[1]
            need(im.height + 10)
            page.paste(im, (margin, y))
            y += im.height + 14
            continue
        if kind == "table":
            rows, cols = b[1], b[2]
            f, fb = font(base - 3), font(base - 3, bold=True)
            for i, row in enumerate(rows):
                cell_lines = [wrap(dr, str(c), fb if i == 0 else f, cols[j] - 16) for j, c in enumerate(row)]
                h = max(len(cl) for cl in cell_lines) * (base + 4) + 12
                need(h)
                x = margin
                for j, cl in enumerate(cell_lines):
                    if i == 0:
                        dr.rectangle((x, y, x + cols[j], y + h), fill=(232, 236, 241))
                    dr.rectangle((x, y, x + cols[j], y + h), outline=(120, 120, 120), width=1)
                    for k, ln in enumerate(cl):
                        dr.text((x + 8, y + 6 + k * (base + 4)), ln, fill="black", font=fb if i == 0 else f)
                    x += cols[j]
                y += h
            y += 16
            continue
        text = b[1]
        f = {"title": font(base + 15, bold=True), "h": font(base + 3, bold=True)}.get(kind, font(base))
        lh = {"title": base + 26, "h": base + 12}.get(kind, base + 11)
        indent = 34 if kind == "li" else 0
        lines = wrap(dr, text, f, width - indent)
        if kind == "h":
            y += 12
        for k, ln in enumerate(lines):
            need(lh)
            if kind == "li" and k == 0:
                dr.text((margin + 8, y), "•", fill="black", font=f)
            dr.text((margin + indent, y), ln, fill="black", font=f)
            y += lh
        y += {"title": 18, "h": 4, "p": 12, "li": 4}.get(kind, 8)
    for i, p in enumerate(pages):
        if footer:
            d = ImageDraw.Draw(p)
            d.text((margin, size[1] - 70), f"{footer}  ·  page {i + 1} of {len(pages)}", fill=(110, 110, 110), font=font(16))
    pages[0].save(path, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return len(pages)


# ---------------------------------------------------------------- app-like screenshots
def browser_shot(path, url, title, draw_body, size=(1100, 640)):
    """A PNG that looks like a cropped browser screenshot: tab strip, address bar, then draw_body(draw, img, top)."""
    im = Image.new("RGB", size, (255, 255, 255))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, size[0], 36), fill=(222, 225, 230))
    dr.rounded_rectangle((10, 6, 300, 40), 8, fill=(255, 255, 255))
    dr.text((24, 14), title[:34], fill=(40, 40, 40), font=font(14))
    dr.rectangle((0, 36, size[0], 76), fill=(255, 255, 255))
    dr.rounded_rectangle((70, 44, size[0] - 30, 70), 12, fill=(241, 243, 244))
    dr.text((90, 49), url, fill=(60, 60, 60), font=font(15))
    for i, c in enumerate([(150, 150, 150)] * 3):
        dr.text((12 + i * 18, 46), "‹›↻"[i], fill=c, font=font(16))
    dr.line((0, 76, size[0], 76), fill=(200, 200, 200))
    draw_body(dr, im, 77)
    im.save(path)


def photo_noise(im, seed, amount=6):
    """Light deterministic noise / tint so a 'scan' or 'phone photo' does not look synthetic-perfect."""
    import random
    rng = random.Random(seed)
    px = im.load()
    w, h = im.size
    for _ in range(w * h // 18):
        x, y = rng.randrange(w), rng.randrange(h)
        r, g, b = px[x, y][:3]
        d = rng.randint(-amount, amount)
        px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    return im


# ---------------------------------------------------------------- databases
def load_app(here, app_file):
    spec = importlib.util.spec_from_file_location(app_file[:-3], os.path.join(here, app_file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fresh_db(here, app_file, db_path):
    """Create an empty database with the app's own schema; returns (connection, app module)."""
    if os.path.exists(db_path):
        os.remove(db_path)
    app = load_app(here, app_file)
    con = sqlite3.connect(db_path)
    app.init_schema(con)
    con.row_factory = None
    return con, app


def copy_app(here, out_dir, app_file):
    shutil.copy(os.path.join(here, app_file), os.path.join(out_dir, app_file))
