"""F1 assets - a ceramics shop's product shoot: culling/organising the frames vs making the webshop images.

Writes into out_dir:
  shoot/DSC_*.JPG            37 camera frames (2400x1600 JPEG with EXIF): test frames, slates, product frames
  Shoot_2026-10-14.xlsx      the photographer's workbook ("Shot list" for task A, "Web images" for task B)
  webshop/KF-108.jpg         last week's finished web image (the reference look, with the text watermark)
  shoot.tar.gz               shoot/ + workbook, extracted once by setup
  expected.json              ground truth (frame kinds, SKUs, statuses, new names, product boxes) - host only
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import tarfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import lib_f
from lib_f import font, hand_text, md5, noise

W, H = 2400, 1600
SKUS = {  # sku: (product name, shape, glaze rgb)
    "KF-201": ("Fjord mug - sage", "mug", (128, 160, 118)),
    "KF-202": ("Fjord mug - cobalt", "mug", (36, 64, 156)),
    "KF-215": ("Dune vase - terracotta", "vase", (186, 92, 56)),
    "KF-221": ("Tide bowl - ocean", "bowl", (30, 118, 132)),
    "KF-230": ("Ember teapot - oxblood", "teapot", (142, 34, 40)),
    "KF-233": ("Moss planter", "planter", (96, 112, 58)),
    "KF-240": ("Slate dinner plates (set of 4)", "plate", (74, 80, 92)),
    "KF-244": ("Honey pitcher", "pitcher", (214, 150, 36)),
}
# per product, after its slate: s = sharp, b = out of focus, r = sharp portrait frame stored sideways, uN = burst of N
SHOTS = {"KF-201": ["s", "b", "s"], "KF-202": ["b", "s", "s"], "KF-215": ["b", "r", "b"],
         "KF-221": ["s", "u3", "s"], "KF-230": ["s", "b", "u2"], "KF-233": ["s", "s"],
         "KF-240": ["b", "s"], "KF-244": ["r", "b", "s"]}
WEB_SKUS = ["KF-202", "KF-215", "KF-230", "KF-244"]
HEIGHT = {"mug": 0.50, "vase": 0.66, "bowl": 0.26, "teapot": 0.50, "planter": 0.62, "plate": 0.22, "pitcher": 0.60}
WATERMARK = "© Kestrel & Fern"


# ---------------------------------------------------------------- drawing
def draw_labels(kind: str, h: int) -> Image.Image:
    """Label image at 2x scale (L): 1 glaze, 2 interior/shadowed glaze, 3 plant. h = product height in final px."""
    s = 2
    hh = h * s
    cw, ch = int(hh * 2.3), int(hh * 1.15)
    im = Image.new("L", (cw, ch), 0)
    d = ImageDraw.Draw(im)
    cx, top, bot = cw / 2, (ch - hh) / 2, (ch + hh) / 2
    k = hh
    if kind == "mug":
        d.ellipse((cx + 0.22 * k, top + 0.22 * k, cx + 0.70 * k, top + 0.78 * k), outline=1, width=int(0.1 * k))
        d.rounded_rectangle((cx - 0.4 * k, top + 0.08 * k, cx + 0.4 * k, bot), int(0.09 * k), fill=1)
        d.ellipse((cx - 0.4 * k, top, cx + 0.4 * k, top + 0.16 * k), fill=1)
        d.ellipse((cx - 0.36 * k, top + 0.02 * k, cx + 0.36 * k, top + 0.14 * k), fill=2)
    elif kind == "vase":
        d.ellipse((cx - 0.26 * k, top + 0.34 * k, cx + 0.26 * k, bot), fill=1)
        d.polygon([(cx - 0.09 * k, top + 0.06 * k), (cx + 0.09 * k, top + 0.06 * k),
                   (cx + 0.2 * k, top + 0.45 * k), (cx - 0.2 * k, top + 0.45 * k)], fill=1)
        d.ellipse((cx - 0.14 * k, top, cx + 0.14 * k, top + 0.1 * k), fill=1)
        d.ellipse((cx - 0.1 * k, top + 0.015 * k, cx + 0.1 * k, top + 0.08 * k), fill=2)
    elif kind == "bowl":
        d.chord((cx - 1.0 * k, top - 0.9 * k, cx + 1.0 * k, bot - 0.06 * k), 0, 180, fill=1)
        d.rectangle((cx - 0.35 * k, bot - 0.1 * k, cx + 0.35 * k, bot), fill=1)
        d.ellipse((cx - 1.0 * k, top - 0.14 * k, cx + 1.0 * k, top + 0.14 * k), fill=1)
        d.ellipse((cx - 0.93 * k, top - 0.1 * k, cx + 0.93 * k, top + 0.1 * k), fill=2)
    elif kind == "teapot":
        d.ellipse((cx + 0.3 * k, top + 0.3 * k, cx + 0.85 * k, top + 0.82 * k), outline=1, width=int(0.08 * k))
        d.polygon([(cx - 0.42 * k, top + 0.62 * k), (cx - 0.98 * k, top + 0.22 * k), (cx - 0.9 * k, top + 0.16 * k),
                   (cx - 0.38 * k, top + 0.42 * k)], fill=1)
        d.ellipse((cx - 0.58 * k, top + 0.24 * k, cx + 0.58 * k, bot), fill=1)
        d.ellipse((cx - 0.3 * k, top + 0.15 * k, cx + 0.3 * k, top + 0.34 * k), fill=2)
        d.ellipse((cx - 0.08 * k, top, cx + 0.08 * k, top + 0.19 * k), fill=1)
    elif kind == "planter":
        for i, (dx, ang) in enumerate([(-0.25, -35), (0.0, 0), (0.22, 30), (-0.1, -12), (0.12, 14)]):
            leaf = Image.new("L", (int(0.3 * k), int(0.6 * k)), 0)
            ImageDraw.Draw(leaf).ellipse((0, 0, leaf.size[0] - 1, leaf.size[1] - 1), fill=255)
            leaf = leaf.rotate(ang, expand=True)
            im.paste(3, (int(cx + dx * k - leaf.size[0] / 2), int(top)), leaf)
        d.polygon([(cx - 0.45 * k, top + 0.4 * k), (cx + 0.45 * k, top + 0.4 * k), (cx + 0.33 * k, bot),
                   (cx - 0.33 * k, bot)], fill=1)
        d.rectangle((cx - 0.48 * k, top + 0.36 * k, cx + 0.48 * k, top + 0.48 * k), fill=1)
    elif kind == "plate":
        for i in range(4):
            y0 = top + i * 0.2 * k
            d.ellipse((cx - 2.1 * k, y0, cx + 2.1 * k, y0 + 0.45 * k), fill=1)
        d.ellipse((cx - 1.6 * k, top + 0.04 * k, cx + 1.6 * k, top + 0.34 * k), fill=2)
    elif kind == "pitcher":
        d.ellipse((cx + 0.2 * k, top + 0.2 * k, cx + 0.62 * k, top + 0.72 * k), outline=1, width=int(0.08 * k))
        d.ellipse((cx - 0.34 * k, top + 0.32 * k, cx + 0.34 * k, bot), fill=1)
        d.polygon([(cx - 0.22 * k, top + 0.06 * k), (cx + 0.24 * k, top + 0.04 * k), (cx + 0.3 * k, top + 0.5 * k),
                   (cx - 0.3 * k, top + 0.5 * k)], fill=1)
        d.polygon([(cx - 0.22 * k, top + 0.06 * k), (cx - 0.4 * k, top - 0.02 * k), (cx - 0.18 * k, top + 0.16 * k)], fill=1)
        d.ellipse((cx - 0.22 * k, top, cx + 0.24 * k, top + 0.1 * k), fill=2)
    return im


def render_product(kind: str, rgb, h: int, rng) -> Image.Image:
    """RGBA product cut-out: glaze with cylindrical shading, highlight, speckles."""
    big = draw_labels(kind, h)
    half = (big.size[0] // 2, big.size[1] // 2)
    full = np.asarray(big.resize(half, Image.NEAREST))
    cov = np.asarray(big.point(lambda v: 255 if v else 0).resize(half, Image.BOX), np.float32) / 255.0
    hgt, wid = full.shape
    ys, xs = np.nonzero(full > 0)
    x0, x1 = xs.min(), xs.max()
    u = (np.arange(wid) - x0) / max(1, x1 - x0)
    shade = 0.68 + 0.42 * np.sin(np.clip(u, 0, 1) * math.pi) ** 0.8
    hl = np.exp(-((u - 0.32) / 0.05) ** 2) * 0.35
    base = np.array(rgb, dtype=np.float32)
    glaze = base[None, None, :] * shade[None, :, None] + 255 * 0.6 * hl[None, :, None]
    col = np.repeat(glaze, hgt, axis=0)
    col[full == 2] *= 0.55
    leaf = np.array([58, 128, 64], np.float32)[None, None, :] * (0.8 + 0.3 * np.sin(np.arange(hgt) / 9.0))[:, None, None]
    col = np.where((full == 3)[..., None], np.repeat(leaf, wid, axis=1), col)
    # speckles in the glaze (fine detail that an out-of-focus frame loses)
    g = np.random.default_rng(rng.randrange(2 ** 31))
    n = int((full == 1).sum() / 900)
    for i in g.choice(len(ys), size=min(n, len(ys)), replace=False):
        y, x = ys[i], xs[i]
        if full[y, x] != 1:
            continue
        r = int(g.integers(1, 3))
        col[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] *= 0.42
    rgba = np.dstack([np.clip(col, 0, 255), cov * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def backdrop(w: int, h: int) -> np.ndarray:
    """Paper sweep: wall -> curve -> floor, warm grey, with vignette."""
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    t = np.clip((y - 0.5) / 0.28, 0, 1)
    lum = 212 + 28 * (3 * t ** 2 - 2 * t ** 3)
    vig = 1 - 0.10 * (x ** 2) - 0.06 * ((y - 0.6) * 2) ** 2
    lum = lum * vig
    return np.dstack([lum + 3, lum + 1, lum - 4]).astype(np.float32) * np.ones((h, w, 1), np.float32)


def scene(sku: str, portrait: bool, dx: float, dy: float, rng, scale=1.0):
    """Upright frame (PIL RGB, no noise/blur yet) + product box (x0, y0, x1, y1)."""
    w, h = (H, W) if portrait else (W, H)
    name, kind, rgb = SKUS[sku]
    ph = int(HEIGHT[kind] * h * (0.78 if portrait else 1.0) * scale)
    prod = render_product(kind, rgb, ph, rng)
    bb = prod.getchannel("A").point(lambda v: 255 if v > 127 else 0).getbbox()
    prod = prod.crop(bb)
    pw, phh = prod.size
    cx, base = int(w / 2 + dx * w), int(h * (0.80 if not portrait else 0.78) + dy * h)
    x0, y0 = cx - pw // 2, base - phh
    bg = backdrop(w, h)
    # contact shadow
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse((x0 - pw * 0.04, base - phh * 0.05 - 10, x0 + pw * 1.12, base + phh * 0.07 + 12), fill=255)
    sh = np.asarray(sh.filter(ImageFilter.GaussianBlur(28)), np.float32) / 255.0
    bg = bg * (1 - 0.33 * sh)[..., None]
    im = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    im.paste(prod, (x0, y0), prod)
    return im, (x0, y0, x0 + pw, y0 + phh)


def slate_frame(sku: str, rng):
    bg = Image.fromarray(np.clip(backdrop(W, H), 0, 255).astype(np.uint8))
    card = Image.new("RGB", (1000, 640), (247, 247, 244))
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, 999, 639), outline=(200, 200, 196), width=4)
    hand_text(card, (40, 24), "14.10.26   A-cam   Kestrel & Fern", 46, rng, fill=(60, 60, 70))
    hand_text(card, (70, 150), sku, 230, rng, fill=(20, 32, 120), bold=True, jitter=0.06)
    hand_text(card, (80, 470), SKUS[sku][0].replace(" - ", " / "), 64, rng, fill=(20, 32, 120))
    card = card.convert("RGBA").rotate(rng.uniform(-6, 6), expand=True, resample=Image.BICUBIC)
    cx, cy = W // 2 + rng.randint(-120, 120), H // 2 + rng.randint(-60, 60)
    bg.paste(card, (cx - card.size[0] // 2, cy - card.size[1] // 2), card)
    d = ImageDraw.Draw(bg)
    tx, ty = cx + card.size[0] // 2 - 140, cy + card.size[1] // 2 - 70
    d.ellipse((tx, ty, tx + 150, ty + 230), fill=(214, 168, 140))      # thumb + hand holding the card
    d.ellipse((tx + 40, ty + 120, tx + 330, ty + 420), fill=(205, 158, 130))
    return bg.filter(ImageFilter.GaussianBlur(1.2))


def test_frame(kind: str, rng):
    if kind == "black":
        return Image.new("RGB", (W, H), (7, 7, 8))
    bg = Image.fromarray(np.clip(backdrop(W, H), 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(bg)
    d.rectangle((300, 260, 1300, 1360), fill=(119, 119, 117))
    d.rectangle((300, 1360, 1300, 1430), fill=(240, 240, 238))
    d.text((330, 1370), "18% GREY  -  WHITE BALANCE REFERENCE", fill=(40, 40, 40), font=font("sans-bold", 40))
    cols = [(115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177), (103, 189, 170),
            (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108), (157, 188, 64), (224, 163, 46),
            (56, 61, 150), (70, 148, 73), (175, 54, 60), (231, 199, 31), (187, 86, 149), (8, 133, 161),
            (243, 243, 242), (200, 200, 200), (160, 160, 160), (122, 122, 121), (85, 85, 85), (52, 52, 52)]
    d.rectangle((1420, 420, 2160, 940), fill=(30, 30, 30))
    for i, c in enumerate(cols):
        r, q = divmod(i, 6)
        d.rectangle((1440 + q * 120, 440 + r * 122, 1540 + q * 120, 540 + r * 122), fill=c)
    return bg.filter(ImageFilter.GaussianBlur(1.0))


def finish(im: Image.Image, rng, blurred: bool) -> Image.Image:
    if blurred:
        im = im.filter(ImageFilter.GaussianBlur(10))
    return noise(im, rng, 1.6)


def watermark(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    f = font("sans-bold", 40)
    tw = f.getbbox(WATERMARK)[2]
    ImageDraw.Draw(layer).text((im.size[0] - tw - 40, im.size[1] - 84), WATERMARK, font=f, fill=(38, 38, 38, 220))
    return Image.alpha_composite(im, layer).convert("RGB")


# ---------------------------------------------------------------- build
def build(d: str):
    rng = random.Random(20261014)
    os.makedirs(f"{d}/shoot", exist_ok=True)
    os.makedirs(f"{d}/webshop", exist_ok=True)
    frames = []
    num = 4101
    t = dt.datetime(2026, 10, 14, 9, 41, 7)

    def emit(kind, im, sku=None, blurred=False, rot=False, burst=0, box=None, status="reject", subsec=0, last=True):
        nonlocal num, t
        name = f"DSC_{num}.JPG"
        stored = im.transpose(Image.ROTATE_270) if rot else im
        ex = lib_f.exif_bytes(dt=t.strftime("%Y:%m:%d %H:%M:%S"), artist="Tomas Reyes",
                              extra={0x9291: f"{subsec:02d}", 0x829A: (1, 160), 0x829D: (56, 10), 0x8827: 200,
                                     0x920A: (85, 1)})
        lib_f.save_jpeg(stored, f"{d}/shoot/{name}", quality=84, exif=ex)
        frames.append({"name": name, "kind": kind, "sku": sku, "blurred": blurred, "rot": rot, "burst": burst,
                       "status": status, "box": box, "upright_size": list(im.size), "md5": md5(f"{d}/shoot/{name}")})
        if last:  # next frame: the odd frame was deleted in camera; bursts are consecutive, same second
            num += 1 if rng.random() > 0.12 else 2
            t += dt.timedelta(seconds=rng.randint(14, 70))
        else:
            num += 1

    emit("grey", finish(test_frame("grey", rng), rng, False))
    emit("black", noise(test_frame("black", rng), rng, 3.0))
    for sku, shots in SHOTS.items():
        t += dt.timedelta(seconds=rng.randint(90, 300))
        emit("slate", finish(slate_frame(sku, rng), rng, False), sku=sku)
        for tok in shots:
            if tok.startswith("u"):
                dx, dy, sc = rng.uniform(-0.07, 0.07), rng.uniform(-0.02, 0.02), rng.uniform(0.92, 1.05)
                for i in range(int(tok[1:])):
                    im, box = scene(sku, False, dx + i * 0.004, dy + i * 0.002, random.Random(sku), sc)
                    emit("product", finish(im, rng, False), sku=sku, burst=i + 1, box=box,
                         status="keep" if i == 0 else "reject", subsec=i * 25, last=i == int(tok[1:]) - 1)
                continue
            portrait = tok == "r"
            dx, dy, sc = rng.uniform(-0.09, 0.09), rng.uniform(-0.025, 0.02), rng.uniform(0.9, 1.06)
            im, box = scene(sku, portrait, dx, dy, random.Random(sku), sc)
            emit("product", finish(im, rng, tok == "b"), sku=sku, blurred=tok == "b", rot=portrait, box=box,
                 status="reject" if tok == "b" else "keep")
    emit("grey", finish(test_frame("grey", rng), rng, False))
    # an extra copy of a keeper (photographer's card reader double import)
    import shutil
    src = next(f for f in frames if f["sku"] == "KF-221" and f["status"] == "keep" and f["burst"] == 0)
    copy = src["name"].replace(".JPG", " copy.JPG")
    shutil.copy(f"{d}/shoot/{src['name']}", f"{d}/shoot/{copy}")
    frames.append(dict(src, name=copy, kind="copy", status="reject", md5=src["md5"]))
    # keepers' new names in shot order
    for sku in SKUS:
        keep = [f for f in frames if f["sku"] == sku and f["status"] == "keep" and f["kind"] == "product"]
        for i, f in enumerate(keep, 1):
            f["new_name"] = f"{sku}_{i:02d}.jpg"
    # ---- the photographer's workbook
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Shot list"
    ws.append(["File", "SKU", "Status", "New name", "Notes"])
    for f in sorted(frames, key=lambda f: f["name"]):
        ws.append([f["name"], None, None, None, None])
    ws.append([])
    ws.append(["Status: keep / reject.  SKU for slates and product frames.  New name only for keepers."])
    for c in "ABCDE":
        ws[f"{c}1"].font = Font(bold=True)
        ws[f"{c}1"].fill = PatternFill("solid", fgColor="DDE6EE")
    for c, w in zip("ABCDE", (22, 10, 10, 18, 40)):
        ws.column_dimensions[c].width = w
    ws.freeze_panes = "A2"
    ws2 = wb.create_sheet("Web images")
    ws2.append(["SKU", "Product", "Source frame", "Width (px)", "Height (px)", "Notes"])
    ws2.append(["KF-108", "Fjord mug - fog", "DSC_3954.JPG", 1200, 1200, "live since 07/10"])
    for sku in WEB_SKUS:
        ws2.append([sku, SKUS[sku][0], None, None, None, None])
    for c in "ABCDEF":
        ws2[f"{c}1"].font = Font(bold=True)
        ws2[f"{c}1"].fill = PatternFill("solid", fgColor="DDE6EE")
    for c, w in zip("ABCDEF", (10, 30, 22, 12, 12, 24)):
        ws2.column_dimensions[c].width = w
    ws2["A1"].alignment = Alignment(horizontal="left")
    wb.save(f"{d}/shoot/Shoot_2026-10-14.xlsx")
    # ---- last week's web image (reference look)
    im, box = scene("KF-201", False, 0.03, 0.0, random.Random("KF-108"), 1.0)
    im = recolour(im, (128, 160, 118), (150, 166, 184))
    x0, y0, x1, y1 = box
    side = int(max(x1 - x0, y1 - y0) * 1.4)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + int(0.03 * side)
    ref = noise(im.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)).resize((1200, 1200), Image.LANCZOS), rng, 1.2)
    watermark(ref).save(f"{d}/webshop/KF-108.jpg", "JPEG", quality=85)
    # ---- tarball extracted once by setup
    with tarfile.open(f"{d}/shoot.tar.gz", "w:gz") as tf:
        tf.add(f"{d}/shoot", arcname="Shoot_2026-10-14")
    json.dump({"frames": frames, "web_skus": WEB_SKUS, "skus": {k: list(v) for k, v in SKUS.items()},
               "watermark": WATERMARK, "workbook_md5": md5(f"{d}/shoot/Shoot_2026-10-14.xlsx")},
              open(f"{d}/expected.json", "w"), indent=1)


def recolour(im: Image.Image, src_rgb, dst_rgb) -> Image.Image:
    """Swap one glaze colour for another (hue/sat match), keeping the shading."""
    a = np.asarray(im.convert("RGB"), np.float32)
    s = np.array(src_rgb, np.float32)
    lum = a.mean(axis=2, keepdims=True)
    chroma = a - lum
    sc = s - s.mean()
    sim = (chroma * sc).sum(axis=2) / (np.linalg.norm(sc) ** 2 + 1e-6)
    mask = (sim > 0.45)[..., None]
    out = np.where(mask, a / (s + 1) * np.array(dst_rgb, np.float32), a)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
