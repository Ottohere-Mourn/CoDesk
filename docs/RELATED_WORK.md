# CoDesk Related Work (Historical Audit Snapshot)

CoDesk is the current benchmark name; the audit below was produced under the Shared-Workspace prototype name and is retained as a dated evidence snapshot.

Audit snapshot: 2026-09-26. The scope is Multi-Actor Computer Use: separate goal-bearing principals sharing a live desktop/application session. Detailed per-work evidence, page numbers, tasks and artifact paths are in [NOVELTY_AUDIT.md](archive/design/NOVELTY_AUDIT.md); the three-level classification is in [OVERLAP_MATRIX.md](archive/design/OVERLAP_MATRIX.md).

## Direct collision

None located in the reviewed GUI/Desktop/Computer-Use papers and public artifacts. The direct-collision test requires distinct actors with separate goals, one live desktop session/resource route, and per-actor plus joint interaction evaluation. This is bounded to the audit’s search and is not a universal “first” claim.

## Partial GUI / Computer-Use overlap

| Work | Evidence-based scope | Difference from this project |
|---|---|---|
| [ParaGUIBench](https://arxiv.org/abs/2607.22689) | Parallel GUI workers, shared mounted directory, aggregate success/efficiency; Appendix A reports same-document editing bottleneck (P=1.47, SR=10%). | Separate Docker desktops and focus; one planner-decomposed instruction rather than independent actor goals. |
| [Multi-Agent Computer Use (MACU)](https://arxiv.org/abs/2606.01533) | Parallel screenshot-driven CUA subagents evaluated on OSWorld and web tasks. | Each actor has isolated VM; manager decomposes one user instruction into a task DAG. |
| [PC-Agent](https://arxiv.org/abs/2502.14282), [UFO/UFO²](https://arxiv.org/abs/2402.07939) | Hierarchical GUI agent roles solve complex PC workflows; UFO roles operate against a desktop. | Delegated roles in one workflow; no evaluated competition between independent goals. |
| [UFO³ / NebulaBench](https://arxiv.org/abs/2511.11332) | Asynchronous cross-device workflows with task success and fault recovery. | Distributed device endpoints, not two actors sharing one desktop session. |
| [MMBench-GUI](https://arxiv.org/abs/2507.19478) | L4 “Task Collaboration” covers one actor coordinating across several applications. | “Collaboration” is inter-app workflow, not multiple active actors. |
| [DeskCraft](https://arxiv.org/abs/2606.03103) | One GUI agent receives clarification, interruption and requirement-change messages from a user simulator. | Simulator does not control GUI or pursue a separately evaluated desktop goal. |
| [GUIDE](https://arxiv.org/abs/2603.25864) | Offline model evaluation over human GUI recordings and intent/help labels. | No concurrent co-control or interaction-caused task outcomes. |
| [OSWorld-Noisy / ENVS](https://arxiv.org/abs/2606.22948) | Single GUI agent task under controlled environment disturbances and recovery. | Noise is not a second principal with its own task. |
| [WeaveBench](https://arxiv.org/abs/2606.09426) | One actor interleaves GUI and CLI and can encounter stale cross-channel views. | No second independent actor. |
| [CUA-Universe](https://arxiv.org/abs/2609.05374) | One actor uses GUI+CLI over shared application state; adapters resynchronize stale GUI views after CLI edits; 160 held-out tasks. | Same-actor hybrid interface, not independent GUI and CLI principals. |
| [OSWorld-Human](https://arxiv.org/abs/2506.16042) | Human reference trajectories provide action/efficiency baselines for desktop tasks. | Reference traces are not a human concurrently acting with a GUI agent. |

## Cross-domain mechanism neighbors

| Work | Methodological relevance | Domain boundary |
|---|---|---|
| [CoAgent](https://arxiv.org/abs/2606.15376) | Independent CLI goals on one live Kubernetes state; serializability and repair. | CLI/AIOps, no GUI benchmark. |
| [AgentRoom](https://arxiv.org/abs/2608.23740) | Concurrent coding sessions edit one shared CRDT filesystem. | Coding CLI/shared files, not desktop GUI; common project objective. |
| [CooperBench](https://arxiv.org/abs/2601.13295) | Separate feature goals individually tested and jointly composed. | Isolated coding workspaces/patch merge, no live desktop. |
| [STALE](https://arxiv.org/abs/2609.25396) | Solo-valid task pairs, composition-induced failure delta, communication recovery. | Offline software patch composition. |
| [SWE-Touch](https://arxiv.org/abs/2608.02499) | Injected user counter-edits test one coding agent’s workspace freshness. | Code workspace; no second GUI/CLI actor goal. |
| [CodeCRDT](https://arxiv.org/abs/2510.18893) | Concurrent edits and semantic conflict in collaborative code documents. | Collaborative editor/code study, not a Computer-Use benchmark. |

## Relevance to V0 branches

- **GUI+GUI:** distinguish independent actors sharing one screen/input route from ParaGUIBench’s isolated desktops, MACU’s isolated VMs and hierarchical agent frameworks.
- **GUI+CLI:** distinguish two principals sharing GUI-visible and backend state from WeaveBench and CUA-Universe’s single actor using two tool channels. Use CoAgent/AgentRoom/CooperBench/STALE as mechanism controls, not as GUI work already done.
- **GUI+Human:** distinguish a human’s own GUI actions and independently graded intention from DeskCraft’s message simulator, GUIDE’s offline observation of human traces, and OSWorld-Human’s efficiency reference trajectories.

No model-count or task-count comparison establishes this contribution. The critical evidence is runtime topology, separate solvability, joint satisfiability, interaction-attributed failures, recovery and executable evaluator coverage.
