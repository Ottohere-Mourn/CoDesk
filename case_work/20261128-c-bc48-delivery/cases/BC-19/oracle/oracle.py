from __future__ import annotations
import hashlib,json
from pathlib import Path
from pipeline.grade import make_grade

def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
RISK={"velocity_window_s":60,"min_risk_to_review":.82,"max_attempts":5,"blocked_region":"ZZ"};ROUTES={"/orders":{"path":"/orders","primary":"orders-v3","fallback":"orders-v2","timeout_s":6},"/catalog":{"path":"/catalog","primary":"catalog-v2","fallback":"catalog-v1","timeout_s":3},"/profile":{"path":"/profile","primary":"profile-v1","fallback":"profile-cache","timeout_s":4}}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";doc=_json(root/"rules.yaml");risk=doc.get("risk",{});routes={x.get("path"):x for x in doc.get("routing",{}).get("rules",[])};risk_ok=risk==RISK;route_ok=routes==ROUTES;ra=_json(out/"risk_report.json");rb=_json(out/"routing_report.json");a_report=len(ra.get("results",[]))==5 and all(x.get("passed") is True for x in ra.get("results",[]));b_report=len(rb.get("results",[]))==3 and all(x.get("passed") is True for x in rb.get("results",[]));active=receipt.get("http_endpoints",{}).get("active_rules",{}).get("body_json",{});active_ok=active==doc;reloads=receipt.get("http_endpoints",{}).get("reload_events",{}).get("body_json",{});reloaded=hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest() in json.dumps(reloads)
 ac=[{"id":"A01","weight":.65,"passed":risk_ok,"required":True,"evidence":{"risk_rule_exact":risk_ok}},{"id":"A02","weight":.35,"passed":a_report,"required":True,"evidence":{"five_risk_cases_passed_and_exported":a_report}}];bc=[{"id":"B01","weight":.65,"passed":route_ok,"required":True,"evidence":{"three_route_rules_exact":route_ok}},{"id":"B02","weight":.35,"passed":b_report,"required":True,"evidence":{"three_route_cases_passed_and_exported":b_report}}];health=receipt.get("http_endpoints",{}).get("rule_health",{}).get("status_code")==200;j=[{"id":"J01","weight":1,"passed":active_ok and reloaded,"required":True,"evidence":{"reloaded_runtime_matches_final_disk_rules":active_ok and reloaded}},{"id":"J02","weight":1,"passed":health,"required":True,"evidence":{"rule_engine_health_200":health}}]
 return make_grade(case_id="BC-19",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=j,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-19 host rule document, evaluation report and reload receipt grader"})
