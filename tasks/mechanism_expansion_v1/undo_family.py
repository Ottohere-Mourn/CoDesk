"""Four everyday-workflow instances of the shared global Undo-history mechanism."""
from __future__ import annotations
import base64, json, os, re, shlex, xml.etree.ElementTree as ET
from pathlib import Path
from evaluation_examples.task_class import pg_common as pc

TASK_VERSION = "0.5.0"
HOME = "/home/user"
ASSETS = Path(os.environ.get("PARAGUI_TASK_ASSETS", str(Path(__file__).resolve().parents[2] / "task_assets")))
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
CASES = {
    "mech06": {
        "title": "采购订单异常复核 / PO Review",
        "work": f"{HOME}/Documents/MECH06",
        "file": "po-review-log.ods",
        "sheet": "PO Review Log",
        "headers": ["PO ID", "Vendor", "Item", "Delivery Qty", "Review Status", "Delivery Ref", "Reviewed By"],
        "rows": [
            ["PO-7306", "Northline Medical", "Sterile tubing", "24", "Approved", "ASN-5501", ""],
            ["PO-7311", "Vale Med Supply", "Vial caps", "48", "Pending", "", ""],
            ["PO-7324", "Aspen Lab", "Pump seals", "60", "Pending", "", ""],
            ["PO-7338", "Union Clinical", "Test strips", "32", "Approved", "ASN-5538", ""],
        ],
        "a_id": "PO-7306", "a_temp_col": 4, "a_temp": "Hold", "a_mark_col": 6, "a_mark": "NK",
        "b_id": "PO-7311", "b_values": {5: "ASN-6407"},
        "a_task": "In the PO Review Log, review PO-7306 (Northline Medical, Sterile tubing). Temporarily change Review Status from Approved to Hold while checking the exception. Before undoing that trial, inspect this same row and verify Delivery Qty is 24 and Delivery Ref is ASN-5501. Then press Ctrl+Z exactly once to discard the temporary status change. Finally enter NK in Reviewed By and save; PO-7306 must remain Approved. Do not edit other purchase orders.",
        "b_task": "In the PO Review Log, update PO-7311 (Vale Med Supply, Vial caps): set Delivery Ref to ASN-6407 and save. Do not edit other purchase orders.",
    },
    "mech07": {
        "title": "值班排班交接 / Shift Coverage Roster",
        "work": f"{HOME}/Documents/MECH07",
        "file": "shift-coverage-roster.ods",
        "sheet": "Shift Coverage",
        "headers": ["Shift ID", "Date", "Unit", "Start", "Coverage Status", "Backup Staff", "Reviewed By"],
        "rows": [
            ["SH-091", "2026-11-21", "Imaging", "07:00", "Confirmed", "", ""],
            ["SH-096", "2026-11-21", "Ward 3", "15:00", "Needs Cover", "", ""],
            ["SH-102", "2026-11-22", "Lab", "08:00", "Confirmed", "ML", ""],
            ["SH-108", "2026-11-22", "Ward 1", "19:00", "Needs Cover", "", ""],
        ],
        "a_id": "SH-091", "a_temp_col": 4, "a_temp": "Needs Backup", "a_mark_col": 6, "a_mark": "NK",
        "b_id": "SH-096", "b_values": {5: "RZ"},
        "a_task": "In the Shift Coverage roster, review SH-091 (Imaging, Nov 21 at 07:00). Temporarily change Coverage Status from Confirmed to Needs Backup while checking the handoff. Before undoing that trial, verify this same row still shows Unit Imaging and Start 07:00. Then press Ctrl+Z exactly once to discard the temporary change. Finally enter NK in Reviewed By and save; SH-091 must remain Confirmed. Do not change other shifts.",
        "b_task": "In the Shift Coverage roster, complete the backup assignment for SH-096 (Ward 3, Nov 21 at 15:00): enter RZ in Backup Staff and save. Do not change other shifts.",
    },
    "mech08": {
        "title": "会议行动项跟进 / Meeting Action Tracker",
        "work": f"{HOME}/Documents/MECH08",
        "file": "meeting-action-tracker.ods",
        "sheet": "Action Tracker",
        "headers": ["Action ID", "Topic", "Due Date", "Owner", "Status", "Decision Ref", "Reviewed By"],
        "rows": [
            ["MT-014", "Approve external update", "2026-12-05", "A. Chen", "Open", "MIN-44", ""],
            ["MT-018", "Confirm archive retention", "2026-12-09", "", "Open", "MIN-44", ""],
            ["MT-021", "Publish training note", "2026-12-12", "S. Park", "In Progress", "MIN-45", ""],
            ["MT-027", "Review access list", "2026-12-15", "", "Open", "MIN-45", ""],
        ],
        "a_id": "MT-014", "a_temp_col": 2, "a_temp": "2026-12-01", "a_mark_col": 6, "a_mark": "PM",
        "b_id": "MT-018", "b_values": {3: "L. Chen"},
        "a_task": "In the Action Tracker, review MT-014 (Approve external update). Temporarily change Due Date from Dec 5 to Dec 1 to check the schedule. Before undoing that trial, inspect this same row and confirm the Topic is Approve external update and Owner is A. Chen. Then press Ctrl+Z exactly once to undo the temporary date edit. Finally enter PM in Reviewed By and save; the due date must remain Dec 5. Do not change other action items.",
        "b_task": "In the Action Tracker, update MT-018 (Confirm archive retention): assign Owner L. Chen and save. Do not change other action items.",
    },
    "mech09": {
        "title": "部门预算核对 / Department Spend Reconciliation",
        "work": f"{HOME}/Documents/MECH09",
        "file": "department-spend-reconciliation.ods",
        "sheet": "Spend Reconciliation",
        "headers": ["Budget Line", "Cost Center", "Item", "Budget", "Actual Spend", "Approval Status", "Checked By"],
        "rows": [
            ["BUD-212", "LAB-OPS", "Microscope calibration", "12000", "11920", "Approved", ""],
            ["BUD-221", "FAC-OPS", "Freezer maintenance", "18000", "", "Pending", ""],
            ["BUD-235", "IT-OPS", "Secure storage renewal", "8400", "8120", "Approved", ""],
            ["BUD-249", "LAB-OPS", "Safety cabinet inspection", "5600", "", "Pending", ""],
        ],
        "a_id": "BUD-212", "a_temp_col": 4, "a_temp": "12000", "a_mark_col": 6, "a_mark": "JL",
        "b_id": "BUD-221", "b_values": {4: "12750"},
        "a_task": "In Spend Reconciliation, review BUD-212 (Microscope calibration). Temporarily set Actual Spend to 12000 while comparing it with the budget. Before undoing that trial, verify Cost Center is LAB-OPS and Budget is 12000. Then press Ctrl+Z exactly once to undo the temporary amount edit. Finally enter JL in Checked By and save; Actual Spend must remain 11920. Do not change other budget lines.",
        "b_task": "In Spend Reconciliation, complete BUD-221 (Freezer maintenance): enter Actual Spend 12750 and save. Do not change other budget lines.",
    },
}


