# Family Gap Audit V3

**Purpose:** bounded audit of two candidate interaction families only.  
**Evidence reviewed through:** 2026-10-01.  
**Repository context checked:** `WORKFLOW_SUITE_V1.md`, at CoDesk HEAD `487e8eaf1145f5d32f08aae089707f3440add9bb`. This audit adds no task, changes no experiment protocol, and reports no Guest/model run.

## Executive decision

| Candidate | Relation to current families | Pure-GUI Solo / MA-ID / MA-SD feasibility | Decision |
|---|---|---|---|
| Selection / Active Object contention | Distinct from OS window/input focus and clipboard when the focused app/control stays fixed. At the current taxonomy boundary it is a fine-grained form of **Application Context** (the active target/range/caret inside a document), rather than a well-supported fourth family. | Feasible without shared filesystem: clone one deterministic Calc fixture; actor goals concern separate ranges and can be independently achieved on cloned desktops; on MA-SD the same sheet/control is shared. A saved ODS cell oracle can determine misapplication; GUI/accessibility or app event telemetry must establish that selection changed while window and focused control did not. | **MERGE into Application Context as a candidate subtrack; do not add a family now.** Worth one bounded feasibility prototype only if telemetry can verify selection identity and control focus independently. |
| Workspace Object Lifecycle / file state contention | Primarily persistent filesystem/backend state, not a transient shared-desktop state. It is outside CoDesk's current shared-filesystem scope and confounds the MA-ID vs MA-SD contrast if MA-ID uses independent local filesystems while MA-SD shares one. | Pure-GUI file-manager tasks are possible in one desktop, but a causal MA-ID control requires equivalent lifecycle state propagation/topology. Independent local fixture copies remove the cross-actor rename/delete/create effect; sharing a backend reopens the explicitly frozen infrastructure branch. | **DROP from current V1/core; do not implement under the frozen protocol.** Reconsider only after a separate protocol decision authorizes and equalizes backend topology. |

The review found many benchmarks for single-agent selection/file operations and several forms of multi-agent parallel work, but no reviewed artifact that evaluates two independent agents contending over a selected GUI object in one desktop session. That is a bounded search observation, **not** a claim that no such work exists anywhere.

## 1. Scope and current taxonomy

CoDesk V1 freezes eight workflow templates across Focus/Input Routing, Clipboard State, and Application Context. Modal is paused. The causal comparison uses Solo, MA-ID (two isolated desktop sessions with equivalent task-relevant fixture), and MA-SD (same desktop session). Shared filesystem/backend engineering is frozen; MA-ID and MA-SD must not differ in backend topology for any claimed desktop-sharing effect.

The distinction used in this audit is:

- **Focus/Input Routing:** which OS window or GUI control receives the submitted input event.
- **Clipboard State:** the current transferable payload/owner/generation used by a later paste.
- **Application Context:** which page, record, document subview, or active target is selected inside the same app/window.
- **Selection/Active Object candidate:** a narrow instance of application-internal target state, e.g. text range, caret, spreadsheet range, or selected object. It is only separable from Application Context if the benchmark explicitly defines and measures that narrower state.
- **Workspace Object Lifecycle candidate:** a file/folder/object is created, renamed, moved, deleted, or replaced in persistent workspace state. This is not merely a window/tab/selection state transition.

## 2. Evidence from related benchmarks and artifacts

### Desktop GUI task benchmarks

