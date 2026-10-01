# CoDesk Workflow Implementation V1

Status: bounded implementation and validation, 2026-10-01. This report covers the **workflow** subtask. The A6000 repository is canonical. The fixed Task Factory hierarchy is family → workflow template → fixed instance → run; this change adds two fixed prototype templates and generates no seed series. It does not modify existing task/evaluator semantics or historical artifacts.
> Current status: historical screening plan; C-02 and F-02 were implemented and bounded-validated after this snapshot. See WORKFLOW_SUITE_V1.md. Keep the original rationale below as history.

## Decision table

| Matrix item | Decision | Reason and evidence ceiling |
|---|---|---|
| F-01 Writer + Calc single-cell focus anchor | Reuse | Existing `scripts/run_writer_calc_v1.py`, `swcub/actors.py` and `GuestLibreOfficeBindingEvaluator` remain unchanged. Historical Qwen focus evidence is in `MECHANISM_VALIDATION_ROUND1.md`; this round did not rerun it. |
| F-02 Browser form + Writer comment | Defer | Browser form backend can be made exact, but the existing Writer setup/evaluator has no reliable comment anchor extraction or deterministic GUI comment path. A text substitution would change the workflow into F-01. Gate: confirm Writer comment creation through GUI and exact ODF annotation anchor/text oracle before registration. |
| F-03 Two Writer windows, comment + heading | Defer | It requires two distinct Writer document windows with stable path/window attribution and the same comment oracle. Two plain paragraph replacements would be another F-01 input-routing variant; this proposal remains uncounted until separate-document identity is observed in Guest. |
| F-04 Calc block + Writer | **Implemented fixed prototype** | Calc actor enters a 2×2 value block in B2:C3 via four GUI cell visits; Writer actor replaces its paragraph. Exact full-sheet oracle detects incomplete block, spill to guarded neighbors and Writer contamination. Offline tests and scripted Guest Solo A/B, MA-ID, MA-SD negative, and refocus recovery passed for this fixed template. No new model trial. |
| C-01 Writer/Calc plain transfer anchor | Reuse | Existing `scripts/run_clipboard_v1_round1.py`, `swcub/tasks/clipboard_v1.py` and observer remain unchanged. Historical scripted Guest evidence is in `MECHANISM_VALIDATION_ROUND1.md`; no Qwen clipboard evidence is claimed. |
| C-03 Calc rectangle transfer + Writer | **Implemented fixed prototype (v0.1.1)** | Calc actor selects A1:B2 with GUI keys, copies it and pastes at A4:B5; Writer actor independently copies a paragraph. Exact full-sheet oracle rejects a flattened, shifted or overwritten rectangle and checks guard cells. Offline tests and scripted Guest Solo A/B, MA-ID, MA-SD negative, and recopy recovery passed for v0.1.1. Guest evidence and one setup-invalid MA-ID attempt are recorded below. |
| C-05 Writer cut/move transaction | Defer | A complete oracle needs both final uniqueness and event evidence for transient source removal, clipboard overwrite, and recovery after possible data loss. Existing observer identifies clipboard changes but the current Writer task does not observe a stable cut/undo transaction. A naive final-text oracle would conflate this with C-01. Gate: demonstrate a deterministic two-phase GUI cut/paste plus independent B goal and source-to-destination recovery. |

The original workflow implementation subtask added F-04 and C-03 code; a later addendum below records A-01 and M-01. The original Solo A smoke alone did not establish joint feasibility. The closure runs below now establish scripted paired feasibility, interference and recovery for these fixed instances. They do not establish a model failure rate.

## Fixed prototype contracts

### F-04: `focus_calc_block_writer_v1`

