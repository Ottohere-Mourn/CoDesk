# Shared-Workspace Computer-Use Benchmark V0

A reproducible, scripted two-actor framework for operating one real GUI desktop and one shared workspace. The verified path uses one Ubuntu 22.04 Docker container per episode, one Xvfb display, a real Tk desktop application, `xdotool` GUI input, and CLI commands in that same container. Both actors read and change the same mounted `shared.csv`. No model calls, mocks, training, or data generation are used.

## Quick start

Requirements: Docker Engine with permission to run containers, Python 3.10+, and pytest for the automated suite. The repository pins the Ubuntu base image digest and guest package versions in `Dockerfile` / `env/requirements.lock`. The first image build downloads only the named Ubuntu packages. No GPU is required.

```bash
python scripts/smoke_real_workspace.py
python -m pytest -q
```

The smoke script builds `swcub-v0:local` if needed and runs GUI-only, CLI-only, GUI+CLI, an intentional stale-write conflict, and an environment-reset case. Full reports, event logs, CSV outputs, and XWD screenshots are written to `outputs/real-smoke/`.

To build the image separately:

```bash
docker build --tag swcub-v0:local --file Dockerfile .
```

## Runtime structure

- `swcub.environment.EnvironmentAdapter`: shared reset/observe/act/snapshot/close contract.
- `swcub.environment.DockerX11Workspace`: real Docker/Xvfb/Tk implementation; one `environment_id` maps to one container and one mounted workspace.
- `swcub.actors.Actor`: actor protocol. Role-scoped `ActorContext` allows GUI tools to GUI actors and CLI tools to CLI actors; neither receives the evaluator or hidden expected rows.
- `swcub.orchestrator.DualActorOrchestrator`: executes a pinned actor schedule in one environment, records actor-attributed actions, and calls the evaluator after actors stop.
- `swcub.evaluator`: exact CSV state predicates and an OSWorld evaluator bridge.
- `swcub.osworld_adapter.OSWorldSharedEpisode`: compatible adapter seam for a caller-provided OSWorld `DesktopEnv` and an injected CLI executor bound to the same guest.

The real GUI/CLI CSV workflow is the V0 end-to-end benchmark case. The earlier focus-window case in `swcub.tasks.focus` is a deterministic state simulator only; real X11 focus contention is not yet implemented.

## Research notes

- [POSITIONING](docs/POSITIONING.md)
- [RELATED_WORK](docs/RELATED_WORK.md)
- [TASK_TAXONOMY](docs/TASK_TAXONOMY.md)
- [EVALUATION](docs/EVALUATION.md)
- [Data production plan](docs/DATA_PRODUCTION.md)
- [RUN_LOG](RUN_LOG.md), [TEST_RESULTS](TEST_RESULTS.md), [NEXT_STEPS](NEXT_STEPS.md)

The benchmark's novelty remains a hypothesis. V0 demonstrates the infrastructure and a controlled shared-file interaction only; it supports no model-performance or paper-level conclusion.
