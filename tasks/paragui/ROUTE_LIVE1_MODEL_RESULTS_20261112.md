# ROUTE-LIVE1 (q1) — GPT-6-Sol first triplet, 2026-11-12

Status: **one valid outcome triplet matches MA-ID PASS / Shared FAIL / Shared+Lock FAIL**, but the intended live-route staleness mechanism was not observed because the service Agent did not successfully save its deferral in either shared arm. Retain as a provisional shared-browser-workflow result, not yet as evidence that a deferred work order made a route stale.

## Frozen task and common-feasibility audit

A: create Draft RTE-17 using the released manifest order filtered by jobs still Scheduled when the route is saved. B: defer WO-503, reschedule to 2026-11-14, preserve the caller note. A may not edit jobs; B may not edit route. The oracle derives the required stops from final job status, so a shared state with B's update and A's three-stop route can pass both. Static controls verify (1) independent 4-stop route + B update both pass, (2) B then A produces a jointly passing terminal state, and (3) A's 4-stop route followed by B's deferral makes the route stale while B passes. tests/test_q1_oracle.py: 3 passed. This eliminates the hard contradiction in raw K2.

## Real runs

All three used the exact same asset and installed task/oracle modules, Codex CLI 0.165.0, GPT-6-Sol, high effort, GUI MCP only, max 45 calls/actor. Model calls were protocol-valid, and every run returned error=null. The preflight runner hash guard verified source modules equal OSWorld-installed modules before API-key intake or Guest/model start.

| Arm | Run ID | A score | B score | A/B steps | Run seconds | Result |
|---|---|---:|---:|---:|---:|---|
| MA-ID | cdesk3-q1-ma-id-20261112T121123Z-988094 | 1.0 | 1.0 | 18/12 | 445.8 | Both exact PASS |
| Shared | cdesk3-q1-shared-20261112T122106Z-993038 | 1.0 | 0.25 | 43/29 | 1104.0 | Outcome target FAIL |
| Shared+Lock | cdesk3-q1-shared-lock-20261112T124030Z-1000676 | 0.1429 | 0.25 | 35/32 | 832.8 | Outcome target FAIL |

The Shared failed-state checks: route was saved correctly and exactly matched the unchanged all-Scheduled jobs (A pass); B's WO-503 exists but is not Deferred, has no new date and no caller note (B 0.25). Agent B's final response says it could not complete because the desktop kept switching pages. Its action log shows it attempted Ctrl+L, then typed the WO-503 URL after the active Chrome title had become Route draft. Thus the observed fail is cross-actor shared browser/page navigation contention; it is not the route becoming stale.

In Shared+Lock neither actor achieved its database goal: no route was saved (A 0.1429, where only the vacuous “every saved stop scheduled” check is true), and B's target job fields remain unchanged (B 0.25). Both agents declared infeasible after repeated page/form navigation changes. All 32 A mutation calls and 23 B mutation calls have lock_enabled=true; sum wait 6.509 s, sum held 126.674 s, max wait 2.153 s. The per-action lock worked mechanically, but does not bind one Agent's thought to its next action or keep Chrome on that Agent's workflow.

## Interpretation / decision

This is a useful application-context/shared-page outcome, not clean evidence for the specific live-status route consistency hypothesis. It is distinct in business scenario from old ROUTE-RECON1 but the observed mechanism is near the existing application-context family and must not be presented as a novel mechanism. Keep the files/runs as an exploratory result. Before including q1 among the requested three new qualified cases, add a matched GUI positive-control schedule in the same Guest that proves B can save the deferral and A can refresh/rebuild a route with 3 stops without prompt/spec changes; then rerun only if that control is reliable. Do not tune the app to suppress ordinary shared GUI interference.

## Cost / environment

Triplet wall-time sum: 2,382.6 s (39.7 min); total Codex-reported input tokens 5,668,319 (4,407,067 cached), output tokens 18,433. No GPU was used. Each arm wrote Guest overlays to /dev/shm during execution and raw runs/logs to RAID. RAID copies of overlays are present (~522 MB, 1.1 GB total for MA-ID; ~529 MB for Shared+Lock); cp reported a metadata permission warning on the RAID mount after copying data, so treat run reports/logs as primary evidence and retain the source overlays if needed. All run-owned containers have destroy records; no QEMU/container remains. Root remains 99% with ~24 GB free; /dev/shm ~101 GB free; RAID ~1.1 TB free.
