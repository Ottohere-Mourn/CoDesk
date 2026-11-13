# LIBRARY-ROOM1 — programme bookings plus safety closures

Status: compact-fixture scripted positive control and one GPT-6-Sol triplet complete; one-time joint pattern reached. See LIBRARY_ROOM1_MODEL_RESULTS_20261113.md.

## Task pair
- **Programme coordinator (A):** schedule two Northbridge College public programmes on 24 November 2026. Choose the exact listed time slot and setup, and select a currently open, step-free room large enough for the listed attendance.
- **Facilities coordinator (B):** close R-101 and R-201 after distinct safety findings and create the two specified work orders. Do not edit programme bookings.

## Shared state and common-pass proof
Both roles use the same one-window college room desk; programme bookings and room inspections have a global active work area and selected record. A room closure updates its live status. The case is not zero-sum: after B closes two rooms, both programme bookings remain feasible using suitable open rooms; the two programmes use the same morning slot, so a room cannot be assigned to both. The Oracle accepts any suitable open room, not a hidden preferred answer. The built-in positive control must demonstrate both tasks passing in one shared fixture before model calls.

## Observable hypothesis
A booking entered before a safety closure may become invalid; switching to the facilities panel also replaces the global work area and active room. Per-action lock serializes clicks but does not make a booking-plus-inspection workflow transactional. A can also recover by rereading live room status and reassigning a room.

## Oracle and distinction
The programme Oracle checks both exact time-slot/setup pairs, checks the selected room against current OPEN status, attendance capacity, step-free requirement and the event room-eligibility facts, and rejects overlapping bookings in the same room. The facilities Oracle checks both room statuses, reasons and work-order ids. A positive terminal state exists under the same shared DB.
This is a facilities/resource-state workflow, distinct from video review, label printing and volunteer finance. It is near the rejected SHELTER-INTAKE1 only at the broad “room closure” level; unlike that no-go, spare suitable rooms are deliberately sufficient. It is not a new underlying resource mechanism.

## Controls required before a model run
- offline: joint PASS, closed-room booking FAIL, capacity/overlap negatives;
- real Guest scripted joint-positive GUI control in one Guest;
- verify app/runtime source parity, reset and evaluator readability.
No arm-specific scheduling barrier or injected obstacle.


## 2026-11-13 model-budget calibration and v4-v6 downsizing

The first real Codex/GPT-6-Sol V4 MA-ID calibration (cdesk3-v4-ma-id-20261113T052039Z-1485864) is preserved unchanged. Guest boot/setup and Oracle were valid, but both actors hit the configured 2400 s timeout: A scored 2/5 programme records, B 2/3 room inspections. This is a valid incomplete task result, not an infrastructure-invalid run and not a pass. No Shared or Shared+Lock arm was run from that fixture. A scripted joint-positive test with that earlier fixture had passed before the later design revision.

To make the three new cases feasible within the fixed 60 GUI-call / 2400 s actor budget, the current frozen candidate fixtures use:
- V4: two same-slot programme bookings; two safety closures (R-101, R-201); spare suitable rooms leave a jointly feasible end state.
- V5: two supplier invoices plus two staff claims; long references and explicit Copy/Paste remain.
- V6: three accommodation profiles and three matching seating records.
These are design revisions, not changes to the preserved run. The current compact assets and controls were validated before the V4-V6 model arms; their reports are linked in the handoff.
