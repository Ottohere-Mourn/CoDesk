from __future__ import annotations

import argparse
import json
import os
import struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def png_size(path: Path):
    try:
        data = path.read_bytes()[:24]
        if data[:8] != b"\x89PNG\r\n\x1a\n": return None
        return struct.unpack(">II", data[16:24])
    except OSError:
        return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        root = Path(os.environ.get("BC05_PROOF_ROOT", ".")).resolve()
        out = root / "out"
        if urlparse(self.path).path == "/api/receipt":
            rows = {}
            for name in ("product_clean.png", "campaign_final.png"):
                path = out / name
                size = png_size(path)
                rows[name] = {"exists": path.is_file(), "size": list(size) if size else None}
            body = json.dumps({"schema": "bc05-proof/v1", "files": rows}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        html = """<!doctype html><meta charset=utf-8><title>Campaign Proof Desk</title>
        <style>body{font:16px sans-serif;background:#eee}main{display:flex;gap:20px}figure{background:white;padding:12px}img{width:360px;max-height:480px;object-fit:contain}</style>
        <h1>Q4 Campaign Proof Desk</h1><main><figure><h2>Clean product visual</h2><img src='/out/product_clean.png'></figure>
        <figure><h2>Complete campaign</h2><img src='/out/campaign_final.png'></figure></main>"""
        if urlparse(self.path).path == "/proof.html":
            body = html.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body); return
        if self.path.startswith("/out/"):
            name = Path(urlparse(self.path).path).name
            if name not in {"product_clean.png", "campaign_final.png"}:
                self.send_error(404); return
            path = out / name
            try: body = path.read_bytes()
            except OSError: self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.end_headers(); self.wfile.write(body); return
        self.send_error(404)

    def log_message(self, *_): pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8091)
    ThreadingHTTPServer(("127.0.0.1", parser.parse_args().port), Handler).serve_forever()
