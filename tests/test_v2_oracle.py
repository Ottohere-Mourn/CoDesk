import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
PAIR=REPO/"tasks"/"paragui"
sys.path.insert(0,str(PAIR))
from build_v2 import build
from pg_v2_oracle import checks

def fixture(tmp):
 build(str(tmp));return json.loads((tmp/"expected.json").read_text())

def joint_jobs(expected):
 rows=[]
 for group in expected.values():
  for item in group["labels"]:
   rows.append({"label_id":item["id"],"profile":group["profile"],"copies":item["copies"]})
 return rows

def test_jointly_feasible_positive_control_both_batches_pass(tmp_path):
 exp=fixture(tmp_path);state={"jobs":joint_jobs(exp)}
 assert checks(state,exp,"bins")[1]==1.0
 assert checks(state,exp,"parcels")[1]==1.0

def test_wrong_stock_profile_fails_only_affected_label(tmp_path):
 exp=fixture(tmp_path);jobs=joint_jobs(exp)
 jobs[0]["profile"]="PARCEL_4X6"
 c,s=checks({"jobs":jobs},exp,"bins")
 assert c["B-104_correct_profile_and_copies"] is False
 assert s==0.8
 assert checks({"jobs":jobs},exp,"parcels")[1]==1.0

def test_wrong_copy_count_does_not_match_required_job(tmp_path):
 exp=fixture(tmp_path);jobs=joint_jobs(exp)
 jobs[0]["copies"]+=1
 assert checks({"jobs":jobs},exp,"bins")[1]==0.8

def test_shared_station_profile_is_sampled_when_print_is_submitted(tmp_path):
 _=fixture(tmp_path);db=tmp_path/"seed.db"
 import socket
 with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
 proc=subprocess.Popen([sys.executable,str(PAIR/"app_v2.py"),"--db",str(db),"--port",str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 base=f"http://127.0.0.1:{port}"
 def post(path,values):
  data=urllib.parse.urlencode(values).encode();req=urllib.request.Request(base+path,data=data)
  return urllib.request.urlopen(req,timeout=3).read()
 try:
  for _ in range(60):
   try:urllib.request.urlopen(base+"/health",timeout=1);break
   except Exception:time.sleep(.1)
  post("/profile",{"profile":"BIN_2X1"})
  # A sees its profile; another normal user changes the shared station before A submits.
  post("/profile",{"profile":"PARCEL_4X6"})
  post("/print",{"label_id":"1","copies":"2"})
  con=sqlite3.connect(db);row=con.execute("SELECT profile,copies FROM jobs ORDER BY id DESC LIMIT 1").fetchone();con.close()
  assert row==("PARCEL_4X6",2)
  exp=json.loads((tmp_path/"expected.json").read_text())
  assert checks({"jobs":[{"label_id":1,"profile":row[0],"copies":row[1]}]},exp,"bins")[1]==0.0
 finally:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
