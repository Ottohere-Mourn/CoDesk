from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path


def _minimal_pdf(path: Path, lines: list[str]) -> None:
    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = ["BT", "/F1 10 Tf", "48 748 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -14 Td")
        commands.append(f"({esc(line[:105])}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)


def _make_ora(path: Path) -> None:
    from PIL import Image, ImageDraw

    names = ["bg_base", "slot_1", "slot_2", "slot_3", "promo_badge", "price_grid", "legal_footer"]
    colors = [(244, 239, 227, 255), (220, 220, 220, 0), (220, 220, 220, 0),
              (220, 220, 220, 0), (218, 70, 47, 220), (32, 48, 70, 210), (32, 48, 70, 220)]
    stack = []
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        for index, (name, color) in enumerate(zip(names, colors)):
            image = Image.new("RGBA", (1200, 1600), color)
            draw = ImageDraw.Draw(image)
            if name == "bg_base":
                draw.rectangle((40, 40, 1160, 1560), outline=(42, 55, 73, 255), width=8)
                draw.text((70, 75), "Q4 PRODUCT CAMPAIGN", fill=(32, 48, 70, 255))
            elif name.startswith("slot_"):
                x = 110 + 350 * (int(name[-1]) - 1)
                draw.rectangle((x, 380, x + 300, 720), outline=(70, 90, 110, 255), width=5)
                draw.text((x + 30, 530), f"PRODUCT SLOT {name[-1]}", fill=(32, 48, 70, 255))
            else:
                draw.text((80, 900 + 100 * index), name.upper(), fill=(255, 255, 255, 255))
            buffer = __import__("io").BytesIO()
            image.save(buffer, format="PNG")
            layer_path = f"data/layer{index}.png"
            archive.writestr(layer_path, buffer.getvalue())
            stack.append(f'<layer name="{name}" src="{layer_path}" opacity="1.0" visibility="visible" composite-op="svg:src-over" x="0" y="0"/>')
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<image version="0.0.1" w="1200" h="1600" name="Q4 Campaign"><stack>'
               + "".join(reversed(stack)) + "</stack></image>")
        archive.writestr("stack.xml", xml)
        merged = __import__("io").BytesIO()
        Image.new("RGBA", (1200, 1600), (244, 239, 227, 255)).save(merged, format="PNG")
        archive.writestr("mergedimage.png", merged.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--start-service", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--open-gimp", action="store_true")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    root = workspace / "campaign"
    assets = root / "assets"
    out = workspace / "out"
    assets.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    db_path = root / "sku_catalog.db"
    db = sqlite3.connect(db_path)
    db.executescript("DROP TABLE IF EXISTS skus; DROP TABLE IF EXISTS promotions; CREATE TABLE skus(sku_id TEXT PRIMARY KEY,status TEXT,region_scope TEXT,stock_qty INTEGER,margin_pct REAL); CREATE TABLE promotions(promo_code TEXT PRIMARY KEY,active INTEGER,channel TEXT,expiry_date TEXT,priority INTEGER,discount_pct INTEGER,disclaimer_id TEXT,base_price REAL);")
    rows = []
    for i in range(1, 26):
        sku = f"SKU-{100+i:03d}"
        margin = round(.25 + ((i * 11) % 30) / 100, 2)
        status = "ACTIVE" if i not in (3, 8) else "INACTIVE"
        region = "GLOBAL" if i % 5 else "EU"
        stock = 80 if i % 7 else 21
        rows.append((sku, status, region, stock, margin))
    db.executemany("INSERT INTO skus VALUES(?,?,?,?,?)", rows)
    promos = []
    for i in range(1, 9):
        code = f"PROMO-{500+i}"
        active = 0 if i % 6 == 0 else 1
        channel = "WEB_ONLY" if i % 4 == 0 else "RETAIL_Q4"
        expiry = "2026-11-30" if i % 7 == 0 else "2026-12-20"
        priority = (i * 7) % 8 + 1
        discount = i * 3 + 10
        promos.append((code,active,channel,expiry,priority,discount,f"DISC-{discount}",79.99))
    db.executemany("INSERT INTO promotions VALUES(?,?,?,?,?,?,?,?)", promos)
    db.commit(); db.close()
    from PIL import Image, ImageDraw
    for i in range(1, 26):
        sku = f"SKU-{100+i:03d}"
        image = Image.new("RGBA", (240 + i * 7, 300 + i * 9), (225, 235, 244, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((30, 30, image.width - 30, image.height - 30), fill=(40 + i * 13, 90 + i * 8, 135 + i * 6, 255))
        draw.text((40, image.height // 2), sku, fill=(255, 255, 255, 255))
        image.save(assets / f"{sku}.png")
    _make_ora(root / "poster_master.ora")
    _minimal_pdf(root / "brand_spec.pdf", [
        "Q4 BRAND SPECIFICATION - REV 4", "Eligible hero SKU: ACTIVE, GLOBAL or NA, stock >= 50, margin >= 0.35.",
        "Rank by margin descending then sku_id ascending; use the first three.",
        "Fit each product inside a 320 x 320 safe box with contain scaling and center alignment.",
        "Clean visual must hide promo_badge, price_grid and legal_footer; canvas is 1200 x 1600.",
        "Retail Q4 promo: active=1, channel=RETAIL_Q4, expiry_date >= 2026-12-15; choose lowest priority.",
        "Discount headline uses percent discount. DISC-25 requires the exact footer: Offers end Dec 31, 2026. While supplies last.",
        "Use highlight color #D9462F. Show calculated price to two decimals; never alter the background.",
    ])
    if args.start_service:
        env = dict(os.environ); env["BC05_PROOF_ROOT"] = str(workspace)
        log = open(root / "proof_service.log", "ab", buffering=0)
        subprocess.Popen([sys.executable, str(Path(args.source_dir) / "proof_service.py"), "--port", "8091"],
                         cwd=str(root), env=env, stdout=log, stderr=log, start_new_session=True)
    if args.open_gimp:
        subprocess.Popen(["gimp", str(root / "poster_master.ora")], start_new_session=True)
    if args.open_browser:
        subprocess.Popen(["google-chrome", "http://127.0.0.1:8091/proof.html"], start_new_session=True)


if __name__ == "__main__": main()
