import sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tasks.mechanism_expansion_v1 import mech05 as m

def fixture_xml(tmp_path):
 p=tmp_path/'start.odt'; m_build=Path(__file__).parents[1]/'tasks/mechanism_expansion_v1/build_mech05_assets.py'
 import runpy
 ns=runpy.run_path(str(m_build)); ns['build'](p)
 with zipfile.ZipFile(p) as z: return z.read('content.xml')

def marked(xmlbytes, include_b_mark=False, include_a=True):
 import xml.etree.ElementTree as ET, zipfile, tempfile
 NS={'office':m.NS['office'],'text':m.NS['text'],'dc':'http://purl.org/dc/elements/1.1/'}
 root=ET.fromstring(xmlbytes); office_text=root.find('.//office:text',NS); ps=office_text.findall('./text:p',NS)
 # change A's paragraph: preserve target text, bracket replacement; deletion metadata stores original text.
 if include_a:
  parent=office_text; old=ps[1].text
  ps[1].text='Approval boundary: '
  d=ET.SubElement(parent.find('./text:tracked-changes',NS) if parent.find('./text:tracked-changes',NS) is not None else parent,'{'+m.NS['text']+'}tracked-changes')
  def region(rid,kind,oldtxt=''):
   r=ET.SubElement(d,'{'+m.NS['text']+'}changed-region',{'{'+m.NS['text']+'}id':rid,'{http://www.w3.org/XML/1998/namespace}id':rid})
   inner=ET.SubElement(r,'{'+m.NS['text']+'}'+kind)
   if oldtxt: ET.SubElement(inner,'{'+m.NS['text']+'}p').text=oldtxt
  region('delA','deletion',m.A_OLD); region('insA','insertion')
  s=ET.SubElement(ps[1],'{'+m.NS['text']+'}change-start',{'{'+m.NS['text']+'}change-id':'insA'}); s.tail=m.A_NEW
  e=ET.SubElement(ps[1],'{'+m.NS['text']+'}change-end',{'{'+m.NS['text']+'}change-id':'insA'}); e.tail=''
  c=ET.SubElement(ps[1],'{'+m.NS['text']+'}change',{'{'+m.NS['text']+'}change-id':'delA'})
 if include_b_mark:
  ps[2].text='Escalation contact: '
  s=ET.SubElement(ps[2],'{'+m.NS['text']+'}change-start',{'{'+m.NS['text']+'}change-id':'insB'}); s.tail=m.B_NEW
  e=ET.SubElement(ps[2],'{'+m.NS['text']+'}change-end',{'{'+m.NS['text']+'}change-id':'insB'}); e.tail=''
  # add insertion-region metadata
  tr=office_text.find('./text:tracked-changes',NS)
  r=ET.SubElement(tr,'{'+m.NS['text']+'}changed-region',{'{'+m.NS['text']+'}id':'insB','{http://www.w3.org/XML/1998/namespace}id':'insB'}); ET.SubElement(r,'{'+m.NS['text']+'}insertion')
 ps[2].text='Escalation contact: '
 # B content is plain by default; if marked its trailing text follows start range.
 if not include_b_mark: ps[2].text='Escalation contact: '+m.B_NEW
 return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def test_builder_fixture_has_expected_initial_text(tmp_path):
 xml=fixture_xml(tmp_path); state=m._content_state(xml)
 assert state['paragraphs']==m.BASE_PARAS
 assert state['markers']==0

def test_mech05_a_requires_tracked_replacement(tmp_path):
 result=m.evaluate_bytes(marked(fixture_xml(tmp_path)), 'A')
 assert result['score']==1.0, result
 assert result['checks']['approval_change_tracked']

def test_mech05_b_plain_contact_passes_but_tracked_contact_fails(tmp_path):
 xml=fixture_xml(tmp_path)
 assert m.evaluate_bytes(marked(xml), 'B')['score']==1.0
 assert m.evaluate_bytes(marked(xml, include_b_mark=True), 'B')['score']==0.0

def test_mech05_a_untracked_replacement_does_not_pass(tmp_path):
 xml=fixture_xml(tmp_path)
 root=m.ET.fromstring(xml); ps=root.findall('.//office:text/text:p',{'office':m.NS['office'],'text':m.NS['text']})
 ps[1].text='Approval boundary: '+m.A_NEW
 result=m.evaluate_bytes(m.ET.tostring(root,encoding='utf-8'), 'A')
 assert result['checks']['approval_text_correct']
 assert not result['checks']['approval_change_tracked']
 assert result['score']==0.0


def test_mech05_a_inline_deleted_old_text_is_not_counted_as_active(tmp_path):
 xml=fixture_xml(tmp_path)
 root=m.ET.fromstring(xml)
 ns={'office':m.NS['office'],'text':m.NS['text']}
 body=root.find('.//office:text',ns)
 para=body.findall('./text:p',ns)[1]
 para.text='Approval boundary: '
 tr=body.find('./text:tracked-changes',ns)
 if tr is None:
  tr=m.ET.Element('{'+m.NS['text']+'}tracked-changes')
  body.insert(0,tr)
 def add_region(rid,kind,old=''):
  r=m.ET.SubElement(tr,'{'+m.NS['text']+'}changed-region',{'{'+m.NS['text']+'}id':rid,'{'+m.NS['xml']+'}id':rid})
  inner=m.ET.SubElement(r,'{'+m.NS['text']+'}'+kind)
  if old: m.ET.SubElement(inner,'{'+m.NS['text']+'}p').text=old
 add_region('delInline','deletion',m.A_OLD)
 add_region('insInline','insertion')
 start=m.ET.SubElement(para,'{'+m.NS['text']+'}change-start',{'{'+m.NS['text']+'}change-id':'delInline'})
 start.tail=m.A_OLD
 end=m.ET.SubElement(para,'{'+m.NS['text']+'}change-end',{'{'+m.NS['text']+'}change-id':'delInline'})
 end.tail=''
 ins=m.ET.SubElement(para,'{'+m.NS['text']+'}change-start',{'{'+m.NS['text']+'}change-id':'insInline'})
 ins.tail=m.A_NEW
 m.ET.SubElement(para,'{'+m.NS['text']+'}change-end',{'{'+m.NS['text']+'}change-id':'insInline'})
 result=m.evaluate_bytes(m.ET.tostring(root,encoding='utf-8'),'A')
 assert result['state']['paragraphs'][1].endswith(m.A_OLD+m.A_NEW)
 assert result['state']['active_paragraphs'][1]=='Approval boundary: '+m.A_NEW
 assert result['score']==1.0, result
 # A duplicate old sentence that is ordinary active text must not be hidden by the revision parser.
 para[-1].tail=(para[-1].tail or '')+' '+m.A_OLD
 result2=m.evaluate_bytes(m.ET.tostring(root,encoding='utf-8'),'A')
 assert result2['checks']['approval_text_correct'] is False
