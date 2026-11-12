from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest
from oscombo.human_apps import consumer_banking, lab_qc, home_energy

APPS=[consumer_banking,lab_qc,home_energy]

@pytest.mark.parametrize("app", APPS)
def test_new_case_fixture_starts_with_both_tasks_unfinished(app,tmp_path):
    db=tmp_path/(app.FIXTURE_ID+".sqlite3")
    manifest=app.create_fixture(db,"preflight")
    assert manifest["fixture_id"]==app.FIXTURE_ID
    assert app.evaluate(db)["agent"]["success"] is False
    assert app.evaluate(db)["user"]["success"] is False
    assert app.AGENT_TASK and app.USER_TASK and app.SHARED_STATE

@pytest.mark.parametrize("app", APPS)
def test_scripted_user_flow_is_sustained_and_finishes_with_verification(app):
    actions=app.user_actions()
    assert len(actions)>=12
    assert len({a.name for a in actions})==len(actions)
    names=[a.name for a in actions]
    assert any("review" in n or "confirmation" in n for n in names)
    assert any("verify" in n for n in names)


def _log(db, method, path):
    db.execute("INSERT INTO request_log(method,path,status,at) VALUES(?,?,200,'now')",(method,path))

def test_finance_actor_oracles_do_not_confuse_users_payment_with_agent_side_effect(tmp_path):
    dbp=tmp_path/"finance.sqlite3";consumer_banking.create_fixture(dbp,"both")
    with sqlite3.connect(dbp) as db:
        for path in ("/card-activity","/transaction/T-821","/transaction/T-822","/transaction/T-823","/guide/spending","/review-card"):_log(db,"GET",path)
        _log(db,"POST","/review-card")
        db.executemany("INSERT INTO card_reviews(txn_id,category,action,note,created_utc) VALUES(?,?,?,?,?)",[
            ("T-821","Software subscriptions","approve","Cloud software subscription; recurring workspace expense.","now"),
            ("T-822","Meals","approve","Team meal with itemized receipt attached.","now"),
            ("T-823","Office equipment","request_receipt","$376 equipment purchase is over threshold; no receipt attached.","now")])
        _log(db,"GET","/bill/ELEC-208");_log(db,"GET","/help/payment-timing");_log(db,"GET","/bill/pay");_log(db,"POST","/bill/pay")
        db.execute("INSERT INTO payments(bill_id,account,amount,pay_date,memo,status,created_utc) VALUES('ELEC-208','Household Checking',68.40,'2026-11-18','November household electric','scheduled','now')")
        db.execute("UPDATE bills SET status='scheduled' WHERE bill_id='ELEC-208'");_log(db,"GET","/payment-history")
    result=consumer_banking.evaluate(dbp)
    assert result["agent"]["success"], result["agent"]["checks"]
    assert result["user"]["success"], result["user"]["checks"]


def test_lab_qc_and_user_accession_oracles_are_actor_separated(tmp_path):
    dbp=tmp_path/"lab.sqlite3";lab_qc.create_fixture(dbp,"both")
    with sqlite3.connect(dbp) as db:
        for path in ("/worklist","/batch/B-615","/qc/QC-615","/sop/QC-SOP-3"):_log(db,"GET",path)
        _log(db,"POST","/batch-review")
        db.execute("INSERT INTO batch_reviews(batch_id,disposition,note,created_utc) VALUES('B-615','hold_retest','QC-H615 is above accepted range; request repeat control run.','now')")
        db.execute("UPDATE qc_batches SET status='hold_retest' WHERE batch_id='B-615'")
        for path in ("/receipt/AC-508","/guide/intake","/accession/new"):_log(db,"GET",path)
        _log(db,"POST","/accession/new")
        db.execute("INSERT INTO accessions(accession_id,collection_date,sample_type,collection_site,coc_id,storage_location,created_utc) VALUES(?,?,?,?,?,?,?)",tuple(lab_qc.SAMPLE[k] for k in ("accession_id","collection_date","sample_type","collection_site","coc_id","storage_location"))+("now",))
        _log(db,"GET","/accession/AC-508")
    result=lab_qc.evaluate(dbp)
    assert result["agent"]["success"], result["agent"]["checks"]
    assert result["user"]["success"], result["user"]["checks"]


def test_home_energy_oracles_allow_both_expected_device_updates(tmp_path):
    dbp=tmp_path/"energy.sqlite3";home_energy.create_fixture(dbp,"both")
    with sqlite3.connect(dbp) as db:
        for path in ("/usage","/tariff/TOU-4","/device/EV-4"):_log(db,"GET",path)
        _log(db,"POST","/ev-schedule")
        db.execute("INSERT INTO ev_schedules(device_id,name,days,start_time,end_time,target_kwh,max_kw,departure,status,created_utc) VALUES(?,?,?,?,?,?,?,?,?,?)",("EV-4","Overnight off-peak charge","Weekdays","00:30","04:30",28.0,7.2,"06:00","scheduled","now"))
        _log(db,"GET","/thermostat/THERM-STUDY");_log(db,"GET","/guide/comfort");_log(db,"GET","/thermostat/schedule");_log(db,"POST","/thermostat/schedule")
        db.execute("INSERT INTO thermostat_schedules(device_id,days,start_time,end_time,setpoint_f,status,created_utc) VALUES(?,?,?,?,?,'scheduled','now')",("THERM-STUDY","Weekdays","18:00","22:00",68))
        _log(db,"GET","/thermostat/THERM-STUDY")
    result=home_energy.evaluate(dbp)
    assert result["agent"]["success"], result["agent"]["checks"]
    assert result["user"]["success"], result["user"]["checks"]


def test_lab_queue_offers_a_persisted_saved_accession_for_reopen(tmp_path):
    from threading import Thread
    from urllib.parse import urlencode
    from urllib.request import Request,urlopen
    dbp=tmp_path/"lab-web.sqlite3";lab_qc.create_fixture(dbp,"web")
    server=lab_qc.make_server(dbp);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_address[1]}"
    try:
        form=urlencode({k:lab_qc.SAMPLE[k] for k in ("accession_id","collection_date","sample_type","collection_site","coc_id","storage_location")}).encode()
        confirmation=urlopen(Request(base+"/accession/new",data=form,method="POST")).read().decode()
        queue=urlopen(base+"/accessions").read().decode()
        reopened=urlopen(base+"/accession/AC-508").read().decode()
        assert "Accession confirmation" in confirmation
        assert "Accessioned · reopen saved record" in queue and "href='/accession/AC-508'" in queue
        assert "Cold Room Rack R2-B14" in reopened
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
