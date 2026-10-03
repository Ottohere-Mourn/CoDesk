"""Deterministic semantic-instance production for CoDesk V1 (offline only).

This package materializes fixed, typed task instances and exact private oracles.
It never starts Guests, applications, models, or external services.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import base64
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
from typing import Any
import xml.etree.ElementTree as ET

SCHEMA_VERSION = 1
BENCHMARK_VERSION = "codesk-v1.0"
FAMILIES = {
    "focus_input_routing": "Focus / Input Routing",
    "clipboard_state": "Clipboard State",
    "application_context": "Application Context",
    "selection_active_object": "Selection / Active Object",
    "undo_redo_history": "Undo / Redo History",
}
DOMAINS = (
    {"id":"capital_allocation", "title":"Capital allocation review", "entity":"capital request",
     "a_status":"Approved", "b_status":"Recorded", "field_a":"Decision", "field_b":"Ledger state",
     "source":"CAP-4821", "payload":"North facility modernization allocation"},
    {"id":"warehouse_reconciliation", "title":"Warehouse reconciliation", "entity":"warehouse lot",
     "a_status":"Reconciled", "b_status":"Counted", "field_a":"Reconciliation", "field_b":"Count status",
     "source":"SKU-7316", "payload":"North depot cycle-count discrepancy"},
    {"id":"supplier_onboarding", "title":"Supplier onboarding review", "entity":"supplier record",
     "a_status":"Accepted", "b_status":"Verified", "field_a":"Review decision", "field_b":"Verification state",
     "source":"SUP-2048", "payload":"Supplier safety and payment review"},
    {"id":"safety_inspection", "title":"Safety inspection closeout", "entity":"inspection item",
     "a_status":"Cleared", "b_status":"Inspected", "field_a":"Clearance", "field_b":"Inspection state",
     "source":"SAFE-1193", "payload":"Loading-bay guardrail follow-up inspection"},
)
LAYOUTS = (
    {"id":"guard_after", "guard_placement":"trailing", "field_order":"goal_then_guard",
     "fixture_layout":"target-before-guard"},
    {"id":"guard_before", "guard_placement":"leading", "field_order":"guard_then_goal",
     "fixture_layout":"guard-before-target"},
)

# Every profile changes target object/schema, not just a displayed token.
_PROFILE_ROWS: dict[str, list[dict[str, Any]]] = {
"F-01":[{"id":"cell_b2","a":"writer/decision-paragraph","b":"calc/B2","schema":{"headers":["Request","Decision"],"target":"B2"}},
{"id":"cell_c2","a":"writer/decision-paragraph","b":"calc/C2","schema":{"headers":["Request","Owner","Decision"],"target":"C2"}},
{"id":"cell_b3","a":"writer/summary-paragraph","b":"calc/B3","schema":{"headers":["Asset","Status"],"target":"B3"}},
{"id":"cell_c3","a":"writer/summary-paragraph","b":"calc/C3","schema":{"headers":["Asset","Region","Status"],"target":"C3"}},
{"id":"cell_d2","a":"writer/approval-field","b":"calc/D2","schema":{"headers":["Item","Owner","Region","Status"],"target":"D2"}}],
"F-04":[{"id":"range_b2_c3","a":"calc/B2:C3","b":"writer/decision-paragraph","schema":{"range":["B2","C3"],"shape":[2,2]}},
{"id":"range_c2_d3","a":"calc/C2:D3","b":"writer/summary-paragraph","schema":{"range":["C2","D3"],"shape":[2,2]}},
{"id":"range_b2_d3","a":"calc/B2:D3","b":"writer/status-paragraph","schema":{"range":["B2","D3"],"shape":[2,3]}},
{"id":"range_b3_c4","a":"calc/B3:C4","b":"writer/approval-paragraph","schema":{"range":["B3","C4"],"shape":[2,2]}},
{"id":"range_c3_e4","a":"calc/C3:E4","b":"writer/summary-paragraph","schema":{"range":["C3","E4"],"shape":[2,3]}}],
"F-02":[{"id":"anchor_summary","a":"writer/comment-anchor:summary","b":"browser/review/decision","schema":{"anchor_kind":"summary sentence","form_fields":["case","decision"]}},
{"id":"anchor_risk","a":"writer/comment-anchor:risk","b":"browser/review/risk","schema":{"anchor_kind":"risk sentence","form_fields":["risk_id","disposition"]}},
{"id":"anchor_supplier","a":"writer/comment-anchor:supplier","b":"browser/review/vendor","schema":{"anchor_kind":"supplier paragraph","form_fields":["supplier","decision"]}},
{"id":"anchor_budget","a":"writer/comment-anchor:budget","b":"browser/review/allocation","schema":{"anchor_kind":"allocation sentence","form_fields":["request","approval"]}},
{"id":"anchor_action","a":"writer/comment-anchor:action","b":"browser/review/action-item","schema":{"anchor_kind":"action item","form_fields":["owner","status"]}}],
"C-01":[{"id":"writer_note_calc_cell","a":"writer/insertion-after-heading","b":"calc/B2","schema":{"payload_kind":"plain note","destination":"single cell"}},
{"id":"writer_record_calc_cell","a":"writer/insertion-after-record","b":"calc/C2","schema":{"payload_kind":"record identifier","destination":"single cell"}},
{"id":"writer_url_calc_cell","a":"writer/insertion-after-reference","b":"calc/B3","schema":{"payload_kind":"plain URL text","destination":"single cell"}},
{"id":"writer_action_calc_cell","a":"writer/insertion-after-action","b":"calc/C3","schema":{"payload_kind":"action phrase","destination":"single cell"}},
{"id":"writer_summary_calc_cell","a":"writer/insertion-before-guard","b":"calc/D2","schema":{"payload_kind":"summary text","destination":"single cell"}}],
"C-03":[{"id":"matrix_2x2","a":"calc/B2:C3","b":"writer/paragraph-2","schema":{"shape":[2,2],"paste_target":"paragraph"}},
{"id":"matrix_2x3","a":"calc/B2:D3","b":"writer/table-slot-1","schema":{"shape":[2,3],"paste_target":"table-slot"}},
{"id":"matrix_3x2","a":"calc/B2:C4","b":"writer/paragraph-3","schema":{"shape":[3,2],"paste_target":"paragraph"}},
{"id":"matrix_3x3","a":"calc/B2:D4","b":"writer/table-slot-2","schema":{"shape":[3,3],"paste_target":"table-slot"}},
{"id":"matrix_2x4","a":"calc/B2:E3","b":"writer/paragraph-4","schema":{"shape":[2,4],"paste_target":"paragraph"}}],
"C-02":[{"id":"href_reference","a":"writer/hyperlink:reference","b":"browser/url-field:case","schema":{"link_label_kind":"reference label","destination_field":"case-url"}},
{"id":"href_source","a":"writer/hyperlink:source","b":"browser/url-field:supplier","schema":{"link_label_kind":"source label","destination_field":"supplier-url"}},
{"id":"href_policy","a":"writer/hyperlink:policy","b":"browser/url-field:policy","schema":{"link_label_kind":"policy label","destination_field":"policy-url"}},
{"id":"href_evidence","a":"writer/hyperlink:evidence","b":"browser/url-field:evidence","schema":{"link_label_kind":"evidence label","destination_field":"evidence-url"}},
{"id":"href_ticket","a":"writer/hyperlink:ticket","b":"browser/url-field:ticket","schema":{"link_label_kind":"ticket label","destination_field":"ticket-url"}}],
"A-01":[{"id":"tabs_review_cases","a":"browser/tab-a/review-form","b":"browser/tab-b/case-form","schema":{"context_kind":"independent tab forms","fields":["review","case"]}},
{"id":"tabs_supplier_docs","a":"browser/tab-a/supplier-page","b":"browser/tab-b/document-page","schema":{"context_kind":"tab-specific records","fields":["supplier","document"]}},
{"id":"tabs_inventory","a":"browser/tab-a/stock-form","b":"browser/tab-b/audit-form","schema":{"context_kind":"tab-specific inventory","fields":["stock","audit"]}},
{"id":"tabs_safety","a":"browser/tab-a/inspection-form","b":"browser/tab-b/incident-form","schema":{"context_kind":"tab-specific safety records","fields":["inspection","incident"]}},
{"id":"tabs_release","a":"browser/tab-a/release-form","b":"browser/tab-b/approval-form","schema":{"context_kind":"tab-specific release records","fields":["release","approval"]}}],
"A-02":[{"id":"record_supplier","a":"browser/record:supplier","b":"browser/record:invoice","schema":{"record_type":"supplier/invoice","selection":"record row"}},
{"id":"record_asset","a":"browser/record:asset","b":"browser/record:maintenance","schema":{"record_type":"asset/maintenance","selection":"record row"}},
{"id":"record_safety","a":"browser/record:inspection","b":"browser/record:incident","schema":{"record_type":"inspection/incident","selection":"record row"}},
{"id":"record_budget","a":"browser/record:allocation","b":"browser/record:reimbursement","schema":{"record_type":"allocation/reimbursement","selection":"record row"}},
{"id":"record_release","a":"browser/record:release","b":"browser/record:change-request","schema":{"record_type":"release/change-request","selection":"record row"}}],
"S-01":[{"id":"cells_b2_c3","a":"calc/B2","b":"calc/C3","schema":{"object_type":"cell","action":"set value"}},
{"id":"cells_c2_d3","a":"calc/C2","b":"calc/D3","schema":{"object_type":"cell","action":"set value"}},
{"id":"cells_b3_d2","a":"calc/B3","b":"calc/D2","schema":{"object_type":"cell","action":"set value"}},
{"id":"cells_c3_e4","a":"calc/C3","b":"calc/E4","schema":{"object_type":"cell","action":"set value"}},
{"id":"cells_b2_e3","a":"calc/B2","b":"calc/E3","schema":{"object_type":"cell","action":"set value"}}],
"U-01":[{"id":"calc_status_cells","a":"calc/B2","b":"calc/C3","schema":{"object_type":"cell","operation":"value edit","undo_depth":1}},
{"id":"calc_formula_cells","a":"calc/C2","b":"calc/D3","schema":{"object_type":"cell","operation":"formula/value edit","undo_depth":1}},
{"id":"calc_audit_cells","a":"calc/B3","b":"calc/E2","schema":{"object_type":"cell","operation":"audit value edit","undo_depth":1}},
{"id":"calc_release_cells","a":"calc/C3","b":"calc/D4","schema":{"object_type":"cell","operation":"release value edit","undo_depth":1}},
{"id":"calc_inventory_cells","a":"calc/D2","b":"calc/E4","schema":{"object_type":"cell","operation":"inventory value edit","undo_depth":1}}],
"F-N1":[{"id":"writer_doc_status","a":"writer/doc-a/status-paragraph","b":"writer/doc-b/status-paragraph","schema":{"documents":["doc-a","doc-b"],"target_kind":"status paragraph"}},
{"id":"writer_doc_summary","a":"writer/doc-a/summary-paragraph","b":"writer/doc-b/summary-paragraph","schema":{"documents":["doc-a","doc-b"],"target_kind":"summary paragraph"}},
{"id":"writer_doc_action","a":"writer/doc-a/action-item","b":"writer/doc-b/action-item","schema":{"documents":["doc-a","doc-b"],"target_kind":"action item"}},
{"id":"writer_doc_decision","a":"writer/doc-a/decision-field","b":"writer/doc-b/decision-field","schema":{"documents":["doc-a","doc-b"],"target_kind":"decision field"}},
{"id":"writer_doc_owner","a":"writer/doc-a/owner-line","b":"writer/doc-b/owner-line","schema":{"documents":["doc-a","doc-b"],"target_kind":"owner line"}}],
"C-N1":[{"id":"rich_table_2x2","a":"writer/table-slot-1","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[2,2],"mime":["text/html","text/plain"]}},
{"id":"rich_table_2x3","a":"writer/table-slot-2","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[2,3],"mime":["text/html","text/plain"]}},
{"id":"rich_table_3x2","a":"writer/table-slot-1","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[3,2],"mime":["text/html","text/plain"]}},
{"id":"rich_table_3x3","a":"writer/table-slot-2","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[3,3],"mime":["text/html","text/plain"]}},
{"id":"rich_table_4x2","a":"writer/table-slot-1","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[4,2],"mime":["text/html","text/plain"]}}],
"A-N1":[{"id":"spa_assignment_incident","a":"browser/route:assignment","b":"browser/route:incident","schema":{"route_pair":["assignment","incident"],"field":"resolution"}},
{"id":"spa_supplier_invoice","a":"browser/route:supplier","b":"browser/route:invoice","schema":{"route_pair":["supplier","invoice"],"field":"decision"}},
{"id":"spa_inventory_audit","a":"browser/route:inventory","b":"browser/route:audit","schema":{"route_pair":["inventory","audit"],"field":"audit-state"}},
{"id":"spa_safety_followup","a":"browser/route:safety","b":"browser/route:followup","schema":{"route_pair":["safety","followup"],"field":"clearance"}},
{"id":"spa_release_change","a":"browser/route:release","b":"browser/route:change","schema":{"route_pair":["release","change"],"field":"approval"}}],
"S-N1":[{"id":"range_word_pair","a":"writer/range:single-word-a","b":"writer/range:single-word-b","schema":{"selection_kind":"word range","action":"bold"}},
{"id":"range_phrase_pair","a":"writer/range:phrase-a","b":"writer/range:phrase-b","schema":{"selection_kind":"phrase range","action":"bold"}},
{"id":"range_sentence_pair","a":"writer/range:sentence-a","b":"writer/range:sentence-b","schema":{"selection_kind":"sentence range","action":"bold"}},
{"id":"range_list_item_pair","a":"writer/range:list-item-a","b":"writer/range:list-item-b","schema":{"selection_kind":"list item range","action":"bold"}},
{"id":"range_heading_pair","a":"writer/range:heading-a","b":"writer/range:heading-b","schema":{"selection_kind":"heading text range","action":"bold"}}],
"U-N1":[{"id":"writer_lines_0_1","a":"writer/paragraph[0]","b":"writer/paragraph[1]","schema":{"object_type":"paragraph","undo_operation":"text replacement","undo_depth":1}},
{"id":"writer_lines_1_2","a":"writer/paragraph[1]","b":"writer/paragraph[2]","schema":{"object_type":"paragraph","undo_operation":"text replacement","undo_depth":1}},
{"id":"writer_lines_0_2","a":"writer/paragraph[0]","b":"writer/paragraph[2]","schema":{"object_type":"paragraph","undo_operation":"text replacement","undo_depth":1}},
{"id":"writer_lines_2_3","a":"writer/paragraph[2]","b":"writer/paragraph[3]","schema":{"object_type":"paragraph","undo_operation":"text replacement","undo_depth":1}},
{"id":"writer_lines_1_3","a":"writer/paragraph[1]","b":"writer/paragraph[3]","schema":{"object_type":"paragraph","undo_operation":"text replacement","undo_depth":1}}],
}

ACTORS = ("A", "B")

@dataclass(frozen=True)
class ActorGoalSpec:
    actor_id: str
    task_domain: str
    goal: str
    operation: str
    target_objects: tuple[str, ...]
    initial_value: str
    expected_value: str

@dataclass(frozen=True)
class InstanceSpecV1:
    benchmark_version: str
    family: str
    workflow_id: str
    instance_id: str
    generation_seed: int
    actor_goals: tuple[ActorGoalSpec, ...]
    task_domains: dict[str, str]
    schedule_policy_id: str
    initial_fixture_spec: dict[str, Any]
    semantic_parameters: dict[str, Any]
    target_objects: dict[str, list[str]]
    expected_final_state: dict[str, Any]
    treatment_relevant_state: dict[str, Any]
    reset_metadata: dict[str, Any]
    topology_compatibility: dict[str, Any]
    provenance: dict[str, Any]
    fixture_files: tuple[dict[str, Any], ...]
    evaluator: dict[str, Any]
    signatures: dict[str, str]
    validation_level: str


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")

def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def git_commit(root: Path) -> str:
    p=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else "unknown"

def _cell_coord(cell: str) -> tuple[int,int]:
    col=0; row=""
    for ch in cell:
        if ch.isalpha(): col=col*26+ord(ch.upper())-64
        elif ch.isdigit(): row += ch
    return int(row)-1,col-1

def _range_cells(cell_range: str) -> list[str]:
    if ":" not in cell_range:return [cell_range]
    start,end=cell_range.split(":",1);r0,c0=_cell_coord(start);r1,c1=_cell_coord(end)
    if r1<r0 or c1<c0:raise ValueError(f"invalid range: {cell_range}")
    def colname(idx:int)->str:
        out="";n=idx+1
        while n: n,rem=divmod(n-1,26);out=chr(65+rem)+out
        return out
    return [f"{colname(c)}{r+1}" for r in range(r0,r1+1) for c in range(c0,c1+1)]

def _xml_file(kind: str, paragraphs: list[str] | None = None,
              rows: list[list[str]] | None = None) -> bytes:
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    root=ET.Element(f"{{{office}}}document",{f"{{{office}}}version":"1.2"})
    body=ET.SubElement(root,f"{{{office}}}body")
    if kind=="writer":
        content=ET.SubElement(body,f"{{{office}}}text")
        for val in paragraphs or []:
            p=ET.SubElement(content,f"{{{text}}}p"); p.text=val
    else:
        content=ET.SubElement(body,f"{{{office}}}spreadsheet")
        sheet=ET.SubElement(content,f"{{{table}}}table",{f"{{{table}}}name":"CoDesk"})
        for values in rows or []:
            tr=ET.SubElement(sheet,f"{{{table}}}table-row")
            for val in values:
                cell=ET.SubElement(tr,f"{{{table}}}table-cell",{f"{{{office}}}value-type":"string"})
                p=ET.SubElement(cell,f"{{{text}}}p"); p.text=val
    ET.register_namespace("office",office); ET.register_namespace("text",text); ET.register_namespace("table",table)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")

def _html(title: str, elements: list[str], layout: str) -> bytes:
    body="\n".join(elements)
    return (f"<!doctype html><meta charset='utf-8'><title>{title}</title>"
            f"<main data-layout='{layout}'><h1>{title}</h1>{body}</main>").encode()

def _profile_catalog(workflow_id: str, seed: int) -> list[tuple[dict[str,Any],dict[str,Any],dict[str,Any]]]:
    profiles=_PROFILE_ROWS[workflow_id]
    combos=list(itertools.product(DOMAINS,profiles,LAYOUTS))
    random.Random(seed).shuffle(combos)
    return combos

def _workflow_row(workflow_id: str) -> dict[str,Any]:
    common={
      "F-01":("focus_input_routing",["Writer","Calc"],"writer_document_vs_calc_field","Edit a Writer decision and a distinct Calc cell.","Save the exact decision in the assigned Writer document.","Set the assigned Calc field and preserve the remaining table.","qwen_mechanism_evidence"),
      "F-04":("focus_input_routing",["Calc","Writer"],"calc_range_vs_writer_document","Fill an assigned Calc rectangle and edit a Writer paragraph.","Fill the assigned spreadsheet range.","Replace the assigned Writer paragraph.","scripted_full"),
      "F-02":("focus_input_routing",["Writer","Browser"],"writer_comment_vs_browser_form","Add an anchored Writer review comment while a Browser review form is completed.","Attach the assigned note to the target review anchor.","Submit the independent review form exactly once.","scripted_full"),
      "C-01":("clipboard_state",["Writer","Calc"],"plain_text_transfer","Transfer plain text from independent sources to Writer and Calc destinations.","Paste the assigned note into the Writer destination.","Paste the assigned identifier into the Calc destination.","qwen_smoke"),
      "C-03":("clipboard_state",["Calc","Writer"],"rectangular_table_transfer","Transfer a Calc rectangle into Writer while duplicating a separate paragraph.","Copy the assigned rectangular range into Writer.","Duplicate the assigned Writer paragraph.","scripted_full"),
      "C-02":("clipboard_state",["Browser","Writer"],"semantic_hyperlink_transfer","Create a semantic hyperlink in Writer while an independent Browser URL is submitted.","Create a link with the exact label and href.","Submit the assigned Browser URL exactly once.","scripted_full"),
      "A-01":("application_context",["Browser","Browser"],"two_tab_context","Submit independent forms in two Browser tabs.","Submit the target value in tab A.","Submit the other target value in tab B.","qwen_mechanism_evidence"),
      "A-02":("selection_active_object",["Browser","Browser"],"selected_record_context","Update two distinct selected Browser records.","Update record A only.","Update record B only.","scripted_full"),
      "S-01":("selection_active_object",["Calc","Calc"],"active_cell_selection","Write two separate Calc cells through selected-cell state.","Set the selected cell A target.","Set the selected cell B target.","qwen_smoke"),
      "U-01":("undo_redo_history",["Calc","Calc"],"calc_document_history","Undo A's temporary edit after B has independently edited the same Calc document.","Undo the temporary value and restore the seeded cell.","Set B's distinct Calc cell to its goal.","qwen_smoke"),
      "F-N1":("focus_input_routing",["Writer","Writer"],"two_writer_windows","Edit distinct Writer documents through two top-level windows.","Replace the assigned paragraph in doc-A.","Replace the assigned paragraph in doc-B.","guest_solo"),
      "C-N1":("clipboard_state",["Browser","Writer"],"rich_html_table_transfer","Paste a real Browser HTML table into Writer while Browser B copies and submits a URL.","Paste the structured table, preserving rows and cells.","Copy and submit the assigned URL.","offline"),
      "A-N1":("application_context",["Browser","Browser"],"same_tab_spa_route","Complete separate route-keyed transactions in one Browser tab.","Submit route A's exact value.","Submit route B's exact value.","offline"),
      "S-N1":("selection_active_object",["Writer","Writer"],"writer_text_range_selection","Apply formatting to two distinct text ranges in one Writer document.","Bold only range A.","Bold only range B.","offline"),
      "U-N1":("undo_redo_history",["Writer","Writer"],"writer_document_history","Undo A's temporary Writer edit after B's independent same-document edit.","Undo the temporary first-line edit and restore the seed.","Set the second-line goal without losing it to A's Undo.","offline"),
    }
    row=common[workflow_id]
    schedule_ids={
      "F-01":"action-boundary-round-robin-ab-v1","F-04":"action-boundary-round-robin-ab-v1",
      "F-02":"writer-anchor-browser-form-comment-v1","C-01":"copy-confirm-b-copy-confirm-resume-a-v1",
      "C-03":"range-copy-confirm-paragraph-copy-confirm-resume-v1","C-02":"url-copy-confirm-link-copy-confirm-resume-v1",
      "A-01":"observe-a-context-change-b-resume-a-v1","A-02":"observe-selection-change-b-resume-a-v1",
      "S-01":"select-a-select-b-resume-a-v1","U-01":"edit-a-edit-b-undo-a-v1",
      "F-N1":"writer-window-a-window-b-resume-a-v1","C-N1":"rich-copy-a-url-copy-b-resume-a-v1",
      "A-N1":"route-observe-a-change-b-resume-a-v1","S-N1":"range-select-a-select-b-resume-a-v1",
      "U-N1":"edit-a-edit-b-undo-a-v1"}
    return {"workflow_id":workflow_id,"family":row[0],"task_domains":row[1],
            "operation_graph":row[2],"description":row[3],"goal_a":row[4],"goal_b":row[5],
            "schedule_policy_id":schedule_ids[workflow_id],
            "validation_level":row[6],"runtime_validation_incomplete":workflow_id in {"F-N1","C-N1","A-N1","S-N1","U-N1"},
            "semantic_parameter_schema":{"domain_fields":["entity","field_a","field_b","a_status","b_status"],
              "object_profiles":_PROFILE_ROWS[workflow_id],
              "layout_fields":["guard_placement","field_order","fixture_layout"],
              "identity_excludes":["generation_seed","repeat","condition","model","window_coordinates"],
              "actor_target_disjoint":True,"no_op_goals_allowed":False}}

def workflow_registry() -> list[dict[str,Any]]:
    return [_workflow_row(w) for w in _PROFILE_ROWS]

def _targets(row: dict[str,Any], profile: dict[str,Any], layout: dict[str,Any]) -> dict[str,list[str]]:
    # Layout is part of a target's semantic context but never its sole identity.
    return {"A":[profile["a"]],"B":[profile["b"]]}

def _semantic_values(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                      layout: dict[str,Any]) -> tuple[str,str,str,str]:
    label=profile["schema"].get("target",profile["schema"].get("selection",profile["schema"].get("payload",profile["schema"].get("object_type","object"))))
    a_initial=f"Draft: {domain['entity']}"
    b_initial=f"Pending: {domain['entity']}"
    a_final=f"{domain['a_status']}: {domain['entity']} ({label})"
    b_final=f"{domain['b_status']}: {domain['entity']} ({label})"
    return a_initial,b_initial,a_final,b_final

def _fixture_bytes(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                   layout: dict[str,Any], a_initial: str, b_initial: str,
                   a_final: str, b_final: str, instance_id: str) -> dict[str,bytes]:
    schema=profile["schema"]
    assets:dict[str,bytes]={}
    if "Writer" in _workflow_row(workflow_id)["task_domains"]:
        if workflow_id=="F-N1":
            paras=[domain["title"],a_initial,"Guard: A-KEEP"]
            paras_b=[domain["title"],b_initial,"Guard: B-KEEP"]
            if layout["guard_placement"]=="leading":
                paras=["Guard: A-KEEP",domain["title"],a_initial]; paras_b=["Guard: B-KEEP",domain["title"],b_initial]
            assets["doc-a.fodt"]=_xml_file("writer",paras)
            assets["doc-b.fodt"]=_xml_file("writer",paras_b)
        else:
            p=[domain["title"],a_initial,b_initial,"Guard: PRESERVE"]
            if layout["guard_placement"]=="leading": p=["Guard: PRESERVE",domain["title"],a_initial,b_initial]
            if workflow_id=="S-N1":
                p=[domain["title"],f"ALPHA {domain['entity']} | BETA {domain['entity']}","Guard: PRESERVE"]
                if layout["guard_placement"]=="leading": p=["Guard: PRESERVE",domain["title"],f"ALPHA {domain['entity']} | BETA {domain['entity']}"]
            elif workflow_id=="U-N1":
                p=[a_initial,b_initial,"Guard: PRESERVE"]
                if layout["guard_placement"]=="leading": p=["Guard: PRESERVE",a_initial,b_initial]
            assets["document.fodt"]=_xml_file("writer",p)
    if "Calc" in _workflow_row(workflow_id)["task_domains"]:
        headers=schema.get("headers") or [domain["field_a"],domain["field_b"]]
        rows=[list(headers)]
        ncols=max(2,len(headers))
        nrows=5
        for ri in range(1,nrows):
            rows.append([f"{domain['entity']} {ri}"]+["Draft"]*(ncols-1))
        for target in (profile["a"],profile["b"]):
            if target.startswith("calc/"):
                try:
                    cell_ref=target.split("/")[-1]
                    for cell_idx,cell in enumerate(_range_cells(cell_ref)):
                        r,c=_cell_coord(cell)
                        while len(rows)<=r: rows.append([""]*ncols)
                        while len(rows[r])<=c: rows[r].append("")
                        rows[r][c]=(f"{a_initial} {cell}" if target==profile["a"] and ":" in cell_ref
                                    else a_initial if target==profile["a"] else b_initial)
                except Exception: raise
        assets["workbook.fods"]=_xml_file("calc",rows=rows)
    if "Browser" in _workflow_row(workflow_id)["task_domains"]:
        elements=[]
        if workflow_id=="C-N1":
            r,c=schema["shape"]
            table="<table data-object='rich-payload'><tbody>"+"".join(
                "<tr>"+"".join(f"<td><strong>{domain['entity']} {ri+1}.{ci+1}</strong></td>" for ci in range(c))+"</tr>" for ri in range(r))+"</tbody></table>"
            elements.append(table)
        elif workflow_id=="C-02":
            elements.append(f"<a href='https://example.org/{domain['id']}/{instance_id[-6:]}'>Open {domain['entity']} reference</a>")
        elif workflow_id=="A-01":
            elements.extend([f"<section data-tab='A'><label>{domain['field_a']}<input id='a' value='{a_initial}'></label></section>",
                             f"<section data-tab='B'><label>{domain['field_b']}<input id='b' value='{b_initial}'></label></section>"])
        elif workflow_id=="A-02":
            elements.extend([f"<button data-record='A'>{domain['entity']} A</button>",f"<button data-record='B'>{domain['entity']} B</button>"])
        elif workflow_id=="A-N1":
            elements.extend(["<button data-route='A'>Open A</button>","<button data-route='B'>Open B</button>",
                             f"<input data-route-field='{schema.get('field','resolution')}'>"])
        elif workflow_id=="F-02":
            elements.append(f"<form data-object='review'><label>{domain['field_a']}<input id='decision'></label><button>Submit</button></form>")
        else:
            elements.append(f"<form data-object='{profile['b']}'><label>{domain['field_b']}<input id='value'></label><button>Submit</button></form>")
        assets["workspace.html"]=_html(domain["title"],elements,layout["fixture_layout"])
        assets["browser-initial-state.json"]=(json.dumps({"domain":domain["id"],"records":{"A":a_initial,"B":b_initial},"routes":{"A":"initial","B":"initial"},"submissions":{}},sort_keys=True)+"\n").encode()
    if not assets:
        assets["task-state.json"]=(json.dumps({"domain":domain["id"],"initial_a":a_initial,"initial_b":b_initial},sort_keys=True)+"\n").encode()
    return assets

def _source_digest() -> str:
    return sha256(Path(__file__).read_bytes())

def build_instance(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                   layout: dict[str,Any], generation_seed: int, root: Path) -> InstanceSpecV1:
    row=_workflow_row(workflow_id)
    a0,b0,a1,b1=_semantic_values(workflow_id,domain,profile,layout)
    target_objects=_targets(row,profile,layout)
    if len(set(target_objects["A"]+target_objects["B"])) != 2:
        raise ValueError(f"actor target overlap in {workflow_id}/{profile['id']}")
    if a0==a1 or b0==b1: raise ValueError("no-op actor goal")
    semantic={"workflow_id":workflow_id,"operation_graph":row["operation_graph"],
              "domain_id":domain["id"],"object_profile_id":profile["id"],
              "object_schema":profile["schema"],"layout_id":layout["id"],
              "domain_schema":{k:domain[k] for k in ("entity","field_a","field_b")}}
    semantic_sig=sha256(canonical_bytes(semantic))
    instance_id=f"cdv1-{workflow_id.lower().replace('-','')}-{semantic_sig[:16]}"
    initial={"actors":{"A":{"value":a0,"object":target_objects["A"][0]},
                       "B":{"value":b0,"object":target_objects["B"][0]},
                       "guards":{"main":"PRESERVE"}},
             "treatment":{"resource":row["family"],"initial":profile["schema"]}}
    expected=json.loads(json.dumps(initial))
    expected["actors"]["A"]["value"]=a1; expected["actors"]["B"]["value"]=b1
    actor_goals=(ActorGoalSpec("A",row["task_domains"][0],row["goal_a"],
                 f"{profile['schema'].get('action','update')} {target_objects['A'][0]}",
                 tuple(target_objects["A"]),a0,a1),
                 ActorGoalSpec("B",row["task_domains"][1],row["goal_b"],
                 f"{profile['schema'].get('action','update')} {target_objects['B'][0]}",
                 tuple(target_objects["B"]),b0,b1))
    assets=_fixture_bytes(workflow_id,domain,profile,layout,a0,b0,a1,b1,instance_id)
    fixture_rows=[]
    for rel,data in sorted(assets.items()):
        fixture_rows.append({"path":f"fixtures/{instance_id}/{rel}","sha256":sha256(data),"size_bytes":len(data)})
    fixture_hash=sha256(canonical_bytes(fixture_rows))
    goal_signature=sha256(canonical_bytes({"workflow":workflow_id,"domain":domain["id"],
        "objects":target_objects,"operations":[actor_goals[0].operation,actor_goals[1].operation],
        "schema":profile["schema"],"layout":layout["id"]}))
    structural_signature=sha256(canonical_bytes({"workflow":workflow_id,
        "operation_graph":row["operation_graph"],"domain_schema_id":domain["id"],
        "object_profile_id":profile["id"],"layout_id":layout["id"],"schema":profile["schema"]}))
    evaluator={"adapter":"codesk_exact_state_v1","actor_paths":{"A":"actors.A.value","B":"actors.B.value"},
       "expected_state":expected,"initial_state":initial,"invariants":[{"path":"actors.guards.main","equals":"PRESERVE"}],
       "schedule_policy_id":row["schedule_policy_id"],
       "condition_semantics":{"solo":"score selected actor; require inactive target and guards unchanged",
        "ma_id":"score each actor on equivalent independent desktop fixture",
        "ma_sd":"score both actor goals and shared-state integrity"}}
    source_hash=_source_digest()
    provenance={"generator":"swcub.production_v1","source_code_sha256":source_hash,
        "source_commit":git_commit(Path(__file__).resolve().parents[1]),"semantic_spec_sha256":semantic_sig,
        "fixture_sha256":fixture_hash,"generation_seed":generation_seed,
        "seed_role":"deterministic profile ordering only; excluded from instance identity"}
    reset={"fixture_id":instance_id,"fresh_guest_required":True,"remove_prior_app_state":True,
           "verify_fixture_hash":fixture_hash,"verify_state":initial}
    topology={"solo":{"desktop_count":1,"actor_bindings":"A or B"},
       "ma_id":{"desktop_count":2,"fixtures":"byte-identical task-relevant clones",
                "backend_binding":"same logical workspace seed; independent desktop sessions allowed"},
       "ma_sd":{"desktop_count":1,"actor_bindings":"A and B share desktop"}}
    spec=InstanceSpecV1(BENCHMARK_VERSION,row["family"],workflow_id,instance_id,generation_seed,
       actor_goals,{"A":row["task_domains"][0],"B":row["task_domains"][1]},row["schedule_policy_id"],
       {"application_set":row["task_domains"],"fixture_profile":profile["id"],"layout_id":layout["id"],
        "public_assets":fixture_rows},semantic,target_objects,expected,
       {"family_state":row["family"],"shared_resource":profile["schema"],"operation_graph":row["operation_graph"]},
       reset,topology,provenance,tuple({"path":f"fixtures/{instance_id}/{rel}","bytes_b64":base64.b64encode(data).decode()} for rel,data in sorted(assets.items())),
       evaluator,{"structural":structural_signature,"semantic":semantic_sig,"goal":goal_signature,
                  "fixture":fixture_hash},row["validation_level"])
    validate_instance(spec)
    return spec

def instance_dict(spec: InstanceSpecV1) -> dict[str,Any]:
    return asdict(spec)

def validate_instance(spec: InstanceSpecV1) -> None:
    if spec.benchmark_version!=BENCHMARK_VERSION or spec.family not in FAMILIES or spec.workflow_id not in _PROFILE_ROWS:
        raise ValueError("unknown version/family/workflow")
    if len(spec.actor_goals)<2 or [a.actor_id for a in spec.actor_goals[:2]] != ["A","B"]:
        raise ValueError("V1 requires independent Actor A/B; schema remains N-extensible")
    if set(spec.topology_compatibility)!={"solo","ma_id","ma_sd"}:
        raise ValueError("all topologies are required")
    if set(spec.target_objects["A"]) & set(spec.target_objects["B"]):
        raise ValueError("actor target objects overlap")
    if any(a.initial_value==a.expected_value for a in spec.actor_goals):
        raise ValueError("no-op actor target")
    if not spec.fixture_files or not spec.provenance.get("source_code_sha256"):
        raise ValueError("fixture/provenance required")

def evaluate_oracle(spec: InstanceSpecV1 | dict[str,Any], actual: dict[str,Any],
                    active_actors: tuple[str,...]=("A","B")) -> dict[str,Any]:
    row=instance_dict(spec) if isinstance(spec,InstanceSpecV1) else spec
    if not active_actors or not set(active_actors)<={"A","B"}: raise ValueError("invalid active actors")
    initial=row["evaluator"]["initial_state"]; expected=row["evaluator"]["expected_state"]
    actor_success={a:(actual.get("actors",{}).get(a,{}).get("value")==expected["actors"][a]["value"])
                   for a in active_actors}
    inactive_integrity={a:(actual.get("actors",{}).get(a)==initial["actors"][a])
                        for a in ("A","B") if a not in active_actors}
    guards_ok=actual.get("actors",{}).get("guards")==initial["actors"]["guards"]
    return {"actor_success":actor_success,"inactive_target_integrity":inactive_integrity,
       "guards_intact":guards_ok,"joint_success":bool(actor_success) and all(actor_success.values())
           and all(inactive_integrity.values()) and guards_ok}

def _positive_state(spec: InstanceSpecV1) -> dict[str,Any]: return json.loads(json.dumps(spec.expected_final_state))
def _negative_state(spec: InstanceSpecV1) -> dict[str,Any]:
    bad=_positive_state(spec); bad["actors"]["A"]["value"]=spec.actor_goals[0].initial_value; return bad

def to_record(spec: InstanceSpecV1) -> dict[str,Any]:
    d=instance_dict(spec)
    d["actor_goals"]=[asdict(x) for x in spec.actor_goals]
    d["schedule_policy_id"]=spec.schedule_policy_id
    # Public manifest references checked hashes/sizes; private encoded bytes stay in the
    # generator's in-memory object and are materialized under fixtures/.
    d["fixture_files"]=list(spec.initial_fixture_spec["public_assets"])
    d["evaluator_path"]=f"evaluators/{spec.instance_id}.json"
    d.pop("expected_final_state",None)
    return d

def materialize(spec: InstanceSpecV1, root: Path) -> dict[str,Any]:
    record=to_record(spec)
    instdir=root/"instances"/spec.instance_id
    if instdir.exists(): raise FileExistsError(instdir)
    instdir.mkdir(parents=True)
    for row in spec.fixture_files:
        path=root/row["path"]; path.parent.mkdir(parents=True,exist_ok=True)
        data=base64.b64decode(row["bytes_b64"],validate=True)
        if sha256(data)!=next(x["sha256"] for x in record["fixture_files"] if x["path"]==row["path"]):
            raise ValueError("fixture hash mismatch before write")
        path.write_bytes(data)
    evaluator=root/record["evaluator_path"]; evaluator.parent.mkdir(parents=True,exist_ok=True)
    evaluator.write_text(json.dumps(spec.evaluator,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    record["evaluator_sha256"]=sha256(evaluator.read_bytes())
    record["manifest_entry_sha256"]=sha256(canonical_bytes(record))
    (instdir/"manifest.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return record

def generate_workflow(workflow_id: str, count: int, seed: int, root: Path) -> list[dict[str,Any]]:
    if workflow_id not in _PROFILE_ROWS: raise ValueError(f"unknown workflow {workflow_id}")
    if type(count) is not int or count<1: raise ValueError("count must be positive")
    catalog=_profile_catalog(workflow_id,seed)
    if count>len(catalog): raise ValueError(f"requested {count}; semantic catalog has only {len(catalog)} unique profiles")
    records=[]
    for domain,profile,layout in catalog[:count]:
        spec=build_instance(workflow_id,domain,profile,layout,seed,root)
        records.append(materialize(spec,root))
    return records

def create_suite(root: Path, seed: int=2026, quota: int=40,
                 workflows: list[str] | None=None) -> dict[str,Any]:
    root.mkdir(parents=True,exist_ok=False)
    for d in ("families","workflows","instances","fixtures","evaluators","metadata","validation_45"):
        (root/d).mkdir()
    selected=workflows or list(_PROFILE_ROWS)
    if set(selected)-set(_PROFILE_ROWS): raise ValueError("unknown workflows")
    for family_id,label in FAMILIES.items():
        (root/"families"/f"{family_id}.json").write_text(json.dumps({"family_id":family_id,"label":label,"benchmark_version":BENCHMARK_VERSION},indent=2)+"\n")
    rows=[]
    for wid in selected:
        wd=_workflow_row(wid)
        (root/"workflows"/f"{wid}.json").write_text(json.dumps(wd,indent=2)+"\n")
        rows.extend(generate_workflow(wid,quota,seed,root))
    rows.sort(key=lambda x:(x["workflow_id"],x["instance_id"]))
    audit=audit_records(rows)
    if audit["duplicate_rejected"]:
        raise ValueError(f"suite diversity gate failed: {audit['duplicate_rejected']} duplicate/near-duplicate records")
    (root/"manifest.jsonl").write_text("".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n" for r in rows))
    validation_rows=[]
    for wid in selected:
        for domain,profile,layout in _profile_catalog(wid,seed)[:3]:
            spec=build_instance(wid,domain,profile,layout,seed,Path(__file__).resolve().parents[1])
            validation_rows.append(materialize(spec,root/"validation_45"))
    (root/"validation_45"/"manifest.jsonl").write_text("".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n" for r in validation_rows))
    smoke_ids=("F-01","C-01","A-01","S-01","U-01")
    smoke_first={}
    for r in rows:
        if r["workflow_id"] in smoke_ids: smoke_first.setdefault(r["workflow_id"],r)
    (root/"smoke_suite.jsonl").write_text("".join(json.dumps(smoke_first[w],sort_keys=True,separators=(",",":"))+"\n" for w in smoke_ids if w in smoke_first))
    (root/"metadata"/"generation.json").write_text(json.dumps({"benchmark_version":BENCHMARK_VERSION,
       "seed":seed,"quota_by_workflow":quota,"workflow_count":len(selected),"instance_count":len(rows),
       "source_commit":git_commit(Path(__file__).resolve().parents[1]),"family_count":len({r["family"] for r in rows}),
       "validation_45_count":len(validation_rows),"smoke_suite_count":len(smoke_first)},indent=2)+"\n")
    (root/"metadata"/"diversity-audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
    return {"instance_count":len(rows),"workflow_count":len(selected),"family_count":len({r["family"] for r in rows}),
            "validation_45_count":len(validation_rows),"smoke_suite_count":len(smoke_first),
            "duplicates_rejected":audit["duplicate_rejected"]}

def audit_records(records: list[dict[str,Any]]) -> dict[str,Any]:
    exact=set(); goals=set(); fixtures=set(); structures=set(); near=set(); exact_rows=set(); near_rows=set()
    rows_by_workflow:dict[str,int]={}; levels:dict[str,str]={}
    for r in records:
        wid=r["workflow_id"]; rows_by_workflow[wid]=rows_by_workflow.get(wid,0)+1; levels[wid]=r["validation_level"]
        sem=r["signatures"]["semantic"]; goal=r["signatures"]["goal"]; fixture=r["signatures"]["fixture"];struct=r["signatures"]["structural"]
        if sem in exact: exact_rows.add((wid,r["instance_id"],"semantic"))
        else: exact.add(sem)
        if goal in goals: exact_rows.add((wid,r["instance_id"],"goal_pair"))
        else: goals.add(goal)
        if fixture in fixtures: exact_rows.add((wid,r["instance_id"],"fixture"))
        else: fixtures.add(fixture)
        if struct in structures: near_rows.add((wid,r["instance_id"],"structural"))
        else: structures.add(struct)
        # Normalize away literal strings and instance ids, but retain semantic domain,
        # object schema/target and structural guard placement. A pure text substitution
        # therefore collides; a different target/schema or task-relevant layout does not.
        near_key=(wid,r["semantic_parameters"]["domain_id"],
                  canonical_bytes(r["semantic_parameters"]["object_schema"]).decode(),
                  canonical_bytes(r["target_objects"]).decode(),
                  r["semantic_parameters"]["layout_id"])
        if near_key in near: near_rows.add((wid,r["instance_id"],"normalized_structure"))
        else: near.add(near_key)
    per={}
    for wid,n in rows_by_workflow.items():
        per[wid]={"generated":n,"retained":n,"duplicate_rejected":0,"near_duplicate_rejected":0,
                  "diversity_assessment":"4 domain schemas × 5 workflow object/schema profiles × 2 target/guard layouts; no literal-only axis"}
    duplicate_rows=exact_rows | near_rows
    return {"generated":len(records),"retained":len(records)-len(duplicate_rows),
            "duplicate_rejected":len(duplicate_rows),"exact_duplicate_rejected":len(exact_rows),
            "near_duplicate_rejected":len(near_rows),
            "duplicate_examples":sorted(duplicate_rows)[:20],"near_duplicate_examples":sorted(near_rows)[:20],
            "per_workflow":per,"validation_levels":levels}

def read_manifest(path: Path) -> list[dict[str,Any]]:
    records=[]
    for i,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():continue
        row=json.loads(line)
        if row.get("manifest_entry_sha256")!=sha256(canonical_bytes({k:v for k,v in row.items() if k!="manifest_entry_sha256"})):
            raise ValueError(f"manifest entry hash mismatch at line {i}")
        records.append(row)
    return records

@dataclass(frozen=True)
class RunConfigV1:
    instance_id: str
    topology: str
    model: str
    repeat: int
    active_actors: tuple[str,...]
    @property
    def run_id(self) -> str:
        return "run-"+sha256(canonical_bytes(asdict(self)))[:20]


def make_run_plan(records: list[dict[str,Any]], topologies: list[str], model: str,
                  repeats: int=1, completed_run_ids: set[str] | None=None,
                  infra_attempts: dict[str,int] | None=None, max_infra_retries: int=1) -> list[dict[str,Any]]:
    """Expand fixed instances into run configs. Planning never touches a Guest."""
    completed_run_ids=completed_run_ids or set()
    infra_attempts=infra_attempts or {}
    allowed={"solo","ma_id","ma_sd"}
    if not set(topologies) <= allowed or repeats < 1: raise ValueError("invalid topology/repeats")
    plan=[]
    for row in records:
        for topology in topologies:
            actor_sets=[(a,) for a in ("A","B")] if topology=="solo" else [("A","B")]
            for active in actor_sets:
                for repeat in range(1,repeats+1):
                    cfg=RunConfigV1(row["instance_id"],topology,model,repeat,active)
                    if cfg.run_id in completed_run_ids: continue
                    # Initial attempt plus bounded retries, and retries are authorized
                    # only when prior artifact explicitly says INVALID_INFRA.
                    attempt=infra_attempts.get(cfg.run_id,0)+1
                    if attempt>max_infra_retries+1: continue
                    attempt_run_id=f"{cfg.run_id}-a{attempt}"
                    plan.append({"run_id":attempt_run_id,"base_run_id":cfg.run_id,"attempt":attempt,
                      "max_infra_retries":max_infra_retries,"instance_id":cfg.instance_id,
                      "workflow_id":row["workflow_id"],"family":row["family"],
                      "schedule_policy_id":row.get("schedule_policy_id","unspecified"),
                      "topology":cfg.topology,"model":cfg.model,"repeat":cfg.repeat,
                      "active_actors":list(cfg.active_actors),"status":"PLANNED",
                      "runtime_adapter":"UNAVAILABLE_FAIL_CLOSED",
                      "owner_uid":__import__("os").getuid(),"ownership":"runner-created-run-dir-only",
                      "artifact_path":f"runs/{attempt_run_id}","run_config_sha256":sha256(canonical_bytes(asdict(cfg)))})
    return plan
