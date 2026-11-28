"""Create the English BC-04 Guest workspace and editable SVG seed."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


SEED_SVG = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000">
  <g id="hero-banner"><rect id="hero-background" x="0" y="0" width="1600" height="560" fill="#20334A"/><rect id="hero-accent" x="0" y="530" width="1600" height="30" fill="#D89B3C"/><text id="hero-title" x="150" y="230" font-family="DejaVu Sans" font-size="78" font-weight="bold" fill="#FFFFFF">PRODUCT LAUNCH</text><text id="hero-subtitle" x="154" y="310" font-family="DejaVu Sans" font-size="34" fill="#E7EDF2">Tools for teams</text><g id="brand-mark" transform="translate(72,72)"><circle cx="0" cy="0" r="24" fill="#D89B3C"/><path d="M-11 0 L-2 9 L14 -10" fill="none" stroke="#20334A" stroke-width="6"/></g></g>
  <g id="pricing-section"><rect id="pricing-background" x="100" y="620" width="1400" height="360" rx="18" fill="#F4F6F8"/><g id="card-starter"><rect x="135" y="660" width="400" height="280" rx="14" fill="#FFFFFF" stroke="#CFD7DE" stroke-width="2"/><text id="starter-title" x="180" y="730" font-family="DejaVu Sans" font-size="28" fill="#253748">Starter</text><text id="starter-price" x="180" y="805" font-family="DejaVu Sans" font-size="34" fill="#253748">$15 / month</text></g>
  <g id="card-growth"><rect x="600" y="660" width="400" height="280" rx="14" fill="#FFFFFF" stroke="#CFD7DE" stroke-width="2"/><rect id="growth-highlight" x="600" y="660" width="400" height="280" rx="14" fill="none" stroke="#CFD7DE" stroke-width="2"/><text id="growth-title" x="650" y="730" font-family="DejaVu Sans" font-size="28" fill="#253748">Growth</text><text id="growth-price" x="650" y="805" font-family="DejaVu Sans" font-size="34" fill="#253748">$49 / month</text><rect x="650" y="845" width="180" height="40" rx="10" fill="#EDF1F4"/><text id="growth-badge" x="666" y="872" font-family="DejaVu Sans" font-size="16" fill="#253748">POPULAR PLAN</text></g>
  <g id="card-scale"><rect x="1065" y="660" width="400" height="280" rx="14" fill="#FFFFFF" stroke="#CFD7DE" stroke-width="2"/><text id="scale-title" x="1110" y="730" font-family="DejaVu Sans" font-size="28" fill="#253748">Scale</text><text id="scale-price" x="1110" y="805" font-family="DejaVu Sans" font-size="34" fill="#253748">$129 / month</text></g></g>
</svg>
'''

PREVIEW_HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Launch Board Preview</title><style>body{margin:0;background:#dce3e8;font:16px sans-serif}.board{display:block;width:min(100%,1280px);height:auto;margin:24px auto;background:white;box-shadow:0 8px 30px #66778855}</style></head><body><img class="board" src="/brand/launch_board.svg" alt="Launch board preview"></body></html>'''


def prepare(workspace: Path, source: Path) -> Path:
    root = workspace.expanduser().resolve()
    brand = root / "brand"
    output = root / "out"
    brand.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    (brand / "launch_board.svg").write_text(SEED_SVG, encoding="utf-8")
    (root / "preview.html").write_text(PREVIEW_HTML, encoding="utf-8")
    shutil.copy2(source / "board_service.py", root / "board_service.py")
    (root / "README.txt").write_text(
        "Local SVG preview: http://127.0.0.1:8094/preview.html\n"
        "Hero crop: http://127.0.0.1:8094/hero.svg\n"
        "Pricing crop: http://127.0.0.1:8094/pricing.svg\n",
        encoding="utf-8",
    )
    return root


def start(root: Path, port: int = 8094) -> subprocess.Popen:
    log = (root / "preview.log").open("ab")
    process = subprocess.Popen(
        [sys.executable, str(root / "board_service.py"), "--root", str(root), "--port", str(port)],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("BC-04 preview service exited during startup")
            try:
                with urlopen(f"http://127.0.0.1:{port}/preview.html", timeout=1) as response:
                    if response.status == 200:
                        return process
            except OSError:
                time.sleep(0.2)
        raise TimeoutError("BC-04 preview service did not become ready")
    except Exception:
        process.terminate()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.home() / "workspace/bc04")
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--start-service", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    root = prepare(args.workspace, args.source_dir)
    if args.start_service:
        start(root)
    if args.open_browser:
        subprocess.Popen(["google-chrome", "--new-window", "http://127.0.0.1:8094/preview.html"], start_new_session=True)
    print(f"Prepared BC-04 workspace at {root}")


if __name__ == "__main__":
    main()
