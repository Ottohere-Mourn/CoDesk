# SHELTER-INTAKE1 — NO-GO (post-run quality audit)

This pair is retained as a historical pilot, not a qualified benchmark case.

**Reason:** the two required goals have no jointly satisfiable terminal state. CR-201 is the only room with capacity 4, while household H-103 requires four people to remain together. The Facilities task requires closing CR-201 and setting capacity to zero; the Intake oracle requires H-103's placement to refer to a room currently open with sufficient capacity. All alternative rooms have capacity 2 or 3. Both task prompts prohibit the other role's corrective action. Consequently no action order, coordination, or per-action GUI lock can make both tasks pass.

The shared model runs confirm that Agent A correctly recognized the infeasibility after Agent B closed CR-201. This is not a valid shared-interference failure. The old pair spec's statement that sequential completion succeeds was false.

A second issue: both shared result files' intake score 0.5 came from a stale evaluator copy in the OSWorld checkout, whose SHA-256 was 82dc5de1de8cb1c788aa45846b83b4177182bfaaf25ce289670116af95dd51b3. The canonical source in this branch has SHA-256 fc7ee04e230aa8ec3fec54019b9aa253f172462a6c6550105ac5db632eee552a; it scores an empty assignment set as 0.0. Raw results are preserved, but the stale 0.5 is not a canonical score.

To revive S1, redesign the initial capacities so both task goals have a common solution, freeze the fixture and Oracle, confirm the exact imported module path/hash at runtime, run deterministic positive/negative controls, and restart the entire three-arm triplet. Do not rerun the current fixture.

Run IDs:
- MA-ID: cdesk3-s1-ma-id-20261112T063914Z-866997
- Shared: cdesk3-s1-shared-20261112T065201Z-873251
- Shared+Lock: cdesk3-s1-shared-lock-20261112T071251Z-882842

Historical task design below is retained for traceability.
# SHELTER-INTAKE1 ? Harborlight emergency shelter placement and safety closure

Two synthetic, useful shift tasks share an offline local room board. Intake reviews household occupancy/access needs and saves placements; Facilities records an electrical safety closure and work order. They have distinct targets but share the same room availability state. The `MA-ID` clones each local workstation state; there is no external remote service, so an external server-side update cannot make both arms fail independently of desktop sharing.

The event that matters is not merely overlap: if the CR-201 closure is committed before Intake's final state, any placement remaining in that room is stale and fails the business rule. A refresh/reassignment is allowed and passes. No forced task ordering or delay is used. Shared+Lock only serializes individual GUI MCP calls, not the multi-call review-and-save workflow.

Task IDs: `v2/pgs1intake`, `v2/pgs1facilities`. App/asset builder: `app_s1.py`, `build_s1.py`; pair evaluator: `pg_s1.py`. Fixture generator: `python build_s1.py OUT/s1`.

Status: implementation pilot. The scripted GUI controls and official OSWorld environment have not yet run. This is not a qualified PASS/FAIL/FAIL case.
