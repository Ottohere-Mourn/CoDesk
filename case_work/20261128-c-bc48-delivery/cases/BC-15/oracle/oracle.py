from __future__ import annotations
import json
from pathlib import Path
from pipeline.grade import make_grade

def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";env={}
 try:
  for line in (root/".env").read_text(encoding="utf-8").splitlines():
   if "=" in line:k,v=line.split("=",1);env[k]=v
 except OSError:pass
 cfg=_json(root/"settings.json");fa=_json(out/"frontline_check.json");fb=_json(out/"catalog_check.json");audit=receipt.get("http_endpoints",{}).get("git_audit",{}).get("body_json",{});front=receipt.get("http_endpoints",{}).get("frontline_health",{}).get("status_code")==200;cat=receipt.get("http_endpoints",{}).get("catalog_health",{}).get("status_code")==200
 for doc,service in [(fa,'frontline'),(fb,'catalog')]:
  health_row=doc.get('verification',doc.get('health_check',{}))
  if 'health_status' not in doc and health_row.get('url')=='http://127.0.0.1:18115/health/'+service:
   doc['health_status']=health_row.get('status_code',health_row.get('http_status'))
 aok=cfg.get("frontline")=={"route":"/v1/customers","limit":45,"auth":"bearer"} and env.get("SERVICE_A_LIMIT")=="45" and fa.get("health_status")==200 and bool(fa.get("commit_sha"))
 bok=cfg.get("catalog")=={"route":"/v1/catalog","timeout_s":9,"fallback":"cache"} and env.get("SERVICE_B_LIMIT")=="30" and fb.get("health_status")==200 and bool(fb.get("commit_sha"))
 commits=audit.get("commits",[]);messages=[x.split("\t",1)[1] for x in commits if "\t" in x];gitok=audit.get("branch")=="main" and audit.get("working_tree_clean") is True and "BC15-A: configure frontline interface" in messages and "BC15-B: configure catalog interface" in messages
 ac=[{"id":"A01","weight":.55,"passed":cfg.get("frontline")=={"route":"/v1/customers","limit":45,"auth":"bearer"},"required":True,"evidence":{"frontline_config_valid":cfg.get("frontline")=={"route":"/v1/customers","limit":45,"auth":"bearer"}}},{"id":"A02","weight":.2,"passed":env.get("SERVICE_A_LIMIT")=="45","required":True,"evidence":{"service_a_env":env.get("SERVICE_A_LIMIT")}},{"id":"A03","weight":.25,"passed":fa.get("health_status")==200 and bool(fa.get("commit_sha")),"required":True,"evidence":{"health_and_commit_receipt":fa.get("health_status")==200 and bool(fa.get("commit_sha"))}}]
 bc=[{"id":"B01","weight":.55,"passed":cfg.get("catalog")=={"route":"/v1/catalog","timeout_s":9,"fallback":"cache"},"required":True,"evidence":{"catalog_config_valid":cfg.get("catalog")=={"route":"/v1/catalog","timeout_s":9,"fallback":"cache"}}},{"id":"B02","weight":.2,"passed":env.get("SERVICE_B_LIMIT")=="30","required":True,"evidence":{"service_b_env":env.get("SERVICE_B_LIMIT")}},{"id":"B03","weight":.25,"passed":fb.get("health_status")==200 and bool(fb.get("commit_sha")),"required":True,"evidence":{"health_and_commit_receipt":fb.get("health_status")==200 and bool(fb.get("commit_sha"))}}]
 joint=[{"id":"J01","weight":1,"passed":front and cat,"required":True,"evidence":{"both_services_reachable_and_green":front and cat}},{"id":"J02","weight":1,"passed":gitok,"required":True,"evidence":{"main_branch_clean_and_both_named_commits":gitok}}]
 return make_grade(case_id="BC-15",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-15 recovered config, health receipts and service Git audit"})
