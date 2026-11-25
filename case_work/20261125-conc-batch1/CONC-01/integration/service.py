#!/usr/bin/env python3
"""English-only local responsive-QA and operations-telemetry web services."""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import secrets
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import fcntl
except ImportError:  # local Windows unit tests use the process-local lock
    fcntl = None

_FALLBACK_LOCK = threading.Lock()

COOKIE = "conc01_session"
SESSION = "local-review-session-v1"
STATE = Path("/tmp/conc01-runtime/state.json")
STATE_LOCK = Path("/tmp/conc01-runtime/state.lock")
WORKSPACE = Path(os.environ.get("CONC01_WORKSPACE", "/home/user/workspace"))
TABS = {"tab_1": "CPU", "tab_2": "GPU", "tab_3": "Network", "tab_4": "Disk", "tab_5": "Queue", "tab_6": "Latency"}
TAB_COLORS = {"tab_1": "#1E88E5", "tab_2": "#8E24AA", "tab_3": "#FB8C00", "tab_4": "#43A047", "tab_5": "#00ACC1", "tab_6": "#F4511E"}
TEAL = "#00BFA5"
RED = "#D32F2F"


def _decode_png_data_url(value):
    """Decode a browser-generated PNG and return bytes plus IHDR dimensions."""
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,"):
        raise ValueError("expected a PNG data URL")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid PNG base64") from exc
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    width, height = struct.unpack(">II", raw[16:24])
    if width < 1 or height < 1 or width > 4096 or height > 4096:
        raise ValueError("PNG dimensions outside supported range")
    return raw, width, height


def _latest_checks(state):
    rows = {}
    for row in state.get("a_checks", []):
        band = row.get("band")
        if band in ("mobile", "tablet", "desktop"):
            rows[band] = row
    return rows


def _build_a_report(state):
    latest = _latest_checks(state)
    if set(latest) != {"mobile", "tablet", "desktop"}:
        raise ValueError("record all three viewport checks before exporting")
    report = {}
    for band in ("mobile", "tablet", "desktop"):
        row = latest[band]
        ids = sorted(set(str(x) for x in row.get("bug_element_ids", [])))
        report[band] = {"has_bug": bool(ids),
                        "bug_element_id": ", ".join(ids) if ids else "NONE",
                        "badge_code": str(row.get("badge_code", ""))}
    return report


def _build_b_report(state):
    observed = {(row.get("tab"), row.get("peak")) for row in state.get("b_hovers", [])
                if int(row.get("width", 0)) >= 1860 and int(row.get("height", 0)) >= 950}
    required = {(tab, peak) for tab in TABS for peak in ("peak_a", "peak_b")}
    if not required <= observed:
        raise ValueError("inspect both peaks in every tab before exporting")
    return {tab: {"peak_a": state["peaks"][tab]["peak_a"],
                  "peak_b": state["peaks"][tab]["peak_b"]} for tab in TABS}


def _save_browser_png(actor, name, body):
    """Save a browser GUI evidence export into the fixed actor output folder."""
    raw, width, height = _decode_png_data_url(body.get("png_data"))
    if actor == "a":
        band = body.get("band")
        allowed = {"mobile": (355, 395, "qa_375.png"),
                   "tablet": (748, 788, "qa_768.png"),
                   "desktop": (1415, 1465, "qa_1440.png")}
        if band not in allowed:
            raise ValueError("unknown viewport band")
        low, high, filename = allowed[band]
        check = _latest_checks(read_state()).get(band)
        if not check or not low <= int(check.get("width", 0)) <= high:
            raise ValueError("record this viewport check before saving its evidence")
        if not low <= width <= high:
            raise ValueError("evidence PNG width does not match the recorded viewport band")
        target = WORKSPACE / "out_a" / filename
    else:
        tab = body.get("tab")
        if tab not in TABS:
            raise ValueError("unknown telemetry tab")
        state = read_state()
        observed = {(row.get("tab"), row.get("peak")) for row in state.get("b_hovers", [])
                    if int(row.get("width", 0)) >= 1860 and int(row.get("height", 0)) >= 950}
        if not {(tab, "peak_a"), (tab, "peak_b")} <= observed:
            raise ValueError("inspect both highlighted peaks before saving this tab")
        if width < 1860 or height < 950:
            raise ValueError("evidence PNG must show the full Guest desktop viewport")
        index = list(TABS).index(tab) + 1
        target = WORKSPACE / "out_b" / f"ops_tab_{index}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return target.name, width, height


