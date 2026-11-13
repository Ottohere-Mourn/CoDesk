import json, os, shutil, socket, sqlite3, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import requests
from build_v3 import build
ROOT=Path(__file__).resolve().parents[1]
class TestCommunityPantryApp(unittest.TestCase):
 def test_live_kiosk_context_is_shared_at_submit(self):
  with tempfile.TemporaryDirectory() as tmp:
   build(tmp);db=Path(tmp)/"app.db";shutil.copy(Path(tmp)/"seed.db",db)
   sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1];sock.close()
   p=subprocess.Popen([sys.executable,str(ROOT/"tasks/paragui/app_v3.py"),"--db",str(db),"--port",str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   url=f"http://127.0.0.1:{port}"
   try:
    for _ in range(100):
     try:
      r=requests.get(url+"/desk",timeout=0.2)
      if r.status_code==200:break
     except requests.RequestException:time.sleep(0.05)
    self.assertIn("Saturday Pantry Service",r.text)
    requests.post(url+"/select",json={"id":"V-214"},timeout=2)
    requests.post(url+"/panel",json={"panel":"shift"},timeout=2)
    requests.post(url+"/save",json={"station":"Check-in","window":"08:00-10:00","status":"CONFIRMED"},timeout=2)
    row=requests.get(url+"/state",timeout=2).json()["volunteers"][0]
    self.assertEqual((row["shift_station"],row["shift_window"],row["shift_status"]),("Check-in","08:00-10:00","CONFIRMED"))
    # A peer can move the global active context between reading a form and submitting it.
    requests.post(url+"/select",json={"id":"V-238"},timeout=2)
    requests.post(url+"/panel",json={"panel":"mileage"},timeout=2)
    requests.post(url+"/panel",json={"panel":"shift"},timeout=2)
    requests.post(url+"/select",json={"id":"V-214"},timeout=2)
    requests.post(url+"/save",json={"station":"Driver","window":"07:30-11:30","status":"CONFIRMED"},timeout=2)
    rows=requests.get(url+"/state",timeout=2).json()["volunteers"]
    by={x["id"]:x for x in rows}
    self.assertEqual(by["V-214"]["shift_station"],"Driver")
    self.assertEqual(by["V-238"]["shift_station"],"")
    c=sqlite3.connect(db);ev=c.execute("SELECT volunteer_id,panel FROM events ORDER BY id").fetchall();c.close()
    self.assertEqual(ev[-1],("V-214","shift"))
   finally:
    p.terminate()
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:p.kill();p.wait()
if __name__=="__main__":unittest.main()
