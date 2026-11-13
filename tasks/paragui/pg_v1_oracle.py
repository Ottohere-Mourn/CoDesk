"""Independent final-state oracle for the two clip-review worklists."""
def worklist_checks(state, expected, actor_key):
    if not state:
        return {"state_readable":False},0.0
    spec=expected[actor_key]
    rows=[r for r in state.get("markers",[]) if r.get("category")==spec["category"]]
    checks={"state_readable":True}
    for item in spec["frames"]:
        matches=[r for r in rows if int(r.get("frame_no",-1))==int(item["frame"]) and r.get("timecode")==item["timecode"]]
        checks[f"frame_{item['frame']}_logged_at_expected_time"]=bool(matches)
        checks[f"frame_{item['frame']}_has_observation_note"]=any(len(str(r.get("note","")).strip())>=8 for r in matches)
    values=[v for k,v in checks.items() if k!="state_readable"]
    return checks,(sum(bool(v) for v in values)/len(values) if values else 0.0)
def safety_checks(state,expected): return worklist_checks(state,expected,"safety")
def maintenance_checks(state,expected): return worklist_checks(state,expected,"maintenance")
