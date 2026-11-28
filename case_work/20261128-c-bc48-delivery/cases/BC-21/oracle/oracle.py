from __future__ import annotations
import hashlib,json
from pathlib import Path
from pipeline.grade import make_grade
def readj(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {}
def check(root,name,outname,required):
 p=Path(root)/name;o=readj(Path(root).parent/'guest-output'/outname);idx=readj(Path(root)/'index.json')
 text=p.read_text(encoding='utf-8') if p.exists() else '';digest=hashlib.sha256(text.encode()).hexdigest()
 d=next((x for x in idx.get('documents',[]) if x.get('path')==name),{})
 queries=o.get('query_terms',[]);hits=o.get('hit_counts',{})
 document=o.get('document',o.get('indexed_document_path',o.get('index_document_path',o.get('document_path',''))))
 document=Path(document).name
 try:revision=int(o.get('revision',o.get('index_revision',0)));current=int(idx.get('revision',-1))
 except (TypeError,ValueError):revision=0;current=-1
 reported_saved=o.get('saved_document_sha256',o.get('document_sha256'))
 reported_index=o.get('indexed_document_sha256',o.get('index_sha256'))
 hashes_match=reported_saved==digest and reported_index==digest
 # Verification must refer to the final active index, even if content is unchanged.
 version_ok=revision>0 and revision==current
 text_complete=all(x in text.lower() for x in required)
 search_ok=bool(queries) and all(isinstance(x,str) and x.lower() in text.lower() and int(hits.get(x,0))>0 for x in queries)
 index_ok=d.get('sha256')==digest and d.get('text')==text
 ok=text_complete and document==name and version_ok and index_ok and search_ok
 return bool(ok),{'text_complete':text_complete,'index_current':index_ok,'verification_current':version_ok,'content_hash_proves_unchanged':hashes_match,'search_terms_present':search_ok}

def grade_episode(snapshot_root,receipt,run_id):
 root=Path(snapshot_root);a,ae=check(root,'operations_guide.md','operations_verification.json',('health verification','rollback checkpoint','utc incident'));b,be=check(root,'api_guide.md','api_verification.json',('idempotency key','exponential backoff','non-retryable'));idx=readj(root/'index.json');joint_ok=len(idx.get('documents',[]))==2 and int(idx.get('revision',0))>0
 ac=[{'id':'A01','weight':.55,'passed':a,'required':True,'evidence':ae},{'id':'A02','weight':.45,'passed':a,'required':True,'evidence':{'operations_search_and_preview_verified':a}}];bc=[{'id':'B01','weight':.55,'passed':b,'required':True,'evidence':be},{'id':'B02','weight':.45,'passed':b,'required':True,'evidence':{'api_search_and_preview_verified':b}}];j=[{'id':'J01','weight':1,'passed':joint_ok,'required':True,'evidence':{'both_documents_in_same_current_index':joint_ok}}]
 return make_grade(case_id='BC-21',run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=j,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={'oracle':'BC-21 host document, search receipt, and index hash consistency'})
