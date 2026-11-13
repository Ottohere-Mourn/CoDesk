"""Frozen row-level Oracle for COMMUNITY-PANTRY1; evaluator reads saved kiosk state only."""
def checks(state,expected,key):
 if not state or not isinstance(state.get("volunteers"),list):
  return {"state_readable":False},0.0
 rows={r.get("id"):r for r in state["volunteers"]}
 wanted=expected[key]["rows"];out={"state_readable":True};passed=0
 for w in wanted:
  r=rows.get(w["id"])
  if key=="shift":
   ok=bool(r and r.get("shift_station")==w["station"] and r.get("shift_window")==w["window"] and r.get("shift_status")==w["status"])
  else:
   try:amount=round(float(r.get("claim_amount")),2) if r and r.get("claim_amount") is not None else None
   except (ValueError,TypeError):amount=None
   ok=bool(r and amount==w["amount"] and r.get("claim_status")==w["decision"] and r.get("claim_note")==w["note"])
  out[f"{w['id']}_{key}_exact"]=ok
  passed+=int(ok)
 out["records_correct"]=f"{passed}/{len(wanted)}"
 return out,(passed/len(wanted) if wanted else 0.0)
