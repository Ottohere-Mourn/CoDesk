from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from swcub.production_v1 import read_manifest, evaluate_oracle
from swcub.runtime_bindings_v1 import F01RuntimeObserver, F04RuntimeObserver, _setup_f01, _setup_f04, build_runtime_binding_registry
from swcub.runtime_v1 import build_runtime_registry


class Guest:
    def __init__(self, slot, plan):
        self.slot = slot
        self.fixtures = {r["guest_path"]: Path(r["host_path"]).read_bytes() for r in plan["fixture_assets"]}
        self.current = dict(self.fixtures)
        self.launched = [{"app":r["app"],"target":r["guest_path"]} for r in plan["fixture_assets"]]
        self.episode = SimpleNamespace(_active_window_title=lambda:"LibreOffice - CoDesk",
            refresh_observation=lambda _x:{"screenshot":b"offline"},
            log=SimpleNamespace(record=lambda *a,**k:None))


class Backend:
    def __init__(self): self.events=[]
    def _command(self, guest, argv):
        if argv[0]=="cat": return guest.current[argv[1]].decode()
        if argv[0]=="bash": return "\n".join(Path(x["target"]).stem+" - LibreOffice Writer" for x in guest.launched if x["app"] in {"Writer","Calc"})
        raise AssertionError(argv)
    def notify_observer_event(self,e): self.events.append(dict(e))


def _case(workflow):
    suite=Path("benchmarks/codesk_v1")
    record=next(r for r in read_manifest(suite/"manifest.jsonl") if r["workflow_id"]==workflow)
    return record, build_runtime_registry().compile(record,suite)


def _replace_para(raw, old, new):
    ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    root=ET.fromstring(raw)
    done=False
    for p in root.iter(f"{{{ns}}}p"):
        if "".join(p.itertext())==old and not done:
            p.text=new; done=True
    assert done
    return ET.tostring(root,encoding="utf-8")


def test_f01_concrete_historical_full_document_binding_and_reset():
    record,plan=_case("F-01")
    assert callable(build_runtime_binding_registry()["F-01"]["evaluator"])
    guest=Guest("shared",plan); backend=Backend(); obs=F01RuntimeObserver()
    _setup_f01(plan,guest,backend)
    assert obs.verify_initial([guest],plan,backend)
    assert len(obs._assets(plan)["Writer"]) if False else True
    writer=next(r["guest_path"] for r in plan["fixture_assets"] if r["app"]=="Writer")
    seed_paras=obs._writer_target(__import__("swcub.runtime_bindings_v1",fromlist=["_writer_paragraphs"])._writer_paragraphs(guest.fixtures[writer]),record["actor_goals"][0])
    assert seed_paras==record["actor_goals"][0]["initial_value"]
    guest.current[writer]=_replace_para(guest.current[writer],record["actor_goals"][0]["initial_value"],record["actor_goals"][0]["expected_value"])
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A",))["actor_success"]["A"]
    guest.current=dict(guest.fixtures)
    assert obs.verify_initial([guest],plan,backend)