def fresh_state():
    return {
        "a_controls": [], "a_checks": [], "b_hovers": [],
        "badges": {}, "peaks": {
            tab: {"peak_a": round(10 + secrets.randbelow(90000) / 1000, 3),
                  "peak_b": round(10 + secrets.randbelow(90000) / 1000, 3)}
            for tab in TABS
        },
    }


def update_state(fn):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        with _FALLBACK_LOCK:
            return _update_state_locked(fn)
    with STATE_LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _update_state_locked(fn)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _update_state_locked(fn):
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = fresh_state()
    result = fn(data)
    STATE.write_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
    return result


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return update_state(lambda data: data)


def a_html():
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Northstar Checkout - Responsive QA</title>
<style>
*{{box-sizing:border-box}} body{{font:16px Arial,sans-serif;margin:0;background:#f1f4f8;color:#15243a}}
header{{padding:22px 28px;background:#173b63;color:white}} main{{max-width:1000px;margin:24px auto;background:white;padding:28px;border-radius:12px;position:relative}}
#qa-band{{position:absolute;right:0;top:0;width:120px;height:24px;background:{TEAL}}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .card{{border:1px solid #c9d4e1;padding:18px;border-radius:8px;min-height:92px}}
label{{display:block;margin-bottom:8px}} select,input,button{{font-size:16px;padding:9px;border:1px solid #8092a6;border-radius:5px}}
button{{background:#176f9f;color:white;cursor:pointer;margin:8px 4px 0 0}} #checkout{{position:relative;min-height:260px}}
#promo-banner{{background:#fff3cd;padding:12px}} #cart-total{{background:#e8f2ff;padding:12px}}
#express-box{{position:relative;padding:12px;background:#edf7ef;margin-top:14px}} #btn-express-pay{{background:#13764b}}
#badge{{margin-top:15px;font-weight:bold;font-size:20px;color:#8a2d78}} #status{{min-height:26px;margin-top:12px;color:#175d45}}
@media(max-width:500px){{#btn-express-pay{{position:absolute;left:calc(100% + 14px);top:12px}} #checkout{{overflow:visible}}}}
@media(min-width:600px) and (max-width:1000px){{#checkout{{min-height:290px}} #promo-banner{{position:absolute;left:60px;top:110px;width:45%;height:70px}} #cart-total{{position:absolute;left:72px;top:137px;width:50%;height:70px}}}}
</style></head><body><header><h1>Northstar Commerce - Checkout QA</h1><div>Release candidate 6.4 | Browser validation workspace</div></header>
<main id="checkout"><div id="qa-band"></div><h2>Responsive transaction review</h2><div class="grid">
<div class="card"><label for="shipping">Delivery method</label><select id="shipping"><option value="standard">Standard · 3–5 days</option><option value="express">Express · 1–2 days</option><option value="pickup">Store pickup</option></select><button id="apply" onclick="control('delivery',document.querySelector('#shipping').value)">Apply delivery</button></div>
<div class="card"><label for="promo">Promotion code</label><input id="promo" value="NORTHSTAR10"><button id="promo-apply" onclick="control('promotion',document.querySelector('#promo').value)">Apply promotion</button></div>
<div class="card" id="promo-banner">Member offer: free delivery above $75</div><div class="card" id="cart-total">Order total: $128.40 · Estimated tax pending</div>
</div><div id="express-box"><button id="btn-express-pay" onclick="control('tax','recalculate')">Recalculate tax</button></div>
<button id="record" onclick="recordCheck()">Record Viewport Check</button><div id="badge"></div><div id="status"></div>
<div class="evidence-tools"><button id="save-viewport-evidence" onclick="saveViewportEvidence()">Save viewport PNG</button><button id="export-qa-report" onclick="exportQaReport()">Export QA report JSON</button></div><div id="evidence-status" role="status"></div>
<p>Record one complete checkout validation at each target browser window width.</p></main>
<script>
async function control(name,value){{let r=await fetch('/api/control',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name,value,width:window.outerWidth,height:window.outerHeight}})}});document.querySelector('#status').textContent=(await r.json()).message}}
function inspectLayout(){{let ids=[];let pay=document.querySelector('#btn-express-pay').getBoundingClientRect(),parent=document.querySelector('#express-box').getBoundingClientRect();if(pay.right>parent.right+1)ids.push('btn-express-pay');let p=document.querySelector('#promo-banner').getBoundingClientRect(),c=document.querySelector('#cart-total').getBoundingClientRect();if(p.left<c.right&&p.right>c.left&&p.top<c.bottom&&p.bottom>c.top)ids.push('promo-banner','cart-total');return [...new Set(ids)]}}
async function recordCheck(){{let id=inspectLayout();let band=window.outerWidth<500?'mobile':(window.outerWidth<1000?'tablet':'desktop');let r=await fetch('/api/record',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{band,width:window.outerWidth,height:window.outerHeight,bug_element_ids:id}})}});let x=await r.json();document.querySelector('#badge').textContent='Validation code: '+x.badge_code;document.querySelector('#status').textContent=x.message}}
async function viewportPngData(){{
 const sourceW=window.innerWidth,sourceH=window.innerHeight,outputW=window.outerWidth,outputH=window.outerHeight;
 const clone=document.documentElement.cloneNode(true);clone.querySelectorAll('script').forEach(x=>x.remove());
 const originals=[...document.querySelectorAll('canvas')],copies=[...clone.querySelectorAll('canvas')];
 copies.forEach((node,i)=>{{const img=clone.ownerDocument.createElement('img');img.src=originals[i].toDataURL('image/png');img.width=originals[i].width;img.height=originals[i].height;node.replaceWith(img)}});
 const source=[...document.querySelectorAll('input,textarea,select')],target=[...clone.querySelectorAll('input,textarea,select')];
 target.forEach((node,i)=>{{if(node.tagName==='SELECT'){{[...node.options].forEach((option,j)=>{{option.selected=source[i].selectedIndex===j}})}}else node.setAttribute('value',source[i].value)}});
 clone.setAttribute('xmlns','http://www.w3.org/1999/xhtml');const markup=new XMLSerializer().serializeToString(clone);
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${{sourceW}}" height="${{sourceH}}"><foreignObject width="100%" height="100%">${{markup}}</foreignObject></svg>`;
 const url=URL.createObjectURL(new Blob([svg],{{type:'image/svg+xml;charset=utf-8'}}));
 try{{const img=new Image();await new Promise((resolve,reject)=>{{img.onload=resolve;img.onerror=reject;img.src=url}});const canvas=document.createElement('canvas');canvas.width=outputW;canvas.height=outputH;const ctx=canvas.getContext('2d');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,outputW,outputH);ctx.drawImage(img,0,0,outputW,outputH);return canvas.toDataURL('image/png')}}finally{{URL.revokeObjectURL(url)}}
}}
async function saveViewportEvidence(){{const band=window.outerWidth<500?'mobile':(window.outerWidth<1000?'tablet':'desktop');const status=document.querySelector('#evidence-status');try{{const png_data=await viewportPngData();const r=await fetch('/api/export/a/screenshot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{band,png_data}})}});const x=await r.json();status.textContent=r.ok?`Saved ${{x.filename}} (${{x.width}}x${{x.height}}).`:x.error}}catch(e){{status.textContent='Evidence export failed: '+e.message}}}}
async function exportQaReport(){{const status=document.querySelector('#evidence-status');const r=await fetch('/api/export/a/report',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});const x=await r.json();status.textContent=r.ok?`Saved ${{x.filename}}.`:(x.error||'Report export failed.')}}
</script></body></html>'''


def b_html():
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Northstar Operations Telemetry</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#eef2f6;color:#172b3e;font:16px Arial,sans-serif}}header{{background:#142e46;color:white;padding:18px 26px}}main{{max-width:1500px;margin:16px auto;padding:16px;background:white;border-radius:10px;position:relative}}#color-band{{position:absolute;right:0;top:0;width:120px;height:24px}}nav{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}nav button{{padding:12px 18px;border:0;border-radius:5px;background:#dce6ef;font-size:16px;cursor:pointer}}nav button.active{{background:#1d577a;color:#fff}}#plot{{width:100%;height:620px;border:1px solid #d4dee8;display:block}}#tip{{position:fixed;background:#172b3e;color:white;padding:10px 14px;border-radius:6px;display:none;z-index:20}}#overlay{{position:fixed;inset:0;background:{RED};color:white;z-index:99;display:none;align-items:center;justify-content:center;font-size:36px;font-weight:bold;text-align:center}}.hint{{color:#536779}}</style></head><body><div id="overlay">VIEWPORT TOO NARROW — MAXIMIZE CHROME TO 1920x1080</div><header><h1>Northstar Operations — Live Telemetry</h1><div>Production service health · Hover both highlighted peaks in each chart</div></header><main><div id="color-band"></div><h2 id="title">CPU</h2><nav id="tabs"></nav><canvas id="plot" width="1800" height="620"></canvas><p class="hint">Peak A and Peak B values appear only while the corresponding point is inspected.</p></main><div id="tip"></div>
<script>
const names={{tab_1:'CPU',tab_2:'GPU',tab_3:'Network',tab_4:'Disk',tab_5:'Queue',tab_6:'Latency'}};
const colors={{tab_1:'#1E88E5',tab_2:'#8E24AA',tab_3:'#FB8C00',tab_4:'#43A047',tab_5:'#00ACC1',tab_6:'#F4511E'}};
let tab='tab_1',points=[];const canvas=document.querySelector('#plot'),ctx=canvas.getContext('2d');
function guestDisplay(){{return {{width:window.screen.width||window.outerWidth,height:window.screen.height||window.outerHeight}}}}
function guard(){{let d=guestDisplay(),ok=d.width>=1280&&d.height>=720;document.querySelector('#overlay').style.display=ok?'none':'flex';return ok}}
function buildTabs(){{let n=document.querySelector('#tabs');n.innerHTML='';for(let [id,label] of Object.entries(names)){{let b=document.createElement('button');b.textContent=label;b.onclick=()=>show(id);n.appendChild(b)}}}}
async function show(id){{tab=id;if(!guard())return;document.querySelector('#title').textContent=names[id];document.querySelector('#color-band').style.background=colors[id];for(let b of document.querySelectorAll('nav button'))b.classList.toggle('active',b.textContent===names[id]);let r=await fetch('/api/plot?tab='+id);let d=await r.json();points=d.points;draw()}}
function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#f9fbfd';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#dce5ec';ctx.lineWidth=1;for(let i=0;i<8;i++){{let y=40+i*75;ctx.beginPath();ctx.moveTo(20,y);ctx.lineTo(canvas.width-20,y);ctx.stroke()}}ctx.strokeStyle='#4a7289';ctx.lineWidth=4;ctx.beginPath();for(let i=0;i<24;i++){{let x=40+i*72,y=310+Math.sin(i*.65)*70+(i%4)*12;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}}ctx.stroke();ctx.font='20px Arial';ctx.fillStyle='#263d50';ctx.fillText('Service utilization — last 60 minutes',40,32);points.forEach((p,i)=>{{ctx.beginPath();ctx.arc(p.x,p.y,15,0,Math.PI*2);ctx.fillStyle=i===0?'#c45535':'#247a68';ctx.fill();ctx.fillStyle='#142e46';ctx.fillText(i===0?'Peak A':'Peak B',p.x+20,p.y-14)}})}}
let last=0;canvas.addEventListener('mousemove',async e=>{{if(!guard())return;let now=Date.now();if(now-last<250)return;let r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*canvas.width/r.width,y=(e.clientY-r.top)*canvas.height/r.height;for(let i=0;i<points.length;i++){{let p=points[i];if(Math.hypot(x-p.x,y-p.y)<24){{last=now;let peak=i===0?'peak_a':'peak_b',display=guestDisplay();let u='/api/hover?tab='+tab+'&peak='+peak+'&width='+display.width+'&height='+display.height;let res=await fetch(u);let d=await res.json();let t=document.querySelector('#tip');if(res.ok){{t.textContent=names[tab]+' '+(i===0?'Peak A':'Peak B')+': '+d.value;t.style.display='block';t.style.left=(e.clientX+15)+'px';t.style.top=(e.clientY+15)+'px';setTimeout(()=>t.style.display='none',3000)}}else{{document.querySelector('#overlay').style.display='flex'}}return}}}}}});
function addEvidenceControls(){{const note=document.createElement('div');note.textContent='The Guest desktop is 1920 x 1080. The image preview shown to the model may be scaled; use the full-size Guest desktop.';note.style.cssText='padding-top:8px;font-weight:bold';document.querySelector('header').append(note);const box=document.createElement('section');box.id='evidence-controls';box.style.cssText='padding:12px;background:#fff;border:1px solid #ccd7df';const save=document.createElement('button');save.id='save-tab-evidence';save.textContent='Save current tab PNG';save.onclick=saveTabEvidence;const report=document.createElement('button');report.id='export-telemetry';report.textContent='Export telemetry JSON';report.onclick=exportTelemetry;const status=document.createElement('div');status.id='evidence-status';status.setAttribute('role','status');status.style.marginTop='8px';box.append(save,report,status);document.querySelector('main').append(box)}}
async function viewportPngData(){{const sourceW=window.innerWidth,sourceH=window.innerHeight,display=guestDisplay(),outputW=display.width,outputH=display.height;const clone=document.documentElement.cloneNode(true);clone.querySelectorAll('script').forEach(x=>x.remove());const originals=[...document.querySelectorAll('canvas')],copies=[...clone.querySelectorAll('canvas')];copies.forEach((node,i)=>{{const img=clone.ownerDocument.createElement('img');img.src=originals[i].toDataURL('image/png');img.width=originals[i].width;img.height=originals[i].height;node.replaceWith(img)}});const source=[...document.querySelectorAll('input,textarea,select')],target=[...clone.querySelectorAll('input,textarea,select')];target.forEach((node,i)=>{{if(node.tagName==='SELECT'){{[...node.options].forEach((option,j)=>{{option.selected=source[i].selectedIndex===j}})}}else node.setAttribute('value',source[i].value)}});clone.setAttribute('xmlns','http://www.w3.org/1999/xhtml');const markup=new XMLSerializer().serializeToString(clone);const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${{sourceW}}" height="${{sourceH}}"><foreignObject width="100%" height="100%">${{markup}}</foreignObject></svg>`;const url=URL.createObjectURL(new Blob([svg],{{type:'image/svg+xml;charset=utf-8'}}));try{{const img=new Image();await new Promise((resolve,reject)=>{{img.onload=resolve;img.onerror=reject;img.src=url}});const out=document.createElement('canvas');out.width=outputW;out.height=outputH;const ctx=out.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,outputW,outputH);ctx.drawImage(img,0,0,outputW,outputH);return out.toDataURL('image/png')}}finally{{URL.revokeObjectURL(url)}}}}
async function saveTabEvidence(){{const status=document.querySelector('#evidence-status');try{{if(!guard())throw new Error('maximize Chrome first');const png_data=await viewportPngData();const r=await fetch('/api/export/b/screenshot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{tab,png_data}})}});const x=await r.json();status.textContent=r.ok?`Saved ${{x.filename}} (${{x.width}}x${{x.height}}).`:x.error}}catch(e){{status.textContent='Evidence export failed: '+e.message}}}}
async function exportTelemetry(){{const status=document.querySelector('#evidence-status');const r=await fetch('/api/export/b/report',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});const x=await r.json();status.textContent=r.ok?`Saved ${{x.filename}}.`:(x.error||'Report export failed.')}}
window.addEventListener('resize',()=>guard());buildTabs();addEvidenceControls();guard();let requested=new URLSearchParams(location.search).get('tab');show(names[requested]?requested:'tab_1');
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    role = "A"

    def log_message(self, fmt, *args):
        pass

    def send_json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def authenticated(self):
        # These loopback-only training pages intentionally open straight into
        # the task UI. Keep /bootstrap for older clients, but never require it.
        return True

    def do_GET(self):
        u = urlparse(self.path); query = parse_qs(u.query)
        if u.path == "/health": return self.send_json({"status": "ok", "role": self.role})
        if u.path == "/bootstrap":
            body = b"<html><body>Session ready.<script>location.replace('/')</script></body></html>"
            self.send_response(200); self.send_header("Set-Cookie", f"{COOKIE}={SESSION}; HttpOnly; SameSite=Strict; Path=/")
            self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if not self.authenticated(): return self.send_json({"error": "authentication_required"}, 401)
        if self.role == "A" and u.path == "/":
            body = a_html().encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.role == "B" and u.path == "/":
            body = b_html().encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.role == "B" and u.path == "/api/plot":
            tab = query.get("tab", [""])[0]
            if tab not in TABS: return self.send_json({"error": "unknown_tab"}, 400)
            return self.send_json({"points": [{"x": 420, "y": 175}, {"x": 1240, "y": 420}]})
        if self.role == "B" and u.path == "/api/hover":
            tab, peak = query.get("tab", [""])[0], query.get("peak", [""])[0]
            width, height = int(query.get("width", ["0"])[0]), int(query.get("height", ["0"])[0])
            if tab not in TABS or peak not in ("peak_a", "peak_b"): return self.send_json({"error": "bad_target"}, 400)
            if width < 1860 or height < 950: return self.send_json({"error": "viewport_too_narrow"}, 409)
            value = read_state()["peaks"][tab][peak]
            update_state(lambda data: data["b_hovers"].append({"tab": tab, "peak": peak, "width": width, "height": height}))
            return self.send_json({"value": value})
        return self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        if not self.authenticated(): return self.send_json({"error": "authentication_required"}, 401)
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length < 0 or content_length > 12 * 1024 * 1024:
            return self.send_json({"error": "request_too_large"}, 413)
        try: body = json.loads(self.rfile.read(content_length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError): return self.send_json({"error": "invalid_json"}, 400)
        if not isinstance(body, dict): return self.send_json({"error": "invalid_json_object"}, 400)
        route = urlparse(self.path).path
        width, height = int(body.get("width", 0)), int(body.get("height", 0))
        if self.role == "A" and route == "/api/export/a/report":
            try: report = _build_a_report(read_state())
            except ValueError as exc: return self.send_json({"error": str(exc)}, 409)
            target = WORKSPACE / "out_a" / "qa_viewport_report.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return self.send_json({"ok": True, "filename": target.name})
        if self.role == "B" and route == "/api/export/b/report":
            try: report = _build_b_report(read_state())
            except ValueError as exc: return self.send_json({"error": str(exc)}, 409)
            target = WORKSPACE / "out_b" / "ops_telemetry.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return self.send_json({"ok": True, "filename": target.name})
        if self.role in ("A", "B") and route in ("/api/export/a/screenshot", "/api/export/b/screenshot"):
            if (self.role == "A" and not route.endswith("/a/screenshot")) or (self.role == "B" and not route.endswith("/b/screenshot")):
                return self.send_json({"error": "wrong_export_role"}, 404)
            try:
                filename, image_width, image_height = _save_browser_png(self.role.lower(), "", body)
            except (ValueError, OSError, TypeError) as exc:
                return self.send_json({"error": str(exc)}, 409 if isinstance(exc, ValueError) else 500)
            return self.send_json({"ok": True, "filename": filename, "width": image_width, "height": image_height})
        if self.role == "A" and route == "/api/control":
            name = body.get("name")
            if name not in ("delivery", "promotion", "tax"): return self.send_json({"error": "unknown_control"}, 400)
            value = str(body.get("value", ""))[:100]
            update_state(lambda data: data["a_controls"].append({"name": name, "value": value, "width": width, "height": height}))
            return self.send_json({"message": f"{name.title()} control recorded for outer width {width}px."})
        if self.role == "A" and route == "/api/record":
            band = str(body.get("band", ""))
            limits = {"mobile": (355, 395), "tablet": (748, 788), "desktop": (1415, 1465)}
            if band not in limits or not limits[band][0] <= width <= limits[band][1]:
                return self.send_json({"error": "viewport_outside_target_band"}, 409)
            badge = str(secrets.randbelow(900000) + 100000)
            ids = sorted(set(str(x) for x in body.get("bug_element_ids", [])))
            update_state(lambda data: (data["a_checks"].append({"band": band, "width": width, "height": height, "bug_element_ids": ids, "badge_code": badge}), data["badges"].__setitem__(band, badge)))
            return self.send_json({"badge_code": badge, "message": "Viewport check recorded."})
        return self.send_json({"error": "not_found"}, 404)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--role", choices=["A", "B"], required=True); ap.add_argument("--port", type=int, required=True)
    args = ap.parse_args()
    update_state(lambda data: data)
    handler = type(f"Handler{args.role}", (Handler,), {"role": args.role})
    ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__": main()
