from __future__ import annotations
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from pipeline.grade import make_grade

DRAW="{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}page";TEXT="{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
REQ={"A":{"Core Services":["Identity Gateway","mTLS / token exchange","Rev 2.6"],"Customer Platform":["Customer API","120 requests/minute","Rev 2.6"]},"B":{"Analytics Platform":["Analytics Warehouse","Nightly ingest: 40 GB","Rev 2.6"],"Resilience Layer":["Regional Cache","Failover target: west-2","Rev 2.6"]}}
def pages(path):
 try:
  with zipfile.ZipFile(path) as z:
   if z.read("mimetype").decode()!="application/vnd.oasis.opendocument.graphics":return {}
   root=ET.fromstring(z.read("content.xml"));return {p.get("{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}name"): ["".join(x.itertext()) for x in p.iter() if x.tag in (TEXT+"p",TEXT+"h")] for p in root.iter() if p.tag==DRAW}
 except (OSError,KeyError,zipfile.BadZipFile,ET.ParseError):return {}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";pg=pages(out/"system_topology.odg");pa=all(k in pg and all(x in " ".join(pg[k]) for x in values) for k,values in REQ["A"].items());pb=all(k in pg and all(x in " ".join(pg[k]) for x in values) for k,values in REQ["B"].items());pdfa=(out/"core_services.pdf");pdfb=(out/"platform_layers.pdf");pdfa_ok=pdfa.is_file() and pdfa.stat().st_size>100 and pdfa.read_bytes().startswith(b"%PDF-");pdfb_ok=pdfb.is_file() and pdfb.stat().st_size>100 and pdfb.read_bytes().startswith(b"%PDF-");full=len(pg)==4
 def side(ok,pdfok,prefix):return [{"id":prefix+"01","weight":.8,"passed":ok,"required":True,"evidence":{"two_pages_match_required_labels_notes_and_revision":ok}},{"id":prefix+"02","weight":.2,"passed":pdfok,"required":True,"evidence":{"section_pdf_valid":pdfok}}]
 a=side(pa,pdfa_ok,"A");b=side(pb,pdfb_ok,"B");j=[{"id":"J01","weight":1,"passed":full and pa and pb,"required":True,"evidence":{"four_page_document_preserved_and_updated":full and pa and pb}},{"id":"J02","weight":1,"passed":pdfa_ok and pdfb_ok,"required":True,"evidence":{"both_exports_present":pdfa_ok and pdfb_ok}}]
 return make_grade(case_id="BC-16",run_id=run_id,actor_a_checks=a,actor_b_checks=b,joint_checks=j,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-16 host ODG/XML and PDF header/size checks"})
