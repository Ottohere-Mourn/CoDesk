from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest
from oscombo.human_apps import code_review, access_review, transit_planner

def test_code_review_v022_user_flow_is_extended_and_requires_rc2_evidence():
    assert "RC-2" in code_review.USER_TASK
    assert len(code_review.user_actions()) == 10
    names = [a.name for a in code_review.user_actions()]
    assert names.index("open_release_candidate_handoff") < names.index("enter_qa_update")

def test_code_review_oracles_keep_tasks_separate(tmp_path: Path):
    dbp=tmp_path/"cr.sqlite3";code_review.create_fixture(dbp,"t")
    with sqlite3.connect(dbp) as db:
        db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                       [("/requirements/RET-30",),("/tests/PR-042",),("/build/BUILD-2026.11.09",),("/release/RC-2026.11.09-rc2",)])
        db.execute("INSERT INTO reviews(pr,line,decision,comment,at) VALUES(?,?,?,?,?)",
                   ("PR-042","20","request_changes","RET-30 includes returns submitted on day 30; use at most 30 so the boundary case passes.","now"))
        db.execute("UPDATE pr_state SET status='ready_for_qa',comment=?,revision=1 WHERE pr='PR-031'",
                   (code_review.USER_COMMENT,))
        db.execute("INSERT INTO request_log(method,path,status,at) VALUES('POST','/update-pr',200,'now')")
    result=code_review.evaluate(dbp)
    assert result["agent"]["success"] and result["user"]["success"]
    assert result["agent"]["review"]["pr"]=="PR-042"

def test_code_review_boundary_oracle_accepts_plain_language_and_rejects_wrong_operator(tmp_path: Path):
    for index, (comment, expected) in enumerate([
        ("RET-30 says the 30th day is eligible. Include the day-30 boundary; later submissions are outside policy.", True),
        ("The strict > 30 rejects day 30; change the condition to >= 30.", False),
    ]):
        dbp=tmp_path/f"cr-boundary-{index}.sqlite3";code_review.create_fixture(dbp,str(index))
        with sqlite3.connect(dbp) as db:
            db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                           [("/requirements/RET-30",),("/tests/PR-042",),("/build/BUILD-2026.11.09",),("/release/RC-2026.11.09-rc2",)])
            db.execute("INSERT INTO reviews(pr,line,decision,comment,at) VALUES(?,?,?,?,?)",
                       ("PR-042","20","request_changes",comment,"now"))
        result=code_review.evaluate(dbp)
        assert result["agent"]["checks"]["policy_boundary_explained"] is expected
def test_access_review_never_provisions_and_profile_is_independent(tmp_path: Path):
    dbp=tmp_path/"ar.sqlite3";access_review.create_fixture(dbp,"t")
    with sqlite3.connect(dbp) as db:
        db.executemany("INSERT INTO request_log(method,path,status,at) VALUES(?,?,200,'now')",[
            ("GET","/settings/security"),("GET","/guide/security-profile"),
            ("GET","/settings/security"),("POST","/profile"),("GET","/settings/security")])
        db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                       [(p,) for p in ("/request/AR-771","/directory/D-148","/roles","/policy/PRIV-4")])
        db.execute("INSERT INTO access_reviews(request_id,decision,role,duration_days,policy_ref,rationale,provisioned) VALUES(?,?,?,?,?,?,0)",
                   ("AR-771","approve_scoped","REPORT_VIEWER",30,"PRIV-4","Aggregate reporting needs no PII; PRIV-4 applies."))
        db.execute("UPDATE profile SET recovery_email=?,security_alerts=1,revision=1 WHERE user_id='SAM'",
                   (access_review.USER_EMAIL,))
    result=access_review.evaluate(dbp)
    assert result["agent"]["success"] and result["user"]["success"]


def test_access_profile_page_renders_saved_settings_for_post_save_verification(tmp_path: Path):
    from threading import Thread
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    dbp=tmp_path/"ar-web.sqlite3";access_review.create_fixture(dbp,"web")
    server=access_review.make_server(dbp);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_address[1]}"
    try:
        before=urlopen(base+"/settings/security").read().decode()
        guide=urlopen(base+"/guide/security-profile").read().decode()
        assert "sam.old@example.test" in before and "checked" not in before
        assert "Recovery address" in guide and "Sign-in alerts" in guide
        data=urlencode({"recovery_email":access_review.USER_EMAIL,"security_alerts":"on"}).encode()
        confirmation=urlopen(Request(base+"/profile",data=data,method="POST")).read().decode()
        reopened=urlopen(base+"/settings/security").read().decode()
        assert "Security profile saved" in confirmation and access_review.USER_EMAIL in confirmation
        assert access_review.USER_EMAIL in reopened
        assert "name='security_alerts' value='on' checked" in reopened
        result=access_review.evaluate(dbp)
        assert result["user"]["success"]
        with sqlite3.connect(dbp) as db: db.execute("DELETE FROM request_log WHERE method='GET' AND path='/settings/security' AND seq=(SELECT MAX(seq) FROM request_log)")
        assert access_review.evaluate(dbp)["user"]["success"] is False
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)

