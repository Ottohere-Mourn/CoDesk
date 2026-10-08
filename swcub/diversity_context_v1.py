"""Task-relevant context profiles for the fixed CoDesk V1 diversity refresh."""
from __future__ import annotations
import html, json, re
import xml.etree.ElementTree as ET

CONTEXTS = {
    "A-02": [("supplier_ledger",1,"supplier/invoice rows"),("asset_register",2,"maintenance-cycle records"),("inspection_queue",3,"inspection/incident distractors"),("allocation_matrix",4,"request/reimbursement context"),("release_board",5,"release/change-request rows")],
    "A-03": [("sparse_sheet_edge",1,"sparse occupied neighborhood"),("dense_ledger_block",4,"dense record neighborhood"),("formula_summary",2,"formula/value context"),("paired_record_table",3,"mixed occupied/empty cells"),("reconciliation_boundary",5,"occupied boundary/blank margin")],
    "C-01": [("memo_source",1,"sparse ledger destination"),("sectioned_source",2,"row-label destination"),("list_source",3,"populated record table"),("reference_source",4,"formula-neighbor destination"),("summary_source",5,"table edge with blank margin")],
    "C-06": [("line_output",1,"unfiltered browser results"),("grouped_output",2,"grouped browser cards"),("csv_output",3,"status-facet results"),("key_value_output",4,"entity/owner result context"),("tree_output",5,"archived-result distractors")],
    "F-01": [("status_memo",1,"sparse Calc ledger neighborhood"),("sectioned_report",2,"dense Calc table"),("action_list",3,"formula-bearing Calc neighbors"),("table_adjacent_report",4,"record table/blank guard"),("multi_section_brief",5,"subtotal and neighboring records")],
    "F-06": [("review_case",1,"one output file context"),("vendor_dossier",2,"directory listing with decoys"),("asset_maintenance",3,"input/output pair context"),("safety_incident",4,"archived outputs context"),("release_approval",5,"multiple candidate artifacts")],
    "S-01": [("sparse_edge",1,"empty neighboring cells"),("dense_table",4,"occupied neighborhood"),("formula_neighbors",2,"formula/value mixture"),("blank_boundary",3,"occupied rows/blank columns"),("subtotal_context",5,"headers/subtotal/guard context")],
    "S-02": [("isolated_rectangles",1,"sparse range neighborhood"),("ledger_surround",4,"dense neighboring records"),("formula_edge",2,"formula-bearing range boundary"),("header_boundary",3,"partly empty neighborhood"),("subtotal_guard",5,"mixed occupied/empty context")],
    "S-04": [("compact_queue",1,"compact table/one distractor"),("vendor_register",2,"similar vendor rows"),("priority_board",3,"near-match severity rows"),("inventory_audit",4,"archived inventory rows"),("release_tracker",5,"pending release distractors")],
    "U-03": [("single_input_total",1,"sparse formula neighborhood"),("ledger_subtotal",4,"dense numeric/value context"),("cross_column_summary",2,"formula-bearing neighbors"),("blank_input_gap",3,"mixed empty/value state"),("guarded_reconciliation",5,"occupied boundary/guard")],
    "U-N1": [("section_body",1,"headed body paragraphs"),("list_items",2,"list/continuation context"),("decision_brief",3,"heading/body context"),("quoted_notes",4,"quote/attribution context"),("mixed_sections",5,"mixed paragraph styles")],
}
OFFICE="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
STYLE="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
FO="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"

def enrich_profiles(profiles):
    for wid, choices in CONTEXTS.items():
        if len(profiles[wid]) != 5: raise ValueError(f"{wid}: expected five profiles")
        for i,(profile,choice) in enumerate(zip(profiles[wid],choices)):
            name,density,description=choice
            profile["schema"]["state_context"]={"profile":name,"profile_index":i,"density_level":density,
                "description":description,"context_axes":{"fixture_state":description,"target_neighborhood":density,
                "workflow_graph":"unchanged","schedule_policy":"unchanged"}}

def _coord(ref):
    m=re.fullmatch(r"([A-Z]+)([1-9][0-9]*)",ref)
    if not m:return None
    col=0
    for c in m.group(1):col=col*26+ord(c)-64
    return int(m.group(2))-1,col-1

def _ranges(profile):
    result=[]
    for key in ("a","b"):
        target=profile.get(key,"")
        if not target.startswith("calc/"):continue
        raw=target.split("/",1)[1];sheet="CoDesk"
        if "." in raw:
            prefix,rest=raw.split(".",1)
            if prefix.startswith("Sheet"):sheet,raw=prefix,rest
        coords=[_coord(x) for x in raw.split(":")]
        if all(coords):
            (r0,c0),(r1,c1)=coords[0],coords[-1]
            result.append((sheet,{(r,c) for r in range(r0,r1+1) for c in range(c0,c1+1)}))
    return result

