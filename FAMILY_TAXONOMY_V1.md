# CoDesk Family Taxonomy V1

Status: **frozen at five families** (`CODESK_V1_SCOPE = 5_FAMILIES`), effective 2026-10-03. The scope is an evidence-backed exploratory benchmark boundary, not a claim that every workflow or application has been validated.

## Measurement contract

CoDesk studies independent computer-use Actors in Solo, multi-agent independent-desktop (MA-ID), and multi-agent shared-desktop (MA-SD) conditions. MA-ID and MA-SD start from equivalent task-relevant fixtures and keep goals, prompt, model, budgets, schedule, evaluator, and reset rules fixed; only the relevant shared GUI state differs. Physical filesystem sharing is not required.

Report scheduled exposure, actual state exposure, harmful interference, final goal outcome, and autonomous recovery separately. A task failure without evidence of the candidate state transition is not mechanism evidence. A successful recovery after exposure is positive interaction evidence, not a non-event.

## Frozen families

| # | Family | Shared hidden state | Boundary from other families | Anchor / evidence status |
|---:|---|---|---|---|
| 1 | **Focus / Input Routing** | OS-level foreground window and keyboard/mouse destination | The active top-level input target changes. It does not require changing the selected object within an application, clipboard payload, page/tab, or document history. | F-01 Writer+Calc; real Qwen Solo pass, MA-ID 2/2 joint pass, MA-SD 2/2 joint fail with input-routing traces. Historical evidence; see `MECHANISM_VALIDATION_ROUND1.md` and `REAL_DUAL_AGENT_EVAL_REPORT.md`. |
| 2 | **Clipboard State** | Shared X11 clipboard/selection owner and payload generation | The payload/owner changes while the receiver's intended GUI target may remain correct. It is distinct from where input is routed. | C-01 text transfer; scripted controls plus real Qwen event-gated overwrite exposure and matched MA-ID. MA-SD showed exposure 2/2; task-outcome attribution also involved focus/grounding, so do not claim clipboard-only task failure. See `QWEN_FAMILY_PILOT_REPORT.md`. |
| 3 | **Application Context** | In-application page/tab/record context | The OS window may remain the same while the app's internal page or record changes. It is distinct from OS focus and from a selection inside a fixed document. | A-01 Browser tabs; Qwen Solo A/B stable, MA-ID 2/2 joint pass, MA-SD 2/2 joint fail with tab-a→tab-b exposure and no autonomous recovery. See `A01_BROWSER_CONTEXT_TASK.md` and `QWEN_FAMILY_PILOT_REPORT.md`. |
| 4 | **Selection / Active Object** | Current selected cell/range/object in an otherwise unchanged app, document, page, and top-level window | The OS window, app page, document, and clipboard can stay unchanged while the action target changes. It is narrower than application context and independent of focus/input routing. | `CODESK-FAMILY-SELECTION-001`, Calc B2/C3. Scripted Solo A/B, MA-ID, MA-SD, and recovery all exercised. Qwen Solo A/B 2/2, MA-ID 2/2, and MA-SD actual selection exposure 3/3; one episode ended in a goal failure and two recovered. **KEEP.** |
| 5 | **Undo / Redo History** | Per-document operation-history stack / current undo branch | A normal Undo/Redo acts on the document's latest history entry, which may belong to another Actor. The app, document, window, selection target, and clipboard need not change. It is distinct from selection, focus, and page context. | `CODESK-FAMILY-UNDO-HISTORY-001`, LibreOffice Calc. Scripted Solo A/B and MA-ID pass; MA-SD produced same-document cross-Actor Undo; recovery positive control passed. Qwen Solo A/B 2/2, MA-ID 2/2, MA-SD valid exposure/interference 2/2 with no autonomous recovery. **KEEP.** |

## Scope boundary and exclusions

- The four families other than Focus are not aliases for “focus conflict.” Their hidden state and evidence are directly observable and held apart from top-level window identity.
- Shared files/backend consistency remains auxiliary and is not a CoDesk core family. MA-ID does not require physically shared filesystems.
- Modal/dialog ownership is paused and not included as a sixth family. Existing evidence did not establish a state effect independent of focus/input routing.
- Workspace Object Lifecycle, Application Mode, and other candidates were not pursued after two distinct new families met the V1 acceptance gate. Their omission means **not in V1**, not that they are impossible.
- The two new families currently have one anchor workflow each. Generalization across more applications, task templates, and independent instances remains future work.

## Evidence interpretation

The model pilots are small, mechanism probes. They support the existence of observable shared-state exposure and candidate-specific outcomes under these fixtures and schedules. They are not estimates of population performance, robust recovery rates, or cross-application generality. Keep each episode's report, action trace, screenshots, provenance, reset, and ownership ledger as the evidence source.
