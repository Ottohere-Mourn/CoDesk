from tasks.mechanism_expansion_v1.oracle import TARGETS, evaluate

def test_clipboard_oracle_separates_result_and_attribution():
    good = {"rows": {"A": TARGETS["MECH-01"]["A"], "B": TARGETS["MECH-01"]["B"]},
            "clipboard_trace": [{"event": "paste", "pasted_value": "INV-48217",
                                 "source_value": "INV-48217"}]}
    assert evaluate("MECH-01", good)["joint_success"]
    bad = {"rows": {"A": {**TARGETS["MECH-01"]["A"], "reference": "ACH-77104"},
                    "B": TARGETS["MECH-01"]["B"]},
           "clipboard_trace": [{"event": "paste", "pasted_value": "ACH-77104",
                                "source_value": "INV-48217", "reason": "clipboard_owner_changed"}]}
    result = evaluate("MECH-01", bad)
    assert not result["actors"]["A"]["success"] and result["mechanism_evidence"]["attributed"]

def test_undo_causal_evidence_is_not_inferred_from_score_alone():
    s = {"rows": {"A": TARGETS["MECH-02"]["A"], "B": {"batch": "QX-207"}},
         "undo_trace": [{"event": "undo", "request_actor": "A", "undid_actor": "B"}]}
    result = evaluate("MECH-02", s)
    assert result["actors"]["A"]["success"] and not result["actors"]["B"]["success"]
    assert result["mechanism_evidence"]["attributed"]

def test_focus_failure_without_focus_trace_is_not_attributed():
    s = {"calc_result": {"cell": "Calc!D12", "value": ""}, "writer_result": TARGETS["MECH-03"]["B"],
         "input_trace": []}
    result = evaluate("MECH-03", s)
    assert not result["actors"]["A"]["success"] and not result["mechanism_evidence"]["attributed"]

def test_focus_misroute_needs_target_window_evidence():
    s = {"calc_result": TARGETS["MECH-03"]["A"], "writer_result": TARGETS["MECH-03"]["B"],
         "input_trace": [{"intended_window": "Calc", "actual_window": "Writer"}]}
    result = evaluate("MECH-03", s)
    assert result["joint_success"] and result["mechanism_evidence"]["attributed"]

def test_range_oracle_uses_stable_ids_not_row_numbers():
    s = {"rows_by_id": {"SMP-041": {"status": "RETEST"}, "SMP-058": {"status": "RETEST"},
                        "SMP-033": {"status": "TRANSFERRED"}},
         "range_trace": [{"intended_record_id": "SMP-041", "written_record_id": "SMP-041"}]}
    assert evaluate("MECH-04", s)["joint_success"]

def test_session_attribution_requires_wrong_role_and_session_change():
    good = {"audit_events": [{"record": "CLM-8401", "principal": "Claims Reviewer", "status": "APPROVED"},
                             {"record": "PAY-2207", "principal": "Treasury Reviewer", "status": "CONFIRMED"}],
            "session_trace": [{"generation_before": "g1", "generation_after": "g2"}]}
    assert evaluate("MECH-05", good)["joint_success"]
    bad = {"audit_events": [{"record": "CLM-8401", "principal": "Treasury Reviewer",
                             "intended_principal": "Claims Reviewer", "operation": "approve",
                             "status": "APPROVED"},
                            {"record": "PAY-2207", "principal": "Treasury Reviewer", "status": "CONFIRMED"}],
           "session_trace": [{"generation_before": "g1", "generation_after": "g2"}]}
    result = evaluate("MECH-05", bad)
    assert not result["actors"]["A"]["success"] and result["mechanism_evidence"]["attributed"]


def test_mech01_http_serves_parseable_html_with_expected_ids(tmp_path):
    from html.parser import HTMLParser
    from http.server import ThreadingHTTPServer
    from urllib.request import urlopen
    import runpy, threading
    module=runpy.run_path("tasks/mechanism_expansion_v1/mech01/app.py")
    module["Handler"].state=module["AppState"](tmp_path/"state.json")
    server=ThreadingHTTPServer(("127.0.0.1",0),module["Handler"])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/desk",timeout=5) as response:
            html=response.read().decode("utf-8")
            assert response.headers.get_content_type()=="text/html"
        class IdParser(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids=set()
            def handle_starttag(self,tag,attrs):
                for key,value in attrs:
                    if key=="id": self.ids.add(value)
        parser=IdParser(); parser.feed(html)
        assert {"source-A","source-B","reference-A","reference-B"} <= parser.ids
        assert not any(x.startswith('"') or x.endswith('"') or '\\' in x for x in parser.ids)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_mech01_http_accepts_and_persists_both_actor_saves(tmp_path):
    from http.server import ThreadingHTTPServer
    from urllib.request import urlopen, Request
    import json, runpy, threading
    module=runpy.run_path("tasks/mechanism_expansion_v1/mech01/app.py")
    module["Handler"].state=module["AppState"](tmp_path/"state.json")
    server=ThreadingHTTPServer(("127.0.0.1",0),module["Handler"])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for role,fields in [
            ("A",{"vendor":"Northwind Safety","reference":"INV-48217","amount":"1840.00"}),
            ("B",{"payee":"Riverside Testing","reference":"ACH-77104","amount":"965.50"}),
        ]:
            body=json.dumps({"role":role,"fields":fields}).encode()
            req=Request(f"http://127.0.0.1:{server.server_port}/api/save",data=body,
                        headers={"Content-Type":"application/json"},method="POST")
            with urlopen(req,timeout=5) as response:
                assert json.loads(response.read())["ok"] is True
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/state",timeout=5) as response:
            state=json.loads(response.read())
        assert state["rows"]["A"]["saved"] and state["rows"]["B"]["saved"]
        assert [event["role"] for event in state["events"] if event["kind"]=="save"]==["A","B"]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
