#!/usr/bin/env python3
import argparse, json, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
CONFIG = __CONFIG__
DB = ''
PAGE_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#192b3a;font:16px Arial,sans-serif}header{background:#20455f;color:#fff;padding:18px 26px}header h1{margin:0 0 5px;font-size:24px}header p{margin:0;color:#d4e4ee}main{display:grid;grid-template-columns:340px 1fr;gap:18px;padding:20px;max-width:1450px;margin:auto}.card{background:white;border:1px solid #d2dce3;border-radius:8px;padding:16px}.items{display:flex;flex-direction:column;gap:8px;max-height:800px;overflow:auto}.item{text-align:left;background:white;border:1px solid #bdc9d2;border-radius:5px;padding:12px;cursor:pointer}.item.sel{border:2px solid #1778a8;background:#edf8fc}small{display:block;color:#66798a;margin-top:4px}.tabs{display:flex;gap:8px;margin:12px 0 18px}.tab{padding:10px 14px;border:1px solid #bdc9d2;border-radius:5px;cursor:pointer;background:#edf2f5}.tab.sel{background:#176d91;color:white}.source{background:#f5f8fa;border-left:4px solid #4291ad;padding:12px;margin:12px 0;line-height:1.5;white-space:pre-wrap}.form{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:850px}label{display:grid;gap:6px;font-weight:600}input,select{padding:10px;border:1px solid #aab8c2;border-radius:4px;font:16px Arial}#save,#copy-ref{padding:11px 16px;border:0;border-radius:5px;background:#146a43;color:white;font-weight:bold;cursor:pointer}#copy-ref{background:#236b8d;margin:8px 0}.status{min-height:24px;color:#176d45;font-weight:bold;margin-top:12px}.banner{padding:10px;background:#eaf3f7;border-radius:5px}.hint{font-size:13px;color:#506677;margin-top:10px}
</style></head><body><header><h1>__TITLE__</h1><p>__SUBTITLE__</p></header>
<main><section class="card"><h2>__LIST_LABEL__</h2><div class="items">__BUTTONS__</div></section>
<section class="card"><h2>__ITEM_NAME__</h2><div class="banner">Record <b>__ITEM_ID__</b> · Active work area <b>__PANEL_LABEL__</b></div>
<div class="tabs"><button class="tab __SEL_A__" data-panel="A">__LABEL_A__</button><button class="tab __SEL_B__" data-panel="B">__LABEL_B__</button></div>
<div class="source"><b>Source information</b><br>__DETAILS__</div>
__ROOMS__
__COPY_BUTTON__
<div id="form" class="form">__FIELDS__<button id="save">Save record</button></div><div id="statusmsg" class="status"></div>
<div class="hint">The work area and current record are shared at this workstation. Verify both before saving.</div></section></main>
<script>
const initialRev=__REV__;
async function refresh(){try{let r=await fetch('/state');let d=await r.json();if(d.desk.rev!==initialRev)location.reload()}catch(e){}}
document.querySelectorAll('.item').forEach(b=>b.onclick=async()=>{await fetch('/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});location.reload()});
document.querySelectorAll('.tab').forEach(b=>b.onclick=async()=>{await fetch('/panel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({panel:b.dataset.panel})});location.reload()});
document.querySelector('#save').onclick=async()=>{let values={};document.querySelectorAll('#form input,#form select').forEach(e=>{if(e.id.startsWith('f-'))values[e.id.slice(2)]=e.value});let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});let d=await r.json();document.querySelector('#statusmsg').textContent=d.message;setTimeout(()=>location.reload(),500)};
let cb=document.querySelector('#copy-ref');if(cb)cb.onclick=async()=>{let v=cb.dataset.ref;try{await navigator.clipboard.writeText(v)}catch(e){let t=document.createElement('textarea');t.value=v;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove()}cb.textContent='Reference copied'};
setInterval(refresh,800);
</script></body></html>'''
def esc(s):
 return str(s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;')
def dbcon():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c
def current_state(c):
 desk=dict(c.execute('SELECT * FROM desk WHERE id=1').fetchone())
 rows=[dict(r) for r in c.execute('SELECT * FROM items ORDER BY rowid')]
 return {'desk':desk,'items':rows}
def render(d):
 desk=d['desk']; panel=desk['active_panel']; cfg=CONFIG['panels'][panel]
 visible=[r for r in d['items'] if r['kind'] in (panel,'both')]
 active=next((r for r in visible if r['id']==desk['active_id']),visible[0] if visible else None)
 if active is None:return '<h1>Empty worklist</h1>'
 saved=json.loads(active['data_'+panel.lower()] or '{}')
 buttons=''.join('<button class="item '+('sel' if r['id']==active['id'] else '')+'" data-id="'+esc(r['id'])+'"><b>'+esc(r['name'])+'</b><small>'+esc(r['id'])+'</small></button>' for r in visible)
 fields=[]
 for f in cfg['fields']:
  value=saved.get(f['key'],'')
  if f['type']=='select':
   opts='<option value=""></option>'+''.join('<option value="'+esc(x)+'" '+('selected' if str(value)==str(x) else '')+'>'+esc(x)+'</option>' for x in f['options'])
   control='<select id="f-'+esc(f['key'])+'">'+opts+'</select>'
  else:
   typ=f['type'] if f['type'] in ('text','date','number') else 'text'
   control='<input type="'+typ+'" id="f-'+esc(f['key'])+'" value="'+esc(value)+'">'
  fields.append('<label>'+esc(f['label'])+control+'</label>')
 copy=('<button id="copy-ref" data-ref="'+esc(active['clip_ref'])+'">Copy source reference</button>' if active['clip_ref'] else '')
 room_block=''
 if CONFIG.get('name')=='v4':
  vals=[]
  for r in d['items']:
   if r['kind']=='B':
    fact=json.loads(r['facts'] or '{}'); saved_room=json.loads(r['data_b'] or '{}')
    vals.append(esc(r['id'])+' · cap '+str(fact.get('capacity','?'))+' · '+esc(saved_room.get('status','OPEN')))
  room_block='<div class="source"><b>Room capacity and live status</b><br>'+ '<br>'.join(vals) + '</div>'
 vals={'__TITLE__':esc(CONFIG['title']),'__SUBTITLE__':esc(CONFIG['subtitle']),'__LIST_LABEL__':esc(cfg['list_label']),
 '__BUTTONS__':buttons,'__ITEM_NAME__':esc(active['name']),'__ITEM_ID__':esc(active['id']),'__PANEL_LABEL__':esc(cfg['label']),
 '__SEL_A__':'sel' if panel=='A' else '', '__SEL_B__':'sel' if panel=='B' else '',
 '__LABEL_A__':esc(CONFIG['panels']['A']['label']),'__LABEL_B__':esc(CONFIG['panels']['B']['label']),
 '__DETAILS__':esc(active['details']),'__ROOMS__':room_block,'__COPY_BUTTON__':copy,'__FIELDS__':''.join(fields),'__REV__':str(desk['rev'])}
 page=PAGE_HTML
 for k,v in vals.items():page=page.replace(k,v)
 return page
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,body,typ='application/json',status=200):
  b=body.encode();self.send_response(status);self.send_header('Content-Type',typ+'; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  c=dbcon();d=current_state(c);c.close();p=urlparse(self.path).path
  if p=='/state':self.send(json.dumps(d,ensure_ascii=False))
  elif p in ('/','/desk'):self.send(render(d),'text/html')
  else:self.send('{}',status=404)
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));payload=json.loads(self.rfile.read(n) or b'{}');c=dbcon();desk=c.execute('SELECT * FROM desk WHERE id=1').fetchone();p=urlparse(self.path).path;msg='Saved.'
  if p=='/panel':
   panel=payload.get('panel','A')
   if panel not in ('A','B'):panel='A'
   row=c.execute("SELECT id FROM items WHERE kind IN (?, 'both') ORDER BY rowid LIMIT 1",(panel,)).fetchone()
   if row:c.execute('UPDATE desk SET active_panel=?,active_id=?,rev=rev+1 WHERE id=1',(panel,row['id']))
  elif p=='/select':
   row=c.execute("SELECT id FROM items WHERE id=? AND kind IN (?, 'both')",(payload.get('id',''),desk['active_panel'])).fetchone()
   if row:c.execute('UPDATE desk SET active_id=?,rev=rev+1 WHERE id=1',(row['id'],))
  elif p=='/save':
   key='data_'+desk['active_panel'].lower();row=c.execute('SELECT * FROM items WHERE id=?',(desk['active_id'],)).fetchone()
   if row:
    old=json.loads(row[key] or '{}');allowed={f['key'] for f in CONFIG['panels'][desk['active_panel']]['fields']}
    old.update({k:str(v) for k,v in payload.items() if k in allowed})
    c.execute('UPDATE items SET '+key+'=?,version=version+1 WHERE id=?',(json.dumps(old,ensure_ascii=False),desk['active_id']))
    c.execute('INSERT INTO events(item_id,panel,payload) VALUES(?,?,?)',(desk['active_id'],desk['active_panel'],json.dumps(payload,ensure_ascii=False,sort_keys=True)))
    c.execute('UPDATE desk SET rev=rev+1 WHERE id=1');msg='Saved under '+desk['active_id']+' in '+desk['active_panel']+'.'
  c.commit();c.close();self.send(json.dumps({'message':msg},ensure_ascii=False))
def main():
 global DB
 a=argparse.ArgumentParser();a.add_argument('--db',required=True);a.add_argument('--port',type=int,default=8139);x=a.parse_args();DB=x.db
 ThreadingHTTPServer(('127.0.0.1',x.port),Handler).serve_forever()
if __name__=='__main__':main()
