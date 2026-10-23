"""Scanned-paper look for the F1 (office documents) pairs o1-o4: render text/tables onto A4 pages with PIL and save
them as image-only PDFs (no text layer), so the content can only be read visually.

Used by build_o*.py on the node (OSWorld venv: PIL only, DejaVu fonts under /usr/share/fonts/truetype/dejavu).
"""
from __future__ import annotations

import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1240, 1754  # A4 at 150 dpi
_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]
_FILES = {"sans": "DejaVuSans.ttf", "bold": "DejaVuSans-Bold.ttf", "serif": "DejaVuSerif.ttf",
          "serifbold": "DejaVuSerif-Bold.ttf", "mono": "DejaVuSansMono.ttf", "monobold": "DejaVuSansMono-Bold.ttf"}
_cache: dict = {}


def font(size: int, kind: str = "sans"):
    key = (size, kind)
    if key not in _cache:
        f = None
        for d in _DIRS:
            p = os.path.join(d, _FILES.get(kind, _FILES["sans"]))
            if os.path.exists(p):
                f = ImageFont.truetype(p, size)
                break
        _cache[key] = f or ImageFont.load_default(size=size)
    return _cache[key]


class Page:
    """One sheet of paper. Coordinates in pixels at 150 dpi (A4 = 1240 x 1754)."""

    def __init__(self, color: bool = False, size=(W, H)):
        self.im = Image.new("RGB", size, "white")
        self.dr = ImageDraw.Draw(self.im)
        self.color = color

    def text(self, x, y, s, size=26, kind="sans", fill=(20, 20, 20), anchor="la"):
        self.dr.text((x, y), s, fill=fill, font=font(size, kind), anchor=anchor)
        return y + int(size * 1.45)

    def right(self, x, y, s, size=26, kind="sans", fill=(20, 20, 20)):
        self.dr.text((x, y), s, fill=fill, font=font(size, kind), anchor="ra")

    def width(self, s, size=26, kind="sans"):
        return self.dr.textlength(s, font=font(size, kind))

    def para(self, x, y, s, size=26, kind="sans", width=1060, fill=(20, 20, 20), gap=1.45):
        """Word-wrapped paragraph; returns the next y."""
        words, line = s.split(), ""
        for w in words:
            cand = (line + " " + w).strip()
            if self.width(cand, size, kind) > width and line:
                self.dr.text((x, y), line, fill=fill, font=font(size, kind))
                y += int(size * gap)
                line = w
            else:
                line = cand
        if line:
            self.dr.text((x, y), line, fill=fill, font=font(size, kind))
            y += int(size * gap)
        return y

    def hline(self, x0, x1, y, w=2, fill=(40, 40, 40)):
        self.dr.line((x0, y, x1, y), fill=fill, width=w)

    def rect(self, box, outline=(40, 40, 40), w=2, fill=None):
        self.dr.rectangle(box, outline=outline, width=w, fill=fill)

    def table(self, x, y, cols, rows, size=24, head_kind="bold", row_h=None, kind="sans", aligns=None):
        """cols: [(header, width)], rows: [[cell...]]; numbers right-aligned when aligns[i] == 'r'."""
        row_h = row_h or int(size * 1.9)
        total = sum(w for _, w in cols)
        aligns = aligns or ["l"] * len(cols)
        self.rect((x, y, x + total, y + row_h * (len(rows) + 1)), w=2)
        cx = x
        for (h, w), al in zip(cols, aligns):
            if al == "r":
                self.right(cx + w - 12, y + 10, h, size, head_kind)
            else:
                self.text(cx + 10, y + 10, h, size, head_kind)
            cx += w
            self.dr.line((cx, y, cx, y + row_h * (len(rows) + 1)), fill=(60, 60, 60), width=1)
        self.hline(x, x + total, y + row_h, 2)
        for i, r in enumerate(rows, 1):
            cx = x
            for (h, w), al, cell in zip(cols, aligns, r):
                if al == "r":
                    self.right(cx + w - 12, y + i * row_h + 10, str(cell), size, kind)
                else:
                    self.text(cx + 10, y + i * row_h + 10, str(cell), size, kind)
                cx += w
            self.dr.line((x, y + (i + 1) * row_h, x + total, y + (i + 1) * row_h), fill=(150, 150, 150), width=1)
        return y + row_h * (len(rows) + 1) + 20

    def stamp(self, x, y, lines, color=(170, 30, 40), size=30, angle=-12):
        """Rubber stamp (rotated box with text), e.g. RECEIVED / DECLINED."""
        f = font(size, "bold")
        tw = int(max(self.width(s, size, "bold") for s in lines)) + 40
        th = int(len(lines) * size * 1.35) + 30
        st = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        d.rectangle((2, 2, tw - 3, th - 3), outline=color + (210,), width=4)
        for i, s in enumerate(lines):
            d.text((tw // 2, 16 + i * size * 1.35), s, fill=color + (210,), font=f, anchor="ma")
        st = st.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.im.paste(st, (x, y), st)

    def hand(self, x, y, s, size=30, color=(200, 25, 25), angle=-3, shear=0.25):
        """Pen annotation: sheared ("italic") text, slightly rotated, in ink colour. Returns the bottom y."""
        f = font(size, "sans")
        tw = int(self.dr.textlength(s, font=f)) + int(size * 1.2)
        th = int(size * 1.8)
        im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((int(size * 0.5), int(size * 0.2)), s, fill=color + (235,), font=f)
        im = im.transform(im.size, Image.AFFINE, (1, shear, -shear * th / 2, 0, 1, 0), resample=Image.BICUBIC)
        im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.im.paste(im, (x, y), im)
        return y + im.size[1]

    def ink_line(self, pts, color=(200, 25, 25), w=4):
        self.dr.line(pts, fill=color, width=w, joint="curve")

    def ink_ellipse(self, box, color=(200, 25, 25), w=4):
        self.dr.ellipse(box, outline=color, width=w)

    def paste(self, im, xy):
        self.im.paste(im, xy)


def _age(im: Image.Image, rng: random.Random, color: bool) -> Image.Image:
    """Scanner look: slight skew, paper tint, speckles, soft blur."""
    angle = rng.uniform(-0.9, 0.9)
    im = im.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(250, 250, 248))
    px = im.load()
    w, h = im.size
    for _ in range(int(w * h / 900)):
        x, y = rng.randrange(w), rng.randrange(h)
        v = rng.randrange(120, 220)
        px[x, y] = (v, v, v)
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    if not color:
        im = im.convert("L").point(lambda v: min(255, int(v * 0.97 + 6)))
    return im


def save_scan(pages, path: str, seed: int, color: bool | None = None):
    """Write the pages as one image-only PDF (JPEG-compressed, ~150 dpi)."""
    rng = random.Random(seed)
    color = any(p.color for p in pages) if color is None else color
    ims = [_age(p.im, rng, color) for p in pages]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ims[0].save(path, "PDF", resolution=150, save_all=True, append_images=ims[1:], quality=70)


def save_png(page: Page, path: str, seed: int):
    rng = random.Random(seed)
    _age(page.im, rng, True).save(path, optimize=True)
