"""Build-time helpers for the F-family pairs (files, scans, images, media): fonts, photo/scan rendering, EXIF, workbooks.

Imported by build_f1.py .. build_f4.py (build_assets.py runs from this directory, so `import lib_f` works).
Everything is deterministic given the caller's random.Random.
"""
from __future__ import annotations

import hashlib
import io
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/lato"]
FONTS = {"sans": "DejaVuSans.ttf", "sans-bold": "DejaVuSans-Bold.ttf", "serif": "DejaVuSerif.ttf",
         "serif-bold": "DejaVuSerif-Bold.ttf", "mono": "DejaVuSansMono.ttf", "mono-bold": "DejaVuSansMono-Bold.ttf",
         "lato": "Lato-Regular.ttf", "lato-bold": "Lato-Bold.ttf", "lato-black": "Lato-Black.ttf",
         "lato-italic": "Lato-Italic.ttf", "lato-light": "Lato-Light.ttf", "hand": "Lato-MediumItalic.ttf",
         "hand-bold": "Lato-BoldItalic.ttf", "cond": "DejaVuSansCondensed.ttf"}


def font(name: str, size: int):
    fn = FONTS.get(name, name)
    for d in FONT_DIRS:
        p = os.path.join(d, fn)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def md5(path_or_bytes) -> str:
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    return hashlib.md5(data).hexdigest()


def noise(im: Image.Image, rng, sigma: float) -> Image.Image:
    """Additive Gaussian sensor/scanner noise (deterministic from rng)."""
    g = np.random.default_rng(rng.randrange(2 ** 31))
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    a = a + g.normal(0, sigma, a.shape[:2])[..., None] + g.normal(0, sigma / 3, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def hand_text(img: Image.Image, xy, text: str, size: int, rng, fill=(25, 35, 110), bold=False, jitter=0.12):
    """Handwritten-style text: italic glyphs drawn one by one with random size/baseline/rotation jitter."""
    x, y = xy
    for ch in text:
        s = int(size * (1 + rng.uniform(-jitter, jitter)))
        f = font("hand-bold" if bold else "hand", s)
        if ch == " ":
            x += int(size * 0.32)
            continue
        bb = f.getbbox(ch)
        w, h = bb[2] + 6, int(size * 1.5)
        tile = Image.new("L", (w + 8, h + 8), 0)
        ImageDraw.Draw(tile).text((4, 4), ch, fill=255, font=f)
        tile = tile.rotate(rng.uniform(-9, 9), resample=Image.BICUBIC, expand=False)
        col = Image.new("RGB", tile.size, fill)
        img.paste(col, (int(x), int(y + rng.uniform(-size * 0.06, size * 0.06))), tile)
        x += bb[2] * rng.uniform(0.93, 1.03) + 1
    return x


def scan(page: Image.Image, rng, angle: float | None = None, dpi_scale: float = 1.0, quality: int = 70,
         tint=(250, 248, 242), sigma: float = 4.0) -> bytes:
    """Make a page look scanned: slight rotation, off-white paper, blur, noise, JPEG artefacts. Returns JPEG bytes."""
    angle = rng.uniform(-1.6, 1.6) if angle is None else angle
    w, h = page.size
    a = np.asarray(page.convert("RGB"), dtype=np.float32) * (np.array(tint, dtype=np.float32) / 255.0)
    paper = Image.fromarray(a.astype(np.uint8))
    paper = paper.rotate(angle, resample=Image.BICUBIC, fillcolor=(236, 236, 232))
    paper = paper.filter(ImageFilter.GaussianBlur(0.7))
    if dpi_scale != 1.0:
        paper = paper.resize((int(w * dpi_scale), int(h * dpi_scale)), Image.LANCZOS)
    paper = noise(paper, rng, sigma)
    buf = io.BytesIO()
    paper.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def image_pdf(jpeg_pages: list[bytes], path: str, page_size=(595.28, 841.89)):
    """Write an image-only PDF (one full-page JPEG per page, no text layer) with PyMuPDF."""
    import fitz
    doc = fitz.open()
    for jp in jpeg_pages:
        pg = doc.new_page(width=page_size[0], height=page_size[1])
        pg.insert_image(pg.rect, stream=jp)
    doc.set_metadata({"producer": "Brother iPrint&Scan", "creator": "ADS-1700W"})
    doc.save(path, deflate=True, garbage=4)
    doc.close()


def exif_bytes(make="NIKON CORPORATION", model="NIKON Z 6_2", dt=None, artist=None, extra=None) -> bytes:
    ex = Image.Exif()
    ex[0x010F] = make
    ex[0x0110] = model
    ex[0x0112] = 1
    if artist:
        ex[0x013B] = artist
        ex[0x8298] = f"(c) 2026 {artist}"
    if dt:
        ex[0x0132] = dt
    sub = ex.get_ifd(0x8769)
    if dt:
        sub[0x9003] = dt
        sub[0x9004] = dt
    for k, v in (extra or {}).items():
        sub[k] = v
    return ex.tobytes()


def save_jpeg(im: Image.Image, path: str, quality=85, exif: bytes | None = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kw = {"quality": quality, "optimize": True}
    if exif:
        kw["exif"] = exif
    im.convert("RGB").save(path, "JPEG", **kw)


def alpha_bbox(alpha: Image.Image, thr: int = 128):
    return alpha.point(lambda v: 255 if v >= thr else 0).getbbox()
