from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def write_pdf(path: Path, lines: list[str]):
    def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream=("BT\n/F1 10 Tf\n48 748 Td\n"+"\n".join(("0 -14 Td\n" if i else "")+f"({esc(line)}) Tj" for i,line in enumerate(lines))+"\nET").encode("ascii","replace")
    bodies=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream"]
    out=bytearray(b"%PDF-1.4\n"); offsets=[0]
    for i,obj in enumerate(bodies,1): offsets.append(len(out));out.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
    xref=len(out);out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode());path.write_bytes(out)


APP = '''from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, sqlite3
ROOT=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=="/api/health": return self.send_obj(200,{"status":"ok"})
  if self.path=="/": return self.send_file(ROOT/"templates/layout.html","text/html; charset=utf-8")
  if self.path=="/static/app.js": return self.send_file(ROOT/"static/app.js","application/javascript; charset=utf-8")
  return self.send_obj(404,{"error":"not_found"})
 def send_obj(self,status,obj):
  data=json.dumps(obj).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
 def send_file(self,path,kind):
  try:data=path.read_bytes()
  except OSError:return self.send_obj(404,{"error":"missing_asset"})
  self.send_response(200);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
ThreadingHTTPServer(("127.0.0.1",8096),Handler).serve_forever()
'''
LAYOUT='''<!doctype html><html><head><meta charset="utf-8"><title>Operations Portal</title></head><body>
<header><h1>Operations Portal</h1><nav id="nav"></nav></header><main id="app"><p>Select a feature.</p></main><script src="/static/app.js"></script></body></html>'''
JS='''document.addEventListener("DOMContentLoaded",()=>{document.getElementById("app").textContent="Operations Portal ready";});'''
PORTALCTL='''from pathlib import Path
import os,signal,subprocess,sys,time,urllib.request
root=Path(__file__).resolve().parents[1]; pidfile=root/"portal.pid"; log=root/"portal.log"
cmd=sys.argv[1] if len(sys.argv)>1 else "status"
def status():
 try: print(urllib.request.urlopen("http://127.0.0.1:8096/api/health",timeout=1).read().decode()); return 0
 except Exception: print("stopped"); return 1
if cmd=="restart":
 try:
  pid=int(pidfile.read_text()); os.kill(pid,signal.SIGTERM); time.sleep(.25)
 except Exception: pass
 f=open(log,"ab",buffering=0); p=subprocess.Popen([sys.executable,str(root/"app.py")],cwd=root,stdout=f,stderr=f,start_new_session=True);pidfile.write_text(str(p.pid));time.sleep(.4);raise SystemExit(status())
elif cmd=="status": raise SystemExit(status())
else: print("usage: portalctl status|restart");raise SystemExit(2)
'''


def main():
    p=argparse.ArgumentParser();p.add_argument("--source-dir",required=True);p.add_argument("--workspace",required=True);p.add_argument("--start-service",action="store_true");p.add_argument("--open-browser",action="store_true");a=p.parse_args()
    repo=Path(a.workspace).expanduser().resolve()/"ops-portal";(repo/"templates").mkdir(parents=True,exist_ok=True);(repo/"static").mkdir(exist_ok=True);(repo/"bin").mkdir(exist_ok=True);(repo/"specs").mkdir(exist_ok=True)
    (repo/"app.py").write_text(APP,encoding="utf-8");(repo/"templates/layout.html").write_text(LAYOUT,encoding="utf-8");(repo/"static/app.js").write_text(JS,encoding="utf-8")
    portalctl=repo/"bin/portalctl";portalctl.write_text(PORTALCTL,encoding="utf-8");portalctl.chmod(0o755)
    db=sqlite3.connect(repo/"portal.db");db.executescript("CREATE TABLE metrics_daily(day TEXT,latency_ms REAL,total_requests INTEGER,error_requests INTEGER);CREATE TABLE incidents(incident_id TEXT,service TEXT,severity TEXT,status TEXT,created_at TEXT);")
    for day in range(1,32):
        latency=None if day in {7,19,29} else 140+((day*37)%260)
        requests=900+day*37;errors=(day*13)%41
        db.execute("INSERT INTO metrics_daily VALUES(?,?,?,?)",(f"2026-10-{day:02d}",latency,requests,errors))
    db.execute("INSERT INTO metrics_daily VALUES(NULL,NULL,NULL,NULL)")
    for i in range(1,31):
        severity=("CRITICAL" if i%6==0 else "HIGH" if i%3==0 else "MEDIUM" if i%2==0 else "LOW")
        status=("OPEN" if i%4 else "ACKNOWLEDGED")
        db.execute("INSERT INTO incidents VALUES(?,?,?,?,?)",(f"INC-{3000+i}",f"svc-{(i%5)+1}",severity,status,f"2026-10-{(i%27)+1:02d}T{(i*3)%24:02d}:00:00Z"))
    db.commit();db.close()
    write_pdf(repo/"specs/spec_metrics.pdf",["METRICS SUMMARY SPECIFICATION", "Read portal.db metrics_daily.", "For inclusive start/end dates, ignore rows with NULL day or latency.", "Return avg_latency_ms as arithmetic average of non-NULL latency_ms, rounded to 2 decimals.", "Return total_requests as the sum of requests in range.", "Return error_rate_pct = sum(error_requests) / sum(total_requests) * 100, rounded to 2 decimals.", "Verify ranges 2026-10-01 through 2026-10-10; 2026-10-11 through 2026-10-20; and 2026-10-21 through 2026-10-31."])
    write_pdf(repo/"specs/spec_triage.pdf",["INCIDENT TRIAGE AND EXPORT SPECIFICATION", "Read portal.db incidents.", "The severity filter is exact and case-insensitive.", "For each requested severity, export rows sorted by created_at descending.", "CSV header must be incident_id,service,severity,status,created_at.", "Verify CRITICAL and HIGH filters. Do not include other severities."])
    if not (repo/".git").exists():
        subprocess.run(["git","init","-b","main"],cwd=repo,check=True,stdout=subprocess.DEVNULL)
        subprocess.run(["git","config","user.name","OSWorld Task Actor"],cwd=repo,check=True)
        subprocess.run(["git","config","user.email","task-actor@localhost"],cwd=repo,check=True)
        subprocess.run(["git","add","."],cwd=repo,check=True)
        subprocess.run(["git","commit","-m","Initial operations portal"],cwd=repo,check=True,stdout=subprocess.DEVNULL)
    if a.start_service:
        subprocess.run([sys.executable,str(portalctl),"restart"],cwd=repo,check=True)
    if a.open_browser:
        subprocess.Popen(["google-chrome","http://127.0.0.1:8096/"],start_new_session=True)


if __name__=="__main__":main()
