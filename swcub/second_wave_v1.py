"""Second-wave workflow catalog: concrete operation graphs for the five frozen families.

These are task templates, not generated instances. Each row keeps the two actor
goals independent while naming the shared GUI state and an objective evidence
surface. Real Guest feasibility remains a separate validation gate.
"""
from __future__ import annotations
import json

def _profiles(rows, kind, **schema):
    return [{"id": row[0], "a": row[1], "b": row[2],
             "schema": {"operation_kind": kind, **schema, "profile_label": row[0]}}
            for row in rows]

SECOND_WAVE = {
    "F-05": {
        "family": "focus_input_routing", "apps": ["Writer", "Calc"],
        "operation_graph": "writer_find_replace_then_calc_formula_entry",
        "description": "Replace one exact Writer phrase while entering an independent Calc formula.",
        "goal_a": "Use Writer Find/Replace to replace the assigned phrase exactly once; preserve all other paragraphs.",
        "goal_b": "Enter the assigned formula in the Calc target cell and preserve neighboring cells.",
        "schedule": "writer-find-calc-formula-action-boundary-v1",
        "schema": {"A": "writer/find-replace", "B": "calc/formula-cell", "shared": "foreground window and keyboard target"},
        "profiles": _profiles([
            ("phrase_summary","writer/paragraph[1]","calc/B2"),("phrase_risk","writer/paragraph[2]","calc/C2"),
            ("phrase_owner","writer/paragraph[3]","calc/D2"),("phrase_action","writer/paragraph[4]","calc/B3"),
            ("phrase_title","writer/paragraph[5]","calc/C3")], "find_replace_formula",
            operation_pair=["exact_phrase_replace","formula_entry"], formula="=SUM(B4:B6)"),
    },
    "F-06": {
        "family": "focus_input_routing", "apps": ["Browser", "Terminal"],
        "operation_graph": "browser_multifield_submit_and_terminal_command_edit",
        "description": "Complete a two-field Browser transaction and independently edit/run a shell command.",
        "goal_a": "Fill the assigned Browser record fields and submit exactly once.",
        "goal_b": "Edit the assigned shell command, run it, and produce the exact output file without changing other files.",
        "schedule": "browser-terminal-edit-submit-action-boundary-v1",
        "schema": {"A": "browser/form-transaction", "B": "terminal/command-line", "shared": "foreground window and keyboard target"},
        "profiles": _profiles([
            ("form_review","browser/record/review","terminal/output/review"),("form_vendor","browser/record/vendor","terminal/output/vendor"),
            ("form_asset","browser/record/asset","terminal/output/asset"),("form_safety","browser/record/safety","terminal/output/safety"),
            ("form_release","browser/record/release","terminal/output/release")], "browser_terminal_transaction",
            operation_pair=["multi_field_submit","command_edit_execute"], fields=["record_id","status"]),
    },
    "F-07": {
        "family": "focus_input_routing", "apps": ["Writer", "Calc"],
        "operation_graph": "writer_character_formatting_and_calc_rectangular_fill",
        "description": "Apply character formatting to one Writer phrase while filling a separate Calc rectangle.",
        "goal_a": "Apply the requested character style to the exact Writer phrase only.",
        "goal_b": "Fill the assigned Calc rectangle with the row-wise values and preserve guard cells.",
        "schedule": "writer-format-calc-range-fill-action-boundary-v1",
        "schema": {"A": "writer/character-range", "B": "calc/rectangular-range", "shared": "foreground window and keyboard target"},
        "profiles": _profiles([
            ("format_word","writer/range/alpha","calc/B2:C3"),("format_phrase","writer/range/beta","calc/C2:D3"),
            ("format_sentence","writer/range/gamma","calc/B3:C4"),("format_heading","writer/range/delta","calc/C3:D4"),
            ("format_list","writer/range/epsilon","calc/B4:C5")], "writer_format_calc_fill",
            operation_pair=["character_style_apply","rectangular_fill"], style="bold", shape=[2,2]),
    },
    "C-04": {
        "family": "clipboard_state", "apps": ["Browser", "Calc"], "actor_domains": ["Calc","Calc"],
        "operation_graph": "browser_url_copy_to_calc_hyperlink_formula_and_calc_range_copy",
        "description": "Copy a Browser URL into a Calc hyperlink formula while B copies a separate Calc range.",
        "goal_a": "Copy the assigned Browser URL and create a Calc hyperlink with the exact href and label.",
        "goal_b": "Copy the assigned Calc rectangle to its paired destination, preserving source and guards.",
        "schedule": "browser-url-calc-range-copy-confirm-v1",
        "schema": {"A": "browser/url-to-calc-hyperlink", "B": "calc/range-copy", "shared": "X11 clipboard selection"},
        "profiles": _profiles([
            ("link_case","calc/B2","calc/A8:B9"),("link_policy","calc/C2","calc/C8:D9"),
            ("link_source","calc/D2","calc/E8:F9"),("link_ticket","calc/B3","calc/G8:H9"),
            ("link_evidence","calc/C3","calc/I8:J9")], "url_hyperlink_range_copy",
            operation_pair=["url_copy_hyperlink_insert","range_copy_paste"], range=["A5:B6","A8:B9"]),
    },
    "C-05": {
        "family": "clipboard_state", "apps": ["Calc", "Writer"], "actor_domains": ["Writer","Writer"],
        "operation_graph": "calc_formula_range_to_writer_table_and_writer_text_copy",
        "description": "Copy a formula-bearing Calc range into a Writer table while B copies a separate Writer paragraph.",
        "goal_a": "Copy the assigned Calc rectangular data including displayed values into the matching Writer table cells.",
        "goal_b": "Copy the assigned Writer paragraph into its blank destination without altering the source.",
        "schedule": "calc-table-writer-paragraph-copy-confirm-v1",
        "schema": {"A": "calc/range-to-writer-table", "B": "writer/paragraph-copy", "shared": "X11 clipboard selection"},
        "profiles": _profiles([
            ("table_2x2","writer/table[0]","writer/paragraph[2]"),("table_2x3","writer/table[0]","writer/paragraph[3]"),
            ("table_3x2","writer/table[0]","writer/paragraph[4]"),("table_3x3","writer/table[0]","writer/paragraph[5]"),
            ("table_2x4","writer/table[0]","writer/paragraph[6]")], "calc_to_writer_structured_copy",
            operation_pair=["range_copy_structured_paste","paragraph_copy_paste"], payload="displayed_cell_values"),
    },
    "C-06": {
        "family": "clipboard_state", "apps": ["Terminal", "Browser"], "actor_domains": ["Browser","Browser"],
        "operation_graph": "terminal_selected_output_to_browser_search_and_browser_text_copy",
        "description": "Copy selected terminal output into a Browser search field while B copies a distinct Browser text token.",
        "goal_a": "Select and copy the exact command output, paste it into the assigned Browser search, and submit the search.",
        "goal_b": "Copy the assigned Browser text token and paste it into the independent destination field.",
        "schedule": "terminal-output-browser-copy-confirm-resume-v1",
        "schema": {"A": "terminal/selection-to-browser-search", "B": "browser/text-copy-paste", "shared": "X11 clipboard selection"},
        "profiles": _profiles([
            ("search_case","browser/search/case","browser/destination/case"),("search_vendor","browser/search/vendor","browser/destination/vendor"),
            ("search_asset","browser/search/asset","browser/destination/asset"),("search_policy","browser/search/policy","browser/destination/policy"),
            ("search_ticket","browser/search/ticket","browser/destination/ticket")], "terminal_browser_text_transfer",
            operation_pair=["terminal_output_copy_search","browser_text_copy_paste"]),
    },
    "A-03": {
        "family": "application_context", "apps": ["Calc", "Calc"],
        "operation_graph": "calc_sheet_switch_and_sheet_scoped_edit",
        "description": "Edit a target on each sheet while another actor changes the active sheet in the same Calc window.",
        "goal_a": "Enter the assigned value in the named cell on Sheet A and preserve its guard cells.",
        "goal_b": "Enter the assigned value in the named cell on Sheet B and preserve its guard cells.",
        "schedule": "calc-sheet-context-change-observe-resume-v1",
        "schema": {"A": "calc/sheet-a/cell", "B": "calc/sheet-b/cell", "shared": "active worksheet context"},
        "profiles": _profiles([
            ("sheet_review","calc/SheetA.B2","calc/SheetB.C3"),("sheet_inventory","calc/SheetA.C2","calc/SheetB.D3"),
            ("sheet_safety","calc/SheetA.D2","calc/SheetB.B4"),("sheet_release","calc/SheetA.B3","calc/SheetB.C4"),
            ("sheet_budget","calc/SheetA.C3","calc/SheetB.D4")], "calc_sheet_context",
            operation_pair=["sheet_scoped_cell_edit","sheet_scoped_cell_edit"]),
    },
    "A-04": {
        "family": "application_context", "apps": ["Browser", "Browser"],
        "operation_graph": "browser_filter_result_context_and_record_transaction",
        "description": "Complete independent records after the other actor changes the single-page filter result set.",
        "goal_a": "Open the assigned filter and update the exact matching result record.",
        "goal_b": "Change to the independent filter and update its matching result record.",
        "schedule": "browser-filter-context-change-resume-v1",
        "schema": {"A": "browser/filter/result-record-a", "B": "browser/filter/result-record-b", "shared": "active query and result-set context"},
        "profiles": _profiles([
            ("filter_open","browser/query/open-record","browser/query/closed-record"),
            ("filter_pending","browser/query/pending-record","browser/query/approved-record"),
            ("filter_owner","browser/query/owner-a","browser/query/owner-b"),
            ("filter_vendor","browser/query/vendor-a","browser/query/vendor-b"),
            ("filter_priority","browser/query/high-priority","browser/query/standard-priority")], "browser_filter_context",
            operation_pair=["filter_result_select_edit","filter_result_select_edit"]),
    },
    "A-05": {
        "family": "application_context", "apps": ["Writer", "Writer"],
        "operation_graph": "writer_document_navigator_section_context",
        "description": "Navigate between named document sections and edit each section while keeping one Writer window/document.",
        "goal_a": "Use Navigator to update the assigned field in section A only.",
        "goal_b": "Use Navigator to update the assigned field in section B only.",
        "schedule": "writer-section-context-change-resume-v1",
        "schema": {"A": "writer/section-a/field", "B": "writer/section-b/field", "shared": "active document section/navigation context"},
        "profiles": _profiles([
            ("section_summary","writer/section[Summary]/paragraph[1]","writer/section[Actions]/paragraph[1]"),
            ("section_risk","writer/section[Risk]/paragraph[1]","writer/section[Owners]/paragraph[1]"),
            ("section_budget","writer/section[Budget]/paragraph[1]","writer/section[Timeline]/paragraph[1]"),
            ("section_vendor","writer/section[Vendor]/paragraph[1]","writer/section[Decision]/paragraph[1]"),
            ("section_release","writer/section[Release]/paragraph[1]","writer/section[Rollback]/paragraph[1]")], "writer_navigator_context",
            operation_pair=["navigator_section_edit","navigator_section_edit"]),
    },
    "S-02": {
        "family": "selection_active_object", "apps": ["Calc", "Calc"],
        "operation_graph": "calc_rectangular_selection_fill_handle",
        "description": "Select and fill two independent Calc rectangles using range-level fill semantics.",
        "goal_a": "Select and fill the assigned 2-by-3 range with the requested row/column pattern.",
        "goal_b": "Select and fill the other 2-by-3 range with its independent pattern.",
        "schedule": "calc-range-selection-change-resume-v1",
        "schema": {"A": "calc/range-fill-a", "B": "calc/range-fill-b", "shared": "active selected range"},
        "profiles": _profiles([
            ("fill_ab","calc/B2:D3","calc/F2:H3"),("fill_bc","calc/C2:E3","calc/G2:I3"),
            ("fill_cd","calc/B4:D5","calc/F4:H5"),("fill_de","calc/C5:E6","calc/G5:I6"),
            ("fill_ef","calc/B7:D8","calc/F7:H8")], "calc_range_fill",
            operation_pair=["range_selection_fill","range_selection_fill"], shape=[2,3]),
    },
    "S-03": {
        "family": "selection_active_object", "apps": ["Writer", "Writer"],
        "operation_graph": "writer_text_selection_replacement",
        "description": "Replace two disjoint selected phrases while preserving surrounding document text.",
        "goal_a": "Find and select the exact target phrase A, replace it, and preserve neighboring text.",
        "goal_b": "Find and select the exact target phrase B, replace it, and preserve neighboring text.",
        "schedule": "writer-range-replacement-selection-resume-v1",
        "schema": {"A": "writer/selection/phrase-a", "B": "writer/selection/phrase-b", "shared": "active text selection and caret"},
        "profiles": _profiles([
            ("replace_alpha","writer/range/alpha","writer/range/beta"),("replace_titles","writer/range/title-a","writer/range/title-b"),
            ("replace_names","writer/range/name-a","writer/range/name-b"),("replace_dates","writer/range/date-a","writer/range/date-b"),
            ("replace_codes","writer/range/code-a","writer/range/code-b")], "writer_selected_phrase_replace",
            operation_pair=["select_replace_exact_phrase","select_replace_exact_phrase"]),
    },
    "S-04": {
        "family": "selection_active_object", "apps": ["Browser", "Browser"],
        "operation_graph": "browser_multirow_selection_bulk_update",
        "description": "Select each actor's disjoint rows in one Browser table and apply independent bulk status updates.",
        "goal_a": "Select all assigned A rows and apply the exact bulk status to those rows only.",
        "goal_b": "Select all assigned B rows and apply the independent bulk status to those rows only.",
        "schedule": "browser-row-selection-bulk-action-resume-v1",
        "schema": {"A": "browser/table/rows-a", "B": "browser/table/rows-b", "shared": "selected row set"},
        "profiles": _profiles([
            ("rows_even","browser/rows/1,3","browser/rows/2,4"),("rows_left","browser/rows/1,2","browser/rows/3,4"),
            ("rows_priority","browser/rows/high","browser/rows/normal"),("rows_vendor","browser/rows/vendor-a","browser/rows/vendor-b"),
            ("rows_safety","browser/rows/safety-a","browser/rows/safety-b")], "browser_multiselect_bulk",
            operation_pair=["multirow_select_bulk_status","multirow_select_bulk_status"]),
    },
    "U-02": {
        "family": "undo_redo_history", "apps": ["Writer", "Writer"],
        "operation_graph": "writer_character_format_then_cross_actor_undo",
        "description": "Apply a temporary Writer character style, let B make an independent edit, then have A Undo and recover both goals.",
        "goal_a": "Apply the temporary style, then after B's edit undo the latest history entry and restore both final document goals.",
        "goal_b": "Insert the assigned independent phrase in the second paragraph and save.",
        "schedule": "writer-style-edit-b-undo-recover-v1",
        "schema": {"A": "writer/history/style", "B": "writer/paragraph[2]", "shared": "Writer document undo stack"},
        "profiles": _profiles([
            ("undo_style_a","writer/range/alpha","writer/paragraph[2]"),("undo_style_b","writer/range/beta","writer/paragraph[3]"),
            ("undo_style_title","writer/range/title","writer/paragraph[3]"),("undo_style_risk","writer/range/risk","writer/paragraph[3]"),
            ("undo_style_owner","writer/range/owner","writer/paragraph[4]")], "writer_style_undo",
            operation_pair=["temporary_style_apply_undo","independent_text_insert"]),
    },
    "U-03": {
        "family": "undo_redo_history", "apps": ["Calc", "Calc"],
        "operation_graph": "calc_formula_edit_peer_commit_undo_recovery",
        "description": "Enter a formula and a peer value in one Calc history stack; A's later Undo must detect and recover the peer edit.",
        "goal_a": "Enter the assigned formula and restore the required formula after observing the peer Undo effect.",
        "goal_b": "Commit the independent value to the assigned Calc cell.",
        "schedule": "calc-formula-edit-b-undo-recover-v1",
        "schema": {"A": "calc/formula-cell", "B": "calc/value-cell", "shared": "Calc document undo stack"},
        "profiles": _profiles([
            ("undo_formula_a","calc/B2","calc/C3"),("undo_formula_b","calc/C2","calc/D3"),
            ("undo_formula_c","calc/D2","calc/E3"),("undo_formula_d","calc/B3","calc/C4"),
            ("undo_formula_e","calc/D3","calc/E4")], "calc_formula_undo",
            operation_pair=["formula_entry_undo_recovery","cell_value_commit"]),
    },
    "U-04": {
        "family": "undo_redo_history", "apps": ["Browser", "Browser"],
        "operation_graph": "browser_rich_editor_shared_undo_stack",
        "description": "Edit a shared rich-text field in one Browser tab; the second actor's insertion becomes the next Ctrl+Z history item.",
        "goal_a": "Insert the assigned phrase into the rich-text editor and verify the final editor contents after any shared Undo.",
        "goal_b": "Insert the independent phrase into the same editor and preserve both assigned phrases.",
        "schedule": "browser-editor-a-b-undo-recover-v1",
        "schema": {"A": "browser/editor/phrase-a", "B": "browser/editor/phrase-b", "shared": "contenteditable undo history"},
        "profiles": _profiles([
            ("editor_review","browser/editor/range/review-a","browser/editor/range/review-b"),("editor_risk","browser/editor/range/risk-a","browser/editor/range/risk-b"),
            ("editor_owner","browser/editor/range/owner-a","browser/editor/range/owner-b"),("editor_budget","browser/editor/range/budget-a","browser/editor/range/budget-b"),
            ("editor_release","browser/editor/range/release-a","browser/editor/range/release-b")], "browser_contenteditable_undo",
            operation_pair=["rich_editor_insert_undo","rich_editor_insert_undo"]),
    },
}

