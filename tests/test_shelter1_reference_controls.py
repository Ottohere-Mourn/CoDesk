"""Positive, exposure-negative, and recovery controls for the SHELTER-INTAKE1 oracle."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
import pytest
from tasks.paragui.build_s1 import build
from tasks.paragui.pg_shelter1_oracle import placement_checks, facilities_checks

@pytest.fixture
def fixture(tmp_path):
    out=tmp_path/'s1'; build(str(out)); exp=json.loads((out/'expected.json').read_text()); db=out/'seed.db'
    return db,exp

def get_state(db):
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row
    out={k:[dict(r) for r in c.execute(q)] for k,q in {
      'rooms':'SELECT id,capacity,accessible,companion,status FROM rooms',
      'assignments':'SELECT family_id,room_id,occupants,status,note FROM assignments',
      'closures':'SELECT room_id,inspection_id,reason,status FROM closures',
      'work_orders':'SELECT room_id,inspection_id,priority,status,note FROM work_orders'}.items()}
    c.close(); return out

def add_reference_placements(db):
    c=sqlite3.connect(db); refs={'H-101':'MP-105','H-102':'CR-203','H-103':'CR-201','H-104':'MP-108'}
    for fid,rid in refs.items():
        occ=c.execute('SELECT adults+children FROM families WHERE id=?',(fid,)).fetchone()[0]
        c.execute('INSERT INTO assignments(family_id,room_id,occupants,status,note,saved_at) VALUES(?,?,?,?,?,?)',(fid,rid,occ,'draft','intake reviewed','2026-11-12T10:00:00'))
    c.commit(); c.close()

def close_room(db):
    c=sqlite3.connect(db); c.execute("UPDATE rooms SET status='Closed',capacity=0 WHERE id='CR-201'")
    c.execute("INSERT INTO closures(room_id,inspection_id,reason,status,saved_at) VALUES('CR-201','SAFE-204','Electrical burning odor at west outlet','Closed','2026-11-12T10:01:00')")
    c.execute("INSERT INTO work_orders(room_id,inspection_id,priority,status,note,created_at) VALUES('CR-201','SAFE-204','High','Open','Inspect and isolate west outlet before reopening','2026-11-12T10:01:00')")
    c.commit(); c.close()

def test_intake_reference_passes_on_untouched_board(fixture):
    db,exp=fixture; add_reference_placements(db)
    checks,score=placement_checks(get_state(db),exp)
    assert score==1.0 and checks['all_four_households_correct'] and checks['no_room_over_capacity']

def test_facilities_reference_passes_and_records_work_order(fixture):
    db,exp=fixture; close_room(db)
    checks,score=facilities_checks(get_state(db),exp)
    assert score==1.0 and all(checks.values())

def test_stale_placement_fails_only_after_shared_closure(fixture):
    db,exp=fixture; add_reference_placements(db); close_room(db)
    checks,score=placement_checks(get_state(db),exp)
    assert score<1.0 and checks['H-103']['open_and_fits'] is False

def test_closure_removes_the_only_safe_four_person_room(fixture):
    db,exp=fixture; add_reference_placements(db); close_room(db)
    checks,score=placement_checks(get_state(db),exp)
    assert score<1.0 and checks['H-103']['open_and_fits'] is False
    assert exp['rooms']['CR-201']['capacity']==4
    assert max(r['capacity'] for rid,r in exp['rooms'].items() if rid!='CR-201')==3


def test_untouched_board_scores_zero_not_vacuous_half_credit(fixture):
    db,exp=fixture
    checks,score=placement_checks(get_state(db),exp)
    assert score==0.0 and checks["any_assignment_saved"] is False
