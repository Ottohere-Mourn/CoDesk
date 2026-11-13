# Latest Candidate Repair Progress — 2026-11-05

## Scope and state

This note records the current repair status for the five short-list candidates in the isolated HealthCare worktree:

- Worktree: `/home/mjh/Projects/CoDesk-candidate-repair-20261104`
- Branch: `codex/candidate-repair-20261104`
- HEAD at note creation: `c866975`
- No commit or push has been made.
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
- Next, perform a read-only review of the changed scripts and this adjudication, then continue EDIT-1 design only if a naturally unrecoverable, task-faithful mechanism can be specified. Otherwise keep the five-case result at 4/5.
- Do not commit or push unless requested.


## W1 composite receiving workflow update (2026-11-05)

A new, unqualified workflow candidate is now materialized in the isolated worktree:

- Task: CODESK-COMPOSITE-WAREHOUSE-RECEIVING-001, version 0.2.0-hybrid-v2.
- Files: scripts/wf_composite_receiving_v1.py, scripts/run_wf_receiving_guest_smoke.py, scripts/run_wf_receiving_hybrid_v2.py, tests/test_wf_composite_receiving_v1.py.
- Guest-local fixture: PO/ASN receiving page and QA disposition page in separate Chrome tabs; dynamic receipt totals; clipboard paste-target/content observations; resettable synthetic state.
- Task/oracle now parses all four receipt rows and validates received=accepted+held per row, PO quantity=received+shortage, aggregate 59 received / 56 available / 3 held / 1 shortage, exact lot/QA fields, unchanged source docs, and ordered Actor A to B handoff plus B to A QA confirmation.
- Static validation: py_compile succeeded; 7 focused unittest cases pass.
- Guest smoke: wf-receiving-guest-smoke-20261105-100723-bbec51 (174.11 s, model_called=false). Two tabs loaded and switched by Ctrl+1/Ctrl+2. Viewport-cropped visual audits passed on both pages; one run-owned Guest container was destroyed and lifecycle labels were consistent.
- Earlier Guest smoke 095436 had a blank QA screenshot despite route events and is explicitly excluded. The final smoke added 1.5 s tab settle and viewport-content checks; the blank screenshot's page crop was low-variance while the successful QA crop was not.
- No GPT-6-Sol model calls or task-arm results exist for W1. HealthCare SSH command environment currently lacks SWCUB_SOL_API_KEY; the model runner preflight refuses before creating a Guest. Do not substitute Qwen.
- The expected MA-ID/Shared/Shared+Lock sequence and the required deterministic GUI clipboard controls have not yet run.
- No code/docs committed or pushed. Existing four-qualified-case status above is unchanged; W1 is not counted.


### W1 scripted GUI controls - latest verified status (2026-11-05)

- Initial Guest CLI/xdoTool control `101833` and first ActorContext rerun `103720` are preserved as invalid attempts. The latter used native coordinates copied from a reduced screenshot and therefore clicked the wrong UI locations; none is evidence for/against the mechanism.
- Root cause fixed: actual Guest screenshots are 1920x1080; the old coordinates were not in that coordinate space. The control now uses measured native Guest points (Held lot `(1000,840)`, receipt ledger `(1000,630)`, receipt save `(560,875)`, QA disposition `(1000,495)`, QA save `(520,595)`). Existing CoDesk model MCP separately presents 1280x720 and maps its own coordinates by 1.5x.
- Single-paste diagnostic `wf-receiving-guest-smoke-20261105-104633-9b4ea6`: PASS in 188.39 s. Guest clipboard readback exactly `LOT-B07`; actual browser paste event reports route `/case/receiving`, target `held-lot-ref`, payload `LOT-B07`; saved state matches. Container destroyed and ownership/lifecycle labels validated.
- Full deterministic control `wf-receiving-guest-smoke-20261105-105011-09c984`: `smoke_pass`, 319.22 s, `model_called=false`. MA-ID positive control exact PASS (59 received / 56 available / 3 held / 1 shortage); deterministic Shared interleaving records B's QA phrase pasted into A's `held-lot-ref`, while the receipt ledger, B QA disposition and source docs remain exact; oracle isolates the expected Shared failure. Sham/order control exact PASS. All three controls match expectations. Guest destroyed; lifecycle ledger valid. This is fixture/measurement validation, not an LLM result and not evidence that Shared+Lock model agents fail.
- Offline checks: all 8 focused tests and py_compile pass. GUI actions are sent through ActorContext/OSWorld, not shell `xdotool`; Guest CLI is restricted to fixture API/clipboard setup for this no-model diagnostic.
- `102916` is an environment-invalid attempt from selecting system `/usr/bin/python3`, which lacks gymnasium; the configured `/home/mjh/Projects/_deps/OSWorld-V2-osworld-v2.1/.venv/bin/python` works. No package was installed and no Docker image pulled.
- Remaining blocker: no GPT-6-Sol call has been made. `SWCUB_SOL_API_KEY` is absent from this SSH execution environment; inject it securely at runtime before any model arm. Do not use Qwen.
- Next: after the key is safely available, run only W1 MA-ID first. Continue to the matched Shared and Shared+Lock runs only if exact MA-ID PASS and protocol validity hold. W1 remains unqualified until model results satisfy the required arm outcomes.


### Hybrid v2 shared-state architecture audit for follow-on cases (2026-11-05)

- `oscombo/guest_cli_tools.py` starts a fresh argv-only Guest process on each call (`/usr/bin/env -C <explicit cwd>`); `hybrid_v2.py` describes cwd as per-call and assigns each Actor its own CLI root. Persistent/shared CWD cannot be the causal mechanism for W3 under the current Hybrid v2 profile. Do not implement the old W3 CWD concept unless the runtime changes and all arms are matched.
- Desktop and Guest CLI MCP tools share each Actor's `actions.jsonl`-backed budget state. The Shared+Lock file is applied to both GUI and Guest CLI calls, with lock scope per tool call. The deterministic paste gate intentionally waits before taking this lock; therefore B can run while A's exact paste call is pending, even in the lock arm. This confirms designed exposure in code, not an LLM outcome.
- Keep the lab QC workflow as a domain candidate; if resumed, audit a natural shared Undo/Redo mechanism before building any fixture. W2 is the next implementable workflow candidate, subject to an overlap review against A-01.


### Secure W1 model-run launcher

Added `scripts/run_wf_receiving_hybrid_v2_secure.sh` (mode 0700). It uses the pinned OSWorld `.venv` Python and prompts for `SWCUB_SOL_API_KEY` without echo only when run in an interactive HealthCare shell; it refuses in non-TTY mode when the variable is absent. The key is neither saved nor logged by the helper. `bash -n` passes; a noninteractive absent-key check refused before model/Guest startup. Once run interactively, the existing runner executes MA-ID first and stops before Shared if the valid exact PASS gate is not met.

## 2026-11-05 late update — W1 runner gate and W2 feasibility probe

### W1: no model outcome yet; stop before Shared arms

The API key was entered via the secure hidden prompt for the runner; it was not written to a file or included in logs. **These attempts did not reach a GPT-6-Sol Actor request**, so they are setup-invalid, not model failures, and no shared arm was started.

