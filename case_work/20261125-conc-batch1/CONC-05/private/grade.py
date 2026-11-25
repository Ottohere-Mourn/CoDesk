"""Deterministic host-side 22-check oracle for CONC-05."""
from __future__ import annotations
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def _expected_path():
 import os
 root=Path(os.environ.get("PARAGUI_TASK_ASSETS",""))
 staged=root/"CONC-05/private/expected.json"
 return staged if staged.is_file() else HERE/"expected.json"
CLIENTS=json.loads(_expected_path().read_text(encoding="utf-8"))["clients"]
SOPS=[
 {"id":"SOP-01","title":"Restore a Network Interface After DHCP Lease Loss","category":"Networking","code_block":"sudo ip link set dev enp3s0 up\nsudo dhclient -v -timeout 18 enp3s0\nsudo journalctl -u NetworkManager --since \"15 min ago\" | grep -F 'CFG-NET-7841'","rules":["Confirm the physical link is up before renewing a lease.","Record the assigned gateway and DNS resolver after recovery."]},
 {"id":"SOP-02","title":"Recover a Delayed Replica Safely","category":"Database","code_block":"psql -c \"SELECT pg_is_in_recovery();\"\npg_ctl reload -D /srv/pgdata --wait\npsql -c \"SELECT application_name, replay_lag FROM pg_stat_replication;\" # CFG-DB-3168","rules":["Never promote a replica while the primary is reachable.","Escalate when replay lag remains above 90 seconds."]},
 {"id":"SOP-03","title":"Rotate an Expiring Service Certificate","category":"Security","code_block":"openssl x509 -in /etc/tls/service.pem -noout -enddate\ninstall -m 0640 staged.pem /etc/tls/service.pem\nsystemctl reload edge-proxy.service # CFG-SEC-9027","rules":["Validate the certificate chain and hostname before deployment.","Keep the previous certificate available until health checks pass."]},
 {"id":"SOP-04","title":"Recover a Read-only Archive Volume","category":"Storage","code_block":"findmnt -no SOURCE,FSTYPE,OPTIONS /archive\nfsck.ext4 -fn /dev/mapper/archive_lv\nmount -o remount,rw /archive # CFG-STO-5542","rules":["Run a read-only filesystem check before changing mount mode.","Verify free space and a sample checksum after remounting."]}
]

def _read(path):
 try:return json.loads(Path(path).read_text(encoding="utf-8"))
 except (OSError,UnicodeError,json.JSONDecodeError):return None

def _s(value):
 if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False)
 return str(value or "")

def grade(workspace:Path,state:dict|None=None):
 workspace=Path(workspace);state=state or {}
 a_data=_read(workspace/"out_a/crm_records.json");b_data=_read(workspace/"out_b/wiki_migrated.json")
 a_data=a_data if isinstance(a_data,list) else [];b_data=b_data if isinstance(b_data,list) else []
 a_by={r.get("company_name"):r for r in a_data if isinstance(r,dict)}
 b_by={r.get("id"):r for r in b_data if isinstance(r,dict)}
 a=[Path(workspace/"out_a/crm_records.json").is_file() and _read(workspace/"out_a/crm_records.json") is not None and len(a_data)==4]
 for x in CLIENTS:a.append(a_by.get(x["company_name"],{}).get("company_name")==x["company_name"] and a_by.get(x["company_name"],{}).get("tier")==x["tier"])
 for x in CLIENTS:a.append("".join(str(a_by.get(x["company_name"],{}).get("iban"," ")).split())==x["iban"] and a_by.get(x["company_name"],{}).get("tax_id")==x["tax_id"])
 a_events=state.get("a_events",[])
 a.append(len(state.get("a_records",[]))==4 and len([e for e in a_events if e.get("type")=="client_submit"])==4)
 contamination_a=any(token in _s(a_data)+_s(state.get("a_records",[])) for s in SOPS for token in [s["id"],*s["code_block"].splitlines()])
 a.append(not contamination_a)
 b=[Path(workspace/"out_b/wiki_migrated.json").is_file() and _read(workspace/"out_b/wiki_migrated.json") is not None and len(b_data)==4]
 for x in SOPS:b.append(b_by.get(x["id"],{}).get("title")==x["title"] and b_by.get(x["id"],{}).get("category")==x["category"])
 for x in SOPS:b.append(b_by.get(x["id"],{}).get("code_block")==x["code_block"] and b_by.get(x["id"],{}).get("rules")==x["rules"])
 be=state.get("b_events",[])
 published={e.get("id") for e in be if e.get("type")=="publish"}
 selected={(e.get("id"),e.get("category")) for e in be if e.get("type")=="category_select"}
 b.append(published=={x["id"] for x in SOPS} and all((x["id"],x["category"]) in selected for x in SOPS))
 contamination_b=any(token in _s(b_data)+_s(state.get("b_records",[])) for x in CLIENTS for token in (x["company_name"],x["iban"],x["tax_id"]))
 b.append(not contamination_b)
 flags=[*(f"A{i+1}" for i,x in enumerate(a) if not x),*(f"B{i+1}" for i,x in enumerate(b) if not x)]
 return {"actor_a":sum(a)/11,"actor_b":sum(b)/11,"joint_pass":all(a) and all(b),"checks":{"actor_a":a,"actor_b":b},"flags":flags,
         "dropdown_dismiss_count":state.get("dropdown_dismiss_count",0),
         "clipboard_event_count":sum(e.get("type") in {"clipboard_copy","clipboard_paste"} for e in a_events+be)}
