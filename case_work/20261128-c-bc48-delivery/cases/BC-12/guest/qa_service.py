from __future__ import annotations
import argparse,hashlib,json,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image,UnidentifiedImageError

LOCK=threading.RLock();SPECS={"A":{"prefix":"a_banner_","width":1280,"height":720,"watermark":"Q4 LAUNCH","valid":{"a_banner_01.png","a_banner_02.png"}},"B":{"prefix":"b_product_","width":800,"height":1000,"watermark":"PRODUCT READY","valid":{"b_product_01.png","b_product_02.png"}}}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def validate(root,role):
 spec=SPECS[role];doc=json.loads((root/"asset_manifest.yaml").read_text(encoding="utf-8"));assets=[x for x in doc.get("assets",[]) if x.get("role")==role];ex=[x for x in doc.get("excluded",[]) if x.get("role")==role];issues=[];seen=set()
 for name in spec["valid"]:
  entry=next((x for x in assets if x.get("source")==name),None)
  if not entry:issues.append(f"Missing required source disposition: {name}");continue
  seen.add(name);path=(root/entry.get("output","" )).resolve()
  try:path.relative_to((root/"out").resolve())
  except ValueError:issues.append(f"Output path must remain below out/: {name}");continue
  try:
   with Image.open(path) as image:w,h=image.size;image.verify()
  except (OSError,UnidentifiedImageError):issues.append(f"Output is not a readable image: {name}");continue
  if (w,h)!=(spec["width"],spec["height"]):issues.append(f"Wrong output dimensions for {name}: {w}x{h}")
  if entry.get("watermark")!=spec["watermark"]:issues.append(f"Watermark label missing for {name}")
  if entry.get("sha256")!=digest(path):issues.append(f"Manifest checksum mismatch for {name}")
  if entry.get("status")!="ready":issues.append(f"Asset status is not ready for {name}")
 classified=seen|{x.get("source") for x in ex}
 for name in sorted((p.name for p in (root/"source").glob(spec["prefix"]+"*.png"))):
  if name not in classified:issues.append(f"Source not classified: {name}")
 for x in ex:
  if not str(x.get("reason","")).strip():issues.append(f"Excluded source requires a reason: {x.get('source')}")
 expected={p.name for p in (root/"source").glob(spec["prefix"]+"*.png")}
 if {x.get("source") for x in assets}!=spec["valid"]:issues.append("Export set must contain exactly the two approved source IDs.")
 if {x.get("source") for x in ex}!=expected-spec["valid"]:issues.append("Excluded set must contain exactly the non-qualifying sources.")
 return issues,doc
def submit(root,role):
 if role not in SPECS:return {"error":"invalid_role"},400
 with LOCK:
  try:
   manifest_bytes=(root/"asset_manifest.yaml").read_bytes();revision=hashlib.sha256(manifest_bytes).hexdigest();issues,doc=validate(root,role)
  except (OSError,json.JSONDecodeError,ValueError) as exc:
   manifest_bytes=b"";revision=hashlib.sha256(manifest_bytes).hexdigest();doc={};issues=[f"Manifest could not be parsed: {type(exc).__name__}"]
  events=[]
  try:events=[json.loads(x) for x in (root/"qa_events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
  except (OSError,json.JSONDecodeError):events=[]
  prior=[x for x in events if x.get("role")==role]
  try:revno=int(doc.get("revision",0))
  except (TypeError,ValueError):revno=0
  if not prior:
   issues.append("Phase 1 candidate review recorded; inspect feedback, update the manifest revision, then submit again.")
  elif prior[-1].get("status")=="REJECTED":
   if prior[-1].get("manifest_sha256")==revision:issues.append("Manifest is unchanged since Phase 1; revise it before resubmission.")
   if revno<=int(prior[-1].get("revision",0)):issues.append("Manifest revision must increase after Phase 1.")
  rec={"status":"PASS" if not issues else "REJECTED","manifest_sha256":revision,"revision":revno,"issues":issues};receipts=json.loads((root/"qa_receipts.json").read_text(encoding="utf-8"));receipts.setdefault("receipts",{})[role]=rec;(root/"qa_receipts.json").write_text(json.dumps(receipts,indent=2)+"\n",encoding="utf-8");events.append({"role":role,"status":rec["status"],"manifest_sha256":revision,"revision":revno,"issues":issues});(root/"qa_events.jsonl").write_text("".join(json.dumps(x)+"\n" for x in events),encoding="utf-8");return rec,(200 if not issues else 422)
class Handler(BaseHTTPRequestHandler):
 def send(self,status,obj):
  data=obj if isinstance(obj,bytes) else (obj if isinstance(obj,str) else json.dumps(obj)).encode();self.send_response(status);self.send_header("Content-Type","text/html; charset=utf-8" if isinstance(obj,str) else "application/json; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.path=="/health":return self.send(200,{"status":"ok"})
  if self.path=="/":return self.send(200,"<!doctype html><meta charset='utf-8'><title>Asset QA Desk</title><h1>Asset QA Desk</h1><p>Inspect source files, update asset_manifest.yaml, then POST /qa/A or /qa/B to validate a revision.</p><p>Source files and the manifest are in ~/workspace/asset_qa/.</p>")
  if self.path=="/manifest":return self.send(200,json.loads((self.server.root/"asset_manifest.yaml").read_text(encoding="utf-8")))
  return self.send(404,{"error":"not_found"})
 def do_POST(self):
  role=urlparse(self.path).path.rsplit("/",1)[-1];rec,status=submit(self.server.root,role);return self.send(status,rec)
 def log_message(self,*args):pass
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",required=True);a=p.parse_args();s=ThreadingHTTPServer(("127.0.0.1",18112),Handler);s.root=Path(a.root);s.serve_forever()
if __name__=="__main__":main()
