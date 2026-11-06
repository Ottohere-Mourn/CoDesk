#!/usr/bin/env python3
"""Local-only DATA-REL1 synthetic export workspace; no external release service."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, copy, json, threading, time
try:
    from scripts import data_rel1_fixture_v1 as fx
except ModuleNotFoundError:
    import data_rel1_fixture_v1 as fx

PORT = 8786
ROUTES = {"exporter": f"http://127.0.0.1:{PORT}/case/exporter",
          "coordinator": f"http://127.0.0.1:{PORT}/case/coordinator"}
PAGE = r'''<!doctype html><html><head><meta charset="utf-8"><title>Study Export Workbench</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#1a2b39;font:16px Arial,sans-serif}
header{height:62px;background:#25465d;color:white;padding:18px 26px;font-size:22px;font-weight:bold}
main{max-width:1150px;margin:18px auto;padding:0 18px}.row{display:flex;gap:16px}.card{background:white;border:1px solid #c7d1da;border-radius:5px;padding:16px;margin-bottom:14px;flex:1}
h2{font-size:19px;margin:0 0 12px;color:#25465d}.muted{color:#586979;font-size:14px}.banner{padding:11px 13px;background:#e8f2fa;border:1px solid #afc9dc;margin:10px 0;line-height:1.4}.warning{background:#fff0da;border-color:#dfb26e;color:#643e05}.good{color:#1e6842;font-weight:bold}.bad{color:#a23939;font-weight:bold}
button{font:16px Arial;padding:10px 14px;border:0;border-radius:3px;background:#236849;color:white;cursor:pointer;margin:6px 6px 0 0}button.secondary{background:#315d83}button.danger{background:#8e3940}table{width:100%;border-collapse:collapse;margin-top:9px}td,th{padding:8px;border-bottom:1px solid #d6dde3;text-align:left;vertical-align:top}pre{white-space:pre-wrap;background:#f4f6f8;border:1px solid #d8dee4;padding:10px;line-height:1.45}#result{min-height:23px;font-weight:bold;color:#25465d}
</style></head><body data-role="__ROLE__"><header>Study Export Workbench · STUDY-SYN-88</header><main>
<div class="row"><section class="card"><h2>Current export policy</h2><div id="policy">Loading…</div><div class="banner">Only local staging is enabled. External release is disabled. Every unreleased package must match the current protocol scope before release.</div></section>
<section class="card"><h2>Protocol scope</h2><div id="scope">Loading…</div><div id="evidence" class="muted">PA-SYN-017 · Synthetic approved protocol amendment · excludes SUB-17 from future unreleased exports; effective immediately for existing unreleased staging packages.</div></section></div>
<section class="card"><h2>Staging packages</h2><div id="status"></div><div id="packages">Loading…</div><div id="actions"></div></section>
<section class="card"><h2>Activity</h2><div id="result"></div><div id="activity" class="muted"></div></section></main>
<script>
const role=document.body.dataset.role;
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function post(path,obj){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});const j=await r.json();if(!r.ok)throw new Error(j.error||'request failed');return j}
async function refresh(source){const s=await fetch('/api/state',{cache:'no-store'}).then(r=>r.json());const active=(s.exclusions||[]).filter(x=>x.status==='ACTIVE');const excluded=active.map(x=>x.subject_id);const expected=(s.subjects||[]).filter(x=>x.export_allowed&&!excluded.includes(x.subject_id)).map(x=>x.subject_id).sort();
$('policy').innerHTML='Policy version <b>'+s.policy_version+'</b> · '+esc(s.release_policy.rule_id)+' · external release: <b>disabled</b>';
$('scope').innerHTML='Dataset <b>'+esc(s.dataset_id)+'</b> version '+s.dataset_version+' · allowed subjects: <b>'+expected.map(esc).join(', ')+'</b>';
const rows=s.packages||[];$('packages').innerHTML=rows.length?'<table><tr><th>Package</th><th>Status / location</th><th>Subjects</th><th>Dataset / policy version</th><th>Manifest SHA-256</th><th>Current?</th></tr>'+rows.map(p=>{const stale=p.policy_version!==s.policy_version||JSON.stringify((p.row_subject_ids||[]).slice().sort())!==JSON.stringify(expected);return '<tr><td>'+esc(p.package_id)+'</td><td>'+esc(p.status)+' / '+esc(p.artifact_location)+'</td><td>'+esc((p.row_subject_ids||[]).join(', '))+'</td><td>'+p.dataset_version+' / '+p.policy_version+'</td><td><small>'+esc(p.manifest_sha256)+'</small></td><td class="'+(stale?'bad':'good')+'">'+(stale?'Requires revalidation':'Matches current scope')+'</td></tr>'}).join('')+'</table>':'No staging package.';
$('status').innerHTML=rows.some(p=>p.status==='READY'&&(p.policy_version!==s.policy_version||JSON.stringify((p.row_subject_ids||[]).slice().sort())!==JSON.stringify(expected)))?'<div class="banner warning">A READY package no longer matches the active protocol scope. Revoke and quarantine it, then rebuild before release.</div>':'';
if(role==='exporter'){$('actions').innerHTML='<button id="build">Build local READY package</button>'+rows.filter(p=>p.status==='READY'&&p.artifact_location==='STAGING_ACTIVE').map(p=>'<button class="danger" data-revoke="'+esc(p.package_id)+'">Revoke / quarantine '+esc(p.package_id)+'</button>').join('');$('build').onclick=async()=>{try{const x=await post('/api/build',{actor:'A'});$('result').textContent=x.message;await refresh('package built')}catch(e){$('result').textContent=e.message}};document.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=async()=>{try{const x=await post('/api/revoke',{actor:'A',package_id:b.dataset.revoke});$('result').textContent=x.message;await refresh('package quarantined')}catch(e){$('result').textContent=e.message}})}
else{$('actions').innerHTML='<button class="secondary" id="amend">Apply verified PA-SYN-017 amendment</button>'; $('amend').onclick=async()=>{try{const x=await post('/api/amendment',{actor:'B'});$('result').textContent=x.message;await refresh('protocol amendment applied')}catch(e){$('result').textContent=e.message}}}
$('activity').textContent='Updated '+new Date().toLocaleTimeString()+' · '+(source||'refresh');}
refresh('page load');setInterval(()=>refresh('workspace refresh'),2000);
</script></body></html>'''

class State:
    def __init__(self, path):
        self.path=Path(path);self.lock=threading.RLock();self.data=fx.initial_workspace();self.events=[];self.flush()
    def flush(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'business':self.data,'events':self.events},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(self.path)
    def record(self,event):
        row={'time_unix':time.time(),**event};self.events.append(row);self.flush()
    def reset(self):self.data=fx.initial_workspace();self.events=[];self.flush()

def create_server(state,port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send_obj(self,code,obj,ctype='application/json; charset=utf-8'):
            body=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def body(self):
            n=int(self.headers.get('Content-Length','0'));return json.loads(self.rfile.read(n) or b'{}')
        def do_GET(self):
            if self.path=='/health':return self.send_obj(200,{'ok':True,'loopback_only':True,'task_version':fx.TASK_VERSION})
            if self.path=='/api/state':
                with state.lock:return self.send_obj(200,{**state.data,'events':state.events})
            if self.path in ('/case/exporter','/case/coordinator'):
                role='exporter' if self.path.endswith('exporter') else 'coordinator'
                return self.send_obj(200,PAGE.replace('__ROLE__',role).encode('utf-8'),'text/html; charset=utf-8')
            return self.send_obj(404,{'error':'not found'})
        def do_POST(self):
            try:obj=self.body()
            except Exception:return self.send_obj(400,{'error':'invalid JSON'})
            with state.lock:
                if self.path=='/api/reset':
                    state.reset();return self.send_obj(200,{'ok':True})
                if self.path=='/api/build':
                    if obj.get('actor')!='A':return self.send_obj(403,{'error':'package creation is assigned to exporter A'})
                    if any(p.get('status')=='READY' and p.get('artifact_location')=='STAGING_ACTIVE' for p in state.data['packages']):return self.send_obj(409,{'error':'active READY package already exists'})
                    n=len([p for p in state.data['packages'] if p.get('created_by')=='A'])+1
                    p=fx.build_ready_package(state.data,f'PKG-A-{n:03d}','A');state.record({'action':'build_ready_package','actor':'A','package_id':p['package_id'],'policy_version':p['policy_version']})
                    return self.send_obj(200,{'ok':True,'package_id':p['package_id'],'message':'Local READY package created.'})
                if self.path=='/api/amendment':
                    if obj.get('actor')!='B':return self.send_obj(403,{'error':'protocol amendment is assigned to coordinator B'})
                    try:x=fx.register_exclusion(state.data,fx.RESTRICTION_EVIDENCE,'B')
                    except ValueError as e:return self.send_obj(409,{'error':str(e)})
                    state.record({'action':'register_exclusion','actor':'B','source_id':x['source_id'],'subject_id':x['subject_id'],'policy_version':x['policy_version']})
                    return self.send_obj(200,{'ok':True,'message':f"PA-SYN-017 active at policy version {x['policy_version']}; SUB-17 excluded from unreleased packages."})
                if self.path=='/api/revoke':
                    if obj.get('actor')!='A':return self.send_obj(403,{'error':'package revocation is assigned to exporter A'})
                    try:fx.revoke_and_quarantine(state.data,str(obj.get('package_id','')),'A')
                    except ValueError as e:return self.send_obj(409,{'error':str(e)})
                    state.record({'action':'revoke_and_quarantine','actor':'A','package_id':str(obj.get('package_id',''))})
                    return self.send_obj(200,{'ok':True,'message':'Package revoked and moved to local quarantine.'})
            return self.send_obj(404,{'error':'not found'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--port',type=int,default=PORT);a=p.parse_args()
    state=State(a.state);server=create_server(state,a.port);server.serve_forever()
if __name__=='__main__':main()
