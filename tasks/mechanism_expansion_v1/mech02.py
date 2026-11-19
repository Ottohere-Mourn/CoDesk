"""MECH-02 shared Calc Undo-history candidate."""
from __future__ import annotations
import base64, json, re, shlex, time, xml.etree.ElementTree as ET
from pathlib import Path
from evaluation_examples.task_class import pg_common as pc

NAME = "mech02"
TASK_VERSION = "0.1.1"
HOME = "/home/user"
WORK = f"{HOME}/Documents/MECH02"
ODS = f"{WORK}/qc-sample-log.ods"
ASSETS = Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets")
NS = {
 "office":"urn:oasis:names:tc:opendocument:xmlns:office:1.0",
 "table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0",
 "text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
HEADERS = ["Sample ID","Material","QC Queue","Review note","Observed count","Verified by"]
BASE_ROWS = [
 ["S-4108","Sterile tubing","Routine","","",""],
 ["S-4112","Vial caps","Priority","","",""],
 ["S-4104","Pump seals","Routine","","",""],
 ["S-4120","Test strips","Priority","","",""],
 ["S-4133","Syringe filters","Routine","","",""],
 ["S-4141","Ampoule trays","Priority","","",""],
 ["S-4150","Catheter caps","Routine","","",""],
 ["S-4165","Culture tubes","Priority","","",""],
]
BASE = [HEADERS] + BASE_ROWS
ROW_A = "S-4108"
ROW_B = "S-4112"
_SET_UP = set()

def _win_script():
    title=shlex.quote("qc-sample-log")
    return f"for i in $(seq 60); do wid=$(xdotool search --onlyvisible --name {title} 2>/dev/null | tail -1 || true); [ -n \"$wid\" ] && {{ xdotool windowactivate --sync \"$wid\"; exit 0; }}; sleep 1; done; exit 1"

def _press(sc, script):
    pc.sh(sc, script, timeout=45)

def setup(sc, role):
    key=f"{getattr(sc,'vm_ip','')}:{getattr(sc,'server_port','')}"
    if key in _SET_UP:
        return
    src="mechanism_expansion_v1/mech02/qc-sample-log.ods"
    pc.upload(sc,[(src,ODS)])
    pc.sh(sc,f"mkdir -p {WORK}/baseline && cp {ODS} {WORK}/baseline/qc-sample-log.ods")
    pc.sh(sc,f"setsid -f libreoffice --calc {shlex.quote(ODS)} >/tmp/mech02-calc.log 2>&1 < /dev/null")
    _press(sc,_win_script())
    _press(sc,"xdotool key --clearmodifiers ctrl+home")
    _SET_UP.add(key)

def _read_guest_xml(env):
    code=("import base64,json,sys,zipfile\n"
          "z=zipfile.ZipFile(sys.argv[1]); print('MECH02STATE'+base64.b64encode(z.read('content.xml')).decode())")
    raw=pc.guest(env,f"python3 -c {shlex.quote(code)} {shlex.quote(ODS)}",timeout=90)
    m=re.search(r"MECH02STATE([A-Za-z0-9+/=]+)",raw)
    if not m: return {"read_error":raw[-1200:]}
    try: return {"ods":base64.b64decode(m.group(1))}
    except Exception as e: return {"read_error":f"{type(e).__name__}: {e}"}

def _text(node):
    return "".join(node.itertext()).strip()

def _ods_rows(xml_bytes):
    """Read the first Calc sheet while expanding ODS repeated cells/rows.

    ODF legitimately omits trailing empty cells. Pad to the six-column schema
    so blank trailing columns don't look like missing/corrupted data.
    """
    root=ET.fromstring(xml_bytes)
    tables=root.findall(".//table:table",NS)
    if not tables: return []
    result=[]
    for row in tables[0].findall("./table:table-row",NS):
        values=[]
        for cell in row.findall("./table:table-cell",NS):
            val=cell.get("{%s}value"%NS["office"])
            if val is not None:
                value=val
            else:
                value="".join(_text(p) for p in cell.findall(".//text:p",NS))
            repeat=int(cell.get("{%s}number-columns-repeated"%NS["table"],"1"))
            values.extend([value]*max(1,repeat))
        values=values[:len(HEADERS)]
        values.extend([""]*(len(HEADERS)-len(values)))
        repeat_rows=int(row.get("{%s}number-rows-repeated"%NS["table"],"1"))
        result.extend([list(values) for _ in range(max(1,repeat_rows))])
    return result

def _state(rows):
    if not rows: return {"rows":rows,"row_order":[]}
    idx=HEADERS.index("Sample ID")
    return {"rows":rows,"row_order":[r[idx] for r in rows[1:] if len(r)>idx],
            "a_row":next((r for r in rows[1:] if r and r[0]==ROW_A),[]),
            "b_row":next((r for r in rows[1:] if r and r[0]==ROW_B),[])}

def evaluate(env, role):
    files=_read_guest_xml(env)
    if "read_error" in files:
        return {"score":0.0,"checks":{"ods_readable":False},"state":files}
    rows=_ods_rows(files["ods"])
    st=_state(rows)
    expected_ids=[r[0] for r in BASE_ROWS]
    ids=st["row_order"]
    by_id={r[0]:r for r in rows[1:] if r and r[0]}
    arow=by_id.get(ROW_A,[]); brow=by_id.get(ROW_B,[])
    header_ok=bool(rows and rows[0]==HEADERS)
    readable=(len(rows)==len(BASE) and all(len(r)==len(HEADERS) for r in rows) and header_ok)
    checks={
      "ods_readable":readable,
      "all_sample_ids_present_once":sorted(ids)==sorted(expected_ids) and len(ids)==len(expected_ids),
    }
    if role=="A":
        checks["original_order_restored"]=ids==expected_ids
        checks["a_note_verified"]=len(arow)>3 and arow[3]=="Verified"
    else:
        checks["b_count_427"]=len(brow)>4 and brow[4]=="427"
        checks["b_verifier_jl"]=len(brow)>5 and brow[5]=="JL"
    # These are the only cells either task is authorized to change. Each
    # actor's own required target values are checked separately above.
    allowed={(ROW_A,3),(ROW_B,4),(ROW_B,5)}
    unchanged=True
    if set(by_id)!=set(expected_ids):
        unchanged=False
    else:
        base_by_id={r[0]:r for r in BASE_ROWS}
        for sample_id,want in base_by_id.items():
            got=by_id[sample_id]
            if len(got)!=len(HEADERS):
                unchanged=False; break
            for ci,(actual,expected) in enumerate(zip(got,want)):
                if (sample_id,ci) in allowed:
                    continue
                if str(actual or "")!=str(expected or ""):
                    unchanged=False; break
            if not unchanged: break
    checks["non_target_values_preserved"]=unchanged
    return {"score":1.0 if all(checks.values()) else 0.0,"checks":checks,"state":st,
            "mechanism_evidence":{"not_inferred_from_final_state":True}}

TASKS={
 "A":"In the QC sample log, mark the Review note for sample S-4108 as exactly Verified. Then sort the table by QC Queue ascending, press Ctrl+Z exactly once to undo only your sort and restore the original row order, and save. Do not edit other records.",
 "B":"In the QC sample log, find sample S-4112 (Vial caps) and enter Observed count 427 and Verified by JL in that row. Save the workbook. Do not change other records."
}
