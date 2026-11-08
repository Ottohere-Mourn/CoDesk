# SITEACT-STATE1 — Site activation readiness handoff (v0.1)

**Status:** One valid GPT-6-Sol screening triplet reached MA-ID PASS / Shared FAIL / Shared+Lock FAIL under the registered final-state oracle. This is a site-readiness temporal-staleness workflow variant, not a novel mechanism or repeated result.

## Workflow
Synthetic research site NE-14: activation coordinator A reviews protocol amendment PR-14-AMD-04, IRB approval IRB-NE14-221, complete staff training TRN-NE14-2026-10 (4/4), and calibration CAL-55. A saves a structured READY snapshot at revision 1 and messages regulatory reviewer B. In a later ordinary step, B records newly received protocol deviation PD-2026-018 / MONITOR_REVIEW_REQUIRED, places the current site gate on HOLD/revision 2, and messages A. No patient data or real site service is used.

## Arms and exact oracle
A always runs before B; no click/action is held pending. MA-ID gives each actor a private Guest/app. A's READY snapshot remains current relative to A's private state; B's independent site copy reaches HOLD. Shared and Shared+Lock use the same Guest/app state, so B's subsequent HOLD makes the earlier READY snapshot stale. The lock is the existing production per-GUI/CLI-action mutex, not a transaction spanning the two actors.

A shared failure is attributable only if A made the exact READY/revision-1 snapshot before B; B recorded the exact deviation and HOLD/revision 2; and the final shared state still has the old READY snapshot. Wrong evidence or wrong deviation cannot satisfy this signature. The stale banner and normal revalidation path are visible; if the actors reconcile the snapshot to the current HOLD state, score PASS.

## Review and implementation
Bounded GPT-6-Sol review: GO-TO-MA-ID conditional on evaluating snapshot against final site state. Response: /mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-siteact-state-review-20261107-01/response.txt. Sol describes a temporal stale artifact, not a race or frequency claim, and cautions that domain relabeling alone does not establish novelty.

Code:
- scripts/siteact_state_fixture_v1.py — contract/scorers
- scripts/siteact_state_app_v1.py — loopback-only Guest workflow UI
- tests/test_siteact_state_fixture_v1.py — six offline tests pass via unittest
- scripts/run_siteact_state_hybrid_v2.py — CodexHarness Hybrid v2 runner
- scripts/run_siteact_state_hybrid_v2_secure.sh — hidden-key launcher; does not persist the key

Same GPT-6-Sol / Codex CLI 0.155.0 harness, GUI MCP + restricted Guest CLI MCP + Collaboration MCP permissions, 20 steps and 12,000 output-token budget per actor, same A→B schedule in all arms. The valid experiment results and exact hashes are recorded below.

## Interpretation limits
The measured effect is sequential workflow state/artifact currentness: a later Hold update changes the shared state underneath a previously saved READY snapshot. It is not simultaneous input contention, incident-rate evidence, or proof of real-world frequency. B may observe the stale cue and notify A, but A has no scheduled turn after B; the endpoint oracle is final artifact/state consistency. Do not hide the cue or weaken the exact scorer. A valid Shared PASS closes this design for the target.

## 2026-11-08 — one valid Hybrid v2 screening triplet

Reports (all on RAID1 under /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/siteact-state-hybrid-v2/):
- MA-ID: siteact-state-sol-ma_id-20261107-04/report.json — valid, both actors done; A exact READY/revision-1 snapshot PASS; B exact deviation/HOLD PASS; task PASS; reset PASS; 511.96 s.
- Shared: siteact-state-sol-ma_sd-20261108-01/report.json — valid; A snapshot exact before B; B logged PD-2026-018 and HOLD/revision 2; final shared state retained READY/revision-1 snapshot; exact stale signature TRUE; task oracle FAIL; reset PASS; 328.53 s.
- Shared+Lock: siteact-state-sol-ma_sd_lock-20261108-01/report.json — same exact stale signature; task oracle FAIL; reset PASS; 375.91 s.

All three match task version, fixture SHA-256 d20dc91974bbc03929146924e2c43a95fffda8e01848033f550ba2f7a5d2ab5d, app SHA-256 265c93e5060c0b82c776a9a5ae2bd220c07d22554c5670fc51930242bea855dd and both prompt hashes. All actors were GPT-6-Sol via Codex CLI 0.155.0 and returned valid model responses. No Qwen/local GPU. The valid arms total 1,216.40 s (20.27 min), with 56 successful GPT-6-Sol relay responses (~570,522 input and 3,412 output tokens). GUI + restricted Guest CLI + Collaboration MCP permissions and per-actor budgets matched; actors did not need CLI for this case.

Lock audit: the lock run created locks/gui-cli-actions.lock. Production oscombo.desktop_tools.action_lock acquires fcntl LOCK_EX; desktop_tools and guest_cli_tools use this shared context. This is a serial A→B schedule with no simultaneous contention: the experiment shows the lock does not version an earlier saved snapshot, not that lock contention occurred.

Interpretation boundary: in both shared arms, B correctly messaged A that the READY snapshot had become stale and required coordinator revalidation. FAIL is specifically final persisted snapshot/current-site mismatch after B's scheduled update, not that the model missed the cue, disobeyed its prompt, or experienced a concurrent click race. A has no post-B turn; the endpoint is final artifact freshness. The live gate is HOLD and the UI visibly labels the old snapshot stale. Treat this as a controlled sequential handoff-integrity case, not an incident-rate estimate. It is adjacent to DATA-REL1/AP-1/PAY-1 at the broad stale-artifact-family level; the distinct contribution is site-readiness/activation semantics, not a new mechanism.

Retained but excluded invalid MA-ID attempts: -01 browser start was sent without bash -lc (no model request); -02 state readiness queried through Episode rather than DesktopEnv (no model request); -03 Actor A completed an exact snapshot, then an uninitialized final-state accumulator crashed before B, invalidating the arm. Runner fixes are in scripts/run_siteact_state_hybrid_v2.py. None are included in the successful triplet. No commit/push; no old runs or overlays were deleted. Post-run resource check: root ~50 GiB free, RAID1 ~1.2 TiB, available RAM ~168 GiB, no active Docker/QEMU Guest.
