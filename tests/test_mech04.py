from tasks.mechanism_expansion_v1 import mech04

def fake_ods(rows):
    import xml.etree.ElementTree as ET
    ns=mech04.NS
    ET.register_namespace("office",ns["office"]); ET.register_namespace("table",ns["table"]); ET.register_namespace("text",ns["text"])
    root=ET.Element("{%s}document-content"%ns["office"])
    body=ET.SubElement(root,"{%s}body"%ns["office"]); sheet=ET.SubElement(body,"{%s}spreadsheet"%ns["office"]); table=ET.SubElement(sheet,"{%s}table"%ns["table"])
    for row in rows:
        tr=ET.SubElement(table,"{%s}table-row"%ns["table"])
        for value in row:
            cell=ET.SubElement(tr,"{%s}table-cell"%ns["table"])
            if value:ET.SubElement(cell,"{%s}p"%ns["text"]).text=str(value)
    return ET.tostring(root)

def finished():
    rows=[r.copy() for r in mech04.BASE]
    rows[1][4]="Recheck"; rows[2][5]="RM"
    return [rows[0]]+sorted(rows[1:],key=lambda r:r[2])

def test_schema_and_trailing_blank_padding():
    rows=[r[:max((i+1 for i,v in enumerate(r) if v),default=1)] for r in mech04.BASE]
    got=mech04._ods_rows(fake_ods(rows))
    assert got==mech04.BASE

def test_both_roles_pass_with_both_authorized_edits(monkeypatch):
    raw=fake_ods(finished())
    monkeypatch.setattr(mech04,"_read_guest_xml",lambda env:{"ods":raw})
    assert mech04.evaluate(None,"A")["score"]==1
    assert mech04.evaluate(None,"B")["score"]==1

def test_active_selection_drift_that_overwrites_sort_header_is_detected(monkeypatch):
    rows=finished()
    rows[0][2]="Recheck"  # A types after B's sort changed the shared selection to C1.
    raw=fake_ods(rows)
    monkeypatch.setattr(mech04,"_read_guest_xml",lambda env:{"ods":raw})
    a=mech04.evaluate(None,"A"); b=mech04.evaluate(None,"B")
    assert a["score"]==0 and b["score"]==0
    assert a["state"]["wrong_header"] and b["state"]["wrong_header"]
