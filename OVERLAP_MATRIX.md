# Overlap matrix

**Audit snapshot:** 2026-09-26. “Verified” means checked against the full paper/appendix or public artifact in this audit; “paper-described” means stated by the paper but not rerun; “not found” is bounded to the reviewed evidence. For detailed sources and task examples see [NOVELTY_AUDIT.md](NOVELTY_AUDIT.md).

## Topology and task structure

| Work | Distinct active actors? | Shared resource actually used | Concurrent interaction/conflict | Goal structure | Representative task / evidence | Status |
|---|---|---|---|---|---|---|
| **ParaGUIBench** | Yes: concurrent GUI workers | Shared mounted artifact directory; each worker has a separate desktop/container | Shared files can contend; systematic contested writes/frequency and conflict recovery are not established. No shared screen/focus. | Planner decomposes one top-level task into self-contained subtasks | `Operation-FileOperate-BatchOperationExcel-001.json`; planner/worker and SCD, paper pp. 2–6; `run_QA_pipeline_parallel.py`, `parallel_manager.py` | Shared directory + separate desktop verified. |
| **AgentRoom** | Yes: separate concurrent coding CLI sessions | One live CRDT-backed shared filesystem, with MCP claim/broadcast/status tools | Yes: real concurrent same-line character edits; file claim conflict and semantic merge risk. No GUI/focus. | Common software task; no fixed actor roles, no separate per-actor goal oracle | T4 ledger; Figure 3 same `transfer` line; Appendix D, pp. 23–24; paper pp. 2–4 | Paper-described and paper transcript verified; public code/data artifact not located. |
| **OSWorld-Noisy / ENVS** | No second goal-bearing actor in the evaluated task | One OSWorld desktop/environment | Perturbation or interruption affects the one agent; it is not a second actor writing/controlling the state | One OSWorld task plus injected noise | Three noise tiers / 153 perturbation generators, paper appendix pp. 13–19 | Full-paper boundary verified; individual generators not rerun. |
| **SWE-Touch** | One coding agent plus scripted/synthesized “user” counter-edit | Same coding repository/workspace | Yes: validated code patch is inserted on read/edit trigger, then a user message arrives; not an independently pursuing actor | One SWE repair task; synthetic user edit has no separate task goal | v0.1.2 records; source `runtime/harness.py`; user-edit validation in `docs/data_schema.md` | Artifact and schema verified. |
| **DeskCraft** | One GUI agent plus user simulator | One GUI desktop; simulator communicates by message | Requirements can change during the task, but simulator does not control windows/keyboard or pursue a second state-changing goal | One evolving task from one user | `interactive_kdenlive_requirement_change_001`: horizontal-to-vertical teaser change; task JSON and evaluator | Task JSON, evaluator, and README verified. |
| **WeaveBench** | One agent using several interface tools | One desktop/workspace in one actor’s trajectory | Cross-channel state can go stale, but no independent actor | One long-horizon task requiring GUI and CLI/code operations | `DOC_task_2_pandoc_docx`, Appendix F.1, PDF p. 34 | Paper case + evaluator/runtime source verified; task corpus distributed separately. |
| **CoAgent** | Yes: independent CLI agents | Same live Kubernetes cluster/application state | Yes: interleaved reads/writes create nonserializable state; framework notifies, retries, compensates | Separate operational instructions; each agent can report success while joint state fails | Repair all wrong-image deployments vs create `geo-canary` from current `geo`; paper pp. 1–4; eval pp. 9–12 | Detailed protocol/results paper-described; code not located. |
| **CooperBench** | Yes: distinct feature workers | By default separate workspaces plus messages; common Git server is optional; outputs composed | Patch conflicts/semantic incompatibility at merge, not same live tree by default | Distinct feature goals meant to be independently implementable | `task1655` feature pair 7/10; `flash_10.json`; `coop.py` has `git_enabled=False`; hidden feature suites | Paper and public dataset/source verified. |
| **STALE** | Two parallel worker patches/tasks in experiment framing | Isolated patches/worktrees; combined and evaluated afterward | Yes: newly introduced composition failures, plus controlled message-based recovery; no live concurrent runtime | Paired tasks/patches are tested solo and composed | 417 Django mined pairs; synthetic and real-Django-helper tiers; `real_corrected.jsonl`, `realstale_batch.jsonl` | Paper plus corrected public artifacts verified. |
| **CodeCRDT** | Multiple coding agents | Shared live CRDT editor document | Yes: simultaneous edits can merge at character level but conflict semantically | Collaborative code task, not per-actor task scoring | Six code tasks, 50 runs/mode, paper pp. 1–9 | Paper-described; author repo not located. |

