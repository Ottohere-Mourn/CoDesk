"""Local-only browser workspace used for cache and replay episodes."""

INDEX_HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><title>Shared Workspace</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#e9edf2;color:#18212d;font:20px Arial,sans-serif}
.panel{position:absolute;top:28px;width:620px;height:700px;padding:28px;background:white;border:2px solid #58677a;border-radius:12px}
#cache-panel{left:28px}#replay-panel{left:700px}h1{font-size:28px;margin:0 0 16px}label{display:block;font-size:18px;margin:14px 0 6px}
input{width:550px;height:54px;padding:8px;font-size:22px;border:2px solid #8493a4;border-radius:6px}
button{height:52px;padding:0 22px;font-size:20px;border:0;border-radius:6px;background:#175bb5;color:white}
#refresh{position:absolute;left:28px;top:355px}#save{position:absolute;left:205px;top:355px}
.goal{margin-top:26px}.goal button{display:block;margin-top:10px}.status{font-size:17px;color:#174d22;margin-top:10px}
</style></head>
<body>
<section class="panel" id="cache-panel"><h1>Cached Shared Record</h1>
<label for="gui-status">GUI status</label><input id="gui-status" autocomplete="off">
<label for="cli-note">CLI annotation (visible after refresh)</label><input id="cli-note" autocomplete="off">
<button id="refresh" onclick="refreshState()">Refresh latest state</button>
<button id="save" onclick="saveSnapshot()">Save record</button>
<div class="status" id="cache-result"></div></section>
<section class="panel" id="replay-panel"><h1>Independent Review Goals</h1>
<div class="goal"><label for="human-goal">Human Replay: review note</label>
<input id="human-goal" autocomplete="off"><button id="human-submit" onclick="submitGoal('human')">Submit human review</button>
<div class="status" id="human-result"></div></div>
<div class="goal"><label for="agent-goal">GUI Agent: approval note</label>
<input id="agent-goal" autocomplete="off"><button id="agent-submit" onclick="submitGoal('agent')">Submit agent approval</button>
<div class="status" id="agent-result"></div></div></section>
<script>
let cached={};
async function refreshState(){cached=await (await fetch('/state')).json();
 document.querySelector('#gui-status').value=cached.gui_status||'';
 document.querySelector('#cli-note').value=cached.cli_note||'';
 document.querySelector('#cache-result').textContent='Loaded revision '+cached.revision;}
async function saveSnapshot(){cached.gui_status=document.querySelector('#gui-status').value;
 const response=await fetch('/replace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cached)});
 const result=await response.json();document.querySelector('#cache-result').textContent='Saved revision '+result.revision;}
async function submitGoal(actor){const field=actor==='human'?'#human-goal':'#agent-goal';
 const response=await fetch('/goal',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({actor:actor,value:document.querySelector(field).value})});
 const result=await response.json();document.querySelector('#'+actor+'-result').textContent='Saved';}
refreshState();
</script></body></html>'''

SERVER_PY = r"""from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json

ROOT=Path('/tmp/swcub_web'); STATE=ROOT/'state.json'
DEFAULT={'gui_status':'Draft','cli_note':'Draft','human_goal':'','agent_goal':'','revision':0}
ROOT.mkdir(parents=True,exist_ok=True)
if not STATE.exists(): STATE.write_text(json.dumps(DEFAULT))

class Handler(BaseHTTPRequestHandler):
    def _json(self, value, status=200):
        data=json.dumps(value).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)))
        self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path=='/':
            data=HTML.encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
        if self.path=='/state': self._json(json.loads(STATE.read_text())); return
        if self.path=='/health': self._json({'ok':True}); return
        self._json({'error':'not found'},404)
    def do_POST(self):
        try: payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        except Exception: return self._json({'error':'invalid JSON'},400)
        state=json.loads(STATE.read_text())
        if self.path=='/cli': state['cli_note']=str(payload.get('cli_note','')); state['revision']+=1
        elif self.path=='/replace': state={**payload,'revision':state['revision']+1}
        elif self.path=='/goal':
            actor=payload.get('actor')
            if actor not in ('human','agent'): return self._json({'error':'unknown actor'},400)
            state[actor+'_goal']=str(payload.get('value','')); state['revision']+=1
        else: return self._json({'error':'not found'},404)
        STATE.write_text(json.dumps(state,sort_keys=True)); self._json(state)
    def log_message(self, *_): pass

HTML='''HTML_PLACEHOLDER'''
HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
"""


def server_source() -> bytes:
    return SERVER_PY.replace("HTML='''HTML_PLACEHOLDER'''", "HTML=" + repr(INDEX_HTML)).encode("utf-8")
