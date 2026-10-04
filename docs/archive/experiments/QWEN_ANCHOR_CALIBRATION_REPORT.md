# CoDesk Qwen Anchor Calibration Report

Date: 2026-10-02  
Canonical repo: `/home1/mjh/Projects/CoDesk-V0-A6000/CoDesk`  
Branch / starting HEAD: `v0` / `e82d1be6c62096b6b1868739c8bb00a7368a2652`  
Guest host: A6000. Inference: existing Qwen3-VL-30B-A3B BF16 worker on 4090 GPUs 4/5, via existing reverse tunnel at `127.0.0.1:15485`. No A6000 inference or deployment changes.

Artifacts are retained outside the Git worktree under:
`/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/qwen-anchor-calibration/`
No historical run/report was overwritten.

## Outcome

**Decision: CONTINUE CALIBRATION.** F-01 already has Qwen mechanism evidence; revised A-01 now has a valid model-level context-interference result. C-01 Solo and MA-ID are calibrated, but the two valid MA-SD runs did not expose an A-owned clipboard payload being overwritten by B. Their observed failures are focus/input-routing interference, so they do not close the Clipboard family.

## 1. Diagnosis of historical failures

### C-01 Writer Solo A

Historical C-01 task versions used a blank/marker destination paragraph and underspecified cursor positioning. In the preserved Qwen traces:

- The first failed episode left an incomplete source value (`REF-731`), so the failure was source selection/grounding.
- The next failed episode pasted around the visible arrow/marker rather than replacing a clearly bounded target line (final text included `Paste copied value here -REF-7319>`). This was a GUI target/caret ambiguity, not evidence that the clipboard mechanism itself failed.
- One earlier run also hit a runner exception after the evaluator had failed: `'tuple' object has no attribute 'copy_artifacts'`. Its original oracle result remains failed; that record is not counted as a clean model run.

### A-01 Solo B and MA-ID

Historical Solo B run `a01-solo-b-r02-20261002` typed `CTX-B-08200` into tab-a, leaving tab-b empty. The screenshot showed the tab-a form as active. The actor did not switch to its assigned tab.

Historical MA-ID runs r01/r03 show the same target-selection failure: Actor B typed into its local tab-a instead of tab-b. Historical MA-ID r02 has `joint_success=true` in the evaluator while the runner recorded `model_task_failure`: Actor B exhausted its 20-step budget without an explicit terminate action. The old runner incorrectly required all actors to terminate even when the exact oracle passed. This was a runner state/status bug, not an evaluator disagreement.

The current runner derives task outcome from the oracle and execution errors, and records termination/budget separately. Revised MA-ID runs completed normally and passed, so the legacy budget-exhaustion branch was diagnosed from its retained report, not deliberately recreated.

### Historical A-01 MA-SD

Both old MA-SD reports have `scheduled_exposure=true`, but their window logs contain no `tab_activated` event. There was no measured tab switch and thus no Application Context exposure. Those old failures are un-attributed task failures and are not mechanism evidence.

### C-01 revised MA-SD telemetry correction

The old convenience field labeled a clipboard payload transition from empty to Actor B's first copy as an “overwrite,” and could infer a wrong paste from final failure without proving a paste. Raw traces for valid revised MA-SD runs show no valid Actor A source copy before Actor B's copy and no Writer paste of B's payload. The runner telemetry has been corrected to require an ordered, digest-verified A copy → distinct B copy → A paste into Writer, with final Writer content, before reporting overwrite/wrong-paste evidence. Existing JSON reports remain untouched; this report post-hoc corrects their interpretation from raw observer events and final files.

## 2. Minimal anchor calibration changes

No task family, scoring condition, evaluator rule, Qwen model, system prompt, action parser, decoding setting, or action budget changed.

