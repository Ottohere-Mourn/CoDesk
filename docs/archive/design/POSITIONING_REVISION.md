# Positioning revision: Multi-Actor Computer Use

**Audit snapshot:** 2026-09-26. This revision supersedes the previous broad reading that CLI/shared-state work occupied the main GUI novelty claim. It preserves those works as cross-domain mechanism neighbors and reclassifies the GUI/Desktop evidence. See [NOVELTY_AUDIT.md](NOVELTY_AUDIT.md) and [OVERLAP_MATRIX.md](OVERLAP_MATRIX.md).

## Updated conclusion

The **GUI/Desktop/Computer-Use mainline is not shown to be occupied by a direct collision in the literature and artifacts audited**. Multiple important partial overlaps must be acknowledged:

- ParaGUIBench runs multiple GUI workers and measures top-level success/efficiency. It has actual concurrent shared-document editing failures, but each worker has a separate desktop/focus and the planner decomposes one user instruction (paper pp. 4–6; Appendix A, Table XI, PDF p. 14 / printed p. 13).
- MACU runs parallel GUI CUA subagents across OSWorld and related computer-use tasks, but gives each subagent an isolated VM and decomposes one task into a DAG (paper pp. 1–4, Appendix p. 14; repository `utils/vm_utils.py`, `osworld/desktop_env/providers/`).
- PC-Agent and UFO/UFO² use hierarchical GUI-agent roles to solve one desktop task; their agents are not separately goal-directed actors competing for the same session.
- UFO³/NebulaBench coordinates heterogeneous devices and evaluates task/fault recovery, not competition inside one shared desktop session.
- DeskCraft evaluates a GUI agent responding to a UserSimulator; GUIDE evaluates model inference over human GUI recordings. Neither measures two simultaneously active, independently tasked desktop controllers.
- WeaveBench and CUA-Universe test one actor switching between GUI and CLI; CUA-Universe exposes shared application state and stale-view resynchronization. OSWorld-Human supplies human reference trajectories for efficiency, not a live co-actor.
- MMBench-GUI L4 calls multi-app workflow execution “Task Collaboration,” but its protocol is one agent coordinating applications.

CoAgent, AgentRoom, CooperBench, STALE, SWE-Touch, and CodeCRDT establish important shared-state/concurrency mechanisms in CLI, code, or patch-composition settings. They are **cross-domain mechanism neighbors**, not GUI Agent Benchmarks, and should shape our controls and evaluator rather than narrow away the GUI mainline.

## Research question

> How do independently goal-directed actors using different computer-use channels affect one another when they share a live graphical workspace, and which interaction, state-awareness, or recovery policies preserve both actors’ goals and global application invariants?

The unit of evaluation is a joint live execution with actor-attributed observations and actions. The benchmark should distinguish one desktop session from separate desktops that happen to share files, and distinct actors from one agent decomposing its own request.

## Three task branches to preserve

### 1. GUI + GUI

Two independently tasked GUI agents operate through the same desktop session and application state. Measure:

- foreground-window/focus and keyboard/pointer routing, including actions delivered to an unintended window;
- shared clipboard, modal dialogs, window switching and application-level state visibility;
- each actor’s goal completion, joint invariants, collateral regressions and recovery;
- the contrast with ParaGUIBench-style separate desktops plus shared directory, and with a serialized same-session schedule.

Do not define the branch as another parallel planner/worker speedup benchmark. Actors must have separate task instructions and independently checkable goal predicates.

### 2. GUI + CLI

A GUI actor and CLI actor act on the same live application/workspace through different control paths. Measure when CLI writes are visible (or stale) in the GUI, whether GUI actions based on stale visible state cause a conflict, and how each actor detects/reconciles it.

WeaveBench and CUA-Universe are important partial overlaps for a single actor using both modalities; CUA-Universe additionally tests shared GUI/CLI project state and stale GUI-view resynchronization (paper arXiv:2609.05374, §§3–4, pp. 3–6). CoAgent/AgentRoom/CooperBench/STALE inform same-state and composition tests. Keep the CSV example as an auxiliary smoke or controlled state-visibility task. Promote it only if the graphical application’s visible/cache state is essential to the failure and recovery predicate; a filesystem overwrite alone is not the central contribution.

### 3. GUI + Human

A human (live participant or faithful replay) and GUI Agent each have an independent intention and act on the same session. Replay must preserve the human’s actual action sequence, target windows, timing relation, and task goal. Evaluate the human’s outcome as well as the agent’s and the joint application state.

DeskCraft occupies the GUI+Human instruction-change and conversational interaction space; GUIDE provides human action/intent traces, and OSWorld-Human provides reference UI trajectories for efficiency comparisons. Differentiate by actual co-control/actions and independently scored goals, not by calling a user message or a reference trace a second actor.

