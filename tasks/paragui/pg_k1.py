"""COURT-SERVICE1 pair setup and read-only evaluation."""
from evaluation_examples.task_class.pg_common import expected,open_chrome,result,sql,start_webapp,webapp_db
NAME,PORT="k1",8132
URL=f"http://127.0.0.1:{PORT}/"
def setup(sc):
 start_webapp(sc,f"{NAME}/app_k1.py",NAME,PORT,f"{NAME}/seed.db");open_chrome(sc,[URL])
def state(env):
 return sql(env,webapp_db(NAME),{"filings":"SELECT case_id,plaintiff,defendant,amount,attachment,status FROM filings ORDER BY case_id","services":"SELECT case_id,service_date,method,server_id,outcome FROM services ORDER BY case_id","events":"SELECT action,case_id,details,ts FROM events ORDER BY id"})
def evaluate_filing(env,dest):
 from evaluation_examples.task_class.pg_k1_oracle import filing_checks
 st=state(env);checks,score=filing_checks(st,expected(NAME));return result(score,checks)
def evaluate_service(env,dest):
 from evaluation_examples.task_class.pg_k1_oracle import service_checks
 st=state(env);checks,score=service_checks(st,expected(NAME));return result(score,checks)