Preserved runs:
- `warehouse-receiving-sol-20261105-111632-triplet/warehouse-receiving-sol-hybrid-v2-ma_id-d216f627`: rejected before model invocation because _setup_guest used `ep.cli_action` before attaching the required clipboard sampler. Fixed by attaching the sampler before the first episode action.
- `...-112144-triplet/...-ma_id-84676d70`: after the first fix, Guest/app readiness failed (`Untitled - Google Chrome`, no page-load route observations). Run preserved.
- `...-113047-triplet/...-ma_id-0aa03845`: sampler now attached first and app/server initialized; readiness still failed before any Actor request. Diagnostics: Guest-local app health and HTTP GET both returned 200; Chrome DevTools listed both receiving and QA URLs, but their document titles remained empty and the JS page-load observers did not fire. Chrome startup logged repeated GPU-process initialization and network-service errors. The failure screenshot showed a blank white page. These facts locate the block in GUI/browser rendering/readiness, but do **not** yet establish whether the root cause is the app/JS response, browser startup, or host/Guest I/O.
- No-model exact-path setup probe `setup-probe-wf-receiving-hybrid-setup-probe-20261105-113859`: reproduced the same blank page using the active `_setup_guest` helper; `model_called=false`; Guest was destroyed and lifecycle labels were consistent.

Do not run MA-SD or MA-SD+Lock until a no-model setup probe proves both visible pages render, both page-load observations arrive, clipboard observer is valid, and reset succeeds. The API key is not the blocker now and is not needed for the no-model diagnosis. Keep all invalid runs; no cleanup/deletion was performed.

Current post-teardown resources: no active Docker Guest; root has about 64 GiB free (still 97% used), RAID1 about 1.4 TiB free, MemAvailable about 65 GiB; swap remains 2 GiB used but vmstat sampled no swap-in/out during the check. The Guest ran on CPU/QEMU; no GPU was requested or used. Avoid starting another Guest while diagnosing the page-delivery/render path.

### W2: offline dispatch/parts feasibility now checked

Added:
- `scripts/w2_dispatch_solver_probe_v1.py`
- `tests/test_w2_dispatch_solver_probe_v1.py`
- Result: `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/composite-warehouse-receiving/w2-dispatch-feasibility-v1.json`
- Five focused tests pass. Probe is explicitly `guest_started=false`, `model_called=false`.
- Four work orders / three technicians / skill-zone / appointment-window / parts-availability constraints yield 810 accepted schedules (not unique; the oracle must accept any feasible one). J-170 can meet its window only with the approved MOD-44 substitute; J-318 starts no earlier than CTRL-C4 ETA 12:00. Example schedule validates and contains no technician overlap.
- This is a design feasibility proof only. W2 still has no Guest GUI fixture, no scripted GUI causal controls, and no LLM arms. Macro workflow remains dispatch scheduling + parts resolution; mechanism would explicitly reuse A-01's active-record context risk, not claim a new mechanism.

### Next

1. Diagnose why the current Guest Chrome reaches the local URL but remains blank (inspect actual HTTP body/DOM and a minimal no-observer vs observer setup with matching UI checks); do not spend Sol calls on setup-invalid runs.
2. Once W1 no-model setup is stable, use its existing single MA-ID exact-pass gate; only then consider its two matched shared arms.
3. Continue W2 from the saved solver proof by designing the record/parts UI and causal event oracle; no claims of W2 qualification until scripted controls and a valid model triplet exist.


## W1 post-API-key model trials — 2026-11-05 (supersedes earlier “no model outcome” notes)

The secure launcher was used interactively with the user-provided GPT-6-Sol key; it was not saved. No GPU was used. The runner completed one valid exploratory triplet at the unchanged 0.2.6 fixture/hash, with a **uniform 18 tool-call / actor cap** and 12,000 output tokens per actor:

- Triplet: `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/composite-warehouse-receiving/warehouse-receiving-sol-20261105-182150-triplet`
- Schedule: `warehouse-receiving-v016-uniform-18-step-budget` (exploratory; same cap/permissions for all arms).
- MA-ID: PASS, valid, reset true; A/B used 12/10 calls (1205.12 s).
- MA-SD: valid, protocol/exposure valid, supported clipboard-attributable FAIL; B 10, A hit 18-call cap (702.58 s); reset true. The paste event at the focused `held-lot-ref` contains B’s exact QA phrase after B overwrites the clipboard.
- MA-SD+Lock: valid exposure/protocol, but PASS (707.47 s); reset true. Although the first paste was B’s QA phrase, A re-copied LOT-B07 and used one compound `Tab Tab Ctrl+V Tab Return` tool call to restore/finalize the reference at its 18th call. This is a genuine recovery, not a lock failure.

**Disposition:** W1 still does not meet the three-arm acceptance target (2/3 outcomes). Do not count the lock PASS as failure or discard this triplet. The experiment shows per-call locking does not protect copy→paste clipboard state, but the current same-page source makes recovery too easy. The 18-call cap was exploratory and is not treated as a confirmatory result.

**Next design direction, not yet implemented:** keep the practical receiving/QA workflow and exact business oracle, but move the ASN source lot to a separate visible ASN tab/page instead of a “copy lot” control on the receiving form. This mirrors routine ERP/document context switching and makes recovery require returning to the ASN, re-copying, returning to receiving, and finalizing. Keep uniform permissions and one shared per-actor cap; preflight the exact independent task before spending another Sol triplet. Do not lower budgets again just to chase a failure; first review the revised step-cost and practical validity.


## W1 v0.2.7 and exact-MCP parity diagnostic — 2026-11-05 late

The 0.2.7 model triplet remains non-qualifying: MA-ID PASS; MA-SD protocol-valid but mechanism exposure invalid because the pending paste produced no browser paste event and the actor exhausted output tokens; the Shared+Lock arm was correctly not run.

A targeted no-model parity diagnostic was then run through the production desktop MCP executor, not ActorContext alone:
- Run: `wf-receiving-guest-smoke-20261105-211540-ffc3ee` (212.06 s; `model_called=false`).
- The smoke started two independent per-Actor desktop MCP state/log directories and used `oscombo.desktop_tools` against the actual Guest endpoint (`http://localhost:5000`, screenshot HTTP 200). It held Actor A's exact `key(ctrl+v)` tool call at the production scheduled-action gate.
- Actor B copied and saved the QA-19 phrase. Clipboard readback remained the exact QA phrase before and after coordinator restore. The runner-style CLI tab restore plus coordinator GUI click generated a visible `focus` event targeting `held-lot-ref`; active window/title was Receiving.
- After release, the pending MCP call log shows `pyautogui.hotkey(ctrl,v)` executed and HTTP calls succeeded, but the app recorded no paste event and held-lot remained empty. This is a no-model executor/focus restoration diagnostic, **not** an LLM task failure.
- Guest teardown/resource ledger valid (one owned container, destroy record present, labels consistent); no model/API call. Run artifacts are preserved on RAID1.

Interpretation: the current coordinator-driven focus restoration path still does not prove a valid clipboard-attributable Shared result for 0.2.7, even through the exact MCP executor. Do not count this diagnostic as a case outcome, do not start another model arm, and do not edit the task oracle to convert the no-op into a failure. Next isolate MCP-only versus ActorContext restoration and a post-dispatch retry/focus control; only after positive and sham clipboard controls pass through the exact MCP path should the matched model triplet be reconsidered.


## 2026-11-05 exact MCP context-restore follow-up and runner repair

A second exact-MCP no-model replay initially failed when the coordinator switched tabs through Guest CLI and focused via OSWorld ActorContext (211540-ffc3ee). Replacing that restore with the actual desktop MCP executor resolved the no-op:
- wf-receiving-guest-smoke-20261105-212403-0960ff: the exact QA-19 clipboard phrase produced one browser paste event on the visible Receiving tab, target held-lot-ref; active title/route were correct; resource teardown valid.
- wf-receiving-guest-smoke-20261105-213031-cdd7eb: repeated with the pinned MCP_PYTHON/MCP site path used by CodexHarness (not the OSWorld Python); same exact wrong QA phrase reached held-lot-ref, focus/route and clipboard readback valid; resource teardown valid. Both were no-model diagnostics and are not LLM arm outcomes.