- Initial Writer: `Review summary: Draft`; goal B: `Review summary: Final`.
- Initial Calc: four rows, B2:C3 blank, non-target guards D2=`Keep-N`, D3=`Keep-S`, B4=`Safe`. Goal A: B2=`11`, C2=`12`, B3=`21`, C3=`22`; all other cells unchanged.
- A first observes Calc, B legitimately switches to Writer and completes its edit, then A resumes. In MA-SD the no-recovery scripted control lets A act from its earlier observation; recovery control explicitly switches back and reobserves. The coordinator never routes a correct action to the wrong app by fiat.
- Operation graph differs from F-01's single B2 edit: four separate cell visits and a rectangular integrity oracle. The evaluator rejects partial fill and neighbor corruption; if future model traces show only generic wrong-window entry, this should remain a Focus workflow, not a new family.
- Solo: A or B on one freshly seeded Guest. MA-ID: two Guests each seeded from the same fixture digest, each with its assigned app. MA-SD: one Guest with Writer and Calc; the same A→B→A turn schedule. Goals do not require cross-Actor persistent file visibility, so independent local fixtures are task-relevant state equivalent in MA-ID.

### C-03: `clipboard_calc_rectangle_v1`

- Initial Calc A1:B2 is `[Q1,Q2;17,29]`; A4:B5 blank. C2=`Keep-2`, C4=`Keep-4`, C5=`Keep-5` and A3=`Guard-R3` are integrity sentinels. Goal A: A4:B5 exactly equals A1:B2, source and all guards unchanged.
- Initial Writer has source `NOTE-571` and an empty destination paragraph. Goal B: destination exactly `NOTE-571`, source unchanged.
- A copies A1:B2 through real GUI `Ctrl+C`; B legitimately copies/pastes its own paragraph; A activates Calc and pastes through real GUI `Ctrl+V`. The recovery control allows A to recopy the original range before pasting. The hidden clipboard observer is installed before any setup ActorContext action and receives no actor-facing access. Version 0.1.1 represents A4:B5 as genuinely empty XML cells; the v0.1.0 fixture used empty string-valued cells and triggered a native overwrite warning.
- The oracle checks full Flat ODF text and cell matrices. It detects scalar replacement, flattening, shift, missing cells, guard mutation and cross-app text contamination. Event evidence remains separate from the final outcome; a failed goal alone is not proof of clipboard overwrite.
- Solo/MA-ID/MA-SD use the same condition topology as F-04. MA-ID has independent clipboard sessions and equivalent initial local files. MA-SD shares a desktop and clipboard. No cross-Actor persistent file visibility is required.

## Code, execution and provenance

- `swcub/tasks/workflows_v1.py`: immutable fixed fixture bytes, actor goals, condition contract, deterministic SHA-256, exact private Flat ODF oracle. Static manifest `evidence_status=offline_oracle_only` describes **template contract validation**; each run report separately records `evidence_level=scripted_real_guest_episode` when Guest execution occurs.
- `swcub/tasks/workflow_actors_v1.py`: scripted GUI-only actor steps; no evaluator or Guest CLI capability. An offline action recorder checks control sequences, while Guest runs use the existing `ActorContext` and OSWorld adapter.
- `scripts/run_workflows_v1.py`: bounded single-episode entry point using existing `base.make_desktop`, ownership ledger, application readiness, hidden observer for C-03, per-Actor event log, final ODF, screenshots, reset Guest and run-local provenance. It creates a new artifact directory and refuses overwrite. The runner classifies setup/observer failures separately from execution/evaluator errors.
- `tests/test_workflows_v1.py`: six offline tests for fixture reproducibility, Solo A/B and joint oracles, non-target mutation, rectangular corruption, and actual GUI copy/paste action intent. Offline constructed final files are oracle tests, **not** evidence that a Guest actor reached those states. A separate targeted synthetic event check confirmed three attribution cases: independently bracketed A→B clipboard overwrite, unowned payload change labeled `unknown_payload_change`, and unchanged A payload labeled `no_overwrite_at_paste`. This check was offline and provides no additional Guest mechanism evidence.

