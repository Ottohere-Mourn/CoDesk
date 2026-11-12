"""ROUTE-LIVE1 pair setup and evaluator."""
from evaluation_examples.task_class.pg_common import expected, open_chrome, result, sql, start_webapp, webapp_db

NAME, PORT = "q1", 8134
URL = f"http://127.0.0.1:{PORT}/"

def setup(sc):
    start_webapp(sc, f"{NAME}/app_q1.py", NAME, PORT, f"{NAME}/seed.db")
    open_chrome(sc, [URL])

def state(env):
    return sql(env, webapp_db(NAME), {
        "routes": "SELECT route_id,service_date,vehicle,depart_time,status FROM routes ORDER BY route_id",
        "stops": "SELECT route_id,position,job_id FROM route_stops ORDER BY route_id,position",
        "jobs": "SELECT id,service_date,status,note FROM jobs ORDER BY id",
    })

def evaluate_route(env, dest):
    from evaluation_examples.task_class.pg_q1_oracle import route_checks
    checks, score = route_checks(state(env), expected(NAME))
    return result(score, checks)

def evaluate_update(env, dest):
    from evaluation_examples.task_class.pg_q1_oracle import update_checks
    checks, score = update_checks(state(env), expected(NAME))
    return result(score, checks)
