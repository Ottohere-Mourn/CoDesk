from __future__ import annotations
import json, sqlite3, urllib.parse, urllib.request
from pathlib import Path
from oscombo.human_apps.calendar_planning import (
    AGENT_EVENT, AGENT_ROOM, CASE_ID, FIXTURE_ID, USER_EVENT, create_fixture,
    evaluate, make_server,
)

def _post(base: str, fields: dict[str,str]) -> str:
    data=urllib.parse.urlencode(fields).encode()
    req=urllib.request.Request(base+"/event/save",data=data,headers={"Content-Type":"application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req,timeout=5) as response:
        return response.read().decode()

def _server(db: Path):
    server=make_server(db,host="127.0.0.1",port=0)
    import threading
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server,thread,f"http://127.0.0.1:{server.server_port}"

def test_empty_fixture_is_not_a_pass(tmp_path: Path):
    db=tmp_path/"calendar.sqlite3";manifest=create_fixture(db,"empty")
    result=evaluate(db)
    assert manifest["fixture_id"]==FIXTURE_ID
    assert not result["agent"]["success"] and not result["user"]["success"]

def test_both_independent_tasks_pass_and_sources_are_logged(tmp_path: Path):
    db=tmp_path/"calendar.sqlite3";manifest=create_fixture(db,"full")
    server,thread,base=_server(db)
    try:
        for path in ("/calendar","/brief","/availability","/rooms"):
            with urllib.request.urlopen(base+path,timeout=5) as r:
                assert r.status==200
                page=r.read().decode()
                assert "CoDesk Calendar" in page
        agent={"calendar_id":"team","title":AGENT_EVENT,"event_date":"2026-11-17","start_time":"10:30","end_time":"11:00",
          "room":AGENT_ROOM,"attendees":"Ava Chen, Eli Brooks, Mina Patel","agenda":"Review blockers, assign owners, and confirm go/no-go criteria.",
          "reminder_min":"none","invite_status":"draft"}
        user={"calendar_id":"personal","title":USER_EVENT,"event_date":"2026-11-20","start_time":"13:00","end_time":"13:45",
          "room":"","attendees":"","agenda":"","reminder_min":"10","invite_status":"none"}
        _post(base,agent);_post(base,user)
        result=evaluate(db)
        assert result["agent"]["success"],result["agent"]
        assert result["user"]["success"],result["user"]
        assert result["agent"]["observed_source_sha256"]==manifest["source_content_sha256"]
        with sqlite3.connect(db) as conn:
            paths={r[0] for r in conn.execute("select path from request_log where method='GET'")}
        assert {"/calendar","/brief","/availability","/rooms"}<=paths
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

def test_wrong_calendar_or_invite_send_fails_agent_oracle(tmp_path: Path):
    db=tmp_path/"calendar.sqlite3";create_fixture(db,"negative")
    server,thread,base=_server(db)
    try:
        for p in ("/brief","/availability","/rooms"):
            urllib.request.urlopen(base+p,timeout=5).read()
        _post(base,{"calendar_id":"personal","title":AGENT_EVENT,"event_date":"2026-11-17","start_time":"10:30","end_time":"11:00",
          "room":AGENT_ROOM,"attendees":"Ava Chen, Eli Brooks, Mina Patel","agenda":"Review blockers, assign owners, and confirm go/no-go criteria.",
          "reminder_min":"none","invite_status":"send"})
        result=evaluate(db)
        assert not result["agent"]["success"]
        assert not result["agent"]["checks"]["correct_calendar"]
        assert not result["agent"]["checks"]["invite_left_as_draft"]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

def test_fixture_sources_are_reproducible(tmp_path: Path):
    left=create_fixture(tmp_path/"left.sqlite3","left");right=create_fixture(tmp_path/"right.sqlite3","right")
    assert left["source_content_sha256"]==right["source_content_sha256"]
    assert left["initial_state"]==right["initial_state"] and left["initial_state"]["event_count"]==0
    assert left["sha256"]!=right["sha256"]

def test_meeting_fixture_has_one_feasible_candidate(tmp_path: Path):
    db=tmp_path/"calendar.sqlite3";create_fixture(db,"feasible")
    with sqlite3.connect(db) as conn:
        rows=conn.execute("select person,day,time_range from availability").fetchall()
        rooms=conn.execute("select room,capacity,day,time_range,status from room_windows").fetchall()
    # Only Tuesday has a 30-minute overlap for all three invitees and a room
    # with the required four seats; Wednesday's participant overlap is absent.
    def mins(span):
        left,right=span.split("-")
        def cv(v):
            h,m=map(int,v.split(":"));return h*60+m
        return cv(left),cv(right)
    by={day:[] for day in ("Tue Nov 17","Wed Nov 18")}
    for person,day,span in rows:by[day].append((person,mins(span)))
    roomdays={day:[] for day in by}
    for room,capacity,day,span,status in rooms:
        if status=="Available" and capacity>=4:roomdays[day].append((room,mins(span)))
    candidates=[]
    for day,people in by.items():
        common_start=max(mins[1][0] for mins in people);common_end=min(mins[1][1] for mins in people)
        for room,(start,end) in roomdays[day]:
            if min(common_end,end)-max(common_start,start)>=30:candidates.append(day)
    assert candidates==["Tue Nov 17"]