# Bind semantic table shapes/ranges to each structured-copy profile.
for _profile, _source, _shape in zip(SECOND_WAVE["C-05"]["profiles"],
    ["A1:B2","A1:C2","A1:B3","A1:C3","A1:D2"], [[2,2],[2,3],[3,2],[3,3],[2,4]]):
    _profile["schema"].update({"source_range":_source,"shape":_shape})
for _profile in SECOND_WAVE["C-04"]["profiles"]:
    _profile["schema"]["destination_range"]=_profile["b"].split("/",1)[1]
    _profile["schema"]["shape"]=[2,2]
for _profile, _rows_a, _rows_b in zip(SECOND_WAVE["S-04"]["profiles"],
    [[1,3],[1,2],[1,4],[2,5],[3,6]], [[2,4],[3,4],[2,3],[1,4],[1,5]]):
    _profile["schema"]["rows_a"]=_rows_a
    _profile["schema"]["rows_b"]=_rows_b

def profile_rows():
    return {wid: row["profiles"] for wid, row in SECOND_WAVE.items()}

def workflow_row(workflow_id):
    item = SECOND_WAVE[workflow_id]
    return {
        "workflow_id": workflow_id,
        "family": item["family"],
        "task_domains": item.get("actor_domains", item["apps"]),
        "required_apps": item["apps"],
        "operation_graph": item["operation_graph"],
        "description": item["description"],
        "goal_a": item["goal_a"],
        "goal_b": item["goal_b"],
        "schedule_policy_id": item["schedule"],
        "validation_level": "offline_operation_template",
        "runtime_validation_incomplete": True,
        "semantic_parameter_schema": {
            "domain_fields": ["entity", "field_a", "field_b", "a_status", "b_status"],
            "object_profiles": item["profiles"],
            "layout_fields": ["guard_placement", "field_order", "fixture_layout"],
            "identity_excludes": ["generation_seed", "repeat", "condition", "model", "window_coordinates"],
            "actor_target_disjoint": True,
            "no_op_goals_allowed": False,
            "operation_schema": item["schema"],
        },
    }

