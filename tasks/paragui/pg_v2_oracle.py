"""Independent correctness oracle for bin-stock and parcel-stock print batches."""
def checks(state,expected,key):
 if not state:return {"state_readable":False},0.0
 spec=expected[key];jobs=state.get("jobs",[]);checks={"state_readable":True}
 for item in spec["labels"]:
  hits=[j for j in jobs if int(j.get("label_id",-1))==int(item["id"]) and j.get("profile")==spec["profile"] and int(j.get("copies",0))==int(item["copies"])]
  checks[f"{item['code']}_correct_profile_and_copies"]=bool(hits)
 values=[v for k,v in checks.items() if k!="state_readable"]
 return checks,(sum(bool(v) for v in values)/len(values) if values else 0.0)
