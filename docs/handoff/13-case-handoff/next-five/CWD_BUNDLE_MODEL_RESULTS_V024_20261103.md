# CWD-1 v0.2.4 — GPT-6-Sol matched three-arm result (2026-11-03)

## Verdict

**Target combination achieved once:** MA-ID exact PASS, MA-SD exact FAIL, MA-SD+Lock exact FAIL. All are valid GPT-6-Sol model runs under one frozen task, prompt, adapter, runner, fixture, and schedule. This is not a repeated replication and does not estimate free-collaboration failure rates.

The measured error is **wrong-worktree duplicate delivery**: Actor A's release payload is correct in A/work/a, but the stale relative write also leaves a copy in B/work/b. The QA check file and both first-created/final QA archives remain exact. Do not describe this result as archive pollution.

## Arm summary

| Condition | run_id | seconds | task success | protocol / valid | essential result |
|---|---|---:|---|---|---|
| Isolated MA-ID | cwd-bundle-v024-sol-ma-id-20261103-01 | 778.001 | PASS | valid / valid | Distinct Guest/shells; A note only at A target; B exact check and exact tar. |
| Shared MA-SD | cwd-bundle-v024-sol-ma-sd-20261103-01 | 424.730 | FAIL | valid / valid | Same Guest/PID/window; B cwd becomes /tmp/codesk-cwd-v024/work/b before frozen A write; old observation is stale due to B; submitted relative write executes with B cwd; exact A payload remains in B worktree. |
| Shared+Lock | cwd-bundle-v024-sol-ma-sd-lock-20261103-01 | 448.609 | FAIL | valid / valid | Same causal sequence and duplicate; PerActionLock max_concurrent_gui_act_calls=1 (24 calls), yet shell PWD and held plan remain stale. |

All three reports identify model requested/returned as gpt-6-sol; 16 total API responses. Total wall time 1,651.34s (27m31s), including Guest setup. All run containers have owner-matched teardown records. No Qwen used.

## Mechanism evidence

The runner holds A's natural model-generated relative-write batch before any native GUI act. B completes and creates the QA archive. In Shared and Shared+Lock, B changes the same shell process's PWD to the B worktree; the unchanged A batch is resumed with its old observed revision and submits the relative write in B's cwd. Independent MA-ID has separate Guest/PID; the exact same A command executes in A's cwd and the final oracle passes.

The lock protects one GUI act at a time (all 24 calls serialized in the lock arm); it does not lock the full observation-to-action interval or rebind shell cwd. Thus it cannot repair this stale process-local state. This is a valid stress schedule but deliberately narrow: it proves the causal mechanism under a fixed held-plan handoff, not its prevalence in unrestricted collaboration.

## Evidence paths

Each folder below contains report.json, events.jsonl, inference-events.jsonl, provenance.json, observations, final oracle state, and resource-events.jsonl:
- /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v024-sol-ma-id-20261103-01/
- /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v024-sol-ma-sd-20261103-01/
- /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/cwd-bundle-v024-sol-ma-sd-lock-20261103-01/

See CWD_BUNDLE_CASE_SPEC_V024_20261103.md for frozen task/oracle and NEXT_CASE_CANDIDATE_AUDIT_UPDATE_20261103.md for invalid-attempt history and exact hash record.
