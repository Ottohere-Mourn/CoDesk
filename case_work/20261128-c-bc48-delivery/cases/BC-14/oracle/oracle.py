from __future__ import annotations
import json
from pathlib import Path
from pipeline.grade import make_grade

TARGETS={"FL-104":{"status":"IN_PROGRESS","owner":"Maya Chen","priority":"P1","sla":"AT_RISK"},"FL-108":{"status":"RESOLVED","owner":"Jordan Lee","priority":"P2","sla":"WITHIN_SLA"},"FL-112":{"status":"ESCALATED","owner":"Sam Rivera","priority":"P1","sla":"OVERDUE"},"BE-203":{"status":"IN_REVIEW","owner":"Platform On-Call","priority":"P1","sla":"AT_RISK"},"BE-207":{"status":"RESOLVED","owner":"Data Ops","priority":"P2","sla":"WITHIN_SLA"},"BE-211":{"status":"IN_PROGRESS","owner":"Runtime Team","priority":"P1","sla":"OVERDUE"}}
def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def _cards(value):
 if isinstance(value,list):return [row for row in value if isinstance(row,dict)]
 if isinstance(value,dict) and isinstance(value.get("cards"),list):return [row for row in value["cards"] if isinstance(row,dict)]
 return []
def valid_state(cards,ids):
 rows={x.get("id"):x for x in cards if isinstance(x,dict)};return all(k in rows and all((str(rows[k].get(f,"")).strip().upper()==v if f=="sla" else rows[k].get(f)==v) for f,v in target.items()) and bool(str(rows[k].get("resolution","")).strip()) for k,target in ((i,TARGETS[i]) for i in ids))
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";state=_json(root/"board_state.json");state=state if isinstance(state,dict) else {};cards=_cards(state);a_ids=["FL-104","FL-108","FL-112"];b_ids=["BE-203","BE-207","BE-211"];a_export=_cards(_json(out/"frontline_export.json"));b_export=_cards(_json(out/"backend_export.json"));a_ok=valid_state(cards,a_ids);b_ok=valid_state(cards,b_ids)
 exact_a={x.get("id") for x in a_export}==set(a_ids) and valid_state(a_export,a_ids);exact_b={x.get("id") for x in b_export}==set(b_ids) and valid_state(b_export,b_ids)
 excluded_ok=all(next((c.get("status") for c in cards if c.get("id")==x),None)=="DUPLICATE" for x in ["FL-119"]) and next((c.get("status") for c in cards if c.get("id")=="BE-219"),None)=="CANCELLED"
 ac=[{"id":"A01","weight":.65,"passed":a_ok,"required":True,"evidence":{"three_frontline_cards_match_policy":a_ok}},{"id":"A02","weight":.35,"passed":exact_a,"required":True,"evidence":{"frontline_export_exact":exact_a}}]
 bc=[{"id":"B01","weight":.65,"passed":b_ok,"required":True,"evidence":{"three_backend_cards_match_policy":b_ok}},{"id":"B02","weight":.35,"passed":exact_b,"required":True,"evidence":{"backend_export_exact":exact_b}}]
 health=receipt.get("http_endpoints",{}).get("board_health",{}).get("status_code")==200;jc=[{"id":"J01","weight":1,"passed":a_ok and b_ok and excluded_ok,"required":True,"evidence":{"both_queues_saved_and_exclusions_unchanged":a_ok and b_ok and excluded_ok}},{"id":"J02","weight":1,"passed":health and int(state.get("revision",0))>=2,"required":True,"evidence":{"service_health_and_multiple_full_state_saves":health and int(state.get("revision",0))>=2}}]
 return make_grade(case_id="BC-14",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=jc,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-14 host final-state and exact-export verification"})