def _writer_context(wid,profile,domain,assets):
    raw=assets.get("document.fodt")
    if not raw:return
    root=ET.fromstring(raw);doc=next(root.iter(f"{{{OFFICE}}}text"),None)
    if doc is None:return
    paras=list(doc.iter(f"{{{TEXT}}}p"))
    if not paras:return
    ctx=profile["schema"]["state_context"];i=ctx["profile_index"]
    names=["BodyContext","ListContext","SectionContext","QuoteContext","ReportContext"];name=names[i]
    auto=next(root.iter(f"{{{OFFICE}}}automatic-styles"),None)
    if auto is None:auto=ET.Element(f"{{{OFFICE}}}automatic-styles");root.insert(0,auto)
    st=ET.SubElement(auto,f"{{{STYLE}}}style",{f"{{{STYLE}}}name":name,f"{{{STYLE}}}family":"paragraph"})
    ET.SubElement(st,f"{{{STYLE}}}paragraph-properties",{f"{{{FO}}}margin-left":f"{i*0.08}in"})
    if wid=="F-01":
        old="".join(paras[0].itertext())
        for child in list(doc):doc.remove(child)
        h=ET.SubElement(doc,f"{{{TEXT}}}h",{f"{{{TEXT}}}outline-level":str(1+i%3)});h.text=f"{domain['title']} — {ctx['profile']}"
        if i%2:
            sub=ET.SubElement(doc,f"{{{TEXT}}}h",{f"{{{TEXT}}}outline-level":"2"});sub.text=ctx["description"]
        p=ET.SubElement(doc,f"{{{TEXT}}}p",{f"{{{TEXT}}}style-name":name});p.text=f"Context: {ctx['description']}"
        target=ET.SubElement(doc,f"{{{TEXT}}}p");target.text=old
        guard=ET.SubElement(doc,f"{{{TEXT}}}p");guard.text="Protected appendix: replace the complete document as assigned."
    elif wid=="U-N1":
        targets=[]
        for key in ("a","b"):
            m=re.search(r"paragraph\[([0-9]+)\]",profile.get(key,""))
            if m:targets.append(int(m.group(1)))
        for n,para in enumerate(paras):para.set(f"{{{TEXT}}}style-name",name if n in targets else names[(n+i+1)%5])
        section=ET.Element(f"{{{TEXT}}}section",{f"{{{TEXT}}}name":ctx["profile"]})
        for child in list(doc): doc.remove(child); section.append(child)
        doc.append(section)
    else:
        for n,para in enumerate(paras):para.set(f"{{{TEXT}}}style-name",name if n<2 else names[(n+i+1)%5])
        if wid=="C-01":
            h=ET.Element(f"{{{TEXT}}}h",{f"{{{TEXT}}}outline-level":str(1+i%3)});h.text=f"{domain['title']} — transfer source context";doc.insert(0,h)
    for prefix,uri in (("office",OFFICE),("text",TEXT),("table",TABLE),("style",STYLE),("fo",FO)):ET.register_namespace(prefix,uri)
    assets["document.fodt"]=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")

