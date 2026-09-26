# Shared-Workspace Benchmark V0: novelty and artifact audit

**Audit date:** 2026-09-26
**Scope:** literature and public-artifact review only; no benchmark engineering was added in this audit.
**Question:** has prior work benchmarked multiple independently acting principals on the same live desktop, filesystem, or application state, and measured their interaction effects?

## Corrected GUI/Desktop novelty verdict

**No direct collision was found in the audited GUI/Desktop/Computer-Use benchmark literature:** none of the inspected benchmark papers and released artifacts showed multiple independently goal-directed actors concurrently controlling the *same live desktop session* (shared foreground windows, pointer/keyboard route, clipboard and application state) while evaluating each actor’s separate goal, joint completion and cross-actor interference. This finding is bounded to the searches and artifacts listed below; it is not a universal priority claim.

There is substantial **partial overlap within GUI/Computer Use**. ParaGUIBench runs concurrent GUI workers, shares a mounted file system, and even documents concurrent edits to one shared document; however each worker has its own Docker desktop, the planner decomposes one top-level instruction, and the paper scores aggregate task outcomes/efficiency. MACU (Multi-Agent Computer Use) runs parallel GUI CUA subagents on OSWorld and other benchmarks, but each subagent has an isolated VM and receives a manager-decomposed subtask. PC-Agent uses a hierarchy of GUI-oriented agents for one PC task, with the Decision Agent carrying out the interactive action loop. UFO/UFO² uses HostAgent/AppAgent roles on one Windows desktop and delegates application subtasks; UFO³/NebulaBench coordinates heterogeneous devices. MMBench-GUI’s “Task Collaboration” means one actor coordinating across multiple applications, not multiple actors. DeskCraft and GUIDE add human context/action data or user messages without testing two independently goal-directed desktop controllers.

The cross-domain systems CoAgent, AgentRoom, CooperBench and STALE establish important concurrency, shared-state, joint-correctness and recovery methods in Kubernetes/CLI or code-patch settings. They do **not** occupy the GUI benchmark contribution by category. Use them to shape causal controls and evaluator design, not as evidence that the GUI mainline is taken. Similarly, WeaveBench evaluates one actor switching GUI and CLI; it is a cross-modality mechanism neighbor, not a multi-actor GUI collision.

The project should preserve GUI+GUI, GUI+CLI and GUI+Human branches. Shared-file stale reads/writes remain useful auxiliary tasks. The core claim should concern GUI-specific shared interaction resources and a joint evaluator: foreground-window/focus changes, shared pointer and keyboard routing, clipboard, application UI/session state, and visible-vs-underlying app state. Current V0 GUI+Human focus competition is the most promising lead, while the CSV case alone is not sufficient to represent the contribution.

## Evidence conventions and limits

- **Verified** means the paper body/appendix or public artifact was directly inspected in this audit. Repository citations below pin the checked commit where a commit was available.
- **Paper-described** means the authors state the property or report an experiment, but no independently rerun experiment was performed here.
- **Inferred** means the boundary follows from the described protocol or inspected code and is stated as such.
- **Unavailable** means an author artifact or enough evidence to resolve the question was not located. It does not mean no such artifact exists.

PDF page references below are the PDF page numbers. Some papers also print their own pagination. Public source review was read-only. Papers and repositories were not rerun; “reported result” is not an independent reproduction. The previous broad reading of CLI/shared-state work is retained below as cross-domain mechanism precedent, not as evidence that GUI/Digital Desktop novelty is occupied.

## GUI/Desktop search and three-level classification

### Direct collision: none located

The direct-collision test used here requires all of: (a) at least two distinct goal-bearing principals; (b) actions routed through one live graphical desktop/application session; (c) actual shared GUI control or same-session application state, rather than separate VMs with a shared folder; and (d) evaluation of both independent goals and interaction-caused joint failures. No inspected public benchmark satisfied all four. In particular, no inspected task/evaluator explicitly measures simultaneous foreground focus, pointer/keyboard routing, or clipboard contention between two independently tasked principals.

### Partial GUI/Computer-Use overlap

#### Multi-Agent Computer Use (MACU)