def semantic_values(workflow_id, domain, profile, layout):
    suffix=domain["source"]; ent=domain["entity"]
    a=f"{domain['a_status']}-{suffix}-A"; b=f"{domain['b_status']}-{suffix}-B"
    if workflow_id=="F-05": return f"Draft phrase {suffix}", "", f"Final phrase {suffix}", "=SUM(B4:B6)"
    if workflow_id=="F-06": return "__UNSUBMITTED__", "", json.dumps({"record":suffix,"status":domain["a_status"]},sort_keys=True), f"TERMINAL-{suffix}"
    if workflow_id=="F-07": return f"plain:{ent}:{suffix}", "__EMPTY_RANGE__", f"bold:{ent}:{suffix}", json.dumps([[f"{domain['a_status']}-{r}{c}" for c in range(2)] for r in range(2)],separators=(",",":"))
    if workflow_id=="C-04":
        href=f"https://example.org/codesk/{domain['id']}/{suffix}"
        return "", "__EMPTY_RANGE__", f'=HYPERLINK("{href}","Open {ent}")', json.dumps([[f"{domain['a_status']}-{r+1}.{c+1}" for c in range(2)] for r in range(2)],separators=(",",":"))
    if workflow_id=="C-05":
        rows,cols=profile["schema"]["shape"]
        matrix=[[f"{ent}-{r+1}.{c+1}" for c in range(cols)] for r in range(rows)]
        return "__EMPTY_TABLE__", "INSERT COPIED VALUE", json.dumps(matrix,separators=(",",":")), f"NOTE-{suffix}"
    if workflow_id=="C-06": return "", "__EMPTY__", f"OUTPUT-{suffix}", f"SEARCH-{suffix}"
    if workflow_id=="A-03": return "", "", f"SHEET-A-{suffix}", f"SHEET-B-{suffix}"
    if workflow_id=="A-04": return "", "", f"FILTER-A-{suffix}", f"FILTER-B-{suffix}"
    if workflow_id=="A-05": return f"Draft section A {suffix}",f"Draft section B {suffix}",f"Final section A {suffix}",f"Final section B {suffix}"
    if workflow_id=="S-02":
        return "__EMPTY_RANGE__","__EMPTY_RANGE__",json.dumps([[f"A{r}{c}-{suffix}" for c in range(3)] for r in range(2)],separators=(",",":")),json.dumps([[f"B{r}{c}-{suffix}" for c in range(3)] for r in range(2)],separators=(",",":"))
    if workflow_id=="S-03": return f"Select phrase A {suffix}",f"Select phrase B {suffix}",f"Replaced phrase A {suffix}",f"Replaced phrase B {suffix}"
    if workflow_id=="S-04":
        return "[]","[]",json.dumps({"rows":profile["schema"]["rows_a"],"status":domain["a_status"]},sort_keys=True),json.dumps({"rows":profile["schema"]["rows_b"],"status":domain["b_status"]},sort_keys=True)
    if workflow_id=="U-02": return f"Seed style A {suffix}",f"Seed line B {suffix}",f"TEMP style A {suffix}",f"Final line B {suffix}"
    if workflow_id=="U-03": return "=SUM(B2:B4)","Seed B",f"=SUM(C2:C4)","Peer final"
    if workflow_id=="U-04": return "Seed A","Seed B",f"TEMP-{suffix}",f"FINAL-{suffix}"
    if workflow_id.startswith("U-"): return "Seed A","Seed B",f"TEMP-{suffix}",b
    return f"Draft A {ent}",f"Draft B {ent}",a,b




