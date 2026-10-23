"""Receipt and travel-document images for pair W2 (Fenwick Spend): thermal till receipts, phone photos of receipts,
hotel folios / e-tickets / rental agreements as A4 documents, a ride-share app screenshot. Deterministic (seeded)."""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter

from lib_w import font, photo_noise


def _mono(size, bold=False):
    return font(size, bold=bold, mono=True)


def thermal(rows, width=500):
    """rows: ("c", text[, size, bold]) centred | ("l", text) | ("lr", left, right[, bold]) | ("sep",) | ("gap", px)
    | ("barcode", seed). Returns a PIL image of a till receipt."""
    lh = {"c": 30, "l": 27, "lr": 27, "sep": 22, "barcode": 70}
    h = 50 + sum(r[1] if r[0] == "gap" else (r[2] + 12 if r[0] == "c" and len(r) > 2 else lh[r[0]]) for r in rows) + 40
    im = Image.new("RGB", (width, h), (252, 251, 245))
    dr = ImageDraw.Draw(im)
    y, ink = 45, (38, 36, 40)
    for r in rows:
        k = r[0]
        if k == "gap":
            y += r[1]
        elif k == "c":
            size = r[2] if len(r) > 2 else 19
            f = _mono(size, len(r) > 3 and r[3])
            dr.text(((width - dr.textlength(r[1], font=f)) / 2, y), r[1], fill=ink, font=f)
            y += size + 12 if len(r) > 2 else lh["c"]
        elif k == "l":
            dr.text((28, y), r[1], fill=ink, font=_mono(18))
            y += lh["l"]
        elif k == "lr":
            f = _mono(18, len(r) > 3 and r[3])
            dr.text((28, y), r[1], fill=ink, font=f)
            dr.text((width - 28 - dr.textlength(r[2], font=f), y), r[2], fill=ink, font=f)
            y += lh["lr"]
        elif k == "sep":
            dr.text((28, y), "-" * 38, fill=(90, 90, 90), font=_mono(18))
            y += lh["sep"]
        elif k == "barcode":
            rng = random.Random(r[1])
            x = 70
            while x < width - 70:
                w = rng.choice((2, 2, 3, 4))
                dr.rectangle((x, y, x + w - 1, y + 50), fill=ink)
                x += w + rng.choice((2, 3, 4))
            y += lh["barcode"]
    return im


