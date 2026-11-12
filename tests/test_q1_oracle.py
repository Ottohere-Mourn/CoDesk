from tasks.paragui.pg_q1_oracle import route_checks, update_checks

EXPECTED = {
    "route": {"route_id":"RTE-17", "service_date":"2026-11-13", "vehicle":"Van 4", "depart_time":"08:00", "status":"Draft", "manifest_sequence":["WO-501","WO-502","WO-503","WO-504"]},
    "update": {"job_id":"WO-503", "status":"Deferred", "service_date":"2026-11-14", "note":"Customer requested Saturday access; no Friday attendance."},
}
def state(route_stops, defer=True):
    return {
        "routes":[{"route_id":"RTE-17","service_date":"2026-11-13","vehicle":"Van 4","depart_time":"08:00","status":"Draft"}],
        "stops":[{"route_id":"RTE-17","position":i+1,"job_id":job} for i,job in enumerate(route_stops)],
        "jobs":[{"id":job,"service_date":"2026-11-13","status":("Deferred" if defer and job=="WO-503" else "Scheduled"),"note":""} for job in EXPECTED["route"]["manifest_sequence"]],
    }
def test_joint_terminal_state_possible_after_defer_then_route_refresh():
    st=state(["WO-501","WO-502","WO-504"])
    assert route_checks(st, EXPECTED)[1] == 1.0
    st["jobs"][2].update(status="Deferred",service_date="2026-11-14",note=EXPECTED["update"]["note"])
    assert update_checks(st, EXPECTED)[1] == 1.0
def test_stale_route_detected_if_defer_happens_after_route_saved():
    st=state(["WO-501","WO-502","WO-503","WO-504"], defer=False)
    assert route_checks(st, EXPECTED)[1] == 1.0
    st["jobs"][2].update(status="Deferred",service_date="2026-11-14",note=EXPECTED["update"]["note"])
    route_score=route_checks(st, EXPECTED)[1]
    assert route_score < 1.0
    assert update_checks(st, EXPECTED)[1] == 1.0
def test_independent_guest_goals_both_pass():
    route_guest=state(["WO-501","WO-502","WO-503","WO-504"],defer=False)
    defer_guest=state([],defer=True)
    defer_guest["jobs"][2].update(status="Deferred",service_date="2026-11-14",note=EXPECTED["update"]["note"])
    assert route_checks(route_guest,EXPECTED)[1] == 1.0
    assert update_checks(defer_guest,EXPECTED)[1] == 1.0
