# TEST_RESULTS

Final verification date: 2026-09-26. Tests use the real pinned Docker image, Xvfb display, Tk app, xdotool GUI actions, container CLI actions, and a shared mounted file. No mocked environment results are included.

## Automated suite

Command:

```bash
pytest -q --junitxml=outputs/test-results/junit.xml
```

Result: **6 passed, 0 failed, 0 skipped in 13.99s**. Machine-readable report: [`outputs/test-results/junit.xml`](outputs/test-results/junit.xml).

| Test | Result | Evidence checked |
|---|---|---|
| GUI single actor | PASS | Real Tk window visible; XWD screenshot captured; GUI row graded from CSV. |
| CLI single actor | PASS | Python CLI process in guest writes row; row graded from CSV. |
| Joint GUI+CLI | PASS | Both actor contexts report the same environment ID; exact two-row final CSV; actor-attributed GUI/CLI/evaluator events. |
| Stale-write conflict | PASS | Intentional GUI stale snapshot overwrites CLI row; evaluator rejects the lost update and reports missing C1. |
| Role/evaluator isolation | PASS | GUI context cannot call CLI, CLI context cannot observe GUI, and neither context exposes an evaluator. |
| Environment reset | PASS | Dirty CSV is replaced by a fresh container/workspace, new GUI becomes visible, old state is absent. |

## End-to-end smoke

`python scripts/smoke_real_workspace.py` result: all 5 checks true. Machine-readable summary: [`outputs/real-smoke/summary.json`](outputs/real-smoke/summary.json). Joint state and conflict reports/logs are saved under `outputs/real-smoke/joint/` and `outputs/real-smoke/conflict/`.

Final artifact audit confirmed all five scenario event logs are non-empty, screenshot artifact type is XWD at 1024x768x24, V0 containers are stopped, and runner temporary workspace directories were removed.

## Resolved attempts and unverified areas

- An initial `pytest -q` invocation failed collection because the console entrypoint omitted the project root. Added pytest `pythonpath` configuration and reran the same command; the final six-test run passes. `python -m pytest -q` also passed all six tests before the final clean run.
- An early smoke failed when a window-title query omitted the isolated `DISPLAY`; fixed and reran all cases successfully.
- **UNVERIFIED:** actual OSWorld VM/provider execution, model actors, real focus-contention case, concurrency under truly simultaneous input, alternative app backends, and statistical benchmark validity.
- **NOT RUN:** training, batch data generation, large downloads, GPU workloads.