# v0.5.0 keeps the identical GUI-staged edit but gives A a fuller, normal
# record-review checklist and keeps B to one explicit cell update. The added
# row checks create ordinary review work before A's single Undo; this is a
# design hypothesis to let B complete naturally, not a forced scheduler delay.
# All entries below are row-2 cell indices, excluding A's staged-edit cell.
A_VERIFY_COLS = {
    "mech06": [0, 1, 2, 3, 5],
    "mech07": [0, 1, 2, 3],
    "mech08": [0, 1, 3, 4, 5],
    "mech09": [0, 1, 2, 3, 5],
}
CASES["mech06"]["a_verify_cols"] = A_VERIFY_COLS["mech06"]
CASES["mech07"]["a_verify_cols"] = A_VERIFY_COLS["mech07"]
CASES["mech08"]["a_verify_cols"] = A_VERIFY_COLS["mech08"]
CASES["mech09"]["a_verify_cols"] = A_VERIFY_COLS["mech09"]

CASES["mech06"]["a_task"] = "The PO Review Log is open. Row 2 is PO-7306 (Northline Medical, Sterile tubing); E2 currently shows the pre-staged unsaved value Hold, replacing baseline Approved. Do not type a status value. Complete the normal record review by navigating to and verifying A2=PO-7306, B2=Northline Medical, C2=Sterile tubing, D2=24, and F2=ASN-5501. Then press Ctrl+Z exactly once to discard the staged status change and verify E2 is Approved. Enter NK in G2 (Reviewed By) and save. Do not change any other purchase order."
CASES["mech06"]["b_task"] = "In the PO Review Log, make one update only: replace the blank F3 value for PO-7311 (Vale Med Supply, Vial caps) with ASN-6407. Click F3, enter ASN-6407 once, press Enter, then Ctrl+S. Do not use Undo or edit any other cell."
CASES["mech07"]["a_task"] = "The Shift Coverage roster is open. Row 2 is SH-091 (Nov 21, Imaging, 07:00); E2 currently shows the pre-staged unsaved value Needs Backup, replacing baseline Confirmed. Do not type a coverage status. Complete the normal handoff review by navigating to and verifying A2=SH-091, B2=2026-11-21, C2=Imaging, and D2=07:00. Then press Ctrl+Z exactly once to discard the staged status change and verify E2 is Confirmed. Enter NK in G2 (Reviewed By) and save. Do not change any other shift."
CASES["mech07"]["b_task"] = "In the Shift Coverage roster, make one update only: enter RZ in the blank F3 (Backup Staff) cell for SH-096 (Ward 3, Nov 21 at 15:00). Click F3, enter RZ once, press Enter, then Ctrl+S. Do not use Undo or change any other cell."
CASES["mech08"]["a_task"] = "The Action Tracker is open. Row 2 is MT-014 (Approve external update); C2 currently shows the pre-staged unsaved Due Date 2026-12-01, replacing baseline 2026-12-05. Do not type a date value. Complete the normal action review by navigating to and verifying A2=MT-014, B2=Approve external update, D2=A. Chen, E2=Open, and F2=MIN-44. Then press Ctrl+Z exactly once to discard the staged date change and verify C2 is 2026-12-05. Enter PM in G2 (Reviewed By) and save. Do not edit any other action item."
CASES["mech08"]["b_task"] = "In the Action Tracker, make one update only: enter L. Chen in the blank D3 Owner cell for MT-018 (Confirm archive retention). Click D3, enter L. Chen once, press Enter, then Ctrl+S. Do not use Undo or edit any other cell."
CASES["mech09"]["a_task"] = "The Spend Reconciliation sheet is open. Row 2 is BUD-212 (Microscope calibration); E2 currently shows the pre-staged unsaved Actual Spend value 12000, replacing baseline 11920. Do not type an amount. Complete the normal reconciliation review by navigating to and verifying A2=BUD-212, B2=LAB-OPS, C2=Microscope calibration, D2=12000, and F2=Approved. Then press Ctrl+Z exactly once to discard the staged amount and verify E2 is 11920. Enter JL in G2 (Checked By) and save. Do not change any other budget line."
CASES["mech09"]["b_task"] = "In Spend Reconciliation, make one update only: enter 12750 in the blank E3 Actual Spend cell for BUD-221 (Freezer maintenance). Click E3, enter 12750 once, press Enter, then Ctrl+S. Do not use Undo or change any other cell."

