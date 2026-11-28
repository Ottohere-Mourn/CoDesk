"""Local loopback preview and crop endpoints for BC-04."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def extract_fragment(source: Path, fragment_id: str, view_box: str, width: int, height: int) -> bytes:
    tree = ET.parse(source)
    root = tree.getroot()
    fragment = root.find(f".//*[@id='{fragment_id}']")
    if fragment is None:
        raise FileNotFoundError(f"Missing SVG group {fragment_id}")
    exported = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(width), "height": str(height), "viewBox": view_box,
        "version": "1.1",
    })
    exported.append(fragment)
    return ET.tostring(exported, encoding="utf-8", xml_declaration=True)


def handler_for(root: Path):
    class PreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def do_GET(self):
            path = urlparse(self.path).path
            source = root / "brand" / "launch_board.svg"
            if path == "/hero.svg":
                self._svg(extract_fragment(source, "hero-banner", "0 0 1600 560", 1600, 560))
                return
            if path == "/pricing.svg":
                self._svg(extract_fragment(source, "pricing-section", "100 620 1400 360", 1400, 360))
                return
            return super().do_GET()

        def _svg(self, payload: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            pass

    return PreviewHandler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.home() / "workspace/bc04")
    parser.add_argument("--port", type=int, default=8094)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(args.root.expanduser().resolve())).serve_forever()


if __name__ == "__main__":
    main()
