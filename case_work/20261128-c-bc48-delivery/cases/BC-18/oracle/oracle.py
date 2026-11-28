from __future__ import annotations
import json,sqlite3
from pathlib import Path
from pipeline.grade import make_grade

A={"SEC-102":"Security Response","ACC-104":"Identity Operations","SEC-109":"Endpoint Security"};B={"DAT-203":"Data Platform","PERF-207":"Performance Engineering","DAT-212":"Data Platform"}
def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";events=[]
 try:events=[json.loads(x) for x in (root/"workflow_events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):pass
 try:
  c=sqlite3.connect((root/"tickets.db").resolve().as_uri()+"?mode=ro",uri=True);c.row_factory=sqlite3.Row;tickets={r["ticket_id"]:dict(r) for r in c.execute("SELECT * FROM tickets")};approvals={r["ticket_id"]:dict(r) for r in c.execute("SELECT * FROM approvals")};c.close()
 except sqlite3.Error:tickets={};approvals={}
 def tickets_ok(targets):
  for tid,assignee in targets.items():
   r=tickets.get(tid,{});a=approvals.get(tid,{});ev=json.loads(r.get("evidence_json") or "{}")
   if r.get("status")!="APPROVED" or not str(r.get("assignee","")).strip() or not all(ev.get(x) for x in ("source_ref","impact","root_cause")) or a.get("status")!="APPROVED":return False
   category={'SEC':'security','ACC':'access','DAT':'data','PERF':'performance'}.get(tid.split('-')[0])
   if r.get('category')!=category or any(ev.get(key)!=r.get(source) for key,source in [('source_ref','source_ref'),('impact','impact'),('root_cause','root_cause_hint')]):return False
   rows=[x for x in events if x.get("ticket_id")==tid];decisions=[x.get("decision") for x in rows if x.get("event")=="REVIEW"]
   if "REJECTED" not in decisions or "READY" not in decisions or not any(x.get("event")=="APPROVED" for x in rows):return False
  return True
 ae=_json(out/"security_access_approvals.json").get("tickets",[]);be=_json(out/"data_performance_approvals.json").get("tickets",[]);ax={x.get("ticket_id"):x for x in ae};bx={x.get("ticket_id"):x for x in be};aexp=set(ax)==set(A) and all(ax[k].get("status")=="APPROVED" and bool(str(ax[k].get("assignee","")).strip()) and ax[k].get("assignee")==tickets.get(k,{}).get("assignee") for k,v in A.items());bexp=set(bx)==set(B) and all(bx[k].get("status")=="APPROVED" and bool(str(bx[k].get("assignee","")).strip()) and bx[k].get("assignee")==tickets.get(k,{}).get("assignee") for k,v in B.items());aok=tickets_ok(A);bok=tickets_ok(B);health=receipt.get("http_endpoints",{}).get("ticket_health",{}).get("status_code")==200
 ac=[{"id":"A01","weight":.7,"passed":aok,"required":True,"evidence":{"three_phase2_security_access_approvals_valid":aok}},{"id":"A02","weight":.3,"passed":aexp,"required":True,"evidence":{"export_exact":aexp}}];bc=[{"id":"B01","weight":.7,"passed":bok,"required":True,"evidence":{"three_phase2_data_performance_approvals_valid":bok}},{"id":"B02","weight":.3,"passed":bexp,"required":True,"evidence":{"export_exact":bexp}}];joint=[{"id":"J01","weight":1,"passed":aok and bok,"required":True,"evidence":{"all_six_tickets_have_two_phase_approval":aok and bok}},{"id":"J02","weight":1,"passed":health,"required":True,"evidence":{"ticket_service_health_200":health}}]
 return make_grade(case_id="BC-18",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-18 host SQLite ticket state and workflow receipt grader"})