def fixture_bytes(workflow_id, domain, profile, layout, a_initial, b_initial, a_final, b_final, instance_id,
                  *, xml_file, html_file, writer_table_file, range_cells, cell_coord):
    import json, re, xml.etree.ElementTree as ET
    row=SECOND_WAVE[workflow_id]; apps=row["apps"]; schema=profile["schema"]; assets={}
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    def writer_doc(paragraphs, target_kind="plain"):
        root=ET.Element(f"{{{office}}}document-content",{f"{{{office}}}version":"1.3"})
        auto=ET.SubElement(root,f"{{{office}}}automatic-styles")
        for name,weight in (("PlainA","normal"),("PlainB","normal"),("BoldA","normal"),("BoldB","normal")):
            st=ET.SubElement(auto,f"{{{style}}}style",{f"{{{style}}}name":name,f"{{{style}}}family":"text"})
            ET.SubElement(st,f"{{{style}}}text-properties",{f"{{{fo}}}font-weight":weight})
        body=ET.SubElement(root,f"{{{office}}}body");doc=ET.SubElement(body,f"{{{office}}}text")
        for index,value in enumerate(paragraphs):
            p=ET.SubElement(doc,f"{{{text}}}p")
            if workflow_id in {"F-07","U-02"} and index==1:
                v=value.split(":",1)[-1] if ":" in value else value
                span=ET.SubElement(p,f"{{{text}}}span",{f"{{{text}}}style-name":"PlainA"});span.text=v
            else:p.text=value
        for prefix,uri in (("office",office),("text",text),("table",table),("style",style),("fo",fo)):ET.register_namespace(prefix,uri)
        return b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")
    def calc_doc(grid, sheet_names=("CoDesk",)):
        root=ET.Element(f"{{{office}}}document-content",{f"{{{office}}}version":"1.3"})
        body=ET.SubElement(root,f"{{{office}}}body");spread=ET.SubElement(body,f"{{{office}}}spreadsheet")
        for sheet_name in sheet_names:
            sh=ET.SubElement(spread,f"{{{table}}}table",{f"{{{table}}}name":sheet_name})
            sheet_grid=grid.get(sheet_name,[]) if isinstance(grid,dict) else grid
            for ri,row_values in enumerate(sheet_grid):
                tr=ET.SubElement(sh,f"{{{table}}}table-row")
                for ci,value in enumerate(row_values):
                    cell=ET.SubElement(tr,f"{{{table}}}table-cell",{f"{{{office}}}value-type":"string"})
                    if value and isinstance(value,str) and value.startswith("="):
                        cell.set(f"{{{table}}}formula","of:"+value)
                    elif value not in (None,""):
                        ET.SubElement(cell,f"{{{text}}}p").text=str(value)
        for prefix,uri in (("office",office),("text",text),("table",table)):ET.register_namespace(prefix,uri)
        return b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")
    # Writer document with explicit paragraph destinations, table targets and a protected guard.
    if "Writer" in apps:
        if workflow_id=="C-05":
            root=ET.fromstring(writer_table_file(domain["title"],tuple(profile["schema"]["shape"])))
            doc=next(root.iter(f"{{{office}}}text"))
            paras=list(doc.iter(f"{{{text}}}p"))
            # Paragraph 0 is the title. Actor B has an explicit source and a separate target paragraph.
            title=paras[0]; title.text=domain["title"]
            source=ET.SubElement(doc,f"{{{text}}}p");source.text=b_final
            target=ET.SubElement(doc,f"{{{text}}}p");target.text=b_initial
            guard=ET.SubElement(doc,f"{{{text}}}p");guard.text="Guard: PRESERVE"
            ET.register_namespace("office",office);ET.register_namespace("text",text);ET.register_namespace("table",table)
            assets["document.fodt"]=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")
        else:
            paragraphs=[domain["title"],a_initial,b_initial,"Guard: PRESERVE"]
            for target,value in ((profile["a"],a_initial),(profile["b"],b_initial)):
                m=re.search(r"paragraph\\[(\\d+)\\]",target)
                if m:
                    idx=int(m.group(1))
                    while len(paragraphs)<=idx:paragraphs.append(f"Unused paragraph {len(paragraphs)}")
                    paragraphs[idx]=value
            if workflow_id=="A-05":
                headers=[re.search(r"section\[([^]]+)\]",target).group(1) for target in (profile["a"],profile["b"])]
                root=ET.Element(f"{{{office}}}document-content",{f"{{{office}}}version":"1.3"})
                ET.SubElement(root,f"{{{office}}}automatic-styles")
                body=ET.SubElement(root,f"{{{office}}}body");doc=ET.SubElement(body,f"{{{office}}}text")
                for heading,value in zip(headers,(a_initial,b_initial)):
                    ET.SubElement(doc,f"{{{text}}}h",{f"{{{text}}}outline-level":"1"}).text=heading
                    ET.SubElement(doc,f"{{{text}}}p").text=value
                ET.SubElement(doc,f"{{{text}}}p").text="Guard: PRESERVE"
                for prefix,uri in (("office",office),("text",text),("table",table)):ET.register_namespace(prefix,uri)
                assets["document.fodt"]=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")
            if workflow_id in {"F-07","U-02"}:
                paragraphs=[domain["title"],a_initial,b_initial,"Guard: PRESERVE"]
            if workflow_id!="A-05": assets["document.fodt"]=writer_doc(paragraphs)
    # Calc fixtures use actual ODF cells, named worksheets, ranges and formula attributes.
    if "Calc" in apps:
        grid=[[f"{domain['entity']} {r+1}.{c+1}" for c in range(12)] for r in range(12)]
        if workflow_id=="C-04":
            for r in range(2):
                for c in range(2):grid[4+r][c]=f"{domain['a_status']}-{r+1}.{c+1}"
        if workflow_id=="C-05":
            source=profile["schema"]["source_range"]; matrix=json.loads(a_final)
            for idx,cell in enumerate(range_cells(source)):
                ri,ci=cell_coord(cell); grid[ri][ci]=matrix[idx//len(matrix[0])][idx%len(matrix[0])]
        for target,value in ((profile["a"],a_initial),(profile["b"],b_initial)):
            if not target.startswith("calc/"):continue
            raw=target.split("/",1)[1]
            raw=re.sub(r"^Sheet[A-Z]\.","",raw)
            try:cells=range_cells(raw)
            except Exception:cells=[]
            if value=="__EMPTY_RANGE__":
                for cell in cells:
                    ri,ci=cell_coord(cell);grid[ri][ci]=""
                continue
            try:matrix=json.loads(value)
            except Exception:matrix=None
            for idx,cell in enumerate(cells):
                ri,ci=cell_coord(cell)
                if ri>100 or ci>100:raise ValueError(f"unreasonable Calc target coordinate: {cell}")
                while len(grid)<=ri:grid.append([""]*12)
                while len(grid[ri])<=ci:grid[ri].append("")
                if isinstance(matrix,list):
                    cols=max(1,max((len(r) for r in matrix),default=1));v=matrix[idx//cols][idx%cols]
                else:v=value
                grid[ri][ci]=v
        if workflow_id=="A-03":
            base=[[f"{domain['entity']} {r+1}.{c+1}" for c in range(12)] for r in range(12)]
            sheets={"SheetA":[x[:] for x in base],"SheetB":[x[:] for x in base]}
            for target,value in ((profile["a"],a_initial),(profile["b"],b_initial)):
                sheet,cell=target.split("/",1)[1].split(".",1); cell=cell
                ri,ci=cell_coord(cell); sheets[sheet][ri][ci]=value
            assets["workbook.fods"]=calc_doc(sheets,("SheetA","SheetB"))
        else:assets["workbook.fods"]=calc_doc(grid)
    # Browser state is private evaluator input; actors interact only with the visible form/table.
    if "Browser" in apps:
        state={"actors":{"A":{"value":a_initial,"revision":0},"B":{"value":b_initial,"revision":0}},
               "active_context":"A","context_revision":0,"active_filter":"all","selected_rows":[],"editor_text":""}
        if workflow_id=="S-04":
            state["rows"]={str(i):{"selected":False,"status":"pending"} for i in range(1,7)}
        if workflow_id=="U-04":state["editor_text"]=a_initial+" "+b_initial;state["undo_stack"]=[]
        elements=["<p>Complete the two independent assigned GUI operations.</p>"]
        if workflow_id=="C-04":
            href=f"https://example.org/codesk/{domain['id']}/{domain['source']}"
            elements.append(f"<a id='url-source' href='{href}'>Open {domain['entity']} reference</a><p>Copy the URL target into Calc as a hyperlink.</p>")
        elif workflow_id=="F-06":
            expected=json.loads(a_final)
            elements.append(f"<p>Record {expected['record']} must be changed to {expected['status']}.</p><form data-actor='A'><label>Record ID <input name='record' aria-label='Record ID'></label><label>Status <input name='status' aria-label='Status'></label><button>Submit record</button></form>")
        elif workflow_id=="A-04":
            elements.extend(["<button type='button' data-context='filter-a'>Filter A</button><button type='button' data-context='filter-b'>Filter B</button>",
                "<form data-actor='A' data-result-context='filter-a'><h2>Filter A result</h2><input name='value'><button>Save A result</button></form>",
                "<form data-actor='B' data-result-context='filter-b' hidden><h2>Filter B result</h2><input name='value'><button>Save B result</button></form>",
                "<script>document.querySelectorAll('[data-context]').forEach(b=>b.onclick=()=>fetch('/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor:b.dataset.context==='filter-a'?'A':'B',context:b.dataset.context})}).then(()=>document.querySelectorAll('form[data-result-context]').forEach(f=>f.hidden=f.dataset.resultContext!==b.dataset.context)));</script>"])
        elif workflow_id=="S-04":
            rows_a=profile["schema"]["rows_a"]; rows_b=profile["schema"]["rows_b"]
            elements.extend(["<table><tbody>"+"".join(f"<tr><td><input type='checkbox' data-row='{i}'></td><td>Record {i}</td><td id='status-{i}'>pending</td></tr>" for i in range(1,7))+"</tbody></table>",
                f"<p>Actor A owns rows {rows_a} and must apply {domain['a_status']}; Actor B owns rows {rows_b} and must apply {domain['b_status']}.</p><button id='bulk-a'>Apply Actor A status</button><button id='bulk-b'>Apply Actor B status</button>",
                "<script>document.querySelectorAll('input[data-row]').forEach(x=>x.onchange=()=>{const rows=[...document.querySelectorAll('input[data-row]:checked')].map(y=>Number(y.dataset.row));fetch('/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows})});});",
                f"document.querySelector('#bulk-a').onclick=()=>fetch('/bulk',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{actor:'A',status:'{domain['a_status']}'}})}}).then(r=>r.json()).then(x=>x.rows.forEach(i=>document.querySelector('#status-'+i).textContent=x.status));",
                f"document.querySelector('#bulk-b').onclick=()=>fetch('/bulk',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{actor:'B',status:'{domain['b_status']}'}})}}).then(r=>r.json()).then(x=>x.rows.forEach(i=>document.querySelector('#status-'+i).textContent=x.status));</script>"])
        elif workflow_id=="U-04":
            elements.append(f"<p>Preserve both assigned phrases: {a_final} and {b_final}.</p><div id='editor' contenteditable='true' role='textbox' aria-label='Shared rich text editor'>{a_initial} {b_initial}</div><button id='save-a'>Record A edit</button><button id='save-b'>Record B edit</button><script>document.querySelector('#save-a').onclick=()=>fetch('/editor',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{actor:'A',value:document.querySelector('#editor').innerText}})}});document.querySelector('#save-b').onclick=()=>fetch('/editor',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{actor:'B',value:document.querySelector('#editor').innerText}})}});</script>")
        else:
            for aid in ("A","B"):
                elements.append(f"<form data-actor='{aid}'><h2>Actor {aid} assigned record</h2><input name='value' aria-label='Actor {aid} value'><button>Save {aid}</button></form>")
        if workflow_id=="F-06":
            elements.append("<script>document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',async e=>{e.preventDefault();const actor=f.dataset.actor;const fields=Object.fromEntries(new FormData(f).entries());const value=JSON.stringify(fields);await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor,value})});}));</script>")
        elif workflow_id!="S-04":
            elements.append("<script>document.querySelectorAll('form').forEach(f=>f.addEventListener('submit',async e=>{e.preventDefault();const actor=f.dataset.actor;const value=f.querySelector('input').value;await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor,value})});}));</script>")
        assets["workspace.html"]=html_file("CoDesk operation task",elements,layout["fixture_layout"])
        assets["browser-initial-state.json"]=(json.dumps(state,sort_keys=True)+"\n").encode()
        assets["browser-events.jsonl"]=b""
        port=8780+int(workflow_id.split("-")[1][1:])
        server=f'''from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
STATE=Path("/home/oem/codesk/{instance_id}/browser-initial-state.json")
EVENTS=Path("/home/oem/codesk/{instance_id}/browser-events.jsonl")
HTML=Path("/home/oem/codesk/{instance_id}/workspace.html")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({{"ok":True}})
  if self.path!="/workspace":return self.reply({{"error":"not found"}},404)
  b=HTML.read_bytes();self.send_response(200);self.send_header("Content-Type","text/html");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());aid=p.get("actor")
  if self.path=="/select":
   rows=sorted({{int(x) for x in p.get("rows",[])}});s["selected_rows"]=rows
   event={{"kind":"selection_change","rows":rows,"generation":s.get("selection_generation",0)+1}}
   s["selection_generation"]=event["generation"]
  elif aid not in ("A","B"):return self.reply({{"error":"bad actor"}},400)
  elif self.path=="/context":
   before=s.get("active_context");s["active_context"]=str(p.get("context"));s["active_filter"]=s["active_context"];s["context_revision"]+=1
   event={{"kind":"context_change","actor":aid,"before":before,"after":s["active_context"]}}
  elif self.path=="/submit":
   requested=aid;active=s.get("active_filter","all");target=active[-1].upper() if active in ("filter-a","filter-b") else aid
   s["actors"][target]["value"]=str(p.get("value",""));s["actors"][target]["revision"]+=1
   event={{"kind":"submit","actor":requested,"routed_actor":target,"active_context":active,"revision":s["actors"][target]["revision"]}}
  elif self.path=="/bulk":
   rows=sorted({{int(x) for x in s.get("selected_rows",[])}});status=str(p.get("status",""))
   for rid in rows:
    key=str(rid)
    if key in s.get("rows",{{}}):s["rows"][key]["status"]=status
   value=json.dumps({{"rows":rows,"status":status}},sort_keys=True)
   s["actors"][aid]["value"]=value;s["actors"][aid]["revision"]+=1
   event={{"kind":"bulk_update","actor":aid,"rows":rows,"status":status,"selection_generation":s.get("selection_generation",0),"revision":s["actors"][aid]["revision"]}}
  elif self.path=="/editor":
   text=str(p.get("value",""));s["editor_text"]=text;s["actors"][aid]["value"]=text;s["actors"][aid]["revision"]+=1
   s.setdefault("undo_stack",[]).append({{"actor":aid,"value":text,"revision":s["actors"][aid]["revision"]}})
   event={{"kind":"editor_commit","actor":aid,"revision":s["actors"][aid]["revision"]}}
  else:return self.reply({{"error":"not found"}},404)
  with EVENTS.open("a") as f:f.write(json.dumps(event,sort_keys=True)+"\\n")
  STATE.write_text(json.dumps(s,sort_keys=True));return self.reply({{"ok":True,"rows":event.get("rows",[]),"status":event.get("status")}})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",{port}),H).serve_forever()
'''
        assets["browser-server.py"]=server.encode()
    if "Terminal" in apps:
        state={"expected":a_final if apps[0]=="Terminal" else b_final,"completed":False}
        if workflow_id=="C-06":
            assets["terminal-task.sh"]=(f"#!/bin/sh\nprintf '{a_final}\\n'\nprintf 'CoDesk terminal ready\\n'\n").encode()
        else:
            assets["terminal-task.sh"]=("#!/bin/sh\nprintf 'CoDesk terminal ready\\n'\n").encode()
        assets["terminal-state.json"]=(json.dumps(state,sort_keys=True)+"\n").encode()
    return assets

