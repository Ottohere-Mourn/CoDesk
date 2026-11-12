"""ROUTE-RECON1 pair setup and evaluator."""
from evaluation_examples.task_class.pg_common import expected,open_chrome,result,sql,start_webapp,webapp_db
NAME,PORT="k2",8133
URL=f"http://127.0.0.1:{PORT}/"
def setup(sc):
 start_webapp(sc,f"{NAME}/app_k2.py",NAME,PORT,f"{NAME}/seed.db");open_chrome(sc,[URL])
def state(env):
 return sql(env,webapp_db(NAME),{"routes":"SELECT route_id,service_date,vehicle,depart_time,status FROM routes ORDER BY route_id",
 "stops":"SELECT route_id,position,job_id FROM route_stops ORDER BY route_id,position","jobs":"SELECT id,service_date,status,note FROM jobs ORDER BY id"})
def evaluate_route(env,dest):
 from evaluation_examples.task_class.pg_k2_oracle import route_checks
 st=state(env);checks,score=route_checks(st,expected(NAME));return result(score,checks)
def evaluate_update(env,dest):
 from evaluation_examples.task_class.pg_k2_oracle import update_checks
 st=state(env);checks,score=update_checks(st,expected(NAME));return result(score,checks)
