"""SHELTER-INTAKE1 pair setup and Guest-backed read-only evaluation."""
from __future__ import annotations
from evaluation_examples.task_class.pg_common import expected, open_chrome, result, sql, start_webapp, webapp_db
from evaluation_examples.task_class.pg_shelter1_oracle import placement_checks, facilities_checks
NAME,PORT='s1',8131
URL=f'http://127.0.0.1:{PORT}/'
def setup(sc):
    start_webapp(sc,f'{NAME}/app_s1.py',NAME,PORT,f'{NAME}/seed.db')
    open_chrome(sc,[URL])
def _read(env,exp):
    iid=exp['required_closure']['inspection']
    return sql(env,webapp_db(NAME),{
      'rooms':'SELECT id,capacity,accessible,companion,status FROM rooms ORDER BY id',
      'assignments':'SELECT family_id,room_id,occupants,status,note FROM assignments ORDER BY id',
      'closures':f"SELECT room_id,inspection_id,reason,status FROM closures WHERE inspection_id='{iid}' ORDER BY id",
      'work_orders':f"SELECT room_id,inspection_id,priority,status,note FROM work_orders WHERE inspection_id='{iid}' ORDER BY id",
      'events':'SELECT action,target,details,ts FROM events ORDER BY id'})
def evaluate_intake(env,dest):
    exp=expected(NAME); st=_read(env,exp); checks,score=placement_checks(st,exp); return result(score,checks)
def evaluate_facilities(env,dest):
    exp=expected(NAME); st=_read(env,exp); checks,score=facilities_checks(st,exp); return result(score,checks)
