from __future__ import annotations
import csv,sqlite3
from pathlib import Path
from pipeline.grade import make_grade
def rows(path):
 try:
  with Path(path).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
 except OSError:return []
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root)
 try:
  c=sqlite3.connect((root/"erp_ledger.db").resolve().as_uri()+"?mode=ro",uri=True);c.row_factory=sqlite3.Row
  invoices={r["invoice_id"]:dict(r) for r in c.execute("SELECT * FROM invoices")};payments={k:sum(x["amount"] for x in c.execute("SELECT amount FROM payments WHERE invoice_id=? AND state='POSTED'",(k,))) for k in invoices};stock={r["sku"]:dict(r) for r in c.execute("SELECT * FROM inventory")};adjust={r["sku"]:dict(r) for r in c.execute("SELECT * FROM stock_adjustments")};adjustment_count=c.execute("SELECT COUNT(*) FROM stock_adjustments").fetchone()[0];tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")};c.close()
 except sqlite3.Error:invoices={};payments={};stock={};adjust={};adjustment_count=0;tables=set()
 # PAID and SETTLED denote fully settled invoices in this public contract;
 # payment sums remain mandatory, so this does not excuse partial payment.
 raw_invoice_statuses={key:row.get('status') for key,row in invoices.items()}
 for row in invoices.values():
  if row.get('status')=='PAID':row['status']='SETTLED'
 ar_expected={"AR-501":("SETTLED",1000),"AR-502":("PARTIAL",400),"AR-503":("OPEN",0)};inv_expected={"SKU-A":-2,"SKU-B":6,"SKU-C":-9};aok=all(i in invoices and invoices[i]["status"]==v[0] and payments.get(i)==v[1] for i,v in ar_expected.items());bok=adjustment_count==3 and all(s in stock and stock[s]["adjustment"]==d and stock[s]["state"]=="RECONCILED" and adjust.get(s,{}).get("quantity_delta")==d and bool(adjust.get(s,{}).get("source_note")) for s,d in inv_expected.items());out=root.parent/"guest-output";ar=rows(out/"ar_reconciliation.csv");ir=rows(out/"inventory_reconciliation.csv");aexp={r.get("invoice_id"):dict(r,status="SETTLED" if r.get("status")=="PAID" else r.get("status")) for r in ar};bexp={r.get("sku"):r for r in ir}
 try:aexport=set(aexp)==set(ar_expected) and all(float(aexp[k].get("posted_payment_total",-1))==v[1] and aexp[k].get("status")==v[0] for k,v in ar_expected.items())
 except (TypeError,ValueError):aexport=False
 raw_export_statuses={row.get('invoice_id'):row.get('status') for row in ar}
 raw_states_consistent=all(key in raw_export_statuses and raw_export_statuses[key]==raw_invoice_statuses.get(key) for key in ar_expected)
 aexport=aexport and raw_states_consistent
 try:bexport=set(bexp)==set(inv_expected) and all(int(bexp[k].get("adjustment",999))==d for k,d in inv_expected.items())
 except (TypeError,ValueError):bexport=False
 ac=[{"id":"A01","weight":.7,"passed":aok,"required":True,"evidence":{"three_invoice_states_and_payment_totals_valid":aok}},{"id":"A02","weight":.3,"passed":aexport,"required":True,"evidence":{"ar_csv_exact":aexport,"raw_db_csv_statuses_match":raw_states_consistent,"raw_db_statuses":raw_invoice_statuses,"raw_csv_statuses":raw_export_statuses}}];bc=[{"id":"B01","weight":.7,"passed":bok,"required":True,"evidence":{"three_inventory_adjustments_valid":bok}},{"id":"B02","weight":.3,"passed":bexport,"required":True,"evidence":{"inventory_csv_exact":bexport}}];health=receipt.get("http_endpoints",{}).get("erp_health",{}).get("status_code")==200;j=[{"id":"J01","weight":1,"passed":aok and bok and raw_states_consistent,"required":True,"evidence":{"both_ledgers_reconciled":aok and bok,"raw_db_csv_statuses_match":raw_states_consistent}},{"id":"J02","weight":1,"passed":health and {"invoices","payments","inventory","stock_adjustments"}.issubset(tables),"required":True,"evidence":{"audit_service_and_all_tables_present":health and {"invoices","payments","inventory","stock_adjustments"}.issubset(tables)}}]
 return make_grade(case_id="BC-17",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=j,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-17 host SQLite snapshot and CSV recomputation"})
