# CoDesk Mechanism Expansion Research

**Scope:** research-only review of interaction mechanisms that could extend CoDesk beyond Focus/Input Routing and Clipboard. No code, Guest, or model was touched. Canonical repo was read-only inspected at A6000, HEAD `a1baba93e1020ffbf9d7060b0bbbf8079215f865`; current `MECHANISM_VALIDATION_ROUND1.md` reports Focus as model-validated, Clipboard as scripted-only, and Modal/Application Context as scripted feasibility candidates.

**Evidence labels:** **Direct evidence** means stated in the cited paper/artifact or present in task/protocol description. **Inference** means the proposed CoDesk distinction or candidate design inferred from that evidence; it is not claimed as an existing benchmark result.

## 1. Findings from nearby benchmarks

| Work | What its protocol actually exercises | Shared live desktop / independent goals? | Relevance to CoDesk |
|---|---|---|---|
| [OSWorld](https://arxiv.org/abs/2404.07972) | **Direct:** Single-agent, stateful desktop tasks with executable environment setup and task-specific state evaluators. The paper formalizes the agent loop as observation/action in a real computer environment. | No multi-actor interaction in the base benchmark. | Establishes the single-agent control/evaluation substrate, not contention. |
| [ParaGUIBench](https://arxiv.org/abs/2607.22689), paper §§II–III, pp. 2–4 | **Direct:** 233 tasks in six categories (web search, file search, online shopping, file operation, web navigation, search-and-write). Every worker runs in a separate Docker container with its own Ubuntu desktop, cursor and keyboard focus; workers share a directory for intermediate files. It scores task success plus critical-path/parallelism/token efficiency. The paper explicitly says separate desktops prevent clicks and keystrokes from disrupting one another. | Multiple GUI actors and often decomposed subgoals, but **not one desktop session**. Its independent tasks may have no cross-worker state; dependent tasks exchange intermediate outputs through files. | Important parallel-GUI neighbor, but its design isolates the exact live GUI control channel CoDesk studies. CoDesk must avoid claiming parallel GUI agents are themselves novel; the distinct question is what happens when independent agents share the active GUI control and application context. |
| [OSWorld-Noisy / ENVS](https://arxiv.org/abs/2606.22948), §4, pp. 4–5; Appendix B.1, Table 5, p. 13 | **Direct:** Keeps the original OSWorld goal/evaluator and injects one deterministic, held-out, recoverable perturbation. The perturbation source is modeled as a benign concurrent user. The 153 generators include non-target app sessions, notifications/dialogs/browser prompts/toasts/modal overlays, and occasional target-window occlusion/shove/resize. Input is not delivered to an unrelated target window, evaluator paths are protected, and events are designed to be recoverable. | A live desktop is perturbed, but the secondary actor is a noise/interruption source, not an independent task-bearing agent whose goal is scored jointly. | Closest overlap for exposure and recovery. CoDesk cannot claim novelty for popups, focus shifts, dialogs, or background activity alone. Its contribution must be independent actor goals, naturally generated cross-goal interference, and separate exposure/interference/outcome/recovery measurements. |
| [DeskCraft](https://arxiv.org/abs/2606.03103); [artifact README](https://github.com/mrwwk/DeskCraft), “Interaction Protocol” and “Evaluation Design” | **Direct:** 538 executable desktop tasks, including 152 interactive tasks. The user simulator sends clarifications, responds to agent questions, interrupts after a step count, or reacts when the agent says it is done (`agent_asks`, `step_count`, `agent_done`; additional triggers include `agent_idle`). Final state is checked programmatically using artifacts/browser state/media metadata, etc. | One GUI agent interacts with a simulated user over turns. The “user” does not run an independently scored GUI task in a shared desktop. | Human interruption and changing requirements are already benchmarked. A CoDesk GUI+Human branch should therefore score the human’s independent goal and agent goal in the same live GUI, rather than merely inject a new user message. Modal/focus interference from a user should not be sold as new without this distinction. |
| [WeaveBench](https://arxiv.org/abs/2606.09426); [artifact README](https://github.com/weavebench/WeaveBench) and `docs/ARCHITECTURE.md` | **Direct:** 114 long-horizon tasks require a single agent trajectory to interleave GUI observations/actions with CLI/code operations. The harness runs a single session over an Ubuntu sandbox, with a GUI plugin added to CLI/code tools. It scores deliverables and trajectory evidence. | One actor uses multiple interfaces; not multiple independently tasked actors sharing a GUI. | Supports hybrid-interface task design, but is not evidence of multi-actor GUI contention. GUI+CLI is an auxiliary modality/state control, not the shared-desktop core. |
| [AgentRoom](https://arxiv.org/abs/2608.23740), §§2.1–2.3, Appendix D; [paper artifact page](https://seonglae-agentroom.static.hf.space/index.html) | **Direct:** Concurrent coding agents share a CRDT-backed filesystem. MCP tools expose file claims/releases, broadcast, state and read. The paper’s tasks are Express/TypeScript services (Appendix D T1/T2/T4/T5); separate Python/Rust checks are supplementary. It reports code quality/abandonment, and explicitly notes that the task suite lacks a held-out correctness suite. | Shared project files and coordination protocol, but agents operate through coding CLIs; no shared screen, pointer, keyboard focus, or desktop-session contention. | Strong neighboring shared-workspace/concurrent-write literature, but not a GUI benchmark. It occupies some shared-artifact/ownership territory; it does not occupy the GUI control-plane question. |
| [CoAgent](https://arxiv.org/abs/2606.15376) and [STALE](https://arxiv.org/abs/2605.06527) | **Direct:** CoAgent studies concurrency control for agents mutating shared external state and proposes notification, semantic repair, ordering and compensation. STALE probes whether later evidence invalidates earlier memory/premises. | General tool/state or memory settings, not GUI desktop interaction. | Mechanism vocabulary for stale reads, invalidated plans and recovery. Cite as cross-domain mechanism neighbors; do not use them to claim the GUI benchmark space is occupied. |

### Consequence for CoDesk framing

**Direct evidence:** Multiple benchmarks now cover (a) parallel GUI task decomposition across isolated desktops (ParaGUIBench), (b) recoverable desktop disturbances including focus/dialog events (OSWorld-Noisy), and (c) human-agent interruptions and clarifications (DeskCraft). Shared code artifacts/coordination are addressed in CLI work (AgentRoom/CoAgent), and hybrid GUI+CLI trajectories in WeaveBench.

**Inference:** The remaining defensible CoDesk axis is the **interaction between two independently goal-directed actors sharing the same live desktop control/application state**, with both goals scored. A noise script that has no independent goal is not an actor; separate desktop workers do not expose shared keyboard/focus routing. Task count, another application, or random disturbances do not establish this distinction.

## 2. Candidate mechanism families

Recommendations are intentionally conservative. Only one candidate below is plausibly a new family. Modal and application context are already CoDesk candidates; literature review mainly sharpens their admission criteria.

### Candidate A — Shared document transaction / undo-history contention

- **Hidden state / contention source:** the application’s document-scoped edit/undo transaction history and dirty/save state. Actor B’s legitimate committed edit can become the newest undoable operation while Actor A is acting on an older local expectation.
- **Why distinct from Focus/Clipboard:** both actors can target the intended same document and correct controls; the conflict comes from application transaction ordering/undo scope, not which window receives a key or which payload is on the clipboard. **Inference.**
- **Literature basis:** AgentRoom’s paper identifies concurrent writes and shared-state coordination as a problem, but its mechanism is shared filesystem/CRDT and CLI—not GUI undo/history. CoAgent’s §2–3 motivates invalidated plans and repair under shared-state mutation, but its interface is tool/runtime middleware. These sources establish a cross-domain analogue, not prior GUI coverage. OSWorld-Noisy explicitly leaves evaluator files untouched and does not make the perturbing actor’s goal a scored document edit (ENVS §4.1, pp. 4–5). **Direct evidence for boundary; inference for novelty.**
- **Minimum workflow:** One Writer document, two independently specified edits to disjoint sections. Actor A applies a formatting operation and, if its own visible result is wrong, may autonomously use undo/reapply; Actor B performs and saves its separate content edit between A’s observation and recovery. Do not inject Ctrl+Z or force an error. The design is valid only if A’s own task makes undo/recovery a natural available action and both goals are jointly reachable.
- **Solo / MA-ID / MA-SD:** Solo runs each goal from the same document fixture. MA-ID uses equivalent seeded documents on separate desktops, so each actor’s undo stack is independent. MA-SD uses the same live Writer document/session and shared undo history. Keep actor goals, schedule, budget, app version and evaluator fixed; report exposure, actual undo target, final goal state, and recovery separately.
- **Oracle / evidence:** Parse saved ODT content/style state; record GUI action and document-change sequence. A mechanism event requires evidence that the undo operation reverted B’s specific earlier edit, not merely that A’s action failed. Score both exact goals and unintended deletion/restoration. Hidden evaluator must not expose undo-stack state to either actor.
- **Cost:** Medium. Same app family, but reliable undo-target provenance may need document snapshots or app-level event instrumentation. UI-only outcome without an undo-history trace is insufficient attribution.
- **Recommendation:** **Explore as one optional, high-value candidate** after current Focus/Clipboard workflow expansion; do not promote to Core before a real Guest feasibility prototype proves causal attribution and independent task reachability. This could be a genuinely distinct shared application-state family if it survives that test.

### Candidate B — Application context / active object ownership (current CoDesk candidate; not a new family)

- **Hidden state:** active tab/page/record/project, selected object/range, current view or pane inside an unchanged OS window.
- **Why it may differ from Focus:** OS window ID and keyboard target remain unchanged while an application-internal target/context changes. The current CoDesk scripted Browser probe reports precisely this signature: same Chrome top-level X11 ID, Page A→Page B, then A’s stale action writes into B. This is **verified in the CoDesk report**, but remains scripted feasibility rather than model evidence.
- **Literature boundary:** OSWorld-Noisy perturbations are broad desktop disruptions; ParaGUI workers have separate GUI state. The cited benchmark protocols do not report two independently goal-directed actors changing and using a shared in-window page/object context. DeskCraft’s user-dialogue phases change instructions, not a second GUI actor’s active browser context. **Direct boundary evidence; novelty inference.**
- **Minimum workflow:** two local browser forms/tabs with independent exact goals; B changes active page in the same browser window; A is free to re-observe and recover. Require constant top-level window ID and distinct page/target IDs as positive mechanism evidence; evaluate fields per URL/page.
- **Solo / MA-ID / MA-SD:** Solo A/B each use a seeded profile; MA-ID has equivalent browser fixtures and independent desktops; MA-SD shares one Chrome window/profile. All other task controls equal.
- **Cost:** Low–medium if browser target IDs and form state are readable; model episode still required before a benchmark claim.
- **Recommendation:** **Keep optional and explicitly separate from OS Focus only while the constant-window signature is measured.** If any distinguishing event is actually a window activation/focus change, merge with Focus. Not an additional new family beyond current taxonomy.

### Candidate C — Modal/transaction continuation ownership (current CoDesk candidate; likely Focus subfamily)

- **Hidden state:** modal stack, transient dialog parent/owner, and which task’s pending save/confirm/cancel transaction the dialog represents.
- **Why it might differ from Focus:** A dialog can hold a pending operation (save path, overwrite confirmation, unsaved-changes decision); the question can be which actor’s transaction is committed/cancelled, rather than just where the keystroke lands. **Inference.**
- **Literature boundary:** OSWorld-Noisy explicitly includes notifications, update/backup dialogs, browser prompts, permission dialogs, modal overlays and recovery actions (Appendix B.1, Table 5). Thus popups/dialogs as visual noise or focus obstacles are already represented. DeskCraft also supports mid-turn user interruptions. What is not shown in those protocols is a second GUI actor with an independent scored goal owning a concurrently pending dialog transaction. **Direct evidence for overlap; inference for remaining gap.**
- **Minimum workflow:** Actor A opens a real native save/overwrite dialog for its own file; Actor B has an independent Writer/Calc output goal. Give A normal observe/recovery opportunities; do not force B to click A’s dialog. A task only qualifies if the dialog’s parent/transaction owner and final commit/cancel decision are independently observable.
- **Solo / MA-ID / MA-SD:** Solo A and B verify each task separately. MA-ID uses equivalent fixture and distinct dialogs on isolated desktops. MA-SD uses the same desktop and a real dialog; score A’s saved path and B’s artifact, dialog ownership, accidental cancellation/commit, and recovery.
- **Cost:** Medium, due to native dialog behavior and ownership attribution; current CoDesk evidence establishes controllability/observability only.
- **Recommendation:** **Do not create a new family yet.** Keep as optional; merge with Focus if the only measured effect is focus/input interception. Keep separate only if task-transaction ownership changes final state even after controlling for focus routing.

### Candidate D — Shared application session / identity / workspace binding

- **Hidden state:** application-global active account, tenant/project/workspace, or selected record context that can change across tabs/panes and alter the meaning or permission of a later action.
- **Why distinct:** This is semantic principal/scope state, not clipboard payload or OS keyboard routing. But it is close to Application Context and shared backend/state consistency. **Inference.**
- **Literature basis:** OSWorld-Noisy includes login/verification-like disruptions only as recoverable environment perturbations; DeskCraft handles evolving user requirements; CoAgent studies tool-visible shared state. In the inspected GUI benchmark protocols I found no example where two independently tasked GUI actors change a shared application principal/scope and are jointly scored. Absence is bounded to the inspected works, not a field-wide proof.
- **Minimum workflow:** Local browser app with two seeded project/account scopes and objectively distinct permissions or record IDs. B switches a genuinely global session/project setting; A must detect the changed principal/scope before committing. Both actors have independent goals. Avoid relying on a real external service/account.
- **Solo / MA-ID / MA-SD:** Solo establishes each operation. MA-ID gets equivalent local seeded accounts and independent browser profiles. MA-SD shares one profile/session. Evaluator checks hidden principal/project ID and exact final records, not screenshot appearance alone.
- **Cost:** High. Deterministic auth/session reset and hidden state oracle required; same-tab/session semantics must be demonstrated rather than asserted.
- **Recommendation:** **Future work or merge with Application Context**, not V1 Core. Avoid splitting a second family until a live prototype shows a stable global identity/scope variable independent of page/tab state.

## 3. Mechanisms to merge or reject

| Proposed label | Recommendation | Reason |
|---|---|---|
| Pop-ups, window resize/move, notifications, background apps | **Do not add as new family** | Explicit OSWorld-Noisy perturbation catalog; unless the event-bearing human/agent has its own independently scored goal, this is robustness/noise exposure. |
| Keyboard target / window activation / focus stealing | **Merge into Focus/Input Routing** | Same hidden OS input target. A different application combination does not make it a new mechanism. |
| Active tab/page/current in-window object/range | **Application Context subfamily** | Distinct only when top-level window/focus is held constant and application context identity is independently observed. Otherwise merge with Focus. |
| Clipboard overwrite / stale clipboard payload / recopy recovery | **Clipboard family** | Already directly validated scripted in CoDesk; variations in text or payload type are workflow templates/instances, not mechanisms. |
| File write, shared directory, CRDT merge, stale file read, lost update | **Auxiliary shared-state track** | Important cross-domain work (ParaGUIBench, AgentRoom, CoAgent), but not evidence of a GUI-specific family and not required by the frozen CoDesk workspace definition. |
| User clarification / changed request / interruption message | **Human-agent interaction track or protocol factor** | DeskCraft already tests this. It is not shared desktop contention unless the human also acts through the same live GUI and has an independently scored goal. |

## 4. Recommended scope and short decision

- **Core now:** Focus/Input Routing.
- **Core candidate after scripted controls:** Clipboard.
- **Optional extensions, not new families:** Modal/transaction continuation ownership; Application Context.
- **One exploratory new candidate:** shared document transaction/undo-history contention.
- **Future / likely merge:** application session/account/project binding; treat as Application Context unless a distinct global scope state is proven.
- **No-go for family proliferation:** pop-up/noise, more focus variants, and filesystem conflicts as new GUI families.

### Admission test for any new family

A candidate should enter the suite only if an episode demonstrates all of these:

1. Two independent actor goals each pass Solo and are jointly feasible from an equivalent task-relevant fixture.
2. MA-ID vs MA-SD changes only the intended shared live GUI/application state; task, schedule, budgets, prompts, evaluator and semantic initial state stay fixed.
3. The hidden state variable can be directly recorded without exposing it to the actors.
4. Logs distinguish scheduled exposure, measured mechanism event, final outcome, and autonomous recovery.
5. The event is not explainable entirely by the existing Focus or Clipboard family.
6. An exact programmatic oracle checks both goals and non-target integrity.

Until a candidate passes this screen, workflow expansion should remain anchored in the two supported families rather than treating the candidate count as the benchmark’s contribution.

## References

1. Xie et al., [OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments](https://arxiv.org/abs/2404.07972), 2024.
2. Yu et al., [Beyond Sequential Interaction: Benchmarking Parallel Execution and Coordination for GUI Agents (ParaGUIBench)](https://arxiv.org/abs/2607.22689), 2026, especially §§II–III, pp. 2–4.
3. Zhou et al., [ENVS: Environment-Native Verified Search for Long-Horizon GUI Agents](https://arxiv.org/abs/2606.22948), 2026, OSWorld-Noisy §4, pp. 4–5, Appendix B.1 Table 5 p. 13.
4. Wang et al., [DeskCraft: Benchmarking Desktop Agents on Professional Workflows and Human-in-the-Loop Collaboration](https://arxiv.org/abs/2606.03103), 2026; artifact [README](https://github.com/mrwwk/DeskCraft), “Interaction Protocol” and “Evaluation Design”.
5. Li et al., [WeaveBench: A Long-Horizon, Real-World Benchmark for Computer-Use Agents with Hybrid Interfaces](https://arxiv.org/abs/2606.09426), 2026; artifact [README](https://github.com/weavebench/WeaveBench), [architecture](https://github.com/weavebench/WeaveBench/blob/main/docs/ARCHITECTURE.md).
6. Cho and Lee, [AgentRoom: Concurrent Multi-Agent Coding in a CRDT-Backed Shared Workspace](https://arxiv.org/abs/2608.23740), 2026, §§2.1–2.3 and Appendix D.
7. Lyu et al., [CoAgent: Concurrency Control for Multi-Agent Systems](https://arxiv.org/abs/2606.15376), 2026.
8. Chao et al., [STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?](https://arxiv.org/abs/2605.06527), 2026.
