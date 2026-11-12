"""Arm-independent ROUTE-RECON1 business oracles."""
def route_checks(st,exp):
 if not st:return {"state":"unreadable"},0.0
 w=exp["route"];rr=[r for r in st["routes"] if r["route_id"]==w["route_id"]];r=rr[0] if len(rr)==1 else {}
 stops=[x["job_id"] for x in st["stops"] if x["route_id"]==w["route_id"]];status={x["id"]:x["status"] for x in st["jobs"]}
 checks={"route_saved":len(rr)==1,"service_date_exact":r.get("service_date")==w["service_date"],"vehicle_exact":r.get("vehicle")==w["vehicle"],
 "departure_exact":r.get("depart_time")==w["depart_time"],"draft_status":r.get("status")==w["status"],
 "released_manifest_order_exact":stops==w["sequence"],"every_stop_still_scheduled":all(status.get(j)=="Scheduled" for j in stops)}
 return checks,sum(checks.values())/len(checks)
def update_checks(st,exp):
 if not st:return {"state":"unreadable"},0.0
 w=exp["update"];rows=[x for x in st["jobs"] if x["id"]==w["job_id"]];r=rows[0] if len(rows)==1 else {}
 checks={"target_job_updated":len(rows)==1,"deferred_status":r.get("status")==w["status"],"rescheduled_date":r.get("service_date")==w["service_date"],"customer_note_exact":r.get("note")==w["note"]}
 return checks,sum(checks.values())/len(checks)