def test_transit_oracles_check_accessibility_arrival_and_favorite(tmp_path: Path):
    dbp=tmp_path/"tp.sqlite3";transit_planner.create_fixture(dbp,"t")
    with sqlite3.connect(dbp) as db:
        db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                       [(p,) for p in ("/network","/disruptions/D-711","/stations/Riverside-Park","/guide/step-free")])
        db.execute("INSERT INTO itineraries(name,travel_date,origin,destination,route_code,departure,arrive_by,step_free,note,ticket_booked) VALUES(?,?,?,?,?,?,?,?,?,0)",
                   ("Museum visit - accessible route","2026-11-19","Oak Wharf","Civic Museum","R4-R5","09:15","10:15",1,"Riverside avoids Central elevator outage."))
        db.execute("INSERT INTO favorites(station,list_name,created_utc) VALUES(?,?,?)",
                   ("Riverside Park","Personal","now"))
        db.execute("INSERT INTO request_log(method,path,status,at) VALUES('POST','/favorite',200,'now')")
        db.execute("INSERT INTO request_log(method,path,status,at) VALUES('GET','/favorites',200,'now')")
    result=transit_planner.evaluate(dbp)
    assert result["agent"]["success"] and result["user"]["success"]

def test_transit_saved_places_page_renders_persisted_favorite(tmp_path: Path):
    from threading import Thread
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    dbp=tmp_path/"tp-web.sqlite3";transit_planner.create_fixture(dbp,"web")
    server=transit_planner.make_server(dbp);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_address[1]}"
    try:
        urlopen(base+"/network").read()
        urlopen(base+"/disruptions/D-711").read()
        urlopen(base+"/stations/Riverside-Park").read()
        data=urlencode({"station":"Riverside Park","list_name":"Personal"}).encode()
        confirmation=urlopen(Request(base+"/favorite",data=data,method="POST")).read().decode()
        saved=urlopen(base+"/favorites").read().decode()
        assert "Riverside Park has been saved to Personal" in confirmation
        assert "Riverside Park - Personal" in saved
        assert transit_planner.evaluate(dbp)["user"]["success"]
        with sqlite3.connect(dbp) as db: db.execute("DELETE FROM request_log WHERE method='GET' AND path='/favorites' AND seq=(SELECT MAX(seq) FROM request_log)")
        assert transit_planner.evaluate(dbp)["user"]["success"] is False
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_revised_user_scripts_are_sustained_and_end_with_reopen_verification():
    access_names=[a.name for a in access_review.user_actions()]
    transit_names=[a.name for a in transit_planner.user_actions()]
    assert access_review.CASE_VERSION=="0.2.1" and len(access_names)==10
    assert access_names.index("read_signin_alert_guidance") < access_names.index("enable_alerts_and_save") < access_names.index("verify_persisted_security_settings")
    assert transit_planner.CASE_VERSION=="0.2.2" and len(transit_names)==13
    assert transit_names.index("read_central_lift_service_alert") < transit_names.index("save_personal_favorite") < transit_names.index("verify_persisted_favorite")
    assert "service alert" in transit_planner.USER_TASK and "verify" in transit_planner.USER_TASK.lower()


@pytest.mark.parametrize("app", [code_review,access_review,transit_planner])
def test_fixture_deterministic_basis(app,tmp_path):
    a=tmp_path/"a.sqlite3";b=tmp_path/"b.sqlite3"
    ma=app.create_fixture(a,"a");mb=app.create_fixture(b,"b")
    assert ma["fixture_id"]==mb["fixture_id"]==app.FIXTURE_ID
    assert ma["initial_state"]==mb["initial_state"]
    assert app.evaluate(a)["agent"]["success"] is False
    assert app.evaluate(a)["user"]["success"] is False
    server=app.make_server(a,"127.0.0.1",0)
    assert server.server_address[1]>0
    server.server_close()



def test_access_rationale_accepts_equivalent_scope_language(tmp_path: Path):
    for index, rationale in enumerate([
        "Aggregate cohort analysis does not require customer identifiers. PRIV-4 allows this scoped role.",
        "Aggregate retention needs no personal information. PRIV-4 limits access to report viewer.",
    ]):
        dbp=tmp_path/f"ar-scope-{index}.sqlite3";access_review.create_fixture(dbp,str(index))
        with sqlite3.connect(dbp) as db:
            db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                           [(p,) for p in ("/request/AR-771","/directory/D-148","/roles","/policy/PRIV-4","/guide/security-profile")])
            db.execute("INSERT INTO access_reviews(request_id,decision,role,duration_days,policy_ref,rationale,provisioned) VALUES(?,?,?,?,?,?,0)",
                       ("AR-771","approve_scoped","REPORT_VIEWER",30,"PRIV-4",rationale))
        assert access_review.evaluate(dbp)["agent"]["checks"]["rationale_explains_scope"] is True


def test_transit_oracle_accepts_lift_synonym_from_fixture(tmp_path: Path):
    dbp=tmp_path/"tp-lift.sqlite3";transit_planner.create_fixture(dbp,"lift")
    with sqlite3.connect(dbp) as db:
        db.executemany("INSERT INTO request_log(method,path,status,at) VALUES('GET',?,200,'now')",
                       [(p,) for p in ("/network","/disruptions/D-711","/guide/step-free","/stations/Riverside-Park")])
        db.execute("INSERT INTO itineraries(name,travel_date,origin,destination,route_code,departure,arrive_by,step_free,note,ticket_booked) VALUES(?,?,?,?,?,?,?,?,?,0)",
                   ("Museum visit - accessible route","2026-11-19","Oak Wharf","Civic Museum","R4-R5","09:15","10:15",1,
                    "R4-R5 uses Riverside Park; Central Station lift is out of service 08:00-12:00."))
    assert transit_planner.evaluate(dbp)["agent"]["checks"]["avoids_central_elevator_outage"] is True
