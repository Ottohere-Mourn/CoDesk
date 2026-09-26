# Shared-Workspace Benchmark V0: novelty and artifact audit

**Audit date:** 2026-09-26
**Scope:** literature and public-artifact review only; no benchmark engineering was added in this audit.
**Question:** has prior work benchmarked multiple independently acting principals on the same live desktop, filesystem, or application state, and measured their interaction effects?

## Verdict

**Yes, the broad question is already occupied.** CoAgent directly evaluates independently assigned CLI agents concurrently changing one live Kubernetes cluster, then measures joint state correctness/serializability and recovery. CooperBench evaluates independently specified software features and whether separately successful agent patches remain jointly correct. AgentRoom runs independent coding-agent sessions concurrently editing one live CRDT-backed shared filesystem. STALE tests whether individually passing changes break when composed and whether communication repairs the failure. These works make “first benchmark of multiple independent agents sharing mutable state and affecting each other” untenable.

The narrower claim that remains plausible in this bounded audit is **independent principals sharing one live graphical desktop’s global focus, foreground window, pointer, and keyboard input route**, with per-principal goals and executable evaluation of collateral effects and recovery. The reviewed GUI neighbors do not appear to instantiate that combination: ParaGUIBench isolates workers in separate desktop instances; DeskCraft simulates a user who sends instructions to one GUI agent; OSWorld-Noisy injects environment disturbances into one agent’s task. This is an evidence-bounded candidate gap, not a priority claim. A second possible angle is a real person’s recorded actions as an independently intended actor on that same desktop; current Human Replay scripts must encode an actor’s own goal and actual UI actions, rather than serving as scheduled noise.

The current V0 CSV case by itself is weakly positioned. Shared-file stale reads and writes are already close to CoAgent, AgentRoom, CooperBench, and STALE. The focus-competition case is the stronger potential differentiator, provided it genuinely uses one display/input target and tests both principals’ independent goals, joint final state, misdirected actions, and recovery.

## Evidence conventions and limits

- **Verified** means the paper body/appendix or public artifact was directly inspected in this audit. Repository citations below pin the checked commit where a commit was available.
- **Paper-described** means the authors state the property or report an experiment, but no independently rerun experiment was performed here.
- **Inferred** means the boundary follows from the described protocol or inspected code and is stated as such.
- **Unavailable** means an author artifact or enough evidence to resolve the question was not located. It does not mean no such artifact exists.

PDF page references below are the PDF page numbers. Some papers also print their own pagination. Public source review was read-only. Papers and repositories were not rerun; “reported result” is not an independent reproduction.

## Core audit: closest overlaps

### ParaGUIBench — GUI workers, shared files, separate desktops

**Sources:** [paper, arXiv:2607.22689](https://arxiv.org/abs/2607.22689), especially pp. 1–6 and evaluation pp. 7–11; [repository at audited commit `32cf217`](https://github.com/pkgunboat/ParaGUIBench/tree/32cf2172482a45fd4f5f1d6d6d1eac3bb5abef3c).

- **Actors and goals — verified:** a planner decomposes one user task into self-contained worker subtasks. It dispatches up to five GUI workers concurrently (paper pp. 2, 5–6). Workers do not get planner history or peer state. This is genuine concurrency between worker processes, but not separately specified independent user goals; it is one goal divided by a planner.
- **Resource topology — verified in paper and source:** each worker has an isolated Docker desktop/container, with a mounted common file exchange directory at `/home/user/shared` (paper pp. 2, 5–6; `src/stages/run_QA_pipeline_parallel.py`, especially shared mount setup and `ThreadPoolExecutor`; `src/desktop_env/providers/docker/parallel_manager.py`). Therefore workers do not share a screen, mouse, keyboard focus, or foreground window. They do share a filesystem path for artifacts.
- **Interference — partially verified:** the paper explicitly notes possible contention over persistent shared artifacts and uses planner assignment/SCD to reduce it (pp. 2, 5–6). Inspected code establishes a shared directory and parallel scheduling. The inspected tasks and reported metrics do not establish a systematic benchmark of simultaneous conflicting writes, stale application observations, or recovery from such conflicts. Treat actual contested-write prevalence as **not established**, not as absent.
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

## Search and artifact coverage

The audit began with the six user-prioritized lines and followed their related-work/citation trails to CoAgent, CooperBench, STALE, and CodeCRDT. Keyword/title searches included shared live state, shared workspace, parallel agents, stale reads/writes, semantic merge, multi-agent computer use, human-in-loop desktop tasks, CRDT editing, and interference. Further boundary checks covered OSWorld/ENVS, SWE-Touch, DeskCraft, and WeaveBench. Full accessible PDFs and appendices for the named papers above were downloaded and read/targeted-searched. Public task schemas/examples/evaluator or runner source were inspected for ParaGUIBench, AgentRoom’s paper appendix/transcript, SWE-Touch, DeskCraft, WeaveBench, CooperBench, and STALE where available.

**Unavailable / not independently verified:** AgentRoom and CoAgent source/data repositories were not located; no author code claims are made. The complete ParaGUIBench mutable repository was inspected but no paper experiment rerun was done. The WeaveBench main task corpus is downloaded by its tooling rather than all task markdown living in the source checkout; paper appendix and fixtures/code were inspected. None of these papers’ model results were independently reproduced.

## Contribution map

### Already occupied

1. Multi-agent execution with shared writable application state, conflict/interference and consistency control: **CoAgent**.
2. Independent per-agent software goals with joint integration/compatibility scoring: **CooperBench**; composition-attributable failure and communication recovery: **STALE**.
3. Concurrent edits to a real-time shared CRDT file system and file-level coordination: **AgentRoom**; collaborative code editing behavior: **CodeCRDT**.
4. Parallel GUI actors with shared file exchange and efficiency metrics: **ParaGUIBench**.
5. One desktop GUI agent reacting to simulated user requirement changes and interruptions: **DeskCraft**.
6. One coding agent adapting to human-style code edits to its workspace: **SWE-Touch**.
7. GUI+CLI work within one agent and cross-channel stale views: **WeaveBench**.
8. One agent’s recovery under environmental disturbance: **OSWorld-Noisy/ENVS**.

### Evidence-supported candidate distinction

The reviewed work separates the relevant ingredients: live shared state exists in CLI/shared-file work; GUI parallelism uses separate desktops; GUI human interaction is a simulated conversation with one GUI actor; GUI+CLI cross-state work is one actor. A controlled benchmark combining **separately goal-directed principals + one live graphical desktop/input focus + joint executable state checks + causal interference/recovery measurement** remains a plausible intersection not found in these artifacts. State it as “we did not find this combination in the audited work” until a broader search and primary-artifact reproduction establish otherwise.

## Decision

Continue only if a real application scenario can make each actor’s goal independently solvable, both goals jointly satisfiable, and an interleaving produce a deterministic observable GUI/focus or state failure with an executable oracle. Make the single-display global focus/input route a first-class variable and compare it to separate-desktop and serialized controls. Include actor-specific success, joint invariants, collateral regressions, recovery, and trace provenance. If the proposed tasks reduce to CSV/filesystem stale-write cases, reposition toward an application-specific concurrency-control benchmark or stop calling it a GUI novelty contribution; those cases overlap the CLI/shared-workspace lines too directly.
