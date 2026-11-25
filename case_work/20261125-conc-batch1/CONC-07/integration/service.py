"""SupplyPortal and AdPulse with a shared rollback-journal SQLite database."""
from __future__ import annotations
import argparse,base64,csv,hashlib,io,json,secrets,sqlite3,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
SUP_IDS=[f"SUP-{i:02d}" for i in range(1,7)];CH_IDS=[f"CH-{i:02d}" for i in range(1,7)]
class State:
    def __init__(self,assets:Path,db:Path,statefile:Path):
        self.assets,self.db,self.path=assets,db,statefile;self.token=secrets.token_urlsafe(24);self.lock=threading.Lock();self.data={"a_events":[],"b_events":[],"finalize_events":[],"sqlite_busy_count":0,"viewport_events":[]};self.init_db()
    def init_db(self):
        self.db.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(self.db,timeout=5);c.execute("PRAGMA journal_mode=DELETE");c.execute("CREATE TABLE IF NOT EXISTS supplier_settlements(supplier_id TEXT PRIMARY KEY,gross_amount REAL,deduction REAL,net_payable REAL,has_dispute INTEGER,batch_code TEXT)");c.execute("CREATE TABLE IF NOT EXISTS campaign_audits(channel_id TEXT PRIMARY KEY,spend REAL,revenue REAL,roi REAL,alert_flag INTEGER,lock_code TEXT)");c.commit();c.close()
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);p=self.path.with_suffix('.tmp');p.write_text(json.dumps(self.data,indent=2),encoding='utf-8');p.replace(self.path)
SUP_PAGE='''<!doctype html><meta charset="utf-8"><title>SupplyPortal | Q4 Settlements</title><style>body{font:15px Arial;margin:22px;background:#f3f6f8;color:#1c3445}header{background:#244a42;color:white;padding:16px;border-radius:8px}.row{background:white;margin:9px 0;padding:12px;border:1px solid #cad5da;border-radius:7px}input,button{padding:8px;margin:4px}button{cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.figure{max-width:320px}</style><header><h1>SupplyPortal Q4 Settlement Batch</h1><p>Review source invoices and quality evidence before finalizing six settlements.</p></header><button onclick="location.href='/a/suppliers.csv'">Download Supplier CSV</button> <button onclick="location.href='/a/figure/settlement_by_vendor.png'">Download Figure</button><main class="grid">__ROWS__</main><section class="row"><h2>Settlement entry</h2><form id="entry"><select name="supplier_id">__OPTIONS__</select><label>Deduction <input name="deduction" type="number" step="0.01" value="0"></label><label>Net payable <input name="net_payable" type="number" step="0.01"></label><label>Dispute flag <select name="has_dispute"><option value="0">No</option><option value="1">Yes</option></select></label><input name="gross_amount" type="number" step="0.01"><input name="evidence" type="file" accept="image/png"><button>Write settlement row</button></form><button id="finalize">Finalize Batch</button><output id="msg"></output></section><script>
const f=document.querySelector('#entry');f.onsubmit=async e=>{e.preventDefault();let d=Object.fromEntries(new FormData(f));let file=f.elements.evidence.files[0];if(file)d.image=await new Promise(ok=>{let r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.readAsDataURL(file)});let q=await fetch('/api/a/settle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});document.querySelector('#msg').textContent=await q.text()};document.querySelector('#finalize').onclick=async()=>{let q=await fetch('/api/a/finalize',{method:'POST'});document.querySelector('#msg').textContent=await q.text()};
</script>'''
AD_PAGE='''<!doctype html><meta charset="utf-8"><title>AdPulse | Campaign Operations</title><style>body{font:15px Arial;margin:22px;background:#f4f7fb;color:#1d344c}header{background:#284767;color:white;padding:16px;border-radius:8px}.panel{background:white;margin:12px 0;padding:14px;border:1px solid #cbd5e1;border-radius:8px}.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.tile{border:1px solid #d7e0e8;padding:8px;background:#fff}.tile img{max-width:100%;height:160px;object-fit:contain}button,input,select{padding:8px;margin:4px}.notice{color:#b91c1c;font-weight:bold}</style><header><h1>AdPulse Campaign Operations</h1><p>Check landing pages, campaign performance, and budget alerts.</p></header><main class="panel"><div id="notice" class="notice"></div><div id="dashboard" class="tiles">__CHANNELS__</div><p><button onclick="location.href='/b/figure/channel_roi.png'">Download Figure</button><button onclick="location.href='/b/figure/budget_variance.png'">Download Figure</button><button onclick="location.href='/b/figure/revenue_mix.png'">Download Figure</button></p><button id="hover">Record dashboard review</button></main><section class="panel"><h2>Campaign entry</h2><form id="e"><select name="channel_id">__OPTIONS__</select><input name="spend" placeholder="Spend"><input name="revenue" placeholder="Revenue"><input name="roi" placeholder="ROI"><select name="alert_flag"><option value="0">Within plan</option><option value="1">Review budget</option></select><input name="lock_code" placeholder="(assigned at lock)"><label>LP-1 image <input id="m1" type="file" accept="image/png"></label><label>LP-2 image <input id="m2" type="file" accept="image/png"></label><button>Write campaign row</button></form><button id="lock">Lock Report</button><p id="msg"></p></section><script>
 function widthCheck(){let ok=window.outerWidth>=1600;document.querySelector('#notice').textContent=ok?'Wide dashboard review enabled.':'Expand the browser window to at least 1600 pixels to review all channels.';document.querySelector('#dashboard').style.display=ok?'grid':'none'}window.addEventListener('resize',widthCheck);widthCheck();let e=document.querySelector('#e');e.onsubmit=async x=>{x.preventDefault();let d=Object.fromEntries(new FormData(e));d.mobile_pngs=[];for(const id of ['m1','m2']){let f=document.getElementById(id).files[0];if(f)d.mobile_pngs.push(await new Promise(ok=>{let r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.readAsDataURL(f)}))}let r=await fetch('/api/b/campaign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});document.querySelector('#msg').textContent=await r.text()};document.querySelector('#hover').onclick=async()=>{for(let i=1;i<=6;i++)await fetch('/b/hover?width='+window.outerWidth+'&channel=CH-'+String(i).padStart(2,'0'));document.querySelector('#msg').textContent='Dashboard review recorded.'};document.querySelector('#lock').onclick=async()=>{let r=await fetch('/api/b/lock',{method:'POST'});document.querySelector('#msg').textContent=await r.text()};
</script>'''
def handler(state:State):
 class H(BaseHTTPRequestHandler):
  def log_message(self,*_):pass
  def send(self,b,ctype='text/html; charset=utf-8',code=200,attachment=None):
   self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('Set-Cookie',f'conc07={state.token}; HttpOnly; SameSite=Lax; Path=/')
   if attachment:self.send_header('Content-Disposition',f'attachment; filename="{attachment}"')
   self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def auth(self):return f'conc07={state.token}' in self.headers.get('Cookie','')
  def body(self):return json.loads(self.rfile.read(min(int(self.headers.get('Content-Length','0')),10000000)).decode())
  def record(self,role,event):
   with state.lock:state.data[role+'_events'].append(event);state.save()
  def do_GET(self):
   from urllib.parse import parse_qs,urlsplit
   u=urlsplit(self.path);p=u.path;q=parse_qs(u.query);port=self.server.server_port
   if p=='/health':return self.send(b'ok','text/plain')
   if not self.auth():return self.send(b'authentication required','text/plain',401)
   if port==18131 and p=='/':
    imgs=''.join(f'<article class="row"><b>{sid}</b>  -  invoice detail available in downloaded CSV. <img class="figure" src="/a/qc/{sid}.png" alt="Quality review {sid}"></article>' for sid in SUP_IDS)
    opts=''.join(f'<option>{sid}</option>' for sid in SUP_IDS);return self.send(SUP_PAGE.replace('__ROWS__',imgs).replace('__OPTIONS__',opts).encode())
   if port==18131 and p=='/a/suppliers.csv':
    f=state.assets/'supplier_master.csv';self.record('a',{'type':'download_csv'});return self.send(f.read_bytes(),'text/csv',attachment='supplier_master.csv')
   if port==18131 and p.startswith('/a/qc/'):
    f=state.assets/'qc_sheets'/Path(p).name
    if f.is_file():return self.send(f.read_bytes(),'image/png')
   if port==18131 and p.startswith('/a/figure/'):
    f=state.assets/Path(p).name
    if f.is_file():self.record('a',{'type':'download_figure','name':f.name});return self.send(f.read_bytes(),'image/png',attachment='figure.png')
   if port==18132 and p=='/mobile-check':
    return self.send(b'''<!doctype html><meta charset="utf-8"><title>AdPulse Mobile Landing Review</title><style>body{font:16px Arial;background:#eef4f9;color:#19344d;margin:18px}.lp{background:white;margin:14px auto;padding:20px;border-radius:12px;max-width:340px}button{padding:8px}</style><h1>Mobile Landing Page Inspection</h1><article class="lp"><h2>LP-1 | Spring Essentials</h2><p>Clear product hierarchy, readable offer, and a single primary action.</p><button onclick="fetch('/b/mobile?width='+outerWidth+'&height='+outerHeight).then(()=>location.href='/b/mobile/mobile_lp_1.png')">Verify and save LP-1</button></article><article class="lp"><h2>LP-2 | Weekend Travel</h2><p>Compact itinerary, accessible booking action, and responsive supporting content.</p><button onclick="fetch('/b/mobile?width='+outerWidth+'&height='+outerHeight).then(()=>location.href='/b/mobile/mobile_lp_2.png')">Verify and save LP-2</button></article>''')
   if port==18132 and p=='/dashboard':
    imgs=''.join(f'<article class="tile"><b>{ch}</b><img src="/b/roi/{ch}.png" alt="Peak ROI for {ch}"></article>' for ch in CH_IDS);opts=''.join(f'<option>{ch}</option>' for ch in CH_IDS);return self.send(AD_PAGE.replace('__CHANNELS__',imgs).replace('__OPTIONS__',opts).encode())
   if port==18132 and p.startswith('/b/roi/'):
    f=state.assets/Path(p).name
    if f.is_file():self.record('b',{'type':'roi_view','channel':Path(p).stem});return self.send(f.read_bytes(),'image/png')
   if port==18132 and p.startswith('/b/figure/'):
    f=state.assets/Path(p).name
    if f.is_file():self.record('b',{'type':'download_figure','name':f.name});return self.send(f.read_bytes(),'image/png',attachment='figure.png')
   if port==18132 and p.startswith('/b/mobile/'):
    name=Path(p).name
    if name in {'mobile_lp_1.png','mobile_lp_2.png'}:
     return self.send((state.assets/name).read_bytes(),'image/png',attachment=name)
   if port==18132 and p=='/b/mobile':
    try:w=int(q.get('width',['0'])[0]);h=int(q.get('height',['0'])[0])
    except ValueError:w=h=0
    self.record('b',{'type':'mobile_viewport_check','width':w,'height':h});return self.send(b'recorded','text/plain')
   if port==18132 and p=='/b/hover':
    try:w=int(q.get('width',['0'])[0])
    except ValueError:w=0
    self.record('b',{'type':'dashboard_hover','width':w,'channel':q.get('channel',[''])[0]});return self.send(b'recorded','text/plain')
   return self.send(b'not found','text/plain',404)
  def do_POST(self):
   if not self.auth():return self.send(b'unauthorized','text/plain',401)
   try:d=self.body()
   except Exception:return self.send(b'invalid request','text/plain',400)
   p=self.path;role='a' if p.startswith('/api/a/') else 'b';table='supplier_settlements' if role=='a' else 'campaign_audits';key='supplier_id' if role=='a' else 'channel_id';ident=d.get(key,'')
   if p in ('/api/a/settle','/api/b/campaign'):
    try:
     cols=['supplier_id','gross_amount','deduction','net_payable','has_dispute','batch_code'] if role=='a' else ['channel_id','spend','revenue','roi','alert_flag','lock_code']
     vals=[d.get(x) for x in cols];c=sqlite3.connect(state.db,timeout=3);c.execute('PRAGMA journal_mode=DELETE');c.execute(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",vals);c.commit();c.close()
     digest=''
     if d.get('image'):
      raw=base64.b64decode(d['image']);digest=hashlib.sha256(raw).hexdigest();out=state.assets/'uploaded';out.mkdir(exist_ok=True);(out/f'{ident}.png').write_bytes(raw)
     if role=='b' and d.get('mobile_pngs'):
      out=state.assets/'uploaded';out.mkdir(exist_ok=True)
      for i,value in enumerate(d['mobile_pngs'][:2],1):
       raw=base64.b64decode(value);dig=hashlib.sha256(raw).hexdigest();(out/f'mobile_lp_{i}.png').write_bytes(raw);state.data.setdefault('mobile_uploads',[]).append({'name':f'mobile_lp_{i}.png','sha256':dig})
     self.record(role,{'type':'row_saved','id':ident,'image_sha256':digest});return self.send(b'Entry saved.','text/plain')
    except sqlite3.OperationalError as e:
     with state.lock:state.data['sqlite_busy_count']+=1;state.save()
     return self.send(str(e).encode(),'text/plain',503)
   if p in ('/api/a/finalize','/api/b/lock'):
    code=('BATCH-'+secrets.token_hex(4).upper()) if role=='a' else ('LOCK-'+secrets.token_hex(4).upper())
    try:
     c=sqlite3.connect(state.db,timeout=5);c.execute('PRAGMA journal_mode=DELETE');c.execute('BEGIN IMMEDIATE');time.sleep(2.0);n=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
     if n<6:c.rollback();c.close();return self.send(b'Complete six rows before finalizing.','text/plain',409)
     c.execute(f'UPDATE {table} SET {"batch_code" if role=="a" else "lock_code"}=?',(code,));c.commit();c.close();ev={'type':'finalize_success' if role=='a' else 'lock_success','code':code,'rows':n}
     with state.lock:state.data['finalize_events'].append(ev);state.save()
     return self.send(json.dumps({'success':True,'code':code}).encode(),'application/json')
    except sqlite3.OperationalError as e:
     with state.lock:state.data['sqlite_busy_count']+=1;state.save()
     return self.send(str(e).encode(),'text/plain',503)
   return self.send(b'not found','text/plain',404)
 return H
def serve(assets:Path,db:Path,statefile:Path):
 s=State(assets,db,statefile);h=handler(s);servers=[ThreadingHTTPServer(('127.0.0.1',p),h) for p in (18131,18132)];ts=[threading.Thread(target=x.serve_forever,daemon=True) for x in servers];[t.start() for t in ts];[t.join() for t in ts]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--db',type=Path,default=Path('/home/user/workspace/shared/enterprise_ops.db'));p.add_argument('--state',type=Path,default=Path('/tmp/conc07-runtime/state.json'));x=p.parse_args();serve(x.assets,x.db,x.state)
