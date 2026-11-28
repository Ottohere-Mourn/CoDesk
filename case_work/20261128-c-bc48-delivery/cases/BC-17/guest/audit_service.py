from __future__ import annotations
import argparse,json,sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
PAGE="<!doctype html><meta charset='utf-8'><title>ERP Reconciliation</title><h1>ERP Reconciliation Audit</h1><p>Accounts receivable <a href='/audit/ar'>view</a></p><p>Inventory <a href='/audit/inventory'>view</a></p>"
def query(root,sql,args=()):
 c=sqlite3.connect(root/"erp_ledger.db");c.row_factory=sqlite3.Row;rows=[dict(x) for x in c.execute(sql,args)];c.close();return rows
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  b=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/":return self.send(200,PAGE)
  if self.path=="/health":return self.send(200,{"status":"ok"})
  if self.path=="/audit/ar":return self.send(200,{"invoices":query(self.server.root,"SELECT * FROM invoices ORDER BY invoice_id"),"summary":query(self.server.root,"SELECT * FROM ar_summary ORDER BY status")})
  if self.path=="/audit/inventory":return self.send(200,{"inventory":query(self.server.root,"SELECT * FROM inventory ORDER BY sku"),"adjustments":query(self.server.root,"SELECT * FROM stock_adjustments ORDER BY adjustment_id")})
  return self.send(404,{"error":"not_found"})
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();s=ThreadingHTTPServer(("127.0.0.1",18117),Handler);s.root=Path(a.root);s.serve_forever()
if __name__=="__main__":main()