## Defensible candidate contribution

The candidate contribution is a **Multi-Actor Computer-Use benchmark and protocol** that combines:

1. distinct, independently verifiable actor goals;
2. actor types spanning GUI agents, CLI agents, and humans/replays in the three branches above;
3. one shared live desktop/application session in the relevant conditions, with topology metadata that separates it from a shared folder or VM pool;
4. deterministic or recorded interleavings that induce GUI-specific interaction effects rather than random timing noise;
5. per-actor success, joint success, cross-actor regressions, recovery outcome and coordination cost;
6. hidden, executable state checks plus source-attributed event logs.

The contribution is the controlled interaction space and joint evaluation design. Model count, task count, orchestration architecture, and reuse of OSWorld by themselves are not sufficient novelty claims.

## Task acceptance gates

Keep a task only when it satisfies all the following:

- **Separate solvability:** each actor passes its own goal from the same reset state when run alone.
- **Joint satisfiability:** a valid serialized/coordinated schedule can satisfy both goals and all shared-state invariants.
- **Real actor interaction:** every actor has its own instruction/intention and source-attributed observations/actions. It is not a planner-created subtask or a disturbance pretending to be an actor.
- **Reproducible effect:** a controlled interleaving can change focus, routing, clipboard, app state, or freshness and cause an observable failure or recovery opportunity.
- **Hidden evaluator:** actors cannot read success predicates; evaluator checks underlying app/workspace state and actor outcomes programmatically.
- **Causal comparison:** evaluate solo A, solo B, serialized A+B, concurrent A+B, and recovery/coordination variants with the same reset and checks. Compute interaction failure only when relevant solo baselines pass.
- **Topology check:** document whether the GUI processes share one display/session, whether OS actions share one pointer/keyboard, whether app windows/state are shared, whether files are mounted/copied/merged, and whether CLI accesses the same backend.

## V0 scope decision

Retain all three branches. Prioritize one compelling GUI+Human focus competition case and one GUI+CLI visible/backend-state case, then add GUI+GUI if the environment can deterministically schedule independent agents over the same desktop. Include shared-file writes as an auxiliary baseline because ParaGUIBench already studies and reports this failure mode.

Do not force every interaction into a focus-conflict narrative. A task can reveal clipboard conflicts, modal ownership errors, stale screen observations, app-level navigation loss, or divergent GUI/backend state. Organize the taxonomy around these observable mechanisms, and let the task evidence determine which deserve emphasis.

## Continue / adjust conditions

**Continue the benchmark contribution** if at least one end-to-end scenario proves independent solvability, joint solvability, same-session shared GUI resources, causal interference and executable recovery assessment. A second modality branch should show that the design extends beyond a single focus anecdote.

**Adjust the claim** if only one narrow app/session supports same-GUI interaction. Present it as a protocol/pilot benchmark for shared-session computer use and avoid generalizing to all GUI work.

**Reposition the CSV branch** as shared-state consistency evaluation if it has no GUI-specific visible state. It can remain useful as a comparison condition without defining the benchmark’s center.

**Pause a novelty claim** if new citation/artifact review finds a direct same-session multi-actor benchmark or if tasks cannot provide separate goals and joint programmatic checks. Compare the exact topology and evaluation before deciding how much overlap that establishes.

## Suggested paper positioning

> Existing GUI benchmarks and systems cover parallel GUI workers exchanging artifacts across isolated desktops (ParaGUIBench), parallel computer-use subagents on isolated VMs (MACU), hierarchical GUI roles completing one user instruction (PC-Agent and UFO), multi-app workflows by one agent (MMBench-GUI L4), and GUI agents reacting to user messages or human traces (DeskCraft and GUIDE). We study independently goal-directed principals that share a live desktop/application session across GUI+GUI, GUI+CLI, and GUI+Human conditions. We measure each principal’s goal, joint application invariants, cross-actor interference and recovery with programmatic state checks. This claim is limited to the shared-session, multi-actor setting and remains subject to ongoing artifact-level review.

## Final evidence checks before publication

- Re-run the literature search near submission, including ParaGUIBench citations/references and recent GUI agent systems.
- Record the exact display/session/window/action routing for each benchmark condition.
- Publish actor tasks, reset state, scripted schedule/replay, event schema, evaluator predicates and task-level results.
- Show Solo A, Solo B, Serial A+B and Concurrent A+B; report per-principal as well as joint pass rates.
- Report Human Replay provenance and whether the actor used the GUI, CLI, or message channel.
- Cite each baseline by exact topology and evaluator. Avoid treating “multi-agent,” “collaboration,” or “shared state” as equivalent labels.
