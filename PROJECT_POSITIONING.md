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

CoDesk evaluates hidden-state contention when independent Computer-Use actors use a shared, non-exclusive desktop. The primary contention is session-level GUI state:

- Focus and input routing across windows and applications.
- Session clipboard ownership and generation.
- Application-internal context such as the active browser tab or document.
- Optional native modal/window ownership where dialog state can intercept or block otherwise valid actions.

The task-relevant workspace is the initialized set of application state and artifacts needed for the goals. It does not require a physically shared filesystem. MA-ID may use separate Guest-local filesystems initialized from equivalent fixtures when neither actor needs to observe the other's persistent changes. For a task requiring cross-actor visibility, the authoritative backend topology must be held constant between MA-ID and MA-SD.

GUI+GUI is the central track. GUI+CLI shared persistent-state consistency is an auxiliary control, not the definition of shared-desktop interaction. GUI+Human Replay is a complementary actor composition and cannot substitute for the two-agent comparison.

Round-1 evidence is exploratory: Focus has real Qwen Solo/MA-ID/MA-SD episodes; Clipboard has scripted real-Guest Solo/MA-ID/MA-SD, observer and recovery feasibility; Modal and Application Context have scripted mechanism-level probes only. These are not broad benchmark performance results and do not mean each candidate is a validated task family.

## Non-goals

- General multi-agent planning, debate, delegation or communication benchmarks where agents do not share a live computer-use environment.
- Measuring collaboration quality for a single decomposed goal as the primary contribution.
- A general GUI automation benchmark for a single agent, or a model leaderboard based on broad task coverage.
- Human-computer interaction usability studies or unconstrained crowdsourced human evaluation.
- Replacing an established GUI agent planner, grounding system or evaluator with a new harness.
- Treating more models, tasks or episodes as novelty by themselves.
- Scoring success with an LLM judge when the task state can be checked programmatically.

## Difference from multi-agent collaboration benchmarks

Many multi-agent benchmarks ask whether agents can coordinate, communicate, delegate or jointly solve a shared objective. CoDesk asks how agents behave when they each have their own valid objective but contend for hidden state in a shared computer-use environment. Coordination may help, but interference can occur without any communication failure: another actor can change focus, replace clipboard contents, switch a tab or document, or open a modal dialog that changes input ownership. Persistent shared-backend updates remain an auxiliary comparison.

Accordingly, CoDesk measures per-actor goal success and joint state integrity under Solo, Sequential, Naive Shared and declared recovery/coordination conditions. It treats a shared desktop session as the experimental condition. A shared filesystem is not required unless a task's goals require live cross-actor persistence; when required, backend topology is matched across MA-ID and MA-SD.

## Positioning guardrail

Do not claim novelty from the name or broad phrase “shared workspace.” For each task, document whether actors use the same desktop session, whether goals are independent and jointly feasible, what resource is contested, the deterministic interaction trigger, the failure signature, the recovery operation, and the hidden-state evaluator predicate. Keep prior competition/overlap audits linked from [`docs/POSITIONING.md`](docs/POSITIONING.md) and refresh them before publication.
