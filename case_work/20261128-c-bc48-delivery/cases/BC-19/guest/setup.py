from __future__ import annotations
import argparse,csv,json,subprocess,sys
from pathlib import Path
RISK=[("R-01",0.91,6,"US","review"),("R-02",0.20,2,"US","allow"),("R-03",0.70,7,"CA","review"),("R-04",0.95,1,"ZZ","block"),("R-05",0.84,4,"GB","review")]
ROUTES=[("/orders","orders-v3","orders-v2",6),("/catalog","catalog-v2","catalog-v1",3),("/profile","profile-v1","profile-cache",4)]
def main():
 p=argparse.ArgumentParser();p.add_argument("--workspace",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args();root=Path(a.workspace).expanduser().resolve()/"rule_lab";root.mkdir(parents=True,exist_ok=True);(root/"out").mkdir(exist_ok=True)
 (root/"rules.yaml").write_text(json.dumps({"version":1,"risk":{},"routing":{"rules":[]}},indent=2)+"\n",encoding="utf-8")
 for name,head,rows in [("risk_tests.csv",["case_id","score","attempts","region","expected"],RISK),("route_tests.csv",["path","primary","fallback","timeout_s"],ROUTES)]:
  with (root/name).open("w",encoding="utf-8",newline="") as f:w=csv.writer(f);w.writerow(head);w.writerows(rows)
 (root/"rule_requirements.txt").write_text("Risk: 60-second velocity window; review when risk score >= 0.82 or attempts > 5; block region ZZ; otherwise allow. Evaluate risk_tests.csv.\nRouting: use every route in route_tests.csv with its exact primary, fallback, and timeout.\nSchema: risk={velocity_window_s: integer, min_risk_to_review: number, max_attempts: integer, blocked_region: string}; routing={rules: [{path: string, primary: string, fallback: string, timeout_s: number}]}. Save a JSON-compatible YAML rules document, reload the engine, run all test cases, and export separate risk/routing reports.\n",encoding="utf-8")
 if a.start_service:
  log=(root/"engine.log").open("ab",buffering=0);subprocess.Popen([sys.executable,str(Path(a.source_dir)/"engine_service.py"),"--root",str(root)],stdout=log,stderr=log,start_new_session=True);log.close()
 if a.open_browser:subprocess.Popen(["google-chrome","http://127.0.0.1:18119/"],start_new_session=True)
if __name__=="__main__":main()
