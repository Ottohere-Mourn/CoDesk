"""In-memory-authenticated twin dashboard for the CONC-04 shared desktop case."""
from __future__ import annotations

import argparse
import base64
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


NODES = ["API Gateway", "Auth Service", "Order Engine", "Inventory DB", "Event Bus", "Billing Worker"]
EDGES = [
    ["API Gateway", "Auth Service"], ["Auth Service", "Order Engine"],
    ["Order Engine", "Inventory DB"], ["Auth Service", "Event Bus"],
    ["Event Bus", "Billing Worker"], ["Billing Worker", "Inventory DB"],
    ["Order Engine", "Billing Worker"],
]
SLOTS = {
    "API Gateway": [105, 100], "Auth Service": [305, 100], "Order Engine": [505, 100],
    "Inventory DB": [805, 100], "Event Bus": [305, 560], "Billing Worker": [705, 560],
}
OBSTACLES = [[395, 220, 495, 365], [610, 365, 740, 490]]
CHARTS = ["chart_1", "chart_2", "chart_3", "chart_4"]
STRIPES = {"chart_1": "#3949AB", "chart_2": "#00838F", "chart_3": "#6A1B9A", "chart_4": "#EF6C00"}
PAGE_A = r'''<!doctype html><html><head><meta charset="utf-8"><title>FlowCanvas — Architecture Studio</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f8;color:#172b4d;font:14px Inter,Arial,sans-serif}header{background:#17324d;color:#fff;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:20px}.stripe{width:120px;height:24px;background:#00897B;border-radius:3px}.wrap{padding:12px 18px}.palette{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.card{background:#fff;border:1px solid #cad5e1;border-radius:6px;padding:8px 10px;cursor:grab;box-shadow:0 1px 2px #0001}.board{background:#fff;border:1px solid #c8d2de;box-shadow:0 4px 16px #172b4d17;display:block;touch-action:none}.below{display:flex;gap:10px;align-items:center;margin-top:10px}.panel{background:#fff;padding:9px 12px;border:1px solid #cad5e1;border-radius:6px}.panel label{margin-right:6px}.panel select,.panel button{padding:6px 9px}.small{color:#66788a;font-size:12px}</style></head><body>
<header><h1>FlowCanvas · Service Topology</h1><div class="stripe" aria-label="FlowCanvas marker"></div></header><div class="wrap">
<div class="palette"><strong>Components — drag each to its matching dashed slot:</strong><span id="cards"></span></div>
<canvas id="cv" class="board" width="1000" height="680"></canvas>
<div class="below"><div class="panel"><label for="edge">Connection specification</label><select id="edge"></select><button id="draw">Draw connection</button><button id="save">Submit topology and export PNG</button></div><div class="panel small">Drag from the source node’s circular anchor to the destination anchor. Trace a bend around each red restricted zone.</div></div>
</div><script>
const names=__NODES__, edges=__EDGES__, slots=__SLOTS__, blocks=__OBSTACLES__;
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),nodes={},done=[],events=[],pending=[];let dragNode=null,current=null,selected=-1;
const colors={ink:'#243b53',node:'#e7f0fb',edge:'#395c7a',slot:'#97a8b6',obs:'#e53935'};
document.getElementById('cards').innerHTML=names.map(n=>`<span class="card" data-node="${n}">${n}</span>`).join('');
document.getElementById('edge').innerHTML=edges.map((e,i)=>`<option value="${i}">${e[0]} to ${e[1]}</option>`).join('');
function draw(){ctx.clearRect(0,0,1000,680);ctx.fillStyle='#fff';ctx.fillRect(0,0,1000,680);ctx.font='12px Arial';
 for(let x=20;x<1000;x+=40){ctx.strokeStyle='#f1f4f7';ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,680);ctx.stroke()}for(let y=20;y<680;y+=40){ctx.strokeStyle='#f1f4f7';ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1000,y);ctx.stroke()}
 for(const [name,p] of Object.entries(slots)){ctx.setLineDash([6,5]);ctx.strokeStyle=colors.slot;ctx.lineWidth=2;ctx.strokeRect(p[0]-62,p[1]-28,124,56);ctx.setLineDash([]);ctx.fillStyle='#61758a';ctx.textAlign='center';ctx.fillText(name,p[0],p[1]+45)}
 for(const b of blocks){ctx.fillStyle='rgba(229,57,53,.16)';ctx.fillRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.save();ctx.beginPath();ctx.rect(b[0],b[1],b[2]-b[0],b[3]-b[1]);ctx.clip();ctx.strokeStyle='#e53935';for(let x=b[0]-100;x<b[2]+100;x+=12){ctx.beginPath();ctx.moveTo(x,b[3]);ctx.lineTo(x+150,b[1]);ctx.stroke()}ctx.restore();ctx.strokeStyle='#c62828';ctx.lineWidth=2;ctx.strokeRect(...[b[0],b[1],b[2]-b[0],b[3]-b[1]])}
 for(const e of done){ctx.strokeStyle=colors.edge;ctx.lineWidth=3;ctx.beginPath();e.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();const p=e.points.at(-1),q=e.points.at(-2);let a=Math.atan2(p[1]-q[1],p[0]-q[0]);ctx.fillStyle=colors.edge;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(p[0]-12*Math.cos(a-.45),p[1]-12*Math.sin(a-.45));ctx.lineTo(p[0]-12*Math.cos(a+.45),p[1]-12*Math.sin(a+.45));ctx.fill()}
 if(current){ctx.strokeStyle='#0b7285';ctx.lineWidth=3;ctx.beginPath();current.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke()}
 for(const [n,p] of Object.entries(nodes)){ctx.fillStyle=colors.node;ctx.strokeStyle='#2e5d7b';ctx.lineWidth=2;ctx.fillRect(p[0]-58,p[1]-23,116,46);ctx.strokeRect(p[0]-58,p[1]-23,116,46);ctx.fillStyle=colors.ink;ctx.textAlign='center';ctx.fillText(n,p[0],p[1]+4);ctx.fillStyle='#087e8b';ctx.beginPath();ctx.arc(p[0]+58,p[1],7,0,Math.PI*2);ctx.fill();ctx.fillStyle='#a23b3b';ctx.beginPath();ctx.arc(p[0]-58,p[1],7,0,Math.PI*2);ctx.fill()}
 ctx.fillStyle='#00897B';ctx.fillRect(860,8,120,24)
}
function pos(ev){const r=cv.getBoundingClientRect();return [(ev.clientX-r.left)*cv.width/r.width,(ev.clientY-r.top)*cv.height/r.height]}
function post(obj){const p=fetch('/api/a/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});pending.push(p);return p}
document.querySelectorAll('.card').forEach(c=>{c.addEventListener('pointerdown',e=>{dragNode=c.dataset.node;c.setPointerCapture(e.pointerId);events.push({type:'node_drag_start',node:dragNode,moves:0});c.dataset.moves='0'});c.addEventListener('pointermove',e=>{if(dragNode)c.dataset.moves=String(Number(c.dataset.moves||0)+1)});c.addEventListener('pointerup',e=>{if(!dragNode)return;const p=pos(e);nodes[dragNode]=p;const ev={type:'node_drop',node:dragNode,x:p[0],y:p[1],moves:Number(c.dataset.moves||0)};events.push(ev);post(ev);dragNode=null;draw()})});
function selectedEdge(){return Number(document.getElementById('edge').value)}
cv.addEventListener('pointerdown',e=>{const p=pos(e);if(selected<0||!nodes[edges[selected][0]])return;const [from,to]=edges[selected];if(Math.hypot(p[0]-(nodes[from][0]+58),p[1]-nodes[from][1])>18)return;current={from,to,points:[p],moves:0};cv.setPointerCapture(e.pointerId)});
cv.addEventListener('pointermove',e=>{if(!current)return;const p=pos(e),last=current.points.at(-1);if(Math.hypot(p[0]-last[0],p[1]-last[1])>6){current.points.push(p);current.moves++}draw()});
cv.addEventListener('pointerup',e=>{if(!current)return;const p=pos(e),[from,to]=[current.from,current.to];const dest=nodes[to];if(dest&&Math.hypot(p[0]-(dest[0]-58),p[1]-dest[1])<22&&current.moves>=3){current.points.push(p);const edge={from,to,points:current.points};done.push(edge);const ev={type:'edge_drag',from,to,moves:current.moves,points:current.points};events.push(ev);post(ev);selected=-1;document.getElementById('edge').value='0'}else{events.push({type:'aborted_drag',from,to,moves:current.moves});post(events.at(-1))}current=null;draw()});
window.addEventListener('blur',()=>{if(dragNode||current){const ev={type:'aborted_drag',node:dragNode,from:current&&current.from,to:current&&current.to};post(ev);dragNode=null;current=null;draw()}});
document.getElementById('draw').onclick=()=>{selected=selectedEdge();document.getElementById('edge').disabled=true;document.getElementById('draw').textContent='Drag the source anchor';setTimeout(()=>{document.getElementById('edge').disabled=false;document.getElementById('draw').textContent='Draw connection'},8000)};
document.getElementById('save').onclick=async()=>{await Promise.all(pending.splice(0));const payload={nodes:Object.entries(nodes).map(([name,p])=>({name,x:p[0],y:p[1]})),edges:done};await fetch('/api/a/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({graph:payload,png:cv.toDataURL('image/png')})});alert('Topology and canvas image saved.')};draw();
</script></body></html>'''

