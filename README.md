# Shared-Workspace Computer-Use Benchmark V0

A reproducible, scripted two-actor framework for operating one real GUI desktop and shared application state. Verified paths include the Docker/Xvfb cases and a pinned OSWorld V2.1 QEMU Guest with LibreOffice and a Guest-local browser app. Real episodes use actual desktop input and Guest-side state; interface-only contract tests use explicit stubs and are labeled separately. No model calls, training, or data generation are used.

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

The Docker/Xvfb path has GUI+CLI shared CSV and GUI+Human Replay window focus cases. The OSWorld V2.1 Guest path adds GUI+GUI Writer/Calc, GUI+CLI browser state updates, and GUI+Human Replay independent browser form goals. See the real-application section below and `TEST_RESULTS.md` for per-run outcomes and boundaries.

The machine-readable task specs, including independent goals, joint goals, pass/fail interactions, and exact final states, live in [`tasks/v0_manifest.json`](tasks/v0_manifest.json). Validate the catalog with `python scripts/validate_task_manifest.py`.

## Research notes

- [Agent framework review and integration decision](AGENT_FRAMEWORK_REVIEW.md)
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

## Real application episodes

The pinned OSWorld V2.1 Guest also runs LibreOffice Writer/Calc and a Guest-local Chrome workspace. All actor actions share one Guest desktop; each episode writes an actor-attributed JSONL log, screenshots, hidden-state evaluator output, and reset check under `outputs/osworld-v2.1/`.

```bash
scripts/run_osworld_v2_1_office.sh writer-solo
scripts/run_osworld_v2_1_office.sh calc-solo
scripts/run_osworld_v2_1_office.sh sequential
scripts/run_osworld_v2_1_office.sh focus-aware
scripts/run_osworld_v2_1_office.sh naive-interleaving
scripts/run_osworld_v2_1_office.sh writer-osworld-agent-solo
scripts/run_osworld_v2_1_office.sh calc-osworld-agent-solo
scripts/run_osworld_v2_1_office.sh writer-agent-calc-scripted-sequential

scripts/run_osworld_v2_1_browser.sh gui-cli-gui-solo
scripts/run_osworld_v2_1_browser.sh gui-cli-cli-solo
scripts/run_osworld_v2_1_browser.sh gui-cli-refresh
scripts/run_osworld_v2_1_browser.sh gui-cli-stale
scripts/run_osworld_v2_1_browser.sh human-solo
scripts/run_osworld_v2_1_browser.sh agent-solo
scripts/run_osworld_v2_1_browser.sh human-agent-focus-aware
scripts/run_osworld_v2_1_browser.sh human-agent-naive

python scripts/validate_task_instances.py
python scripts/summarize_osworld_runs.py outputs/osworld-v2.1 --successful-only --output outputs/osworld-v2.1/summary.json
```

The `naive-interleaving`, `gui-cli-stale`, and `human-agent-naive` commands return success only when their expected interference is detected. A report's `evaluation.success` remains false for those negative controls by design; `scenario_success` records successful reproduction of the failure condition. These are scripted real-Guest experiments, not model or human performance measurements.

The model office scenarios use the pinned OSWorld V2.1 `Qwen3VLAgent` pipeline with local Qwen3-VL weights. The default is `/mnt/raid1/mjh/models/Qwen/Qwen3-VL-30B-A3B-Instruct`; set `SWCUB_LOCAL_VLM_PATH=/mnt/raid1/mjh/models/Qwen3-VL-4B-Instruct` to use the smaller local checkpoint. Inference is offline and loopback-only through `/opt/miniconda3/bin/python`; set `SWCUB_MODEL_PYTHON` or `SWCUB_LOCAL_VLM_DEVICE` to select another installed runtime/device. The benchmark does not replace OSWorld's prompt, visual history, action format, parser, coordinate conversion, or PyAutoGUI generation. Episode trace artifacts include screenshot hashes/resolution, model response, native action strings and inference time. The framework comparison and adapter boundary are in [AGENT_FRAMEWORK_REVIEW.md](AGENT_FRAMEWORK_REVIEW.md); execution status is in [TEST_RESULTS.md](TEST_RESULTS.md).
