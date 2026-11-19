import sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
OFFICE='urn:oasis:names:tc:opendocument:xmlns:office:1.0'
TEXT='urn:oasis:names:tc:opendocument:xmlns:text:1.0'
STYLE='urn:oasis:names:tc:opendocument:xmlns:style:1.0'
FO='urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'
MAN='urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
MIME='application/vnd.oasis.opendocument.text'
LINES=['Access review — Draft 18 November 2026','Approval boundary: Pilot access is limited to two named reviewers.','Escalation contact: Pending confirmation.','Control text: Preserve exactly TRACE-ONLY-77.']
def xml(node): return ET.tostring(node,encoding='utf-8',xml_declaration=True)
def build(path):
 for p,u in [('office',OFFICE),('text',TEXT),('style',STYLE),('fo',FO),('manifest',MAN)]: ET.register_namespace(p,u)
 root=ET.Element('{%s}document-content'%OFFICE,{'{%s}version'%OFFICE:'1.2'})
 body=ET.SubElement(root,'{%s}body'%OFFICE); doc=ET.SubElement(body,'{%s}text'%OFFICE)
 for line in LINES: ET.SubElement(doc,'{%s}p'%TEXT).text=line
 styles=ET.Element('{%s}document-styles'%OFFICE,{'{%s}version'%OFFICE:'1.2'})
 ET.SubElement(styles,'{%s}styles'%OFFICE); ET.SubElement(styles,'{%s}automatic-styles'%OFFICE); ET.SubElement(styles,'{%s}master-styles'%OFFICE)
 meta=ET.Element('{%s}document-meta'%OFFICE,{'{%s}version'%OFFICE:'1.2'}); ET.SubElement(meta,'{%s}meta'%OFFICE)
 settings=ET.Element('{%s}document-settings'%OFFICE,{'{%s}version'%OFFICE:'1.2'}); ET.SubElement(settings,'{%s}settings'%OFFICE)
 manifest=ET.Element('{%s}manifest'%MAN,{'{%s}version'%MAN:'1.2'})
 ET.SubElement(manifest,'{%s}file-entry'%MAN,{'{%s}full-path'%MAN:'/','{%s}version'%MAN:'1.2','{%s}media-type'%MAN:MIME})
 for name in ('content.xml','styles.xml','meta.xml','settings.xml'): ET.SubElement(manifest,'{%s}file-entry'%MAN,{'{%s}full-path'%MAN:name,'{%s}media-type'%MAN:'text/xml'})
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(path,'w') as z:
  i=zipfile.ZipInfo('mimetype'); i.compress_type=zipfile.ZIP_STORED; z.writestr(i,MIME)
  for name,data in [('content.xml',xml(root)),('styles.xml',xml(styles)),('meta.xml',xml(meta)),('settings.xml',xml(settings)),('META-INF/manifest.xml',xml(manifest))]: z.writestr(name,data,compress_type=zipfile.ZIP_DEFLATED)
if __name__=='__main__': build(sys.argv[1])
