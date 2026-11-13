# CRM-LU1 Case Card v0.1.1 - Customer Record Lost Update
Date: 2026-11-08
Status: One valid GPT-6-Sol screening triplet achieved
Scope: controlled synthetic legacy full-record form workflow; not evidence about default behavior or failure rate of current commercial CRM products.

## Result at a glance

| Arm | Valid model run | Task result | Final record | Classification |
|---|---:|---:|---|---|
| MA-ID | Yes | PASS | A's Guest: Jordan Lee / old billing; B's Guest: old renewal / ap@northwind.example | MA-ID_PASS |
| Shared | Yes | FAIL | Jordan Lee / old billing | Shared_FAIL |
| Shared+Lock | Yes | FAIL | Jordan Lee / old billing | Shared+Lock_FAIL |

One screening triplet only; no repeatability or incidence claim.

## Daily workflow and failure signature

A customer-service team maintains the renewal contact and billing email of one synthetic customer record, C-014.

- Actor A uses signed renewal addendum RN-014 to set Renewal contact = Jordan Lee.
- Actor B uses verified billing-contact notice BN-014 to set Billing email = ap@northwind.example.
- Both tasks are valid, independently actionable changes to disjoint fields. The required final shared record is {Jordan Lee, ap@northwind.example}.
- Both arm schedules run serially B then A. In Shared, one browser page opens both role sections against version 1 before either agent acts. Each form keeps its own loaded field snapshot. Saving B updates the record to version 2; the still-open A form subsequently submits a full record including the old billing email. The ordinary Save is accepted without stale-version rejection or field-level merge.

The audit trail identifies B's valid E1 save, A's version-1 full-record submission against version 2, and the exact lost-field result. A's assigned field is correct at final state; B's previously correct field is not. This is not focus, active-row, clipboard, CLI, or simultaneous-action contention.

## Isolation, task and scoring

- MA-ID: a fresh Guest-local application state per actor, both seeded identically. The same actor-specific oracle evaluates A's owner field in A's workspace and B's owner field in B's workspace.
- Shared / Shared+Lock: one Guest-local CRM state shared by both actors; both forms are initially loaded against that state before the B-then-A schedule. The same role-specific evaluator is used, and the final shared record must satisfy both owners' field goals.
- Task ID/version: CRM-LU1 / 0.1.1-legacy-full-record-form-role-tabs.
- GPT-6-Sol, Codex CLI 0.155.0 / reused CodexHarness; 20 steps and 12k output-token budget per actor in all arms. GUI MCP, restricted Guest CLI MCP and Collaboration MCP permissions are identical in every arm. The agents used GUI actions for the assigned edits; the runs did not need CLI or collaboration calls.
- Shared+Lock uses the production per-action GUI/CLI lock. Because this schedule serializes B then A, it does not test simultaneous lock contention; it demonstrates only that a per-tool-call mutex does not merge a stale full-record business save.

## Validation and recovery

- Offline oracle/HTTP tests: 5/5 passed (tests/test_crm_lu1_v1.py).
- Production GUI MCP scripted control passed (crm-lu1-gui-semantic-control-20261108-05): B save -> A's unrefreshed full-form save -> exact field-loss signature -> browser reload -> B reapplies its authorized value -> joint final PASS. The audit preserves all three events.
- The GUI app has normal browser refresh and a role-specific B form, so recovery is possible and was verified. The model screening schedule ends after the assigned B and A turns; there is no post-A B recovery turn. Consequently the Shared FAIL is a final completion-order mismatch, not a claim that the app makes recovery impossible.
- Wrong customer/unauthorized owner value are rejected by contract tests. All successful scripted/model Guests have destroy records; reset is valid in all three model reports.

## Product-semantics and external-validity boundary

This pilot uses a transparent, loopback-only synthetic application written for this controlled condition. It explicitly implements a legacy full-record HTML form Save with no optimistic-concurrency rejection and no PATCH/field merge. This was an intentional, documented fixture contract, not a discovered defect in an installed CRM. Do not generalize this result to modern CRM software or claim a real product was tested.

Earlier read-only product research found reports of stale full-form overwrites in some older SuiteCRM deployments and later optimistic-lock protection; the version/default-product gate is why this card remains scoped as a formalized legacy scenario:
- [SuiteCRM community thread on editing the same record in two sessions](https://community.suitecrm.com/t/multiple-users-edit-same-record-stop-edit-or-override/68882)
- [SuiteCRM PR #3276: optimistic-locking correction](https://github.com/salesagility/SuiteCRM/pull/3276)

The experimental contrast is met within the pinned synthetic application and topology: isolated workspaces preserve each assigned edit; one shared workspace lets the stale full form erase the earlier disjoint-field update.

## Exact evidence

Run artifacts are on RAID1:

- MA-ID: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-hybrid-v2/crm-lu1-sol-ma_id-20261108-01/report.json
- Shared: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-hybrid-v2/crm-lu1-sol-ma_sd-20261108-01/report.json
- Shared+Lock: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-hybrid-v2/crm-lu1-sol-ma_sd_lock-20261108-01/report.json
- Current scripted GUI semantic control: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-guest-controls/crm-lu1-gui-semantic-control-20261108-05/report.json

Total model-run wall time was 1,083.44 s (18m 03s): MA-ID 484.60 s (8m 05s), Shared 295.39 s (4m 55s), Shared+Lock 303.45 s (5m 03s). All three reports show valid_model_run=true, reset_success=true, matching app/fixture/task hashes, and successful final resource teardown. No GPU inference was run; model requests went to the GPT-6-Sol endpoint. The local worktree is uncommitted/unpushed; no historical case files or artifacts were overwritten.


## Reproduction and files

The local HealthCare worktree is /home/mjh/Projects/CoDesk-candidate-repair-20261104, branch codex/candidate-repair-20261104, HEAD 909c88b4081cf981ff9187c6e976720bca48295b before these uncommitted additions.

New case files:
- scripts/crm_lu1_app_v1.py - loopback-only visible CRM UI.
- scripts/crm_lu1_fixture_v1.py - state, exact field goals and full-record save audit.
- tests/test_crm_lu1_v1.py - five focused offline contract/HTTP tests.
- scripts/run_crm_lu1_hybrid_v2.py and scripts/run_crm_lu1_hybrid_v2_secure.sh - matched Hybrid v2 actor runner and hidden-key wrapper.
- scripts/probe_crm_lu1_gui_control_v1.py - no-model production GUI MCP semantic/recovery control.

For a fresh run, run MA-ID first. Use its successful report as baseline for each shared arm:
1. scripts/run_crm_lu1_hybrid_v2_secure.sh --condition ma_id --run-id <fresh-id>
2. scripts/run_crm_lu1_hybrid_v2_secure.sh --condition ma_sd --run-id <fresh-id> --baseline-report <ma_id-report.json>
3. scripts/run_crm_lu1_hybrid_v2_secure.sh --condition ma_sd_lock --run-id <fresh-id> --baseline-report <ma_id-report.json>

The secure wrapper prompts on a TTY for the GPT-6-Sol API key and does not save it. Artifacts go under /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/crm-lu1-hybrid-v2 by default. No commit or push was made.

