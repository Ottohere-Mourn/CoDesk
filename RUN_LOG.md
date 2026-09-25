# RUN_LOG

Date: 2026-09-26 (Asia/Shanghai). Working directory: `/home/mjh/Projects/Shared-Workspace-Benchmark-V0`, standalone Git repository on branch `v0`. The original `Multi-GUI-Agent-Bench` directory was copied as the starting point and left untouched during V0 implementation.

## Environment and access audit

- Host: Python 3.13.2, pytest available, Docker Engine 29.1.3; user `mjh` is in the `docker` group.
- Docker image `ubuntu:22.04` was present locally. Its repo digest is pinned in `Dockerfile` as `sha256:3ba65aa20f86a0fad9df2b2c259c613df006b2e6d0bfcc8a146afb8c525a9751`.
- Installed only the listed, version-pinned guest packages for the isolated image: Python 3.10.6, Tk 3.10.8, Xvfb 21.1.4, xdotool 3.20160805.1, x11-utils 7.7+5, x11-apps 7.7+8, and ca-certificates 20260601. Package inventory is saved in `env/requirements.lock`.
- `desktop_env`/OSWorld and pyautogui were not installed. `/dev/kvm` exists. Host `DISPLAY` is unset; `:0` belongs to user `supermicr`, and authorization failed. No attempt was made to access or alter that session. The V0 runtime therefore uses its own Xvfb inside a disposable container.
- No GPU used; scripted desktop and CSV workloads are CPU-bound.

## Implementation and execution

- Added a common reset/observe/act/snapshot/close `EnvironmentAdapter` contract, `Actor` protocol, role-scoped actor tools, `DualActorOrchestrator`, shared event log, final-state evaluator, Docker/X11 environment, and OSWorld adapter seam.
- Built one container per episode. Xvfb, the Tk GUI app, and CLI Python process all run inside that container. The host temporary directory is mounted at `/workspace`; both actor channels mutate the same `/workspace/shared.csv`.
- Ran `python scripts/smoke_real_workspace.py` after a pinned image build. The five cases passed: GUI single actor, CLI single actor, paired GUI+CLI, stale-write conflict rejected, and reset clears the workspace/restarts the GUI. Evidence is under `outputs/real-smoke/`; XWD files are 1024x768x24 actual X server captures.
- Fixed two implementation issues during smoke development: a window-title query lacked `DISPLAY=:99`, and the standalone pytest console entrypoint omitted the repository root from its import path. Added pytest path configuration; the final smoke and both pytest invocation styles were rerun successfully.
- Removed only containers and temporary workspace directories created by this runner. Final audit found no running V0 containers or leftover `/tmp/swcub-episode-*` directories. No unrelated containers, images, project files, or host configuration were changed.

## Research boundary

The existing literature audit and positioning remain in `docs/`. The real GUI+CLI CSV case is an infrastructure prototype, not benchmark-scale task coverage. Real X11 focus competition is not implemented; `swcub.tasks.focus` remains a simulator. The OSWorld adapter follows the discovered `DesktopEnv` call shape but was not exercised because the package/task assets are absent. No model was connected and no paper claim was tested.
