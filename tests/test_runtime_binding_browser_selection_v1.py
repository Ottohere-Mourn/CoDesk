from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import json
import xml.etree.ElementTree as ET

from swcub.production_v1 import read_manifest,evaluate_oracle,_xml_file
from swcub.runtime_bindings_v1 import A01RuntimeObserver,A02RuntimeObserver,AN1RuntimeObserver,S01RuntimeObserver,SN1RuntimeObserver,U01RuntimeObserver,UN1RuntimeObserver,C03RuntimeObserver,CN1RuntimeObserver,build_runtime_binding_registry,_writer_paragraphs
from swcub.runtime_v1 import build_runtime_registry

SUITE=Path("benchmarks/codesk_v1")
class Guest:
    def __init__(self,slot,plan):
        self.slot=slot
        self.fixtures={r["guest_path"]:Path(r["host_path"]).read_bytes() for r in plan["fixture_assets"]}
        self.current=dict(self.fixtures)
        self.launched=[{"app":r["app"],"target":r["guest_path"]} for r in plan["fixture_assets"]]
        self.episode=SimpleNamespace(_active_window_title=lambda:"Chromium - CoDesk",refresh_observation=lambda _x:{"screenshot":b"offline"},log=SimpleNamespace(record=lambda *a,**k:None))
class BrowserBackend:
    def __init__(self):self.events=[]
    def _command(self,g,argv):
        if argv[0]=="cat":return g.current[argv[1]].decode()
        if argv[0]=="bash":
            cmd=argv[-1]
            if "search --class chromium" in cmd:return "12345\n"
            if "getactivewindow" in cmd:return "12345"
            if "getwindowname" in cmd:return "Chromium - CoDesk"
            if "cat " in cmd:
                path=cmd.split("cat ",1)[1].split()[0]
                return g.current.get(path,b"").decode()
        raise AssertionError(argv)
    def notify_observer_event(self,row):self.events.append(dict(row))
def case(wid,semantic):
    r=next(x for x in read_manifest(SUITE/"manifest.jsonl") if x["workflow_id"]==wid and semantic(x))
    return r,build_runtime_registry().compile(r,SUITE)
def set_json(g,plan,name,value):
    path=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name==name)
    g.current[path]=(json.dumps(value,sort_keys=True)+"\n").encode()
    return path
