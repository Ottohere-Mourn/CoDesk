# Repeatability Study

bounded scripted replay repeatability check on fresh Docker/Xvfb environments

Episodes: 20 total, 5 per policy.

| Policy | Expected outcomes | Unique final states | Median episode time | Check |
|---|---:|---:|---:|---|
| csv_gui_then_cli | 5/5 | 1 | 0.972s | PASS |
| csv_cli_then_gui | 5/5 | 1 | 0.985s | PASS |
| focus_recovery | 5/5 | 1 | 2.086s | PASS |
| focus_stale_failure | 5/5 | 1 | 1.633s | PASS |

These are scripted infrastructure checks. They provide no model, human, or benchmark-validity evidence.
See `study.json` for trial hashes, environment IDs, and timings.