- **OSWorld** defines real desktop/web tasks with task setup and execution-based state evaluators; its stated task collection includes OS file I/O and multiple apps. That establishes substantial prior coverage of file manipulation and app-level operations as *single-agent task content*, not shared-object contention. See the [OSWorld paper/project page](https://os-world.github.io/) and [public repository](https://github.com/xlang-ai/OSWorld). The reviewed overview does not specify independent actors racing over one live desktop.
- **Windows Agent Arena** provides 150+ Windows tasks and device-state evaluators, with parallel benchmark execution at scale. Its public task/evaluation description is about separate evaluations and final device state, not two actors manipulating one simultaneous session. See [paper](https://arxiv.org/abs/2409.08264), [repository](https://github.com/microsoft/WindowsAgentArena), and the paper's appendix task/evaluator description.
- **GUI-Drag / ScreenDrag** demonstrates that exact text-span selection is a real, measurable GUI capability: its 5,333 human-annotated cases report exact Selection Rate as well as drag-trigger and boundary metrics across Word, PowerPoint, and PDF. This supports selection as a stable task primitive and an objective oracle, but it is a single-agent grounding benchmark, not multi-actor contention. See [project and metrics](https://osu-nlp-group.github.io/GUI-Drag/).
- **ParaGUIBench** studies multi-agent GUI parallelism using workers on separate desktop instances and a shared filesystem, with decomposed tasks and throughput/efficiency metrics. Its stated setup is not one session with competing keyboard focus or in-app selection. It is a near-domain coordination benchmark, not evidence that either candidate is already covered as shared-desktop contention. See [paper](https://arxiv.org/abs/2607.22689), especially abstract and Introduction, and the paper-linked project/release should be pinned before relying on task-level details. The exact ParaGUIBench task repository was not inspected in this bounded audit.
- **DeskCraft** evaluates long-horizon professional desktop workflows and a human-agent protocol with mid-turn clarification, user-initiated interruptions, and post-turn feedback. This supports interruption as a studied interaction pattern, but the reviewed protocol describes conversational intervention, not two independent agents concurrently changing a shared selection or file namespace. See [paper](https://arxiv.org/abs/2606.03103) and [project page](https://mrwwk.github.io/DeskCraft/).

### Multi-agent and hybrid-interface near neighbors

- **AgentRoom** is the closest file-state neighbor: coding CLI agents concurrently edit a CRDT-backed shared filesystem using file claims/status/broadcast. The paper explicitly defines its substrate as a shared filesystem and evaluates coding outputs; it is not a GUI benchmark and does not evaluate a live desktop's file-manager focus/selection. This means file lifecycle/content conflict is an established *cross-domain mechanism*, while GUI presentation-specific claims would need distinct evidence. See [paper](https://arxiv.org/abs/2608.23740), §2.1 and experimental task description, and [project artifact](https://seonglae-agentroom.static.hf.space/index.html).
- **WeaveBench** requires one agent trajectory to interleave GUI with CLI/code; its examples validate GUI-visible state against backend/service state. It is relevant to interface/channel state consistency, not independent actors racing over one desktop. See [repository](https://github.com/weavebench/WeaveBench) and [paper](https://arxiv.org/abs/2606.09426).

Together these sources set the collision boundary: ordinary selection and file lifecycle tasks already exist in single-agent desktop suites; multi-agent shared-file coordination exists in CLI/code systems; parallel GUI task decomposition exists across independent desktop instances. The candidate novelty, if any, would be the *causal shared-session interference protocol and its instrumentation*, not the underlying click, selection, rename, or delete operation.

## 3. Candidate A — Selection / Active Object contention

### Mechanism and collision analysis

Candidate state: the active text range, caret, spreadsheet range, canvas object, or list item within an application. The defining event is Actor B changing that target after A's observation; A's later GUI operation is then applied to B's active target or no target.

This is not necessarily Focus/Input Routing: both actors may remain in the same Calc top-level window, same sheet, and same focused grid control. The divergent state can be only `selected_range`. It is also unrelated to Clipboard if the workflow uses direct GUI editing and no copy/paste. However, under the current broad Application Context definition (“active target inside the app”), selection is a finer-grained context variable. Splitting it into a new family now would overstate taxonomy independence. The defensible treatment is a **Selection subtrack under Application Context**, pending a discriminating experiment.

### Minimal pure-GUI workflow proposal (design only)

**App:** LibreOffice Calc, one sheet with disjoint protected target ranges and guard cells.  
**Actor A:** select named range B2:C3 and enter a four-cell pattern, preserving its guard.  
**Actor B:** select named range G2:H3 and enter a different four-cell pattern, preserving its guard.  
**Shared state:** Calc window, sheet, focused grid control, and current selected cell/range. No persistent cross-session filesystem sharing is needed; MA-ID receives byte-identical independent workbook fixtures, and each desktop is checked separately.

**Solo:** A and B each run alone from the same fixture class and must reach their exact target.  
**MA-ID:** each actor operates an isolated desktop initialized from the identical fixture; both exact goals must pass independently.  
**MA-SD:** actors use the same Calc desktop with a fixed opportunity schedule. A observes/selects its range, yields; B selects and edits its range; A resumes with the same operation policy and may either proceed autonomously or re-observe/reselect. Do not force A to type into the wrong range.

### Oracle and mechanism evidence

- **Hidden final-state oracle:** parse saved ODS cell matrix; exact values in A/B target ranges; all non-target cells unchanged; file opens/saves successfully. Score A, B, joint outcome separately.
- **Selection transition:** capture active sheet/cell/range after each observation and each committed action using a verified read-only LibreOffice accessibility/UNO observer or UIA/AT-SPI property. The observer must not inject focus or change selection. If exact selection cannot be read reliably, screenshots alone support only an ambiguous inference and are not enough to label selection contention.
- **Control invariants:** log X11 top-level window ID/title and focused accessibility control before/after B. To call this selection-specific, require unchanged window and unchanged focused grid control while active range changes. Any window/control focus transition is classified as Focus/Input Routing or mixed/unknown.
- **Exposure:** A had an observation/action plan tied to range A; B's selection mutation occurred before A's next submitted action.
- **Observed interference:** range changes from A target to B target, then A's action is delivered while focus remains the same grid; final state/log shows A's value/action affected B's range or failed at A's range.
- **Recovery:** A re-observes/reselects its intended range and achieves both target matrices without undoing B's goal. Preserve the unrecovered naive run as a separate episode.

### Feasibility and decision

The GUI workflow is constructible and its final-state oracle is robust. Existing GUI-Drag evidence shows exact selection can be objectively evaluated as a task capability. The open risk is *mechanism instrumentation*: an evaluator can read saved cell values but cannot by itself prove that the range changed while focus remained constant. Before coding a benchmark task, do a bounded observer feasibility check. If the stable observer is unavailable, place the instance under Application Context with “interference source unknown/mixed” attribution, or drop it; do not create a new family.

**Decision: MERGE into Application Context (candidate subtrack); no family-count increase.** Reconsider a distinct family only if a preregistered state definition and instrumentation separate active-object selection from the existing tab/page/record context tasks and from focus routing.

## 4. Candidate B — Workspace Object Lifecycle / file state contention

### Mechanism and collision analysis

Candidate state: persistent file/folder existence, path, parent, or version. One actor creates, renames, moves, replaces, or deletes an object while another acts on an observation/reference that predates the mutation. Possible GUI manifestations include stale File Manager listings, stale Open/Save dialog paths, or an application holding an object whose path was changed.

The mechanism's causal carrier is persistent workspace/backend state. It differs conceptually from transient focus, clipboard payload, or app-internal tab/selection state. However, an MA-ID/MA-SD comparison is not valid under the present topology if lifecycle updates propagate only in MA-SD: that changes both (a) sharing the live desktop and (b) sharing the persistent backend. With independent local filesystems, the mutation by B cannot invalidate A's MA-ID object reference, so the defining exposure disappears. This is precisely the frozen shared-filesystem branch and cannot be solved by task wording.

### Minimal GUI-only workflow considered (not approved for implementation)

**App:** GNOME Files, one project directory with `draft.odt`, `approved.odt`, and unique decoy names.  
**Actor A:** open the specifically assigned file, make a designated GUI edit, and save to the specified path.  
**Actor B:** rename or move a different specified file to an archive subfolder through Files, preserving its content.  
**MA-SD opportunity:** A observes/open dialog listing; B performs the rename/move; A resumes using its prior file/path observation. A may refresh/navigate and recover. **Oracle:** exact directory tree (relative paths and content hashes), exact document edit, no decoy mutation, and event log proving B's GUI rename/move preceded A's path operation.

Solo A/B are feasible. MA-SD is feasible. But under current MA-ID each desktop starts from the same file tree and B's rename on Guest B will not affect A's Guest A. To make MA-ID a true isolation control for this mechanism, both agents need the same task-relevant namespace with equivalent propagation semantics, which returns to shared backend work. A mirrored-event service would introduce a new synchronization mechanism and a different treatment, not a minimal control.

### Decision

**DROP from current V1/core and defer indefinitely under the frozen backend policy.** Do not count ordinary file-management tasks as validation of lifecycle contention. Revisit only in a separately approved protocol where MA-ID and MA-SD have matched backend topology and independently manipulated desktop control surfaces. This conclusion does not claim the mechanism is uninteresting; it says the present causal design cannot isolate it.

## 5. Recommended scope and next action

- Keep the three frozen families and eight workflows unchanged.
- Do not add a fourth family.
- If future instrumentation work is authorized, test **one** Selection subtrack probe under Application Context. Gate: same window + same focused grid control + observed active-range change + exact final-state attribution, with Solo/MA-ID feasible and recovery observable.
- Do not prototype Workspace Object Lifecycle while backend topology remains frozen.
- Continue the already planned Qwen pilot/instance work according to the main task; this audit is non-blocking and provides no model evidence.

## Evidence limits

1. This was a targeted desk review, not a systematic review of every desktop/HCI publication or task repository. Absence claims are deliberately limited to the artifacts listed here.
2. Paper pages and linked project pages were inspected; the exact ParaGUIBench task-level repository and full task manifest were not audited in this pass. No claims about individual ParaGUIBench task IDs are made.
3. GUI-Drag's Selection Rate validates selection correctness as a single-agent capability metric; it does not prove multi-actor selection contention is novel or robust.
4. No CoDesk code, evaluator, Guest, model, or task configuration was changed or run for this audit.

## References

- Xie et al., [OSWorld](https://arxiv.org/abs/2404.07972), [project](https://os-world.github.io/), [code](https://github.com/xlang-ai/OSWorld).
- Yu et al., [Beyond Sequential Interaction: ParaGUIBench](https://arxiv.org/abs/2607.22689); task-level artifact inspection remains open and task-ID claims are intentionally omitted.
- Wang et al., [DeskCraft](https://arxiv.org/abs/2606.03103), [project](https://mrwwk.github.io/DeskCraft/).
- GUI-Drag authors, [GUI-Drag / ScreenDrag](https://osu-nlp-group.github.io/GUI-Drag/).
- AgentRoom authors, [AgentRoom](https://arxiv.org/abs/2608.23740), [project artifact](https://seonglae-agentroom.static.hf.space/index.html).
- WeaveBench authors, [WeaveBench](https://arxiv.org/abs/2606.09426), [code](https://github.com/weavebench/WeaveBench).
- Bonatti et al., [Windows Agent Arena](https://arxiv.org/abs/2409.08264), [code](https://github.com/microsoft/WindowsAgentArena).

