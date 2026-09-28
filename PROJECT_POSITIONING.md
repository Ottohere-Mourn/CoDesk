# CoDesk Project Positioning

## Name

**Benchmark name:** CoDesk

**Full name:** Collaborative Desktop Use Benchmark

**Historical name:** Shared-Workspace Computer-Use Benchmark (also referred to as Shared-Workspace Benchmark V0 in earlier checkpoints and artifacts).

CoDesk is the current project name. Historical names remain in prior experiment reports, provenance, stable task identifiers, resource labels and artifact paths. These identifiers are retained so that past results and safety records remain auditable.

## Research question

**How reliably can independently goal-directed Computer-Use Agents complete their own tasks when they share a live, non-exclusive desktop and application state, and how do actions by one actor affect the success, errors and recovery of another?**

The unit of analysis is an episode with multiple actors, individually meaningful goals, one shared environment instance, a reproducible interaction opportunity, and an executable evaluator that checks actor goals and shared-state integrity.

## Scope

CoDesk focuses on interactions that arise because actors share computer-use resources:

- One live graphical desktop session, including active window, keyboard, pointer and application context.
- Shared application objects and backend state where multiple interfaces can observe or change them.
- Independently goal-directed GUI agents, with GUI+GUI as the central track and GUI+CLI and GUI+Human Replay as complementary tracks.
- Solo controls and shared conditions that distinguish actor capability from interaction effects.
- Programmatic evaluation of each actor's goal, joint completion, unintended changes, interaction traces and recovery.

The current prototype has validated focus/input routing and GUI/CLI stale-state conflict mechanisms on the OSWorld V2.1 Guest. These are early mechanism validations, not a complete benchmark or a claim that every interaction category is already implemented.

## Non-goals

- General multi-agent planning, debate, delegation or communication benchmarks where agents do not share a live computer-use environment.
- Measuring collaboration quality for a single decomposed goal as the primary contribution.
- A general GUI automation benchmark for a single agent, or a model leaderboard based on broad task coverage.
- Human-computer interaction usability studies or unconstrained crowdsourced human evaluation.
- Replacing an established GUI agent planner, grounding system or evaluator with a new harness.
- Treating more models, tasks or episodes as novelty by themselves.
- Scoring success with an LLM judge when the task state can be checked programmatically.

## Difference from multi-agent collaboration benchmarks

Many multi-agent benchmarks ask whether agents can coordinate, communicate, delegate or jointly solve a shared objective. CoDesk asks how agents behave when they each have their own valid objective but contend for a shared computer-use surface and shared application state. Coordination may help, but interference can occur without any communication failure: another actor can change focus, replace clipboard contents, switch an application object, invalidate an observation or commit a conflicting update.

Accordingly, CoDesk measures per-actor goal success and joint state integrity under Solo, Sequential, Naive Shared and declared recovery/coordination conditions. It treats a shared desktop session as part of the experimental condition, rather than assuming agents have separate desktops and only share files or messages.

## Positioning guardrail

Do not claim novelty from the name or broad phrase “shared workspace.” For each task, document whether actors use the same desktop session, whether goals are independent and jointly feasible, what resource is contested, the deterministic interaction trigger, the failure signature, the recovery operation, and the hidden-state evaluator predicate. Keep prior competition/overlap audits linked from [`docs/POSITIONING.md`](docs/POSITIONING.md) and refresh them before publication.
