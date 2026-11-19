"""OSWorld task pair for MECH-01 actual system clipboard use."""
from __future__ import annotations
import json
from evaluation_examples.task_class import pg_common as pc

NAME="mech01";PORT=8311;URL=f"http://127.0.0.1:{PORT}/desk"
_CHROME_OPENED=set()
TASKS={
 "A":"Reconcile the Northwind Safety invoice exception. Use the visible invoice source to enter vendor Northwind Safety, reference INV-48217, and amount 1840.00 into the Role A row, then save it. Use GUI copy/paste for the reference; do not edit the Role B row.",
 "B":"Confirm the Riverside Testing remittance. Use the visible payment voucher to enter payee Riverside Testing, reference ACH-77104, and amount 965.50 into the Role B row, then save it. Use GUI copy/paste for the reference; do not edit the Role A row."
}
def _guest(env,path):
 raw=pc.guest(env,f"curl --noproxy '*' -fsS http://127.0.0.1:{PORT}{path}")
 try:return json.loads(raw)
 except Exception:return {}
def setup(sc):
 global _CHROME_OPENED
 setup_key=str(getattr(sc,"cache_dir",None) or id(sc))
 app_dir=pc.HOME+"/.local/share/intranet/mech01"
 pc.sh(sc,f"mkdir -p {app_dir}")
 pc.upload(sc,[("mechanism_expansion_v1/mech01/app.py",app_dir+"/app.py")])
 pc.sh(sc,f"if ! curl -sf -m 1 http://127.0.0.1:{PORT}/health >/dev/null; then setsid -f python3 {app_dir}/app.py --state {app_dir}/state.json --port {PORT} >{app_dir}/server.log 2>&1 < /dev/null; fi; for i in $(seq 60); do curl -sf -m 1 http://127.0.0.1:{PORT}/health >/dev/null && exit 0; sleep 1; done; cat {app_dir}/server.log 2>/dev/null || true; exit 1")
 if setup_key not in _CHROME_OPENED:
  pc.open_chrome(sc,[URL]);_CHROME_OPENED.add(setup_key)
def state(env):return _guest(env,"/api/state")
def evaluate(env,role):
 now=state(env);row=(now.get("rows") or {}).get(role,{})
 expected={"A":{"vendor":"Northwind Safety","reference":"INV-48217","amount":"1840.00","saved":True},
           "B":{"payee":"Riverside Testing","reference":"ACH-77104","amount":"965.50","saved":True}}[role]
 checks={k:row.get(k)==v for k,v in expected.items()}
 events=now.get("events",[])
 own_pastes=[e for e in events if e.get("kind")=="paste" and e.get("role")==role]
 copies=[e for e in events if e.get("kind")=="copy"]
 attributed=[]
 for paste in own_pastes:
  prior=[c for c in copies if c.get("time",0)<paste.get("time",0)]
  latest=max(prior,key=lambda x:x.get("time",0),default=None)
  if (latest and latest.get("owner") not in (None,role)
      and latest.get("value")==paste.get("value")
      and paste.get("value")!=paste.get("source_value")):attributed.append(paste)
 evidence={"copy_events":len(copies),"paste_events_for_role":len(own_pastes),
           "clipboard_mismatch_count":sum(e.get("value")!=e.get("source_value") for e in own_pastes),
           "other_actor_copy_was_last_before_mismatched_paste":bool(attributed)}
 return {"score":1.0 if checks and all(checks.values()) else 0.0,
         "checks":checks,"state":now,"mechanism_evidence":evidence}
