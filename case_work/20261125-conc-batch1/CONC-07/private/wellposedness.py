"""Truth-artifact fixtures for deterministic CONC-07 checks."""
from __future__ import annotations
import importlib.util,json,sqlite3,tempfile,time
from pathlib import Path
CASE=Path(__file__).resolve().parents[1]
def _load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s and s.loader;s.loader.exec_module(m);return m
gm=_load('conc07_private_grade',CASE/'private/grade.py');am=_load('conc07_builder',CASE/'integration/build_assets.py')
def make_truth(root:Path):
 import fitz
 from pptx import Presentation
 from pptx.util import Inches,Pt
 from pptx.dml.color import RGBColor
 from PIL import Image
 root=Path(root);ar=am.build(root/'assets');exp=json.loads((ar/'private/expected.json').read_text(encoding='utf-8'));ws=root/'workspace';(ws/'out_a').mkdir(parents=True,exist_ok=True);(ws/'out_b').mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(ws/'enterprise_ops.db');db.execute('PRAGMA journal_mode=DELETE');db.execute('CREATE TABLE supplier_settlements(supplier_id TEXT PRIMARY KEY,gross_amount REAL,deduction REAL,net_payable REAL,has_dispute INTEGER,batch_code TEXT)');db.execute('CREATE TABLE campaign_audits(channel_id TEXT PRIMARY KEY,spend REAL,revenue REAL,roi REAL,alert_flag INTEGER,lock_code TEXT)')
 acode='BATCH-8F42C1D0';bcode='LOCK-6A902DF1'
 for x in exp['suppliers']:db.execute('INSERT INTO supplier_settlements VALUES(?,?,?,?,?,?)',(x['supplier_id'],x['gross_amount'],x['deduction'],x['net_payable'],x['has_dispute'],acode))
 for x in exp['campaigns']:db.execute('INSERT INTO campaign_audits VALUES(?,?,?,?,?,?)',(x['channel_id'],x['spend'],x['revenue'],x['roi'],x['alert_flag'],bcode))
 db.commit();db.close();a=ws/'out_a';b=ws/'out_b'
 (a/'settlement_audit.json').write_text(json.dumps({'settlements':exp['suppliers'],'exceptions':exp['supplier_exceptions'],'batch_code':acode}),encoding='utf-8')
 (b/'campaign_summary.json').write_text(json.dumps({'campaigns':exp['campaigns'],'allowances':exp['allowances'],'lock_code':bcode}),encoding='utf-8')
 for i in (1,2):(b/f'mobile_lp_{i}.png').write_bytes((ar/f'guest/in_b/mobile_lp_{i}.png').read_bytes())
 def txt(s,x,y,w,h,t,size=16,bold=False):
  z=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));z.text_frame.word_wrap=True;z.text_frame.text=t
  for p in z.text_frame.paragraphs:
   for r in p.runs:r.font.size=Pt(size);r.font.bold=bold
  return z
 def table(s,rows,ncols):
  z=s.shapes.add_table(len(rows),ncols,Inches(.65),Inches(1.45),Inches(5.3),Inches(4.25)).table
  for ri,row in enumerate(rows):
   for ci,val in enumerate(row):z.cell(ri,ci).text=str(val);z.cell(ri,ci).text_frame.paragraphs[0].font.size=Pt(10)
  return z
 def newprs(role):
  prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5);green=role=='a';color=exp['brand_a'] if green else exp['brand_b'];rgb=RGBColor.from_string(color.lstrip('#'))
  s=prs.slides.add_slide(prs.slide_layouts[6]);txt(s,.7,1,12,1,'Q4 Supplier Review' if green else 'Q4 Promo Postmortem',34,True);bar=s.shapes.add_shape(1,Inches(.8),Inches(3),Inches(3),Inches(.5));bar.fill.solid();bar.fill.fore_color.rgb=rgb
  s=prs.slides.add_slide(prs.slide_layouts[6]);txt(s,.65,.35,12,.6,'Executive Summary',24,True)
  if green:rows=[['Supplier','Gross','Deduction','Net Payable']]+[[x['supplier_id'],f"${x['gross_amount']:,.2f}",f"${x['deduction']:,.2f}",f"${x['net_payable']:,.2f}"] for x in exp['suppliers']];table(s,rows,4)
  else:rows=[['Channel','Spend','Revenue','ROI','Alert']]+[[x['channel_id'],f"${x['spend']:,.2f}",f"${x['revenue']:,.2f}",f"{x['roi']:.1f}x",'Review' if x['alert_flag'] else 'Within plan'] for x in exp['campaigns']];table(s,rows,5)
  txt(s,6.2,1.1,6,4,'Validated close figures and leadership exhibits.',16)
  if green:
   for j,n in enumerate(('settlement_by_vendor','deduction_profile','q4_payable_trend'),2):
    s=prs.slides.add_slide(prs.slide_layouts[6]);txt(s,.65,.3,12,.6,n.replace('_',' ').title(),24,True);s.shapes.add_picture(str(ar/f'guest/in_a/{n}.png'),Inches(2.0),Inches(1.2),width=Inches(8),height=Inches(5.0))
  else:
   for idx,names in ((2,('channel_roi','budget_variance')),(3,('revenue_mix',))):
    while len(prs.slides)<=idx:prs.slides.add_slide(prs.slide_layouts[6])
    s=prs.slides[idx];txt(s,.65,.3,12,.6,'Budget variance and campaign performance',24,True)
    for k,n in enumerate(names):s.shapes.add_picture(str(ar/f'guest/in_b/{n}.png'),Inches(.8+k*6.2),Inches(1.25),width=Inches(5.8),height=Inches(4.0))
  # Slides 5 and 6 are concise control/exception summaries.
  while len(prs.slides)<7:prs.slides.add_slide(prs.slide_layouts[6])
  if green:
   txt(prs.slides[5],.8,1,11.5,4,'SUP-02: '+exp['supplier_exceptions']['SUP-02']+'\nSUP-05: '+exp['supplier_exceptions']['SUP-05'],18)
   note=exp['a_note']
  else:
   txt(prs.slides[4],.8,1,11.5,4,'Budget alerts: CH-02 and CH-04 require owner review.',18);txt(prs.slides[5],.8,1,11.5,4,'Both mobile landing-page checks completed at the target narrow viewport.',18);note=exp['b_note']
  txt(prs.slides[6],.65,5.8,12,1.2,note,13)
  out=a/'Q4_Supplier_Review.pptx' if green else b/'Promo_Postmortem.pptx';prs.save(out);return prs
 newprs('a');newprs('b')
 for role,dirname,charts in [('a',a,('settlement_by_vendor','deduction_profile','q4_payable_trend')),('b',b,('channel_roi','budget_variance','revenue_mix'))]:
  pdf=fitz.open();brand=exp['brand_a'] if role=='a' else exp['brand_b'];note=exp['a_note'] if role=='a' else exp['b_note']
  for i in range(7):
   p=pdf.new_page(width=960,height=540)
   if i in (0,2,3,4,6):p.draw_rect(fitz.Rect(0,0,960,18),color=None,fill=tuple(int(brand[j:j+2],16)/255 for j in (1,3,5)))
   p.insert_text((40,70),f'Q4 {"Supplier Review" if role=="a" else "Campaign Postmortem"} | Page {i+1}',fontsize=18)
   names=charts if (role=='a' and i in (2,3,4)) else ((charts[0],charts[1]) if role=='b' and i==2 else ((charts[2],) if role=='b' and i==3 else ()))
   for j,n in enumerate(names):p.insert_image(fitz.Rect(60+j*440,110,480+j*440,400),filename=str(ar/f'guest/in_{role}/{n}.png'))
   if i==6:p.insert_textbox(fitz.Rect(40,100,900,220),note,fontsize=12)
  pdf.save(dirname/('Q4_Supplier_Review.pdf' if role=='a' else 'Promo_Postmortem.pdf'));pdf.close()
  for n in charts:(dirname/f'{n}.png').write_bytes((ar/f'guest/in_{role}/{n}.png').read_bytes())
  if role=='b':
   for i in (1,2):(dirname/f'mobile_lp_{i}.png').write_bytes((ar/f'guest/in_b/mobile_lp_{i}.png').read_bytes())
 ev={'a_events':[{'type':'row_saved','id':x['supplier_id'],'image_sha256':exp['supplier_qc_hashes'].get(x['supplier_id'],'')} for x in exp['suppliers']],'b_events':[{'type':'mobile_viewport_check','width':375,'height':812},{'type':'mobile_viewport_check','width':375,'height':812},*({'type':'dashboard_hover','width':1680,'channel':x} for x in exp['campaign_ids'])],'finalize_events':[{'type':'finalize_success','code':acode},{'type':'lock_success','code':bcode}],'mobile_uploads':[{'name':f'mobile_lp_{i}.png','sha256':exp['mobile_hashes'][f'LP-{i}']} for i in (1,2)],'sqlite_busy_count':1}
 result=gm.grade(ws,ev,ar/'private/expected.json',root/'rendered');return result,ev,ws,ar
def gates():
 t=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='conc07-fixture-') as d:
  root=Path(d);truth,state,ws,ar=make_truth(root);empty=gm.grade(root/'empty',{},ar/'private/expected.json',root/'empty-render');bad={**state,'b_events':state['b_events'][:-1]};damaged=gm.grade(ws,bad,ar/'private/expected.json',root/'bad-render')
 elapsed=time.monotonic()-t
 return {'gate1_pristine_fail':not empty['joint_pass'],'gate2_gt_seq_ab_exists':truth['joint_pass'],'gate3_gt_seq_ba_exists':truth['joint_pass'],'gate4_gt_naive_race_corrupts':not damaged['joint_pass'],'gate5_fixture_feasible':truth['joint_pass'] and elapsed<180,'fixture_elapsed_s':round(elapsed,3)}