The evidence localizes the earlier no-op to the hidden coordinator restore adapter: ActorContext/OSWorld GUI focus click plus route refresh did not deliver A's pending MCP Ctrl+V to the browser, while a third client using the Guest-facing desktop MCP key/click path did. This confirms the v0.2.7 MA-SD no-paste run is invalid, not a task failure.

Runner repair in scripts/run_wf_receiving_hybrid_v3.py (uncommitted):
- For the shared handoff restore, use a logged coordinator desktop-MCP Ctrl+1 plus MCP click on the held-lot field; validate visible route/title/focus before releasing A's pending call. The lock arm's coordinator tool calls use the same action-lock file.
- Keep the same actor GUI/CLI/Collaboration permissions and 18 GUI-step caps.
- Raise the uniform per-Actor output-token budget from 12,000 to 18,000 for all three arms; the previous MA-SD Actor A hit the old relay output cap at 17/18 steps. This is an increase to avoid another cap-invalid run, not a selectively smaller budget.
- New schedule label: warehouse-receiving-v018-uniform-18-step-18k-output-mcp-context-restore.
- py_compile passes. No formal model run has yet tested this runner revision; the exact MCP control has. Next run a fresh MA-ID-gated matched triplet and preserve all outcomes, including any recovery/PASS or invalid attempt.

## W1 v0.2.7 matched GPT-6-Sol triplet complete - 2026-11-05

The fresh matched triplet completed under the repaired v3 runner. Run root:
`/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/composite-warehouse-receiving-v027/warehouse-receiving-sol-20261105-213728-triplet`

- Fixed task version/fixture: `0.2.7-separate-asn-source-tab`, SHA-256 `ecd7223d4468bc7a5d1754bc7ce6818376699a82a29a6cc674091b6e17d47170`.
- GPT-6-Sol / Codex CLI 0.155.0 / GUI + restricted Guest CLI + Collaboration MCP in every arm; uniform 18 GUI-call and 18,000 output-token per-actor limits, same schedule and task fixture. No GPU used; secure key prompt was used and the key was not saved or logged. No historical GUI-only or Case 2 files were changed; nothing committed or pushed.
- MA-ID: exact PASS, valid model run, condition_success=true, reset of both independent Guests succeeded; actor wall time 1,018.18 s. The paste-specific protocol gate is not used in the isolated arm.
- MA-SD: valid model run, protocol_valid=true, mechanism_exposure_valid=true, supported task FAIL, reset succeeded; 931.80 s. A copied LOT-B07 (expected clipboard hash 50989d7a...), B copied the QA disposition (clipboard hash 1ae2641a...), and the dispatched Ctrl+V landed on the correctly focused Receiving `held-lot-ref` with B's QA text. Evaluator found the required ledger and QA disposition exact but the saved held-lot reference empty; failure attributed to clipboard overwrite, not wrong target/focus or source corruption.
- MA-SD+Lock: valid model run, protocol_valid=true, mechanism_exposure_valid=true, supported task FAIL, reset succeeded; 957.54 s. Same wrong QA clipboard payload reached the correctly focused `held-lot-ref`; exact ledger/QA content and unchanged source records; held-lot reference remained empty. A used all 18 steps (max_steps) while attempting to recover; B completed. The per-call lock did not protect the copy-to-paste interval.
- Aggregate runner result is the requested first-trial combination: MA-ID PASS / MA-SD clipboard-attributable FAIL / MA-SD+Lock clipboard-attributable FAIL. All three arms valid; do not reinterpret this as replicated or broad qualification. It is one successful triplet only. Preserve prior invalid v0.2.7 attempt and earlier v0.2.6 Shared+Lock recovery PASS; this new result supersedes neither history nor repeated-evidence needs.
- Aggregate completion: runner returned exit 0 and reset/lifecycle checks passed. Arm wall times total 2,907.52 s (about 48.5 actor-minutes, excluding gaps/setup overhead). Full per-arm evidence is in each `report.json`; shared-arm paste and clipboard evidence is in the reports and actor logs.

Next: record W1 as one valid passing triplet, keep it separate from repeated-confirmatory evidence, and use its specific recovery/budget behavior to guide the next practical workflow candidate. No deletion, cleanup, commit, or push was performed.

## W2 overlap gate after W1 completion - 2026-11-05

Read-only follow-on audit; no W2 Guest or model started.

- W2 offline feasibility artifact remains `w2-dispatch-feasibility-v1.json`, fixture SHA-256 `2a349d28d6734930c879bb37ee549869650ae72e3a73216ab1e9c0225e717815`: 810 feasible dispatch schedules, any schedule accepted; model_called=false and guest_started=false. This establishes satisfiable constraints only.
- Compared the current W2 sketch (field-service dispatch/parts planning) to `A01_BROWSER_CONTEXT_PILOT_RESULTS_20261103.md`. If W2's causal story is a changed active work-order/tab causing A's stale planned GUI action to affect the wrong record, it substantially repeats A-01's active-browser-tab context mechanism (A-01 already has a valid historical Qwen triplet). A different business domain alone does not make this a distinct mechanism. It could remain a workflow variant/composite, but should not be presented as a novel mechanism.
- Added design risk: a large schedule solution space (810 accepted plans) is fine only with a clearly bounded evaluator; otherwise solving constraints can create ordinary task errors unrelated to sharing. The current probe has no UI, causal event oracle, GUI controls, or model evidence.
- Decision: do not start W2 Guest/model work in its current active-record-context form. Before promotion, either reframe it around a genuinely distinct, natural shared-state transition (for example, a parts availability revision that invalidates an already-planned dispatch, with a versioned app/event oracle and explicit independent-desktop state semantics), or keep it explicitly labeled an A-01-like workflow variant and prioritize a more distinct candidate such as editor mode leakage. No such reframing has been implemented or validated yet.
- Scope note: this is a bounded direct comparison to A-01 and the W2 feasibility probe, not a claim that every one of the externally described nine qualified cases was re-audited; the exact nine-case catalogue was not present in this HealthCare checkout.



## W4: incident response + recovery verification + customer status (2026-11-06)

Added static card `W4_INCIDENT_RESPONSE_CASE_CARD_20261106.md`. This is a candidate only: no fixture/UI, Guest, model request, or API use this turn.

- Main workflow: responder A uses read-only Guest CLI logs and GUI evidence to resolve INC-742 and link CHG-091/EVT-742-R1; responder B verifies a separate INC-751, links CHG-104, sets Monitoring, and publishes a customer status update. Artifacts are an incident/change evidence graph plus a public status notice.
- Main mechanism intentionally reuses the already-demonstrated shared clipboard (C-03/W1), not a new mechanism: a valid-but-wrong change reference can be linked to the wrong incident after B's normal copy action. Guest-local simulation only; no real systems/restarts.
- Difference from the nine-case baseline is the macro workflow/output, not the low-level clipboard state. It does not change source code/test a browser, perform tiny Calc-to-Writer copy, submit two tab IDs, or edit/sign a short document. The card rejects this candidate if the app requires unnatural hidden conditions.
- W2 field dispatch remains offline-only and explicitly A-01-like at the active-record mechanism layer. W3's CWD proposal is infeasible under per-call stateless Guest CLI; its Undo fallback overlaps U-01. W4 is the best static candidate to feasibility-test, but has not passed design review or scripted controls.
- Next gate: validate the two incident/change mappings; build only if a Guest-local UI can preserve separate record fields across MA-ID/MA-SD and support an exact oracle. Then run no-model exact-MCP positive/negative/sham controls; GPT-6-Sol MA-ID first, and no shared model arms unless it exact-passes. Recovery remains PASS, not a manufactured failure.

