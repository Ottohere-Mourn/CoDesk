from __future__ import annotations
import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

from oscombo.human_apps.mail_workflow import (
    CASE_ID, CUSTOMER_EMAIL, CUSTOMER_THREAD, OPS_EMAIL, USER_REPLY, USER_THREAD,
    create_fixture, evaluate, make_server,
)

def _post(base: str, path: str, fields: dict[str, str]) -> str:
    data=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request(base+path,data=data,headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req,timeout=5) as response:
        return response.read().decode()

def test_empty_fixture_is_not_a_pass(tmp_path: Path):
    db=tmp_path/"mail.sqlite3"
    manifest=create_fixture(db,"empty-test")
    result=evaluate(db)
    assert manifest["fixture_id"]=="shared-mailbox-customer-review-and-ops-reply-v1"
    assert not result["agent"]["success"]
    assert not result["user"]["success"]
    assert "customer_email" not in json.dumps(manifest).lower()

def test_full_normal_workflows_pass_and_are_logged(tmp_path: Path):
    db=tmp_path/"mail.sqlite3"
    manifest=create_fixture(db,"http-test")
    server=make_server(db,host="127.0.0.1",port=0)
    import threading
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base+"/mail",timeout=5) as response:
            inbox=response.read().decode()
        assert "Damaged dock on order SO-7718" in inbox and "Afternoon queue coverage" in inbox
        with urllib.request.urlopen(base+f"/thread/{CUSTOMER_THREAD}",timeout=5) as response:
            case_page=response.read().decode()
        assert "DLV-7718" in case_page and "Save review" in case_page
        with urllib.request.urlopen(base+"/policy/POL-WAR-3",timeout=5) as response:
            assert "two business days" in response.read().decode()
        _post(base,"/review",{"thread_id":CUSTOMER_THREAD,"label":"replacement_eligible","priority":"P2"})
        draft=("Hi Casey, I am sorry your dock was damaged during delivery. We will arrange a replacement. "
               "It should dispatch within two business days, and we will send tracking details afterward.")
        _post(base,"/reply/submit",{"thread_id":CUSTOMER_THREAD,"recipient":CUSTOMER_EMAIL,
            "subject":"Re: Damaged dock on order SO-7718","body":draft,"action":"draft"})
        _post(base,"/reply/submit",{"thread_id":USER_THREAD,"recipient":OPS_EMAIL,
            "subject":"Re: Afternoon queue coverage","body":USER_REPLY,"action":"send"})
        _post(base,"/thread/done",{"thread_id":USER_THREAD})
        result=evaluate(db)
        assert result["agent"]["success"], result["agent"]
        assert result["user"]["success"], result["user"]
        assert manifest["source_content_sha256"]==result["agent"]["observed_source_sha256"]
        with sqlite3.connect(db) as conn:
            paths=[r[0] for r in conn.execute("select path from request_log")]
        assert "/thread/CUST-2048" in paths and "/policy/POL-WAR-3" in paths
        assert "/reply/submit" in paths and "/thread/done" in paths
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

def test_wrong_recipient_and_customer_send_fail_oracles(tmp_path: Path):
    db=tmp_path/"mail.sqlite3";create_fixture(db,"negative-test")
    server=make_server(db,host="127.0.0.1",port=0)
    import threading
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        _post(base,"/review",{"thread_id":CUSTOMER_THREAD,"label":"replacement_eligible","priority":"P2"})
        body="Hi Casey, sorry for the damage. We will arrange a replacement within two business days."
        # A customer-facing send is deliberately not equivalent to the requested safe draft.
        _post(base,"/reply/submit",{"thread_id":CUSTOMER_THREAD,"recipient":CUSTOMER_EMAIL,
            "subject":"Re: Damaged dock on order SO-7718","body":body,"action":"send"})
        _post(base,"/reply/submit",{"thread_id":USER_THREAD,"recipient":"wrong@company.test",
            "subject":"Re: Afternoon queue coverage","body":USER_REPLY,"action":"send"})
        _post(base,"/thread/done",{"thread_id":USER_THREAD})
        result=evaluate(db)
        assert not result["agent"]["success"]
        assert not result["agent"]["checks"]["draft_not_sent"]
        assert not result["user"]["success"]
        assert not result["user"]["checks"]["correct_recipient"]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

def test_fixture_content_is_deterministic_across_run_ids(tmp_path: Path):
    left=create_fixture(tmp_path/"left.sqlite3","left")
    right=create_fixture(tmp_path/"right.sqlite3","right")
    assert left["source_content_sha256"]==right["source_content_sha256"]
    assert left["initial_state"]==right["initial_state"]
    assert left["sha256"]!=right["sha256"] # run provenance remains distinct
