from __future__ import annotations
import csv,json
from datetime import date
from pathlib import Path
from pipeline.grade import make_grade

def _rows(path):
 try:
  with Path(path).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
 except OSError:return []
def truth_revenue(path):
 rows=_rows(path);seen=set();regional={};count=refunds=0
 for r in rows:
  if not ("2026-10-01"<=r["invoice_date"]<="2026-12-31"):continue
  if r["status"]=="POSTED":
   if r["invoice_id"] in seen:continue
   seen.add(r["invoice_id"]);count+=1
  elif r["status"]=="REFUND":refunds+=1
  else:continue
  regional[r["region"]]=regional.get(r["region"],0)+int(r["amount_usd"])
 return {"regional_net_usd":regional,"q4_net_usd":sum(regional.values()),"posted_invoice_count":count,"refund_count":refunds}
def truth_retention(path):
 rows=_rows(path);first={}
 for r in rows:
  if r["status"]!="VALID" or r["event_type"]!="signup" or not "2026-10-01"<=r["event_date"]<="2026-10-31":continue
  first[r["user_id"]]=min(first.get(r["user_id"],r["event_date"]),r["event_date"])
 active={"M1":set(),"M2":set()}
 for r in rows:
  if r["status"]!="VALID" or r["event_type"]!="session" or r["user_id"] not in first:continue
  delta=(date.fromisoformat(r["event_date"])-date.fromisoformat(first[r["user_id"]])).days
  if 14<=delta<=30:active["M1"].add(r["user_id"])
  if 31<=delta<=60:active["M2"].add(r["user_id"])
 n=len(first);return {"cohort_size":n,"month_1_active":len(active["M1"]),"month_1_retention_pct":round(100*len(active["M1"])/n,2) if n else 0,"month_2_active":len(active["M2"]),"month_2_retention_pct":round(100*len(active["M2"])/n,2) if n else 0}
def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";files=root.parent/"guest-inputs";ar=truth_revenue(files/"revenue_source.csv");br=truth_retention(files/"product_events.csv");a=_json(out/"revenue_analysis.json");b=_json(out/"retention_analysis.json");pipe=_json(root/"q4_pipeline.json");cells=pipe.get("cells",[]) if isinstance(pipe,dict) else []
 a_cells=[c for c in cells if c.get("section")=="A" and not c.get("error")];b_cells=[c for c in cells if c.get("section")=="B" and not c.get("error")]
 def eq(payload,truth,keys):return all(payload.get(k)==truth.get(k) for k in keys)
 ak=list(ar);bk=list(br);av=eq(a,ar,ak);bv=eq(b,br,bk)
 ac=[{"id":"A01","weight":.50,"passed":av,"required":True,"evidence":{"matched_fields":sum(a.get(k)==ar[k] for k in ak),"expected_fields":len(ak)}},{"id":"A02","weight":.25,"passed":len(a_cells)>=2,"required":True,"evidence":{"successful_section_cells":len(a_cells)}},{"id":"A03","weight":.25,"passed":(root/"kernel_events.jsonl").is_file() and bool(a_cells),"required":True,"evidence":{"kernel_event_log_present":(root/"kernel_events.jsonl").is_file()}}]
 bc=[{"id":"B01","weight":.50,"passed":bv,"required":True,"evidence":{"matched_fields":sum(b.get(k)==br[k] for k in bk),"expected_fields":len(bk)}},{"id":"B02","weight":.25,"passed":len(b_cells)>=2,"required":True,"evidence":{"successful_section_cells":len(b_cells)}},{"id":"B03","weight":.25,"passed":(root/"kernel_events.jsonl").is_file() and bool(b_cells),"required":True,"evidence":{"kernel_event_log_present":(root/"kernel_events.jsonl").is_file()}}]
 service=receipt.get("http_endpoints",{}).get("kernel_health",{}).get("status_code")==200;jc=[{"id":"J01","weight":1,"passed":bool(a_cells and b_cells) and (root/"q4_pipeline.json").is_file(),"required":True,"evidence":{"both_sections_saved":bool(a_cells and b_cells)}},{"id":"J02","weight":1,"passed":service,"required":True,"evidence":{"persistent_kernel_health_200":service}}]
 return make_grade(case_id="BC-11",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=jc,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-11 host deterministic CSV recomputation"})