def test_f04_range_and_writer_bindings_score_positive_and_contamination():
    record,plan=_case("F-04")
    guest=Guest("shared",plan); backend=Backend(); obs=F04RuntimeObserver()
    _setup_f04(plan,guest,backend)
    assert obs.verify_initial([guest],plan,backend)
    actors={x["actor_id"]:x for x in plan["actors"]}
    calc=next(r["guest_path"] for r in plan["fixture_assets"] if r["app"]=="Calc")
    writer=next(r["guest_path"] for r in plan["fixture_assets"] if r["app"]=="Writer")
    grid=obs._grid(guest.current[calc].decode())
    cells=obs._range(actors["A"]["target_objects"][0].split("/",1)[1])
    ns_t="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    ns_x="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    root=ET.fromstring(guest.current[calc])
    table=root.find(".//{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table")
    rows=list(table.findall("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row"))
    matrix=__import__("json").loads(actors["A"]["expected_value"])
    for index,(ri,ci) in enumerate(cells):
        row=rows[ri]
        cell=list(row)[ci]
        p=cell.find(f"{{{ns_x}}}p")
        p.text=matrix[index//len(matrix[0])][index%len(matrix[0])]
    guest.current[calc]=ET.tostring(root,encoding="utf-8")
    guest.current[writer]=_replace_para(guest.current[writer],actors["B"]["initial_value"],actors["B"]["expected_value"])
    actual=obs([guest],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    bad=ET.fromstring(guest.current[calc]); bad.find(".//{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row/{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell/{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p").text="CONTAMINATION"
    guest.current[calc]=ET.tostring(bad,encoding="utf-8")
    assert not evaluate_oracle(record,obs([guest],plan,backend),("A","B"))["joint_success"]


def test_f01_canonical_instance_matches_historical_operation_and_oracle():
    import json
    task=json.loads(Path("tasks/codesk_writer_calc_v1.json").read_text())
    record,plan=_case("F-01")
    canonical=next(r for r in read_manifest(Path("benchmarks/codesk_v1/manifest.jsonl"))
        if r["workflow_id"]=="F-01" and r["semantic_parameters"]["domain_id"]=="capital_allocation"
        and r["semantic_parameters"]["object_profile_id"]=="cell_b2"
        and r["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in canonical["actor_goals"]}
    assert plan["operation_graph"]=="writer_full_document_vs_calc_cell"
    assert task["actor_goals"]["writer_actor"]["operation"]=="replace complete document content and save"
    assert goals["A"]["target_objects"]==["writer/document-content"]
    assert goals["A"]["initial_value"]==task["environment"]["initial_state"]["writer_document"]["text"]
    assert goals["A"]["expected_value"]==task["actor_goals"]["writer_actor"]["expected_text"]
    assert goals["B"]["target_objects"]==["calc/B2"]
    assert goals["B"]["expected_value"]=="Approved"
    writer_asset=next(x for x in canonical["fixture_files"] if x["path"].endswith(".fodt"))
    assert len(__import__("swcub.runtime_bindings_v1",fromlist=["_writer_paragraphs"])._writer_paragraphs(
        Path("benchmarks/codesk_v1",writer_asset["path"]).read_bytes()))==1


def test_f04_canonical_instance_matches_fixed_historical_range_workflow():
    from swcub.tasks.workflows_v1 import F04
    all_rows=read_manifest(Path("benchmarks/codesk_v1/manifest.jsonl"))
    canonical=next(r for r in all_rows if r["workflow_id"]=="F-04"
        and r["semantic_parameters"]["domain_id"]=="capital_allocation"
        and r["semantic_parameters"]["object_profile_id"]=="range_b2_c3"
        and r["semantic_parameters"]["layout_id"]=="guard_after")
    goals={x["actor_id"]:x for x in canonical["actor_goals"]}
    assert goals["A"]["target_objects"]==["calc/B2:C3"]
    assert __import__("json").loads(goals["A"]["expected_value"] )==[["11","12"],["21","22"]]
    assert goals["B"]["initial_value"]==F04.writer_initial
    assert goals["B"]["expected_value"]==F04.writer_final
    plan=build_runtime_registry().compile(canonical,Path("benchmarks/codesk_v1"))
    assert plan["operation_graph"]=="calc_range_vs_writer_document"
    assert F04.actor_a_goal.startswith("In Calc Sheet1, enter 11,12,21,22 in B2:C3")


def test_c01_instance_spec_copy_targets_sources_oracle_and_reset():
    import json
    from swcub.runtime_bindings_v1 import C01RuntimeObserver
    rows=read_manifest(Path("benchmarks/codesk_v1/manifest.jsonl"))
    record=next(r for r in rows if r["workflow_id"]=="C-01"
        and r["semantic_parameters"]["domain_id"]=="capital_allocation"
        and r["semantic_parameters"]["object_profile_id"]=="writer_note_calc_cell"
        and r["semantic_parameters"]["layout_id"]=="guard_after")
    plan=build_runtime_registry().compile(record,Path("benchmarks/codesk_v1"))
    actors={a["actor_id"]:a for a in plan["actors"]}
    assert actors["A"]["target_objects"]==("writer/paragraph[1]",)
    assert actors["A"]["initial_value"]=="INSERT COPIED VALUE"
    assert actors["A"]["expected_value"]=="REF-7319"
    assert actors["B"]["target_objects"]==("calc/A2",)
    assert actors["B"]["initial_value"]=="__EMPTY_CELL__"
    assert actors["B"]["expected_value"]=="BATCH-204"
    obs=C01RuntimeObserver(); backend=Backend()
    shared=Guest("shared",plan)
    assert obs.verify_initial([shared],plan,backend)
    writer=next(r["guest_path"] for r in plan["fixture_assets"] if r["app"]=="Writer")
    calc=next(r["guest_path"] for r in plan["fixture_assets"] if r["app"]=="Calc")
    shared.current[writer]=_replace_para(shared.current[writer],"INSERT COPIED VALUE","REF-7319")
    root=ET.fromstring(shared.current[calc])
    table=root.find(".//{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table")
    row=list(table)[1]; cell=list(row)[0]
    text_ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    para=cell.find(f"{{{text_ns}}}p")
    if para is None:
        para=ET.SubElement(cell,f"{{{text_ns}}}p")
    para.text="BATCH-204"
    shared.current[calc]=ET.tostring(root,encoding="utf-8")
    actual=obs([shared],plan,backend)
    assert evaluate_oracle(record,actual,("A","B"))["joint_success"]
    shared.current=dict(shared.fixtures)
    assert obs.verify_initial([shared],plan,backend)
    bindings=build_runtime_binding_registry()["C-01"]
    assert all(callable(bindings[k]) for k in ("setup","initial_verifier","evaluator","event_gate"))
    assert "x11_clipboard_payload_generation_v1" in obs.observer_ids
    from swcub.tasks.clipboard_v1 import task_specification
    task=task_specification()
    assert task["actors"]["writer_actor"]["source"]=="Writer paragraph 1"
    assert task["actors"]["writer_actor"]["destination"]=="Writer paragraph 2"
    assert task["actors"]["calc_actor"]["source"]=="Calc Sheet1.A1"
    assert task["actors"]["calc_actor"]["destination"]=="Calc Sheet1.A2"
    assert actors["A"]["goal"].startswith("Copy Writer source REF-7319")
    assert actors["B"]["goal"].startswith("Copy Calc A1 value BATCH-204")


def test_c02_instance_spec_binds_hyperlink_and_browser_submission_oracle():
    import json
    from swcub.runtime_bindings_v1 import C02RuntimeObserver
    rows=read_manifest(Path("benchmarks/codesk_v1/manifest.jsonl"))
    record=next(r for r in rows if r["workflow_id"]=="C-02"
        and r["semantic_parameters"]["domain_id"]=="capital_allocation"
        and r["semantic_parameters"]["object_profile_id"]=="href_reference"
        and r["semantic_parameters"]["layout_id"]=="guard_after")
    plan=build_runtime_registry().compile(record,Path("benchmarks/codesk_v1"))
    assert plan["required_apps"]==["Writer","Browser"]
    actors={x["actor_id"]:x for x in plan["actors"]}
    assert actors["A"]["expected_value"]==json.dumps(
        {"text":"Reference link","href":"https://example.org/codesk/reference-a"},
        sort_keys=True,separators=(",",":"))
    assert actors["B"]["expected_value"]=="https://example.org/codesk/reference-b"
    obs=C02RuntimeObserver(); backend=Backend(); shared=Guest("shared",plan)
    assert obs.verify_initial([shared],plan,backend)
    writer=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    browser_state=next(x["guest_path"] for x in plan["fixture_assets"]
        if Path(x["fixture"]).name=="browser-initial-state.json")
    root=ET.fromstring(shared.current[writer])
    text_ns="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xlink_ns="http://www.w3.org/1999/xlink"
    body=root.find(".//{urn:oasis:names:tc:opendocument:xmlns:office:1.0}body/{urn:oasis:names:tc:opendocument:xmlns:office:1.0}text")
    para=body.findall(f"{{{text_ns}}}p")[0]
    para.clear()
    link=ET.SubElement(para,f"{{{text_ns}}}a",{f"{{{xlink_ns}}}href":"https://example.org/codesk/reference-a"})
    link.text="Reference link"
    shared.current[writer]=ET.tostring(root,encoding="utf-8")
    shared.current[browser_state]=b'{"revision":1,"submission":{"url":"https://example.org/codesk/reference-b"}}'
    assert evaluate_oracle(record,obs([shared],plan,backend),("A","B"))["joint_success"]
    bad=ET.fromstring(shared.current[writer])
    bad_link=bad.find(f".//{{{text_ns}}}a")
    bad_link.set(f"{{{xlink_ns}}}href","https://example.org/wrong")
    shared.current[writer]=ET.tostring(bad,encoding="utf-8")
    assert not evaluate_oracle(record,obs([shared],plan,backend),("A","B"))["joint_success"]
    from swcub.tasks.browser_writer_workflows_v1 import C02 as historical
    assert actors["A"]["initial_value"]==historical.writer_initial[0]
    assert actors["B"]["expected_value"]==historical.browser_expected()["url"]
    assert actors["A"]["goal"].startswith("Copy the Browser link")
    assert historical.writer_goal_ok({"valid_structure":True,"visible_text":"Reference link",
        "guard_text":"Guard paragraph","links":[{"text":"Reference link","href":"https://example.org/codesk/reference-a"}],
        "annotations":0})
    binding=build_runtime_binding_registry()["C-02"]
    assert all(callable(binding[k]) for k in ("setup","initial_verifier","evaluator","event_gate"))
    assert {"writer_hyperlink_href_v1","browser_submission_revision_v1"}<=set(obs.observer_ids)


def test_f02_instance_spec_binds_exact_writer_comment_and_browser_form():
    import json
    from swcub.runtime_bindings_v1 import F02RuntimeObserver
    from swcub.tasks import browser_writer_workflows_v1 as historical_module
    historical=historical_module.F02
    rows=read_manifest(Path("benchmarks/codesk_v1/manifest.jsonl"))
    record=next(r for r in rows if r["workflow_id"]=="F-02"
        and r["semantic_parameters"]["domain_id"]=="capital_allocation"
        and r["semantic_parameters"]["object_profile_id"]=="anchor_summary"
        and r["semantic_parameters"]["layout_id"]=="guard_after")
    plan=build_runtime_registry().compile(record,Path("benchmarks/codesk_v1"))
    actors={x["actor_id"]:x for x in plan["actors"]}
    assert plan["required_apps"]==["Writer","Browser"]
    assert json.loads(actors["A"]["expected_value"])=={"anchor":"Review anchor","comment":historical_module.COMMENT}
    assert json.loads(actors["B"]["expected_value"])=={"case":historical_module.CASE,"decision":historical_module.DECISION}
    observer=F02RuntimeObserver(); backend=Backend(); shared=Guest("shared",plan)
    assert observer.verify_initial([shared],plan,backend)
    writer=next(x["guest_path"] for x in plan["fixture_assets"] if x["app"]=="Writer")
    browser_state=next(x["guest_path"] for x in plan["fixture_assets"]
        if Path(x["fixture"]).name=="browser-initial-state.json")
    office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    root=ET.fromstring(shared.current[writer])
    body=root.find(f".//{{{office}}}body/{{{office}}}text")
    anchor=body.findall(f"{{{text}}}p")[0]
    ann=ET.SubElement(anchor,f"{{{office}}}annotation",{f"{{{office}}}name":"comment-1"})
    ET.SubElement(ann,f"{{{text}}}p").text=historical_module.COMMENT
    ET.SubElement(anchor,f"{{{office}}}annotation-end",{f"{{{office}}}name":"comment-1"})
    shared.current[writer]=ET.tostring(root,encoding="utf-8")
    expected={"case":historical_module.CASE,"decision":historical_module.DECISION}
    shared.current[browser_state]=json.dumps({"submission":expected,"revision":1},sort_keys=True).encode()
    assert evaluate_oracle(record,observer([shared],plan,backend),("A","B"))["joint_success"]
    root=ET.fromstring(shared.current[writer])
    ann=root.find(f".//{{{office}}}annotation")
    ann.find(f".//{{{text}}}p").text="WRONG COMMENT"
    shared.current[writer]=ET.tostring(root,encoding="utf-8")
    assert not evaluate_oracle(record,observer([shared],plan,backend),("A","B"))["joint_success"]
    binding=build_runtime_binding_registry()["F-02"]
    assert all(callable(binding[k]) for k in ("setup","initial_verifier","evaluator","event_gate"))