PAGE_B = r'''<!doctype html><html><head><meta charset="utf-8"><title>MetricAnnotator — Incident Review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#172b4d;font:14px Inter,Arial,sans-serif}header{background:#17324d;color:white;padding:12px 18px;display:flex;justify-content:space-between;align-items:center}h1{font-size:20px;margin:0}.bar{width:120px;height:24px;background:__STRIPE__;border-radius:3px}.wrap{padding:12px 18px}.tabs{display:flex;gap:7px;margin-bottom:8px}.tabs button,.save{padding:7px 11px;background:white;border:1px solid #b9c7d5;border-radius:5px;cursor:pointer}.tabs button.active{background:#dbeafe;border-color:#3572a5}.frame{background:white;border:1px solid #c8d2de;padding:8px;width:max-content;box-shadow:0 4px 16px #172b4d17}canvas{display:block;touch-action:none}.hint{margin-top:8px;color:#52667a}.save{margin-top:10px;background:#176b87;color:white;border:0}</style></head><body><header><h1>MetricAnnotator · Time-series Incident Review</h1><div class="bar"></div></header><main class="wrap"><div class="tabs" id="tabs"></div><div class="frame"><canvas id="cv" width="960" height="540"></canvas></div><div class="hint">Drag a tight rectangle around each anomaly, select it, then classify: 1 SPIKE · 2 DROP · 3 FLATLINE. Delete or Backspace removes the selected box.</div><button class="save" id="save">Submit all charts and export PNGs</button></main><script>
const charts=__CHARTS__,colors=__COLORS__,cv=document.getElementById('cv'),ctx=cv.getContext('2d');let active=charts[0],drag=null,selected=-1;const pending=[];const labels={};for(const c of charts)labels[c]=[];
document.getElementById('tabs').innerHTML=charts.map((c,i)=>`<button data-chart="${c}" class="${i===0?'active':''}">${c.replace('_',' ')}</button>`).join('');
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{active=b.dataset.chart;document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));selected=-1;draw()});
function loadImg(){let im=new Image();im.onload=()=>{window.currentImage=im;draw()};im.src='/assets/'+active+'.png'}
function draw(){ctx.clearRect(0,0,960,540);if(window.currentImage)ctx.drawImage(window.currentImage,0,0,960,540);ctx.fillStyle=colors[active];ctx.fillRect(824,10,120,24);ctx.fillStyle='#fff';ctx.font='bold 12px Arial';ctx.fillText(active.toUpperCase(),835,26);labels[active].forEach((b,i)=>{ctx.lineWidth=i===selected?4:3;ctx.strokeStyle=b.label==null?'#c62828':({'SPIKE':'#c62828','DROP':'#1565c0','FLATLINE':'#7b1fa2'}[b.label]);ctx.strokeRect(b.x1,b.y1,b.x2-b.x1,b.y2-b.y1);ctx.fillStyle='#182230';ctx.fillText((b.label||'UNCLASSIFIED'),b.x1+2,b.y1-5)})}
function point(e){let r=cv.getBoundingClientRect();return [(e.clientX-r.left)*960/r.width,(e.clientY-r.top)*540/r.height]}
function postEvent(obj){obj.chart=active;const p=fetch('/api/b/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});pending.push(p);return p}
cv.onpointerdown=e=>{let p=point(e);selected=labels[active].findIndex(b=>p[0]>=b.x1&&p[0]<=b.x2&&p[1]>=b.y1&&p[1]<=b.y2);if(selected<0){drag={x1:p[0],y1:p[1],x2:p[0],y2:p[1],moves:0};cv.setPointerCapture(e.pointerId);postEvent({type:'box_drag_start',x:p[0],y:p[1]})}else draw()};
cv.onpointermove=e=>{if(!drag)return;let p=point(e);drag.x2=p[0];drag.y2=p[1];drag.moves++;draw();ctx.strokeStyle='#111';ctx.setLineDash([5,3]);ctx.strokeRect(drag.x1,drag.y1,drag.x2-drag.x1,drag.y2-drag.y1);ctx.setLineDash([])};
cv.onpointerup=e=>{if(!drag)return;let p=point(e),box={x1:Math.min(drag.x1,p[0]),y1:Math.min(drag.y1,p[1]),x2:Math.max(drag.x1,p[0]),y2:Math.max(drag.y1,p[1]),label:null};if(box.x2-box.x1>5&&box.y2-box.y1>5){labels[active].push(box);selected=labels[active].length-1;postEvent({type:'box_drag',...box,moves:drag.moves})}drag=null;draw()};
window.addEventListener('keydown',e=>{if(selected>=0&&['1','2','3'].includes(e.key)){const lab={'1':'SPIKE','2':'DROP','3':'FLATLINE'}[e.key];labels[active][selected].label=lab;postEvent({type:'classify',index:selected,key:e.key,label:lab});draw()}else if(selected>=0&&['Delete','Backspace'].includes(e.key)){labels[active].splice(selected,1);postEvent({type:'delete',key:e.key});selected=-1;draw()}else if(['1','2','3','Delete','Backspace'].includes(e.key)){postEvent({type:'misrouted_key',key:e.key})}});
window.addEventListener('blur',()=>{if(drag){postEvent({type:'aborted_drag',x1:drag.x1,y1:drag.y1});drag=null;draw()}});
document.getElementById('save').onclick=async()=>{const screenshots={};for(const c of charts){active=c;await new Promise(r=>{let im=new Image();im.onload=()=>{window.currentImage=im;draw();screenshots[c]=cv.toDataURL('image/png');r()};im.src='/assets/'+c+'.png'})}active=charts[0];draw();await Promise.all(pending.splice(0));await fetch('/api/b/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({labels,screenshots})});alert('All four annotations and PNGs saved.')};loadImg();document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',loadImg));
</script></body></html>'''