def test_a01_two_tab_binding_keeps_one_window_and_scores_each_tab():
    record,plan=case("A-01",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="tabs_review_cases" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert (goals["A"]["expected_value"],goals["B"]["expected_value"])==("CTX-A-04100","CTX-B-08200")
    guest=Guest("shared",plan);backend=BrowserBackend();obs=A01RuntimeObserver()
    assert obs.verify_initial([guest],plan,backend)
    state_path=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-initial-state.json")
    state=json.loads(guest.current[state_path]);state["window_id"]="12345"
    state["tabs"]["tab-a"].update(goal=goals["A"]["expected_value"],revision=1)
    state["tabs"]["tab-b"].update(goal=goals["B"]["expected_value"],revision=1)
    guest.current[state_path]=(json.dumps(state,sort_keys=True)+"\n").encode()
    evpath=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-events.jsonl")
    guest.current[evpath]=b'{"kind":"active_tab_changed","before":"tab-a","after":"tab-b"}\n'
    actual=obs([guest],plan,backend)
    assert actual["application_context"][0]["window_ids"]==["12345"]
    assert actual["application_context"][0]["context_changes"]
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    state["tabs"]["tab-b"]["goal"]="wrong";guest.current[state_path]=(json.dumps(state)+"\n").encode()
    assert not evaluate_oracle(record,obs([guest],plan,backend),("A","B"))["joint_success"]
    guest.current={k:v for k,v in guest.fixtures.items()}
    assert obs.verify_initial([guest],plan,backend)
    assert all(callable(build_runtime_binding_registry()["A-01"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_a01_matches_historical_anchor_goals_and_fixture_protocol():
    from swcub.tasks.browser_context_v1 import MANIFEST
    values={k:v["expected"] for k,v in MANIFEST["actor_goals"].items()}
    record,plan=case("A-01",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="tabs_review_cases" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert goals["A"]["expected_value"]==values["actor_a"]=="CTX-A-04100"
    assert goals["B"]["expected_value"]==values["actor_b"]=="CTX-B-08200"
    state=next(Path(x["host_path"]).read_bytes() for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-initial-state.json")
    assert json.loads(state)["tabs"]==MANIFEST["initial_state"]["tabs"]
    assert record["semantic_parameters"]["operation_graph"]=="two_tab_context"

def test_a02_same_page_record_binding_and_historical_equivalence():
    from swcub.tasks.browser_record_context_v1 import INITIAL_STATE,VALUES
    values=VALUES
    record,plan=case("A-02",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="record_supplier" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert goals["A"]["expected_value"]==values["actor_a"]=="REC-A-4100"
    assert goals["B"]["expected_value"]==values["actor_b"]=="REC-B-8200"
    guest=Guest("shared",plan);backend=BrowserBackend();obs=A02RuntimeObserver()
    assert obs.verify_initial([guest],plan,backend)
    path=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-initial-state.json")
    state=INITIAL_STATE.copy();state=json.loads(json.dumps(state))
    state["records"]["record-a"].update(goal=VALUES["actor_a"],revision=1)
    state["records"]["record-b"].update(goal=VALUES["actor_b"],revision=1)
    guest.current[path]=(json.dumps(state)+"\n").encode()
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    assert all(callable(build_runtime_binding_registry()["A-02"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_s01_calc_cells_bind_to_historical_selection_probe():
    from scripts import probe_selection_active_object_v1 as legacy
    record,plan=case("S-01",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="cells_b2_c3" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert tuple(goals["A"]["target_objects"])==("calc/B2",) and goals["A"]["expected_value"]==legacy.TARGETS["actor_a"]["value"]
    assert tuple(goals["B"]["target_objects"])==("calc/C3",) and goals["B"]["expected_value"]==legacy.TARGETS["actor_b"]["value"]
    assert goals["A"]["initial_value"]==legacy.INITIAL[1][1] and goals["B"]["initial_value"]==legacy.INITIAL[2][2]
    guest=Guest("shared",plan);backend=BrowserBackend();obs=S01RuntimeObserver()
    assert obs.verify_initial([guest],plan,backend)
    calc=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Calc")
    root=ET.fromstring(guest.current[calc]);ns={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
    cells={x["target_objects"][0].split("/")[-1]:x for x in goals.values()}
    def assign(cell,value):
        col=ord(cell[0])-65;rownum=int(cell[1:])-1
        rows=root.findall(".//table:table-row",ns);p=rows[rownum].findall("table:table-cell",ns)[col].find("text:p",ns);p.text=value
    assign("B2",goals["A"]["expected_value"]);assign("C3",goals["B"]["expected_value"])
    guest.current[calc]=ET.tostring(root,encoding="utf-8")
    backend._command=lambda g,argv: json.dumps({"sheet":0,"start_column":2,"start_row":2,"end_column":2,"end_row":2}) if argv[0]=="python3" else BrowserBackend._command(backend,g,argv)
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    assert any(x.get("observer")=="uno_active_cell_selection_v1" for x in backend.events)
    assert all(callable(build_runtime_binding_registry()["S-01"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_an1_single_tab_route_context_binding_and_oracle():
    record,plan=case("A-N1",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="spa_inventory_audit" and x["semantic_parameters"]["layout_id"]=="guard_after")
    guests={x["actor_id"]:x for x in plan["actors"]}
    g=Guest("shared",plan);backend=BrowserBackend();obs=AN1RuntimeObserver()
    assert obs.verify_initial([g],plan,backend)
    state_path=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-initial-state.json")
    state=json.loads(g.current[state_path]);state["window_id"]="12345"
    state["active_route"]="route-b";state["tab_hash"]="/workspace#route-b"
    state["routes"]["route-a"].update(value=guests["A"]["expected_value"],revision=1)
    state["routes"]["route-b"].update(value=guests["B"]["expected_value"],revision=1)
    g.current[state_path]=(json.dumps(state,sort_keys=True)+"\n").encode()
    evpath=next(x["guest_path"] for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-events.jsonl")
    g.current[evpath]=b'{"kind":"route_changed","before":"route-a","after":"route-b"}\n'
    actual=obs([g],plan,backend)
    assert actual["application_context"][0]["window_ids"]==["12345"]
    assert actual["application_context"][0]["route_changes"]
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    server=next(Path(x["host_path"]).read_bytes() for x in plan["fixture_assets"] if Path(x["guest_path"]).name=="browser-server.py")
    compile(server,"an1-server.py","exec")
    assert all(callable(build_runtime_binding_registry()["A-N1"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_sn1_odf_style_oracle_and_range_observer():
    record,plan=case("S-N1",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="range_sentence_pair" and x["semantic_parameters"]["layout_id"]=="guard_after")
    guest=Guest("shared",plan);backend=BrowserBackend();obs=SN1RuntimeObserver()
    assert obs.verify_initial([guest],plan,backend)
    path=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    root=ET.fromstring(guest.current[path]);textns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    spans=[x for x in root.iter(f"{{{textns}}}span") if x.get(f"{{{textns}}}style-name")]
    assert len(spans)==2
    spans[0].set(f"{{{textns}}}style-name","BoldA");spans[1].set(f"{{{textns}}}style-name","BoldB")
    guest.current[path]=ET.tostring(root,encoding="utf-8")
    backend._command=lambda g,argv: json.dumps({"selected_text":"Alpha sentence one."}) if argv[0]=="python3" else BrowserBackend._command(backend,g,argv)
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    assert any(x.get("observer")=="uno_text_range_selection_v1" for x in backend.events)
    spans[1].set(f"{{{textns}}}style-name","RangeB");guest.current[path]=ET.tostring(root,encoding="utf-8")
    assert not evaluate_oracle(record,obs([guest],plan,backend),("A","B"))["joint_success"]
    assert all(callable(build_runtime_binding_registry()["S-N1"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def _set_calc_cell(raw,cell,value):
    root=ET.fromstring(raw)
    ns={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
    col=ord(cell[0].upper())-65;row=int(cell[1:])-1
    rows=root.findall(".//table:table-row",ns)
    rows[row].findall("table:table-cell",ns)[col].find("text:p",ns).text=value
    return ET.tostring(root,encoding="utf-8")

def test_u01_requires_history_evidence_and_distinguishes_ma_id_from_shared_undo():
    from scripts.probe_undo_history_v1 import GOALS
    record,plan=case("U-01",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="calc_status_cells" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert goals["A"]["expected_value"]==GOALS["actor_a"]["value"]=="A-TEMP"
    assert goals["A"]["initial_value"]==GOALS["actor_a"]["final"]=="B2 seed"
    assert goals["B"]["expected_value"]==GOALS["actor_b"]["value"]=="B-2042"
    obs=U01RuntimeObserver();backend=BrowserBackend()
    backend.scheduler_event_history=[
      {"kind":"action_complete","actor_id":"A","action_payload":"type_text('A-TEMP')"},
      {"kind":"action_complete","actor_id":"B","action_payload":"type_text('B-2042')"},
      {"kind":"action_complete","actor_id":"A","action_payload":"hotkey('ctrl','z')"}]
    backend.active_actor_ids=["A","B"]
    ga=Guest("actor_a",plan);gb=Guest("actor_b",plan)
    path=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Calc")
    ga.current[path]=_set_calc_cell(ga.current[path],"B2","B2 seed")
    gb.current[path]=_set_calc_cell(gb.current[path],"C3","B-2042")
    actual=obs([ga,gb],plan,backend)
    assert actual["workflow_evidence"]["A"]["undo_after_actor_b"]
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    shared=Guest("shared",plan)
    shared.current[path]=_set_calc_cell(shared.current[path],"B2","A-TEMP")
    shared.current[path]=_set_calc_cell(shared.current[path],"C3","C3 seed")
    bad=obs([shared],plan,backend)
    assert bad["workflow_evidence"]["A"]["undo_after_actor_b"]
    assert not evaluate_oracle(record,bad,("A","B"))["joint_success"]
    no_history={**actual,"workflow_evidence":{"A":{}}}
    assert not evaluate_oracle(record,no_history,("A","B"))["joint_success"]
    assert all(callable(build_runtime_binding_registry()["U-01"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_un1_writer_undo_history_is_part_of_the_runtime_oracle():
    record,plan=case("U-N1",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="writer_lines_0_1" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert plan["operation_graph"]=="writer_document_history"
    assert goals["A"]["expected_value"]=="TEMP-A"
    assert goals["B"]["expected_value"]=="FINAL-B"
    obs=UN1RuntimeObserver();backend=BrowserBackend();guest=Guest("shared",plan)
    assert obs.verify_initial([guest],plan,backend)
    writer=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    assert _writer_paragraphs(guest.current[writer])==["Seed A","Seed B","Guard: PRESERVE"]
    root=ET.fromstring(guest.current[writer]);paras=list(root.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"))
    paras[0].text="Seed A";paras[1].text="FINAL-B";guest.current[writer]=ET.tostring(root,encoding="utf-8")
    backend.scheduler_event_history=[
      {"kind":"action_complete","actor_id":"A","action_payload":"type_text('TEMP-A')"},
      {"kind":"action_complete","actor_id":"B","action_payload":"type_text('FINAL-B')"},
      {"kind":"action_complete","actor_id":"A","action_payload":"hotkey('ctrl','z')"}]
    backend.active_actor_ids=["A","B"]
    actual=obs([guest],plan,backend)
    assert actual["workflow_evidence"]["A"]["undo_after_actor_b"]
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    backend.scheduler_event_history=backend.scheduler_event_history[:2]+backend.scheduler_event_history[2:]
    backend.scheduler_event_history[1],backend.scheduler_event_history[2]=backend.scheduler_event_history[2],backend.scheduler_event_history[1]
    reordered=obs([guest],plan,backend)
    assert not reordered["workflow_evidence"]["A"]["undo_after_actor_b"]
    assert not evaluate_oracle(record,reordered,("A","B"))["joint_success"]
    assert all(callable(build_runtime_binding_registry()["U-N1"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_cn1_exact_writer_table_and_browser_submission_oracle():
    from swcub.runtime_bindings_v1 import _cn1_server_source
    compile(_cn1_server_source("/tmp/page.html", "/tmp/state.json", "/tmp/events.jsonl"), "cn1_server.py", "exec")
    record,plan=case("C-N1",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="rich_table_2x2" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert goals["A"]["task_domain"]=="Writer" and goals["B"]["task_domain"]=="Browser"
    assert goals["A"]["target_objects"]==("writer/table[0]",)
    assert goals["B"]["target_objects"]==("browser/url-submit",)
    obs=CN1RuntimeObserver();backend=BrowserBackend();guest=Guest("shared",plan)
    assert obs.verify_initial([guest],plan,backend)
    writer=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    doc=ET.fromstring(guest.current[writer]);ns={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
    grid=next(x for x in doc.iter("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table") if x.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name")=="CoDeskDestination")
    rows=grid.findall("table:table-row",ns);expected=json.loads(goals["A"]["expected_value"])
    for ri,row in enumerate(rows):
        cells=row.findall("table:table-cell",ns)
        for ci,cell in enumerate(cells):cell.find("text:p",ns).text=expected[ri][ci]
    guest.current[writer]=ET.tostring(doc,encoding="utf-8")
    support={Path(x["guest_path"]).name:x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Support"}
    state_path=support["browser-initial-state.json"];state=json.loads(guest.current[state_path]);state["submission"]={"url":goals["B"]["expected_value"]};state["revision"]=1
    guest.current[state_path]=(json.dumps(state,sort_keys=True)+"\n").encode()
    event_path=support["browser-events.jsonl"];guest.current[event_path]=b'{"kind":"url_submitted","revision":1}\n'
    class Sampler:
        def sample(self):return {"targets":["TARGETS","text/html","text/plain"],"payload_sha256":"a"*64,"generation":2,"status":"ok"}
    guest.episode.clipboard_sampler=Sampler()
    actual=obs([guest],plan,backend)
    assert actual["clipboard_observations"][0]["snapshot"]["targets"]==["TARGETS","text/html","text/plain"]
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    # Same visible strings in a paragraph do not satisfy the structured-table oracle.
    guest.current[writer]=_xml_file("writer",[" ".join(x for row in expected for x in row),"Guard: PRESERVE"])
    flat=obs([guest],plan,backend)
    assert not evaluate_oracle(record,flat,("A","B"))["joint_success"]
    assert all(callable(build_runtime_binding_registry()["C-N1"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))

def test_c03_historical_range_and_paragraph_copy_are_runtime_equivalent():
    from swcub.tasks.workflows_v1 import C03
    record,plan=case("C-03",lambda x:x["semantic_parameters"]["domain_id"]=="capital_allocation" and x["semantic_parameters"]["object_profile_id"]=="matrix_2x2" and x["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in plan["actors"]}
    assert plan["operation_graph"]=="calc_range_and_writer_paragraph_copy"
    assert goals["A"]["target_objects"]==("calc/A4:B5",)
    assert goals["B"]["target_objects"]==("writer/paragraph[1]",)
    assert goals["A"]["operation"]=="copy Calc source range A1:B2 and paste into the assigned destination range"
    assert goals["B"]["operation"]=="copy Writer paragraph 1 and paste into blank paragraph 2"
    obs=C03RuntimeObserver();backend=BrowserBackend();guest=Guest("shared",plan)
    assert obs.verify_initial([guest],plan,backend)
    calc=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Calc")
    writer=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    grid=obs._grid(guest.current[calc].decode())
    initial=tuple(tuple(grid.get((r,c),"") for c in range(3)) for r in range(5))
    assert initial==C03.calc_initial
    assert _writer_paragraphs(guest.current[writer])==["NOTE-571",""]
    root=ET.fromstring(guest.current[calc]);ns={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
    rows=root.findall(".//table:table-row",ns)
    for dest_row,src_row in ((3,0),(4,1)):
        for col in range(2):
            cell=rows[dest_row].findall("table:table-cell",ns)[col]
            para=cell.find("text:p",ns)
            if para is None:para=ET.SubElement(cell,"{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p")
            para.text=grid[(src_row,col)]
    guest.current[calc]=ET.tostring(root,encoding="utf-8")
    doc=ET.fromstring(guest.current[writer]);paras=list(doc.iter("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"));paras[1].text=paras[0].text
    guest.current[writer]=ET.tostring(doc,encoding="utf-8")
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    final=obs._grid(guest.current[calc].decode())
    assert tuple(tuple(final.get((r,c),"") for c in range(3)) for r in range(5))==C03.calc_final
    assert _writer_paragraphs(guest.current[writer])==["NOTE-571","NOTE-571"]
    guest.current=dict(guest.fixtures);assert obs.verify_initial([guest],plan,backend)
    assert all(callable(build_runtime_binding_registry()["C-03"][k]) for k in ("setup","initial_verifier","evaluator","event_gate"))
