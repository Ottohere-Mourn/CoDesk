# Latest Candidate Repair Progress — 2026-11-05

## Scope and state

This note records the current repair status for the five short-list candidates in the isolated HealthCare worktree:

- Worktree: `/home/mjh/Projects/CoDesk-candidate-repair-20261104`
- Branch: `codex/candidate-repair-20261104`
- HEAD at note creation: `c866975`
- This handoff copy records outcome only; raw run artifacts remain on HealthCare.
- Only Hybrid GUI + read-only Guest CLI + Collaboration MCP candidate runs are covered here. Historical GUI-only experiments are untouched.

Acceptance target for each case: GPT-6-Sol; both MA-ID tasks pass; MA-SD fails because of a supported shared-state interaction; MA-SD+Lock also fails; all runs valid and reset succeeds. Infrastructure/protocol-invalid attempts are retained but are not counted as failures.

## Current shortlist status

| Candidate | Current result | Disposition |
|---|---|---|
| CWD-1 | MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL | Meets target |
| VIEW-1 | MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL | Meets target |
| AUTH-1 | MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL | Meets target |
| FIND-1 | MA-ID PASS / MA-SD FAIL / MA-SD+Lock FAIL | Meets target after supplemental adjudication of the Shared report aggregator bug |
| EDIT-1 | MA-ID PASS / MA-SD PASS / MA-SD+Lock PASS | Does not meet target; do not claim as a shared-failure case |

Thus four of five currently meet the target; EDIT-1 remains a legitimate negative result.

## VIEW-1 and AUTH-1

The latest VIEW-1 repair v0.1.1 triplet is valid PASS / FAIL / FAIL: view-signoff-sol-hybrid-v2-repair-011-ma-id-20261104-03, view-signoff-sol-hybrid-v2-repair-011-ma-sd-20261104-01, and view-signoff-sol-hybrid-v2-repair-011-ma-sd-lock-20261104-01. Do not merge with the earlier v0.2.0 result.

AUTH-1 v0.1.0 local mock also has a valid PASS / FAIL / FAIL triplet: auth-identity-sol-hybrid-v2-010-ma-id-20261104-02, auth-identity-sol-hybrid-v2-010-ma-sd-20261104-01, and auth-identity-sol-hybrid-v2-010-ma-sd-lock-20261104-01. No internet or real credentials were used.

## EDIT-1: overtype-mode interference

The scripted probe isolates Writer's global Insert/Overwrite mode:

- Probe: `scripts/probe_edit_mode_only_v040.py`
- Mechanism: A is paused just before typing `READY `; B toggles Insert to OVR without moving the pointer or changing document content.
- Scripted MA-SD control reproduces the expected overtype corruption.
- Sham control toggles twice back to Insert and passes.
- Scripted MA-SD+Lock control also reproduces the corruption.
- Probe completed and reset successfully (about 10.1 minutes).

The GPT-6-Sol model trial did not reproduce the desired failure:

- Runner: `scripts/run_edit_overwrite_hybrid_v2_mode_only_v050.py`
- MA-ID: PASS (399.581 s).
- MA-SD: PASS (352.113 s).
- MA-SD+Lock: PASS (320.604 s).
- All three runs were model/protocol/task-valid and reset succeeded.
- In shared conditions the model noticed/recovered from OVR (e.g. undo, switch back to Insert, retype, save).

Conclusion: the mode mechanism is real and controlled, but this task is recoverable by the tested agent. Do not weaken the model budget or suppress visible recovery cues to manufacture failure. EDIT-1 is not a passed case.

## FIND-1: shared Find & Replace option interference

Task semantics: A replaces all lowercase `pending` occurrences with `approved`; B enables Match case and must leave it enabled. The task's shared failure is a joint-task failure if the shared option does not remain in B's requested final state, even when A's document edits are exact.

Valid aligned triplet:

- MA-ID baseline: `find-replace-sol-hybrid-v2-v031-ma-id-20261105-01` — PASS, valid/protocol/reset all true (880.001 s).
- MA-SD: `find-replace-sol-hybrid-v2-v032-ma-sd-20261105-01` — supported shared exposure and nested full evaluator says FAIL.
- MA-SD+Lock: `find-replace-sol-hybrid-v2-v032-ma-sd-lock-20261105-01` — valid/protocol/reset true, task FAIL (511.755 s).

The MA-SD v032 coordinator held the actual pending Replace All click (observed at logical x=845, y=367) while B enabled Match case in the same Writer dialog. Logs establish Match case false before B, true after B, same Writer XID/Guest, and no change to other search options. The final document is exact, but B's Match case task state is false; the full evaluator therefore correctly says `evaluation.task_success=false`.

**Reporting caveat:** the MA-SD run was generated before the runner's top-level aggregator fix, so its original `report.json` incorrectly says `task_success=true` and `shared_recovered_or_pass`. The original report is preserved unchanged. See sibling `adjudication.json` in that run directory; it records the source report SHA-256 and the corrected interpretation. The v032 Lock runner includes the aggregator fix and reports the failure at top level.

Earlier FIND attempts are preserved but excluded:
- v030 MA-SD: invalid because A changed Whole words before B.
- v031 MA-SD/Lock: the gate held a non-target click rather than the Replace All click.
These are not counted as either passes or failures.

Approximate FIND triplet model time: 36.4 minutes. No second valid repeat was requested.

## Environment and next steps

- Recent safety check showed no active Docker containers; root had about 68 GiB free and `/mnt/raid1` about 1.4 TiB free. No data was deleted.
- Preserve all invalid and valid run artifacts.
- The user has decided not to continue rescuing EDIT-1. Keep the five-case result at 4/5; v0.5.0 is a valid recovery result, not a case success.
- The user authorized publishing this status to the 13-case handoff branch and decided not to continue rescuing EDIT-1.
