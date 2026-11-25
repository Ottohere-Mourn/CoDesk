"""Authenticated MetricPulse and AssetHub sites for CONC-06."""
from __future__ import annotations
import argparse, csv, io, json, secrets, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

COMBOS = {
    "NA-Q3": [420000, 385000, 410000, 442000],
    "EU-Q3": [321000, 309000, 330000, 358000],
    "APAC-Q4": [550000, 530000, 580000, 602000],
    "LATAM-Q4": [200000, 216000, 228000, 240000],
}
ASSETS = ("Summit_Keynote", "Summit_TrackA", "Summit_TrackB", "Summit_Roadmap")

A_PAGE = '''<!doctype html><meta charset="utf-8"><title>MetricPulse | Regional BI</title>
<style>body{font:16px Arial;margin:24px;background:#f4f7fb;color:#19334a}header{padding:18px;background:#173b5a;color:white;border-radius:10px}main{display:grid;grid-template-columns:340px 1fr;gap:20px;margin-top:20px}.card{background:white;padding:18px;border:1px solid #d8e1ea;border-radius:10px}select,button{font-size:15px;padding:9px;margin:6px 4px}img{width:min(100%,900px);height:auto}#msg{color:#176b87}</style>
<header><h1>MetricPulse Business Intelligence</h1><div>Quarterly performance review</div></header>
<main><section class="card"><label>Region <select id="region"><option>NA</option><option>EU</option><option>APAC</option><option>LATAM</option></select></label><label>Quarter <select id="quarter"><option>Q1</option><option>Q2</option><option>Q3</option><option>Q4</option></select></label><p id="combo"></p><button id="csv">Export CSV</button><button id="png">Export Chart PNG</button><p id="msg">Choose a region and quarter, then inspect the chart.</p></section><section class="card"><img id="chart" alt="Quarterly commercial performance chart"></section></main>
<script>
const region=document.querySelector('#region'),quarter=document.querySelector('#quarter'),img=document.querySelector('#chart'),combo=document.querySelector('#combo');let current='NA-Q3';
function refresh(){current=region.value+'-'+quarter.value;combo.textContent='Report: '+current;img.src='/a/chart-view.png?combo='+encodeURIComponent(current)+'&v='+Date.now();fetch('/api/event?role=a&type=filter&combo='+encodeURIComponent(current));}
region.onchange=refresh;quarter.onchange=refresh;document.querySelector('#csv').onclick=()=>location.href='/a/report.csv?combo='+encodeURIComponent(current);document.querySelector('#png').onclick=()=>location.href='/a/chart.png?combo='+encodeURIComponent(current);refresh();
</script>'''

B_PAGE = '''<!doctype html><meta charset="utf-8"><title>AssetHub | Summit Library</title>
<style>body{font:16px Arial;margin:24px;background:#f5f7fa;color:#19334a}header{padding:18px;background:#284f68;color:white;border-radius:10px}main{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}.card{background:white;padding:15px;border:1px solid #d8e1ea;border-radius:10px}.card img{width:100%;height:300px;object-fit:contain}.card button{font-size:15px;padding:9px 13px;background:#176b87;color:white;border:0;border-radius:5px}</style>
<header><h1>AssetHub Summit Library</h1><div>Download the four approved 2026 summit graphics.</div></header><main>__CARDS__</main>'''

class State:
    def __init__(self, assets: Path, state_path: Path):
        self.assets, self.state_path = assets, state_path
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.data = {"a_events": [], "b_events": [], "download_events": []}
    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def send(self, body: bytes, ctype="text/html; charset=utf-8", code=200, download=None):
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
            self.send_header("Set-Cookie", f"conc06_session={state.token}; HttpOnly; SameSite=Lax; Path=/")
            if download: self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def ok(self): return f"conc06_session={state.token}" in self.headers.get("Cookie", "")
        def event(self, role, item):
            with state.lock:
                (state.data["a_events"] if role == "a" else state.data["b_events"]).append(item)
                state.save()
        def do_GET(self):
            from urllib.parse import parse_qs, urlsplit
            u=urlsplit(self.path); path=u.path; q=parse_qs(u.query)
            if path == "/health": return self.send(b"ok", "text/plain")
            if not self.ok(): return self.send(b"authentication required", "text/plain", 401)
            port=self.server.server_port
            if port == 18121 and path == "/": return self.send(A_PAGE.encode())
            if port == 18122 and path == "/":
                cards="".join(f'<section class="card"><h2>{n.replace("_"," ")}</h2><img src="/b/preview/{n}.png" alt="{n} summit graphic"><p><button onclick="location.href=\'/b/download/{n}.png\'">Download PNG</button></p></section>' for n in ASSETS)
                return self.send(B_PAGE.replace("__CARDS__",cards).encode())
            if path == "/api/event":
                role=q.get("role",[""])[0];kind=q.get("type",[""])[0]
                if role not in {"a","b"}: return self.send(b"bad role","text/plain",400)
                self.event(role,{"type":kind,"combo":q.get("combo",[None])[0]})
                return self.send(b"ok","text/plain")
            if port == 18121 and path in {"/a/report.csv","/a/chart.png","/a/chart-view.png"}:
                combo=q.get("combo",[""])[0]
                if combo not in COMBOS: return self.send(b"unknown report","text/plain",404)
                if path == "/a/report.csv":
                    b=io.StringIO(newline="");w=csv.writer(b,lineterminator="\n");w.writerow(["period","revenue"]);w.writerows((f"Month-{i+1}",v) for i,v in enumerate(COMBOS[combo]))
                    self.event("a",{"type":"download","kind":"csv","combo":combo,"filename":"report.csv"})
                    return self.send(b.getvalue().encode(),"text/csv; charset=utf-8",download="report.csv")
                image=(state.assets/f"{combo}.png").read_bytes()
                if path == "/a/chart-view.png": return self.send(image,"image/png")
                self.event("a",{"type":"download","kind":"bi_chart","combo":combo,"filename":"chart.png"})
                return self.send(image,"image/png",download="chart.png")
            if port == 18122 and path.startswith("/b/"):
                parts=path.strip("/").split("/")
                if len(parts)==3 and parts[1] in {"preview","download"} and parts[2].endswith(".png"):
                    name=parts[2][:-4]
                    if name not in ASSETS:return self.send(b"not found","text/plain",404)
                    image=(state.assets/f"{name}.png").read_bytes()
                    if parts[1]=="download":
                        self.event("b",{"type":"download","kind":"summit_asset","name":name,"filename":"chart.png"})
                        return self.send(image,"image/png",download="chart.png")
                    return self.send(image,"image/png")
            return self.send(b"not found","text/plain",404)
    return Handler

def serve(assets: Path, state_path: Path):
    state=State(assets,state_path);handler=make_handler(state)
    servers=[ThreadingHTTPServer(("127.0.0.1",port),handler) for port in (18121,18122)]
    workers=[threading.Thread(target=s.serve_forever,daemon=True) for s in servers]
    [t.start() for t in workers];[t.join() for t in workers]

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--assets",type=Path,required=True);p.add_argument("--state",type=Path,default=Path("/tmp/conc06-runtime/state.json"));a=p.parse_args();serve(a.assets,a.state)