def _calc_context(profile,assets):
    raw=assets.get("workbook.fods")
    if not raw:return
    root=ET.fromstring(raw);sheets=list(root.iter(f"{{{TABLE}}}table"))
    if not sheets:return
    ctx=profile["schema"]["state_context"];i=ctx["profile_index"]
    patterns=[
        [(-1,-1,"Record"),(-1,0,"Target field"),(0,-1,"Subtotal")],
        [(-1,-1,"Period"),(-1,0,"Owner"),(0,-1,"North"),(0,1,"South"),(1,-1,"West"),(1,1,"East")],
        [(-1,0,"=SUM(A1:A2)"),(0,-1,"Input"),(0,1,"=SUM(B1:B3)"),(1,0,"Checked")],
        [(-1,-1,"Section"),(-1,0,"Current"),(1,-1,"Next row"),(0,1,"")],
        [(-1,0,"Subtotal"),(0,-1,"=SUM(A1:A3)"),(0,1,"Guard: KEEP"),(1,0,"Reconciled")],
    ][i]
    reserved_by_sheet={}
    for sheet,cells in _ranges(profile):reserved_by_sheet.setdefault(sheet,set()).update(cells)
    for sh in sheets:
        sheet_name=sh.get(f"{{{TABLE}}}name","CoDesk");reserved=reserved_by_sheet.get(sheet_name,set())
        targets=sorted(reserved) or [(1,1)]
        old_rows=list(sh.findall(f"{{{TABLE}}}table-row"));matrix=[]
        for row in old_rows:
            vals=[]
            for cell in row.findall(f"{{{TABLE}}}table-cell"):
                formula=cell.get(f"{{{TABLE}}}formula")
                value=cell.get(f"{{{OFFICE}}}value")
                vals.append(formula.removeprefix("of:") if formula else value if value is not None else "".join("".join(p.itertext()) for p in cell.findall(f"{{{TEXT}}}p")))
            matrix.append(vals)
        width=max([len(r) for r in matrix]+[8])
        for row in matrix:row.extend([""]*(width-len(row)))
        for r,c in targets:
            for dr,dc,val in patterns:
                rr,cc=r+dr,c+dc
                if rr<0 or cc<0 or (rr,cc) in reserved:continue
                while len(matrix)<=rr:matrix.append([""]*width)
                if cc>=width:
                    for row in matrix:row.extend([""]*(cc+1-width))
                    width=cc+1
                matrix[rr][cc]=val
        target_rows=max((r+1 for r,c in reserved),default=0);target_cols=max((c+1 for r,c in reserved),default=0)
        keep_rows=max(8+i,target_rows);keep_cols=max(7+(i%4),target_cols)
        matrix=[row[:keep_cols] for row in matrix[:keep_rows]]
        while len(matrix)<keep_rows:matrix.append([""]*keep_cols)
        for old in old_rows:sh.remove(old)
        for vals in matrix:
            tr=ET.SubElement(sh,f"{{{TABLE}}}table-row")
            for val in vals:
                cell=ET.SubElement(tr,f"{{{TABLE}}}table-cell")
                if val.startswith("="):
                    cell.set(f"{{{TABLE}}}formula","of:"+val);cell.set(f"{{{OFFICE}}}value-type","float");cell.set(f"{{{OFFICE}}}value","0")
                elif val:
                    cell.set(f"{{{OFFICE}}}value-type","string");ET.SubElement(cell,f"{{{TEXT}}}p").text=val
    for prefix,uri in (("office",OFFICE),("text",TEXT),("table",TABLE)):ET.register_namespace(prefix,uri)
    assets["workbook.fods"]=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")

def apply_context(wid,profile,domain,assets):
    if wid not in CONTEXTS:return assets
    ctx=profile["schema"]["state_context"]
    assets["state-context.json"]=(json.dumps(ctx,sort_keys=True,separators=(",",":"))+"\n").encode()
    _writer_context(wid,profile,domain,assets);_calc_context(profile,assets)
    if "workspace.html" in assets:
        source=assets["workspace.html"].decode();rows=[]
        for n in range(1,ctx["density_level"]+3):
            role="assigned" if n<=2 else "distractor"
            rows.append(f"<tr><td>{html.escape(domain['entity'])} {n}</td><td>{html.escape(ctx['description'])}</td><td>{role}</td></tr>")
        block=(f"<section data-context-profile='{ctx['profile']}'><h2>{html.escape(domain['title'])}: {html.escape(ctx['profile'])}</h2>"
               f"<table><thead><tr><th>Record context</th><th>Field group</th><th>Role</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>")
        source=source.replace("</main>",block+"</main>") if "</main>" in source else source+block
        if wid=="S-04":
            extras="".join(f"<tr><td><input type='checkbox' data-row='{n}'></td><td>{html.escape(ctx['profile'])} distractor {n}</td><td id='status-{n}'>pending</td></tr>" for n in range(7,7+ctx["density_level"]))
            source=source.replace("</tbody></table>",extras+"</tbody></table>",1)
        assets["workspace.html"]=source.encode()
    if "browser-initial-state.json" in assets and wid=="S-04":
        state=json.loads(assets["browser-initial-state.json"])
        for n in range(7,7+ctx["density_level"]):state.setdefault("rows",{})[str(n)]={"selected":False,"status":"pending","role":"distractor"}
        assets["browser-initial-state.json"]=(json.dumps(state,sort_keys=True)+"\n").encode()
    if "terminal-task.sh" in assets:
        original=assets["terminal-task.sh"].decode();lines=[]
        for n in range(1,ctx["density_level"]+1):
            text=f"context {ctx['profile']} {n}: {domain['entity']} {domain['field_a']}"
            lines.append("printf '%s\\\\n' "+json.dumps(text))
        assets["terminal-task.sh"]=("#!/bin/sh\n"+"\n".join(lines)+"\n"+original.removeprefix("#!/bin/sh\n")).encode()
    return assets