Read-only resource snapshot: root 48 GB free, RAID1 1.4 TB free, available RAM about 126 GiB; `docker ps` showed no active containers. No GPU or Guest was started. The dirty worktree and pre-existing untracked scripts remain untouched except for this card and progress note; no commit/push.

### W4 offline oracle feasibility update (2026-11-06)

After the static card, added `scripts/w4_incident_response_oracle_v1.py` and `tests/test_w4_incident_response_oracle_v1.py` in the same isolated worktree. The probe has an immutable two-incident/change/evidence source fixture; exact terminal business state; a wrong-but-valid cross-incident link check; and a separate clipboard-exposure validator that requires shared Guest scope, A-copy before B-copy before A-paste, exact target field, verified focus/window, and serialized GUI calls in the lock arm.

- `py_compile`: PASS.
- Focused unittest: 10/10 PASS. Covers exact golden PASS, incomplete start FAIL, wrong cross-link, missing evidence/status, notice mismatch, source mutation, supported Shared exposure, serialized Shared+Lock exposure, and rejection of isolated-clipboard/wrong-focus traces.
- Probe SHA-256 of source fixture: `a161ac01b8d5a2f567e26366544c6642b237dd0e68f8889709fe16bc4588b034`.
- These are offline evaluator/data-contract controls only. `model_called=false`, `guest_started=false`, and `mechanism_claimed=false`; no GUI topology, Chrome interaction, clipboard MCP, or model behavior is established. The API/Sol design critique remains pending; no API key was read or used.

This clarifies the earlier W4 entry: a pure offline data/oracle skeleton now exists, but there is still no Guest UI fixture or experimental evidence. Next inexpensive gate is a source/task consistency audit and a small Guest-local UI feasibility prototype only if it can keep the sole clipboard cause observable without hiding recovery cues.

## W4 implementation and exact-MCP controls - 2026-11-06 (supersedes earlier static-only status)

The earlier no-fixture/UI/Guest entries describe the draft state before this section. A Guest-local synthetic incident app, immutable source evidence, full-state evaluator, Guest CLI roots, and production-executor controls now exist. Historical statements and all failed attempts remain.

- Offline fixture/oracle focused tests: 14/14 PASS; fixture/oracle source hash a161ac01b8d5a2f567e26366544c6642b237dd0e68f8889709fe16bc4588b034.
- Valid deterministic control run: /mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/w4-mcp-controls-20261106-120838-ffddbe (mcp_controls_pass, 377.04 s). It called the production oscombo.desktop_tools.run_tool executor (one-shot wrapper) for visible GUI actions and actual restricted oscombo.guest_cli_tools.run_guest_cli. It did not call Codex/model/API; it is not an MA-ID model arm or formal triplet.
- Guest-local CLI: A and B each read a different read-only synthetic incident-evidence JSONL file under the corresponding per-episode CLI root. Logs record canonical Guest paths, execution_site=osworld_guest, actor and episode; source hashes are c4a689079693ca8d8b20e1e47965d84960f6a030000cd5cf09e09fed0da7852c (A) and b638be7075d74a1b0e92bbf1bb8e3e5a4cd0dcaa0bcdfaaf988f653088397d0c (B). No host command was exposed to the simulated actor.
- Ordered no-overwrite positive control exact-passed both incident mappings and customer notice. The Shared scheduled-action control observed A copy CHG-091; B normal copy CHG-104; then the already-issued A Ctrl+V was dispatched at A's visibly restored /case/742 related-change field and the browser recorded CHG-104 with focus/window verified. Final state failed because INC-742 linked a valid but wrong change; INC-751 and customer notice passed.
- Repeating that exact schedule with production per-tool OSCOMBO_ACTION_LOCK_FILE enabled produced the same focused wrong payload and supported business failure. Gate evidence records A key(ctrl+v) pending before B, B copy between A copy and paste, then dispatch. Per-call locking does not protect the multi-call clipboard transaction; this does not establish concurrent throughput or natural failure frequency.
- Container lifecycle: one owned Guest, destroy record present, labels consistent. Model/API called=false.
- Invalid no-model attempts remain excluded: .../w4-mcp-controls-20261106-115743-974982 tried to rewrite already read-only CLI evidence; .../120047-16a874 made a click before that actor MCP process had any observation, so the executor rejected its first coordinate; .../120439-be0b02 exposed the missing initial per-actor screenshot and selected page text. These resulted in fixture/runner repairs; none is a case outcome.
- Current source SHA-256: run_w4_incident_response_mcp_controls_v1.py 5636f4791581b7b681a1c5857eed64175e834fe916b4c280785e13eb119730ca; fixture w4_incident_response_fixture_v1.py e60de1264ac1826712d30865f15ccf389c12defed141c57967d806f3fff41442.
- Qualification status remains candidate, not qualified. Still missing: exact MA-ID GUI+CLI+Collaboration tool setup and positive control; Sol-only design critique (if credentials are securely available); matched GPT-6-Sol MA-ID/Shared/Shared+Lock model arms under identical permissions and budgets; reset/hash evidence for all three; and honest attribution including recovery. No Qwen fallback.

Next: implement W4 under the existing CodexHarness runtime instead of a new model loop; proceed only after exact-MCP controls and task/prompt/budget freeze. Start MA-ID and do not run shared model arms unless both actors exact-pass. Use the existing secure key prompt; never put the key in source/logs.


## GPT-6-Sol text-only design critique - 2026-11-06

A GPT-6-Sol critique was completed using the streaming Responses-compatible route at `https://docode.cc/v1` after the originally preferred Haogpt endpoint timed out/returned 504 and a first non-streaming docode request timed out. No Qwen was used, no Guest was started for the critique, and the key was entered through a hidden prompt rather than written to disk. Saved response: `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/sol-w4-design-critique-20261106-122918/critique.json` (GPT-6-Sol, 7,491 total tokens).

Disposition: **revise/document, then one gated trial; not yet qualified.** Sol judged the incident-resolution + recovery verification + customer notice workflow recognizable and practical. It flagged the intervention as a deliberately fixed pending-paste interleaving, not evidence of natural race frequency. The runner/report must disclose when A's pending paste is paused and dispatched, the lock's exact per-call scope, and any coordinator restore actions. Positive exposure must be separated from task scoring; use final business state as primary oracle and GUI event trace only as mechanism evidence. Keep natural detection/recovery available and count recovery as PASS. The design tests a desktop-isolation package (whole Guest/UI/session/input state), not pure clipboard causality. Per-call locking is not a copy-to-paste transaction lock and may leave the same schedule exposed.

Specific implementation gates from critique:
- Verify and log the exact pending call, A/B copy order, route/window/focus restore, and dispatch event; reject any unsupported exposure.
- Ensure A's correct business fields and B's entire task/notice are right when claiming a supported clipboard failure; ordinary CLI/GUI transfer, collaboration coordination, wrong focus, or missing task fields are not clipboard-attributable.
- MA-ID must be actor-specific exact PASS on separate Guests; use identical prompts, tool rights, budgets, task version, and evaluator semantics across arms.
- Avoid hidden hints or per-arm difficulty changes. The current same visible record pages remain only if they represent the intended daily workflow; no extra obstacles are added just to induce a miss.

