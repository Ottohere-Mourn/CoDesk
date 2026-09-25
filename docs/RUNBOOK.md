# V0 Runbook

## Prerequisites and boundaries

- Docker Engine is installed and the current user can run containers.
- Python 3.10+ runs the host orchestrator. Host Python dependencies: none. `pytest` is needed for tests.
- The first build uses the locally available Ubuntu 22.04 base digest and installs the small, version-pinned guest packages listed in `env/requirements.lock`.
- The benchmark does not connect to or manipulate the host's active X session. GUI actions happen in an Xvfb server inside a disposable container.

The working directory for V0 is a standalone git repo on branch `v0` (`Shared-Workspace-Benchmark-V0`). It is separate from the initial research-prototype directory.

## Build and run

```bash
docker build --tag swcub-v0:local --file Dockerfile .
python scripts/smoke_real_workspace.py
python -m pytest -q
```

The smoke runner builds automatically, then executes fresh episodes for each scenario. It writes reports and JSONL logs under `outputs/real-smoke/`, including the GUI/CLI CSV case, stale-write control, real GUI+Human Replay focus recovery/failure, and reset. GUI episodes also retain real XWD desktop screenshots. Each action log includes actor ID, action/interface, environment ID, before/after workspace digests and operation result. GUI and CLI actions share the same container and `/workspace/shared.csv` bind mount within each episode.

`python -m swcub.cli run-all --out outputs/simulated-smoke` remains available for fast simulator protocol checks. Those results are not real-environment evidence.

## Actor/evaluator separation

The orchestrator creates role-limited `ActorContext` objects; GUI actors cannot call its CLI method and CLI actors cannot observe/control the GUI. The exact expected rows live only in the `RequiredRowsEvaluator` held by the orchestrator. The evaluator receives the adapter after all actors finish and reads the authoritative CSV privately. It does not use an LLM judge.

## Reset and cleanup

Every reset force-removes only the V0 container identified by that adapter, deletes only its own temporary workspace directory, creates a clean workspace/container, restarts Xvfb and the Tk app, and records old/new environment IDs. `close()` applies the same targeted cleanup. It does not prune Docker images, stop unrelated containers, or remove other files. Keep `outputs/real-smoke/` as run evidence.

## OSWorld path

The host does not have `desktop_env` installed, and the available X11 display belongs to another user; neither is modified. `OSWorldSharedEpisode` conforms to the shared observe/act/reset contract and wraps `DesktopEnv.reset`, `step`, `evaluate`. Supply one `DesktopEnv` per episode and an injected CLI executor connected to that same guest. This bridge is implemented but not run against OSWorld; V0's verified runtime is the pinned Docker/Xvfb app. For OSWorld setup details consult its [official repository](https://github.com/xlang-ai/OSWorld) and pin a release before model evaluation.

## Failure handling

Build or runtime failures stop the smoke with a nonzero exit. Errors are not converted into success scores. A failed actor is recorded with its exception; evaluation then runs on the resulting final workspace so conflict/loss failures remain inspectable.
