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
"F-01":[{"id":"cell_b2","a":"writer/document-content","b":"calc/B2","schema":{"headers":["Record","Status"],"target":"B2"}},
{"id":"cell_c2","a":"writer/document-content","b":"calc/C2","schema":{"headers":["Request","Owner","Decision"],"target":"C2"}},
{"id":"cell_b3","a":"writer/document-content","b":"calc/B3","schema":{"headers":["Asset","Status"],"target":"B3"}},
{"id":"cell_c3","a":"writer/document-content","b":"calc/C3","schema":{"headers":["Asset","Region","Status"],"target":"C3"}},
{"id":"cell_d2","a":"writer/document-content","b":"calc/D2","schema":{"headers":["Item","Owner","Region","Status"],"target":"D2"}}],
"F-04":[{"id":"range_b2_c3","a":"calc/B2:C3","b":"writer/document-content","schema":{"range":["B2","C3"],"shape":[2,2],"headers":["Metric","Week 1","Week 2","Guard"]}},
{"id":"range_c2_d3","a":"calc/C2:D3","b":"writer/document-content","schema":{"range":["C2","D3"],"shape":[2,2]}},
{"id":"range_b2_d3","a":"calc/B2:D3","b":"writer/document-content","schema":{"range":["B2","D3"],"shape":[2,3]}},
{"id":"range_b3_c4","a":"calc/B3:C4","b":"writer/document-content","schema":{"range":["B3","C4"],"shape":[2,2]}},
{"id":"range_c3_e4","a":"calc/C3:E4","b":"writer/document-content","schema":{"range":["C3","E4"],"shape":[2,3]}}],
"F-02":[{"id":"anchor_summary","a":"writer/comment-anchor:summary","b":"browser/review/decision","schema":{"anchor_kind":"summary sentence","form_fields":["case","decision"]}},
{"id":"anchor_risk","a":"writer/comment-anchor:risk","b":"browser/review/risk","schema":{"anchor_kind":"risk sentence","form_fields":["risk_id","disposition"]}},
{"id":"anchor_supplier","a":"writer/comment-anchor:supplier","b":"browser/review/vendor","schema":{"anchor_kind":"supplier paragraph","form_fields":["supplier","decision"]}},
{"id":"anchor_budget","a":"writer/comment-anchor:budget","b":"browser/review/allocation","schema":{"anchor_kind":"allocation sentence","form_fields":["request","approval"]}},
{"id":"anchor_action","a":"writer/comment-anchor:action","b":"browser/review/action-item","schema":{"anchor_kind":"action item","form_fields":["owner","status"]}}],
"C-01":[{"id":"writer_note_calc_cell","a":"writer/paragraph[1]","b":"calc/A2","schema":{"payload_kind":"plain note","destination":"single cell"}},
{"id":"writer_record_calc_cell","a":"writer/insertion-after-record","b":"calc/C2","schema":{"payload_kind":"record identifier","destination":"single cell"}},
{"id":"writer_url_calc_cell","a":"writer/insertion-after-reference","b":"calc/B3","schema":{"payload_kind":"plain URL text","destination":"single cell"}},
{"id":"writer_action_calc_cell","a":"writer/insertion-after-action","b":"calc/C3","schema":{"payload_kind":"action phrase","destination":"single cell"}},
{"id":"writer_summary_calc_cell","a":"writer/insertion-before-guard","b":"calc/D2","schema":{"payload_kind":"summary text","destination":"single cell"}}],
"C-03":[{"id":"matrix_2x2","a":"calc/A1:B2","b":"writer/paragraph[1]","schema":{"shape":[2,2],"source_range":"A1:B2","destination_range":"A4:B5","paste_target":"calc_range","writer_target":"paragraph[1]"}},
{"id":"matrix_2x3","a":"calc/A1:C2","b":"writer/paragraph[1]","schema":{"shape":[2,3],"source_range":"A1:C2","destination_range":"A4:C5","paste_target":"calc_range","writer_target":"paragraph[1]"}},
{"id":"matrix_3x2","a":"calc/A1:B3","b":"writer/paragraph[1]","schema":{"shape":[3,2],"source_range":"A1:B3","destination_range":"A4:B6","paste_target":"calc_range","writer_target":"paragraph[1]"}},
{"id":"matrix_3x3","a":"calc/A1:C3","b":"writer/paragraph[1]","schema":{"shape":[3,3],"source_range":"A1:C3","destination_range":"A4:C6","paste_target":"calc_range","writer_target":"paragraph[1]"}},
{"id":"matrix_2x4","a":"calc/A1:D2","b":"writer/paragraph[1]","schema":{"shape":[2,4],"source_range":"A1:D2","destination_range":"A4:D5","paste_target":"calc_range","writer_target":"paragraph[1]"}}],
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
"C-N1":[{"id":"rich_table_2x2","a":"writer/table[0]","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[2,2],"mime":["text/html","text/plain"]}},
{"id":"rich_table_2x3","a":"writer/table[0]","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[2,3],"mime":["text/html","text/plain"]}},
{"id":"rich_table_3x2","a":"writer/table[0]","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[3,2],"mime":["text/html","text/plain"]}},
{"id":"rich_table_3x3","a":"writer/table[0]","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[3,3],"mime":["text/html","text/plain"]}},
{"id":"rich_table_4x2","a":"writer/table[0]","b":"browser/url-submit","schema":{"payload":"HTML table","shape":[4,2],"mime":["text/html","text/plain"]}}],
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

from .second_wave_v1 import SECOND_WAVE as _SECOND_WAVE, profile_rows as _second_wave_profile_rows
_PROFILE_ROWS.update(_second_wave_profile_rows())
from .diversity_context_v1 import enrich_profiles as _enrich_diversity_profiles, apply_context as _apply_diversity_context
_enrich_diversity_profiles(_PROFILE_ROWS)

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

def _writer_table_file(title: str, shape: tuple[int,int], values: list[list[str]] | None = None) -> bytes:
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0";text="urn:oasis:names:tc:opendocument:xmlns:text:1.0";table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    root=ET.Element(f"{{{office}}}document",{f"{{{office}}}version":"1.2"});body=ET.SubElement(root,f"{{{office}}}body");content=ET.SubElement(body,f"{{{office}}}text")
    ET.SubElement(content,f"{{{text}}}p").text=title;grid=ET.SubElement(content,f"{{{table}}}table",{f"{{{table}}}name":"CoDeskDestination"})
    rows,cols=shape;values=values or [[""]*cols for _ in range(rows)]
    for row in values:
        tr=ET.SubElement(grid,f"{{{table}}}table-row")
        for value in row:
            cell=ET.SubElement(tr,f"{{{table}}}table-cell",{f"{{{office}}}value-type":"string"});ET.SubElement(cell,f"{{{text}}}p").text=value
    ET.SubElement(content,f"{{{text}}}p").text="Guard: PRESERVE"
    ET.register_namespace("office",office);ET.register_namespace("text",text);ET.register_namespace("table",table)
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
    if workflow_id in _SECOND_WAVE:
        from .second_wave_v1 import workflow_row as _second_workflow_row
        return _second_workflow_row(workflow_id)
    common={
      "F-01":("focus_input_routing",["Writer","Calc"],"writer_full_document_vs_calc_cell","Replace the complete Writer document content and change one distinct Calc cell.","Replace all Writer document content with the assigned decision and save.","Set the assigned Calc field and preserve the remaining table.","qwen_mechanism_evidence"),
      "F-04":("focus_input_routing",["Calc","Writer"],"calc_range_vs_writer_document","Fill an assigned Calc rectangle and edit a Writer paragraph.","Fill the assigned spreadsheet range.","Replace the assigned Writer paragraph.","scripted_full"),
      "F-02":("focus_input_routing",["Writer","Browser"],"writer_comment_vs_browser_form","Add an anchored Writer review comment while a Browser review form is completed.","Attach the assigned note to the target review anchor.","Submit the independent review form exactly once.","scripted_full"),
      "C-01":("clipboard_state",["Writer","Calc"],"plain_text_transfer","Transfer plain text from independent sources to Writer and Calc destinations.","Paste the assigned note into the Writer destination.","Paste the assigned identifier into the Calc destination.","qwen_smoke"),
      "C-03":("clipboard_state",["Calc","Writer"],"calc_range_and_writer_paragraph_copy","Copy a Calc rectangle to a Calc destination while duplicating a Writer paragraph.","Copy the assigned Calc source rectangle to its Calc destination without changing the source or guards.","Copy Writer paragraph 1 into the blank paragraph 2.","scripted_full"),
      "C-02":("clipboard_state",["Writer","Browser"],"semantic_hyperlink_transfer","Create a semantic hyperlink in Writer while an independent Browser URL is submitted.","Create a link with the exact label and href.","Submit the assigned Browser URL exactly once.","scripted_full"),
      "A-01":("application_context",["Browser","Browser"],"two_tab_context","Submit independent forms in two Browser tabs.","Submit the target value in tab A.","Submit the other target value in tab B.","qwen_mechanism_evidence"),
      "A-02":("selection_active_object",["Browser","Browser"],"selected_record_context","Update two distinct selected Browser records.","Update record A only.","Update record B only.","scripted_full"),
      "S-01":("selection_active_object",["Calc","Calc"],"active_cell_selection","Write two separate Calc cells through selected-cell state.","Set the selected cell A target.","Set the selected cell B target.","qwen_smoke"),
      "U-01":("undo_redo_history",["Calc","Calc"],"calc_document_history","Undo A's temporary edit after B has independently edited the same Calc document.","Undo the temporary value and restore the seeded cell.","Set B's distinct Calc cell to its goal.","qwen_smoke"),
      "F-N1":("focus_input_routing",["Writer","Writer"],"two_writer_windows","Edit distinct Writer documents through two top-level windows.","Replace the assigned paragraph in doc-A.","Replace the assigned paragraph in doc-B.","guest_solo"),
      "C-N1":("clipboard_state",["Writer","Browser"],"rich_html_table_transfer","Transfer a Browser HTML table into a Writer table while an independent Browser URL is copied and submitted.","Copy the Browser HTML table into the assigned Writer table, preserving exact rows and cells.","Copy the assigned Browser URL and submit it exactly once.","offline"),
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
    if row["workflow_id"]=="C-01":
        index=2 if layout["guard_placement"]=="leading" else 1
        return {"A":[f"writer/paragraph[{index}]"],"B":[profile["b"]]}
    if row["workflow_id"]=="C-N1":
        return {"A":[profile["a"]],"B":[profile["b"]]}
    if row["workflow_id"]=="C-03":
        r,c=profile["schema"]["shape"]
        return {"A":[f"calc/{profile['schema']['destination_range']}"],"B":[f"writer/{profile['schema']['writer_target']}"]}
    if row["workflow_id"]=="C-02":
        index=1 if layout["guard_placement"]=="leading" else 0
        return {"A":[f"writer/hyperlink-paragraph[{index}]"],"B":[profile["b"]]}
    return {"A":[profile["a"]],"B":[profile["b"]]}

def _semantic_values(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                      layout: dict[str,Any]) -> tuple[str,str,str,str]:
    if workflow_id in _SECOND_WAVE:
        from .second_wave_v1 import semantic_values as _second_semantic_values
        return _second_semantic_values(workflow_id, domain, profile, layout)
    label=profile["schema"].get("target",profile["schema"].get("selection",profile["schema"].get("payload",profile["schema"].get("object_type","object"))))
    a_initial=f"Draft: {domain['entity']}"
    b_initial=f"Pending: {domain['entity']}"
    a_final=f"{domain['a_status']}: {domain['entity']} ({label})"
    b_final=f"{domain['b_status']}: {domain['entity']} ({label})"
    if workflow_id=="A-01":
        if domain["id"]=="capital_allocation" and profile["id"]=="tabs_review_cases" and layout["id"]=="guard_after":
            return "","", "CTX-A-04100","CTX-B-08200"
        return "","",f"{domain['a_status']}-{domain['source']}",f"{domain['b_status']}-{domain['source']}"
    if workflow_id=="A-02":
        return "","", "REC-A-4100","REC-B-8200"
    if workflow_id=="A-N1":
        return "","",f"ROUTE-A-{domain['source'].split('-')[-1]}",f"ROUTE-B-{domain['source'].split('-')[-1]}"
    if workflow_id=="S-01":
        if domain["id"]=="capital_allocation" and profile["id"]=="cells_b2_c3":
            return "B2 seed","C3 seed","A-7319","B-2042"
        return f"{profile['schema']['object_type']} seed A",f"{profile['schema']['object_type']} seed B",f"A-{domain['source'].split('-')[-1]}",f"B-{domain['source'].split('-')[-1]}"
    if workflow_id=="S-N1":
        return "normal","normal","bold","bold"
    if workflow_id=="U-01":
        return "B2 seed","C3 seed","A-TEMP", "B-2042"
    if workflow_id=="U-N1":
        return "Seed A","Seed B","TEMP-A", "FINAL-B"
    if workflow_id=="C-N1":
        rows,cols=profile["schema"]["shape"]
        matrix=[[f"{domain['entity']} {r+1}.{c+1}" for c in range(cols)] for r in range(rows)]
        url=f"https://example.org/codesk/{domain['id']}/{domain['source']}"
        return "__EMPTY_TABLE__","__UNSUBMITTED__",json.dumps(matrix,separators=(",",":"),ensure_ascii=False),url
    if workflow_id=="C-03":
        rows,cols=profile["schema"]["shape"]
        if domain["id"]=="capital_allocation" and profile["id"]=="matrix_2x2":
            values=[["Q1","Q2"],["17","29"]];note="NOTE-571"
        else:
            values=[[f"{domain['a_status']}-{r+1}{c+1}" for c in range(cols)] for r in range(rows)]
            note=f"NOTE-{domain['source'].split('-')[-1]}"
        return "__EMPTY_RANGE__","",json.dumps(values,separators=(",",":")),note
    if workflow_id=="F-02":
        anchor=f"{domain['field_a']} for {domain['entity']}"
        case=f"CASE-{domain['source'].split('-')[-1]}"
        decision=domain["a_status"].upper()
        comment="Review note 482"
        if domain["id"]=="capital_allocation" and profile["id"]=="anchor_summary" and layout["id"]=="guard_after":
            anchor="Review anchor"; case="CASE-901"; decision="APPROVE"
        a_state={"anchor":anchor,"comment":comment}
        b_state={"case":case,"decision":decision}
        return anchor,"__UNSUBMITTED__",json.dumps(a_state,sort_keys=True,separators=(",",":")),json.dumps(b_state,sort_keys=True,separators=(",",":"))
    if workflow_id=="C-02":
        href=f"https://example.org/{domain['id']}/{profile['id']}"
        label=f"Open {domain['entity']} reference"
        destination=f"https://example.org/{domain['id']}/submit"
        if domain["id"]=="capital_allocation" and profile["id"]=="href_reference" and layout["id"]=="guard_after":
            label="Reference link"; href="https://example.org/codesk/reference-a"; destination="https://example.org/codesk/reference-b"
        return label,"",json.dumps({"text":label,"href":href},sort_keys=True,separators=(",",":")),destination
    if workflow_id=="C-01":
        a_source="REF-7319" if domain["id"]=="capital_allocation" else domain["source"]
        b_source="BATCH-204" if domain["id"]=="capital_allocation" else domain["b_status"].upper()+"-"+domain["source"].split("-")[-1]
        return "INSERT COPIED VALUE","__EMPTY_CELL__",a_source,b_source
    return a_initial,b_initial,a_final,b_final

def _a01_server_source(state_path: str, events_path: str) -> bytes:
    source=r"""from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path(__STATE__); EVENTS=Path(__EVENTS__)
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path=="/state":
   s=json.loads(STATE.read_text());s["events"]=EVENTS.read_text().splitlines() if EVENTS.exists() else []
   return self.reply(s)
  tab="tab-a" if self.path=="/actor-a" else "tab-b" if self.path=="/actor-b" else None
  if not tab:return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk "+tab+"</title>"
   "<style>body{font:22px Arial;margin:32px}input,button{font:22px Arial;padding:8px;margin:12px}</style>"
   "<h1>"+tab+"</h1><p>Complete the independent "+tab+" record.</p>"
   "<input id=value aria-label='Goal value'><button id=submit>Submit</button><output id=result></output>"
   "<script>const tab='"+tab+"';"
   "async function context(){await fetch('/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tab})})}"
   "document.addEventListener('visibilitychange',()=>{if(!document.hidden)context()});context();"
   "document.querySelector('#submit').onclick=async()=>{let value=document.querySelector('#value').value;"
   "await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tab,value})});"
   "document.querySelector('#result').textContent='Saved';};</script>")
  b=html.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b);event({"kind":"tab_page_loaded","tab":tab})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text())
  if self.path=="/context":
   tab=p.get("tab")
   if tab not in s["tabs"]:return self.reply({"error":"bad tab"},400)
   before=s["active_tab"];s["active_tab"]=tab;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"active_tab_changed","before":before,"after":tab});return self.reply({"ok":True})
  if self.path!="/submit":return self.reply({"error":"not found"},404)
  tab=p.get("tab")
  if tab not in s["tabs"]:return self.reply({"error":"bad tab"},400)
  s["active_tab"]=tab;s["tabs"][tab]["goal"]=str(p.get("value",""));s["tabs"][tab]["revision"]+=1
  STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"form_submitted","tab":tab,"revision":s["tabs"][tab]["revision"],"value":p.get("value")});return self.reply({"ok":True})
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8766),H).serve_forever()
"""
    return source.replace("__STATE__",repr(state_path)).replace("__EVENTS__",repr(events_path)).encode()

def _s_n1_fodt(title: str, range_a: str, range_b: str) -> bytes:
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
    fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
    root=ET.Element(f"{{{office}}}document-content",{f"{{{office}}}version":"1.3"})
    automatic=ET.SubElement(root,f"{{{office}}}automatic-styles")
    for name,weight in (("RangeA","normal"),("RangeB","normal"),("BoldA","bold"),("BoldB","bold")):
        st=ET.SubElement(automatic,f"{{{style}}}style",{f"{{{style}}}name":name,f"{{{style}}}family":"text"})
        ET.SubElement(st,f"{{{style}}}text-properties",{f"{{{fo}}}font-weight":weight})
    body=ET.SubElement(root,f"{{{office}}}body");doc=ET.SubElement(body,f"{{{office}}}text")
    h=ET.SubElement(doc,f"{{{text}}}p");h.text=title
    p=ET.SubElement(doc,f"{{{text}}}p")
    a=ET.SubElement(p,f"{{{text}}}span",{f"{{{text}}}style-name":"RangeA"});a.text=range_a
    gap=ET.SubElement(p,f"{{{text}}}span");gap.text=" | "
    b=ET.SubElement(p,f"{{{text}}}span",{f"{{{text}}}style-name":"RangeB"});b.text=range_b
    guard=ET.SubElement(doc,f"{{{text}}}p");guard.text="Guard: PRESERVE"
    for prefix,uri in (("office",office),("text",text),("style",style),("fo",fo)):ET.register_namespace(prefix,uri)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")


def _a02_server_source(state_path: str, events_path: str) -> bytes:
    source=r"""from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path(__STATE__);EVENTS=Path(__EVENTS__)
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path!="/workspace":return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk record workspace</title>"
   "<style>body{font:20px Arial;margin:24px}button,input{font:20px Arial;padding:8px;margin:8px}</style>"
   "<h1>Record workspace</h1><p>Record A and Record B have separate goal fields.</p>"
   "<button id=record-a>Record A</button><button id=record-b>Record B</button>"
   "<input id=value autocomplete=off><button id=save>Save selected</button><output id=result></output>"
   "<script>let selected='record-a';const drafts={'record-a':'','record-b':''};"
   "document.querySelector('#value').addEventListener('input',e=>{drafts[selected]=e.target.value});"
   "async function selectRecord(r){selected=r;document.querySelector('#value').value=drafts[r];"
   "await fetch('/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:r})})}"
   "document.querySelector('#record-a').onclick=()=>selectRecord('record-a');"
   "document.querySelector('#record-b').onclick=()=>selectRecord('record-b');"
   "document.querySelector('#save').onclick=async()=>{let value=document.querySelector('#value').value;"
   "let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record:selected,value})});"
   "document.querySelector('#result').textContent=r.ok?'Saved':'Rejected'};</script>")
  self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(html)));self.end_headers();self.wfile.write(html.encode());event({"kind":"page_loaded"})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());r=p.get("record")
  if r not in ("record-a","record-b"):return self.reply({"error":"bad record"},400)
  if self.path=="/select":
   before=s["selected_record"];s["selected_record"]=r;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"record_selected","before":before,"record":r});return self.reply({"ok":True})
  if self.path=="/save":
   if s["selected_record"]!=r:return self.reply({"error":"selection changed"},409)
   s["records"][r]["goal"]=str(p.get("value",""));s["records"][r]["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"record_saved","record":r,"revision":s["records"][r]["revision"]});return self.reply({"ok":True})
  return self.reply({"error":"not found"},404)
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8767),H).serve_forever()
"""
    return source.replace("__STATE__",repr(state_path)).replace("__EVENTS__",repr(events_path)).encode()


def _an1_server_source(state_path: str, events_path: str) -> bytes:
    source=r"""from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from datetime import datetime,timezone
import json
STATE=Path(__STATE__);EVENTS=Path(__EVENTS__)
def event(x):
 x["utc"]=datetime.now(timezone.utc).isoformat()
 with EVENTS.open("a") as f:f.write(json.dumps(x,sort_keys=True)+"\n")
class H(BaseHTTPRequestHandler):
 def reply(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=="/health":return self.reply({"ok":True})
  if self.path.split("#",1)[0]!="/workspace":return self.reply({"error":"not found"},404)
  html=("<!doctype html><meta charset='utf-8'><title>CoDesk route workspace</title>"
   "<style>body{font:22px Arial;margin:30px}button,input{font:22px Arial;padding:8px;margin:8px}</style>"
   "<h1>Route workspace</h1><button id=a>Route A</button><button id=b>Route B</button>"
   "<p id=label>Route A</p><input id=value><button id=save>Submit route value</button><output id=result></output>"
   "<script>let route='route-a';const vals={'route-a':'','route-b':''};"
   "function selectRoute(r){route=r;history.pushState({},'', '/workspace#'+r);document.querySelector('#label').textContent=r;"
   "document.querySelector('#value').value=vals[r];fetch('/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route:r})})}"
   "document.querySelector('#a').onclick=()=>selectRoute('route-a');document.querySelector('#b').onclick=()=>selectRoute('route-b');"
   "document.querySelector('#value').addEventListener('input',e=>vals[route]=e.target.value);"
   "document.querySelector('#save').onclick=async()=>{await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route,value:document.querySelector('#value').value})});document.querySelector('#result').textContent='Saved'};</script>")
  self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(html)));self.end_headers();self.wfile.write(html.encode());event({"kind":"page_loaded"})
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))));s=json.loads(STATE.read_text());route=p.get("route")
  if route not in ("route-a","route-b"):return self.reply({"error":"bad route"},400)
  if self.path=="/context":
   before=s["active_route"];s["active_route"]=route;s["tab_hash"]="/workspace#"+route;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"route_changed","before":before,"after":route});return self.reply({"ok":True})
  if self.path=="/submit":
   s["active_route"]=route;s["routes"][route]["value"]=str(p.get("value",""));s["routes"][route]["revision"]+=1;STATE.write_text(json.dumps(s,sort_keys=True));event({"kind":"route_submitted","route":route,"revision":s["routes"][route]["revision"]});return self.reply({"ok":True})
  return self.reply({"error":"not found"},404)
 def log_message(self,*args):pass
HTTPServer(("127.0.0.1",8770),H).serve_forever()
"""
    return source.replace("__STATE__",repr(state_path)).replace("__EVENTS__",repr(events_path)).encode()


def _fixture_bytes(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                   layout: dict[str,Any], a_initial: str, b_initial: str,
                   a_final: str, b_final: str, instance_id: str) -> dict[str,bytes]:
    if workflow_id in _SECOND_WAVE:
        from .second_wave_v1 import fixture_bytes as _second_fixture_bytes
        return _second_fixture_bytes(workflow_id, domain, profile, layout, a_initial, b_initial, a_final, b_final, instance_id,
            xml_file=_xml_file, html_file=_html, writer_table_file=_writer_table_file, range_cells=_range_cells, cell_coord=_cell_coord)
    schema=profile["schema"]
    assets:dict[str,bytes]={}
    if "Writer" in _workflow_row(workflow_id)["task_domains"]:
        if workflow_id=="C-N1":
            shape=tuple(schema["shape"])
            assets["document.fodt"]=_writer_table_file(domain["title"],shape)
        elif workflow_id=="F-N1":
            paras=[domain["title"],a_initial,"Guard: A-KEEP"]
            paras_b=[domain["title"],b_initial,"Guard: B-KEEP"]
            if layout["guard_placement"]=="leading":
                paras=["Guard: A-KEEP",domain["title"],a_initial]; paras_b=["Guard: B-KEEP",domain["title"],b_initial]
            assets["doc-a.fodt"]=_xml_file("writer",paras)
            assets["doc-b.fodt"]=_xml_file("writer",paras_b)
        else:
            p=[domain["title"],a_initial,b_initial,"Guard: PRESERVE"]
            if workflow_id=="C-01":
                p=[a_final,a_initial]
                if layout["guard_placement"]=="leading":
                    p=["Guard: PRESERVE",a_final,a_initial]
            if workflow_id=="C-03":
                p=[b_final,""]
                if layout["guard_placement"]=="leading":p=["Guard: PRESERVE",b_final,""]

            if workflow_id=="F-04":
                p=[b_initial]
            if layout["guard_placement"]=="leading" and workflow_id not in {"C-01","C-02","F-02"}: p=["Guard: PRESERVE",domain["title"],a_initial,b_initial]
            if workflow_id=="F-01":
                # Historical CODESK-TA-OFFICE-001 replaces the whole Writer document.
                p=[a_initial]
            elif workflow_id=="F-04":
                p=[b_initial]
            elif workflow_id=="C-02":
                p=[a_initial,"Guard paragraph"]
            elif workflow_id=="F-02":
                p=[a_initial,"Guard paragraph"]
                if layout["guard_placement"]=="leading": p=["Guard paragraph",a_initial]
                if layout["guard_placement"]=="leading":
                    p=["Guard paragraph",a_initial]
            if workflow_id=="S-N1":
                p=[domain["title"],f"ALPHA {domain['entity']} | BETA {domain['entity']}","Guard: PRESERVE"]
                if layout["guard_placement"]=="leading": p=["Guard: PRESERVE",domain["title"],f"ALPHA {domain['entity']} | BETA {domain['entity']}"]
            elif workflow_id=="U-N1":
                p=[a_initial,b_initial,"Guard: PRESERVE"]
                if layout["guard_placement"]=="leading": p=["Guard: PRESERVE",a_initial,b_initial]
            if workflow_id=="S-N1":
                texts={"range_word_pair":("ALPHA","BETA"),"range_phrase_pair":("ALPHA PHRASE","BETA PHRASE"),
                    "range_sentence_pair":("Alpha sentence one.","Beta sentence two."),
                    "range_list_item_pair":("Alpha list item","Beta list item"),
                    "range_heading_pair":("Alpha heading","Beta heading")}
                ta,tb=texts[profile["id"]]
                assets["document.fodt"]=_s_n1_fodt(domain["title"],ta,tb)
            else:
                assets["document.fodt"]=_xml_file("writer",p)
    if "Calc" in _workflow_row(workflow_id)["task_domains"]:
        headers=schema.get("headers") or [domain["field_a"],domain["field_b"]]
        rows=[list(headers)]
        ncols=max(2,len(headers))
        nrows=5
        if workflow_id=="F-01" and domain["id"]=="capital_allocation" and profile["id"]=="cell_b2" and layout["id"]=="guard_after":
            rows=[["Record","Status"],["Quarterly","Draft"]]
            ncols=2; nrows=2
        if workflow_id=="F-04" and domain["id"]=="capital_allocation" and profile["id"]=="range_b2_c3" and layout["id"]=="guard_after":
            rows=[["Metric","Week 1","Week 2","Guard"],["North","","","Keep-N"],
                  ["South","","","Keep-S"],["Sentinel","Safe","",""]]
            ncols=4; nrows=4
        canonical_f01_calc = workflow_id=="F-01" and domain["id"]=="capital_allocation" and profile["id"]=="cell_b2" and layout["id"]=="guard_after"
        canonical_f04_calc = workflow_id=="F-04" and domain["id"]=="capital_allocation" and profile["id"]=="range_b2_c3" and layout["id"]=="guard_after"
        if not canonical_f01_calc and not canonical_f04_calc:
            for ri in range(1,nrows):
                rows.append([f"{domain['entity']} {ri}"]+["Draft"]*(ncols-1))
        if workflow_id=="C-01":
            rows=[["BATCH-204"]]
            ncols=1; nrows=1
        if workflow_id=="C-03":
            shape=schema["shape"];rr,cc=shape
            ncols=max(3,cc);nrows=max(5,rr+3)
            rows=[[""]*ncols for _ in range(nrows)]
            matrix=json.loads(a_final)
            for i in range(rr):rows[i][:cc]=matrix[i]
            if domain["id"]=="capital_allocation" and profile["id"]=="matrix_2x2":
                rows[0][:2]=["Q1","Q2"];rows[1][:2]=["17","29"];rows[2][0]="Guard-R3"
                rows[0][2]="Guard";rows[1][2]="Keep-2";rows[3][2]="Keep-4";rows[4][2]="Keep-5"
            elif cc<ncols:
                rows[0][cc]="Guard";rows[1][cc]="Keep-2";rows[3][cc]="Keep-4";rows[4][cc]="Keep-5"
            if rr>2:
                for i in range(2,rr):rows[i][cc if cc<ncols else 0]=f"Guard-R{i+1}"

        if workflow_id=="S-01" and domain["id"]=="capital_allocation" and profile["id"]=="cells_b2_c3":
            rows=[["Name","Target A","Unused"],["Row2","B2 seed","Unused"],["Row3","Unused","C3 seed"]]
            ncols=3;nrows=3
        for target in (profile["a"],profile["b"]):
            target_for_file = profile["b"] if workflow_id=="C-01" else target
            if workflow_id=="C-03":
                continue
            if target_for_file.startswith("calc/"):
                try:
                    cell_ref=target_for_file.split("/")[-1]
                    for cell_idx,cell in enumerate(_range_cells(cell_ref)):
                        r,c=_cell_coord(cell)
                        while len(rows)<=r: rows.append([""]*ncols)
                        while len(rows[r])<=c: rows[r].append("")
                        rows[r][c]=("" if workflow_id=="F-04" and target==profile["a"] or workflow_id=="C-01" else
                                    a_initial if target==profile["a"] else b_initial)
                except Exception: raise
        calc_bytes=_xml_file("calc",rows=rows)
        if workflow_id=="C-03":
            root=ET.fromstring(calc_bytes)
            tns="urn:oasis:names:tc:opendocument:xmlns:table:1.0";xns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
            for cell in root.iter(f"{{{tns}}}table-cell"):
                paras=list(cell.findall(f"{{{xns}}}p"))
                if paras and all(not "".join(x.itertext()) for x in paras):cell.clear()
            calc_bytes=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(root,encoding="utf-8")
        assets["workbook.fods"]=calc_bytes
    if "Browser" in _workflow_row(workflow_id)["task_domains"]:
        elements=[]
        if workflow_id=="C-N1":
            r,c=schema["shape"]
            table="<table id='source-table' data-object='rich-payload'><tbody>"+"".join(
                "<tr>"+"".join(f"<td><strong>{domain['entity']} {ri+1}.{ci+1}</strong></td>" for ci in range(c))+"</tr>" for ri in range(r))+"</tbody></table>"
            elements.extend([table,f"<p id='source-url'>{b_final}</p>",
                "<form id='url-form'><input id='url' aria-label='URL destination'><button>Submit URL</button></form>",
                "<script>document.querySelector('#url-form').addEventListener('submit',async e=>{e.preventDefault();let r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.querySelector('#url').value})});document.querySelector('#result').textContent=r.ok?'Submitted':'Rejected'});</script>","<output id='result'></output>"])
        elif workflow_id=="C-02":
            href=json.loads(a_final)["href"]
            elements.extend([f"<a id='source-a' href='{href}'>{a_initial}</a>",
                f"<p id='source-b'>Destination URL: {b_final}</p>",
                "<form id='submit-form'><input id='value' aria-label='URL destination'><button>Submit URL</button></form>",
                "<script>document.querySelector('#submit-form').addEventListener('submit',async e=>{e.preventDefault();await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.querySelector('#value').value})});});</script>"])
        elif workflow_id=="A-01":
            elements.append("<p>CoDesk Application Context task: use the two local Browser routes.</p>")
        elif workflow_id=="A-02":
            elements.extend(["<button data-record='A'>Record A</button>","<button data-record='B'>Record B</button>",
                "<input id='value'><button id='save'>Save selected</button>"])
        elif workflow_id=="A-N1":
            elements.extend(["<button data-route='A'>Open A</button>","<button data-route='B'>Open B</button>",
                             f"<input data-route-field='{schema.get('field','resolution')}'>"])
        elif workflow_id=="F-02":
            task=json.loads(b_final)
            elements.extend([f"<h2>Review {task['case']}</h2>",
                f"<label>Case<input id='case' value='{task['case']}'></label>",
                f"<label>Decision<input id='decision' value='{task['decision']}'></label>",
                "<button id='submit'>Submit review</button>",
                "<script>document.querySelector('#submit').onclick=async()=>{await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({case:document.querySelector('#case').value,decision:document.querySelector('#decision').value})})}</script>"])
        else:
            elements.append(f"<form data-object='{profile['b']}'><label>{domain['field_b']}<input id='value'></label><button>Submit</button></form>")
        page_title=("CoDesk C-02 hyperlink transfer" if workflow_id=="C-02" else domain["title"])
        assets["workspace.html"]=_html(page_title,elements,layout["fixture_layout"])
        if workflow_id=="A-01":
            initial_browser={"window_id":None,"active_tab":"tab-a","tabs":{
                "tab-a":{"url":"/actor-a","goal":"","revision":0},
                "tab-b":{"url":"/actor-b","goal":"","revision":0}}}
            assets["browser-server.py"]=_a01_server_source(
                "/home/oem/codesk/"+instance_id+"/browser-initial-state.json",
                "/home/oem/codesk/"+instance_id+"/browser-events.jsonl")
            assets["browser-events.jsonl"]=b""
        elif workflow_id=="A-02":
            initial_browser={"selected_record":"record-a","records":{
                "record-a":{"goal":"","revision":0},"record-b":{"goal":"","revision":0}}}
            assets["browser-server.py"]=_a02_server_source(
                "/home/oem/codesk/"+instance_id+"/browser-initial-state.json",
                "/home/oem/codesk/"+instance_id+"/browser-events.jsonl")
            assets["browser-events.jsonl"]=b""
        elif workflow_id=="A-N1":
            initial_browser={"window_id":None,"active_route":"route-a","tab_hash":"/workspace#route-a",
                "routes":{"route-a":{"value":"","revision":0},"route-b":{"value":"","revision":0}}}
            assets["browser-server.py"]=_an1_server_source(
                "/home/oem/codesk/"+instance_id+"/browser-initial-state.json",
                "/home/oem/codesk/"+instance_id+"/browser-events.jsonl")
            assets["browser-events.jsonl"]=b""
        elif workflow_id=="C-N1":
            initial_browser={"submission":{},"revision":0,"expected_url":b_final}
            assets["browser-events.jsonl"]=b""
        elif workflow_id in {"C-02","F-02"}:
            initial_browser={"submission":{},"revision":0}
        else:
            initial_browser={"domain":domain["id"],"records":{"A":a_initial,"B":b_initial},"routes":{"A":"initial","B":"initial"},"submissions":{}}
        assets["browser-initial-state.json"]=(json.dumps(initial_browser,sort_keys=True)+"\n").encode()
    if not assets:
        assets["task-state.json"]=(json.dumps({"domain":domain["id"],"initial_a":a_initial,"initial_b":b_initial},sort_keys=True)+"\n").encode()
    return assets

def _source_digest() -> str:
    helper=Path(__file__).with_name("diversity_context_v1.py")
    return sha256(Path(__file__).read_bytes()+helper.read_bytes())

def build_instance(workflow_id: str, domain: dict[str,Any], profile: dict[str,Any],
                   layout: dict[str,Any], generation_seed: int, root: Path) -> InstanceSpecV1:
    row=_workflow_row(workflow_id)
    a0,b0,a1,b1=_semantic_values(workflow_id,domain,profile,layout)
    canonical_f01 = workflow_id=="F-01" and domain["id"]=="capital_allocation" and profile["id"]=="cell_b2" and layout["id"]=="guard_after"
    if canonical_f01:
        a0,b0,a1,b1="Quarterly status report","Draft","Approved by GUI actor","Approved"
    canonical_f04 = workflow_id=="F-04" and domain["id"]=="capital_allocation" and profile["id"]=="range_b2_c3" and layout["id"]=="guard_after"
    if canonical_f04:
        b0,b1="Review summary: Draft","Review summary: Final"
    target_objects=_targets(row,profile,layout)
    if len(set(target_objects["A"]+target_objects["B"])) != 2:
        raise ValueError(f"actor target overlap in {workflow_id}/{profile['id']}")
    if (a0==a1 and workflow_id!="U-01") or b0==b1: raise ValueError("no-op actor goal")
    semantic={"workflow_id":workflow_id,"operation_graph":row["operation_graph"],
              "operation_schema_revision": {"F-01":4,"F-04":4,"C-01":4,"C-02":3,"F-02":3,"A-01":2,"U-01":2,"C-03":3,"U-N1":1,"C-N1":2}.get(workflow_id,1),
              "domain_id":domain["id"],"object_profile_id":profile["id"],
              "object_schema":profile["schema"],"state_context":profile["schema"].get("state_context"),"layout_id":layout["id"],
              "domain_schema":{k:domain[k] for k in ("entity","field_a","field_b")}}
    semantic_sig=sha256(canonical_bytes(semantic))
    instance_id=f"cdv1-{workflow_id.lower().replace('-','')}-{semantic_sig[:16]}"
    matrix_expected = None
    if workflow_id=="C-01":
        canonical_c01 = domain["id"]=="capital_allocation" and profile["id"]=="writer_note_calc_cell" and layout["id"]=="guard_after"
        if canonical_c01:
            a0,b0,a1,b1="INSERT COPIED VALUE","__EMPTY_CELL__","REF-7319","BATCH-204"
    if workflow_id=="A-01":
        a0="";b0=""
    if workflow_id=="F-02":
        if domain["id"]=="capital_allocation" and profile["id"]=="anchor_summary" and layout["id"]=="guard_after":
            a0="Review anchor";b0="__UNSUBMITTED__"
            a1=json.dumps({"anchor":"Review anchor","comment":"Review note 482"},sort_keys=True,separators=(",",":"))
            b1=json.dumps({"case":"CASE-901","decision":"APPROVE"},sort_keys=True,separators=(",",":"))
    if workflow_id=="C-02":
        if domain["id"]=="capital_allocation" and profile["id"]=="href_reference" and layout["id"]=="guard_after":
            a0="Reference link"; b0=""
            a1=json.dumps({"text":"Reference link","href":"https://example.org/codesk/reference-a"},sort_keys=True,separators=(",",":"))
            b1="https://example.org/codesk/reference-b"
    if workflow_id=="F-04":
        r0,c0=_cell_coord(profile["schema"]["range"][0])
        r1,c1=_cell_coord(profile["schema"]["range"][1])
        rows,cols=r1-r0+1,c1-c0+1
        if profile["id"]=="range_b2_c3":
            matrix_expected=[["11","12"],["21","22"]]
        else:
            matrix_expected=[[f"{domain['a_status']}-{r+1}{c+1}" for c in range(cols)] for r in range(rows)]
        a0="__EMPTY_RANGE__"
        a1=json.dumps(matrix_expected,separators=(",",":"))
    initial={"actors":{"A":{"value":a0,"object":target_objects["A"][0]},
                       "B":{"value":b0,"object":target_objects["B"][0]},
                       "guards":{"main":"PRESERVE"}},
             "treatment":{"resource":row["family"],"initial":profile["schema"],"context_profile":profile["schema"].get("state_context")}}
    expected=json.loads(json.dumps(initial))
    expected["actors"]["A"]["value"]=a0 if workflow_id in {"U-01","U-N1","U-02"} else a1
    expected["actors"]["B"]["value"]=b1
    goal_a=row["goal_a"]
    goal_b=row["goal_b"]
    if workflow_id in _SECOND_WAVE:
        goal_a += f" Target {target_objects['A'][0]}; initial {a0!r}; required final {a1!r}."
        goal_b += f" Target {target_objects['B'][0]}; initial {b0!r}; required final {b1!r}."
        for _actor_id,_domain,_target,_value in (("A",row["task_domains"][0],target_objects["A"][0],a1),("B",row["task_domains"][1],target_objects["B"][0],b1)):
            if _domain=="Terminal":
                _path=f"/home/oem/codesk/{instance_id}/terminal-result-{_actor_id}.txt"
                if _actor_id=="A": goal_a += f" Run the command and write exactly {_value!r} to {_path}."
                else: goal_b += f" Run the command and write exactly {_value!r} to {_path}."
        if workflow_id=="C-04": goal_a=f"Create a Calc hyperlink in {target_objects['A'][0]} with the assigned Browser URL and exact visible label {domain['entity']}."
        if workflow_id=="C-05": goal_a=f"Copy Calc range {profile['schema']['source_range']} into the Writer destination table with exact rows/cells."
    op_a=f"{profile['schema'].get('action','update')} {target_objects['A'][0]}"
    if workflow_id=="U-01":
        goal_a=f"Temporarily set Calc {profile['a'].split('/')[-1]} to {a1}; after Actor B's edit, use Undo so this cell returns to {a0}."
        goal_b=f"Set Calc {profile['b'].split('/')[-1]} to {b1} and save."
        op_a="temporary value edit followed by an Undo after Actor B's committed edit"
    if workflow_id=="U-N1":
        index=int(profile["a"].split("[")[-1].split("]")[0])
        goal_a=f"Temporarily replace Writer paragraph {index+1} with {a1}; after Actor B edits their paragraph, use Undo to restore the original text {a0}."
        goal_b=f"Replace Writer paragraph {profile['b'].split('[')[-1].split(']')[0]} with {b1} and save."
        op_a="temporary Writer paragraph replacement followed by Undo after Actor B's committed edit"
    if workflow_id=="U-02":
        goal_a=f"Apply the temporary style {a1} to the assigned range. After Actor B's independent paragraph edit, use Undo once, then verify your range is back to its seeded unstyled state {a0}."
        goal_b=f"Insert {b1} into the assigned Writer paragraph; after Actor A's Undo, re-observe and restore the paragraph if it was reverted."
        op_a="temporary Writer character style followed by cross-actor Undo"
        op_b="Writer text insertion followed by post-Undo recovery"
    if workflow_id=="U-03":
        goal_a=f"Enter the assigned formula {a1} in {target_objects['A'][0]}. After Actor B commits, use Undo once to expose the shared history effect; preserve your formula."
        goal_b=f"Commit {b1} in {target_objects['B'][0]}; after Actor A's Undo, re-observe and restore the value if it was reverted."
        op_a="temporary Calc formula edit followed by peer-history Undo"
        op_b="Calc value edit followed by post-Undo recovery"
    if workflow_id=="U-04":
        goal_a=f"Insert {a1} into the shared editor. After Actor B's edit, use Undo once and restore both assigned phrases so {a1} and {b1} are present."
        goal_b=f"Insert {b1} into the shared editor after Actor A's first edit and preserve both phrases."
        op_a="temporary rich-text insertion, cross-actor Undo, then restoration"
        op_b="rich-text insertion into shared editor history"
    if workflow_id=="A-01":
        goal_a=f"Submit {a1} in Browser tab A (/actor-a)."
        goal_b=f"Submit {b1} in Browser tab B (/actor-b)."
        op_a="submit exact goal in active tab A"
    if workflow_id=="F-02":
        goal_a=f"Attach the exact comment {json.loads(a1)['comment']} to the Writer anchor {a0}; preserve the document text and guard."
        goal_b=f"Fill the Browser case {json.loads(b1)['case']} and decision {json.loads(b1)['decision']} and submit exactly once."
        op_a="attach comment to exact Writer anchor without changing visible text"
    if workflow_id=="C-02":
        goal_a=f"Copy the Browser link labeled {a0} into the Writer label with its exact destination; preserve the guard and save."
        goal_b=f"Submit the Browser destination URL {b1} exactly once."
        op_a="copy Browser hyperlink object and paste into Writer label"
    if workflow_id=="C-01":
        goal_a=f"Copy Writer source {a1} into the destination placeholder paragraph and save."
        goal_b=f"Copy Calc A1 value {b1} into {target_objects['B'][0].split('/')[-1]} and save."
        op_a="copy Writer source paragraph and paste into the assigned destination paragraph"
    if workflow_id=="C-N1":
        goal_a=f"Copy the {profile['schema']['shape'][0]} by {profile['schema']['shape'][1]} HTML table from the Browser page into the Writer destination table and preserve exact row/cell structure."
        goal_b=f"Copy the Browser URL {b1} into the URL field and submit it exactly once."
        op_a="copy Browser HTML table and paste as a structured Writer table"
        op_b="copy Browser URL text and submit exact value"
    if workflow_id=="C-03":
        rows,cols=profile["schema"]["shape"];source_end=f"{chr(ord('A')+cols-1)}{rows}"
        goal_a=f"Copy Calc source range {profile['schema']['source_range']} into {target_objects['A'][0].split('/',1)[1]} and save; preserve the source and guards."
        goal_b="Copy Writer paragraph 1 into the blank Writer paragraph 2 and save."
        op_a=f"copy Calc source range {profile['schema']['source_range']} and paste into the assigned destination range"
        op_b="copy Writer paragraph 1 and paste into blank paragraph 2"
    if workflow_id=="F-04":
        goal_a=f"Fill Calc range {profile['schema']['range'][0]}:{profile['schema']['range'][1]} row-wise with {a1} and save."
        op_a=f"fill {target_objects['A'][0]} row-wise"
    op_b=locals().get("op_b",f"{profile['schema'].get('action','update')} {target_objects['B'][0]}")
    actor_goals=(ActorGoalSpec("A",row["task_domains"][0],goal_a,
                 op_a,tuple(target_objects["A"]),a0,a1),
                 ActorGoalSpec("B",row["task_domains"][1],goal_b,
                 op_b,tuple(target_objects["B"]),b0,b1))
    assets=_fixture_bytes(workflow_id,domain,profile,layout,a0,b0,a1,b1,instance_id)
    assets=_apply_diversity_context(workflow_id,profile,domain,assets)
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
       "context_expectation":profile["schema"].get("state_context"),
       "condition_semantics":{"solo":"score selected actor; require inactive target and guards unchanged",
        "ma_id":"score each actor on equivalent independent desktop fixture",
        "ma_sd":"score both actor goals and shared-state integrity"}}
    if workflow_id=="U-01":
        evaluator["history_contract"]={"actor_a_requires":["temporary_edit_committed","undo_action_after_actor_b_commit"],
            "actor_b_requires":["target_edit_committed"],"final_state_is_not_sufficient":True,
            "operation_schema_revision":2}
    if workflow_id=="U-N1":
        evaluator["history_contract"]={"actor_a_requires":["temporary_edit_committed","undo_action_after_actor_b_commit"],
            "actor_b_requires":["target_edit_committed"],"final_state_is_not_sufficient":True,
            "operation_schema_revision":1,"final_actor_a_value":"initial_value"}
    if workflow_id in _SECOND_WAVE:
        row2=_SECOND_WAVE[workflow_id]
        evaluator["operation_contract"]={"A":row2["schema"]["A"],"B":row2["schema"]["B"],"shared_state":row2["schema"]["shared"],"operation_graph":row2["operation_graph"],"evidence_required":True}
    if workflow_id in {"U-02","U-03","U-04"}:
        evaluator["history_contract"]={"actor_a_requires":["temporary_edit_or_operation_observed","undo_action_after_actor_b_commit","recovery_verified"],"actor_b_requires":["target_edit_committed"],"final_state_is_not_sufficient":True,"operation_schema_revision":1}
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
       {"application_set":row.get("required_apps",row["task_domains"]),"fixture_profile":profile["id"],"layout_id":layout["id"],
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
    operation_contract=row["evaluator"].get("operation_contract")
    if operation_contract:
        evidence=actual.get("operation_evidence",{})
        for aid in active_actors:
            actor_success[aid]=actor_success.get(aid,False) and bool(evidence.get(aid,{}).get("satisfied"))
    history_contract=row["evaluator"].get("history_contract")
    if row.get("workflow_id") in {"U-01","U-N1","U-02","U-03","U-04"} and history_contract:
        evidence=actual.get("workflow_evidence",{})
        actor_a=evidence.get("A",{})
        if "A" in active_actors:
            actor_success["A"]=actor_success.get("A",False) and bool(actor_a.get("temporary_edit_observed"))
            if "B" in active_actors:
                actor_success["A"] &= bool(actor_a.get("undo_after_actor_b"))
            else:
                actor_success["A"] &= bool(actor_a.get("undo_after_temporary_edit"))
    inactive_integrity={a:(actual.get("actors",{}).get(a)==initial["actors"][a])
                        for a in ("A","B") if a not in active_actors}
    guards_ok=actual.get("actors",{}).get("guards")==initial["actors"]["guards"]
    expected_context=row["evaluator"].get("context_expectation")
    observed_context=actual.get("context_state",actual.get("treatment",{}).get("context_profile"))
    context_ok=None if observed_context is None else observed_context==expected_context
    return {"actor_success":actor_success,"inactive_target_integrity":inactive_integrity,
       "guards_intact":guards_ok,"context_integrity":context_ok,
       "joint_success":bool(actor_success) and all(actor_success.values())
           and all(inactive_integrity.values()) and guards_ok and context_ok is not False}

def _positive_state(spec: InstanceSpecV1) -> dict[str,Any]:
    state=json.loads(json.dumps(spec.expected_final_state))
    if spec.workflow_id in _SECOND_WAVE:
        state["operation_evidence"]={a:{"satisfied":True,"operation":op} for a,op in _SECOND_WAVE[spec.workflow_id]["schema"].items() if a in {"A","B"}}
    if spec.workflow_id in {"U-01","U-N1","U-02","U-03","U-04"}:
        state["workflow_evidence"]={"A":{"temporary_edit_observed":True,"undo_after_temporary_edit":True,"undo_after_actor_b":True}}
    return state
def _negative_state(spec: InstanceSpecV1) -> dict[str,Any]:
    bad=_positive_state(spec); bad["actors"]["A"]["value"]=spec.actor_goals[0].initial_value
    if spec.workflow_id in _SECOND_WAVE: bad["operation_evidence"]["A"]["satisfied"]=False
    if spec.workflow_id in {"U-01","U-N1","U-02","U-03","U-04"}:bad["workflow_evidence"]["A"]["undo_after_actor_b"]=False
    return bad

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
        contexts={canonical_bytes(r["semantic_parameters"].get("state_context")).decode()
                  for r in records if r["workflow_id"]==wid and r["semantic_parameters"].get("state_context")}
        item={"generated":n,"retained":n,"duplicate_rejected":0,"near_duplicate_rejected":0,
              "state_context_profile_count":len(contexts)}
        if contexts:
            item["diversity_assessment"]="4 domains × 5 rendered task-state/context profiles; operation graph and schedule fixed"
            item["diversity_level"]="STATE_DIVERSE"
            item["meaningful_axes"]=["application/document/workbook context","target neighborhood or distractor structure","initial state"]
        else:
            item["diversity_assessment"]="legacy semantic profiles; classify from INSTANCE_VARIATION_AUDIT.md"
        per[wid]=item
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
