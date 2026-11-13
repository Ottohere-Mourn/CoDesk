from __future__ import annotations
import importlib, threading, urllib.parse, urllib.request
import pytest
CASES=["edu_grade","media_library","facility_wo","volunteer_ops","garden_ops"]
@pytest.mark.parametrize("name", CASES)
def test_case_fixture_http_oracle_and_independent_basis(tmp_path,name):
 app=importlib.import_module("oscombo.human_apps."+name); a=tmp_path/"a.sqlite"; b=tmp_path/"b.sqlite"
 ma=app.create_fixture(a,"run-a"); mb=app.create_fixture(b,"run-b")
 assert {k:v for k,v in ma.items() if k not in {"run_id","sha256"}} == {k:v for k,v in mb.items() if k not in {"run_id","sha256"}}
 server=app.make_server(a,"127.0.0.1",0); th=threading.Thread(target=server.serve_forever); th.start(); base="http://127.0.0.1:"+str(server.server_port)
 try:
  for p in ("/agent/evidence","/agent/task","/user/guide","/user/task"): assert urllib.request.urlopen(base+p).status==200
  cfg=importlib.import_module("oscombo.human_apps._next_workflow_factory").DATA[name]
  for actor,key in (("agent","af"),("user","uf")):
   payload={k:v for k,_,v in cfg[key]}; req=urllib.request.Request(base+"/"+actor+"/submit",data=urllib.parse.urlencode(payload).encode(),method="POST"); assert urllib.request.urlopen(req).status==200
  assert urllib.request.urlopen(base+"/user/result").status==200
  result=app.evaluate(a)
  assert result["agent"]["success"], result["agent"]["checks"]
  assert result["user"]["success"], result["user"]["checks"]
 finally: server.shutdown(); server.server_close(); th.join(timeout=5)
