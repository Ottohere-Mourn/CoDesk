"""State-aware route oracle for ROUTE-LIVE1; the route must match the final job statuses."""
def route_checks(st, exp):
    if not st:
        return {"state": "unreadable"}, 0.0
    w = exp["route"]
    routes = [r for r in st["routes"] if r["route_id"] == w["route_id"]]
    route = routes[0] if len(routes) == 1 else {}
    stops = [x["job_id"] for x in st["stops"] if x["route_id"] == w["route_id"]]
    status = {x["id"]: x["status"] for x in st["jobs"]}
    scheduled_in_manifest = [job for job in w["manifest_sequence"] if status.get(job) == "Scheduled"]
    checks = {
        "route_saved": len(routes) == 1,
        "service_date_exact": route.get("service_date") == w["service_date"],
        "vehicle_exact": route.get("vehicle") == w["vehicle"],
        "departure_exact": route.get("depart_time") == w["depart_time"],
        "draft_status": route.get("status") == w["status"],
        "route_matches_current_scheduled_manifest": stops == scheduled_in_manifest,
        "every_stop_currently_scheduled": all(status.get(job) == "Scheduled" for job in stops),
    }
    return checks, sum(checks.values()) / len(checks)

def update_checks(st, exp):
    if not st:
        return {"state": "unreadable"}, 0.0
    w = exp["update"]
    rows = [x for x in st["jobs"] if x["id"] == w["job_id"]]
    row = rows[0] if len(rows) == 1 else {}
    checks = {
        "target_job_updated": len(rows) == 1,
        "deferred_status": row.get("status") == w["status"],
        "rescheduled_date": row.get("service_date") == w["service_date"],
        "customer_note_exact": row.get("note") == w["note"],
    }
    return checks, sum(checks.values()) / len(checks)
