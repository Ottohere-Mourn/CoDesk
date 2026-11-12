"""Arm-independent COURT-SERVICE1 business oracles."""
def filing_checks(state,exp):
 if not state:return {"state":"unreadable"},0.0
 w=exp["filing"];rows=[r for r in state["filings"] if r["case_id"]==w["case_id"]];r=rows[0] if len(rows)==1 else {}
 checks={"saved_to_SC208":len(rows)==1,"plaintiff_exact":r.get("plaintiff")==w["plaintiff"],"defendant_exact":r.get("defendant")==w["defendant"],
 "claim_amount_exact":float(r.get("amount") or 0)==w["amount"],"correct_complaint_attached":r.get("attachment")==w["attachment"],"ready_for_clerk_check":r.get("status")==w["status"]}
 return checks,sum(checks.values())/len(checks)
def service_checks(state,exp):
 if not state:return {"state":"unreadable"},0.0
 w=exp["service"];rows=[r for r in state["services"] if r["case_id"]==w["case_id"]];r=rows[0] if len(rows)==1 else {}
 checks={"saved_to_SC193":len(rows)==1,"service_date_exact":r.get("service_date")==w["service_date"],"method_exact":r.get("method")==w["method"],"server_id_exact":r.get("server_id")==w["server_id"],"served_outcome":r.get("outcome")==w["outcome"]}
 return checks,sum(checks.values())/len(checks)