class SharedState:
    def __init__(self, chart_root: Path, out_root: Path, state_path: Path):
        self.chart_root, self.out_root, self.state_path = chart_root, out_root, state_path
        self.lock = threading.Lock()
        self.session = secrets.token_urlsafe(24)
        self.data = {"a_events": [], "b_events": [], "aborted_drag_count": 0,
                     "misrouted_key_count": 0, "a_submitted": False, "b_submitted": False}

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


def handler_for(state: SharedState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ProcureMetrics/1.0"

        def log_message(self, *_):
            return

        def _send(self, body: bytes, typ="text/html; charset=utf-8", cookie=False):
            self.send_response(200)
            self.send_header("Content-Type", typ)
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", f"conc04_session={state.session}; HttpOnly; SameSite=Lax; Path=/")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self):
            n = min(int(self.headers.get("Content-Length", "0")), 5_000_000)
            return json.loads(self.rfile.read(n).decode("utf-8"))

        def _authorized(self):
            return f"conc04_session={state.session}" in self.headers.get("Cookie", "")

        def _json(self, obj, code=200):
            raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = unquote(self.path.split("?", 1)[0])
            if path == "/health":
                return self._send(b"ok", "text/plain")
            if path == "/a" or (path == "/" and self.server.server_port == 18091):
                page = PAGE_A.replace("__NODES__", json.dumps(NODES)).replace("__EDGES__", json.dumps(EDGES))
                page = page.replace("__SLOTS__", json.dumps(SLOTS)).replace("__OBSTACLES__", json.dumps(OBSTACLES))
                return self._send(page.encode("utf-8"), cookie=True)
            if path == "/b" or (path == "/" and self.server.server_port == 18092):
                page = PAGE_B.replace("__CHARTS__", json.dumps(CHARTS)).replace("__COLORS__", json.dumps(STRIPES))
                return self._send(page.encode("utf-8"), cookie=True)
            if path.startswith("/assets/"):
                name = Path(path).name
                if name in {c + ".png" for c in CHARTS}:
                    p = state.chart_root / name
                    if p.is_file():
                        return self._send(p.read_bytes(), "image/png")
            self.send_error(404)

        def do_POST(self):
            if not self._authorized():
                return self._json({"error": "authentication required"}, 401)
            path = self.path.split("?", 1)[0]
            try:
                data = self._json_body()
                if path == "/api/a/event":
                    with state.lock:
                        state.data["a_events"].append(data)
                        state.data["aborted_drag_count"] += data.get("type") == "aborted_drag"
                        state.save()
                    return self._json({"ok": True})
                if path == "/api/b/event":
                    with state.lock:
                        state.data["b_events"].append(data)
                        state.data["aborted_drag_count"] += data.get("type") == "aborted_drag"
                        state.data["misrouted_key_count"] += data.get("type") == "misrouted_key"
                        state.save()
                    return self._json({"ok": True})
                if path == "/api/a/save":
                    out = state.out_root / "out_a"
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "arch_flow.json").write_text(json.dumps(data.get("graph", {}), indent=2), encoding="utf-8")
                    png = data.get("png", "").partition(",")[2]
                    if png:
                        (out / "arch_flow.png").write_bytes(base64.b64decode(png, validate=True))
                    with state.lock:
                        state.data["a_submitted"] = True
                        state.save()
                    return self._json({"ok": True})
                if path == "/api/b/save":
                    out = state.out_root / "out_b"
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "anomaly_labels.json").write_text(json.dumps(data.get("labels", {}), indent=2), encoding="utf-8")
                    for chart, b64 in (data.get("screenshots") or {}).items():
                        if chart in CHARTS and isinstance(b64, str):
                            payload = b64.partition(",")[2]
                            if payload:
                                (out / f"{chart}.png").write_bytes(base64.b64decode(payload, validate=True))
                    with state.lock:
                        state.data["b_submitted"] = True
                        state.save()
                    return self._json({"ok": True})
            except (ValueError, TypeError, json.JSONDecodeError):
                return self._json({"error": "invalid request"}, 400)
            self.send_error(404)

    return Handler


def serve(chart_root: Path, out_root: Path, state_path: Path, ports=(18091, 18092)):
    state = SharedState(Path(chart_root), Path(out_root), Path(state_path))
    handler = handler_for(state)
    servers = [ThreadingHTTPServer(("127.0.0.1", p), handler) for p in ports]
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chart-root", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, default=Path("/home/user/workspace"))
    ap.add_argument("--state", type=Path, default=Path("/tmp/conc04-runtime/state.json"))
    ap.add_argument("--port-a", type=int, default=18091)
    ap.add_argument("--port-b", type=int, default=18092)
    a = ap.parse_args()
    serve(a.chart_root, a.out_root, a.state, (a.port_a, a.port_b))