- **C-01 v1.0.3-calibration:** replaced the ambiguous blank/arrow destination with a visible line `INSERT COPIED VALUE`; Writer now starts as two explicit paragraphs. The final exact oracle is unchanged: `REF-7319\nREF-7319`. Actor A's task-specific instruction names keyboard selection and the placeholder replacement; global Qwen prompt/action protocol is unchanged.
- **A-01 v1.0.0-rc5-calibration:** Actor goals now state the deterministic tab shortcuts (tab-a Ctrl+1, tab-b Ctrl+2). Goal values, pages, expected final state, evaluator thresholds, and interaction mechanism are unchanged.
- **Runner:** task oracle result and actor termination are separate. Window events are now binding-scoped so identically numbered X11 window IDs from independent MA-ID Guests cannot be combined into a fictitious shared-window timeline. C-01 overwrite attribution is based on ownership/content digests and ordered copy/paste evidence.
- **Guest startup:** the migrated qcow2 is at `/home1/mjh/Projects/CoDesk-V0-A6000/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2`; the runner's former default `_deps/.../docker_vm_data/osworld-v2-ubuntu-x86.qcow2` path is an empty directory. During r08 diagnosis, the owned QEMU container console reported `No boot disk specified`; the runner report records readiness timeout and the resource ledger records successful owned-resource destruction. The container auto-removed before a full console log could be saved. The runner now resolves an explicit `SWCUB_OSWORLD_GUEST_IMAGE` first, then falls back to an existing pinned image in the migrated assets directory. The resolver was verified to return the real file; all valid collected runs used the explicit verified path. This is a launch configuration issue, not a model failure.

## 3. Revised Qwen results

All valid rows below used OSWorld V2.1 Qwen3VLAgent, the existing remote endpoint, fresh run-scoped Guest(s), independent Actor histories, and the existing exact evaluator. Each listed run has `reset_success=true`; artifacts include report, event/action trace, screenshots/observations, provenance, and owned-resource ledger.

### C-01 Clipboard, task v1.0.3-calibration

| Condition | Run IDs | Result | Evidence |
|---|---|---:|---|
| Solo A | `c01-cal-v103-r01-solo-a-qwen-20261002`, `c01-cal-v103-r02-solo-a-qwen-20261002` | 2/2 pass | Exact Writer final state; no recopy required. |
| Solo B | `c01-cal-v103-r03-solo-b-qwen-20261002`, `c01-cal-v103-r04-solo-b-qwen-20261002` | 2/2 pass | Calc A1 preserved; A2 has BATCH-204. |
| MA-ID | `c01-cal-v103-r05-ma-id-qwen-20261002`, `c01-cal-v103-r06-ma-id-qwen-20261002` | 2/2 joint pass | Both independent Guests pass their own goal; reset verified. |
| MA-SD | `c01-cal-v103-r07-ma-sd-qwen-20261002`, `c01-cal-v103-r09-ma-sd-qwen-20261002` | 0/2 joint pass | No valid A→B clipboard overwrite chain; both failures are focus/input-routing or task failures, not Clipboard attribution. |
| MA-SD startup | `c01-cal-v103-r08-ma-sd-qwen-20261002` | INVALID_INFRA | Guest image default resolved to an empty directory; VM did not become ready. Excluded from model outcomes; failure report/ledger retained and runner recorded owned-resource destruction. |

For r07 and r09, Actor B's Calc copy was observed, but Actor A's subsequent Ctrl+C was routed while Calc was active and did not match Actor A's Writer source digest. Final Writer remained `REF-7319\nINSERT COPIED VALUE`; no Actor A paste action into Writer occurred. The old runner labels for these two runs overstate clipboard overwrite/wrong-paste; raw evidence does not support those labels.

Task-specific model action trajectory and all observer samples are in each run's `model_trace.jsonl` and `events.jsonl`.

### A-01 Application Context, task v1.0.0-rc5-calibration

| Condition | Run IDs | Result | Exposure / recovery |
|---|---|---:|---|
| Solo A | `a01-cal-rc5-r01-solo-a-qwen-20261002`, `a01-cal-rc5-r02-solo-a-qwen-20261002` | 2/2 pass | Actor A exact tab-a goal; reset 2/2. |
| Solo B | `a01-cal-rc5-r01-solo-b-qwen-20261002`, `a01-cal-rc5-r02-solo-b-qwen-20261002` | 2/2 pass | Actor B exact tab-b goal; reset 2/2. |
| MA-ID | `a01-cal-rc5-r01-ma-id-qwen-20261002`, `a01-cal-rc5-r02-ma-id-qwen-20261002` | 2/2 joint pass | Independent Guests, equivalent fixture/goals, both actor goals pass; both Guests reset. No shared-context exposure by definition. |
| MA-SD | `a01-cal-rc5-r01-ma-sd-qwen-20261002`, `a01-cal-rc5-r02-ma-sd-qwen-20261002` | 0/2 joint pass | Actual shared tab switch and wrong-page actions in both runs; no recovery. |