**Sources:** [paper, arXiv:2606.01533](https://arxiv.org/abs/2606.01533), especially pp. 1–5 and VM appendix p. 14; [repository pinned at `5b1b8f9`](https://github.com/kohjingyu/multi-agent-computer-use/tree/5b1b8f91dfc5dc66a2f06af4b443b3009a9cd105), especially `run_macu.py`, `utils/macu_runtime.py`, `utils/vm_utils.py`, and `osworld/desktop_env/providers/{vmware,apptainer}/`.

MACU is the clearest broad GUI/Computer-Use multi-agent precedent and must be named in project positioning. A manager dynamically decomposes one user instruction into a DAG; parallel CUA subagents execute ready subtasks in OSWorld, Online-Mind2Web, WebTailBench and Odysseys (paper pp. 1–4). Each CUA subagent runs on an isolated VM (pp. 3–4); appendix p. 14 and repository VM code specify cloning/snapshotting for parallel variants and fresh writable overlays for independent VM sessions. Dependent work can inherit a completed predecessor’s state, but concurrently executing workers do not mutate one shared live VM. The paper evaluates top-level success and efficiency against single-agent baselines, not independently specified principals’ separate objectives or collateral effects. Example Fig. 2 (p. 3): parallel hotel-review and flight-search subtasks are combined into one travel recommendation. **Classification: partial GUI overlap** (multi-agent CUA, parallel GUI execution, coordination and end-task evaluation); **not a same-session multi-actor benchmark**.

#### PC-Agent

**Sources:** [paper, arXiv:2502.14282](https://arxiv.org/abs/2502.14282), §§2.3–3.2 and Appendix; [official repository](https://github.com/X-PLUG/MobileAgent/tree/main/PC-Agent).

PC-Agent defines Manager, Progress, Decision and Reflection agent roles for one complex PC instruction (paper pp. 1–4). The Manager decomposes, Progress handles state/parameter handoff, and the Decision Agent directly produces GUI actions against the current PC environment (§2.3, pp. 3–4). PC-Eval has 25 complex instructions / 79 subtasks across eight applications; success is reported per instruction and per subtask (§3.1, pp. 4–5). It is a multi-agent **framework evaluated on a GUI task benchmark**, not a benchmark of separate simultaneous actors. The tasks decompose one request and the paper does not describe independent competing GUI controllers contending for the same focus/input route. **Classification: partial GUI overlap** in multi-agent orchestration and per-subtask measurement.

#### UFO, UFO² and UFO³ / NebulaBench

**Sources:** [UFO paper, arXiv:2402.07939](https://arxiv.org/abs/2402.07939); [UFO³ paper, arXiv:2511.11332](https://arxiv.org/abs/2511.11332); [repository pinned at `e2a0312`](https://github.com/microsoft/UFO/tree/e2a03126241c696fdaf9a669a271ca3fca6d9916), particularly `ufo/agents/agent/host_agent.py`, `ufo/agents/agent/app_agent.py`, `ufo/agents/states/`, and its session modules.

UFO/UFO² is directly relevant as a GUI agent architecture: a HostAgent delegates application-specific subtasks to AppAgents operating on the same Windows environment. The inspected state machine returns control from a finished AppAgent to HostAgent (`ufo/agents/states/app_agent_state.py`; HostAgent/AppAgent code). This is hierarchical delegation for one user request; the paper/released benchmark evidence does not establish independent, simultaneous actors or measure their mutual interference. UFO³/NebulaBench expands to asynchronous orchestration over heterogeneous devices: 55 cross-device tasks over five machines, with subtask/task success and fault-injection recovery in its paper. It does not establish two actors competing for one desktop session. ParaGUIBench itself names UFO³/NebulaBench as a closest adjacent system (ParaGUI paper p. 2–3). **Classification: partial GUI/Computer-Use overlap** for multi-agent architecture, cross-device coordination, and task/recovery scoring; no same-desktop contention evidence located.

#### ParaGUIBench: relevant GUI collision boundary and real shared-file interference

**Sources:** [paper, arXiv:2607.22689](https://arxiv.org/abs/2607.22689), pp. 1–6, evaluation pp. 7–11 and Appendix A, Table XI; [repository at audited commit `32cf217`](https://github.com/pkgunboat/ParaGUIBench/tree/32cf2172482a45fd4f5f1d6d6d1eac3bb5abef3c), notably `src/stages/run_QA_pipeline_parallel.py` and `src/desktop_env/providers/docker/parallel_manager.py`.

ParaGUIBench is directly in the GUI-agent benchmark family and is a strong partial overlap, not a cross-domain analogy. Its workers execute real screen/mouse/keyboard actions concurrently, each inside its own full Ubuntu Docker desktop. The paper explicitly says separate desktops provide distinct cursor and keyboard focus, so workers cannot disrupt one another’s clicks/keystrokes (paper §III-A, p. 4). A shared directory is mounted for file exchange. Its task taxonomy includes search-and-write tasks where concurrent workers edit the same document: Appendix A reports that this shared-document bottleneck limits parallelism to 1.47 and success rate to 10%; the text says planner region assignment does not reliably keep worker edits disjoint (Appendix A, PDF p. 14 / printed p. 13; see also paper’s conflict discussion pp. 2, 5–6). Thus **real GUI-worker file-edit interference is present**, and must be acknowledged. But the actors are still executing a planner-decomposed single instruction, their desktops/focus are isolated, and evaluation reports top-level task success and efficiency—not two independent user goals or the effect of one actor on another’s window/input/application session.

Representative top-level task files verified in the repository include `Operation-FileOperate-CombinationDocs-015.json` (extract citations from an open document into `references.bib`) and `Operation-FileOperate-BatchOperationExcel-001.json` (aggregate yearly workbook columns). These confirm GUI task operation but do not encode separately goal-directed workers. **Classification: closest benchmark partial overlap** for GUI+GUI concurrency, shared files, contested edits, and aggregate success/efficiency; explicit boundary: independent desktops + one decomposed task.

#### MMBench-GUI “Task Collaboration”

**Sources:** [full paper, arXiv:2507.19478](https://arxiv.org/abs/2507.19478), pp. 12–14; [official repository](https://github.com/open-compass/MMBench-GUI).

The phrase “Task Collaboration” is easy to misread. L4 contains 248 cross-application workflows. The paper defines one agent generating an action sequence across multiple apps and explicitly says the tier extends single-app automation to multi-app collaboration and information transfer (pp. 12–13, §§3.5–3.6). A representative task searches a conference date and creates a calendar event. The evaluator checks final state/SR/EQA, not per-actor state (p. 13). There are not multiple goal-bearing actors. **Classification: partial GUI benchmark terminology/task-composition overlap only**, not multi-actor collaboration.

#### DeskCraft and GUIDE: GUI plus human interaction/behavior

**Sources:** [DeskCraft, arXiv:2606.03103](https://arxiv.org/abs/2606.03103), pp. 1–8 and Appendix H.2 pp. 35–38; [pinned task and code paths](https://github.com/mrwwk/DeskCraft/tree/73985ecdd37e7db02a6ba617bc020161641af43a); [GUIDE, arXiv:2603.25864](https://arxiv.org/abs/2603.25864), full paper; [GUIDE project/dataset](https://guide-bench.github.io/).

DeskCraft is a direct human-in-the-loop **GUI benchmark**, with 152 interactive tasks among 538. Its simulator answers the acting agent, clarifies, changes requirements or interrupts it; the Kdenlive task `interactive_kdenlive_requirement_change_001` shifts a horizontal teaser to 1080×1920 vertical output. The released `task.json`, `README_INTERACTIVE.md`, and evaluator show one GUI agent/environment plus message exchange, not a second controller writing or navigating windows. **Partial overlap** for GUI+Human requirements and final-state evaluation.

GUIDE is an offline benchmark built from 67.5 hours of screen recordings from 120 novice-user demonstrations across ten applications; it tests behavior-state detection, intent prediction and help prediction. The model observes/reasons about a human’s GUI interaction, rather than simultaneously controlling that human’s desktop or pursuing a second desktop task. **Partial overlap** for GUI+Human action traces and independent human intent labels; no co-control/interference test.

#### Other GUI/Computer-Use boundaries

- **OSWorld-Noisy / ENVS** ([arXiv:2606.22948](https://arxiv.org/abs/2606.22948), appendix pp. 13–19): real desktop tasks and interruption/recovery, but one acting agent plus environment noise, not another goal-bearing actor. Partial overlap for controlled GUI disturbance and recovery.
- **OSWorld-Human** ([arXiv:2506.16042](https://arxiv.org/abs/2506.16042), methods pp. 2–4; [artifact repository](https://github.com/WukLab/osworld-human)): human-derived single-action and grouped-action reference trajectories assess CUA efficiency. The reference trajectory is a baseline, not a human concurrently using the same GUI with an agent. Partial overlap for Human Replay traces and human-efficiency controls.
- **WeaveBench** ([arXiv:2606.09426](https://arxiv.org/abs/2606.09426), 38pp including appendices; [repo pinned at `acf203a`](https://github.com/weavebench/WeaveBench/tree/acf203ae24386aa9bcc0da950c533c8c796dc38e)): one actor interleaves GUI+CLI; `DOC_task_2_pandoc_docx` (Appendix F.1, PDF p. 34) has stale GUI document state after CLI XML edits. Partial overlap for GUI+CLI shared application state, not independent GUI and CLI actors.
- **CUA-Universe** ([arXiv:2609.05374](https://arxiv.org/abs/2609.05374), §§3–4, pp. 3–6): one actor uses GUI+CLI on shared app state with stale-view resynchronization; 160-task held-out CUA-Verse. Partial overlap for GUI+CLI, not an independent actor pair.
- **WindowsWorld** ([paper](https://arxiv.org/abs/2604.27776); [artifact](https://github.com/HITsz-TMG/WindowsWorld)): multi-agent framework generates/reviews tasks, but the benchmark executes one GUI agent on professional cross-app workflows. Multi-agent task creation is not runtime actors. Partial conceptual overlap only.
- **UFO³/NebulaBench** above is also cross-device rather than same-session. Multi-device/cross-device wording alone does not establish one shared desktop.
- **OSWorld-Human** provides reference human actions, but execution remains one CUA compared with recorded actions, not two live actors.

### Cross-domain concurrency/mechanism neighbors

These papers inform experiment design and causal evaluators; their results should not be used to say that a GUI/Desktop benchmark contribution is already occupied.

- **CoAgent** ([arXiv:2606.15376](https://arxiv.org/abs/2606.15376), pp. 1–4, 9–12): independent CLI agents contend on a live Kubernetes state; tests joint invariants/serializability and recovery. Strong mechanism precedent; not a GUI benchmark.
- **AgentRoom** ([arXiv:2608.23740](https://arxiv.org/abs/2608.23740), pp. 1–10, appendices pp. 13–26): concurrent coding CLIs edit one live CRDT filesystem, with one shared project goal and shared-project scoring. Strong live shared-file precedent; not a GUI benchmark.
- **CooperBench** ([arXiv:2601.13295](https://arxiv.org/abs/2601.13295), pp. 1–7 + appendices; [pinned repo](https://github.com/cooperbench/CooperBench/tree/63b9d44d9f39a02fccf5bf0052db48a917a011fd)): separate feature agents/workspaces and post-hoc composition tests. Useful independent-vs-joint test design; not live shared desktop.
- **STALE** ([arXiv:2609.25396](https://arxiv.org/abs/2609.25396), six pp. including Appendix C; [pinned repo](https://github.com/illinoisdata/STALE-bench/tree/f7bc831e4eff08b9652acd893553824636ae3985)): patches pass solo then fail composition; correction controls require both solo tasks to pass and use union tests. Useful causal attribution/recovery design; not GUI runtime topology.
- **SWE-Touch** ([arXiv:2608.02499](https://arxiv.org/abs/2608.02499); [pinned repo](https://github.com/Trae1ounG/SWE-Touch/tree/4bd121b4a058c117fbef05e9247d4a55ae5f25d7)): injected user counter-edits affect one coding agent’s repository. Useful same-workspace update precedent; no GUI agent or independent second task.
- **CodeCRDT** ([arXiv:2510.18893](https://arxiv.org/abs/2510.18893), pp. 1–9): collaborative coding/editor conflict mechanism; not a GUI computer-use benchmark.

## Core audit: closest overlaps

### ParaGUIBench — GUI workers, shared files, separate desktops

**Sources:** [paper, arXiv:2607.22689](https://arxiv.org/abs/2607.22689), especially pp. 1–6 and evaluation pp. 7–11; [repository at audited commit `32cf217`](https://github.com/pkgunboat/ParaGUIBench/tree/32cf2172482a45fd4f5f1d6d6d1eac3bb5abef3c).

- **Actors and goals — verified:** a planner decomposes one user task into self-contained worker subtasks. It dispatches up to five GUI workers concurrently (paper pp. 2, 5–6). Workers do not get planner history or peer state. This is genuine concurrency between worker processes, but not separately specified independent user goals; it is one goal divided by a planner.
- **Resource topology — verified in paper and source:** each worker has an isolated Docker desktop/container, with a mounted common file exchange directory at `/home/user/shared` (paper pp. 2, 5–6; `src/stages/run_QA_pipeline_parallel.py`, especially shared mount setup and `ThreadPoolExecutor`; `src/desktop_env/providers/docker/parallel_manager.py`). Therefore workers do not share a screen, mouse, keyboard focus, or foreground window. They do share a filesystem path for artifacts.
- **Interference — verified for shared-file edits:** the paper explicitly reports the search-and-write shared-document bottleneck, with parallelism falling to 1.47 and success rate to 10%; it says workers’ edits are not reliably kept within disjoint regions (Appendix A, Table XI, PDF p. 14 / printed p. 13). The infrastructure/code confirms each worker’s separate desktop and shared mounted directory. This establishes real concurrent file-edit interference. It does not establish simultaneous GUI focus contention, independent actor goals, or per-actor collateral/recovery metrics.
- **Tasks — verified:** 233 GUI tasks in six categories, including information retrieval, file operations, web navigation, and shopping/search (paper pp. 3–5; task files). Representative released instances include `InformationRetrieval-FileSearch-Readonly-001.json` (identify the paper associated with a diagram in a shared folder), `Operation-FileOperate-BatchOperationExcel-001.json` (aggregate each yearly column across Mixue shop workbooks), `Operation-FileOperate-CombinationDocs-015.json` (extract citations from an open document into `references.bib`), and `Operation-WebOperate-WebNavigate-001.json` (visit/bookmark Accuweather monthly weather and an official AQI page). The planner can decompose at runtime; these task files are top-level tasks, not fixed independent actor goals.
- **Evaluation — verified:** rule-based task outcome evaluators plus step/parallelism/efficiency reporting (paper pp. 6–9; `src/paraguibench/runtime/evaluators.py` and `src/paraguibench/evaluation/`). The paper does not report per-worker independent goal success, causal interference attributable to another worker, state integrity under concurrent writes, or recovery as separate outcomes.
- **Artifact caveat:** repository state is newer/evolving than the paper; README/status material includes tasks marked ready but not live-validated. We do not conflate the paper’s reported benchmark experiments with every current repository task’s release readiness.
- **Overlap judgment:** strong overlap for parallel GUI execution and shared file artifacts; not the same desktop or independent goals. This rules out novelty claims based on “multiple GUI agents share files” or coordination efficiency alone.

### AgentRoom — live shared CRDT files, concurrent coding sessions

**Sources:** [full paper including appendices, arXiv:2608.23740](https://arxiv.org/abs/2608.23740), pp. 1–10 and appendices pp. 13–26; paper project references AgentRoom. An author GitHub repository/task bundle was **not located** by paper references and title/arXiv searches during this audit; no claim is made that one does not exist.

- **Actors and goals — verified from paper:** two or three separate coding CLI agent sessions are launched concurrently (pp. 1–3, 5–7). They work on the same broad project specification without fixed role assignment or orchestrated handoffs (p. 2 and Appendix D, pp. 23–24). Agents are independent sessions, but success is measured for the common project, not as two separate user tasks with actor-specific success criteria.
- **Resource topology — verified from paper:** one live shared CRDT filesystem based on Yrs/Yjs, plus MCP tools for file claims, release, broadcasts, room state, and reads (pp. 2–3). It is a shared coding workspace, not a graphical desktop; GUI focus and OS input are not involved.
- **Interaction — verified example:** Figure 3 (p. 3) traces one T4 ×2 run: both agents concurrently insert into the same `transfer` function line, with both insertions preserved at character level. The paper explains that a syntactically merged edit can still violate intent, compilation, or tests (pp. 3–4). Claims are advisory at the prompt layer; CRDT preserves unclaimed edits rather than blocking them (pp. 3–4).
- **Tasks — verified:** T1 JWT authentication across six files; T2 marketplace API across at least ten files; T3 collaborative e-commerce; T4 a double-entry multi-currency ledger with hash-chained audit/reconciliation/fraud requirements across at least fifteen files; T5 algorithmic trading platform (paper p. 4 and Appendix D pp. 23–24). Appendix C pp. 21–23 contains a run transcript. This is real concurrent same-workspace editing, but actor objectives are a shared software build.
- **Evaluation and recovery — verified:** Solo, Shared-only, and Parallel-merge baselines (p. 4); measures include abandonment, variance, and shared project quality (pp. 4–8). Quality primarily uses an LLM judge, cross-checked with regex and AST signals; the authors explicitly say they do not claim execution-verified correctness and note small samples/reproducibility limits (pp. 9–10, Appendix E pp. 24–26). File claim adherence and protocol behavior are analyzed; recovery is not a dedicated held-out task-success/state-integrity metric. A claim conflict can lead an agent to choose another file, but this differs from evaluating post-conflict recovery on independently assigned goals.
- **Overlap judgment:** very strong overlap for real-time shared-file mutation and concurrent edits; weaker overlap for actor independence of objectives, benchmark-grade bilateral correctness/recovery, and no overlap for shared GUI focus. V0 must not claim first “live shared workspace,” “multi-agent concurrent file edits,” or “shared-state agent benchmark.”

## Other directly relevant work

### CoAgent — independent CLI goals on one live Kubernetes state

**Sources:** [CoAgent: Concurrency Control for Multi-Agent Systems, arXiv:2606.15376](https://arxiv.org/abs/2606.15376), especially pp. 1–4 and evaluation pp. 9–12. A linked author implementation was not located through paper and exact-title/arXiv repository searches; code availability is **unresolved**.

- **Actors/goals/topology — paper-described:** separate CLI agents have independent instructions and operate concurrently against the same live Kubernetes cluster/state (pp. 1–4). Figure 1 / §2.2 gives a concrete two-agent trace: A must find and repair every deployment using the wrong image; B reads the `geo` image and creates a zero-replica `geo-canary` from it. A’s earlier inventory misses B’s newly created canary; B’s earlier read preserves the bad image. Both report completing their own objectives, but the joint cluster violates the required relationship and is not equivalent to a valid serial execution (pp. 1–3). This is direct evidence that the broad shared-live-state question has prior work.
- **Evaluation — paper-described:** ten contended workloads, 10 trials per protocol/cell (experimental setup/results pp. 9–11); correctness is task invariants/serializability, with wall-clock speed and token cost, versus serial, uncoordinated, 2PL-saga, OCC-saga, and CoAgent. Notifications trigger selective re-execution; external writes can be reversed/reordered via recorded compensations (pp. 3–8). The paper reports that its protocol retains correctness close to serial with parallel speed gains (pp. 1, 10–11). These are reported results, not reproduced here.
- **Boundary:** direct prior art for distinct CLI goals, common live mutable application state, stale reads/writes, joint correctness, and recovery. It does not test GUI display/focus contention, a human as an actor, or application-level visual state. It makes the V0 CSV stale-observation case conceptually close unless that case measures an explicit GUI-visible consistency mechanism that CoAgent’s CLI/Kubernetes environment does not.

### CooperBench — separately solvable feature goals and composed patches

**Sources:** [CooperBench, arXiv:2601.13295](https://arxiv.org/abs/2601.13295), pp. 1–7 and appendices; [repository at audited commit `63b9d44`](https://github.com/cooperbench/CooperBench/tree/63b9d44d9f39a02fccf5bf0052db48a917a011fd), especially `dataset/README.md`, `src/cooperbench/runner/coop.py`, `src/cooperbench/eval/evaluate.py`, and `src/cooperbench/eval/sandbox.py`.

- **Actors/goals — verified:** pairs receive distinct feature specifications from the same PR/task set; features are intended to be independently implementable. The runner launches separate agent environments. Messaging is enabled by default; a shared Git server is an optional mode (`git_enabled=False` default in `src/cooperbench/runner/coop.py`). Thus do not call the default condition one shared live working tree. It is isolated worker workspaces with communication and optionally a common Git remote, followed by patch composition.
- **Tasks — verified:** dataset README reports 199 features, 52 PR task sets and 652 evaluated feature pairs in the paper snapshot. Example repo task directory `dottxt_ai_outlines_task/task1655` contains feature specs; `flash_10.json` identifies a pair (feature 7 credit-card regex type; feature 10 SHA-256 hash string type). Dataset documents that many gold pairs have textual conflict and supplies a resolved `combined.patch` oracle. Version differences between paper and mutable dataset are possible.
- **Evaluation — verified from paper/source:** each feature has its own tests; the resulting patches are composed and both feature suites are checked; merge conflict and cooperation cost are measured (paper pp. 3–7; `src/cooperbench/eval/evaluate.py`). Paper describes resolving trivial merge conflicts with an LLM judge to measure semantic compatibility (pp. 4–5). The data’s gold composition checks must be distinguished from agent-run interaction outcomes.
- **Boundary:** direct prior art for separate actor objectives, standalone solvability, and joint compatibility. It studies software feature integration through isolated clones/patches, not one live desktop or online shared application state; focus and interaction-time read/write anomalies are out of scope.

### STALE — composition-caused failures, careful controls, and recovery

**Sources:** [paper, arXiv:2609.25396](https://arxiv.org/abs/2609.25396), six-page paper including Appendix C; [repository at audited commit `f7bc831`](https://github.com/illinoisdata/STALE-bench/tree/f7bc831e4eff08b9652acd893553824636ae3985), particularly `README.md`, `instances/django.jsonl`, `results/real_corrected.jsonl`, `results/realstale_batch.jsonl`, and `pdbench/harness/run_pair.py`.

- **Evaluation design — verified:** run each patch/task alone and in combination on the same tests; count only failures newly caused by composition and only pairs where both solo tasks pass (paper pp. 1–3; README correction notes). This is a strong design precedent for V0’s independent solvability plus interaction delta.
- **Task tiers — verified:** synthetic controlled interface changes; mined PR pairs; constructed real-Django-helper cases anchored in real code (paper pp. 2–5, Appendix C; repository instances and results). The 417 mined Django pairs yielded one run with any corrected `delta_blind > 0` and zero both-solved-and-break events over 834 runs. By contrast, the constructed 12-helper tier reports interference in 105/108 blind runs, with a precise one-message hint recovering 89/108. The authors explicitly warn the constructed rate does not estimate practical prevalence (paper pp. 4–5; `README.md`).
- **Methodological result:** the README marks prior `real_delta_blind.jsonl` as uncorrected and artifact-inflated. It explains that agent test edits and differing solo/union grading created false positives; corrected grading discards agent test edits and grades each condition on the union test set. This is a valuable evaluator lesson: task-only independent checks can miss collateral failures, while inconsistent test sets can create spurious interaction failures.
- **Boundary:** despite its name and parallel-agent framing, the validated outcomes are generated and composed as code patches, not through two principals concurrently operating one running desktop/filesystem. It has no live display, focus, or real-time shared app-state test. Strong overlap in causal attribution and recovery methodology, not runtime topology.

### CodeCRDT — shared editor collaboration, system rather than broad benchmark

**Source:** [CodeCRDT, arXiv:2510.18893](https://arxiv.org/abs/2510.18893), full 11-page paper including Appendix A. Paper pp. 1–9 describe multiple agents editing one shared CRDT/Monaco code document, six code tasks, 50 runs per mode, semantic conflicts despite character-level merge, and quality/time/task metrics. It is a collaborative editing system study, not a broad shared-desktop task benchmark. An author repository was not located in the audit. AgentRoom cites it as a related CRDT coding system (AgentRoom p. 9).

## Requested neighbors and boundary checks

### OSWorld-Noisy / ENVS

**Sources:** [ENVS paper, arXiv:2606.22948](https://arxiv.org/abs/2606.22948), full paper and appendix pp. 1–19; [repository at audited commit `d397b0e`](https://github.com/ArtysicistZ/ENVS/tree/d397b0e296dbe89045b4a2c331fd5bc83d2c2a13).

Paper pp. 1–6 frames recoverable, stochastic environmental perturbations to OSWorld’s single-agent execution; appendix pp. 13–19 enumerates three tiers and 153 perturbation generators. The protocol evaluates whether the task agent can recover/pass under noise (including repeated trials/pass-at-k), not whether another principal pursues a separate goal and mutates shared state. The title’s “Noisy” conditions therefore do not establish multi-actor contention. This distinction is **verified at paper level**; not every generator was individually rerun.

### SWE-Touch

**Sources:** [paper, arXiv:2608.02499](https://arxiv.org/abs/2608.02499), full paper and appendix; [repository at audited commit `4bd121b`](https://github.com/Trae1ounG/SWE-Touch/tree/4bd121b4a058c117fbef05e9247d4a55ae5f25d7), especially `README.md`, `docs/data_schema.md`, `harbor/src/harbor/swe_touch/runtime/harness.py`, `runtime/records.py`, and `data/v0.1.2/*.jsonl`.

SWE-Touch inserts a validated counter-edit into the same coding agent’s repository when it reads/edits a critical region, then supplies a `role=user` message (README; `runtime/harness.py` applies the patch; the record schema fixes trigger and message). The patch is checked as a counter-edit: it fails alone, and user-edit plus reference fix still fails. Release v0.1.2 has 200 Verified, 25 Pro, 25 DeepSWE records; 242 validated edits and eight message-only fallbacks (README). It is a strong precedent for another party changing the workspace and stale-state robustness, but the “user” does not run an independent task or issue concurrent GUI/CLI actions. Evaluation compares vanilla and counter-edit task success; it is not bilateral co-task completion.

### DeskCraft

**Sources:** [paper, arXiv:2606.03103](https://arxiv.org/abs/2606.03103), full 42-page paper and appendices; [repository at audited commit `73985ec`](https://github.com/mrwwk/DeskCraft/tree/73985ecdd37e7db02a6ba617bc020161641af43a), especially `README_INTERACTIVE.md`, `evaluation_examples/examples_per_task/kdenlive/INTERACTIVE_kdenlive_interactive_kdenlive_requirement_change_001./task.json`, its `evaluator.py`, and `desktop_env/evaluators/metrics/interactive.py`.

DeskCraft contains 538 desktop tasks (386 standard, 152 interactive; paper pp. 1–3, 10–12). Interactive tasks use a simulator to answer the one acting GUI agent’s questions, clarify, change requirements, or interrupt (paper pp. 5–8, Appendix H.2 pp. 35–38). The concrete `interactive_kdenlive_requirement_change_001` first asks for a horizontal teaser, then changes the request to 1080×1920 MP4 and a project save (task JSON); the evaluator checks rendered codec/resolution, project XML, and title text. `README_INTERACTIVE.md` describes a single agent/environment plus user simulator and message injection; the simulator is not a second GUI controller or independently tasked actor. This work occupies human-in-the-loop GUI changes and interruptions, but not competing actor focus or separately scored human/agent tasks.

### WeaveBench

**Sources:** [paper, arXiv:2606.09426](https://arxiv.org/abs/2606.09426), 38 pages including appendices; [repository at audited commit `acf203a`](https://github.com/weavebench/WeaveBench/tree/acf203ae24386aa9bcc0da950c533c8c796dc38e), particularly `weavebench/eval/orchestrator.py`, `weavebench/utils/task_parser.py`, `weavebench/eval/agent_judge/`, `examples/fixtures/`, and task package/download scripts.

114 long-horizon tasks expose GUI and CLI/code tools within **one actor’s single trajectory** (paper pp. 1–7, Appendix A/B). Appendix F.1 (PDF p. 34) includes `DOC_task_2_pandoc_docx`, in which CLI XML changes and a GUI application’s stale cached state cause a cross-channel desynchronization. That is a within-agent UI/CLI consistency issue, not an independent second actor. The main score is a trajectory-aware agentic judge (pp. 6–8), with task-local checks/fixtures also available; it is not a bilateral shared-workspace evaluator. This work occupies hybrid GUI+CLI tool use and stale cross-interface state awareness.

### CUA-Universe — live shared GUI/CLI application state, one evaluated actor

**Source:** [paper, arXiv:2609.05374](https://arxiv.org/abs/2609.05374), especially §§3–4, pp. 3–6.

CUA-Universe exposes real desktop applications through both GUI and application-specific CLI over shared project state. Its CUA-Verse held-out set contains 160 GUI+CLI tasks across eight desktop apps, with each agent coordinating two modalities in one trajectory (paper §§3.2–4.1, pp. 3–5). Application adapters resynchronize stale GUI views after external CLI edits (§3.2, pp. 3–4). During data construction, parallel exploration agents target different facets of an app, but attempts are made from fresh environment instances; these are data-generation runs, not separately goal-graded concurrent actors sharing one live desktop (§§3.3–3.4, pp. 4–5). Evaluation scores outcomes with a VLM judge and reports efficiency (§4.1, pp. 5–6). **Classification: partial GUI+CLI overlap** for live shared app state, modality shifts, and stale-view handling; no independent GUI and CLI principals or same-session actor interference test.

**Unavailable / not independently verified:** AgentRoom and CoAgent source/data repositories were not located; no author code claims are made. The complete ParaGUIBench mutable repository was inspected but no paper experiment rerun was done. The WeaveBench main task corpus is downloaded by its tooling rather than all task markdown living in the source checkout; paper appendix and fixtures/code were inspected. None of these papers’ model results were independently reproduced.

## Search and artifact coverage

The audit began with the user-prioritized papers, examined ParaGUIBench’s related-work and reference trail (including UFO³/NebulaBench, Flash-Searcher, PC-Agent and multi-agent CUA), and followed relevant citation chains and keywords. Search terms included multi-agent computer use, shared live desktop, shared screen, same desktop session, focus/input contention, clipboard conflict, multi-user GUI automation, human-agent co-control, and shared GUI/CLI application state. Full accessible papers and appendices for ParaGUIBench, MACU, PC-Agent, MMBench-GUI, DeskCraft, GUIDE, CUA-Universe and the other named neighbors were read or checked at the cited methods/task sections. Public code/task/evaluator artifacts were inspected where available. This is a bounded audit of public literature and artifacts as of the snapshot date.

## Contribution map after boundary correction

### Direct collision

None found under the four-part direct-collision test above. This does **not** mean the GUI area is empty: multiple partial GUI/Computer-Use precedents exist, especially ParaGUIBench, MACU, PC-Agent, UFO/UFO³, DeskCraft, and MMBench-GUI.

### Partial GUI/Computer-Use overlap

1. Parallel GUI workers, shared file exchange, actual same-document write interference and aggregate task/efficiency scoring: **ParaGUIBench**.
2. Parallel GUI CUA subagents and end-task gains on computer-use benchmarks, isolated VM per actor: **MACU**.
3. Hierarchical GUI-oriented agents decomposing one PC task and scoring task/subtasks: **PC-Agent**; **UFO/UFO²**.
4. Cross-device multi-agent GUI/API task orchestration and fault recovery: **UFO³/NebulaBench**.
5. One actor’s cross-app collaboration and state handoff: **MMBench-GUI L4**.
6. GUI+Human instruction changes or observations of real human workflows: **DeskCraft**, **GUIDE**.
7. One agent’s GUI response to environmental interruption: **OSWorld-Noisy/ENVS**.
8. One actor’s GUI+CLI hybrid work and stale cross-interface view: **WeaveBench, CUA-Universe**.

### Cross-domain mechanism neighbors

**CoAgent, AgentRoom, CooperBench, STALE, SWE-Touch and CodeCRDT** occupy or explore concurrency mechanisms, shared state, composition correctness or stale updates in CLI/software settings. They should shape controls, event attribution, hidden-state evaluators and independent/joint-success design; they do not establish that multiple independent actors have already been benchmarked on one shared live GUI desktop.

### Evidence-supported candidate distinction

The reviewed work separates the relevant ingredients: live shared state exists in CLI/shared-file work; GUI parallelism uses separate desktops; GUI human interaction is a simulated conversation with one GUI actor; GUI+CLI cross-state work is one actor. A controlled benchmark combining **separately goal-directed principals + one live graphical desktop/input focus + joint executable state checks + causal interference/recovery measurement** remains a plausible intersection not found in these artifacts. State it as “we did not find this combination in the audited work” until a broader search and primary-artifact reproduction establish otherwise.

## Decision

The GUI/Digital Desktop novelty hypothesis remains viable, with **partial overlap rather than no prior work**. Preserve the three experiment branches: (1) GUI+GUI, distinguishing independent goal owners from planner-delegated workers; (2) GUI+CLI, distinguishing separate actors sharing visible/backend application state from one agent choosing between tools; and (3) GUI+Human, distinguishing independent human goals/actions from a conversational simulator or offline human trace. Shared files are useful controls and secondary conflict tasks.

The main benchmark contribution should test GUI-specific interaction resources (window focus, foreground app, pointer/keyboard route, clipboard, dialog/modal ownership and visible application/session state) and jointly grade each actor plus global invariants. Compare same-session runs with independent desktops/shared-directory runs and serialized same-session runs. Keep shared-file conflict in scope as a task family, but do not let it alone stand in for shared GUI control.
