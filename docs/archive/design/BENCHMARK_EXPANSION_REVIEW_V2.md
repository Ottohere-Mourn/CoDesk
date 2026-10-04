# CoDesk Benchmark Expansion Review V2

Date: 2026-10-01. Canonical repository: A6000. Starting Git HEAD: `93ab566ce68ed114427001f527e7020113d2eac7`. This review merges two independent sub-agent deliverables: `WORKFLOW_IMPLEMENTATION_V1.md` (code and bounded Guest smoke) and `NEW_FAMILY_HUNT_V2.md` (literature and mechanism boundaries). Historical artifacts and evaluators were not modified. No Qwen run, bulk instance generation, migration, or shared-filesystem work occurred.

## 1. Workflow implementation decision

| Candidate | Decision now | Evidence | Next gate |
|---|---|---|---|
| F-01 Writer + Calc anchor | REUSE | Existing Qwen Focus evidence from Round 1; unchanged this round. | Keep as control anchor. |
| F-02 Browser form + Writer comment | DEFER | No deterministic Writer comment anchor/text oracle or GUI creation path yet. Replacing a comment with plain text would duplicate F-01. | Demonstrate real GUI comment creation and exact ODF annotation anchor/text before registration. |
| F-03 two Writer documents | DEFER | Stable path/window identity and comment oracle have not been demonstrated. Two plain replacements would be a Focus variant. | Observe two real Writer window/document identities, then prove exact separate-document oracle. |
| F-04 Calc 2x2 block + Writer | IMPLEMENTED PROTOTYPE | Fixed setup, GUI scripted actors, private full-sheet/text oracle, Solo/MA-ID/MA-SD runner entry. Offline controls passed; one real Guest Solo A passed. | Solo B, MA-ID, MA-SD and recovery remain unverified. |
| C-01 plain transfer anchor | REUSE | Existing scripted Guest Clipboard evidence; unchanged this round. No model evidence. | Keep as clipboard control anchor. |
| C-03 Calc rectangle copy + Writer | IMPLEMENTED PROTOTYPE v0.1.1 | GUI Ctrl+C/Ctrl+V path, true empty-cell fixture, private matrix/text oracle, observer, runner entry. Offline controls and one corrected real Guest Solo A passed. | Solo B, MA-ID, MA-SD and recopy recovery remain unverified. |
| C-05 cut/move | DEFER | No reliable event oracle for transient source removal, overwrite, and recovery; final text alone would overlap C-01. | Prove two-stage GUI operation and source-to-destination recovery oracle. |

The new code is in `swcub/tasks/workflows_v1.py`, `swcub/tasks/workflow_actors_v1.py`, `scripts/run_workflows_v1.py`, and `tests/test_workflows_v1.py`. It reuses the existing OSWorld desktop adapter, ActorContext, application readiness, ownership ledger, event log, reset, and provenance. No prior task evaluator was edited. Fixed instances only; no seed series was generated.

**Evidence boundary:** F-04 and C-03 are runnable prototypes, not accepted benchmark templates. Their Solo B and paired Guest conditions have not run. Offline positive joint-oracle tests establish the oracle contract, not joint GUI reachability.

### Bounded real-Guest evidence

| Run ID | Version | Result and cause | Integrity |
|---|---|---|---|
| `workflow-f04-soloa-20261001-01` | F-04 0.1.0 | Solo A PASS: saved Calc B2:C3 exact four values; Writer initial content preserved. | Reset passed; 31 events, five screenshots, provenance and destroyed records for both run-owned containers; 351.809 s. |
| `workflow-c03-soloa-20261001-01` | C-03 0.1.0 | Solo A FAIL: string-valued blank destination cells triggered Calc overwrite confirmation; scripted actor did not confirm, so target remained initial. This is a fixture/task-path defect, not clipboard contention. | Reset passed; 26 healthy observer samples, original artifact retained, both run-owned containers destroyed; 322.229 s. |
| `workflow-c03-soloa-20261001-02` | C-03 0.1.1 | One bounded retry PASS: real GUI copy/paste filled A4:B5 exactly; source, guards and Writer initial content preserved. True empty-cell XML removed the warning. | Reset passed; 26 healthy observer samples, 50 events, five screenshots, provenance and two destroyed container records; 322.898 s. |