In both MA-SD runs the X11 window ID remained `12582916`. Actor A first observed tab-a and focused its form. Actor B's Ctrl+2 switched the same Chrome window to tab-b. Actor A resumed with tab-b active and typed its tab-a value there, then submitted in tab-b. Final state: both forms empty, tab-b revision 2, actor B non-target integrity false. The evaluator reports `cross_tab_contamination=true` and `wrong_page_action_supported=true`.

The screenshots supplied to Actor A were refreshed before its later actions. Thus this is **not proven stale-image delivery**. The trace supports a stale action plan/target-context: the agent continued the tab-a operation in the newly active tab-b without reacquiring tab-a. No Ctrl+1 return or successful recovery was observed.

## 4. Scripted regression for rc5

New Guest runs (not model evidence):

| Run | Result | Reset |
|---|---:|---:|
| `a01-rc5-scripted-solo-a-r01-20261002` | pass | pass |
| `a01-rc5-scripted-solo-b-r01-20261002` | pass | pass |
| `a01-rc5-scripted-ma-id-r01-20261002` | joint pass | both pass |
| `a01-rc5-scripted-ma-sd-r01-20261002` | expected naive failure, wrong-tab action observed | pass |
| `a01-rc5-scripted-ma-sd-recovery-r01-20261002` | joint pass, recovery control | pass |

Offline regression:
`pytest -q tests/test_browser_context_workflow_v1.py tests/test_clipboard_observer.py tests/test_osworld_agent_actor.py` → **28 passed**.  
`py_compile scripts/run_qwen_family_pilot.py` and `git diff --check` passed.

## 5. Family closure

| Family | Current Qwen evidence | Status |
|---|---|---|
| Focus / Input Routing (F-01) | Historical Solo pass; MA-ID 2/2 joint pass; MA-SD 2/2 joint fail with input-routing evidence. Not rerun here. | Evidence already present |
| Clipboard State (C-01) | Revised Solo A/B 2/2 each; MA-ID 2/2; MA-SD 0/2 but neither has a verified clipboard overwrite/paste exposure. | **Not closed** |
| Application Context (A-01) | Revised Solo A/B 2/2 each; MA-ID 2/2; MA-SD 2/2 fail with same-window tab-switch exposure and wrong-page actions; no recovery. | **Model-level mechanism evidence** |

Three-family closure is **not met** because Clipboard lacks valid Qwen shared-state evidence. Do not begin 200-instance generation.

## 6. Next calibration step

Keep all current traces. For C-01, first address the failure to expose clipboard ownership under MA-SD without forcing an incorrect paste: use a transparent, predeclared turn schedule that pauses A only after the observer verifies A's source copy, permits B to perform its normal independent copy goal, then resumes A with a fresh screenshot. Apply the same schedule to MA-ID as the isolation control, then run at most two repeats per condition. The evaluator and actor goals stay fixed. If A cannot make a valid source copy, or B never changes the content hash, report no Clipboard exposure and keep the family open.

For A-01, preserve rc5 and its two-repeat result; no more repeats are warranted unless new evidence contradicts this pair.

## 7. Reproduction commands

Use the existing 4090 endpoint/tunnel, no A6000 inference. Example:
```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
SWCUB_OSWORLD_GUEST_IMAGE=/home1/mjh/Projects/CoDesk-V0-A6000/assets/osworld-v2.1/guest/osworld-v2-ubuntu-x86.qcow2 \
  /home1/mjh/Projects/CoDesk-V0-A6000/envs/osworld-v2.1/bin/python scripts/run_qwen_family_pilot.py \
  --family app_context --condition ma_sd --run-id UNIQUE_RUN_ID \
  --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/qwen-anchor-calibration \
  --qwen-endpoint http://127.0.0.1:15485
```

The task evaluator was not changed. The report is an analysis of original artifacts plus newly collected runs; no Push was performed.