Run from A6000 with the pinned environment:

```bash
cd /home1/mjh/Projects/CoDesk-V0-A6000/CoDesk
source scripts/a6000_env.sh
$CODESK_PYTHON -m pytest -q tests/test_workflows_v1.py
$CODESK_PYTHON scripts/run_workflows_v1.py --template F-04 --condition solo_a \
  --run-id <unique-run-id> --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1
$CODESK_PYTHON scripts/run_workflows_v1.py --template C-03 --condition solo_a \
  --run-id <different-unique-run-id> --artifact-parent /home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1
```

Supported conditions are `solo_a`, `solo_b`, `ma_id`, `ma_sd`. `--recovery` activates refocus for F-04 or recopy for C-03. Each run should be interpreted from its own `report.json`, `events.jsonl`, `provenance.json`, final ODF files, screenshots and append-only `resource-events.jsonl`. The run does not invoke Qwen. In the current runner, `condition_success` means all active goals pass, while `joint_success` is populated only for two-Actor conditions (`null` for Solo). The two archived Solo smoke reports were emitted before this field distinction and contain `joint_success=true` meaning only that the single active Actor passed. Do not count those values as dual-Actor success. Old reports were not edited.

## Verification status

| Check | F-04 | C-03 |
|---|---|---|
| Deterministic fixture and SHA-256 | OFFLINE PASS | OFFLINE PASS |
| Solo A/B and joint **oracle** positive/negative controls | OFFLINE PASS | OFFLINE PASS |
| Scripted GUI action sequence inspection | OFFLINE PASS | OFFLINE PASS |
| Solo A real Guest goal/readiness/reset/provenance | PASS: `workflow-f04-soloa-20261001-01` | v0.1.0 FAIL: `workflow-c03-soloa-20261001-01`; v0.1.1 PASS: `workflow-c03-soloa-20261001-02` |
| Solo B real Guest | PASS: `workflow-f04-solob-20261001-r01` | PASS: `workflow-c03-solob-20261001-r01` |
| MA-ID real Guest | PASS: `workflow-f04-maid-20261001-r01` | r01 setup-invalid; PASS: `workflow-c03-maid-20261001-r02` |
| MA-SD real Guest interference/recovery | Naive joint FAIL with 4 wrong-app content actions; refocus joint PASS | Naive joint FAIL with clipboard overwrite; recopy joint PASS |
| Qwen actor | UNVERIFIED | UNVERIFIED |

C-03 v0.1.0 failed artifact: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/workflow-c03-soloa-20261001-01`. The run completed with `actor_a=false`, reset true, 26 healthy observer samples and two destroyed run-owned containers. Its screenshot shows a native Calc overwrite confirmation because the destination cells were encoded as empty string-valued cells. The scripted Actor did not confirm the modal and saved no target changes. This is a **fixture defect / scripted task failure**, not evidence of clipboard interference. The run remains unmodified. C-03 v0.1.1 alters only the initial blank-cell XML representation and gets a new fixture digest; the target goal and exact evaluator remain the same. Run `workflow-c03-soloa-20261001-02` is the one bounded retry. It passed: saved Calc A4:B5 matches the source rectangle exactly, Writer and guards remain initial, `status=completed`, Solo A goal=true, `reset_success=true`, 26 healthy observer samples, 50 events, 5 screenshots, wall time 322.898 s, and both run-owned container IDs have matching destroyed ledger rows. Observer trace has Calc copy digest equal to the payload at Calc paste, no wrong-app content action, and no overwrite at paste. This is evidence of a successful Solo transfer; it does not exercise clipboard contention between Actors.

F-04 Solo A artifact: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/workflow-f04-soloa-20261001-01`. The true saved Calc is exactly B2=`11`, C2=`12`, B3=`21`, C3=`22`; Writer stays at its initial value. `report.json` records `status=completed`, actor A success, legacy `joint_success=true` for its **single active actor**, `reset_success=true`, 31 event rows, 5 screenshots, wall time 351.809 s, and two current-run container IDs with matching destroyed ledger rows. This is one Solo A smoke only. Its initial run report predates the explicit run-level evidence field; the static manifest's offline status is a template contract label, not a denial of the archived Guest artifact. Historical artifact files were not edited.

