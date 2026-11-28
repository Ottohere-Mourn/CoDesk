from __future__ import annotations
import argparse,json,sqlite3
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root).resolve();dbpath=root/'data/closeout.db'
 class H(BaseHTTPRequestHandler):
  def log_message(self,*x):pass
  def sendj(self,obj,code=200):
   b=json.dumps(obj).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def do_GET(self):
   if self.path=='/closeout':self.sendj({'desk':'Quarter Closeout','actions':['preview','commit','status']})
   elif self.path=='/status':
    with sqlite3.connect(dbpath) as c:r=c.execute('SELECT revision FROM dashboard_revision').fetchone()[0];n=c.execute('SELECT count(*) FROM reconciliation').fetchone()[0]
    self.sendj({'revision':r,'reconciled':n})
   else:self.send_error(404)
  def do_POST(self):
   try:d=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));scope=d.get('scope');rows=d.get('decisions',[])
   except (json.JSONDecodeError,ValueError):self.send_error(400);return
   if scope not in ('subscription','fulfillment'):self.send_error(400);return
   with sqlite3.connect(dbpath) as c:
    ids={x[0] for x in c.execute('SELECT line_id FROM statement_line WHERE business_line=? AND period="2026-Q4"',(scope,))};bad=[x for x in rows if x.get('line_id') not in ids or x.get('decision') not in ('matched','adjusted','disputed') or not x.get('reason')]
    if self.path=='/preview':self.sendj({'valid':not bad,'missing_ids':sorted(ids-{x.get('line_id') for x in rows}),'invalid':bad,'revision':c.execute('SELECT revision FROM dashboard_revision').fetchone()[0]});return
    if self.path!='/commit' or bad:self.sendj({'error':'invalid_decisions','invalid':bad},409);return
    rev=c.execute('SELECT revision FROM dashboard_revision').fetchone()[0]+1
    for x in rows:c.execute('INSERT OR REPLACE INTO reconciliation VALUES(?,?,?,?,?)',(x['line_id'],x['decision'],float(x['amount']),x['reason'],rev))
    c.execute('UPDATE dashboard_revision SET revision=?',(rev,));c.execute('INSERT INTO audit_event VALUES(?,?,?,?)',(rev,scope,'commit',len(rows)));c.commit()
   self.sendj({'status':'committed','revision':rev,'rows':len(rows)})
 HTTPServer(('127.0.0.1',18224),H).serve_forever()
if __name__=='__main__':main()
