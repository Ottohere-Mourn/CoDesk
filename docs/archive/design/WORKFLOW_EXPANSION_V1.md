# CoDesk Workflow Expansion V1 - Initial Template Candidates

Status: design-only shortlist. No task instances were generated or registered by this document. Existing real-Guest evidence is cited only where stated. A workflow template is defined by its operation sequence, target type, interaction point, and evaluator predicate. Text/seed/layout/coordinates are instance or run data, not templates.

## Family gate

- Focus / Input Routing is the validated anchor family. Qwen Solo passed, MA-ID passed twice, and MA-SD failed twice with trace-supported cross-window input routing.
- Clipboard Ownership is a scripted real-Guest candidate. Solo A/B, MA-ID, MA-SD overwrite, observer control and recopy recovery have evidence; model behavior remains untested.
- Modal and Application Context are optional mechanism candidates from scripted feasibility probes. Do not make them prerequisites for this initial Focus/Clipboard expansion.
- GUI+CLI persistent-state consistency remains an auxiliary comparison. Shared filesystems are not required when goals need only equivalent seeded state.

## Template / instance / run hierarchy

Family groups related hidden-state contention. A workflow template fixes the operation path, independent Actor goal structure, shared resource, exposure opportunity and oracle. An instance supplies concrete documents, values, pages or records while keeping that workflow. A run supplies condition, schedule realization, Guest IDs, model, budget, coordinates and repeat. Changing only values, text, IDs or coordinates never creates another template.

For every template, Solo must show each Actor can finish independently; MA-ID uses semantically equivalent initialized task state on separate desktops/resources; MA-SD uses one shared live desktop. Keep task, model, prompt, budgets, schedule, evaluator and initial state semantics fixed. Let Actors observe and recover. Record scheduled exposure, observed interference, outcome and recovery separately.

## Initial shortlist

### Focus / Input Routing

| ID | Workflow template | Actor goals and operation path | Shared resource and exposure | Oracle / distinction |
|---|---|---|---|---|
| F-01 | Dual office direct-entry (existing anchor) | A enters and saves a Writer document value; B edits and saves a Calc cell. | Active window, keyboard and pointer; one Actor's legitimate window activation occurs between the other's observation and next GUI action. | Exact Writer/Calc state plus cross-document contamination; direct keyboard/text input routing. Existing Qwen Solo/MA-ID/MA-SD episodes are exploratory evidence. |
| F-02 | Same-application multi-document switching | A adds a comment to Writer document A; B edits a named heading in Writer document B. Each document is open in a distinct top-level window. | Window focus among same-process documents; each Actor must target a different document identity. | Exact comment and heading in their respective files; detects wrong-window action even when app name/process is unchanged. |
| F-03 | Browser form submission beside document editing | A completes a multi-field local Browser form, validates and submits it; B edits/saves a Writer note. | Window focus plus keyboard and pointer during a multi-step form; the form submission is one atomic goal. | Exact form record and Writer content; distinguishes partial form entry from wrong-window routing. |
| F-04 | Spreadsheet range/formula entry beside prose editing | A selects a declared Calc range, enters a formula, fills the range and saves; B revises a Writer paragraph. | Active window, cell selection and keyboard routing; exposure occurs between observation of the selected range and formula/fill action. | Exact cell matrix/formulas and Writer text; checks range spill or text contamination. The operation differs from a single-cell edit. |
| F-05 | Pointer selection and drag/reorder | A reorders named Calc columns or rows by drag; B selects and edits a specific Writer object/paragraph. | Shared pointer position, selection and active window during a press/drag/release sequence. | Exact order and Writer target state, plus unchanged neighbors; tests pointer/selection routing rather than only typed input. Feasibility must be checked before promotion. |

### Clipboard Ownership

| ID | Workflow template | Actor goals and operation path | Shared resource and exposure | Oracle / distinction |
|---|---|---|---|---|
| C-01 | Plain paragraph transfer (existing prototype) | A copies a source paragraph and pastes it into a Writer destination; B copies a distinct source string and pastes into Calc. | Session clipboard generation changes between A's copy and paste; Actors may recopy. | Exact source/destination text and cell values; observer joins owner/payload digest with target and final state. Scripted Guest evidence exists. |
| C-02 | URL to hyperlink transfer | A copies a Browser page URL, then inserts it as a hyperlink in a Writer phrase; B copies/pastes its own identifier into a different destination. | Clipboard payload ownership across Browser and Writer; a URL can be normalized or pasted into the wrong UI field. | Exact hyperlink href/text, second destination and source integrity. Different sequence and link oracle from plain text. |
| C-03 | Rectangular range transfer | A copies a multi-cell Calc rectangle and pastes it at a declared target range; B performs a separate clipboard task before A consumes it. | Clipboard carries tab/newline structured cell data; ownership and generation can change before paste. | Exact matrix dimensions, values and formulas; detects flattening, shifted ranges or overwrite, distinct from one string. |
| C-04 | Rich-text transfer and paste mode | A copies formatted Writer text (bold/list or link) and pastes into another document using the task's declared paste mode; B copies different rich text. | Clipboard MIME representations and paste negotiation; the same payload may have text/plain and HTML/RTF representations. | Exact text plus required formatting/structure and no extra objects. Distinct from plain-text digest only if format preservation is part of the goal. |
| C-05 | Cut-and-move with source integrity | A cuts a specific paragraph/object and pastes it into a destination; B performs an independent copy before A completes the move. | Clipboard replacement can interrupt a destructive transfer after source removal but before destination confirmation. | Destination exactness, source deletion only after successful move, and no duplication/loss; recovery may require recopy or undo. |
| C-06 | File URI to upload control | A copies a file in the file manager and attaches it through a Browser upload control; B uses the clipboard for an independent text transfer. | Session clipboard switches between file URI/list and text; paste/upload target remains a GUI control. | Exact uploaded filename/content plus B's destination and source preservation. This is a different payload type and app operation from text transfer. |

## Deduplication and promotion

- The 11 rows above are workflow candidates, not 11 validated tasks. F-01 and C-01 reuse existing evidence; the remaining rows need offline oracle review and real-Guest feasibility.
- Promote a candidate only if its operation graph or primary oracle differs from existing templates. Swapping Writer for another editor, changing string values, or using a new seed is insufficient.
- Keep Focus primary. Keep Clipboard as candidate pending future genuine-agent evidence. Modal and Application Context can be optional extension tags; do not count them in this 11-template shortlist.
- Before expanding an accepted template into instances, run both Solo controls, a jointly feasible scripted control, MA-ID and MA-SD with matched relevant state, exact evaluator, reset and event/provenance checks.
- First expansion milestone: select at most 4 templates (2 Focus and 2 Clipboard) for executable task specs. Add more only when they pass the distinct-workflow gate. Instance scale can follow later; do not create 200-300 seeds first.
