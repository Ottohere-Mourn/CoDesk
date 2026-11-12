# SHELTER-INTAKE1 ? Harborlight emergency shelter placement and safety closure

Two synthetic, useful shift tasks share an offline local room board. Intake reviews household occupancy/access needs and saves placements; Facilities records an electrical safety closure and work order. They have distinct targets but share the same room availability state. The `MA-ID` clones each local workstation state; there is no external remote service, so an external server-side update cannot make both arms fail independently of desktop sharing.

The event that matters is not merely overlap: if the CR-201 closure is committed before Intake's final state, any placement remaining in that room is stale and fails the business rule. A refresh/reassignment is allowed and passes. No forced task ordering or delay is used. Shared+Lock only serializes individual GUI MCP calls, not the multi-call review-and-save workflow.

Task IDs: `v2/pgs1intake`, `v2/pgs1facilities`. App/asset builder: `app_s1.py`, `build_s1.py`; pair evaluator: `pg_s1.py`. Fixture generator: `python build_s1.py OUT/s1`.

Status: implementation pilot. The scripted GUI controls and official OSWorld environment have not yet run. This is not a qualified PASS/FAIL/FAIL case.
