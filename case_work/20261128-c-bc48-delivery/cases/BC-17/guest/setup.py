from __future__ import annotations
import argparse,sqlite3,subprocess,sys
from pathlib import Path
INVOICES=[("AR-501","Orion Labs",1000,"OPEN"),("AR-502","Cedar Group",750,"OPEN"),("AR-503","Northstar",420,"OPEN")]
PAYMENTS=[("P-1","AR-501",600,"POSTED"),("P-2","AR-501",400,"POSTED"),("P-3","AR-502",400,"POSTED"),("P-4","AR-502",350,"REVERSED"),("P-5","AR-503",420,"PENDING")]
STOCK=[("SKU-A","WH-EAST",40,38),("SKU-B","WH-EAST",12,18),("SKU-C","WH-WEST",9,0)]
def pdf(path):
 d=b"BT /F1 11 Tf 48 748 Td (LEDGER RECONCILIATION POLICY) Tj 0 -18 Td (Only POSTED payments count toward receivables.) Tj 0 -18 Td (Reconcile each invoice to the sum of posted payments; keep PARTIAL and OPEN states accurate.) Tj 0 -18 Td (Inventory adjustment equals counted quantity minus book quantity.) Tj 0 -18 Td (Every stock correction requires a source note and a unique adjustment ID.) Tj ET";objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(d)).encode()+b" >>\nstream\n"+d+b"\nendstream"];o=bytearray(b"%PDF-1.4\n");off=[0]
 for i,x in enumerate(objs,1):off.append(len(o));o.extend(f"{i} 0 obj\n".encode()+x+b"\nendobj\n")
 pos=len(o);o.extend(f"xref\n0 {len(off)}\n0000000000 65535 f \n".encode());[o.extend(f"{n:010d} 00000 n \n".encode()) for n in off[1:]];o.extend(f"trailer\n<< /Size {len(off)} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n".encode());path.write_bytes(o)
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"erp_reconcile";root.mkdir(parents=True,exist_ok=True);(root/"out").mkdir(exist_ok=True);db=sqlite3.connect(root/"erp_ledger.db");db.executescript("CREATE TABLE invoices(invoice_id TEXT PRIMARY KEY,customer TEXT,amount REAL,status TEXT);CREATE TABLE payments(payment_id TEXT PRIMARY KEY,invoice_id TEXT,amount REAL,state TEXT);CREATE TABLE inventory(sku TEXT PRIMARY KEY,warehouse TEXT,book_qty INTEGER,counted_qty INTEGER,adjustment INTEGER DEFAULT 0,state TEXT DEFAULT 'PENDING');CREATE TABLE stock_adjustments(adjustment_id TEXT PRIMARY KEY,sku TEXT,quantity_delta INTEGER,source_note TEXT);CREATE VIEW ar_summary AS SELECT status,COUNT(*) AS invoice_count,SUM(amount) AS face_value FROM invoices GROUP BY status;")
 db.executemany("INSERT INTO invoices VALUES(?,?,?,?)",INVOICES);db.executemany("INSERT INTO payments VALUES(?,?,?,?)",PAYMENTS);db.executemany("INSERT INTO inventory(sku,warehouse,book_qty,counted_qty) VALUES(?,?,?,?)",STOCK);db.commit();db.close();pdf(root/"reconciliation_rules.pdf")
 if a.start_service:
  log=(root/"audit_service.log").open("ab",buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/"audit_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18117/"],start_new_session=True)
if __name__=="__main__":main()
