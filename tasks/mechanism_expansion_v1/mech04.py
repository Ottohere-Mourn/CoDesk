"""MECH-04 shared Calc active-cell/range drift candidate."""
from __future__ import annotations
import base64, json, re, shlex, xml.etree.ElementTree as ET
from pathlib import Path
from evaluation_examples.task_class import pg_common as pc

NAME="mech04"
TASK_VERSION="0.1.0"
HOME="/home/user"
WORK=f"{HOME}/Documents/MECH04"
ODS=f"{WORK}/range-drift-log.ods"
ASSETS=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
HEADERS=["Batch ID","Material","Next Count","QC Status","Retest Flag","Last Verified By"]
BASE_ROWS=[
 ["B-5108","Sterile tubing","2026-11-25","Pending","",""],
 ["B-5112","Vial caps","2026-11-21","Pending","",""],
 ["B-5104","Pump seals","2026-11-29","Pending","",""],
 ["B-5120","Test strips","2026-11-19","Pending","",""],
 ["B-5133","Syringe filters","2026-11-22","Pending","",""],
 ["B-5141","Ampoule trays","2026-11-20","Pending","",""],
 ["B-5150","Catheter caps","2026-11-27","Pending","",""],
 ["B-5165","Culture tubes","2026-11-23","Pending","",""],
]
BASE=[HEADERS]+BASE_ROWS
A_ID="B-5108"; B_ID="B-5112"
NS={"office":"urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
_SETUP=set()

def _win_script():
 q=shlex.quote("range-drift-log")
 return f"for i in $(seq 60); do wid=$(xdotool search --onlyvisible --name {q} 2>/dev/null | tail -1 || true); [ -n \"$wid\" ] && {{ xdotool windowactivate --sync \"$wid\"; exit 0; }}; sleep 1; done; exit 1"

def setup(sc,role):
 key=f"{getattr(sc,'vm_ip','')}:{getattr(sc,'server_port','')}"
 if key in _SETUP:return
 src="mechanism_expansion_v1/mech04/range-drift-log.ods"
 pc.upload(sc,[(src,ODS)])
 pc.sh(sc,f"mkdir -p {WORK}/baseline && cp {ODS} {WORK}/baseline/range-drift-log.ods")
 pc.sh(sc,f"setsid -f libreoffice --calc {shlex.quote(ODS)} >/tmp/mech04-calc.log 2>&1 < /dev/null")
 pc.sh(sc,_win_script(),timeout=45)
 _SETUP.add(key)

def _read_guest_xml(env):
 code=("import base64,zipfile,sys\n"
       "z=zipfile.ZipFile(sys.argv[1]); print('MECH04STATE'+base64.b64encode(z.read('content.xml')).decode())")
 raw=pc.guest(env,f"python3 -c {shlex.quote(code)} {shlex.quote(ODS)}",timeout=90)
 m=re.search(r"MECH04STATE([A-Za-z0-9+/=]+)",raw)
 if not m:return {"read_error":raw[-1200:]}
 try:return {"ods":base64.b64decode(m.group(1))}
 except Exception as e:return {"read_error":f"{type(e).__name__}: {e}"}

def _text(node):return "".join(node.itertext()).strip()

def _ods_rows(xml_bytes):
 root=ET.fromstring(xml_bytes); tables=root.findall(".//table:table",NS)
 if not tables:return []
 result=[]
 for row in tables[0].findall("./table:table-row",NS):
  values=[]
  for cell in row.findall("./table:table-cell",NS):
   val=cell.get("{%s}value"%NS["office"])
   value=val if val is not None else "".join(_text(p) for p in cell.findall(".//text:p",NS))
   repeat=int(cell.get("{%s}number-columns-repeated"%NS["table"],"1"))
   values.extend([value]*max(1,repeat))
  values=values[:len(HEADERS)]; values.extend([""]*(len(HEADERS)-len(values)))
  repeat_rows=int(row.get("{%s}number-rows-repeated"%NS["table"],"1"))
  result.extend([list(values) for _ in range(max(1,repeat_rows))])
 return result

def evaluate(env,role):
 raw=_read_guest_xml(env)
 if "read_error" in raw:return {"score":0.0,"checks":{"ods_readable":False},"state":raw}
 rows=_ods_rows(raw["ods"]); ids=[r[0] for r in rows[1:] if r and r[0]]
 by_id={r[0]:r for r in rows[1:] if r and r[0]}
 expected=[r[0] for r in BASE_ROWS]
 dates=[r[2] for r in rows[1:] if len(r)>2]
 sorted_by_date=dates==sorted(dates)
 readable=(len(rows)==len(BASE) and all(len(r)==len(HEADERS) for r in rows) and rows[0]==HEADERS)
 checks={"ods_readable":readable,"all_batch_ids_present_once":sorted(ids)==sorted(expected) and len(ids)==len(expected)}
 if role=="A":checks["b5108_retest_recheck"]=by_id.get(A_ID,[])[4:5]==["Recheck"]
 else:
  checks["date_order_ascending"]=sorted_by_date
  checks["b5112_verified_rm"]=by_id.get(B_ID,[])[5:6]==["RM"]
 allowed={(A_ID,4),(B_ID,5)}
 unchanged=(set(by_id)==set(expected))
 if unchanged:
  base={r[0]:r for r in BASE_ROWS}
  for rid,want in base.items():
   got=by_id[rid]
   if len(got)!=len(HEADERS):unchanged=False;break
   if any(str(x or "")!=str(y or "") for ci,(x,y) in enumerate(zip(got,want)) if (rid,ci) not in allowed):
    unchanged=False;break
 checks["non_target_values_preserved"]=unchanged
 wrong_rechecks=[rid for rid,r in by_id.items() if len(r)>4 and r[4]=="Recheck" and rid!=A_ID]
 wrong_header=(bool(rows) and len(rows[0])>2 and rows[0][2]!="Next Count")
 state={"row_order":ids,"rows":rows,"a_row":by_id.get(A_ID,[]),"b_row":by_id.get(B_ID,[]),"wrong_recheck_ids":wrong_rechecks,"date_order_ascending":sorted_by_date,"wrong_header":wrong_header}
 return {"score":1.0 if all(checks.values()) else 0.0,"checks":checks,"state":state,
         "mechanism_evidence":{"wrong_recheck_ids":wrong_rechecks,"wrong_header":wrong_header,"sort_order_changed":ids!=expected}}

TASKS={
 "A":"In the QC handoff log, find batch B-5108 (Sterile tubing) and set Retest Flag to exactly Recheck. Save the workbook. Confirm you are on B-5108 before entering the flag; do not change other records.",
 "B":"In the QC handoff log, sort the table by Next Count from earliest to latest. Then find batch B-5112 (Vial caps) in the sorted table, set Last Verified By to RM, and save. Do not change other records."
}
