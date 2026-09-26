# TEST_RESULTS

Final verification date: 2026-09-26. Tests use real Docker Ubuntu containers, Xvfb, Tk windows, xdotool desktop actions, guest CLI processes, and mounted files. No mocked environment results are included.

## Automated suite

Command:

```bash
pytest -q --junitxml=outputs/test-results/junit.xml
```

Result: **16 passed, 0 failed, 0 skipped in 27.22s**. Machine-readable report: [`outputs/test-results/junit.xml`](outputs/test-results/junit.xml).

| Test | Result | Evidence checked |
|---|---|---|
| GUI single actor | PASS | Real Tk window visible, real XWD captured, GUI row graded from CSV. |
| CLI single actor | PASS | Guest Python CLI writes row; row graded from CSV. |
| Joint GUI+CLI | PASS | Same environment ID, both exact rows survive, actor-attributed event trace. |
| Stale CSV write conflict | PASS | GUI stale snapshot loses CLI row; evaluator rejects final state and identifies missing C1. |
| Role/evaluator isolation | PASS | GUI context cannot call CLI; CLI cannot observe GUI; neither exposes evaluator. |
| Environment reset | PASS | Dirty state removed by a fresh container/workspace, new GUI window visible, prior container gone. |
| GUI+Human Replay focus recovery | PASS | One real display, three interleaved actor turns, both final window states exact. |
| Stale focus contention | PASS | GUI text goes to Chat after replay steals focus; evaluator rejects both incorrect window state and cross-window contamination. |
| Focus goals independently solvable | PASS | GUI-only and Human Replay-only episodes each satisfy their private goal. |
| Event schema round trip | PASS | V1 version field and contiguous sequence survive JSONL serialization and parsing. |
| Event schema rejection cases | PASS | Unsupported version, missing/extra fields, invalid digest, sequence, malformed JSON, and non-standard constants are rejected. |

## End-to-end smoke

`python scripts/smoke_real_workspace.py` result: **7/7 checks true**. Machine-readable summary: [`outputs/real-smoke/summary.json`](outputs/real-smoke/summary.json). Scenario reports/logs are in the adjacent per-scenario directories; real XWD screenshots are retained.

Final artifact audit confirmed non-empty event logs, valid XWD screenshot files (`1024x768x24`), no running V0 containers, and no leftover runner temporary workspace directories.

`read_event_log` validated all **29 archived event logs / 359 events** across real Docker runs, repeated runs, and the separately labeled simulator outputs. CLI checks for joint CSV, focus, conflict, and simulator logs reported schema version 1.

## Repeated deterministic replay

Command: `python scripts/repeatability_study.py 5`.

Result: **20 fresh-container episodes, all expected outcomes observed, and one final-state hash per policy across five repetitions**. CSV GUI→CLI and CLI→GUI each passed 5/5; focus recovery passed 5/5; stale-focus control failed evaluation as intended in 5/5. Median actor/evaluation/report time was 0.972s, 0.985s, 2.086s, and 1.633s respectively (reset/build excluded). See [`outputs/repeatability/REPORT.md`](outputs/repeatability/REPORT.md) and [`study.json`](outputs/repeatability/study.json).

These results establish deterministic scripted replay on this local Docker/Xvfb setup. They do not establish cross-host reproducibility, model/human performance, or benchmark validity.

## Resolved attempts and unverified areas

- Initial `pytest -q` collection missed the repository import path. Added pytest path configuration; `pytest -q` and `python -m pytest -q` subsequently passed.
- Early smoke issues (missing isolated `DISPLAY` on one xdotool query and Tk child Entry focus after top-level focus) were fixed and the full smoke rerun.
- **UNVERIFIED:** actual OSWorld VM/provider execution, model actors, alternative real applications/backends, truly simultaneous key events, and statistical benchmark validity.
- **NOT RUN:** training, batch data generation, large downloads, GPU workloads.