## Next promotion gate

1. The fixed F-04 and C-03 instances have passed the scripted paired gate. Keep their evidence label SCRIPTED VALIDATED; a model result would need fresh Solo controls and independent actors.
2. Audit C-03 against C-01 for distinct matrix/shape oracle before accepting additional instances. Keep F-02/F-03/C-05 deferred until their stated oracles and GUI paths are tested.

## Scripted closure addendum (2026-10-01)

These runs use the same fixed goals, fixture digest per template, A→B→A schedule and private evaluator. All completed runs saved screenshots, final ODF, event log and provenance, passed reset, and had destruction records for all run-owned containers. No Qwen actor participated.

| Template | Condition / run | Actor A | Actor B | Exposure, observed interference, recovery |
|---|---|---:|---:|---|
| F-04 | Solo B `workflow-f04-solob-20261001-r01` | n/a | PASS | Writer final exact; Calc initial. |
| F-04 | MA-ID `workflow-f04-maid-20261001-r01` | PASS | PASS | Equal fixture hashes, independent desktops, joint PASS. |
| F-04 | MA-SD `workflow-f04-masd-20261001-r01` | FAIL | FAIL | Scheduled focus exposure; 4 A content actions reached foreground Writer. Calc stayed initial; Writer gained `11/21/12/22` contamination. Joint FAIL. |
| F-04 | MA-SD recovery `workflow-f04-masd-recovery-20261001-r01` | PASS | PASS | A switched back to Calc and reobserved; 0 wrong-app content actions; joint PASS. |
| C-03 | Solo B `workflow-c03-solob-20261001-r01` | n/a | PASS | Writer source/destination exact; Calc initial; observer 18 samples/0 failures. |
| C-03 | MA-ID `workflow-c03-maid-20261001-r02` | PASS | PASS | Equal fixture hashes, separate clipboards, joint PASS; observer 26+18 samples/0 failures. |
| C-03 | MA-SD `workflow-c03-masd-20261001-r01` | FAIL | PASS | B copy changed payload digest between A copy and A paste; A pasted `NOTE-571` into Calc A4. Correct target app, 0 wrong-app content actions; joint FAIL. |
| C-03 | MA-SD recovery `workflow-c03-masd-recovery-20261001-r01` | PASS | PASS | A recopied source before paste; payload matched original at paste; joint PASS, observer 54 samples/0 failures. |

`workflow-c03-maid-20261001-r01` is a retained **invalid setup attempt**: Calc never opened (desktop screenshot, last active title `@!0,0;BDHF`), accessibility requests transiently disconnected, and readiness timed out at 120 s before actor action. Its run-owned container was destroyed with matching ledger. The unchanged r02 retry passed; r01 is excluded from agent/task success statistics. This failure does not support clipboard or model-interference attribution.

F-04 and C-03 are now **SCRIPTED VALIDATED fixed workflows**. The `VALIDATED` label is limited to the scripted Guest protocol on these fixed instances and does not imply Qwen success or statistical stability. Scheduled exposure, measured mechanism event, final outcome and positive recovery are reported separately in each run.

## A-01 complete workflow and M-01 de-duplication addendum (2026-10-01)

A-01 `chromium_two_tab_context_v1` is a different Browser workflow from the Writer/Calc top-level focus tasks. A and B submit exact independent values in two tabs of the **same Chromium top-level window**. `swcub/tasks/browser_context_v1.py` holds the fixed manifest, two actor goals, scripted action graph and private condition oracle; `scripts/run_browser_context_v1.py` reuses the current Guest adapter, ActorContext, event log, reset, provenance and ownership ledger. The initial and expected values are deterministic. Solo and MA-ID also check that the unassigned tab has empty content and revision zero. The shared oracle requires both exact values and no extra B revision. Window ID and active-tab snapshots are private to the evaluator. `tests/test_browser_context_workflow_v1.py` has five offline oracle/action controls.

