"""Host-only BC-07 Oracle for transactional inbound/outbound workflow."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any
from pipeline.grade import make_grade

INBOUND = {"IN-1002":"BIN-A1","IN-1005":"BIN-A2","IN-1009":"BIN-B1","IN-1013":"BIN-B2","IN-1018":"COLD-OV1","IN-1024":"COLD-OV1"}
OUTBOUND = {"OUT-2001":"","OUT-2004":"","OUT-2007":"","OUT-2011":"","OUT-2015":"CUS-OVR-7A","OUT-2020":"CUS-OVR-9C"}

def _check(cid,w,ok,evidence):return {"id":cid,"weight":w,"passed":bool(ok),"score":float(bool(ok)),"required":True,"evidence":evidence}
def _json(p):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return {}
def _rows(db,table):
    try:
        uri=Path(db).resolve().as_uri()+"?mode=ro";c=sqlite3.connect(uri,uri=True);c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute(f"SELECT * FROM {table}")];c.close();return {r["order_id"]:r for r in rows}
    except (OSError,sqlite3.Error):return {}
def _actions(db,kind):
    try:
        uri=Path(db).resolve().as_uri()+"?mode=ro";c=sqlite3.connect(uri,uri=True);rows=c.execute("SELECT kind,token,detail_json FROM actions WHERE kind=?",(kind,)).fetchall();c.close();return rows
    except (OSError,sqlite3.Error):return []

def grade_case(root: str|Path, run_id="offline", database_path: str|Path|None=None):
    root=Path(root);db=Path(database_path) if database_path is not None else root/"rooms.db"; inbound=_rows(db,"inbound");outbound=_rows(db,"outbound")
    audit_a=_json(root/"inbound_audit.json");audit_b=_json(root/"outbound_audit.json")
    a_ids=set(INBOUND);b_ids=set(OUTBOUND)
    a_status=all(inbound.get(k,{}).get("status")=="RECEIVED" and inbound.get(k,{}).get("bin_code")==v for k,v in INBOUND.items())
    b_status=all(outbound.get(k,{}).get("status")=="RELEASED" and outbound.get(k,{}).get("override_code")==v for k,v in OUTBOUND.items())
    no_extra_a=all(r.get("status")=="PENDING" for k,r in inbound.items() if k not in a_ids)
    no_extra_b=all(r.get("status")=="PENDING" for k,r in outbound.items() if k not in b_ids)
    rows_a={r.get("order_id"):r for r in audit_a.get("rows",audit_a.get("orders",[])) if isinstance(r,dict)};rows_b={r.get("order_id"):r for r in audit_b.get("rows",audit_b.get("orders",[])) if isinstance(r,dict)}
    def tokens_valid(audit, rows, field, kind):
        recorded={x[1] for x in _actions(db,kind)}
        tokens={audit.get(field)} if audit.get(field) else {x.get(field) for x in rows.values()}
        return bool(tokens) and None not in tokens and tokens.issubset(recorded)
    token_a_valid=tokens_valid(audit_a,rows_a,'allocation_token','inbound_phase2')
    token_b_valid=tokens_valid(audit_b,rows_b,'release_token','outbound_phase2')
    def committed(audit, rows, status):
        return audit.get('status')=='committed' or (bool(rows) and all(x.get('final_status',x.get('status',audit.get('final_status')))==status for x in rows.values()))
    a=[_check("A01",.25,a_status,{"target_count":6,"received":sum(inbound.get(k,{}).get("status")=="RECEIVED" for k in a_ids)}),
       _check("A02",.20,all(inbound.get(k,{}).get("bin_code")==v for k,v in INBOUND.items()),{"bins":{k:inbound.get(k,{}).get("bin_code") for k in INBOUND}}),
       _check("A03",.20,all(rows_a.get(k,{}).get("final_bin")==v or rows_a.get(k,{}).get("bin_code")==v for k,v in INBOUND.items()),{"audit_order_ids":sorted(rows_a)}),
       _check("A04",.20,token_a_valid and set(rows_a)==a_ids and committed(audit_a,rows_a,"RECEIVED"),{"token_valid":token_a_valid,"audit_ids":sorted(rows_a)}),
       _check("A05",.15,no_extra_a,{"unrelated_orders_unchanged":no_extra_a})]
    b=[_check("B01",.25,b_status,{"target_count":6,"released":sum(outbound.get(k,{}).get("status")=="RELEASED" for k in b_ids)}),
       _check("B02",.20,all(outbound.get(k,{}).get("override_code")==v for k,v in OUTBOUND.items()),{"overrides":{k:outbound.get(k,{}).get("override_code") for k in OUTBOUND}}),
       _check("B03",.20,all(rows_b.get(k,{}).get("override_code","")==v for k,v in OUTBOUND.items()),{"audit_order_ids":sorted(rows_b)}),
       _check("B04",.20,token_b_valid and set(rows_b)==b_ids and committed(audit_b,rows_b,"RELEASED"),{"token_valid":token_b_valid,"audit_ids":sorted(rows_b)}),
       _check("B05",.15,no_extra_b,{"unrelated_orders_unchanged":no_extra_b})]
    joint=[_check("J01",1.0,a_status and b_status,{"inbound_complete":a_status,"outbound_complete":b_status}),
           _check("J02",1.0,token_a_valid and token_b_valid,{"phase2_tokens_verified":token_a_valid and token_b_valid}),
           _check("J03",1.0,no_extra_a and no_extra_b,{"unrelated_records_preserved":no_extra_a and no_extra_b})]
    return make_grade(case_id="BC-07",run_id=run_id,actor_a_checks=a,actor_b_checks=b,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,
                      failure_reasons=[] if db.is_file() else ["Dispatch database snapshot is missing."],run_metadata={"oracle":"BC-07 offline deterministic"})

def grade_episode(snapshot_root:Path,receipt:dict[str,Any],run_id:str):
    return grade_case(snapshot_root.parent/"guest-output",run_id,database_path=snapshot_root/"rooms.db")
