from types import SimpleNamespace
import evaluation_examples.task_class.pg_v2 as pair
class Response:
 def __init__(self,ready):self.ready=ready
 def raise_for_status(self):pass
 def json(self):return {"output":"V2_READY\n" if self.ready else ""}
def test_setup_starts_one_app_and_opens_chrome_once(monkeypatch):
 state={"ready":False};starts=[];opens=[];marks=[]
 monkeypatch.setattr(pair.requests,"post",lambda *a,**k:Response(state["ready"]))
 monkeypatch.setattr(pair,"start_webapp",lambda *a:starts.append(a))
 monkeypatch.setattr(pair,"open_chrome",lambda sc,urls:opens.append(urls))
 def sh(sc,command):marks.append(command);state["ready"]=True
 monkeypatch.setattr(pair,"sh",sh)
 sc=SimpleNamespace(vm_ip="127.0.0.1",server_port=5000)
 pair.setup(sc);pair.setup(sc)
 assert len(starts)==len(opens)==len(marks)==1
