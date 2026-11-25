"""Build English, deterministic chart fixtures for CONC-04."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TITLES = ["CPU Load", "API Latency", "Memory Usage", "Request Throughput"]
COLORS = ["#3949AB", "#00838F", "#6A1B9A", "#EF6C00"]


def _font(size=14):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_chart(index: int, path: Path) -> None:
    w, h = 960, 540
    im = Image.new("RGB", (w, h), "#fbfcfe")
    d = ImageDraw.Draw(im)
    ink, grid, axis = "#344054", "#e7ebf0", "#8993a1"
    d.text((32, 18), TITLES[index], fill="#172b4d", font=_font(23))
    d.text((32, 47), "Operational telemetry - last 60 minutes", fill="#667085", font=_font(12))
    left, top, right, bottom = 88, 92, 920, 458
    for j in range(6):
        y = top + (bottom - top) * j / 5
        d.line((left, y, right, y), fill=grid, width=1)
        d.text((35, y - 7), f"{100-j*20}", fill="#667085", font=_font(11))
    for j in range(7):
        x = left + (right - left) * j / 6
        d.line((x, top, x, bottom), fill=grid, width=1)
        d.text((x - 17, bottom + 12), f"{j*10:02d}m", fill="#667085", font=_font(10))
    d.line((left, top, left, bottom), fill=axis, width=2)
    d.line((left, bottom, right, bottom), fill=axis, width=2)
    # A deliberately visible threshold line provides a normal operational reference.
    threshold = top + 0.30 * (bottom - top)
    for x in range(left, right, 14):
        d.line((x, threshold, min(x + 7, right), threshold), fill="#d97706", width=2)
    color = ["#3155a6", "#087e8b", "#7851a9", "#ce6a15"][index]
    points = []
    for i in range(241):
        x = left + (right - left) * i / 240
        base = 0.56 + 0.08 * math.sin(i * 0.12 + index) + 0.035 * math.sin(i * 0.43 + 1.2)
        # Four distinct, unmistakable but naturally embedded event shapes.
        if index == 0 and 54 <= i <= 62:
            base = 0.10 + (abs(i - 58) / 4) * 0.06
        if index == 0 and 158 <= i <= 183:
            base = 0.47
        if index == 1 and 78 <= i <= 91:
            base = 0.92 - 0.015 * math.sin(i)
        if index == 1 and 174 <= i <= 182:
            base = 0.08 + abs(i - 178) * 0.12
        if index == 2 and 46 <= i <= 72:
            base = 0.39
        if index == 2 and 154 <= i <= 166:
            base = 0.95 - abs(i - 160) * 0.03
        if index == 3 and 105 <= i <= 113:
            base = 0.09 + abs(i - 109) * 0.13
        if index == 3 and 191 <= i <= 216:
            base = 0.82
        y = top + base * (bottom - top)
        points.append((x, y))
    d.line(points, fill=color, width=3, joint="curve")
    d.ellipse((right - 4, points[-1][1] - 4, right + 4, points[-1][1] + 4), fill=color)
    d.line((742, 64, 770, 64), fill=color, width=3)
    d.text((778, 56), "Observed", fill=ink, font=_font(12))
    for x in range(742, 770, 10):
        d.line((x, 78, x + 5, 78), fill="#d97706", width=2)
    d.text((778, 70), "Alert threshold", fill=ink, font=_font(12))
    im.save(path, format="PNG", optimize=True)


def build(destination: Path) -> Path:
    out = Path(destination) / "CONC-04" / "guest" / "in_b" / "charts"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        draw_chart(i, out / f"chart_{i + 1}.png")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("destination", type=Path)
    print(build(ap.parse_args().destination))
