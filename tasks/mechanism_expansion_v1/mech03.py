"""MECH-03 Writer/Calc focus routing candidate."""
from __future__ import annotations
import base64, json, re, shlex, time, xml.etree.ElementTree as ET
from pathlib import Path
from evaluation_examples.task_class import pg_common as pc

NAME = "mech03"
TASK_VERSION = "0.6.0"
HOME = "/home/user"
WORK = f"{HOME}/Documents/MECH03"
ODS = f"{WORK}/service-adjustments.ods"
ODT = f"{WORK}/customer-response.odt"
EXPECTED_REPLY = "We have received your service request and will respond by 3 PM."
BASE_GRID = [
 ["Service ID","Customer","Adjustment status","Approved credit"],
 ["SR-2001","Maple Grove","Closed","0.00"],
 ["SR-2004","Cedar Works","Closed","0.00"],
 ["SR-2010","North Shore","Reviewed","0.00"],
 ["SR-2016","Blue Peak","Reviewed","0.00"],
 ["SR-2022","Orchard Labs","Pending","0.00"],
 ["SR-2029","Westlake Clinic","Pending","0.00"],
 ["SR-2032","Brightline","Approved","0.00"],
 ["SR-2038","Hawthorne","Approved","0.00"],
 ["SR-2047","Fairview Co-op","Pending","0.00"],
 ["SR-2055","Lakeside Motors","Reviewed","0.00"],
 ["SR-2081","Kestrel Supplies","Approved",""],
]
NS = {"office":"urn:oasis:names:tc:opendocument:xmlns:office:1.0",
      "table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0",
      "text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
_SETUP = set()

def _win_script(title):
    q=shlex.quote(title)
    return f"for i in $(seq 60); do wid=$(xdotool search --onlyvisible --name {q} 2>/dev/null | tail -1 || true); [ -n \"$wid\" ] && {{ xdotool windowactivate --sync \"$wid\"; exit 0; }}; sleep 1; done; exit 1"

def _press(sc, key_script):
    pc.sh(sc, key_script, timeout=45)

def setup(sc, role):
    key=f"{getattr(sc,'vm_ip','')}:{getattr(sc,'server_port','')}"
    first=key not in _SETUP
    if first:
        pc.upload(sc,[
          ("mechanism_expansion_v1/mech03/customer-response.odt",ODT),
          ("mechanism_expansion_v1/mech03/service-adjustments.ods",ODS)])
        pc.sh(sc,f"mkdir -p {WORK}/baseline && cp {ODT} {WORK}/baseline/customer-response.odt && cp {ODS} {WORK}/baseline/service-adjustments.ods")
        pc.sh(sc,f"setsid -f libreoffice --calc {shlex.quote(ODS)} >/tmp/mech03-calc.log 2>&1 < /dev/null")
        _press(sc,_win_script("service-adjustments"))
        # The fixture opens with A1 selected. D12 is the target cell.
        _press(sc,"xdotool key --clearmodifiers Down Down Down Down Down Down Down Down Down Down Down Right Right Right; xdotool mousemove --sync 420 500 click 1")
        pc.sh(sc,f"setsid -f libreoffice --writer {shlex.quote(ODT)} >/tmp/mech03-writer.log 2>&1 < /dev/null")
        _press(sc,_win_script("customer-response"))
        # Place the Writer insertion point in the draft without preselecting it.
        _press(sc,"xdotool mousemove --sync 650 295 click 1")
        _SETUP.add(key)
        # For every arm the Writer window is initially frontmost, so the Calc actor must
        # switch windows. In Shared, task B setup leaves that common focus unchanged.
        target="customer-response"
        _press(sc,_win_script(target))
    elif role=="A":
        _press(sc,_win_script("service-adjustments"))
    # A second role setup in the same shared Guest must not steal the initial Writer focus
    # or overwrite documents while LibreOffice has them open.


def _read_guest_xml(env):
    code = ("import base64,json,sys,zipfile\n"
            "out={}\n"
            "for key,path in [('ods',sys.argv[1]),('odt',sys.argv[2])]:\n"
            " z=zipfile.ZipFile(path); out[key]=base64.b64encode(z.read('content.xml')).decode('ascii')\n"
            "print('MECH03STATE'+json.dumps(out))")
    cmd=f"python3 -c {shlex.quote(code)} {shlex.quote(ODS)} {shlex.quote(ODT)}"
    raw=pc.guest(env,cmd,timeout=90)
    m=re.search(r"MECH03STATE(\{.*\})",raw,re.S)
    if not m:
        return {"read_error":raw[-1500:]}
    try:
        b64=json.loads(m.group(1))
        return {k:base64.b64decode(v) for k,v in b64.items()}
    except Exception as e:
        return {"read_error":f"{type(e).__name__}: {e}"}

def _text(node):
    return "".join(node.itertext()).strip()

def _ods_values(xml_bytes):
    root=ET.fromstring(xml_bytes)
    tables=root.findall(".//table:table",NS)
    if not tables:return []
    values=[]
    for row in tables[0].findall(".//table:table-row",NS):
        cells=[]
        for cell in row.findall("./table:table-cell",NS):
            vtype=cell.get("{%s}value-type"%NS["office"])
            value=cell.get("{%s}value"%NS["office"])
            if value is not None and vtype in ("float","currency","percentage"):
                cells.append(value)
            else:
                paras=cell.findall(".//text:p",NS)
                cells.append("".join(_text(p) for p in paras))
        values.append(cells)
    return values

def _odt_paragraphs(xml_bytes):
    root=ET.fromstring(xml_bytes)
    return [_text(p) for p in root.findall(".//text:p",NS)]

def _matches_credit(v):
    try:return round(float(str(v).strip()),2)==1250.00
    except Exception:return False

def evaluate(env, role):
    files=_read_guest_xml(env)
    if "read_error" in files:
        return {"score":0.0,"checks":{"documents_readable":False},"state":files}
    grid=_ods_values(files["ods"])
    paragraphs=_odt_paragraphs(files["odt"])
    headers=grid[0] if grid else []
    target_col=headers.index("Approved credit") if "Approved credit" in headers else None
    target_rows=[r for r in grid[1:] if r and r[0]=="SR-2081"]
    target=target_rows[-1] if target_rows else []
    credit=target[target_col] if target_col is not None and len(target)>target_col else ""
    reply=next((p for p in paragraphs if p and p!="Draft response pending."),"")
    non_target_ok = len(grid)==len(BASE_GRID) and all(
        (str(got or "").strip()==str(want or "").strip())
        for ri,(gotrow,wantrow) in enumerate(zip(grid,BASE_GRID))
        for ci,(got,want) in enumerate(zip(gotrow,wantrow))
        if not (ri==11 and ci==3))
    if role=="A":
        checks={"ods_readable":bool(grid),"target_service_id_present":bool(target_rows),
                "credit_1250":_matches_credit(credit),"calc_non_target_cells_unchanged":non_target_ok}
    else:
        checks={"odt_readable":bool(paragraphs),"exact_reply":paragraphs==[EXPECTED_REPLY]}
    success=bool(checks) and all(checks.values())
    state={"role":role,"headers":headers,"target_row":target,"credit_raw":credit,
           "paragraphs":paragraphs,"sheet_rows":len(grid),"calc_non_target_cells_unchanged":non_target_ok}
    return {"score":1.0 if success else 0.0,"checks":checks,"state":state,
            "mechanism_evidence":{"not_inferred_from_final_state":True}}

TASKS={
 "A":"In LibreOffice Calc, update Approved credit in D12 for SR-2081 (Kestrel Supplies) to exactly 1250.00 and save with Ctrl+S. Writer is initially frontmost; switch to Calc with Alt+Tab. Click directly inside the D12 target cell to focus the grid, type 1250.00, then press Enter. Do not edit other cells or Writer.",
 "B":"In LibreOffice Writer, replace the draft paragraph with exactly: We have received your service request and will respond by 3 PM. If another window is in front, activate the open Writer window first. Press Ctrl+A to select the draft, type the exact reply, and press Ctrl+S to save. Do not edit Calc."
}
