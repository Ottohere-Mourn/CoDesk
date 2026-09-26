# POSITIONING

Status: research hypothesis revised after the GUI/Desktop novelty audit (2026-09-26).

Shared-Workspace Benchmark V0 studies **Multi-Actor Computer Use**: separate, independently goal-directed principals acting through GUI, CLI or Human Replay while sharing a live desktop/application workspace. The planned branches are GUI+GUI, GUI+CLI and GUI+Human. Shared-file conflicts are a useful auxiliary task family; the central evaluation is each actor’s outcome, joint application state, cross-actor interaction and recovery.

The current audit found **no direct collision** among the reviewed GUI/Desktop/Computer-Use benchmarks for independently tasked actors concurrently sharing one desktop session and being evaluated on both goals and interference. Important partial GUI overlaps include ParaGUIBench (concurrent GUI workers, shared files and documented same-document edit failures, but isolated desktops and planner-decomposed tasks), MACU (parallel CUA workers in isolated VMs), PC-Agent/UFO (hierarchical agent roles), MMBench-GUI L4 (one agent coordinating applications), and DeskCraft/GUIDE (user messages or recorded human activity). See [POSITIONING_REVISION.md](../POSITIONING_REVISION.md), [NOVELTY_AUDIT.md](../NOVELTY_AUDIT.md), and [OVERLAP_MATRIX.md](../OVERLAP_MATRIX.md).

CoAgent, AgentRoom, CooperBench, STALE, SWE-Touch and CodeCRDT are cross-domain concurrency/shared-state neighbors. Their independent/joint correctness checks and recovery controls are useful methodological precedents; they are not GUI Agent Benchmarks and do not occupy the GUI mainline.

This is a bounded evidence claim, not a priority claim. Before publication, refresh citation and artifact searches and verify the precise desktop/session topology. Each task must have two independently solvable goals, a jointly satisfiable state, a reproducible interaction effect, and hidden executable state predicates for per-actor and joint evaluation.
