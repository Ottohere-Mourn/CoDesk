# CoDesk

**CoDesk (Collaborative Desktop Use Benchmark)** studies what changes when independently goal-directed GUI agents use a live desktop whose focus, input devices, clipboard, application context, selection, and undo history are not exclusive to one actor.

## Research question

How do independent computer-use agents perform when they act alone, use independent desktop sessions, or share one live desktop session? The main comparison is:

- **Solo:** each actor completes its goal without partner actions.
- **MA-ID:** multiple actors have independent desktop/input sessions.
- **MA-SD:** actors share one live desktop control session.

For a valid MA-ID/MA-SD comparison, task-relevant initial state, goals, schedule, budgets, applications, backend, evaluator, and reset must be equivalent. The intended treatment is desktop-session sharing. See the [benchmark overview](docs/research/BENCHMARK_OVERVIEW.md) and [protocol](docs/research/CODESK_PROTOCOL_V1.md).

## V1 suite

The offline final suite contains **5 families, 30 workflow templates, and 600 fixed task instances** (20 instances per workflow), across **Writer, Calc, Browser, and Terminal**. “Fixed tasks” means reproducible task instances in the offline suite; it does not mean 600 completed Guest or model episodes.

`benchmarks/codesk_v1_final/` is the **only current V1 suite**. `benchmarks/codesk_v1/` is a legacy prototype and is retained for historical reproducibility; it is not the current task catalog.

**Current status: `OFFLINE_FINAL_SUITE_READY`. This is not `FULL_HANDOFF_READY`.** The suite and runtime plans are present, but the 5-family real Guest smoke and formal model evaluation remain to be completed. Runtime plans are not proof of live runtime validation.

## Quick Start

Start with the [Quick Start guide](docs/getting-started/QUICK_START.md). It separates offline manifest/oracle validation from commands that launch a real Guest. Current top priorities and experiment gates are in the [handoff](docs/handoff/HANDOFF.md).

At a glance, the offline suite audit command is:

```bash
python scripts/audit_instance_suite.py \
  benchmarks/codesk_v1_final/manifest.jsonl \
  --suite-root benchmarks/codesk_v1_final \
  --output /tmp/codesk-v1-audit.json
```

Real Guest execution is explicitly marked **PENDING REAL-GUEST VALIDATION** in the guide. Do not start a full run before the representative workflow smoke passes.

## Repository map

- `swcub/` — actor, environment, orchestrator, runtime binding, provenance, and task logic.
- `benchmarks/codesk_v1_final/` — current V1 families, workflows, fixed instances, fixtures, evaluators, and manifests.
- `scripts/` — validation, runner, aggregation, environment, and development utilities.
- `tests/` — offline and interface tests.
- `docs/` — research, getting started, adapter interface, handoff, and archive index.

## Documents

- [Benchmark overview](docs/research/BENCHMARK_OVERVIEW.md)
- [Quick Start and run commands](docs/getting-started/QUICK_START.md)
- [Agent adapter interface](docs/getting-started/AGENT_ADAPTER.md)
- [Current handoff](docs/handoff/HANDOFF.md)
- [Historical document index](docs/archive/README.md)
- [Evaluation protocol](docs/research/CODESK_PROTOCOL_V1.md)
- [Task instance schema](docs/data/INSTANCE_SCHEMA_V1.md)

## Evidence boundary

Offline structure/oracle validation, scripted Guest episodes, and model-agent episodes are separate evidence levels. A task failure is attributed to shared interaction only when exposure and state/action evidence support it; scheduled exposure, observed interference, outcome, and recovery are reported separately. Historical reports remain available and may describe older protocols or superseded task counts; use the current handoff and final manifest for the present suite status.