Formal rc4 artifacts are under `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/browser-context-v1/<run-id>/`. The one-shot gated command is `bash scripts/run_a01_rc4_validation.sh` on a clean A6000 Guest pool; its fixed run IDs are already used, so reproductions should call `scripts/run_browser_context_v1.py` with new unique IDs instead. The gate runs Solo A/B, MA-ID, naive MA-SD and explicit-recovery MA-SD serially and stops when a prerequisite fails. Conditions differ in Guest binding and whether recovery is explicitly enabled. In the naive conditions, A's five GUI actions, B's five GUI actions and A→B→A turn order are identical; there is no forced misrouting. The negative MA-SD action is A's own pending click after B legitimately changes the tab.

| Workflow | Fixed version | Solo A/B | MA-ID | MA-SD naive | MA-SD recovery | Evidence ceiling |
|---|---|---|---|---|---|---|
| F-04 Calc block + Writer | 0.1.0 | PASS/PASS | joint PASS | A/B FAIL, wrong-app content actions | joint PASS | SCRIPTED VALIDATED |
| C-03 Calc rectangle + Writer | 0.1.1 | PASS/PASS | joint PASS after one setup-invalid attempt | A FAIL/B PASS, clipboard overwrite at correct target app | joint PASS | SCRIPTED VALIDATED |
| A-01 Browser two-tab context | 1.0.0-rc4 | PASS/PASS | joint PASS | A FAIL/B PASS, B tab revision 2 with one constant X11 window ID | joint PASS after tab reacquisition | SCRIPTED VALIDATED fixed instance; no model evidence |
| M-01 two LibreOffice Save dialogs | prototype probe | not scored | not run | diagnostic only | not run | BLOCKED separate-family attribution |

A-01 formal run IDs: `a01-soloa-20261001-r04`, `a01-solob-20261001-r03`, `a01-maid-20261001-r02`, `a01-masd-20261001-r01`, and `a01-masd-recovery-20261001-r01`. Every run passed reset and ownership/provenance checks. The negative trace has X11 ID `12582916` for A first turn, B turn and A resume; tab A→B; A final goal empty; B goal correct but revision 2. The explicit recovery returns to tab A and achieves both goals with revision 1 each. These are **one run per control**, not a statistical success rate. Earlier A-01 rc1/rc2 setup-script failures and rc3 policy-confounded MA-ID are retained and excluded from the rc4 causal contrast; details are in `MECHANISM_VALIDATION_ROUND1.md`. A raw rc4 recovery field labeled `autonomous_recovery=true` means scripted recovery only; the runner's later metadata correction avoids that label in future outputs.

M-01 `scripts/probe_modal_m01_boundary.py` is deliberately a diagnostic, not a new scored family. Run `m01-modal-boundary-20261001-r01` saved real Writer/Calc readiness, two dialog screenshots and X11 parent/modal properties, B's switch and Save As attempt, Escape attempts, reset, provenance and resource ledger. B could activate Calc and open a separate native chooser while Writer's remained open. The later Escape anomaly is unassigned because keyboard focus was not separately measured and no exact dual output was scored. Keep M-01 BLOCKED as an independent mechanism, and do not expand M-02 from this trace.

**Expansion gate:** F-04, C-03 and A-01 each justify implementing a small number of actually different GUI operation graphs. Continue to require Solo feasibility, MA-ID joint feasibility, one measured MA-SD exposure/interference control, explicit recovery and a private oracle before generating fixed instances. Do not mass-generate seeds or claim scripted controls predict Qwen outcomes.