def photo(im, seed, angle=None, bg=(78, 62, 50)):
    """A phone photo of a paper receipt lying on a table: margins, slight rotation, shading and noise."""
    rng = random.Random(seed)
    angle = rng.uniform(-2.2, 2.2) if angle is None else angle
    rot = im.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=bg)
    W, H = rot.width + 120, rot.height + 140
    canvas = Image.new("RGB", (W, H), bg)
    dr = ImageDraw.Draw(canvas)
    for i in range(0, H, 6):  # wood-grain-ish stripes
        c = tuple(max(0, min(255, v + rng.randint(-6, 6))) for v in bg)
        dr.line((0, i, W, i + rng.randint(-3, 3)), fill=c, width=3)
    canvas.paste(rot, (60, 70))
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for i in range(W):
        sd.line((i, 0, i, H), fill=int(40 * i / W))
    canvas = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), canvas, shade.point(lambda v: v // 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.6))
    return photo_noise(canvas, seed, 7)


def document(title, brand, brand_color, addr, fields, table_head, table_rows, totals, footer_lines, col_w, size=(1000, 1294)):
    """An A4-style document (hotel folio, e-ticket, rental agreement): brand bar, key/value fields, a charges table."""
    im = Image.new("RGB", size, "white")
    dr = ImageDraw.Draw(im)
    W = size[0]
    dr.rectangle((0, 0, W, 110), fill=brand_color)
    dr.text((50, 26), brand, fill="white", font=font(36, bold=True))
    dr.text((50, 74), addr, fill=(230, 235, 240), font=font(16))
    dr.text((50, 145), title, fill=(30, 30, 30), font=font(30, bold=True))
    y = 205
    for i, (k, v) in enumerate(fields):
        x = 50 if i % 2 == 0 else W // 2 + 10
        dr.text((x, y), k, fill=(110, 110, 110), font=font(15))
        dr.text((x, y + 20), v, fill=(25, 25, 25), font=font(19, bold=True))
        if i % 2 == 1 or i == len(fields) - 1:
            y += 62
    y += 20
    xs = [50]
    for w in col_w[:-1]:
        xs.append(xs[-1] + w)
    dr.rectangle((50, y, W - 50, y + 36), fill=(236, 239, 243))
    for j, (x, hd) in enumerate(zip(xs, table_head)):
        fh = font(16, bold=True)
        tx = x + 8 if j < len(table_head) - 1 else W - 58 - dr.textlength(hd, font=fh)
        dr.text((tx, y + 8), hd, fill=(40, 40, 40), font=fh)
    y += 44
    for row in table_rows:
        for j, (x, c) in enumerate(zip(xs, row)):
            f = font(17)
            tx = x + 8 if j < len(row) - 1 else W - 58 - dr.textlength(c, font=f)
            dr.text((tx, y), c, fill=(30, 30, 30), font=f)
        y += 32
        dr.line((50, y - 4, W - 50, y - 4), fill=(225, 228, 232))
    y += 12
    for label, val, bold in totals:
        f = font(19, bold=bold)
        dr.text((W - 420, y), label, fill=(30, 30, 30), font=f)
        dr.text((W - 58 - dr.textlength(val, font=f), y), val, fill=(30, 30, 30), font=f)
        y += 34
    y += 30
    for ln in footer_lines:
        dr.text((50, y), ln, fill=(95, 95, 95), font=font(15))
        y += 24
    return im


def rideshare(path, when, pickup, dropoff, items, total, card, driver, seed):
    """Screenshot of a ride-share app receipt (phone, 540 x 1100)."""
    W, H = 540, 1100
    im = Image.new("RGB", (W, H), (248, 248, 250))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, W, 40), fill=(20, 20, 24))
    dr.text((20, 10), "9:41", fill="white", font=font(16, bold=True))
    dr.text((W - 90, 10), "5G  83%", fill="white", font=font(15))
    dr.rectangle((0, 40, W, 130), fill=(108, 46, 210))
    dr.text((30, 62), "zipp", fill="white", font=font(40, bold=True))
    dr.text((150, 80), "Trip receipt", fill=(230, 220, 250), font=font(20))
    y = 160
    dr.text((30, y), "Thanks for riding, Dana", fill=(25, 25, 25), font=font(26, bold=True))
    dr.text((30, y + 42), when, fill=(100, 100, 100), font=font(18))
    y += 100
    dr.rounded_rectangle((20, y, W - 20, y + 150), 14, fill="white", outline=(225, 225, 230))
    dr.ellipse((40, y + 28, 54, y + 42), fill=(108, 46, 210))
    dr.text((70, y + 22), pickup, fill=(30, 30, 30), font=font(17))
    dr.line((47, y + 46, 47, y + 98), fill=(180, 180, 190), width=2)
    dr.rectangle((40, y + 100, 54, y + 114), fill=(30, 30, 30))
    dr.text((70, y + 95), dropoff, fill=(30, 30, 30), font=font(17))
    y += 180
    dr.rounded_rectangle((20, y, W - 20, y + 60 + 40 * len(items) + 70), 14, fill="white", outline=(225, 225, 230))
    dr.text((40, y + 20), "Payment", fill=(25, 25, 25), font=font(20, bold=True))
    y += 64
    for k, v in items:
        dr.text((40, y), k, fill=(70, 70, 70), font=font(18))
        dr.text((W - 40 - dr.textlength(v, font=font(18)), y), v, fill=(70, 70, 70), font=font(18))
        y += 40
    dr.line((40, y, W - 40, y), fill=(220, 220, 225))
    dr.text((40, y + 14), "Total", fill=(20, 20, 20), font=font(22, bold=True))
    dr.text((W - 40 - dr.textlength(total, font=font(22, bold=True)), y + 14), total, fill=(20, 20, 20), font=font(22, bold=True))
    y += 100
    dr.text((30, y), card, fill=(90, 90, 90), font=font(17))
    dr.text((30, y + 34), driver, fill=(90, 90, 90), font=font(17))
    dr.text((30, H - 60), "Zipp Mobility Inc. · help.zipp.example", fill=(150, 150, 155), font=font(14))
    photo_noise(im, seed, 2).save(path)