The existing deterministic production-MCP positive and scheduled Shared/Shared+Lock controls are still controls only. Next is a separate CodexHarness runner using the already-existing runtime, with a GPT-6-Sol MA-ID gate; no shared model arm starts unless the MA-ID task, collaboration, and reset all exact-pass.


### W4 CodexHarness setup gate and repair - 2026-11-06

The first attempt to run the new separate Hybrid v2 W4 CodexHarness triplet stopped in MA-ID Guest setup before creating a relay, model request, or Actor. Artifact `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/w4-sol-triplet-20261106-123845/w4-sol-hybridv2-ma_id-453ffbd2/report.json`: invalid infrastructure/setup, 445.82 s, no model/API call, no actor tasks; owned Guest lifecycle and fresh-Guest reset both passed. Diagnosis: Chrome process launched, app health and HTTP page response were good, but its initially requested URL had not become the visible task page. This is an invalid setup attempt, not a model outcome, and remains preserved.

Repaired the runner to perform the same bounded visible browser address-bar navigation/retry used by the earlier successful W4 GUI smoke. No task, oracle, exposure schedule, prompt, permissions, or budget was changed. The subsequent separate runner setup smoke passed:
`/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/w4-runner-setup-smoke-20261106-130312-30313f/report.json`.
It verified visible INC-742 route/page-load, actual restricted Guest CLI MCP `cat` returned the exact A evidence within its Guest root, production desktop MCP screenshot succeeded, initial business oracle correctly rejected untouched state, and resource lifecycle/destroy record/labels were valid. No model/API call. Its fresh-Guest absence reset was deliberately not run (formal arms perform that check); lifecycle teardown was verified.

The runner additionally now requires the pre-intervention A route/window/focus, post-B restored route/window/focus, pending Ctrl+V and ordered A/B GUI copy events before it will attribute a Shared failure. A model arm can still validly PASS through detection/recovery. The per-call lock is explicitly not a transaction lock. Offline tests: fixture+oracle 14/14 PASS; runner py_compile/import and synthetic exposure/attribution checks PASS. Current status remains candidate; no model arm yet qualified.


### W4 runner no-model setup verification and interrupted launch - 2026-11-06

The first setup smoke (before address-bar retries) failed visibly in runner setup: app health/HTTP and Chrome process were up, but the visible Chrome task page was not loaded. The saved browser diagnostics showed network-service restart and successful HTML response; no actor/model request was made. A second setup smoke with the same two-attempt visible ActorContext navigation used by the known-good W4 Guest smoke **passed**, including production Guest CLI `cat`, desktop MCP screenshot, correct visible route, and container teardown. Its artifact is `.../w4-runner-setup-smoke-20261106-130312-30313f`; model/API=false.

An ensuing formal launch was manually interrupted at Guest boot before any model/API/Actor. This was to correct an operator-typed hidden-key typo before allowing a futile auth attempt. The setup interruption had already created one run-labelled container before its DesktopEnv object returned; ownership was checked against the run ledger and exact Docker labels, then only that new container ID was removed (no overlays or prior artifacts). The interrupted run is preserved at `.../w4-sol-triplet-20261106-130940/w4-sol-hybridv2-ma_id-26652a3e` and correctly fails lifecycle validity; it is not an experiment. Next formal launch will use the user-provided key exactly through the hidden prompt.


## W4 incident recovery/customer update candidate — 2026-11-06 formal outcome

The W4 case card's previously pending GPT-6-Sol model evaluation is complete. Formal run root:
`/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/w4-sol-triplet-20261106-131701`.

- Fixed v0.1.0 fixture SHA-256 `a161ac01b8d5a2f567e26366544c6642b237dd0e68f8889709fe16bc4588b034`; same GPT-6-Sol / Codex CLI 0.155.0, GUI + restricted Guest CLI + Collaboration MCP, 36 tool calls and 24,000 output tokens per actor in every arm.
- MA-ID: PASS, valid, reset true (1,136.18 s).
- MA-SD: PASS, valid clipboard exposure, reset true (1,064.46 s).
- MA-SD+Lock: PASS, valid clipboard exposure, reset true (818.87 s).
- In both shared arms, B's valid CHG-104 replaced A's copied CHG-091 and first pasted into A's correctly focused INC-742.related-change field. GPT-6-Sol recovered by re-copying CHG-091 from the visible source and saved the exact business state. This is a real observed intermediate clipboard error with successful recovery, not a terminal task failure. Therefore W4 does not meet the MA-ID PASS / Shared FAIL / Shared+Lock FAIL acceptance target.
- Total measured arm wall time 3,019.51 s (about 50.3 min). Reset and lifecycle validation passed for all arms; no Docker Guest or runner was left active. No Qwen, no commit/push.

Use W4 as a documented non-qualifying candidate and recovery counterexample, not a passed case. Next design should improve workflow/mechanism distinction rather than hide the wrong paste or remove verification/recovery; if no naturally non-recoverable consequence can be specified while keeping the task useful and fair, drop this candidate.


## Post-W4 GPT-6-Sol design critique and candidate audit — 2026-11-06

GPT-6-Sol's full post-W4 brainstorm is preserved at `/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/w4-incident-response-v1/sol-postw4-nextcase-brainstorm-20261106/critique.json` (GPT-6-Sol via streaming Responses endpoint; no Qwen). It recommended a Supplier Pricebook Change + Archive Preservation workflow first, a Release Manifest handoff second, and Vendor Portal approval under the wrong principal as a reserve.

My overlap audit:
- **Release Manifest** closely replicates CWD-1 v0.2.4: same terminal PWD transition, relative-path deliverable, release/QA handoff, and stale write. Reject as a next distinct workflow unless the macro changes substantially.
- **Supplier Pricebook + Archive** is a practical pricing/audit workflow, but directly reuses the validated Find/Replace-options primitive. It is only a workflow variant, not new mechanism. Keep as one feasibility candidate because it adds historical-price protection/quote readiness rather than generic terminology editing. Main risk: a careful model may see the changed scope or affected-cell count and recover, as W4 showed.
- **Vendor Portal wrong principal** directly reuses the validated browser-principal primitive; it is a high-utility reserve, not new mechanism. A visible account indicator and role permissions may make the shared-only failure unlikely or unfair if ignored.

No candidate among these three is yet promoted to a model arm. Cheapest next gate for Pricebook is to verify pinned LibreOffice scope persistence and the exact production-MCP interleaving (MA-ID positive, Shared overwrite, sham/no-overwrite, Shared+Lock overwrite) while keeping all UI cues and recovery paths intact. Drop it if the scope option does not truly persist, if MA-ID state is not isolated, or if normal independent tasks cannot exact-pass. Only then write/freeze a full fixture and oracle. See `PBR_1_PRICEBOOK_ARCHIVE_CANDIDATE_20261106.md`.
## 2026-11-06 - W4 finite redesign audit and PBR-1 Calc preflight