## Outcome coverage

| Work | Each actor independently succeeds? | Joint result / state integrity? | Interference attribution? | Recovery measured? | Primary evaluation form |
|---|---|---|---|---|---|
| ParaGUIBench | Not as separately assigned goal owners | Top-level task success and efficiency | Not a principal outcome | Not separately scored | Rule-based task evaluators + efficiency |
| AgentRoom | No actor-specific task oracle | Shared project quality and abandonment | Behavior/collision evidence, not a held-out causal delta | Protocol adherence/observed behavior; no dedicated recovery benchmark | LLM judge + regex/AST cross-check |
| OSWorld-Noisy | N/A | Original task pass after disturbance | Disturbance effect, not another actor’s effect | Implicit in post-noise task success | Task evaluator / repeated pass rate |
| SWE-Touch | N/A | Original repair passes after workspace edit | Paired vanilla vs counter-edit gap | Adaptation is implicit in task success; not actor-to-actor repair | Tests/task outcome |
| DeskCraft | N/A | Final task artifact/application state | Interactive request effect, not competing actor collateral effect | Later phase completion | Task-specific executable evaluator |
| WeaveBench | N/A | Deliverables and task rubric | No independent-actor delta | Agent’s recovery appears in one trajectory/judgment | Trajectory-aware LLM judge plus checks |
| CoAgent | Instructions are distinct; agents may claim completion | **Yes:** shared state invariants/serializability | **Yes:** contended workloads and uncoordinated control | **Yes:** selective retry and compensating writes | Programmed invariants + serial reference, time/token cost |
| CooperBench | **Yes:** per-feature tasks/tests | **Yes:** composed patch runs both feature suites | Merge/cooperation tax and feature regression | Coordination/message conditions, not GUI recovery | Hidden feature tests + merge analysis; paper also describes LLM conflict resolution |
| STALE | **Yes:** pair only counts when both solo tasks pass | **Yes:** newly introduced failure on composition | **Yes:** composition delta over standalone | **Yes:** precise communication hint tier | Test outcome delta; exact-artifact validation gates |
| CodeCRDT | Not actor-specific | Shared result quality/task completion | Semantic conflicts reported | Not a distinct recovery metric | Task success/quality/time |

## Similarity to the current V0 proposal

| V0 claim or proposed case | Closest overlap | Novelty assessment |
|---|---|---|
| “Multiple independent agents share writable state and interfere” | CoAgent, AgentRoom, CooperBench, STALE | **Occupied at the general level.** Narrow by resource topology, modality, or a new measurable failure mechanism. |
| GUI agents share artifacts | ParaGUIBench | **Occupied.** Separate desktops and decomposed task goals are its key boundary. |
| GUI and CLI act on the same task/state | WeaveBench | **Occupied for one actor’s hybrid workflow.** Independent-principal interaction could still distinguish V0. |
| GUI plus user changes requirements mid-task | DeskCraft; SWE-Touch in code workspace | **Occupied as human-in-loop intervention.** Does not establish a second actor controlling the GUI or pursuing an independent goal. |
| OSWorld task under interference/noise | OSWorld-Noisy | **Occupied for one actor under environment perturbations.** Do not label another actor as “noise”; establish its own goal and actions. |
| GUI + CLI shared CSV reads/writes and stale observation | CoAgent (same live state / stale reads), AgentRoom (shared live filesystem), CooperBench/STALE (independent success and combined failure) | **Weak difference unless GUI-app cache/visible state adds a distinct tested mechanism.** A CSV toy alone is not a novelty basis. |
| GUI + Human Replay global window focus competition on same desktop | DeskCraft (simulated user messages), ParaGUIBench (multiple GUI agents but isolated desktops) | **Candidate distinction supported by this audit.** Verify literal one display/input route, independent human goal, cross-actor attribution, and executable recovery outcome. |

## Reading the matrix

“Same workspace” is not a sufficient topology description. Relevant categories are: one live in-place shared state; one shared file service across isolated desktops; isolated changes composed later; one actor switching tools over the same workspace; and one actor facing exogenous disturbance or messages. Separate model sessions do not imply independent task goals. Any next paper or benchmark description should report both dimensions explicitly.
