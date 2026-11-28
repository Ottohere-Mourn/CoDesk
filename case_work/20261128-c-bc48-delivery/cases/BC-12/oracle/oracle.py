from __future__ import annotations
import hashlib,json,struct
from pathlib import Path
from pipeline.grade import make_grade

SPECS={"A":{"sources":{"a_banner_01.png","a_banner_02.png"},"excluded":{"a_banner_square.png","a_banner_low.png","a_banner_broken.png"},"dims":(1280,720),"watermark":"Q4 LAUNCH"},"B":{"sources":{"b_product_01.png","b_product_02.png"},"excluded":{"b_product_square.png","b_product_low.png","b_product_broken.png"},"dims":(800,1000),"watermark":"PRODUCT READY"}}
def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def _png_size(p):
 try:
  b=Path(p).read_bytes()
  if b[:8]!=b"\x89PNG\r\n\x1a\n" or b[12:16]!=b"IHDR":return None
  return struct.unpack(">II",b[16:24])
 except (OSError,struct.error):return None
def _valid_set(role,manifest,root):
 spec=SPECS[role];assets=[x for x in manifest.get("assets",[]) if x.get("role")==role];excluded=[x for x in manifest.get("excluded",[]) if x.get("role")==role];good=True;found=set()
 for x in assets:
  if x.get("source") in found:good=False
  found.add(x.get("source"));p=(root/x.get("output","missing")).resolve()
  try:p.relative_to((root.parent/"guest-output").resolve())
  except ValueError:good=False;continue
  size=_png_size(p)
  if x.get("source") not in spec["sources"] or size!=spec["dims"] or x.get("watermark")!=spec["watermark"] or x.get("status")!="ready":good=False
  try:d=hashlib.sha256(p.read_bytes()).hexdigest()
  except OSError:d=""
  if x.get("sha256")!=d:good=False
 if found!=spec["sources"] or {x.get("source") for x in excluded}!=spec["excluded"] or any(not str(x.get("reason","")).strip() for x in excluded):good=False
 return good,len(assets),len(excluded)
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);archive=root.parent;manifest=_json(root/"asset_manifest.yaml");receipts=_json(root/"qa_receipts.json").get("receipts",{});events=[]
 try:events=[json.loads(x) for x in (root/"qa_events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):events=[]
 a_ok,na,ea=_valid_set("A",manifest,archive/"guest-output");b_ok,nb,eb=_valid_set("B",manifest,archive/"guest-output");manifest_hash=hashlib.sha256((root/"asset_manifest.yaml").read_bytes()).hexdigest() if (root/"asset_manifest.yaml").is_file() else ""
 def qa(role):
  rec=receipts.get(role,{})
  role_events=[x for x in events if x.get("role")==role]
  rejected=[x for x in role_events if x.get("status")=="REJECTED"];passed=[x for x in role_events if x.get("status")=="PASS"]
  revised=bool(rejected and passed and rejected[0].get("manifest_sha256")!=passed[-1].get("manifest_sha256") and rejected[0].get("revision",0)<passed[-1].get("revision",0))
  return rec.get("status")=="PASS" and rec.get("manifest_sha256")==manifest_hash and revised and passed[-1].get("manifest_sha256")==manifest_hash
 ac=[{"id":"A01","weight":.55,"passed":a_ok,"required":True,"evidence":{"valid_outputs":na,"required":2,"exclusions":ea,"required_exclusions":3}},{"id":"A02","weight":.45,"passed":qa("A"),"required":True,"evidence":{"qa_receipt_matches_manifest":qa("A")}}]
 bc=[{"id":"B01","weight":.55,"passed":b_ok,"required":True,"evidence":{"valid_outputs":nb,"required":2,"exclusions":eb,"required_exclusions":3}},{"id":"B02","weight":.45,"passed":qa("B"),"required":True,"evidence":{"qa_receipt_matches_manifest":qa("B")}}]
 health=receipt.get("http_endpoints",{}).get("asset_qa_health",{}).get("status_code")==200;joint=[{"id":"J01","weight":1,"passed":a_ok and b_ok,"required":True,"evidence":{"all_six_deliverables_and_dispositions_valid":a_ok and b_ok}},{"id":"J02","weight":1,"passed":health,"required":True,"evidence":{"qa_health_200":health}}]
 return make_grade(case_id="BC-12",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-12 host PNG-header/checksum/manifest validation"})