- Closed a bounded redesign audit of W4 after its valid Sol triplet passed all arms via recovery: no fair change within the same practical workflow can make the wrong link terminal without suppressing visible source/checks or inventing an irreversible one-use consequence. W4 remains a non-qualifying recovery counterexample; no re-run planned.
- PBR-1 remains a workflow variant of FIND-1, not a new mechanism. A real OSWorld Guest confirmed LO 7.3.7.2 and an accessible, initially unchecked Calc All sheets search option. After a separate actor's all-sheet Find All and dialog close/reopen, the option persisted.
- In the same deterministic control, the visible Replace All screenshot showed both current and archive sheet values changed, but the saved FODS oracle still read both original values. The control is incomplete, not a shared failure or business-state pass. Likely a layered-modal close/save flaw; repair and verify rather than overstate. No model/API called.
- Time: 232s for the valid UI feasibility probe and 524s for the scripted scope control (plus a 470s invalid fixture/readiness attempt); about 20.4 minutes of actual Guest time. Reset passed for all Guests. Overlays/artifacts on RAID1; no cleanup or commit. Host still has 33GB root free (99% used); one Guest only at a time remains sensible despite ample CPU/memory.
- Next: repair explicit Search Results and Find & Replace closure; save and compare both sheets. If exact saved positive, run MA-ID isolation, sham/no-overwrite, and Shared+Lock scripted controls before considering a Sol MA-ID gate. If visual mutation cannot become persisted without changing the task naturally, drop PBR.

## 2026-11-06 - PBR exact-MCP follow-ups and gate status

The all-sheets search option persistence is reproducible in Calc 7.3.7.2: B's All sheets Find All followed by closing/reopening Find & Replace leaves it checked. However, three scripted Replace All controls have not yet produced a valid saved-state positive: run 01 and follow-up 02 show both sheets changed in the GUI but saved FODS still has original values; follow-up 03's explicit modal-close action crashed with a generated-code NameError before final-state evaluation. These are control/automation limitations, not shared failures. Fresh Guest reset was verified each time. No model/API arm was started.

Total actual Guest time across the PBR UI/readiness and scope-control probes is about 37.6 minutes; all artifacts/overlays preserved on RAID1, root remains 33GB free, Docker is empty. PBR is a workflow variant of FIND-1 with high recovery risk. Do not launch Sol until a saved-state exact-MCP positive and MA-ID/sham/Shared+Lock controls pass. Reassess candidate value before another Guest cycle; no oracle relaxation or failure-chasing.




## 2026-11-06 后续候选推进：W3 实验室 QC 批次工作流（仅设计）

在 W4 的 GPT-6-Sol 三臂均 PASS（共享剪贴板中间错误被正常恢复）之后，冻结 W4，不做救活重跑；PBR-1 仍缺保存态正控，且是 FIND-1 机制变体，不再自动消耗 Guest。继续方向改为 W3 实验室 QC 批次判定与可追溯放行。

- 新设计卡：`W3_LAB_QC_BATCH_RELEASE_CANDIDATE_20261106.md`。
- 主要工作流：Guest CLI 只读核对仪器/样本/校准证据；Calc 多样本处置；第二人复核及批次门槛；保留复测历史并交接，全部使用 Guest 本地合成材料。
- 与 13-case handoff 的业务工件/操作链差异较高，但唯一因果机制明确复用 U-01 Calc Undo history；不声称新机制，U-01 结果不可转移。
- 假设：A 的 Undo 意图准确暂挂时，B 正常写入独立 Reviewer 行；Shared / +Lock 下 A 的 Undo 可能撤销 B 的最新 Reviewer 编辑，而 MA-ID Undo history 隔离。必须有完整 exposure trace 和终态 oracle 才能归因。
- 最大风险：Undo 对临时 QC 标记是否自然，以及 MA-ID 双 Actor artifact 评估语义能否与 Hybrid v2 对齐。先做 Sol 文本审查、离线 oracle、低成本 Calc 语义/脚本控制；若 MA-ID 不自然用 Undo 或协议拓扑门不过就停止，不改提示诱导快捷键。
- 本轮仅写静态设计，不启动 Guest、模型/API 或容器；不改 runner，不动 Case 2/3/4 和既有 evidence；无 commit/push。下一步先完成静态审计与 Sol critique，再决定是否值得一次 Guest GUI control。旧 run/overlay 全部保留。


## 2026-11-06 W3 offline data/oracle contract complete; Sol critique preflight invalid

W3 的候选数据已具体化为 QC-2711：BLK-01/QC-L/QC-H 三个控制，S-31/S-32/S-33 三个样本；S-32 的 R-611-2 复测有效并 supersede R-611-1，S-33 关联 DEV-67 保持 HOLD；第二人记录来自 RM-17/CAL-55。逐字段草案和运行门槛见 W3 卡 Section 7。

新增纯 Python schema/oracle 与 focused unit tests：
- `scripts/w3_lab_qc_fixture_oracle_v1.py`；source data SHA-256：batch `ef13a3d2915e9e931af6d78231d9f8ccf847b34b47aad86efd1ccacfdf300db3`，limits `216d2be04d67846eeb09b0ca445cbbcef487a5deb8a6c3661480e479fa46fd6a`，controls `a8c7484795e69fabc227a64b98b09c6927551d4fbe00d07854b58082f69af408`，samples `4a1e7fb3f18109e42c0302d447c261770bcb0a31cf1ad1be73cd01b12cc877bb`，calibration `560a8821c073cd76bf31a9e19c5a5cb334b6336355f96039c002ba085fcd0d6e`。
- `tests/test_w3_lab_qc_fixture_oracle_v1.py`：`py_compile` 通过，16/16 unittest 通过。
- 证据范围严格是离线状态契约、actor-role-scoped MA-ID evaluator 和 synthetic Undo exposure trace tests；**不解析 FODS，不验证 LO，不建立 Guest，不证明用户态 Undo 语义或 Actor 行为**。
- 两个 text-only Sol critique launcher attempt 均 fail-closed，因为调用进程环境中没有可用 `SWCUB_SOL_API_KEY`；artifact `/mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-w3-lab-qc-20261106-01/report.json` 与 `...-02/report.json` 记录 `model_called=false`。没有 HTTP request/模型费用，也没有凭证进入脚本日志或 artifacts；它们不是 Sol 的设计结论。审查脚本在 `scripts/review_w3_design_sol_v1.py`，py_compile 通过。
- 本轮未启动 Guest、Docker、模型 Actor；未改 Case 2/3/4 或 GUI-only 历史，未删除资源、未 commit/push。

下一门仍是：先通过可用的安全凭证注入路径取得一次 Sol 文本设计审查；再独立审计 MA-ID artifact scoring 与任务自然度。只有自然度得到支持后，才值得一次低成本 Calc Guest Undo-stack semantic control；不先建完整 UI/正式 runner。


## 2026-11-06 — W3 GPT-6-Sol 设计审查完成；暂停 W3 Guest 路径

