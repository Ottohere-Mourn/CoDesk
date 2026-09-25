# POSITIONING

Status: research hypothesis and prototype plan (2026-09-26). The claim of a clear innovation gap is **not yet established**.

## Proposed problem

Measure how independently acting GUI agents, CLI agents, and replayed humans complete tasks while sharing one desktop and/or stateful application backend. The unit of evaluation is a joint execution, including its interaction history, not merely a set of parallel single-agent scores.

Candidate capabilities to measure:

1. joint task completion and per-actor task completion;
2. interference: collateral loss or regression caused by another actor;
3. state awareness and consistency across observations and writes;
4. coordination efficiency: latency, actions, retries, and recovery overhead.

## Working hypotheses (falsifiable)

- H1: shared mutable state creates failures beyond the additive failure rate of isolated tasks.
- H2: GUI focus contention and stale-read/write conflicts produce distinguishable error signatures.
- H3: explicit coordination (freshness checks, focus reacquisition, announcements/claims) reduces interference, with measurable overhead.
- H4: human replay and CLI actors expose interaction patterns not represented by multi-agent benchmarks on isolated desktops.

## Novelty boundary / risks

The novelty should be framed narrowly as **cross-actor interaction under shared desktop and application state**, not as the first parallel GUI benchmark, the first hybrid GUI/CLI benchmark, or the first shared-workspace benchmark. See [RELATED_WORK](RELATED_WORK.md). ParaGUIBench's described shared filesystem across separate desktop instances is the closest GUI coordination neighbor; AgentRoom and SWE-Touch are close shared-workspace analogues. We need a systematic search and direct artifact inspection before making priority claims.

Key threats: trivial toy tasks; one benchmark item standing in for an entire interaction class; scripted timing overfitting; hidden task leakage through evaluators; unequal actor capability; app-level locks/transaction semantics masking conflicts; measurement confounding by VM latency; and an evaluator that rewards a particular trajectory rather than the required final state.

## Intended contribution if validated

An OSWorld-compatible task/harness extension with controlled actor schedules, shared-state instrumentation, resettable scenarios, and deterministic state-based evaluators; a task suite crossing actor types, resource contention, and coordination policy; and empirical analysis separating task solvability from interaction robustness. All are contingent on scale, task-quality review, and comparisons against neighboring work.
