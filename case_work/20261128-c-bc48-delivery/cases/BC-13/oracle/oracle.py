from __future__ import annotations
import unicodedata,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from pipeline.grade import make_grade

GERMAN=["Guten Morgen, wir best\u00e4tigen Ihren Termin in M\u00fcnchen.","Die Gr\u00f6\u00dfe des Pakets entspricht der bestellten Variante.","Bitte pr\u00fcfen Sie die Stra\u00dfe und die Postleitzahl.","Ihre R\u00fccksendung ist am n\u00e4chsten Werktag unterwegs.","\u00d6ffnen Sie die Einstellungen f\u00fcr den gew\u00e4hlten Tarif.","Vielen Dank f\u00fcr Ihre R\u00fcckmeldung zum Lieferzeitfenster."]
POLISH=["Przesy\u0142ka dotar\u0142a do \u0141odzi o godzinie osiemnastej.","Prosz\u0119 zg\u0142osi\u0107 usterk\u0119 przez panel serwisowy.","Zasilanie awaryjne jest gotowe do przegl\u0105du.","W\u0142\u0105cznik pozostaje w pozycji bezpiecznej.","Instrukcja zawiera aktualne dane techniczne.","Dzi\u0119kujemy za potwierdzenie odbioru urz\u0105dzenia."]
NS="{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
def doc_text(path):
 try:
  with zipfile.ZipFile(path) as z:
   if z.read("mimetype").decode()!="application/vnd.oasis.opendocument.text":return ""
   root=ET.fromstring(z.read("content.xml"));return "\n".join("".join(x.itertext()) for x in root.iter() if x.tag in (NS+"p",NS+"h"))
 except (OSError,KeyError,zipfile.BadZipFile,ET.ParseError):return ""
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";text=doc_text(out/"shared_release.odt");pdf=(out/"shared_release.pdf");pdf_ok=pdf.is_file() and pdf.stat().st_size>100 and pdf.read_bytes().startswith(b"%PDF-");nfc=unicodedata.normalize("NFC",text)==text
 def checks(items,prefix):
  found=sum(x in text for x in items);complete=found==len(items);section=all(s in text for s in ("Localization Release Brief","Release window: Q4 2026","German Service Notices","Polish Maintenance Notes"))
  norm=nfc and "\ufffd" not in text
  return [{"id":prefix+"01","weight":.6,"passed":complete,"score":found/len(items),"required":True,"evidence":{"exact_entries_found":found,"expected":len(items)}},{"id":prefix+"02","weight":.2,"passed":section,"required":True,"evidence":{"template_sections_preserved":section}},{"id":prefix+"03","weight":.2,"passed":norm,"required":True,"evidence":{"document_text_is_nfc_and_no_replacement_character":norm}}]
 a=checks(GERMAN,"A");b=checks(POLISH,"B");joint=[{"id":"J01","weight":1,"passed":bool(text) and pdf_ok,"required":True,"evidence":{"valid_odt_and_pdf_present":bool(text) and pdf_ok}},{"id":"J02","weight":1,"passed":all(x["passed"] for x in a+b),"required":True,"evidence":{"both_localization_sections_complete":all(x["passed"] for x in a+b)}}]
 return make_grade(case_id="BC-13",run_id=run_id,actor_a_checks=a,actor_b_checks=b,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-13 host ODT/XML, Unicode NFC and PDF checks"})