- 凭证本身并非缺失：之前阻塞是 `SWCUB_SOL_API_KEY` 未进入 Python runner 进程。此次在 HealthCare SSH 交互 TTY 用 `read -s` 隐藏输入并 export 到当次进程；密钥未写文件、命令行参数或报告。成功使用 GPT-6-Sol，经 `https://docode.cc/v1/responses`，HTTP 200，valid=true，model_called=true，402.399 秒。未用 Qwen。
- 成功审查 artifact：`/mnt/raid1/mjh/codesk-next-candidates-20261103/reviews/sol-design-review-w3-lab-qc-20261106-04/report.json`。报告不含 key。注意请求 max_output_tokens=3500 但 response usage 报告 output_tokens=10264（total 13543）；没有再发第二个模型请求，之后先审计 endpoint 对预算字段的解释。
- 一个较早、失败的 shell 引号版本留下 `.../sol-design-review-w3-lab-qc-20261106-03/report.json`，其中 `model_called=false`/missing credential；它仅为 no-call，不作为审查意见。
- Sol 判定 revise / high confidence：QC 工作流有价值且宏观不同，但机制只是 U-01 共享 Undo 复刻。更自然的正确做法是直接编辑，不应在 prompt 中指定 Ctrl+Z；若中性 MA-ID 不自然产生 Undo，不跑 shared arms。
- 另一个 blocker 是 MA-ID role artifacts 不等于 B 复核 A 的真实工作：独立副本下 B 看不到 A 的处置，而 Shared live workbook 可见，构成任务语义不等价。需先定 role-scoped 单独产出/聚合，或每臂统一提供相同只读快照。再者，Reviewer 多格编辑可能有多个 Undo units；save/live-state、document identity、focus 和 lock scope 均未验证。
- 因此更新 `W3_LAB_QC_BATCH_RELEASE_CANDIDATE_20261106.md`：W3 不实现 Guest，不跑模型，除非整个机制/角色语义重构；不强行制造 Undo 暴露。W3 不是通过 case，也不计入 13-case 达标集。离线 fixture/oracle 16/16 测试仍仅支持数据契约，不证明 Calc/模型语义。
- 本次仅增加审查结论文档；未改旧实验配置、未启动 Guest/容器/Actor、未清理资源、未 commit/push。

## 2026-11-06 — GPT-6-Sol output-budget audit (not a case/model-arm result)

**Finding: this was not an API-key-missing failure.** A previous hidden `read -s` injection successfully called GPT-6-Sol through the third-party OpenAI-compatible `docode.cc/v1` endpoint (HTTP 200, returned model `gpt-6-sol`, `response_status=completed`, 402.399 s). I rechecked the original request builder: it explicitly sends `reasoning.effort=medium` and `max_output_tokens=3500`. The saved response reports `output_tokens=10,264` (6,732 reasoning + 3,532 visible message tokens), `total_tokens=13,543`, with no incomplete status. Thus the returned output usage is 2.93x the requested cap; even the visible-message attribution alone is 32 tokens over it. This is a real and material **endpoint/proxy budget-semantics anomaly**, not a missing credential and not an interrupted response. The safe metadata is in `.../reviews/sol-design-review-w3-lab-qc-20261106-04/report.json`; it contains no credential.

Official OpenAI Responses API documentation defines `max_output_tokens` as an upper bound that includes visible output and reasoning: https://developers.openai.com/api/reference/resources/responses/methods/create . That documents OpenAI's endpoint contract, **not** the behavior of `docode.cc`; compatibility of MCP/tool-call protocol does not prove budget enforcement parity.

I attempted one bounded, low-effort conformance probe against the same proxy (`max_output_tokens=64`, streaming, prompt requested 600 repetitions) using `scripts/audit_sol_output_cap_v1.py`. It did not produce a terminal Responses event within about 11 minutes. The client remained blocked reading the stream; an intermediate TCP diagnostic showed ~5.57 MB received by the Python-to-local-proxy socket (transport bytes, not decoded output tokens). I manually interrupted it. The artifact `.../reviews/sol-output-cap-probe-20261106-01/report.json` records this as **inconclusive**, with no usage or token-cap verdict; the partial stream was not saved. The probe did not alter any Guest or experiment state. Credential was unset immediately after cancellation and is not in the repo or artifacts.

**Operational conclusion:** treat the 10,264-token completed response as evidence that we cannot rely on the `docode.cc` `max_output_tokens` request field as a hard total-output guard. Do not relabel it as proven proxy nonconformance from a single successful usage record alone, but do not use the requested cap as a safety guarantee either. Any later Sol call should have an independent client-side wall-clock stop, partial-result/error persistence, and explicit requested-vs-returned usage audit; until a short, bounded response confirms semantics, avoid expensive/open-ended critique calls and do not run formal model arms on an assumed 3,500-token budget. No second endpoint call was made. No Guest/model Actor or formal experiment was started for this audit.

For any later intentional calibration, I added (but did **not** execute) `scripts/audit_sol_output_cap_v2.py`: a separate metadata-only probe with a 180-second SIGALRM hard wall deadline, idle timeout, partial-event counters, automatic comparison of final reported output usage against the requested cap, and no full response/key persistence. `py_compile` passes. It targets a new `...-02` artifact and cannot overwrite the interrupted probe. This is tooling readiness only, not a second model result.

## 2026-11-06 — Follow-up confirms output-cap mismatch on both supplied Sol hosts

Continued the bounded check using a hidden credential injection and the user-provided alternate `api.haogpt.net` base URL. The v2 minimal prompt (cap 16, ask for one word) completed in 4.802 s at 5 output tokens; this is only a liveness check, not a meaningful cap challenge. A 600-repetition challenge on that host did not receive HTTP headers before the 20 s socket idle timeout, so it is inconclusive. A more natural three-sentence answer prompt with the same cap 16 then returned HTTP 200/completed in 4.612 s but reported **46 output tokens**, 0 reasoning and 232 visible characters. Thus the two provided hosts have now both yielded completed responses exceeding their requested caps (`docode.cc`: cap 3500 vs 10264; `api.haogpt.net`: cap 16 vs 46). We still cannot infer actual billing from response usage metadata.

Full chronology, limitations, paths and safe-use recommendation are in `SOL_OUTPUT_BUDGET_AUDIT_20261106.md`; probe reports 01–04 are preserved in RAID1 reviews. I did not make another endpoint call. The API key was unset after the probes; no Guest, Actor, container or formal task arm ran. The cap mismatch is now a confirmed operational caveat for the user-supplied proxies, not a missing-key blocker.

## 2026-11-06 — Read-only PBR control artifact audit while continuing candidate triage

No new Guest was launched. Re-read existing PBR scripted control reports 01–03 and the saved `after_replace_all.xml`. Runs 01/02 did preserve the `All sheets` option through B's Find All + close/reopen, but both final saved-state reports still contain `SUP-OLD-1001` on both `Current Pricebook` and `Quote Archive`; therefore their UI-scope positive is **not** a passing save-state positive. Run 03 likewise preserved scope but failed with `NameError: pyautogui is not defined` before final evaluation. In 01/02 the post-Replace-All accessibility snapshot still shows a `Search Results` dialog (`2 results found`) and a separate accessible `Close` button, while the old script then dismisses by Enter and uses two unverified fixed-coordinate clicks before Ctrl+S. This is a likely control-automation flaw, not evidence that the product mechanism passed. However, PBR is still a FIND-1 mechanism variant and has consumed ~37.6 minutes in controls; no additional Guest run is justified until its candidate value is re-confirmed and the close/save sequence is corrected with observable state checks. The existing result files and overlays remain unchanged.

## 2026-11-06 — GPT-6-Sol 下一批工作流候选构思与静态审计

- 一次 GPT-6-Sol 流式文本构思调用成功：`docode.cc/v1`，returned `gpt-6-sol`，HTTP 200/completed，483 output tokens，32.267 s。首选 `api.haogpt.net/v1` 的前次请求 read-timeout，没有文本，保留失败 artifact；没有改用 Qwen。密钥通过隐藏输入，未记录，调用后 unset。
- Sol 提议 AP remittance matching、refund reconciliation、room capacity reconciliation。审计后：AP-1 排在首位，进入**静态详细设计**；Refund 作为后备（与 Case 2/W4 宏观重合较大）；Room 容量当前不做（与 W2/排程太近）。
- 新文档 `NEXT_WORKFLOW_BRAINSTORM_TRIAGE_20261106.md` 和 `AP1_REMITTANCE_MATCHING_CANDIDATE_20261106.md` 记录依据、重合与停止门。
- AP-1 仍只有因果假设，不是通过/达标案例。设计关键阻塞不是 API/token cap，而是证明在同任务语义/独立数据副本下，B 的正常应付状态更新能令 A 的业务事实变陈旧，并区分业务状态错误与 focus/selection/clipboard/CWD；且不能为了制造 FAIL 抑制 Agent 的重观察与正常恢复。
- 本轮只做了 API 文本构思与文件/历史文档审计；没有启动 Guest、LLM task arm、GPU worker或修改旧 Case 2/3/4。

