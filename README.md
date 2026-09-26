# Shared-Workspace Computer-Use Benchmark V0

A reproducible, scripted two-actor framework for operating one real GUI desktop and shared application state. The verified path uses one Ubuntu 22.04 Docker container per episode, one Xvfb display, real Tk desktop applications, `xdotool` GUI input, and guest CLI commands. In CSV-001 both actors share the mounted `shared.csv`; in FOCUS-001 they share the same active desktop and keyboard focus. No model calls, mocks, training, or data generation are used.

## Quick start

Requirements: Docker Engine with permission to run containers, Python 3.10+, and pytest for the automated suite. The repository pins the Ubuntu base image digest and guest package versions in `Dockerfile` / `env/requirements.lock`. The first image build installs only the named Ubuntu packages and their required dependencies. No GPU is required.

```bash
python scripts/smoke_real_workspace.py
python -m pytest -q
python scripts/repeatability_study.py 5
python scripts/validate_task_manifest.py
```

The smoke script builds `swcub-v0:local` if needed and runs GUI-only, CLI-only, GUI+CLI, an intentional stale-write conflict, and an environment-reset case. Full reports, event logs, CSV/GUI-state outputs, and XWD screenshots are written to `outputs/real-smoke/`. The runner also checks focus recovery and the stale-focus failure control.

To run the same checks against an already-built image tag without rebuilding it, use `python scripts/smoke_real_workspace.py --image swcub-v0:clean-check --skip-build`.

The bounded repeatability script starts fresh real containers for each trial (default: five per policy) and checks both CSV actor orders, focus recovery, and stale-focus failure. It writes per-trial reports/event logs plus state hashes and timings under `outputs/repeatability/`. This characterizes deterministic scripted replay only. Use `python scripts/repeatability_study.py 1` for a shorter check; the accepted range is 1–20.

To build the image separately:

```bash
docker build --tag swcub-v0:local --file Dockerfile .
```

## Runtime structure

- `swcub.environment.EnvironmentAdapter`: shared reset/observe/act/snapshot/close contract.
- `swcub.environment.DockerX11Workspace`: real Docker/Xvfb/Tk implementation; one `environment_id` maps to one container and one mounted workspace.
- `swcub.actors.Actor`: actor protocol. Role-scoped `ActorContext` allows GUI tools to GUI actors and CLI tools to CLI actors; GUI observations include the captured XWD screenshot bytes. Actors do not receive the evaluator or hidden expected rows.
- `swcub.orchestrator.DualActorOrchestrator`: executes a pinned actor schedule in one environment, records actor-attributed actions, and calls the evaluator after actors stop.
- `swcub.evaluator`: exact CSV state predicates and an OSWorld evaluator bridge.
- `swcub.osworld_adapter.OSWorldSharedEpisode`: compatible adapter seam for a caller-provided OSWorld `DesktopEnv` and an injected CLI executor bound to the same guest.

V0 has two real end-to-end cases: GUI+CLI shared CSV read/write, and GUI+Human Replay focus competition across two Tk windows. Both run in one actual Xvfb display inside a single Docker container. `swcub.tasks.focus` remains a simulator/protocol control; real focus validation is in the Docker-backed focus actors and app.

The machine-readable task specs, including independent goals, joint goals, pass/fail interactions, and exact final states, live in [`tasks/v0_manifest.json`](tasks/v0_manifest.json). Validate the catalog with `python scripts/validate_task_manifest.py`.

## Research notes

- [POSITIONING](docs/POSITIONING.md)
- [RELATED_WORK](docs/RELATED_WORK.md)
- [TASK_TAXONOMY](docs/TASK_TAXONOMY.md)
- [EVALUATION](docs/EVALUATION.md)
- [Data production plan](docs/DATA_PRODUCTION.md)
- [RUN_LOG](RUN_LOG.md), [TEST_RESULTS](TEST_RESULTS.md), [NEXT_STEPS](NEXT_STEPS.md)

## OSWorld V2.1 real Guest path

The project now has an additional real OSWorld Guest adapter path. Follow [ENV_SETUP.md](ENV_SETUP.md) to reproduce the pinned V2.1 setup, local QEMU/KVM runtime fallback, official quickstart, GUI+CLI shared CSV/conflict episodes, and GUI+Human Replay two-window focus episodes. Both branches use one Guest per episode and hidden programmatic final-state checks. The V2.1 gated official task set and official scoring remain unavailable.

To run the deliberate lost-update control, pass `--scenario stale-overwrite` to the same launcher. A successful control result means the evaluator caught the missing CLI row and reset still cleared the Guest; see [ENV_SETUP.md](ENV_SETUP.md) for the command and evidence files.

The benchmark's novelty remains a hypothesis. V0 demonstrates controlled shared-file and focus interactions only; it supports no model-performance or paper-level conclusion.
