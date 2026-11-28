from __future__ import annotations
import hashlib,json,struct,zipfile
from pathlib import Path
from pipeline.grade import make_grade
from xml.etree import ElementTree as ET
def j(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {}
def png_info(p):
 try:
  b=Path(p).read_bytes()
  if b[:8]!=b'\x89PNG\r\n\x1a\n' or len(b)<26:return (0,0,-1)
  return (*struct.unpack('>II',b[16:24]),b[25])
 except OSError:return (0,0,-1)
def layered_source_ok(path):
 try:
  with zipfile.ZipFile(path) as z:
   if z.read('mimetype') != b'image/openraster':return False
   xml=ET.fromstring(z.read('stack.xml'));layers=xml.findall('.//layer')
   return len(layers)>=2 and all(x.get('src') in z.namelist() and z.read(x.get('src')).startswith(b'\x89PNG\r\n\x1a\n') for x in layers)
 except (OSError,KeyError,zipfile.BadZipFile,ET.ParseError):return False

def member_checksums_ok(path,archive):
 try:
  checks={}
  for row in path.read_text(encoding='utf-8').splitlines():
   digest,name=row.split(None,1);checks[name.lstrip(' *')]=digest.lower()
  with zipfile.ZipFile(archive) as z:
   return set(checks)==set(z.namelist()) and all(checks[n]==hashlib.sha256(z.read(n)).hexdigest() for n in checks)
 except (OSError,ValueError,zipfile.BadZipFile):return False

def check(root,role):
 root=Path(root);out=root.parent/'guest-output';m=j(root/'release_manifest.json');art=m.get(role,{}).get('artifacts',{});meta=j(out/(role+'_release.json'));receipt=j(root/'qa-final.json')
 if role=='client':
  p1=out/'out/client/client_banner.png';p2=out/'out/client/client_thumbnail.png';valid=(png_info(p1)==(640,360,2) and png_info(p2)==(320,180,2) and all(p.is_file() for p in (p1,p2)))
  valid=valid and art.get('out/client/client_banner.png')==hashlib.sha256(p1.read_bytes()).hexdigest() and art.get('out/client/client_thumbnail.png')==hashlib.sha256(p2.read_bytes()).hexdigest()
  valid=valid and layered_source_ok(out/'out/client/client_source.ora')
 else:
  p=out/'out/server/server_package.zip';valid=p.is_file() and art.get('out/server/server_package.zip')==hashlib.sha256(p.read_bytes()).hexdigest()
  if valid:
   try:
    with zipfile.ZipFile(p) as z:valid=set(z.namelist())=={'config/service.json','LICENSE.txt'} and json.loads(z.read('config/service.json')).get('api_version')=='v3' and json.loads(z.read('config/service.json')).get('locale')=='en-US'
   except (OSError,zipfile.BadZipFile,json.JSONDecodeError):valid=False
  valid=valid and member_checksums_ok(out/'out/server/checksums.sha256',p)
 return bool(valid and meta and receipt.get('state')=='FINAL'),{'artifact_structure_and_hashes':bool(valid),'release_metadata_present':bool(meta),'final_qa_receipt':receipt.get('state')=='FINAL'}
def grade_episode(snapshot_root,receipt,run_id):
 root=Path(snapshot_root);a,ae=check(root,'client');b,be=check(root,'server');m=j(root/'release_manifest.json');events=[]
 try:events=[json.loads(x) for x in (root/'qa_events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
 except (OSError,json.JSONDecodeError):pass
 joint=bool(m.get('client',{}).get('artifacts') and m.get('server',{}).get('artifacts') and m.get('qa_state')=='FINAL' and events and events[-1].get('state')=='FINAL')
 ac=[{'id':'A01','weight':.6,'passed':a,'required':True,'evidence':ae},{'id':'A02','weight':.4,'passed':a,'required':True,'evidence':{'client_visual_delivery_verified':a}}];bc=[{'id':'B01','weight':.6,'passed':b,'required':True,'evidence':be},{'id':'B02','weight':.4,'passed':b,'required':True,'evidence':{'package_delivery_verified':b}}];jc=[{'id':'J01','weight':1,'passed':joint,'required':True,'evidence':{'manifest_and_qa_final_cover_both_roles':joint}}]
 return make_grade(case_id='BC-23',run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=jc,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={'oracle':'BC-23 host PNG/archive/hash/manifest and QA ledger'})
