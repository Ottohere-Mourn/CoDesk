from __future__ import annotations
import csv,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from pipeline.grade import make_grade
NS={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","office":"urn:oasis:names:tc:opendocument:xmlns:office:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
def parse_ods(path):
 try:
  with zipfile.ZipFile(path) as z:
   if z.read("mimetype").decode()!="application/vnd.oasis.opendocument.spreadsheet":return {}
   root=ET.fromstring(z.read("content.xml"));out={}
   for t in root.findall(".//table:table",NS):
    rows=[]
    for r in t.findall("table:table-row",NS):
     cells=[]
     for c in r.findall("table:table-cell",NS):cells.extend([{ "value":c.get("{"+NS["office"]+"}value"),"formula":c.get("{"+NS["table"]+"}formula"),"text":"".join(c.itertext())}] * min(64,int(c.get("{"+NS["table"]+"}number-columns-repeated","1"))))
     rows.extend([cells] * min(64,int(r.get("{"+NS["table"]+"}number-rows-repeated","1"))))
    out[t.get("{"+NS["table"]+"}name")]=rows
   return out
 except (OSError,KeyError,zipfile.BadZipFile,ET.ParseError):return {}
def expected(path,half):
 latest={}
 try:
  with Path(path).open(encoding="utf-8",newline="") as f:
   for r in csv.DictReader(f):
    if r["half"]!=half or r["status"]!="ACTIVE":continue
    key=r["department"];rev=int(r["revision"])
    if key not in latest or rev>int(latest[key]["revision"]):latest[key]=r
 except OSError:pass
 result={}
 for dept,r in latest.items():
  requested=int(r["request_usd"]);approved=requested if r["protected"]=="YES" else round(requested*.96);result[dept]={"requested":requested,"protected":r["protected"],"approved":approved,"reduction":requested-approved}
 return result
def check_half(tables,name,want):
 rows=tables.get(name,[]);found={};formula_ok=True
 for r in rows[1:4]:
  if not r:continue
  dept=r[0].get("text","");
  if dept not in want or len(r)<5:continue
  try:entry={"requested":int(float(r[1]["value"])),"protected":r[2]["text"],"approved":int(float(r[3]["value"])),"reduction":int(float(r[4]["value"]))}
  except (TypeError,ValueError):continue
  found[dept]=entry;formula_ok=formula_ok and bool(r[3].get("formula")) and bool(r[4].get("formula"))
 totalrow=rows[4] if len(rows)>4 else [];summary_ok=bool(totalrow and len(totalrow)>4 and totalrow[3].get("formula") and totalrow[4].get("formula"))
 return found==want and formula_ok and summary_ok,found
def _json(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return {}
def grade_episode(snapshot_root:Path,receipt:dict,run_id:str):
 root=Path(snapshot_root);out=root.parent/"guest-output";fixtures=root.parent/"guest-inputs";tables=parse_ods(root/"budget_master.ods");a_want=expected(fixtures/"budget_requests.csv","H1");b_want=expected(fixtures/"budget_requests.csv","H2");a_ok,ar=check_half(tables,"Budget_H1",a_want);b_ok,br=check_half(tables,"Budget_H2",b_want);aj=_json(out/"h1_summary.json");bj=_json(out/"h2_summary.json");a_sum=aj.get("departments")==a_want and aj.get("approved_total")==sum(x["approved"] for x in a_want.values());b_sum=bj.get("departments")==b_want and bj.get("approved_total")==sum(x["approved"] for x in b_want.values());pa=out/"h1_budget.pdf";pb=out/"h2_budget.pdf";p_a=pa.is_file() and pa.stat().st_size>50 and pa.read_bytes().startswith(b"%PDF-");p_b=pb.is_file() and pb.stat().st_size>50 and pb.read_bytes().startswith(b"%PDF-")
 ac=[{"id":"A01","weight":.65,"passed":a_ok,"required":True,"evidence":{"h1_values_and_formulas_match":a_ok}},{"id":"A02","weight":.2,"passed":a_sum,"required":True,"evidence":{"h1_summary_matches":a_sum}},{"id":"A03","weight":.15,"passed":p_a,"required":True,"evidence":{"h1_pdf_valid":p_a}}];bc=[{"id":"B01","weight":.65,"passed":b_ok,"required":True,"evidence":{"h2_values_and_formulas_match":b_ok}},{"id":"B02","weight":.2,"passed":b_sum,"required":True,"evidence":{"h2_summary_matches":b_sum}},{"id":"B03","weight":.15,"passed":p_b,"required":True,"evidence":{"h2_pdf_valid":p_b}}];joint=[{"id":"J01","weight":1,"passed":bool(tables.get("Summary")) and a_ok and b_ok,"required":True,"evidence":{"shared_workbook_and_both_halves_complete":bool(tables.get("Summary")) and a_ok and b_ok}},{"id":"J02","weight":1,"passed":p_a and p_b,"required":True,"evidence":{"both_pdfs_valid":p_a and p_b}}]
 return make_grade(case_id="BC-20",run_id=run_id,actor_a_checks=ac,actor_b_checks=bc,joint_checks=joint,pass_threshold_a=.8,pass_threshold_b=.8,run_metadata={"oracle":"BC-20 host ODS formula/value and source request recomputation"})