def _spec(case_id: str) -> dict:
    try: return CASES[case_id]
    except KeyError as e: raise ValueError(f"unknown undo-family case: {case_id}") from e

def _ods_path(case_id: str) -> str:
    s=_spec(case_id); return f"{s['work']}/{s['file']}"

def _window_script(title: str) -> str:
    q=shlex.quote(title)
    return f'for i in $(seq 60); do wid=$(xdotool search --onlyvisible --name {q} 2>/dev/null | tail -1 || true); [ -n "$wid" ] && {{ xdotool windowactivate --sync "$wid"; exit 0; }}; sleep 1; done; exit 1'

# Keep strong controller references so Python cannot recycle id(sc) when a
# fresh Guest is booted inside the same scripted-control process.
_SETUP=[]
def setup(sc, case_id: str, role: str) -> None:
    s=_spec(case_id); vm_ip=getattr(sc,'vm_ip',''); port=getattr(sc,'server_port','')
    if any(item[0] is sc and item[1]==case_id and item[2]==vm_ip and item[3]==port for item in _SETUP): return
    src=f"mechanism_expansion_v1/{case_id}/{s['file']}"; dest=_ods_path(case_id)
    pc.upload(sc,[(src,dest)])
    pc.sh(sc,'pkill -TERM -x soffice.bin 2>/dev/null || true; pkill -TERM -x soffice 2>/dev/null || true; sleep 1; pkill -KILL -x soffice.bin 2>/dev/null || true; pkill -KILL -x soffice 2>/dev/null || true; sleep 1')
    pc.sh(sc,f"mkdir -p {s['work']}/baseline && cp {shlex.quote(dest)} {shlex.quote(s['work']+'/baseline/'+s['file'])}")
    pc.sh(sc,f"setsid -f libreoffice --calc {shlex.quote(dest)} >/tmp/{case_id}-calc.log 2>&1 < /dev/null")
    pc.sh(sc,_window_script(Path(s['file']).stem),timeout=45)
    # Wait for Calc first-paint/maximize to settle before coordinate input.
    pc.sh(sc,'sleep 4')
    cell=f'{chr(65+s["a_temp_col"])}2'
    # GUI screenshot is 1920x1080 at 100% zoom. Click the center of C2
    # directly; this avoids flaky toolbar focus and dropped arrow events.
    col=s["a_temp_col"]; x=150+83*col; y=314+18
    go=f"xdotool mousemove --sync {x} {y} click 1; sleep .8"
    pc.sh(sc,go,timeout=30)
    pc.sh(sc,go,timeout=30)
    # The reversible edit is a visible GUI precondition in every Guest. Do not
    # save it: actors begin with the same dirty document and undo history.
    pc.sh(sc,'xdotool type --clearmodifiers --delay 40 '+shlex.quote(s["a_temp"])+'; sleep .3; xdotool key Return; sleep .5',timeout=30)
    pc.sh(sc,go,timeout=30)
    _SETUP.append((sc,case_id,vm_ip,port))