Raw artifacts are under `/home1/mjh/Projects/CoDesk-V0-A6000/artifacts/workflow-v1/<run-id>/`. The v0.1.0 failure was not overwritten. Old Solo reports used `joint_success=true` to mean all active goals passed; new runs separate `condition_success` and set Solo `joint_success=null`. The static manifest label `offline_oracle_only` describes contract validation; run-level Guest evidence is recorded separately. The corrected clipboard attribution only calls overwrite supported when A copy, B copy, A paste payload, paste target, and timing agree; unexplained payload changes are UNKNOWN.

## 2. New-family decision

**V1 remains four candidate mechanism categories, not four fully validated families:** Focus is the Core anchor; Clipboard is a scripted KEEP candidate; Modal and Application Context are optional. The literature screen does not justify a fifth V1 category now.

| Candidate from targeted hunt | Decision | Reason and evidence gate |
|---|---|---|
| Spatial-frame / viewport contention | CONDITIONAL FEASIBILITY CANDIDATE | A legitimate B scroll/zoom in the same focused window and same page could change A's old screen-coordinate mapping. Admit only if window XID, page identity, focus, clipboard and modal state remain fixed while viewport transform alone changes the target at A's coordinate. Both goals need exact record oracles and autonomous recovery. No CoDesk Guest evidence yet. |
| Selection / caret / active object | MERGE into Application Context | It is an internal target/selection state under unchanged OS window. A separate family would duplicate that candidate. |
| Window geometry, z-order, occlusion | MERGE with Focus or Modal | OSWorld and OSWorld-Noisy already study window motion/clutter/overlay as single-agent perturbations. A dual-goal trial could be a Focus/Modal workflow, but geometry alone does not define another family. |
| Notification / interruption | DROP as separate family | Treat a legitimate B-caused toast as exposure; modal decisions or focus theft are scored in existing categories. OSWorld-Noisy, DeskCraft, DynamicGUIBench and OSWorld 2.0 already cover interruption forms without two independently scored GUI goals. |
| Global IME / keyboard mode | FUTURE, UNVERIFIED | WindowsWorld reports single-agent IME/keystroke failures, but session-wide mode on pinned Ubuntu and sensitivity of the current Qwen action path are unproven. Requires deterministic reset and raw-key/committed-text oracle. |
| Shared undo/redo transaction history (prior H-01/H-02 proposal) | FUTURE, do not admit to V1 | MA-ID with separate local documents versus MA-SD with one shared document changes persistent-document topology as well as desktop sharing. A valid shared application backend in both conditions is not available in this phase. The earlier proposal remains a hypothesis, not a V1 family. |

The literature/source and direct-evidence versus inference boundary is in `NEW_FAMILY_HUNT_V2.md`. The finding is bounded to inspected papers; it is not a claim that no other work exists.

## 3. A-01 and M-01 priority

Complete the F-04/C-03 paired controls first because their code and exact oracles now exist. Then prioritize **A-01 same-window Browser tabs** for a full task if the top-level window stays constant and page/target IDs identify wrong-context actions. This has a clearer independence test against Focus. M-01 Save As should follow only if modal parent/transaction ownership predicts an outcome beyond ordinary focus interception; otherwise merge it into Focus. Neither feasibility probe is yet a registered paired task.

## 4. Next stage and acceptance rule

**Continue task implementation**, with a bounded validation sequence: Solo B for F-04 and C-03; one scripted MA-ID and MA-SD each; recovery controls only after the mechanism trace is interpretable. Preserve invalid attempts and check reset/provenance/ownership for every run. Stop or merge a prototype if the actor path or oracle is unstable. Do not scale to many instances or model runs until both goals and joint feasibility are demonstrated on real Guests.

For any new family, require equivalent task-relevant state across MA-ID/MA-SD, both independently scored goals, a logged hidden-state transition that existing families do not explain, exact private oracle, and separate exposure/interference/outcome/recovery records. A viewport probe may run later under that gate; its positive signature would support a fifth candidate, not automatically a Core family.

## 5. Review checks

Main-agent read-only artifact review confirmed the three run reports and resource ledgers above. The pinned A6000 Python environment ran `pytest -q tests/test_workflows_v1.py`: 6 passed. Python compile and Git whitespace checks passed. No new model/Guest episodes were run by the main agent. Existing untracked `artifacts/` remains outside the documentation/code checkpoint.
