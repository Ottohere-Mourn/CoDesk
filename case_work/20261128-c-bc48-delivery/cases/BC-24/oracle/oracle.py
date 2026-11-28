from __future__ import annotations
import csv,json,sqlite3,zipfile
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree as ET
from pipeline.grade import make_grade
A={'SUB-001':('matched',120),'SUB-002':('matched',80),'SUB-003':('adjusted',-20)};B={'FUL-101':('matched',4),'FUL-102':('adjusted',2),'FUL-103':('disputed',0),'FUL-104':('adjusted',-1)}
def j(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError):return {}
def work_ok(path,sheet,required=()):
 try:
  with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('content.xml'))
  ns={'table':'urn:oasis:names:tc:opendocument:xmlns:table:1.0'};tables=root.findall('.//table:table',ns);names={t.get('{'+ns['table']+'}name'):t for t in tables};return all(x in names for x in ('Readme','Subscriptions','Fulfillment','Adjustments','Close Summary')) and sheet in names and all(term in ''.join(names[sheet].itertext()) for term in required)
 except (OSError,KeyError,zipfile.BadZipFile,ET.ParseError):return False
def actor(root,role,expected,dbname):
 root=Path(root);out=root.parent/'guest-output';report=j(out/(role+'_closeout.json'));dec={x.get('line_id'):(x.get('decision'),x.get('amount')) for x in report.get('decisions',[])};data_ok=dec==expected
 pdf=out/(role+'_closeout.pdf');pdf_ok=pdf.is_file() and pdf.read_bytes().startswith(b'%PDF-')
 try:
  with closing(sqlite3.connect((root/dbname).resolve().as_uri()+"?mode=ro", uri=True)) as c:db={x[0]:(x[1],x[2]) for x in c.execute('SELECT line_id,decision,amount FROM reconciliation')}
  db_ok=all(db.get(k)==v for k,v in expected.items())
 except (OSError,sqlite3.Error):db_ok=False
 sheet='Subscriptions' if role=='subscription' else 'Fulfillment';ods=work_ok(root/'quarter_closeout.ods',sheet,expected.keys())
 return bool(data_ok and pdf_ok and db_ok and ods),{'report_matches_expected_lines':data_ok,'persisted_rows_match':db_ok,'pdf_valid':pdf_ok,'workbook_sheets_present':ods}
def grade_episode(snapshot_root,receipt,run_id):
 root=Path(snapshot_root);a,ae=actor(root,'subscription',A,'closeout.db');b,be=actor(root,'fulfillment',B,'closeout.db')
 try:
  with closing(sqlite3.connect((root/"closeout.db").resolve().as_uri()+"?mode=ro", uri=True)) as c:rev=c.execute('SELECT revision FROM dashboard_revision').fetchone()[0];scopes={x[0] for x in c.execute('SELECT DISTINCT scope FROM audit_event')}
 except (OSError,sqlite3.Error,TypeError):rev=0;scopes=set()
 joint=rev>=2 and scopes=={'subscription','fulfillment'} and work_ok(root/'quarter_closeout.ods','Close Summary')
 ac=[{'id':'A01','weight':.6,'passed':a,'required':True,'evidence':ae},{'id':'A02','weight':.4,'passed':a,'required':True,'evidence':{'subscription_closeout_consistent':a}}];bc=[{'id':'B01','weight':.6,'passed':b,'required':True,'evidence':be},{'id':'B02','weight':.4,'passed':b,'required':True,'evidence':{'fulfillment_closeout_consistent':b}}];jc=[{'id':'J01','weight':1,'passed':joint,'required':True,'evidence':{'both_business_lines_committed_with_shared_summary':joint}}]
 return make_grade(case_id='BC-24',run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=jc,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={'oracle':'BC-24 host SQLite/workbook/JSON/PDF reconciliation grader'})