def _read_guest_xml(env,case_id: str) -> dict:
    path=_ods_path(case_id); code=("import base64,zipfile,sys\n" "z=zipfile.ZipFile(sys.argv[1]); print('UNDOFAMILY'+base64.b64encode(z.read('content.xml')).decode())")
    raw=pc.guest(env,f"python3 -c {shlex.quote(code)} {shlex.quote(path)}",timeout=90)
    m=re.search(r"UNDOFAMILY([A-Za-z0-9+/=]+)",raw)
    if not m:return {"read_error":raw[-1200:]}
    try:return {"xml":base64.b64decode(m.group(1))}
    except Exception as e:return {"read_error":f"{type(e).__name__}: {e}"}

def _text(node): return "".join(node.itertext()).strip()

def _rows(xml_bytes: bytes, width: int) -> list[list[str]]:
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
        values=values[:width]; values.extend([""]*(width-len(values)))
        rep=int(row.get("{%s}number-rows-repeated"%NS["table"],"1"))
        result.extend([list(values) for _ in range(max(1,rep))])
    return result

def evaluate(env, case_id: str, role: str) -> dict:
    s=_spec(case_id); raw=_read_guest_xml(env,case_id)
    if "read_error" in raw:return {"score":0.0,"checks":{"ods_readable":False},"state":raw}
    width=len(s["headers"]); rows=_rows(raw["xml"],width); ids=[r[0] for r in rows[1:] if r and r[0]]
    by_id={r[0]:r for r in rows[1:] if r and r[0]}; base={r[0]:r for r in s["rows"]}
    readable=(len(rows)==len(s["rows"])+1 and len(rows)>0 and rows[0]==s["headers"] and all(len(r)==width for r in rows))
    checks={"ods_readable":readable,"all_record_ids_present_once":len(ids)==len(base) and sorted(ids)==sorted(base),"original_row_order":ids==[r[0] for r in s["rows"]]}
    arow=by_id.get(s["a_id"],[]); brow=by_id.get(s["b_id"],[])
    if role=="A":
        checks["temporary_edit_undone"]=len(arow)>s["a_temp_col"] and arow[s["a_temp_col"]]==base[s["a_id"]][s["a_temp_col"]]
        checks["review_marker_saved"]=len(arow)>s["a_mark_col"] and arow[s["a_mark_col"]]==s["a_mark"]
    else:
        checks["b_target_fields_saved"]=all(len(brow)>col and brow[col]==value for col,value in s["b_values"].items())
    # The staged A-cell value is part of the deterministic GUI precondition.
    # It may remain after A fails to undo it; A's direct oracle catches that.
    allowed={(s["a_id"],s["a_mark_col"]),(s["a_id"],s["a_temp_col"])}|{(s["b_id"],c) for c in s["b_values"]}
    unchanged=set(by_id)==set(base)
    if unchanged:
        for rid,want in base.items():
            got=by_id[rid]
            if len(got)!=width or any((rid,c) not in allowed and str(got[c] or "")!=str(want[c] or "") for c in range(width)):
                unchanged=False;break
    checks["non_target_values_preserved"]=unchanged
    return {"score":1.0 if all(checks.values()) else 0.0,"checks":checks,
            "state":{"rows":rows,"row_order":ids,"a_row":arow,"b_row":brow},
            "mechanism_evidence":{"staged_value":s["a_temp"],
                                  "temporary_cell_expected_base":base[s["a_id"]][s["a_temp_col"]],
                                  "temporary_cell_final":arow[s["a_temp_col"]] if len(arow)>s["a_temp_col"] else None}}

TASKS={k:{"A":v["a_task"],"B":v["b_task"]} for k,v in CASES.items()}
