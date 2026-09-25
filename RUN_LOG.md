# RUN_LOG

Date: 2026-09-26 (Asia/Shanghai). Working directory: `/home/mjh/Projects/Shared-Workspace-Benchmark-V0`, standalone Git repository on branch `v0`. The original `Multi-GUI-Agent-Bench` directory was copied as the starting point and left untouched during V0 implementation.

## Environment and access audit

- Host: Python 3.13.2, pytest available, Docker Engine 29.1.3; user `mjh` is in the `docker` group.
- Docker image `ubuntu:22.04` was present locally. Its repo digest is pinned in `Dockerfile` as `sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751`.
- Installed only the listed, version-pinned guest packages for the isolated image: Python 3.10.6, Tk 3.10.8, Xvfb 21.1.4, xdotool 3.20160805.1, x11-utils 7.7+5, x11-apps 7.7+8, and ca-certificates 20260601. Package inventory is saved in `env/requirements.lock`.
- `desktop_env`/OSWorld and pyautogui were not installed. `/dev/kvm` exists. Host `DISPLAY` is unset; `:0` belongs to user `supermicr`, and authorization failed. No attempt was made to access or alter that session. V0 uses isolated Xvfb inside disposable containers.
- No GPU used; scripted desktop and CSV workloads are CPU-bound.

## Implementation and execution

- Added a common reset/observe/act/snapshot/close `EnvironmentAdapter`, actor protocol, role-scoped actor tools, `DualActorOrchestrator`, shared event log, final-state evaluators, Docker/X11 environment, and OSWorld adapter seam.
- Each episode uses one Ubuntu container, one Xvfb display and one temporary workspace. The GUI and CLI channels share `/workspace/shared.csv`; the GUI and Human Replay channels interact with two windows on one X11 display.
- Final `python scripts/smoke_real_workspace.py` run passed all seven checks: GUI-only CSV, CLI-only CSV, joint GUI+CLI, stale CSV write rejected, recovered GUI+Human focus task, stale-focus failure detected, and environment reset.
- Final `pytest -q --junitxml=outputs/test-results/junit.xml` passed all nine real environment tests. Reports, JSONL logs, XWD screen captures and final application state are under `outputs/real-smoke/`.
- Fixed two implementation issues during development: a window-title query initially lacked `DISPLAY=:99`; and the pytest console entrypoint initially omitted repository import configuration. Both were fixed and rerun. The first focus recovery attempt also showed that X11 top-level focus alone did not set the Tk Entry focus in Xvfb; adding a real pointer click to the selected entry fixed it. The stale-focus control then reproduced the intended misdirected text.
- Removed only containers and temporary workspace directories created by this runner. Final audit found no running V0 containers or leftover `/tmp/swcub-episode-*` directories. No unrelated containers, images, project files, or host configuration were changed.

## Research boundary

The real CSV and two-window focus cases are controlled infrastructure probes, not benchmark-scale task coverage. The OSWorld adapter follows the discovered `DesktopEnv` call shape but was not exercised because the package/task assets are absent. No model was connected and no paper claim or statistical hypothesis was tested.
