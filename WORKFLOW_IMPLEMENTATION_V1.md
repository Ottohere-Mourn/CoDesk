# CoDesk Workflow Implementation V1

Status: bounded implementation and validation, 2026-10-01. This report covers the **workflow** subtask. The A6000 repository is canonical. The fixed Task Factory hierarchy is family → workflow template → fixed instance → run; this change adds two fixed prototype templates and generates no seed series. It does not modify existing task/evaluator semantics or historical artifacts.

## Decision table

| Matrix item | Decision | Reason and evidence ceiling |
|---|---|---|
| F-01 Writer + Calc single-cell focus anchor | Reuse | Existing `scripts/run_writer_calc_v1.py`, `swcub/actors.py` and `GuestLibreOfficeBindingEvaluator` remain unchanged. Historical Qwen focus evidence is in `MECHANISM_VALIDATION_ROUND1.md`; this round did not rerun it. |
| F-02 Browser form + Writer comment | Defer | Browser form backend can be made exact, but the existing Writer setup/evaluator has no reliable comment anchor extraction or deterministic GUI comment path. A text substitution would change the workflow into F-01. Gate: confirm Writer comment creation through GUI and exact ODF annotation anchor/text oracle before registration. |
| F-03 Two Writer windows, comment + heading | Defer | It requires two distinct Writer document windows with stable path/window attribution and the same comment oracle. Two plain paragraph replacements would be another F-01 input-routing variant; this proposal remains uncounted until separate-document identity is observed in Guest. |
| F-04 Calc block + Writer | **Implemented fixed prototype** | Calc actor enters a 2×2 value block in B2:C3 via four GUI cell visits; Writer actor replaces its paragraph. Exact full-sheet oracle detects incomplete block, spill to guarded neighbors and Writer contamination. Offline tests passed; one scripted Guest Solo A smoke passed. Solo B, MA-ID, MA-SD remain unverified. |
| C-01 Writer/Calc plain transfer anchor | Reuse | Existing `scripts/run_clipboard_v1_round1.py`, `swcub/tasks/clipboard_v1.py` and observer remain unchanged. Historical scripted Guest evidence is in `MECHANISM_VALIDATION_ROUND1.md`; no Qwen clipboard evidence is claimed. |
| C-03 Calc rectangle transfer + Writer | **Implemented fixed prototype (v0.1.1)** | Calc actor selects A1:B2 with GUI keys, copies it and pastes at A4:B5; Writer actor independently copies a paragraph. Exact full-sheet oracle rejects a flattened, shifted or overwritten rectangle and checks guard cells. Offline tests passed. Guest evidence listed below. |
| C-05 Writer cut/move transaction | Defer | A complete oracle needs both final uniqueness and event evidence for transient source removal, clipboard overwrite, and recovery after possible data loss. Existing observer identifies clipboard changes but the current Writer task does not observe a stable cut/undo transaction. A naive final-text oracle would conflate this with C-01. Gate: demonstrate a deterministic two-phase GUI cut/paste plus independent B goal and source-to-destination recovery. |

Only F-04 and C-03 have new code. A single Solo A Guest smoke does **not** establish joint feasibility in real applications, MA-ID/MA-SD control validity or a mechanism failure rate.

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
| Solo B real Guest | UNVERIFIED | UNVERIFIED |
| MA-ID real Guest | UNVERIFIED | UNVERIFIED |
| MA-SD real Guest interference/recovery | UNVERIFIED | UNVERIFIED |
| Qwen actor | UNVERIFIED | UNVERIFIED |

C-03 v0.1.0 failed artifact: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/workflow-c03-soloa-20261001-01`. The run completed with `actor_a=false`, reset true, 26 healthy observer samples and two destroyed run-owned containers. Its screenshot shows a native Calc overwrite confirmation because the destination cells were encoded as empty string-valued cells. The scripted Actor did not confirm the modal and saved no target changes. This is a **fixture defect / scripted task failure**, not evidence of clipboard interference. The run remains unmodified. C-03 v0.1.1 alters only the initial blank-cell XML representation and gets a new fixture digest; the target goal and exact evaluator remain the same. Run `workflow-c03-soloa-20261001-02` is the one bounded retry. It passed: saved Calc A4:B5 matches the source rectangle exactly, Writer and guards remain initial, `status=completed`, Solo A goal=true, `reset_success=true`, 26 healthy observer samples, 50 events, 5 screenshots, wall time 322.898 s, and both run-owned container IDs have matching destroyed ledger rows. Observer trace has Calc copy digest equal to the payload at Calc paste, no wrong-app content action, and no overwrite at paste. This is evidence of a successful Solo transfer; it does not exercise clipboard contention between Actors.

F-04 Solo A artifact: `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/workflow-f04-soloa-20261001-01`. The true saved Calc is exactly B2=`11`, C2=`12`, B3=`21`, C3=`22`; Writer stays at its initial value. `report.json` records `status=completed`, actor A success, legacy `joint_success=true` for its **single active actor**, `reset_success=true`, 31 event rows, 5 screenshots, wall time 351.809 s, and two current-run container IDs with matching destroyed ledger rows. This is one Solo A smoke only. Its initial run report predates the explicit run-level evidence field; the static manifest's offline status is a template contract label, not a denial of the archived Guest artifact. Historical artifact files were not edited.

## Next promotion gate

1. Validate Solo B for both templates. Then one scripted MA-ID and MA-SD per template, checking both goals, reset and provenance. Add recovery control only after naive evidence is cleanly attributed.
2. Promote F-04 or C-03 to an accepted executable workflow only after the joint Guest controls pass. If C-03 reduces to scalar clipboard transfer, merge with C-01. Keep F-02/F-03/C-05 deferred until their stated oracles and GUI paths are tested.