## 2026-11-06 — 后续候选筛选：PAY-1 工时更正进入静态审计

- GPT-6-Sol 再给了三个新宏流程候选；后续定向 review 对 Payroll Timesheet Correction 判为 **revise**（不是模型实验结果）。已排除 release-gate 候选的近似软件发布 workflow，AP 保留备选；PAY-1 当前优先因为工资核算与已审计工作流的宏观领域区分更清楚。
- 新卡 `PAY1_PAYROLL_TIMESHEET_CANDIDATE_20261106.md` 定义 8.0 小时→6.0 小时监督更正、$32/h 与 workspace-local 统一 oracle。它要求 MA-ID 每个 clone 各自评分，Shared 使用同一规则检查共享 ledger；不按 arm 写死金额。恢复成功计 PASS；共享+锁不预设失败。
- GPT-6-Sol 指出的确切设计风险已保留：若以单一全局权威账本跨 MA-ID/Shared 评分会破坏隔离条件；若普通提交会原子检查最新审批状态则不应出现 stale fail；固定 pending-submit interleaving 只能称压力测试。
- 此轮未跑 Guest、未运行 LLM task、未改旧 Case 2/3/4；Sol 的两次新构思与 PAY-1 critique 均为文本设计调用，凭证隐藏输入并在调用后 unset。当前关键工作已从“多造想法”转为验证 PAY-1 的 task/oracle/topology 是否完全同义，再考虑离线 control。

## 2026-11-06 PAY-1 oracle hardening 与 runner audit

- PAY-1 纯离线 oracle 发现并修正一个契约漏洞：卡片承诺付款后正常 void/reissue 可恢复 PASS，旧 oracle 却只接受恰好一条总付款记录。现按“唯一 active payment + 最多一条有审计的 voided 历史记录”评分；Shared workspace 中 B 的 supervisor correction 仍按 B-owned audit 严格评分，不会被 A 的正常付款历史误拒。
- python3 -m unittest -v tests.test_pay1_timesheet_fixture_v1 **9/9 PASS**，py_compile PASS。明确覆盖 MA-ID 同 fixture clone 的 A/B task success、Shared stale payment failure、重读后修正 PASS、void/reissue PASS、错误身份/来源/金额、无审计 void、duplicate active line 等负例。该项只证实 Python state contract，不是应用、Guest 或模型实验。
- 只读核对 W4 runner：可复用同一 CodexHarness/Hybrid v2 actor 调用和 Guest GUI/受限 Guest CLI/协作 MCP、MA-ID/Shared Guest 拓扑、resource ledger、每动作锁及完整 teardown；W4 当前 MCP gate 实证拦截的是 pending Ctrl+V，尚不能视作 PAY-1 的“提交/导出” click gate 已验证。PAY-1 必须单独验证 gate 命中与释放证据，若目标按钮/业务事务不能被不混淆地同步，不做强制 pending-call intervention。
- 当前资源只读快照：根盘 99%，约 33 GB 可用；/mnt/raid1 约 1.4 TB 可用；MemAvailable 209 GiB；swap 2/2 GiB 已用；Docker active list 空、Guest image 和 runtime 本地存在。新一轮没有启动 Guest/容器/模型任务或删资源；继续先完成 PAY-1 的自然业务语义与提交 gate 可行性审计，避免为了得到失败而造 UI 障碍。
- 文件均未 commit/push；Case 2/3/4 与既有正式配置未动。当前有效结论：PAY-1 oracle contract 可测，但候选仍未资格化；实际缺口是静态付款快照是否为正常工作流、MA-ID/Shared 副本的任务语义是否公平，以及生产 action gate 是否能无混淆地对齐待提交动作。


- Action-gate 只读审计进一步收敛：desktop_tools.py 的 scheduled gate 是通用 Actor/tool/scalar-argument 字符串匹配，在 per-action lock 之前阻塞；click 可以按 x 或 y 触发，且 pending/dispatched 记录完整动作和 release。不过 W4 证据只验证 Ctrl+V；PAY-1 仍需低成本 scripted production-MCP control 验证其具体提交按钮坐标唯一且是目标业务事件，然后才可正式用该 gate。


- 新增一个未关闭的构念效度门：MA-ID 是同初始 fixture 的 actor-private workspace clones，Shared 是一个共同 workspace；因此这不是“跨臂共享同一个 enterprise database，只改变屏幕”的对照。若验收定义要求后者，PAY-1 clone 拓扑不合格。需在实现/实验前锁定 actor/workspace-level success 的解释，不可切换成跨臂 scorer 分支以追求目标组合。



## PAY-1 2026-11-06 completion-order 实验结果

- 第一轮 no-model Guest smoke、生产 Desktop MCP action-gate smoke、离线 controls 均已完成。Guest/app 只连接 loopback，不使用 payroll/bank 外部服务；所有模型运行用 HealthCare 本地 pinned OSWorld runtime，reset 和 container teardown 均留存审计。
- 在 forced pre-submit interleaving 中，GPT-6-Sol 从 B 的后续更新中发现 6.0 小时，使用正常的 void/reissue 修复付款；业务结局是 PASS。该轮 B/A 消息顺序不符合协议，因此无效、不计为 Shared 结果。这确认不能靠取消可见刷新或恢复路径强造 FAIL。
- 为测试更实际的完成顺序而修订 schedule：A 完整完成 8.0h/$256 付款任务并发送 handoff，结束后 B 才从同一 Shared Guest 读取该 handoff、根据签字文件把时卡改成 6.0h。MA-ID baseline 不变，仍为两个相同 fixture 的隔离 Guest clone。
- MA-ID baseline pay1-sol-ma_id-20261106-180233-b0578d：有效 PASS，880.0s。
- Completion-order MA-SD pay1-sol-completion-order-ma_sd-20261106-184148-ca9cde：有效 FAIL，329.2s；A 在 B 开始前先通过，B 更正后亦通过，但最终共同 workspace 中 active payment 仍为 8.0h/$256、获批时卡已为 6.0h，统一 A oracle 失败；协作、reset、生命周期通过。
- Completion-order MA-SD+Lock pay1-sol-completion-order-ma_sd_lock-20261106-184751-88fc4b：有效 FAIL，552.43s；同样的 A-before-B 业务状态与结果，生产 action lock 已启用；协议、reset、生命周期通过。
- 三个有效臂 task version、fixture SHA、prompt hashes、GPT-6-Sol、GUI/Guest CLI/Collaboration MCP 权限、每 Actor 预算都匹配。PAY-1 fixture/app 14/14 unittest 通过。
- 方法边界：成功 FAIL 来自**晚到业务更正使之前完成的付款快照过时**，不是并发焦点/键鼠误路由。本次完成顺序下 lock 没有并发竞争者；因此可以说明逐动作锁不保证跨任务事务新鲜度，不能声称该实验测出了 GUI 并发锁竞争。
- 详情见 PAY1_HYBRID_EXPERIMENT_STATUS_20261106.md。没有做重复、没有运行大规模实验；Case 2/3/4 冻结内容未动。新代码/文档尚未 commit/push。
